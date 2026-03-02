from django.core.management.base import BaseCommand
from scraping.araz.scraper import scrape_araz


class Command(BaseCommand):
    help = "Scrape Araz marketplace raw product pages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--resume-attempt",
            type=int,
            help="Resume an existing attempt number",
        )

    def handle(self, *args, **options):
        resume_attempt = options.get("resume_attempt")

        self.stdout.write("[START] Araz scraping started")

        scrape_araz(resume_attempt=resume_attempt)

        self.stdout.write(self.style.SUCCESS("[DONE] Araz scraping finished"))
