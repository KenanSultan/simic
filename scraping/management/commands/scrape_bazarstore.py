from django.core.management.base import BaseCommand
from scraping.bazarstore.scraper import scrape_bazarstore


class Command(BaseCommand):
    help = "Scrape Bazarstore marketplace raw product pages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--resume-attempt",
            type=int,
            help="Resume an existing attempt number",
        )

    def handle(self, *args, **options):
        resume_attempt = options.get("resume_attempt")

        self.stdout.write("[START] Bazarstore scraping")

        scrape_bazarstore(resume_attempt=resume_attempt)

        self.stdout.write(self.style.SUCCESS("[DONE] Scraping completed"))
