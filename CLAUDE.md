# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Simic is a price comparison platform for Azerbaijani grocery/retail marketplaces. It scrapes product and pricing data from multiple marketplaces (Araz, Bazarstore, Bravo, Neptun), stores raw data in MongoDB, and normalizes it into Django models for comparison.

## Commands

```bash
# Activate virtualenv
source .venv/bin/activate

# Run Django dev server
python manage.py runserver

# Run migrations
python manage.py makemigrations
python manage.py migrate

# Scrape marketplaces (each supports --resume-attempt N for interrupted runs)
python manage.py scrape_araz
python manage.py scrape_bazarstore
python manage.py scrape_bravo
python manage.py scrape_neptun

# Extract structured products from raw scraped data
python manage.py extract_raw_products --market all
python manage.py extract_raw_products --market bravo --attempt 3

# Normalize extracted products
python manage.py normalize_products --market araz --source-type wolt --category spirtsiz-ickiler
python manage.py normalize_products --market araz --source-type website --category spirtsiz-ickiler

# Match products and create golden records
python manage.py match_products --scope intra_marketplace --market araz --source-type wolt --category spirtsiz-ickiler
python manage.py match_products --scope cross_source --market araz --category spirtsiz-ickiler
python manage.py match_products --scope passthrough --market bazarstore --source-type website --category spirtsiz-ickiler
```

## Architecture

### Dual Database Design

- **SQLite** (Django ORM): Normalized product/pricing data — `Category`, `Product`, `Market`, `MarketBranch`, `MarketProduct`, `Price`
- **MongoDB** (`simic_raw` database): Raw scraped pages, extracted products, normalized products, and product matches

### Data Pipeline

1. **Scraping** (`scraping/`): Fetches raw pages from marketplace APIs/websites → stores in MongoDB `*_raw_pages` → extracts to `*_raw_products`
2. **Normalization** (`normalizer/`): Parses product names, assigns categories, extracts structured fields → stores in `*_normalised_products`
3. **Matching** (`matcher/`): Deduplicates within branches, matches across sources, creates golden records → stores in `*_product_matches`

Each scraping run is tracked by an `attempt` number. Writes are idempotent (upsert by attempt + page/product_id), enabling safe resume of interrupted runs.

### Django Apps

**Infrastructure:**
- **core** — Abstract `BaseModel` with `created_at`/`updated_at` timestamps; all other models inherit from it
- **datastore** — MongoDB connection and collection registry (`datastore/mongo.py`)

**Data Pipeline:**
- **scraping** — Marketplace-specific scrapers (Araz, Bazarstore, Bravo, Neptun, Wolt). Commands: `scrape_*`, `extract_raw_products`, `import_wolt`
- **normalizer** — Product name parsing, category assignment, market-specific extractors, rule engine. Command: `normalize_products`
- **matcher** — Product deduplication, multi-tier matching (barcode → exact → structured → fuzzy), golden record creation, cross-source matching. Command: `match_products`

**Domain Models (SQLite):**
- **catalog** — `Category` model with self-referential parent FK for hierarchical categories
- **product** — `Product` model (barcode, title, brand, size, unit, category FK)
- **market** — `Market` (code, name, website) and `MarketBranch` (address, city, coordinates, unique on market+code)
- **pricing** — `MarketProduct` (links Product to Market via external_product_id) and `Price` (price, discount_price, currency=AZN, fetched_at)

**UI:**
- **review** — Web interface for reviewing matched products, golden records, warnings, and image galleries
- **discover** — Exploratory query utilities

### App Dependency Flow

```
datastore/          ← no project deps (pymongo + Django settings)
    ↑
scraping/           ← depends on: datastore
normalizer/         ← depends on: datastore
    ↑
matcher/            ← depends on: datastore, normalizer (category utils)
review/             ← depends on: datastore, normalizer (category utils)
```

### Scraper Structure

Each marketplace scraper lives in `scraping/<market_name>/` with a consistent pattern:
- `client.py` — HTTP fetching with rate limiting (random sleep between requests)
- `scraper.py` (or `bravo.py` for Bravo) — Pagination logic, stores raw pages in MongoDB
- `extractor.py` — Parses raw pages into structured product dicts
- `attempts.py` — Tracks attempt numbers and last-fetched page for resume

Shared utilities:
- `datastore/mongo.py` — MongoDB connection and collection references
- `scraping/raw_products/writer.py` — `write_raw_product()` upsert helper

### Normalizer Structure

- `normalizer/parser.py` — Product name parser (brand, size, flavor, packaging, etc.)
- `normalizer/category.py` — Two-layer category assigner (direct mapping + keyword rules)
- `normalizer/extractors/` — Market-specific extractors (Araz, Bazarstore, Neptun, Wolt)
- `normalizer/rules/` — Hierarchical rule engine (general → category → market → brand scopes)

### Marketplace-Specific Notes

| Market | Data Format | API/Source |
|---|---|---|
| Araz | JSON API | `b7x9kq.arazmarket.az/api/products/category` |
| Bazarstore | JSON API | `bazarstore.az/collections/{handle}/products.json` (~494 leaf categories, Shopify) |
| Bravo | JSON API | `mp-catalog.umico.az/api/v1/products` (category 4497) |
| Neptun | HTML scraping | `neptun.az` category pages (~116 leaf categories), parsed with BeautifulSoup |

## Key Conventions

- Django settings module: `simic.settings`
- Default currency: AZN (Azerbaijani Manat)
- All models inherit from `core.models.BaseModel`
- MongoDB database name: `simic_raw`
- MongoDB access: always import from `datastore.mongo`, never connect directly
- Management commands: `scraping/management/commands/` (scraping), `normalizer/management/commands/` (normalization), `matcher/management/commands/` (matching)
- Data files (canonical categories, brand dictionary): `data/` directory, referenced via `settings.DATA_DIR`