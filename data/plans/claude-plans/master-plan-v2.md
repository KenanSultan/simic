# Simic Master Plan v2 — Full Product Catalog for Price Comparison

*Created: 2026-04-06*

## Context

Simic is a consumer-facing price comparison platform for Azerbaijani grocery marketplaces. The goal is a website where users search products and compare prices across Araz, Neptun, Bravo, and Bazarstore.

**Current state** (as of 2026-04-06):
- Beverages (Spirtsiz ickiler, category 14) are fully processed for Araz (1,329 golden records), Neptun (973), and Bravo (730)
- Bazarstore has 10,022 raw products but no normalization/matching
- Rahat excluded from scope
- Canonical categories expanded from 5 to 11 beverage subcategories (1401-1411)
- Review UI functional for browsing/filtering golden records
- Django SQL models exist but are unused — all data lives in MongoDB

**Known quality issues**:
- Cross-source missed matches (website products failing to match Wolt golden records)
- Category misassignment (products landing in wrong subcategories)
- Root causes not yet investigated

**Key decisions from brainstorming**:
- End goal: Consumer price comparison website
- Marketplaces: Araz + Neptun + Bravo + Bazarstore (skip Rahat)
- Category priority: Consumer staples — Dairy → Snacks → Cleaning → Personal care
- Parser approach: Keep current fields (brand, size, unit, packaging, flavor, product_type), generalize rules. Generic parser + category-specific overrides.
- Canonical model: Single unified golden record per physical product (for future inter-marketplace matching)
- Bazarstore: Direct passthrough to golden records (single source, no dedup needed)
- Data freshness: Full re-scrape periodically, incremental normalization/matching (future concern)

---

## Execution Order

```
Phase 1: Bazarstore Beverages          ← Complete beverages across all 4 marketplaces
Phase 2: Quality Investigation & Fixes  ← Fix cross-source matching + category issues
Phase 3: Generic Parser Refactor        ← Make pipeline work for any category
Phase 4: Category Expansion             ← Dairy → Snacks → Cleaning → Personal care
Phase 5: Inter-Marketplace Matching     ← Unified canonical products across all markets
Phase 6: Django Integration + Frontend  ← API, consumer-facing website
```

---

## Phase 1: Bazarstore Beverages

**Goal**: Complete the beverage pipeline for all 4 marketplaces.

Bazarstore is a Shopify site, website-only (no Wolt). Has `vendor` field = brand. 10,022 raw products in `bazarstore_raw_products`. Single source → direct passthrough to golden records.

### 1.1 — Profile Bazarstore Data
- Examine raw product structure (Shopify JSON format)
- List all categories, identify beverage categories
- Check vendor/brand coverage, naming patterns
- Count beverage products
- Check for duplicates or size variants

### 1.2 — Create BazarstoreExtractor
**New file**: `scraping/normalization/extractors/bazarstore_website.py`

