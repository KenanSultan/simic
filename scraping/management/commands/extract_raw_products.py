from django.core.management.base import BaseCommand

from scraping.bravo.extractor import extract_bravo_products
from scraping.araz.extractor import extract_araz_products
from scraping.bazarstore.extractor import extract_bazarstore_products
from scraping.neptun.extractor import extract_neptun_products


class Command(BaseCommand):
    help = "Extract raw products from raw page collections"

    def add_arguments(self, parser):
        parser.add_argument(
            "--market",
            choices=["bravo", "araz", "bazarstore", "neptun", "all"],
            default="all",
            help="Which market to extract",
        )
        parser.add_argument(
            "--attempt",
            type=int,
            help="Extract only a specific attempt",
        )

    def handle(self, *args, **options):
        market = options["market"]
        attempt = options.get("attempt") or 1

        self.stdout.write(
            f"[START] Extract raw products | market={market}, attempt={attempt}"
        )

        if market in ("bravo", "all"):
            self.stdout.write("→ Extracting Bravo products")
            extract_bravo_products(attempt)

        if market in ("araz", "all"):
            self.stdout.write("→ Extracting Araz products")
            extract_araz_products(attempt)

        if market in ("bazarstore", "all"):
            self.stdout.write("→ Extracting Bazarstore products")
            extract_bazarstore_products(attempt)

        if market in ("neptun", "all"):
            self.stdout.write("→ Extracting Neptun products")
            extract_neptun_products(attempt)

        self.stdout.write(self.style.SUCCESS("[DONE] Extraction completed"))
