from django.core.management.base import BaseCommand
from scraping.araz.category_scraper import scrape_araz_categories


class Command(BaseCommand):
    help = "Scrape Araz marketplace category hierarchy"

    def handle(self, *args, **options):
        self.stdout.write("[START] Scraping Araz categories...")
        scrape_araz_categories()
        self.stdout.write(self.style.SUCCESS("[DONE] Araz categories saved"))
