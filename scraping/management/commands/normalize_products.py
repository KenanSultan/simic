from collections import Counter

from django.core.management.base import BaseCommand

from scraping.images import download_product_image
from scraping.mongo import db
from scraping.normalization.category import (
    load_canonical_categories,
    load_category_assigner,
    get_subcategory_ids,
)
from scraping.normalization.rules import RuleLoader
from scraping.normalization.extractors.wolt import WoltExtractor
from scraping.normalization.extractors.araz_website import ArazWebsiteExtractor
from scraping.normalization.extractors.neptun_website import NeptunWebsiteExtractor

# Source type → config (collection templates use {market} placeholder)
# "market_extractors" overrides extractor_class and category_field per market.
SOURCE_REGISTRY = {
    "wolt": {
        "collection_template": "wolt_{market}_raw_products",
        "output_collection_template": "wolt_{market}_normalised_products",
        "category_field": "product.category",
        "extractor_class": WoltExtractor,
    },
    "website": {
        "collection_template": "{market}_raw_products",
        "output_collection_template": "website_{market}_normalised_products",
        "category_field": "product.category_title",
        "extractor_class": ArazWebsiteExtractor,
        "market_extractors": {
            "neptun": {
                "extractor_class": NeptunWebsiteExtractor,
                "category_field": "product._meta.category_title",
            },
        },
    },
}


class Command(BaseCommand):
    help = "Normalize raw products: parse names, assign categories, store in per-market normalised collections"

    def add_arguments(self, parser):
        parser.add_argument("--market", required=True, choices=["araz", "bazarstore", "bravo", "neptun"])
        parser.add_argument("--source-type", required=True, choices=["website", "wolt"])
        parser.add_argument("--category", required=True, help="Canonical category slug (e.g., spirtsiz-ickiler)")
        parser.add_argument("--branch", help="Specific branch name (default: all branches)")
        parser.add_argument("--skip-images", action="store_true", help="Skip downloading product images")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        market = options["market"]
        source_type = options["source_type"]
        category_slug = options["category"]
        branch_filter = options.get("branch")
        skip_images = options["skip_images"]
        dry_run = options["dry_run"]

        self.stdout.write(
            f"[START] Normalize | market={market}, source={source_type}, "
            f"category={category_slug}, branch={branch_filter or 'all'}"
        )

        # Load rules with explicit scope
        rule_loader = RuleLoader(category_slug=category_slug, market=market)

        # Load category assigner (market-specific)
        assigner = load_category_assigner(market, source_type)
        all_cats = assigner.all_wolt_categories()
        self.stdout.write(f"  Loaded mappings for {len(all_cats)} categories")

        # Determine target canonical IDs
        canonical_cats = load_canonical_categories()
        target_ids = get_subcategory_ids(canonical_cats, category_slug)
        self.stdout.write(f"  Target canonical IDs: {target_ids}")

        # Get source and output collections (per-market)
        source_config = SOURCE_REGISTRY[source_type]
        collection_name = source_config["collection_template"].format(market=market)
        output_name = source_config["output_collection_template"].format(market=market)
        raw_collection = db[collection_name]
        output_collection = db[output_name]

        # Check for market-specific overrides (e.g., NeptunWebsiteExtractor)
        market_override = source_config.get("market_extractors", {}).get(market, {})
        extractor_class = market_override.get("extractor_class", source_config["extractor_class"])
        category_field = market_override.get("category_field", source_config["category_field"])

        # Create extractor with rule_loader
        extractor = extractor_class(
            marketplace=market,
            rule_loader=rule_loader,
        )

        # Query products in mapped categories
        query = {category_field: {"$in": list(all_cats)}}
        if branch_filter:
            query["branch"] = branch_filter

        total = raw_collection.count_documents(query)
        self.stdout.write(f"  Found {total} raw products to process")

        # Process
        stats = Counter()
        warning_counter = Counter()
        category_counter = Counter()

        for raw_doc in raw_collection.find(query):
            stats["processed"] += 1

            normalized = extractor.extract(raw_doc, assigner)
            if normalized is None:
                stats["skipped_no_mapping"] += 1
                continue

            if normalized["canonical_category_id"] not in target_ids:
                stats["skipped_wrong_category"] += 1
                continue

            # Download product image
            if not skip_images and not dry_run and normalized.get("image"):
                local_path = download_product_image(normalized["image"], market)
                normalized["local_image"] = local_path
            elif not normalized.get("image"):
                normalized["local_image"] = None

            for w in normalized.get("parse_warnings", []):
                warning_counter[w] += 1

            category_counter[normalized["canonical_category_id"]] += 1
            stats["succeeded"] += 1

            if not dry_run:
                output_collection.update_one(
                    {
                        "product_id": normalized["product_id"],
                        "marketplace": normalized["marketplace"],
                        "source_type": normalized["source_type"],
                        "branch": normalized["branch"],
                    },
                    {"$set": normalized},
                    upsert=True,
                )

            if stats["processed"] % 2000 == 0:
                self.stdout.write(f"  ... processed {stats['processed']}/{total}")

        # Report
        self.stdout.write(f"\n  Processed:             {stats['processed']}")
        self.stdout.write(f"  Succeeded:             {stats['succeeded']}")
        self.stdout.write(f"  Skipped (no mapping):  {stats['skipped_no_mapping']}")
        self.stdout.write(f"  Skipped (wrong cat):   {stats['skipped_wrong_category']}")

        if category_counter:
            self.stdout.write(f"\n  Products by canonical category:")
            for cat_id, count in category_counter.most_common():
                cat_name = canonical_cats.get(cat_id, {}).get("name", "?")
                self.stdout.write(f"    {cat_id} ({cat_name}): {count}")

        if warning_counter:
            self.stdout.write(f"\n  Parse warnings:")
            for warning, count in warning_counter.most_common():
                self.stdout.write(f"    {warning}: {count}")

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\n  [DRY RUN] No data written."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n  [DONE] Written to '{output_name}'"))
