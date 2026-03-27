from django.core.management.base import BaseCommand

from scraping.wolt.category_scraper import scrape_wolt_categories


class Command(BaseCommand):
    help = "Scrape Wolt category hierarchy for marketplace branches"

    def add_arguments(self, parser):
        parser.add_argument(
            "--market",
            choices=["neptun", "araz", "bravo", "all"],
            default="all",
            help="Which market to scrape (default: all)",
        )

    def handle(self, *args, **options):
        market = options["market"]
        markets = ["neptun", "araz", "bravo"] if market == "all" else [market]

        for m in markets:
            self.stdout.write(f"[START] Scraping Wolt categories for {m}...")
            scrape_wolt_categories(m)
            self.stdout.write(self.style.SUCCESS(f"[DONE] Wolt {m} categories saved"))
