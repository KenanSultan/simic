# Bravo Marketplace: Normalization & Identification Plan

*Created: 2026-03-31*

## Context

Extend the product identification pipeline to Bravo — the third marketplace after Araz and Neptun. Bravo has **43 Wolt branches only** (no website). Focus: Spirtsiz içkilər (non-alcoholic beverages).

Bravo is the **simplest marketplace yet**: product-type categories (like Araz, not brand-level like Neptun), excellent barcode coverage, consistent naming, and no website to handle.

---

## Data Profiling Results

### Bravo Wolt (43 branches, 290,504 total products)

**Beverage categories**: 11 product-type categories, **18,384 beverage products**.

| Category | Products | Barcode | Canonical ID |
|----------|----------|---------|-------------|
| Şirə və Nektarlar | 5,314 | 96% | 1402 |
| Cola və Sodalar | 2,676 | 88% | 1403 |
| Soyuq Çaylar, Kofelər və Digər Şirin İçkilər | 2,458 | 97% | **Rule-based** |
| Limonadlar | 2,076 | 100% | 1403 |
| Qazsız Sular | 1,587 | 97% | 1401 |
| Qazlı Sular | 1,513 | 97% | 1401 |
| Energetik və Sport İçkilər | 985 | 80% | 1404 |
| Kompotlar | 803 | 100% | 1402 |
| Spirtsiz Pivələr | 375 | 100% | 1403 |
| XXL Sular | 330 | 100% | 1401 |
| Sağlam Sular | 267 | 100% | 1401 |

**Barcode coverage: 95.1%** — excellent (vs Araz 99.5%, Neptun 2.1%).

**Names 100% consistent** across all 43 branches for same-barcode products.

### Key Differences from Araz & Neptun

| Aspect | Araz | Neptun | Bravo |
|--------|------|--------|-------|
| Branches | 26 | 11 | **43** |
| Categories | Product-type (2 catch-alls) | Brand-level (~60) | **Product-type (1 catch-all)** |
| Barcode coverage | 99.5% | 2.1% | **95.1%** |
| Website | Yes | Yes | **No** |
| Beverage products | 14,229 | 5,405 | **18,384** |

### Category Mapping Analysis

**10 direct mappings** — clean product-type categories, no ambiguity:

| Category | → Canonical |
|----------|------------|
| Qazsız Sular | 1401 (Su & Mineral su) |
| Qazlı Sular | 1401 |
| XXL Sular | 1401 |
| Sağlam Sular | 1401 |
| Şirə və Nektarlar | 1402 (Meyvə şirəsi & Kompot) |
| Kompotlar | 1402 |
| Cola və Sodalar | 1403 (Qazlı içkilər) |
| Limonadlar | 1403 |
| Spirtsiz Pivələr | 1403 |
| Energetik və Sport İçkilər | 1404 (Enerji içkiləri) |

**1 rule-based mapping** — "Soyuq Çaylar, Kofelər və Digər Şirin İçkilər" (2,458 products):

This catch-all contains:
- **Cold teas**: Full, Coolsy, Fuse Tea, Lipton, Berg soyuq çay → **1405**
- **Cold coffees**: Mac Coffee, Hell Latte/Kapuçino → **1405**
- **Flavored mineral water**: Sarıkız Qazlı Su Limon → **1401**
- **Carbonated drinks**: Harika Qarpız Qazlı İçki, Laimon Fresh → **1403**

Keywords:
- `soyuq çay`, `soyuq cay`, `ice tea`, `fuse tea` → 1405
- `soyuq kofe`, `soyuq qəhvə`, `coffee`, `kofe`, `latte`, `kapuçino`, `cappuccino` → 1405
- `mineral su`, `essentuki` → 1401
- Default → 1403

### New Brands to Add

Beverage brands from Bravo not yet in `brands.json`:
- **Coolsy** — Bravo's private label (cold tea, cola, orange)
- **Ulusu** — water brand
- **Sizlik** — water brand

---

## Implementation Steps

### Step 1: Create Bravo Rules Directory

**Create**: `scraping/normalization/rules/market/bravo/`
- `__init__.py` (empty)
- `wolt_categories.json`

No abbreviations file needed (Bravo uses standard Wolt naming, not ALL CAPS).
No website categories needed (Bravo has no website).

### Step 2: Create `wolt_categories.json`

**File**: `scraping/normalization/rules/market/bravo/wolt_categories.json`

10 direct mappings + 1 rule-based mapping. Same v2 format as Araz and Neptun.

```json
{
    "version": 2,
    "market": "bravo",
    "source_type": "wolt",
    "direct_mappings": [
        {"wolt_category": "Qazsız Sular", "canonical_category_id": 1401},
        {"wolt_category": "Qazlı Sular", "canonical_category_id": 1401},
        {"wolt_category": "XXL Sular", "canonical_category_id": 1401},
        {"wolt_category": "Sağlam Sular", "canonical_category_id": 1401},
        {"wolt_category": "Şirə və Nektarlar", "canonical_category_id": 1402},
        {"wolt_category": "Kompotlar", "canonical_category_id": 1402},
        {"wolt_category": "Cola və Sodalar", "canonical_category_id": 1403},
        {"wolt_category": "Limonadlar", "canonical_category_id": 1403},
        {"wolt_category": "Spirtsiz Pivələr", "canonical_category_id": 1403},
        {"wolt_category": "Energetik və Sport İçkilər", "canonical_category_id": 1404}
    ],
    "rule_based_mappings": [
        {
            "wolt_category": "Soyuq Çaylar, Kofelər və Digər Şirin İçkilər",
            "rules": [
                {"keywords": ["soyuq cay", "soyuq çay", "ice tea", "fuse tea", "lipton"], "canonical_category_id": 1405},
                {"keywords": ["soyuq kofe", "soyuq qəhvə", "coffee", "kofe", "latte", "kapuçino", "cappuccino"], "canonical_category_id": 1405},
                {"keywords": ["mineral su", "essentuki", "yessentuki"], "canonical_category_id": 1401}
            ],
            "default_canonical_category_id": 1403
        }
    ]
}
```

