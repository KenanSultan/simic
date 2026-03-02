# Simic

A price comparison platform for Azerbaijani grocery and retail marketplaces. Simic scrapes product and pricing data from multiple retailers, stores raw data in MongoDB, and normalizes it into Django models for comparison.

## Supported Marketplaces

| Marketplace | Data Source | Method |
|-------------|------------|--------|
| **Araz** | `arazmarket.az` | JSON API |
| **Bazarstore** | `bazarstore.az` | JSON API |
| **Bravo** | `umico.az` catalog | JSON API |
| **Neptun** | `neptun.az` | HTML scraping |

## Tech Stack

- **Python 3.12** / **Django 5.2**
- **SQLite** — normalized product and pricing data (Django ORM)
- **MongoDB** — raw scraped pages and extracted products
- **requests** — HTTP client for API calls
- **BeautifulSoup** + **lxml** — HTML parsing (Neptun)
- **pymongo** — MongoDB driver

## Architecture

### Dual Database Design

Simic uses two databases for different stages of the data pipeline:

- **MongoDB** (`simic_raw`): Stores raw API responses and HTML pages as-is, along with extracted product documents. Each marketplace has its own pair of collections (`*_raw_pages` and `*_raw_products`).
- **SQLite** (Django ORM): Holds the normalized, deduplicated product catalog with pricing history across markets and branches.

### Data Pipeline

```
Marketplace APIs/Websites
        │
        ▼
┌─────────────────────┐
│  Phase 1: Scraping   │  Fetch raw pages → MongoDB *_raw_pages
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Phase 2: Extraction │  Parse raw pages → MongoDB *_raw_products
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Phase 3: Normalize  │  Transfer to Django ORM (not yet implemented)
└─────────────────────┘
```

Each scraping run is tracked by an **attempt number**. All writes are idempotent (upsert by attempt + page/product ID), so interrupted runs can be safely resumed.

### Django Apps

| App | Purpose |
|-----|---------|
| `core` | Abstract `BaseModel` with `created_at` / `updated_at` timestamps |
| `catalog` | `Category` model with hierarchical parent FK |
| `product` | `Product` model (barcode, title, brand, size, unit) |
| `market` | `Market` and `MarketBranch` models (name, address, coordinates) |
| `pricing` | `MarketProduct` (links products to markets) and `Price` (price history with discount support) |
| `scraping` | Scrapers, extractors, and management commands for all marketplaces |

## Getting Started

### Prerequisites

- Python 3.12+
- MongoDB running on `localhost:27017`

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd SimicProject

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate
```

### Configuration

The project uses environment variables via `python-dotenv`. Create a `.env` file in the project root if you need to override defaults:

```env
MONGODB_URI=mongodb://localhost:27017
```

## Usage

### Scraping (Phase 1)

Fetch raw data from marketplace APIs and websites into MongoDB:

```bash
python manage.py scrape_araz
python manage.py scrape_bazarstore
python manage.py scrape_bravo
python manage.py scrape_neptun
```

To resume an interrupted scraping run:

```bash
python manage.py scrape_araz --resume-attempt 3
```

### Extraction (Phase 2)

Parse raw pages into structured product documents:

```bash
# Extract from all marketplaces
python manage.py extract_raw_products --market all

# Extract from a specific marketplace and attempt
python manage.py extract_raw_products --market bravo --attempt 3
```

### Development Server

```bash
python manage.py runserver
```

## Project Structure

```
SimicProject/
├── simic/                  # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                   # Base model with timestamps
├── catalog/                # Category hierarchy
├── product/                # Product catalog
├── market/                 # Marketplace and branch data
├── pricing/                # Price tracking
├── scraping/               # Scraping infrastructure
│   ├── management/commands/ # CLI commands
│   ├── araz/               # Araz scraper & extractor
│   ├── bazarstore/         # Bazarstore scraper & extractor
│   ├── bravo/              # Bravo scraper & extractor
│   ├── neptun/             # Neptun scraper & extractor
│   ├── raw_products/       # Shared upsert helper
│   └── mongo.py            # MongoDB connection & collections
├── templates/              # Django templates
├── requirements.txt
└── manage.py
```

## Data Models

### MongoDB Collections

Each marketplace has two collections in the `simic_raw` database:

**`*_raw_pages`** — Raw API responses / HTML pages:
```json
{
  "attempt": 1,
  "page": 5,
  "fetched_at": "2025-01-15T10:30:00",
  "data": { "...raw response..." }
}
```

**`*_raw_products`** — Extracted product documents:
```json
{
  "product_id": "12345",
  "attempt": 1,
  "fetched_at": "2025-01-15T10:30:00",
  "product": { "...structured fields..." }
}
```

### Django ORM (Normalized)

```
Category ←─── Product ───→ MarketProduct ───→ Price
                              │                  │
                              ▼                  ▼
                           Market          MarketBranch
```

- **Product**: barcode, title, brand, size, unit, category
- **MarketProduct**: links a product to a specific market via external ID
- **Price**: price, discount_price, currency (AZN), fetched_at — indexed for efficient time-series queries

## License

All rights reserved.