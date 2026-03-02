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
```

## Architecture

### Dual Database Design

- **SQLite** (Django ORM): Normalized product/pricing data — `Category`, `Product`, `Market`, `MarketBranch`, `MarketProduct`, `Price`
- **MongoDB** (`simic_raw` database): Raw scraped pages and extracted products, one pair of collections per marketplace (e.g., `araz_raw_pages` / `araz_raw_products`)

### Data Pipeline (Two-Phase Scraping)

1. **Phase 1 — Raw Collection**: Scraper fetches pages from marketplace APIs/websites → stores raw JSON/HTML in MongoDB `*_raw_pages` collections
2. **Phase 2 — Extraction**: Extractor parses raw pages → writes structured product data to `*_raw_products` collections
3. **Phase 3 — Normalization** (not yet implemented): Transfer extracted products into Django ORM models

Each scraping run is tracked by an `attempt` number. Writes are idempotent (upsert by attempt + page/product_id), enabling safe resume of interrupted runs.

### Django Apps

- **core** — Abstract `BaseModel` with `created_at`/`updated_at` timestamps; all other models inherit from it
- **catalog** — `Category` model with self-referential parent FK for hierarchical categories
- **product** — `Product` model (barcode, title, brand, size, unit, category FK)
- **market** — `Market` (code, name, website) and `MarketBranch` (address, city, coordinates, unique on market+code)
- **pricing** — `MarketProduct` (links Product to Market via external_product_id, unique on market+external_id) and `Price` (price, discount_price, currency=AZN, fetched_at; indexed on market_product+branch+fetched_at)

### Scraper Structure

Each marketplace scraper lives in `scraping/<market_name>/` with a consistent pattern:
- `client.py` — HTTP fetching with rate limiting (random sleep between requests)
- `scraper.py` (or `bravo.py` for Bravo) — Pagination logic, stores raw pages in MongoDB
- `extractor.py` — Parses raw pages into structured product dicts
- `attempts.py` — Tracks attempt numbers and last-fetched page for resume

Shared utilities:
- `scraping/mongo.py` — MongoDB connection and collection references
- `scraping/raw_products/writer.py` — `write_raw_product()` upsert helper

### Marketplace-Specific Notes

| Market | Data Format | API/Source |
|---|---|---|
| Araz | JSON API | `b7x9kq.arazmarket.az/api/products/category` |
| Bazarstore | JSON API | `bazarstore.az/products.json` |
| Bravo | JSON API | `mp-catalog.umico.az/api/v1/products` (category 4497) |
| Neptun | HTML scraping | `neptun.az` search results, parsed with BeautifulSoup |

## Key Conventions

- Django settings module: `simic.settings`
- Default currency: AZN (Azerbaijani Manat)
- All models inherit from `core.models.BaseModel`
- MongoDB database name: `simic_raw`
- Management commands are in `scraping/management/commands/`
- No admin registrations, views, URL routing, or API endpoints exist yet (only `admin/` path is configured)