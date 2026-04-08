from pymongo import MongoClient
from django.conf import settings

client = MongoClient(settings.MONGO_URI)
db = client["simic_raw"]

bravo_raw_pages = db["bravo_raw_pages"]
araz_raw_pages = db["araz_raw_pages"]
bazarstore_raw_pages = db["bazarstore_raw_pages"]
neptun_raw_pages = db["neptun_raw_pages"]

bravo_raw_products = db["bravo_raw_products"]
araz_raw_products = db["araz_raw_products"]
bazarstore_raw_products = db["bazarstore_raw_products"]
neptun_raw_products = db["neptun_raw_products"]

araz_raw_categories = db["araz_raw_categories"]
bazarstore_raw_categories = db["bazarstore_raw_categories"]
neptun_raw_categories = db["neptun_raw_categories"]
wolt_raw_categories = db["wolt_raw_categories"]

wolt_araz_raw_products = db["wolt_araz_raw_products"]
wolt_bravo_raw_products = db["wolt_bravo_raw_products"]
wolt_neptun_raw_products = db["wolt_neptun_raw_products"]
wolt_rahat_raw_products = db["wolt_rahat_raw_products"]

# Per-market normalised collections
wolt_araz_normalised_products = db["wolt_araz_normalised_products"]
website_araz_normalised_products = db["website_araz_normalised_products"]
araz_product_matches = db["araz_product_matches"]

wolt_neptun_normalised_products = db["wolt_neptun_normalised_products"]
website_neptun_normalised_products = db["website_neptun_normalised_products"]
neptun_product_matches = db["neptun_product_matches"]

wolt_bravo_normalised_products = db["wolt_bravo_normalised_products"]
bravo_product_matches = db["bravo_product_matches"]

website_bazarstore_normalised_products = db["website_bazarstore_normalised_products"]
bazarstore_product_matches = db["bazarstore_product_matches"]
