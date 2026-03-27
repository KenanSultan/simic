import json

from django.core.management.base import BaseCommand
from scraping.mongo import araz_raw_products

DEFAULT_CATEGORY_IDS = [1503]  # Fill with known Araz category IDs


class Command(BaseCommand):
    help = "Query and display raw Araz products from MongoDB"

    def add_arguments(self, parser):
        parser.add_argument(
            "--category-id",
            type=int,
            help="Filter by a specific product category_id",
        )

    def handle(self, *args, **options):
        category_id = options.get("category_id")

        if category_id is not None:
            category_ids = [category_id]
        else:
            category_ids = DEFAULT_CATEGORY_IDS

        if not category_ids:
            self.stdout.write(self.style.WARNING(
                "No category IDs provided. Use --category-id or populate DEFAULT_CATEGORY_IDS."
            ))
            return

        for cid in category_ids:
            self.stdout.write(f"\n--- category_id: {cid} ---\n")
            cursor = araz_raw_products.find({"product.category_id": cid})
            count = 0
            for doc in cursor:
                doc.pop("_id", None)
                self.stdout.write(json.dumps(doc, indent=2, default=str))
                count += 1
            self.stdout.write(f"\n({count} products found)\n")
