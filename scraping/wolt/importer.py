import json
import os
from collections import defaultdict

from scraping.mongo import (
    wolt_araz_raw_products,
    wolt_bravo_raw_products,
    wolt_neptun_raw_products,
    wolt_rahat_raw_products,
)

MARKET_COLLECTIONS = {
    "Araz": wolt_araz_raw_products,
    "Bravo": wolt_bravo_raw_products,
    "Neptun": wolt_neptun_raw_products,
    "Rahat": wolt_rahat_raw_products,
}

BATCH_SIZE = 1000


def _group_files_by_market(directory):
    """Group .jsonl files by market prefix (first word of filename)."""
    groups = defaultdict(list)
    for filename in os.listdir(directory):
        if not filename.endswith(".jsonl"):
            continue
        prefix = filename.split()[0]
        filepath = os.path.join(directory, filename)
        groups[prefix].append(filepath)
    return groups


def _import_files(filepaths, collection, stdout=None):
    """Read all JSONL files and insert products into the collection."""
    collection.delete_many({})

    batch = []
    total = 0

    for filepath in filepaths:
        branch_name = os.path.basename(filepath).replace(".jsonl", "")
        file_count = 0

        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                product = json.loads(line)
                doc = {
                    "branch": product.get("market", ""),
                    "product_id": product.get("id", ""),
                    "product": product,
                }
                batch.append(doc)
                file_count += 1

                if len(batch) >= BATCH_SIZE:
                    collection.insert_many(batch)
                    total += len(batch)
                    batch = []

        if stdout:
            stdout.write(f"    {branch_name}: {file_count} products\n")

    if batch:
        collection.insert_many(batch)
        total += len(batch)

    return total


def import_wolt(directory, stdout=None):
    """Import all branches per market from Wolt JSONL files."""
    groups = _group_files_by_market(directory)

    for market, collection in MARKET_COLLECTIONS.items():
        if market not in groups:
            if stdout:
                stdout.write(f"  No files found for {market}, skipping\n")
            continue

        filepaths = groups[market]
        if stdout:
            stdout.write(f"  {market}: importing {len(filepaths)} branches...\n")

        inserted = _import_files(filepaths, collection, stdout=stdout)

        if stdout:
            stdout.write(f"  {market}: {inserted} total products inserted\n")
