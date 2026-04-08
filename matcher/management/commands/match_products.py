import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from datastore.mongo import db
from normalizer.category import load_canonical_categories, get_subcategory_ids
from matcher.dedup import dedup_within_branch
from matcher.matchers.barcode import match_by_barcode
from matcher.matchers.exact import match_by_exact_fields
from matcher.matchers.structured import match_by_structured_fields, match_by_structured_sparkling
from matcher.matchers.fuzzy import match_by_fuzzy
from matcher.golden import create_golden_record_consensus


class Command(BaseCommand):
    help = "Match normalized products across branches and create golden records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            required=True,
            choices=["intra_marketplace", "cross_source", "passthrough"],
        )
        parser.add_argument(
            "--market",
            required=True,
            choices=["araz", "bazarstore", "bravo", "neptun"],
        )
        parser.add_argument(
            "--source-type",
            default="wolt",
            choices=["wolt", "website", "all"],
        )
        parser.add_argument(
            "--category",
            required=True,
            help="Canonical category slug",
        )
        parser.add_argument(
            "--fuzzy-threshold",
            type=float,
            default=0.85,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
        )

    def handle(self, *args, **options):
        market = options["market"]
        source_type = options["source_type"]
        category_slug = options["category"]
        fuzzy_threshold = options["fuzzy_threshold"]
        dry_run = options["dry_run"]
        scope = options["scope"]

        self.stdout.write(
            f"[START] Match | scope={scope}, market={market}, source={source_type}, "
            f"category={category_slug}, fuzzy_threshold={fuzzy_threshold}"
        )

        if scope == "cross_source":
            return self._handle_cross_source(market, category_slug, fuzzy_threshold, dry_run)

        if scope == "passthrough":
            return self._handle_passthrough(market, source_type, category_slug, dry_run)


        # Determine target canonical category IDs
        canonical_cats = load_canonical_categories()
        target_ids = get_subcategory_ids(canonical_cats, category_slug)

        # Load normalized products (per-market collections)
        collection_map = {
            "wolt": f"wolt_{market}_normalised_products",
            "website": f"website_{market}_normalised_products",
        }

        products = []
        for src, coll_name in collection_map.items():
            if source_type not in (src, "all"):
                continue
            coll = db[coll_name]
            query = {"canonical_category_id": {"$in": list(target_ids)}}
            docs = list(coll.find(query))
            products.extend(docs)
            self.stdout.write(f"  Loaded {len(docs)} from {coll_name}")

        self.stdout.write(f"  Total products: {len(products)}")

        # Step 1: Within-branch dedup
        before_dedup = len(products)
        products = dedup_within_branch(products)
        self.stdout.write(f"  After within-branch dedup: {len(products)} (removed {before_dedup - len(products)})")

        # Step 2: Barcode matching
        barcode_groups, remaining = match_by_barcode(products)
        self.stdout.write(f"  Barcode matches: {len(barcode_groups)} groups ({sum(len(g) for g in barcode_groups)} products)")

        # Step 3: Exact field matching
        exact_groups, remaining = match_by_exact_fields(remaining)
        self.stdout.write(f"  Exact matches:   {len(exact_groups)} groups ({sum(len(g) for g in exact_groups)} products)")

        # Step 4: Structured field matching (brand + size + unit + pack_size + flavor)
        structured_groups, remaining = match_by_structured_fields(remaining)
        self.stdout.write(f"  Structured matches: {len(structured_groups)} groups ({sum(len(g) for g in structured_groups)} products)")

        # Step 5: Structured sparkling matching (brand + size + sparkling + packaging + flavor)
        sparkling_groups, remaining = match_by_structured_sparkling(remaining)
        self.stdout.write(f"  Sparkling matches:  {len(sparkling_groups)} groups ({sum(len(g) for g in sparkling_groups)} products)")

        # Step 6: Fuzzy matching
        fuzzy_groups, remaining, fuzzy_scores = match_by_fuzzy(remaining, threshold=fuzzy_threshold)
        self.stdout.write(f"  Fuzzy matches:   {len(fuzzy_groups)} groups ({sum(len(g) for g in fuzzy_groups)} products)")

        self.stdout.write(f"  Unmatched:       {len(remaining)} products (single-branch only)")

        # Build match documents with provenance
        now = datetime.now(timezone.utc)
        match_docs = []

        # Cascade provenance: how many groups formed at each tier
        provenance_cascade = {
            "total_products": before_dedup,
            "after_dedup": len(products),
            "barcode_groups": len(barcode_groups),
            "exact_groups": len(exact_groups),
            "structured_groups": len(structured_groups),
            "sparkling_groups": len(sparkling_groups),
            "fuzzy_groups": len(fuzzy_groups),
            "unmatched": len(remaining),
        }

        def _make_doc(group, match_type, confidence, needs_review=False, extra=None):
            golden = create_golden_record_consensus(group)
            doc = {
                "match_group_id": str(uuid.uuid4()),
                "scope": "intra_marketplace",
                "marketplace": market,
                "match_type": match_type,
                "match_confidence": confidence,
                "needs_review": needs_review,
                "products": [
                    {"source_type": p["source_type"], "branch": p["branch"], "product_id": p["product_id"]}
                    for p in group
                ],
                "golden_record": golden,
                "provenance": provenance_cascade,
                "created_at": now,
            }
            if extra:
                doc.update(extra)
            return doc

        for group in barcode_groups:
            match_docs.append(_make_doc(group, "barcode", 1.0))

        for group in exact_groups:
            match_docs.append(_make_doc(group, "exact", 0.95))

        for group in structured_groups:
            match_docs.append(_make_doc(group, "structured", 0.92))

        for group in sparkling_groups:
            match_docs.append(_make_doc(group, "structured_sparkling", 0.92))

        for group, score in zip(fuzzy_groups, fuzzy_scores):
            match_docs.append(_make_doc(group, "fuzzy", score, needs_review=True))

        # Single-branch products also get golden records (unmatched)
        for product in remaining:
            match_docs.append(_make_doc([product], "single", 1.0))

        # Summary
        type_counts = Counter(d["match_type"] for d in match_docs)
        self.stdout.write(f"\n  Golden records created: {len(match_docs)}")
        for t, c in type_counts.most_common():
            self.stdout.write(f"    {t}: {c}")

        # Write to MongoDB
        if not dry_run:
            matches_coll = db[f"{market}_product_matches"]
            # Clear previous matches for this scope
            matches_coll.delete_many({
                "scope": "intra_marketplace",
            })
            if match_docs:
                matches_coll.insert_many(match_docs)
            self.stdout.write(self.style.SUCCESS(f"\n  [DONE] Written {len(match_docs)} match groups to 'product_matches'"))
        else:
            self.stdout.write(self.style.WARNING("\n  [DRY RUN] No data written."))

    def _handle_passthrough(self, market, source_type, category_slug, dry_run):
        """Create golden records directly from normalized products (no matching).

        Used for single-source marketplaces like Bazarstore where each
        normalized product becomes its own golden record.
        """
        canonical_cats = load_canonical_categories()
        target_ids = get_subcategory_ids(canonical_cats, category_slug)

        # Load normalized products
        collection_map = {
            "wolt": f"wolt_{market}_normalised_products",
            "website": f"website_{market}_normalised_products",
        }

        products = []
        for src, coll_name in collection_map.items():
            if source_type not in (src, "all"):
                continue
            coll = db[coll_name]
            query = {"canonical_category_id": {"$in": list(target_ids)}}
            docs = list(coll.find(query))
            products.extend(docs)
            self.stdout.write(f"  Loaded {len(docs)} from {coll_name}")

        self.stdout.write(f"  Total products: {len(products)}")

        # Create one golden record per product
        now = datetime.now(timezone.utc)
        match_docs = []

        for product in products:
            golden = create_golden_record_consensus([product])
            match_docs.append({
                "match_group_id": str(uuid.uuid4()),
                "scope": "passthrough",
                "marketplace": market,
                "match_type": "passthrough",
                "match_confidence": 1.0,
                "needs_review": False,
                "products": [{
                    "source_type": product["source_type"],
                    "branch": product.get("branch"),
                    "product_id": product["product_id"],
                }],
                "golden_record": golden,
                "provenance": {
                    "total_products": len(products),
                    "passthrough": True,
                },
                "created_at": now,
            })

        # Category distribution
        cat_counts = Counter()
        for doc in match_docs:
            cat_id = doc["golden_record"].get("canonical_category_id")
            cat_name = canonical_cats.get(cat_id, {}).get("name", "?")
            cat_counts[f"{cat_id} ({cat_name})"] += 1

        self.stdout.write(f"\n  Golden records: {len(match_docs)}")
        for cat, count in cat_counts.most_common():
            self.stdout.write(f"    {cat}: {count}")

        if not dry_run:
            matches_coll = db[f"{market}_product_matches"]
            matches_coll.delete_many({"scope": "passthrough"})
            if match_docs:
                matches_coll.insert_many(match_docs)
            self.stdout.write(self.style.SUCCESS(
                f"\n  [DONE] Written {len(match_docs)} passthrough golden records"
            ))
        else:
            self.stdout.write(self.style.WARNING("\n  [DRY RUN] No data written."))

    def _handle_cross_source(self, market, category_slug, fuzzy_threshold, dry_run):
        """Match website products against existing Wolt golden records.

        Uses the CrossSourceMatcher with 3-tier hybrid approach:
        Tier 1 (EXACT) → Tier 2 (EXACT-ON-SHARED) → Tier 3 (SCORING)
        """
        from matcher.cross_source_matcher import CrossSourceMatcher

        canonical_cats = load_canonical_categories()
        target_ids = get_subcategory_ids(canonical_cats, category_slug)

        # Load website products
        website_coll = db[f"website_{market}_normalised_products"]
        web_products = list(website_coll.find({
            "canonical_category_id": {"$in": list(target_ids)},
        }))
        self.stdout.write(f"  Website products: {len(web_products)}")

        # Load existing Wolt golden records
        matches_coll = db[f"{market}_product_matches"]
        golden_docs = list(matches_coll.find({
            "scope": "intra_marketplace",
        }))
        self.stdout.write(f"  Wolt golden records: {len(golden_docs)}")

        # Preload Wolt prices for golden records
        golden_prices = {}
        wolt_norm_coll = db[f"wolt_{market}_normalised_products"]
        for doc in golden_docs:
            wolt_prods = [p for p in doc.get("products", []) if p.get("source_type") == "wolt"]
            if wolt_prods:
                norm = wolt_norm_coll.find_one({
                    "product_id": wolt_prods[0]["product_id"],
                    "branch": wolt_prods[0]["branch"],
                })
                if norm and norm.get("price"):
                    golden_prices[doc["_id"]] = norm["price"]

        # Two-pass matching: subcategory-first, then cross-subcategory
        matcher = CrossSourceMatcher(
            score_threshold=0.70,
            review_threshold=0.50,
        )

        # Group by subcategory
        web_by_subcat = defaultdict(list)
        for wp in web_products:
            web_by_subcat[wp["canonical_category_id"]].append(wp)

        golden_by_subcat = defaultdict(list)
        for doc in golden_docs:
            golden_by_subcat[doc["golden_record"]["canonical_category_id"]].append(doc)

        # Pass 1: Match within same subcategory
        matched = []
        pass1_unmatched = []
        pass1_stats = Counter()

        for subcat_id, subcat_web in web_by_subcat.items():
            subcat_golden = golden_by_subcat.get(subcat_id, [])
            if not subcat_golden:
                pass1_unmatched.extend(subcat_web)
                pass1_stats["no_candidates"] += len(subcat_web)
                continue
            m, um, st = matcher.match(subcat_web, subcat_golden, golden_prices=golden_prices)
            matched.extend(m)
            pass1_unmatched.extend(um)
            pass1_stats += st

        # Pass 2: Match unmatched against ALL golden records (cross-subcategory)
        pass2_stats = Counter()
        unmatched_web = pass1_unmatched

        if pass1_unmatched:
            m2, unmatched_web, pass2_stats = matcher.match(
                pass1_unmatched, golden_docs, golden_prices=golden_prices,
            )
            matched.extend(m2)

        # Report
        total_matched = len(matched)
        pct = total_matched / len(web_products) * 100 if web_products else 0
        pass1_matched = sum(v for k, v in pass1_stats.items() if k not in ("no_candidates", "unmatched"))
        self.stdout.write(f"\n  Pass 1 (same subcategory): {pass1_matched} matched")
        for tier in ["exact", "exact_shared", "scoring", "scoring_review", "no_candidates", "unmatched"]:
            if pass1_stats[tier]:
                self.stdout.write(f"    {tier:20s}: {pass1_stats[tier]}")

        if sum(v for k, v in pass2_stats.items() if k not in ("no_candidates", "unmatched")):
            pass2_matched = sum(v for k, v in pass2_stats.items() if k not in ("no_candidates", "unmatched"))
            self.stdout.write(f"  Pass 2 (cross subcategory): {pass2_matched} matched")
            for tier in ["exact", "exact_shared", "scoring", "scoring_review", "no_candidates", "unmatched"]:
                if pass2_stats[tier]:
                    self.stdout.write(f"    {tier:20s}: {pass2_stats[tier]}")

        self.stdout.write(f"\n  Total matched: {total_matched}/{len(web_products)} ({pct:.1f}%)")
        self.stdout.write(f"  Unmatched: {len(unmatched_web)}")

        # Show scoring match samples
        scoring_pairs = [(wp, gd, c) for wp, gd, t, c in matched if t in ("scoring", "scoring_review")]
        if scoring_pairs:
            self.stdout.write(f"\n  === Scoring match samples (first 10) ===")
            for wp, gd, conf in scoring_pairs[:10]:
                self.stdout.write(f"    [{conf:.2f}] Website: {wp['original_name']}")
                self.stdout.write(f"           Wolt:    {gd['golden_record']['original_name']}")

        # Write results
        now = datetime.now(timezone.utc)
        updates = 0
        new_records = []

        if not dry_run:
            # Clear previous cross-source results
            matches_coll.update_many(
                {"has_website": True, "match_type": {"$ne": "website_only"}},
                {
                    "$pull": {"products": {"source_type": "website"}},
                    "$unset": {
                        "golden_record.website_barcode": "",
                        "golden_record.website_price": "",
                        "has_website": "",
                    },
                },
            )
            matches_coll.delete_many({"match_type": "website_only"})

            for wp, golden_doc, match_type, confidence in matched:
                needs_review = match_type == "scoring_review"
                matches_coll.update_one(
                    {"_id": golden_doc["_id"]},
                    {
                        "$push": {"products": {
                            "source_type": "website",
                            "branch": None,
                            "product_id": wp["product_id"],
                            "match_type": match_type,
                            "match_confidence": confidence,
                        }},
                        "$set": {
                            "golden_record.website_barcode": wp.get("website_barcode"),
                            "golden_record.website_price": wp.get("price"),
                            "has_website": True,
                            "needs_review": needs_review or None,
                        },
                    },
                )
                updates += 1

            for wp in unmatched_web:
                golden = create_golden_record_consensus([wp])
                golden["website_barcode"] = wp.get("website_barcode")
                golden["website_price"] = wp.get("price")
                new_records.append({
                    "match_group_id": str(uuid.uuid4()),
                    "scope": "intra_marketplace",
                    "marketplace": market,
                    "match_type": "website_only",
                    "match_confidence": 1.0,
                    "needs_review": False,
                    "has_website": True,
                    "products": [{
                        "source_type": "website",
                        "branch": None,
                        "product_id": wp["product_id"],
                    }],
                    "golden_record": golden,
                    "created_at": now,
                })

            if new_records:
                matches_coll.insert_many(new_records)

            self.stdout.write(self.style.SUCCESS(
                f"\n  [DONE] Updated {updates} golden records, created {len(new_records)} website-only records"
            ))
        else:
            self.stdout.write(self.style.WARNING("\n  [DRY RUN] No data written."))
