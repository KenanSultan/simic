from django.core.management.base import BaseCommand
from scraping.neptun.category_scraper import scrape_neptun_categories


class Command(BaseCommand):
    help = "Scrape Neptun marketplace category hierarchy"

    def handle(self, *args, **options):
        self.stdout.write("[START] Scraping Neptun categories...")
        scrape_neptun_categories()
        self.stdout.write(self.style.SUCCESS("[DONE] Neptun categories saved"))