### Step 3: Add New Brands to `brands.json`

**File**: `scraping/normalization/rules/general/brands.json`

Add:
```json
{"canonical": "Coolsy", "aliases": ["Coolsy"]},
{"canonical": "Ulusu", "aliases": ["Ulusu"]},
{"canonical": "Sizlik", "aliases": ["Sizlik"]}
```

May discover more missing brands during dry-run — iterate.

### Step 4: Add Bravo Collections to `mongo.py`

**File**: `scraping/mongo.py`

```python
wolt_bravo_normalised_products = db["wolt_bravo_normalised_products"]
bravo_product_matches = db["bravo_product_matches"]
```

### Step 5: Normalize Bravo Wolt Products

```bash
python manage.py normalize_products --market bravo --source-type wolt --category spirtsiz-ickiler --dry-run
```

**Verify**:
- ~18,384 products processed
- `brand_not_found` < 3% (Bravo uses standard naming)
- `size_not_found` < 1%
- Category distribution: 1401 ~3,700, 1402 ~6,100, 1403 ~5,500, 1404 ~1,000, 1405 ~2,100
- Check `brand_not_found` products, add missing brands, re-run

Then run for real:
```bash
python manage.py normalize_products --market bravo --source-type wolt --category spirtsiz-ickiler
```

**Output**: `wolt_bravo_normalised_products` collection.

### Step 6: Intra-Marketplace Matching

```bash
python manage.py match_products --scope intra_marketplace --market bravo --source-type wolt --category spirtsiz-ickiler
```

**Expected results**:
- With 95.1% barcode coverage and 43 branches, barcode matching will handle the vast majority
- Expected golden records: ~400-500 (18,384 products / 43 branches ≈ 427 unique per branch)
- Match tier distribution: ~90% barcode, ~8% exact, ~2% single
- Names are 100% consistent → exact matching will catch remaining products

**Output**: `bravo_product_matches` collection.

### Step 7: Validate Results

```bash
python manage.py shell -c "
from scraping.mongo import db
from collections import Counter

wolt = db['wolt_bravo_normalised_products']
matches = db['bravo_product_matches']

print(f'Wolt normalized: {wolt.count_documents({})}')
print(f'Golden records: {matches.count_documents({})}')

# Match type distribution
types = Counter()
for doc in matches.find({}, {'match_type': 1}):
    types[doc['match_type']] += 1
print(f'Match types: {dict(types)}')

# Category distribution
cats = Counter()
for doc in matches.find({}, {'golden_record.canonical_category_id': 1}):
    cats[doc['golden_record']['canonical_category_id']] += 1
print(f'Categories: {dict(cats)}')
"
```

**Spot-check**:
- Known products (Coca-Cola, Sirab, Cappy, Red Bull, Fuse Tea) parse correctly
- "Soyuq Çaylar" catch-all products split correctly by keyword rules
- No obvious false matches in fuzzy tier
- Barcode matches are dominant (expected given 95.1% coverage)

---

## Files to Create/Modify

| File | Action | Notes |
|------|--------|-------|
| `rules/market/bravo/__init__.py` | Create (empty) | Package init |
| `rules/market/bravo/wolt_categories.json` | Create | 10 direct + 1 rule-based |
| `rules/general/brands.json` | Modify | Add Coolsy, Ulusu, Sizlik (+ any from dry-run) |
| `scraping/mongo.py` | Modify | Add `wolt_bravo_normalised_products`, `bravo_product_matches` |

### Existing Files — Reused As-Is

| File | Reason |
|------|--------|
| `extractors/wolt.py` | WoltExtractor is shared across all Wolt markets |
| `parser.py` | Market-agnostic, uses RuleLoader |
| `category.py` | CategoryAssigner with NFC normalization already in place |
| `matchers/*.py` | All matchers work with flavor in matching key |
| `match_products.py` | Already supports per-market collections |
| `normalize_products.py` | Already supports `--market bravo` |
| `rules/category/beverages/*` | All beverage rules are category-specific, not market-specific |

No new extractors, no new RuleLoader methods, no new management commands needed.

---

## Verification Checklist

- [ ] ~18,384 products normalized
- [ ] `brand_not_found` < 3%
- [ ] `size_not_found` < 1%
- [ ] Catch-all "Soyuq Çaylar, Kofelər..." splits correctly (tea→1405, coffee→1405, mineral→1401, default→1403)
- [ ] Golden record count ~400-500
- [ ] Barcode matches cover ~90%+ of products
- [ ] Known products parse correctly
- [ ] No false matches in fuzzy tier

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| 43 branches → larger dataset, slower processing | Low | Pipeline already handles 5,405 (Neptun); 18K is 3x but still manageable |
| "Coolsy" is a private label — may have unusual naming | Low | Sample shows standard naming (brand + flavor + size) |
| Some products in catch-all category may be miscategorized | Low | Keyword rules cover main types; default→1403 is safe fallback |
| Bravo-specific brands not in dictionary | Low | Dry-run first, check warnings, iterate (same as Neptun process) |

---

## Estimated Effort

This is the **simplest marketplace** of the three:
- No website extractor needed
- No abbreviation handling needed
- No cross-source matching needed
- Product-type categories (simple mapping, only 1 catch-all)
- High barcode coverage (barcode matching will dominate)
- Only 4 files to create/modify

Implementation: Steps 1-4 (rules + config), then Steps 5-7 (normalize + match + verify).
