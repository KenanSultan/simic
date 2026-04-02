from django.core.management.base import BaseCommand

from scraping.neptun.scraper import scrape_neptun


class Command(BaseCommand):
    help = "Scrape Neptun category pages (raw HTML)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--resume-attempt",
            type=int,
            help="Resume an existing attempt number",
        )

    def handle(self, *args, **options):
        resume_attempt = options.get("resume_attempt")

        self.stdout.write("[START] Neptun category scraping started")

        scrape_neptun(resume_attempt=resume_attempt)

        self.stdout.write(
            self.style.SUCCESS("[DONE] Neptun category scraping finished")
        )
