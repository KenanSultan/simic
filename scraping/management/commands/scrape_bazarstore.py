from django.core.management.base import BaseCommand
from scraping.bazarstore.scraper import scrape_bazarstore


class Command(BaseCommand):
    help = "Scrape Bazarstore category pages (raw JSON)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--resume-attempt",
            type=int,
            help="Resume an existing attempt number",
        )

    def handle(self, *args, **options):
        resume_attempt = options.get("resume_attempt")

        self.stdout.write("[START] Bazarstore category scraping started")

        scrape_bazarstore(resume_attempt=resume_attempt)

        self.stdout.write(
            self.style.SUCCESS("[DONE] Bazarstore category scraping finished")
        )
