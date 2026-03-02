from django.core.management.base import BaseCommand
from scraping.bravo.bravo import scrape_birmarket_bravo


class Command(BaseCommand):
    help = "Scrape Bravo products from Birmarket (raw, attempt-based)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--resume-attempt",
            type=int,
            help="Resume an existing attempt number",
        )

    def handle(self, *args, **options):
        resume_attempt = options.get("resume_attempt")

        self.stdout.write("[START] Birmarket Bravo scraping")

        scrape_birmarket_bravo(resume_attempt=resume_attempt)

        self.stdout.write(self.style.SUCCESS("[DONE] Scraping completed"))
