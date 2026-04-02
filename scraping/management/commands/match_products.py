import uuid
from collections import Counter
from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from scraping.mongo import db
from scraping.normalization.category import load_canonical_categories, get_subcategory_ids
from scraping.identification.dedup import dedup_within_branch
from scraping.identification.matchers.barcode import match_by_barcode
from scraping.identification.matchers.fuzzy import _similarity
from scraping.identification.matchers.exact import match_by_exact_fields
from scraping.identification.matchers.structured import match_by_structured_fields, match_by_structured_sparkling
from scraping.identification.matchers.fuzzy import match_by_fuzzy
from scraping.identification.golden import create_golden_record_consensus


class Command(BaseCommand):
    help = "Match normalized products across branches and create golden records"

    def add_arguments(self, parser):
        parser.add_argument(
            "--scope",
            required=True,
            choices=["intra_marketplace", "cross_source"],
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

    def _handle_cross_source(self, market, category_slug, fuzzy_threshold, dry_run):
        """Match website products against existing Wolt golden records."""
        canonical_cats = load_canonical_categories()
        target_ids = get_subcategory_ids(canonical_cats, category_slug)

        # Load website products (per-market collection)
        website_coll = db[f"website_{market}_normalised_products"]
        web_products = list(website_coll.find({
            "canonical_category_id": {"$in": list(target_ids)},
        }))
        self.stdout.write(f"  Website products: {len(web_products)}")

        # Load existing Wolt golden records (per-market collection)
        matches_coll = db[f"{market}_product_matches"]
        golden_docs = list(matches_coll.find({
            "scope": "intra_marketplace",
        }))
        self.stdout.write(f"  Wolt golden records: {len(golden_docs)}")

        # Build lookups
        golden_by_key = {}       # (brand, name, size, unit, packaging, flavor) → doc
        golden_by_key_no_pkg = {}  # (brand, name, size, unit, flavor) → [docs]
        golden_by_structured = {}  # (brand, size, unit, pack_size, flavor) → doc
        golden_by_sparkling = {}   # (brand, size, unit, pack_size, is_sparkling, packaging, flavor) → doc
        golden_prices = {}       # golden doc _id → average price from Wolt
        wolt_norm_coll = db[f"wolt_{market}_normalised_products"]

        for doc in golden_docs:
            gr = doc["golden_record"]
            key = (
                gr.get("normalized_brand") or "",
                gr.get("normalized_name") or "",
                gr.get("size"),
                gr.get("unit"),
                gr.get("packaging"),
                gr.get("flavor") or "",
            )
            key_no_pkg = (
                gr.get("normalized_brand") or "",
                gr.get("normalized_name") or "",
                gr.get("size"),
                gr.get("unit"),
                gr.get("flavor") or "",
            )
            golden_by_key[key] = doc
            golden_by_key_no_pkg.setdefault(key_no_pkg, []).append(doc)

            # Structured key (brand + size + flavor) — requires flavor
            s_brand = gr.get("normalized_brand") or ""
            s_flavor = gr.get("flavor") or ""
            if s_brand and s_flavor:
                s_key = (s_brand, gr.get("size"), gr.get("unit"), gr.get("pack_size"), s_flavor)
                golden_by_structured[s_key] = doc

            # Sparkling key (brand + size + sparkling + packaging + flavor)
            s_sparkling = gr.get("is_sparkling")
            s_pkg = gr.get("packaging")
            if s_brand and s_sparkling is not None and s_pkg:
                sp_key = (s_brand, gr.get("size"), gr.get("unit"), gr.get("pack_size"), s_sparkling, s_pkg, s_flavor)
                golden_by_sparkling[sp_key] = doc

            # Preload one Wolt price for this golden record
            wolt_prods = [p for p in doc.get("products", []) if p.get("source_type") == "wolt"]
            if wolt_prods:
                norm = wolt_norm_coll.find_one({
                    "product_id": wolt_prods[0]["product_id"],
                    "branch": wolt_prods[0]["branch"],
                })
                if norm and norm.get("price"):
                    golden_prices[doc["_id"]] = norm["price"]

        # Build list of golden records for fuzzy matching
        golden_list = [(doc, doc["golden_record"]) for doc in golden_docs]

        # Match website products
        stats = Counter()
        matched_pairs = []  # (website_product, golden_doc, match_type, confidence)
        unmatched_web = []

        for wp in web_products:
            key = (
                wp.get("normalized_brand") or "",
                wp.get("normalized_name") or "",
                wp.get("size"),
                wp.get("unit"),
                wp.get("packaging"),
                wp.get("flavor") or "",
            )

            # Tier 1: Exact match (with packaging)
            if key in golden_by_key:
                matched_pairs.append((wp, golden_by_key[key], "exact", 0.95))
                stats["exact"] += 1
                continue

            # Tier 2: Relaxed packaging match — brand+name+size+unit+flavor match,
            # one side has packaging=None, prices are the same
            key_no_pkg = (
                wp.get("normalized_brand") or "",
                wp.get("normalized_name") or "",
                wp.get("size"),
                wp.get("unit"),
                wp.get("flavor") or "",
            )
            wp_price = wp.get("price")
            wp_pkg = wp.get("packaging")
            relaxed_match = None

            if key_no_pkg in golden_by_key_no_pkg:
                for candidate in golden_by_key_no_pkg[key_no_pkg]:
                    c_pkg = candidate["golden_record"].get("packaging")
                    # Only if one has packaging and the other doesn't
                    if (wp_pkg is None) == (c_pkg is None):
                        continue
                    # Check price similarity (within 15% of the lower price)
                    c_price = golden_prices.get(candidate["_id"])
                    if wp_price and c_price:
                        lower = min(wp_price, c_price)
                        if lower > 0 and abs(wp_price - c_price) / lower <= 0.15:
                            relaxed_match = candidate
                            break

            if relaxed_match:
                matched_pairs.append((wp, relaxed_match, "relaxed_pkg", 0.90))
                stats["relaxed_pkg"] += 1
                continue

            # Tier 3: Structured match (brand + size + unit + pack_size + flavor) — requires flavor
            wp_brand = wp.get("normalized_brand") or ""
            wp_flavor = wp.get("flavor") or ""
            if wp_brand and wp_flavor:
                s_key = (wp_brand, wp.get("size"), wp.get("unit"), wp.get("pack_size"), wp_flavor)
                if s_key in golden_by_structured:
                    matched_pairs.append((wp, golden_by_structured[s_key], "structured", 0.92))
                    stats["structured"] += 1
                    continue

            # Tier 4: Structured sparkling match (brand + size + sparkling + packaging + flavor)
            wp_sparkling = wp.get("is_sparkling")
            if wp_brand and wp_sparkling is not None and wp_pkg:
                sp_key = (wp_brand, wp.get("size"), wp.get("unit"), wp.get("pack_size"), wp_sparkling, wp_pkg, wp.get("flavor") or "")
                if sp_key in golden_by_sparkling:
                    matched_pairs.append((wp, golden_by_sparkling[sp_key], "structured_sparkling", 0.92))
                    stats["structured_sparkling"] += 1
                    continue

            # Tier 5: Fuzzy match (same size+unit+packaging+flavor required)
            best_score = 0
            best_golden = None
            wp_name = wp.get("normalized_name") or ""
            wp_size = wp.get("size")
            wp_unit = wp.get("unit")

            for doc, gr in golden_list:
                if gr.get("size") != wp_size or gr.get("unit") != wp_unit or gr.get("packaging") != wp_pkg:
                    continue
                if (gr.get("flavor") or "") != (wp.get("flavor") or ""):
                    continue
                gr_name = gr.get("normalized_name") or ""
                score = _similarity(wp_name, gr_name)
                if score > best_score:
                    best_score = score
                    best_golden = doc

            if best_score >= fuzzy_threshold and best_golden:
                matched_pairs.append((wp, best_golden, "fuzzy", best_score))
                stats["fuzzy"] += 1
            else:
                unmatched_web.append(wp)
                stats["unmatched"] += 1

        self.stdout.write(f"\n  Exact matches:       {stats['exact']}")
        self.stdout.write(f"  Relaxed pkg matches: {stats['relaxed_pkg']}")
        self.stdout.write(f"  Structured matches:  {stats['structured']}")
        self.stdout.write(f"  Sparkling matches:   {stats['structured_sparkling']}")
        self.stdout.write(f"  Fuzzy matches:       {stats['fuzzy']}")
        self.stdout.write(f"  Unmatched:           {stats['unmatched']} (website-only products)")

        # Update golden records with website info
        now = datetime.now(timezone.utc)
        updates = 0
        new_records = []

        if not dry_run:
            # Clear previous cross-source results for idempotent re-runs:
            # 1. Remove website products from existing golden records
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
            # 2. Delete previous website-only records
            matches_coll.delete_many({"match_type": "website_only"})

            for wp, golden_doc, match_type, confidence in matched_pairs:
                # Add website product to the golden record's products list
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
                        },
                    },
                )
                updates += 1

            # Create new golden records for website-only products
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

        # Show fuzzy match samples
        fuzzy_pairs = [(wp, gd, s) for wp, gd, mt, s in matched_pairs if mt == "fuzzy"]
        if fuzzy_pairs:
            self.stdout.write(f"\n  === Fuzzy match samples (first 10) ===")
            for wp, gd, score in fuzzy_pairs[:10]:
                self.stdout.write(f"    [{score:.2f}] Website: {wp['original_name']}")
                self.stdout.write(f"           Wolt:    {gd['golden_record']['original_name']}")
