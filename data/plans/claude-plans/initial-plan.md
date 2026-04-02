# Product Identification Pipeline — Master Plan

*Last updated: 2026-03-30*

## Context

Simic scrapes product data from ~80 distinct sources across 4 Azerbaijani grocery marketplaces:
- **Araz**: 1 website + 26 Wolt branches (27 sources)
- **Neptun**: 1 website + 11 Wolt branches (12 sources)
- **Bazarstore**: 1 website (1 source)
- **Bravo**: 40 Wolt branches (40 sources)

Each source has its own product IDs, naming conventions, and category hierarchy. The goal is to identify the same physical product across all sources and create a canonical product catalog for price comparison.

All raw data is scraped and stored in MongoDB (`simic_raw` database):
- Website products: `{market}_raw_products`
- Wolt products: `wolt_{market}_raw_products`

Canonical categories defined in `data/categories/canonical-categories.json`.

---

## Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Processing order | Category-first, then by marketplace | Reduces matching search space |
| Different sizes | Different canonical products | Coca-Cola 500ml ≠ Coca-Cola 1L |
| Different packaging | Different canonical products | Coca-Cola 330ml can ≠ Coca-Cola 330ml glass |
| Weight products | Skip (entire categories) | Focus on packaged goods first |
| Accuracy priority | Precision over recall | Better to miss than mismatch |
| Parsing approach | Rule-based (regex/heuristics) | LLMs as future fallback |
| Match tiers | Barcode → exact → relaxed pkg → fuzzy | Layered confidence |
| Unmatched products | Still become golden records | Complete catalog |
| Text normalization | ASCII lowercase + doubled consonant collapse | Handles Azerbaijani/Turkish/Russian variants |
| Normalization pass | Combined: normalize + parse + category assign | Single pass, fewer intermediates |
| Per-market collections | `wolt_{market}_normalised_products`, `{market}_product_matches` | Clean isolation per marketplace |
| Rule organization | Scope hierarchy: general → category → market → brand | Clear provenance, no cross-contamination |
| Rule format | Hybrid: JSON for data rules, Python for logic rules | Easy to edit data, full power for logic |
| Golden record: with website | Website-primary, Wolt fills gaps | Website naming is most authoritative |
| Golden record: Wolt-only | Consensus across branches | No single authority, aggregate |
| Category mapping | Two-layer: direct 1:1 + keyword rules for catch-alls | Wolt categories are often too coarse |
| Branch pricing | Track all branch prices individually | Users see location-based prices |

---

## Iteration Strategy

| Iteration | Scope | Status | Result |
|-----------|-------|--------|--------|
| **1** | Araz Wolt branches, Spirtsiz içkilər | **DONE** | 788 golden records from 14,229 products |
| **2** | Araz website + Wolt, Spirtsiz içkilər | **DONE** | 529 matched cross-source, 173 website-only |
| **3** | All marketplaces, Spirtsiz içkilər | TODO | Inter-marketplace matching |
| **4** | All marketplaces, all categories | TODO | Full pipeline at scale |

---

## What's Built (Current State)

### Normalization Pipeline

**Parser** (`scraping/normalization/parser.py`):
Orchestrates 11-step extraction pipeline using RuleLoader:
1. Clean text (Unicode, whitespace)
2. Extract brand (dictionary match: start → prefix-strip → anywhere)
3. Extract size/unit (regex + bare volume fallback + sanity check)
4. Extract packaging (glass, pet, can, tetra)
5. Extract sparkling/still
6. Detect & remove product type (kompot, limonad, nektar, ...)
7. Extract flavor (80+ patterns, multi-flavor with `-` join)
8. Remove stop words/phrases
9. Remove piece counts
10. Color-as-flavor fallback
11. Produce `remaining_data` field

**Output fields**: `brand`, `size`, `unit`, `pack_size`, `packaging`, `is_sparkling`, `flavor`, `product_type`, `remaining_data`, `normalized_name`, `normalized_brand`, `parse_warnings`

### Rules System (`scraping/normalization/rules/`)

```
rules/
├── __init__.py              # RuleLoader class
├── RULES.md                 # Full documentation
├── general/                 # ALL products — text, sizes, brands
│   ├── text.py, size.py, piece_count.py
│   └── brands.json          # 130+ brands with aliases
├── category/
│   └── beverages/           # Spirtsiz içkilər only
│       ├── flavors.json     # 80+ flavor patterns
│       ├── packaging.json, sparkling.json
│       ├── product_types.json, stop_words.json, prefixes.json
│       └── sanity.py
├── market/
│   └── araz/                # Araz only
│       ├── wolt_categories.json
│       └── website_categories.json
└── brand/                   # Future
```

### Extractors

| Extractor | File | Scope |
|-----------|------|-------|
| WoltExtractor | `scraping/normalization/extractors/wolt.py` | All Wolt branches (shared) |
| ArazWebsiteExtractor | `scraping/normalization/extractors/araz_website.py` | Araz website |

### Matchers (`scraping/identification/`)

| Matcher | File | Confidence |
|---------|------|------------|
| Barcode (GTIN) | `matchers/barcode.py` | 1.0 |
| Exact fields | `matchers/exact.py` | 0.95 |
| Relaxed packaging | in `match_products.py` | 0.90 (same price + one pkg null) |
| Fuzzy name | `matchers/fuzzy.py` | 0.85 threshold |