Shopify-specific extraction:
- Brand from `vendor` field (Shopify convention)
- Price from `price` (Shopify format)
- Category from collection/tag structure
- Image from Shopify `images` array
- No barcode expected (Shopify doesn't expose GTIN)

### 1.3 — Create Category Mappings
**New file**: `scraping/normalization/rules/market/bazarstore/website_categories.json`

Map Bazarstore collection handles to canonical category IDs (1401-1411).

### 1.4 — Update Infrastructure
- `scraping/mongo.py`: Add `website_bazarstore_normalised_products`, `bazarstore_product_matches`
- `normalize_products.py`: Register BazarstoreExtractor for market=bazarstore
- `match_products.py`: Add passthrough mode for single-source marketplaces (each normalized product → golden record directly)

### 1.5 — Normalize & Create Golden Records
```bash
python manage.py normalize_products --market bazarstore --source-type website --category spirtsiz-ickiler
python manage.py match_products --scope passthrough --market bazarstore --category spirtsiz-ickiler
```

### 1.6 — Verify
- Check total normalized + golden record counts
- Review parse warnings (brand_not_found, size_not_found)
- Spot-check known products in review UI
- Add missing brands to `brands.json` if needed

**Files to create/modify**:
| File | Action |
|------|--------|
| `extractors/bazarstore_website.py` | Create |
| `rules/market/bazarstore/website_categories.json` | Create |
| `scraping/mongo.py` | Add bazarstore collections |
| `normalize_products.py` | Register bazarstore extractor |
| `match_products.py` | Add passthrough scope |
| `rules/general/brands.json` | Add missing brands |
| `review/mongo_queries.py` | Add bazarstore to market registry |

---

## Phase 2: Quality Investigation & Fixes

**Goal**: Diagnose and fix cross-source matching failures and category misassignment.

### 2.1 — Investigate Cross-Source Missed Matches

For each marketplace with both sources (Araz, Neptun):

1. **Get unmatched website products** — products that didn't match any Wolt golden record
2. **For each unmatched product, find candidate Wolt matches** — same brand+size or similar name
3. **Classify failure reasons**:
   - Naming difference (normalization produces different names)
   - Brand not recognized on one side
   - Size/unit extraction inconsistency
   - Packaging difference (website says "pet", Wolt says null)
   - Product genuinely website-only (no Wolt equivalent)
4. **Quantify**: What % of unmatched are real misses vs genuine website-only?

**Build investigation tooling**:
- Management command or review UI view that shows unmatched website products alongside their closest Wolt candidate
- Side-by-side normalized field comparison

### 2.2 — Investigate Category Misassignment

1. **Review category mapping rules** for each marketplace
2. **Sample products from each subcategory** — check if they belong there
3. **Check inference.py** — does category correction logic work as intended?
4. **Focus on rule-based mappings** — these are the most error-prone (keyword matching)

### 2.3 — Fix Issues Found

Based on investigation results. Likely fixes:
- Adjust normalization to produce more consistent names across sources
- Expand brand dictionary with aliases
- Fix category mapping keywords
- Adjust matching tiers (lower fuzzy threshold, add new matching signals)
- Fix inference.py rules

### 2.4 — Re-run Matching After Fixes

For each affected marketplace, re-normalize and re-match. Compare before/after metrics.

---

## Phase 3: Generic Parser Refactor

**Goal**: Make the parsing pipeline work for any grocery category with minimal per-category setup.

### Current State Assessment

The parser is already *almost* generic. Key findings:
- Steps 1-3, 9, 11 are fully generic (clean text, brand, size, piece counts, remaining)
- Steps 4-8, 10 are beverage-specific but gracefully handle empty rules (return None, pass text through)
- The only hardcoded beverage logic: `_COLOR_PATTERNS` / `_extract_color_as_flavor` in parser.py, and hardcoded `beverages` import paths in RuleLoader

### 3.1 — Generalize RuleLoader

**File**: `scraping/normalization/rules/__init__.py`

1. Replace hardcoded imports in `get_sanity_checker()` and `get_inference_fn()` with dynamic imports based on `_category_dir()`:
   ```python
   # Before: from ...rules.category.beverages.sanity import sanity_check_size
   # After:  importlib.import_module(f"scraping.normalization.rules.category.{cat_dir}.sanity")
   ```

2. Expand `_CATEGORY_DIR_MAP` with new categories:
   ```python
   _CATEGORY_DIR_MAP = {
       "spirtsiz-ickiler": "beverages",
       "sud-mehsullari": "dairy",
       "sirniyyat-cerezler": "snacks",
       "temizlik-vasiteleri": "cleaning",
       "sexsi-baxim-kosmetika": "personal_care",
       # ... add as we expand
   }
   ```

3. Add `get_custom_extractors()` method — loads category-specific Python extractors from `rules/category/{name}/extractors.py` if it exists.

### 3.2 — Generalize Parser Output

**File**: `scraping/normalization/parser.py`

1. Add `category_attrs` dict to output — stores category-specific extractions (e.g., `is_sparkling` for beverages, `fat_percent` for dairy)
2. Move `_COLOR_PATTERNS` / `_extract_color_as_flavor` into `rules/category/beverages/` as a custom extractor
3. After main pipeline, call `rule_loader.get_custom_extractors()` and run each
4. **Backwards compatible**: Keep `is_sparkling` as top-level field for beverages (also in `category_attrs`)

### 3.3 — Create Empty Category Directories

For each planned category, create `rules/category/{name}/` with `__init__.py`. Having the directory exist (even empty) is enough for the parser to run — general rules (brand, size) still work, category-specific steps return empty.

### 3.4 — Update Downstream Consumers

- **Extractors** (wolt.py, araz_website.py, neptun_website.py, bazarstore_website.py): Pass through `category_attrs`
- **golden.py**: Handle `category_attrs` consensus (apply `most_frequent()` to each key)
- **Matchers**: No changes — existing tiers work as-is, new category-specific tiers added later
- **Review UI**: Support `category_attrs` display in templates

### 3.5 — Verify No Regression

**Critical**: Run beverages normalization in dry-run mode before and after refactoring. Diff output — there must be ZERO changes to existing parsed fields.

```bash
# Before refactoring
python manage.py normalize_products --market araz --source-type wolt --category spirtsiz-ickiler --dry-run > before.json
# After refactoring
python manage.py normalize_products --market araz --source-type wolt --category spirtsiz-ickiler --dry-run > after.json
# Diff
diff before.json after.json  # Must be empty (except category_attrs addition)
```

**Files to modify**:
| File | Change |
|------|--------|
| `rules/__init__.py` | Dynamic imports, `_CATEGORY_DIR_MAP`, `get_custom_extractors()` |
| `parser.py` | `category_attrs` output, move color-as-flavor to beverages |
| `rules/category/beverages/extractors.py` | New: beverage-specific extractors (sparkling, color-as-flavor) |
| `extractors/*.py` | Pass through `category_attrs` |
| `golden.py` | Consensus for `category_attrs` |
| `review/views.py` | Display `category_attrs` |

---

## Phase 4: Category Expansion

**Goal**: Expand to consumer staple categories. For each category, the process is:

1. **Profile data** — examine raw products, understand naming patterns
2. **Create category rules** — `rules/category/{name}/` with relevant JSON files
3. **Create category mappings** — for each marketplace in `rules/market/{market}/`
4. **Expand brand dictionary** — add category-specific brands
5. **Normalize** — run for all marketplaces
6. **Match** — intra-marketplace dedup + cross-source
7. **Review & iterate** — check quality, fix rules, re-run

### 4.1 — Dairy (Süd mehsulları)

**Subcategories**: Süd (501), Pendir (502), Yogurt & Qatıq (503), Kefir & Ayran (504), Qaymaq & Xama (505), Kəsmik & Şor (506), Kərə yağı (507)

**Category-specific attributes**:
- Fat percentage (1.5%, 2.5%, 3.2%, etc.)
- Product subtype more critical than beverages (kefir vs ayran vs süd)

**Expected rule files**:
- `rules/category/dairy/product_types.json` — süd, kefir, ayran, yogurt, qatıq, pendir, qaymaq, xama, kəsmik
- `rules/category/dairy/packaging.json` — tetra, plastic cup, glass jar, bag, box
- `rules/category/dairy/flavors.json` — çiyələk, banan, şaftalı, təbii, etc.
- `rules/category/dairy/stop_words.json`
- `rules/category/dairy/extractors.py` — fat percentage extractor

### 4.2 — Snacks (Şirniyyat & Çərəzlər)

**Subcategories**: Şokolad & Konfet (1301), Peçenye & Vafli (1302), Saqqız (1303), Çipslər & Kraker (1304)

**Category-specific considerations**:
- Weight-based (grams) — size extraction already handles `g`/`kg`
- Flavor variants very common (chips: duz, ketçup, qaymaq-soğan; chocolate: süd, tünd, ağ)
- Pack sizes common (multi-packs)

### 4.3 — Cleaning (Təmizlik vasitələri)

**Subcategories**: Paltaryuyan (1801), Qabyuyan (1802), Ümumi təmizlik (1803), Həşəratlara qarşı (1804)

**Category-specific considerations**:
- Volume (ml/L) or weight (g/kg)
- Product subtype is key differentiator (gel, powder, liquid, spray)
- Scent variants (lavender, lemon, etc.) — use flavor field
- Count-based products (dishwasher tablets: 40 tabs, 80 tabs)

### 4.4 — Personal Care (Şəxsi baxım & Kosmetika)

**Subcategories**: Duş & Hamam (1901), Saç baxımı (1902), Diş baxımı (1903), Dezodorant (1904), Təraş (1905), Qadın gigiyenası (1906), Ətirlər (1907), Kosmetika (1908)

**Category-specific considerations**:
- Volume (ml) for liquids, count for disposables
- Scent/variant critical (shampoo scents, toothpaste types)
- Gender variants possible (men's/women's deodorant)

### 4.5 — Additional Categories (Lower Priority)

After the big four, continue with:
- Quru qida (Dry foods) — rice, pasta, flour
- Sous & Ədviyyat (Sauces & Spices)
- Konservlər & Turşular (Canned goods)
- Çay & Kofe (Tea & Coffee)
- Uşaq məhsulları (Baby products)
- And remaining categories

### Per-Category Checklist

For each new category:
- [ ] Profile raw products from at least 2 marketplaces
- [ ] Create `rules/category/{name}/` with product_types.json, packaging.json, flavors.json, stop_words.json
- [ ] Register in `_CATEGORY_DIR_MAP`
- [ ] Add category mappings for Araz Wolt, Araz Website, Neptun Wolt, Neptun Website, Bravo Wolt, Bazarstore Website
- [ ] Add missing brands to brands.json
- [ ] Normalize all marketplaces (dry-run first)
- [ ] Check brand_not_found < 5%, size_not_found < 3%
- [ ] Run intra-marketplace matching
- [ ] Run cross-source matching (Araz, Neptun)
- [ ] Review golden records in UI
- [ ] Fix rules and re-run as needed

---

## Phase 5: Inter-Marketplace Matching (Future)

**Goal**: Create a single unified golden record per physical product, linking data from all marketplaces.

### Architecture

```
Per-market golden records         Unified canonical product
┌─────────────────────┐          ┌───────────────────────────┐
│ araz_product_matches │──┐      │ canonical_products         │
├─────────────────────┤  │      │                           │
│ neptun_product_matches├─┼──▶  │ canonical_product_id: uuid │
├─────────────────────┤  │      │ brand, name, size, unit    │
│ bravo_product_matches │──┤      │ packaging, flavor, barcode │
├─────────────────────┤  │      │ category_id, image         │
│ bazarstore_product_  │──┘      │ market_links: [            │
│ matches              │          │   {market: araz, golden_id}│
└─────────────────────┘          │   {market: neptun, ...}    │
                                 │ ]                          │
                                 └───────────────────────────┘
```

### Matching Strategy
1. **Barcode** — where available across marketplaces (highest confidence)
2. **Exact fields** — (normalized_brand, normalized_name, size, unit, packaging) across market golden records
3. **Fuzzy** — with manual review
4. **Unmatched** — market-exclusive products still become canonical products with single market link

### New Command
```bash
python manage.py match_products --scope inter_marketplace --category spirtsiz-ickiler
```

---

## Phase 6: Django Integration + Frontend (Future)

**Goal**: Sync canonical products to Django ORM for proper API and consumer frontend.

### Model Updates
- `Product`: Populate from canonical golden records
- `MarketProduct`: Link each market's offering to the Product
- `Price`: Import branch-level prices with timestamps
- `Market` / `MarketBranch`: Populate from Wolt branch data + website info

### API
- Product search/browse endpoints
- Price comparison per product
- Category browsing
- Filtering by market, branch, price range

### Frontend
- Product search with autocomplete
- Category browsing with filters
- Price comparison cards
- Price history charts (once we have multiple scrape runs)

---

## Verification Strategy

For every phase:
1. **Dry-run first** — always run normalization with `--dry-run` before writing to MongoDB
2. **Metric comparison** — track key metrics before/after (golden record count, match type distribution, warning rates)
3. **Spot-check** — manually verify 10+ known products in the review UI
4. **Regression check** — when refactoring (Phase 3), ensure existing beverage results don't change
5. **Review UI** — use dashboard, warnings view, and singles view to find systematic issues

---

## Risk Register

| Risk | Impact | Phase | Mitigation |
|------|--------|-------|------------|
| Bazarstore Shopify format has unexpected quirks | Medium | 1 | Profile data thoroughly before building extractor |
| Quality fixes change golden records, breaking review UI references | Low | 2 | Golden record IDs are UUIDs, regenerated on re-match |
| Generic parser refactor breaks beverage results | High | 3 | Before/after diff of dry-run output as verification gate |
| New categories have very different naming patterns | Medium | 4 | Start with profiling, iterate rules based on remaining_data |
| Bare volume fallback (0.33 → 330ml) wrong for non-beverages | Medium | 3-4 | Make bare-volume unit configurable per category |
| Inter-marketplace matching has low barcode overlap | High | 5 | Invest in name-based matching quality in Phase 2 |
| Brand dictionary becomes unwieldy at scale | Medium | 4 | Consider per-category brand lists or brand detection improvements |
