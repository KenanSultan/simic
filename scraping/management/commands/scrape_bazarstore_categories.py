from django.core.management.base import BaseCommand
from scraping.bazarstore.category_scraper import scrape_bazarstore_categories


class Command(BaseCommand):
    help = "Scrape Bazarstore marketplace category hierarchy"

    def handle(self, *args, **options):
        self.stdout.write("[START] Scraping Bazarstore categories...")
        scrape_bazarstore_categories()
        self.stdout.write(self.style.SUCCESS("[DONE] Bazarstore categories saved"))