**Matching key**: `(normalized_brand, normalized_name, size, unit, packaging)`

### Management Commands

```bash
# Normalize raw products into structured data
python manage.py normalize_products --market araz --source-type wolt --category spirtsiz-ickiler

# Match within marketplace (creates golden records)
python manage.py match_products --scope intra_marketplace --market araz --source-type wolt --category spirtsiz-ickiler

# Match website against Wolt golden records
python manage.py match_products --scope cross_source --market araz --category spirtsiz-ickiler
```

### MongoDB Collections (Per-Market)

| Collection | Documents | Content |
|------------|-----------|---------|
| `wolt_araz_normalised_products` | 14,229 | Normalized Araz Wolt products |
| `website_araz_normalised_products` | 702 | Normalized Araz website products |
| `araz_product_matches` | 961 | Golden records + match groups |

### Canonical Categories (Spirtsiz içkilər)

| ID | Name | Wolt Products | Website Products |
|----|------|---------------|------------------|
| 1401 | Su & Mineral su | 2,858 | 129 |
| 1402 | Meyvə şirəsi & Kompot | 3,584 | 256 |
| 1403 | Qazlı içkilər | 5,802 | 244 |
| 1404 | Enerji içkiləri | 661 | 32 |
| 1405 | Soyuq çay & Soyuq kofe | 1,324 | 62 |

### Cross-Source Matching Results (Araz)

| Tier | Matched | % |
|------|---------|---|
| Exact | 522 | 74.4% |
| Relaxed pkg | 7 | 1.0% |
| Fuzzy | 0 | 0% |
| **Total matched** | **529** | **75.4%** |
| Website-only | 173 | 24.6% |

---

## ITERATION 3: All Marketplaces × Spirtsiz içkilər

**Goal**: Extend to Neptun, Bravo, Bazarstore. Run intra-marketplace dedup for each, then inter-marketplace matching to create a unified product catalog.

### Phase 0: Setup (per marketplace)

**Neptun** (website + 11 Wolt branches):
- Create `rules/market/neptun/wolt_categories.json`
- Create `rules/market/neptun/website_categories.json`
- Profile Neptun data (barcode coverage, naming patterns)
- Note: Neptun website uses HTML scraping, barcodes may not exist

**Bravo** (40 Wolt branches only):
- Create `rules/market/bravo/wolt_categories.json`
- Profile Bravo Wolt data
- WoltExtractor is shared — no new extractor needed
- Golden record strategy: consensus (no website to be primary)

**Bazarstore** (website only):
- Create `rules/market/bazarstore/website_categories.json`
- Build BazarstoreExtractor (Shopify format, has `vendor` field = brand)
- Single source — no dedup needed, direct passthrough to golden records
- Note: has variants (different sizes as separate entries)

### Phase 1: Normalize & Dedup Each Marketplace

For each marketplace:
```bash
python manage.py normalize_products --market <market> --source-type <type> --category spirtsiz-ickiler
python manage.py match_products --scope intra_marketplace --market <market> --source-type <type> --category spirtsiz-ickiler
```

For marketplaces with website + Wolt:
```bash
python manage.py match_products --scope cross_source --market <market> --category spirtsiz-ickiler
```

### Phase 2: Inter-Marketplace Matching

**New command**: `match_products --scope inter_marketplace --category spirtsiz-ickiler`

Match golden records across all 4 marketplaces:
- Load golden records from `araz_product_matches`, `neptun_product_matches`, `bravo_product_matches`, `bazarstore_product_matches`
- Tier 1: GTIN barcode matching (where available)
- Tier 2: Exact `(normalized_brand, normalized_name, size, unit, packaging)` matching
- Tier 3: Fuzzy name matching with review

**Output**: Canonical product records linking golden records from multiple marketplaces

### Phase 3: Django Integration

- Update `Product` model (add `match_source`, `normalized_name`)
- Update `MarketProduct` model (add `match_type`, `match_confidence`, `needs_review`, `original_name`)
- Load canonical categories into Django `Category` model
- Create `Product` records from inter-marketplace match groups
- Create `MarketProduct` links for each marketplace's golden record
- Import branch-level prices into `Price` model

---

## ITERATION 4: All Categories

Expand to remaining canonical categories. For each new category:

1. Create `rules/category/<name>/` directory
2. Add category-specific rules (flavors, packaging, stop words, etc.)
3. Register in `_CATEGORY_DIR_MAP` in `rules/__init__.py`
4. Create category mappings for each market (`rules/market/*/`)
5. Expand brand dictionary as needed
6. Run normalize → match pipeline

Priority categories:
- Süd məhsulları (Dairy)
- Şirniyyat & Çərəzlər (Sweets & Snacks)
- Təmizlik vasitələri (Cleaning)
- Şəxsi baxım & Kosmetika (Personal care)

---

## Future Enhancements

- **Image-based matching**: Perceptual hashing to disambiguate products with same brand+size but different flavors (238 false positive candidates identified — brand+size+price alone is insufficient)
- **Frontend review UI**: Django views to browse golden records, review fuzzy matches, see unmatched products
- **Brand-specific rules**: `rules/brand/` for brand-specific defaults and overrides
- **LLM fallback**: Use Claude API for products that fail rule-based parsing
- **Continuous pipeline**: Auto-process new scrapes incrementally
- **Weight product support**: Price-per-kg comparison for fruits, vegetables, meat
