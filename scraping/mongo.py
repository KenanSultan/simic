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