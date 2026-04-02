from django.core.management.base import BaseCommand

from scraping.wolt.importer import import_wolt


class Command(BaseCommand):
    help = "Import Wolt product data from JSONL files into MongoDB"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            type=str,
            default="/home/kenansultan/Downloads/wolt",
            help="Directory containing Wolt JSONL files",
        )

    def handle(self, *args, **options):
        directory = options["dir"]
        self.stdout.write(self.style.SUCCESS("[START] Importing Wolt data..."))
        import_wolt(directory, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("[DONE] Wolt import complete."))
