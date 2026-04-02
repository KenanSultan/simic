# Neptun Marketplace: Normalization & Identification Plan

## Context

Extend the product identification pipeline to Neptun — the second marketplace after Araz. Neptun has 1 website + 11 Wolt branches (12 sources). Focus: Spirtsiz içkilər (non-alcoholic beverages).

### Key challenges (different from Araz):
- **Barcode coverage is terrible**: Website 0%, Wolt 11.3% (vs Araz Wolt 99.5%). Name matching is the PRIMARY identification method.
- **Wolt uses brand-level categories**: "Coca-Cola", "Pepsi", "Sirab" are categories themselves (not inside "Spirtsiz Içkilər")
- **Website uses ALL CAPS + abbreviations**: "COCA-COLA 1.5LT SEKERSIZ", "S/Q" = şüşə qab, "PL/Q" = plastik qab, "T/P" = tetra pak
- **Brand categories vary by branch**: Each Wolt branch may have different brand-level categories
- **72,727 Wolt products** across 11 branches, **11,495 website products**

---

## Phase 0: Discovery & Data Profiling

### 0.1 — Profile Neptun Wolt Beverage Data
- List all 11 branches with product counts
- List ALL categories that are beverage-related (including brand categories like "Coca-Cola", "Sirab", "Borjomi")
- Count beverage products per branch
- Check barcode coverage specifically for beverages
- Check naming consistency across branches (same barcode → same name?)
- Sample 30+ product names across different categories

**Expected output**: Category list, product counts, barcode stats, naming report

### 0.2 — Profile Neptun Website Beverage Data
- Count products in beverage categories ("Meyvə Suları" = 427, "Sular" = 167, etc.)
- Analyze ALL CAPS naming patterns and abbreviations (S/Q, PL/Q, T/P, Q/Q, etc.)
- Catalog all abbreviations used in website product names
- Sample product names and compare with Wolt names for the same products
- Check `_meta` structure for category hierarchy

**Expected output**: Category list, abbreviation catalog, naming comparison

### 0.3 — Create Category Mapping: Wolt Neptun → Canonical

Neptun Wolt has ~224 categories. Many are brand-specific (Coca-Cola, Pepsi, etc.). Need to map ALL beverage-related ones.

**File**: `rules/market/neptun/wolt_categories.json`

**Mapping strategy** (approved: map each brand category):

Direct mappings for brand categories:
- "Coca-Cola" → 1403 (Qazlı içkilər)
- "Pepsi" → 1403
- "Fanta" → 1403
- "Sprite" → 1403
- "Sirab" → 1401 (Su & Mineral su)
- "Borjomi" → 1401
- "Bonaqua" → 1401
- "Vita 1000" → 1402 (Meyvə şirəsi & Kompot)
- "Natura" → 1402
- "Qızıl Quyu" → 1403
- "Full" → 1404 (Enerji içkiləri) — or split by product line
- "7up" → 1403
- ... (all brand categories)

Rule-based for catch-all categories:
- "Diqər Spirtsiz İçkilər" → keyword rules (same as Araz's "Spirtsiz Içkilər")
- "Other" → keyword rules

**Important**: Brand categories may differ by branch. Need to check ALL 11 branches and create a union of all brand categories.

### 0.4 — Create Category Mapping: Website Neptun → Canonical

**File**: `rules/market/neptun/website_categories.json`

Neptun website categories are cleaner (product-based, not brand-based):
- "Meyvə Suları" → 1402 (Meyvə şirəsi & Kompot)
- "Sular" → 1401 (Su & Mineral su)
- (identify other beverage categories from the _meta.category_title values)

May need rule-based mapping if "Meyvə Suları" contains cold teas or coffees mixed in.

### 0.5 — Create Neptun-Specific Rules

**File**: `rules/market/neptun/abbreviations.json` (NEW — market-specific)

Neptun website uses marketplace-specific abbreviations that need expansion before parsing:

```json
{
    "scope": "market",
    "market": "neptun",
    "description": "Neptun website-specific abbreviations used in product names",
    "abbreviations": [
        {"pattern": "\\bS/Q\\b", "expansion": "şüşə", "packaging": "glass"},
        {"pattern": "\\bPL/Q\\b", "expansion": "pet", "packaging": "pet"},
        {"pattern": "\\bT/P\\b", "expansion": "tetra pak", "packaging": "tetra"},
        {"pattern": "\\bQ/Q\\b", "expansion": "qalay qab", "packaging": "can"},
        {"pattern": "\\bD/Q\\b", "expansion": "dəmir qab", "packaging": "can"}
    ]
}
```

**Implementation**: NeptunWebsiteExtractor applies abbreviation expansion BEFORE calling `parse_product_name()`.

### 0.6 — Expand Brand Dictionary

Run Wolt normalization dry-run, check for `brand_not_found` warnings.
Neptun may carry brands not available at Araz. Add new brands to `rules/general/brands.json`.

### 0.7 — Update RuleLoader for Market-Specific Rules

Add method to RuleLoader:
```python
def get_abbreviations(self):
    """Load market-specific abbreviations. Scope: MARKET."""
    # Returns list of (compiled_pattern, expansion, packaging_type)
```

---

## Phase 1: Normalize Neptun Wolt

### 1.1 — Run Normalization

The **WoltExtractor is shared** — same code as Araz. Only the category mapping differs.

```bash
python manage.py normalize_products --market neptun --source-type wolt --category spirtsiz-ickiler
```

**Output collection**: `wolt_neptun_normalised_products`

### 1.2 — Validate Normalization

- Check total products normalized (expect subset of 72,727 — only beverages)
- Check parse warnings: `brand_not_found`, `size_not_found`
- Check category distribution across 1401-1405
- Spot-check product names: are brands, sizes, flavors correctly extracted?
- Check `remaining_data` for unrecognized text
- **Iterate**: add missing brands, fix parser rules

### 1.3 — Check Naming Consistency Across Branches

Critical for intra-marketplace matching since barcode coverage is only 11.3%:
- For products with same barcode across branches: are names identical?
- For products without barcodes: how similar are names across branches?
- This determines how much we can rely on exact name matching vs fuzzy

---

## Phase 2: Intra-Marketplace Matching (Neptun Wolt)

### 2.1 — Run Matching

```bash
python manage.py match_products --scope intra_marketplace --market neptun --source-type wolt --category spirtsiz-ickiler
```

**Output collection**: `neptun_product_matches`

### 2.2 — Analyze Results

Expected: MUCH lower barcode match rate than Araz (11.3% vs 99.5%). Most matching will happen via exact fields and fuzzy.

**Key metrics to check**:
- How many golden records created?
- What % matched by barcode vs exact vs fuzzy?
- Fuzzy matches: review for false positives (critical since we rely on name matching more)
- Unmatched products: are they genuinely unique or matching failures?

### 2.3 — Handle Low Barcode Coverage

If exact name matching is insufficient (names differ across branches):
- Consider lowering fuzzy threshold from 0.85
- Or add branch-specific name normalization rules
- Or use price as an additional matching signal (same brand+size+similar price → likely same product)

---

## Phase 3: Normalize Neptun Website

### 3.1 — Build NeptunWebsiteExtractor

**New file**: `scraping/normalization/extractors/neptun_website.py`

**Key differences from ArazWebsiteExtractor**:
- Product name in `product.name` (not `product.title`)
- Price is `product.price` (float, already in AZN — no conversion needed)
- Discount price: `product.old_price`
- Category: `product._meta.category_title` + `product._meta.parent_category_title`
- Image: `product.image` (single URL, not array)
- **NO barcode field** at all
- **ALL CAPS names** — need abbreviation expansion before parsing

**Extraction flow**:
1. Load abbreviations from `rules/market/neptun/abbreviations.json`
2. Expand abbreviations in product name (S/Q → şüşə, PL/Q → pet, T/P → tetra pak)
3. Call `parse_product_name(expanded_name, rule_loader)`
4. Map to normalized schema

### 3.2 — Register in normalize_products Command

Add to `SOURCE_REGISTRY`:
```python
"website": {
    ...
    "extractor_class": NeptunWebsiteExtractor,  # when market == "neptun"
}
```

**Note**: Need to handle multiple website extractors per market. Options:
- Registry keyed by `(source_type, market)` instead of just `source_type`
- Or: single generic WebsiteExtractor with market-specific hooks

### 3.3 — Run Normalization

```bash
python manage.py normalize_products --market neptun --source-type website --category spirtsiz-ickiler
```

**Output collection**: `website_neptun_normalised_products`

### 3.4 — Validate

- Check ALL CAPS handling: are brands/flavors/sizes extracted correctly from "COCA-COLA 1.5LT SEKERSIZ"?
- Check abbreviation expansion: is "S/Q" becoming packaging=glass?
- Check parse warnings
- Compare: how do website normalized names compare to Wolt normalized names for the same products?

---

## Phase 4: Cross-Source Matching (Website vs Wolt)

### 4.1 — Run Matching

```bash
python manage.py match_products --scope cross_source --market neptun --category spirtsiz-ickiler
```

### 4.2 — Expected Challenges

- **No barcodes on either side**: Website has 0%, Wolt has 11.3%. Barcode matching won't bridge them.
- **ALL CAPS vs Mixed case**: Handled by `normalize_for_matching` (lowercases everything)
- **Abbreviations**: Handled by NeptunWebsiteExtractor expansion
- **Naming differences**: "COCA-COLA 1.5LT" vs "Coca-Cola 1.5 l" — after normalization both should be "coca cola"
- **Price for validation**: Website prices are float AZN, Wolt prices are cents. After conversion both in AZN. Can use relaxed packaging tier with price check.

### 4.3 — Validate & Iterate

- How many website products matched to Wolt golden records?
- Spot-check known products
- Check unmatched: are they website-only products or matching failures?
- Adjust fuzzy threshold if needed

---

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `rules/market/neptun/__init__.py` | Package init |
| `rules/market/neptun/wolt_categories.json` | Wolt Neptun → canonical mapping |
| `rules/market/neptun/website_categories.json` | Website Neptun → canonical mapping |
| `rules/market/neptun/abbreviations.json` | Neptun website abbreviations (S/Q, PL/Q, etc.) |
| `scraping/normalization/extractors/neptun_website.py` | Neptun website extractor |

### Modified Files
| File | Change |
|------|--------|
| `rules/general/brands.json` | Add Neptun-specific brands |
| `rules/__init__.py` | Add `get_abbreviations()` method to RuleLoader |
| `scraping/management/commands/normalize_products.py` | Handle market-specific website extractors |
| `scraping/mongo.py` | Add `wolt_neptun_normalised_products`, `website_neptun_normalised_products`, `neptun_product_matches` |

### Existing Files (reused as-is)
| File | Why reusable |
|------|-------------|
| `scraping/normalization/extractors/wolt.py` | WoltExtractor is shared across all markets |
| `scraping/normalization/parser.py` | Parser is market-agnostic, uses RuleLoader |
| `scraping/identification/matchers/*.py` | All matchers work regardless of market |
| `scraping/management/commands/match_products.py` | Already uses per-market collections |
| `rules/category/beverages/*.json` | Beverage rules are category-specific, not market-specific |

---

## Verification Checklist

### After Phase 1 (Wolt normalization):
- [ ] Products normalized: should be subset of 72,727 (beverage categories only)
- [ ] `brand_not_found` < 5% of products
- [ ] `size_not_found` < 2% of products
- [ ] Category distribution looks reasonable across 1401-1405
- [ ] Known products (Coca-Cola, Pepsi, Sirab) parse correctly

### After Phase 2 (Wolt matching):
- [ ] Barcode matches cover ~11% of products
- [ ] Exact + fuzzy matches cover most of the rest
- [ ] No obvious false matches in fuzzy tier
- [ ] Golden record count is reasonable (fewer than total products / avg branches)

### After Phase 3 (Website normalization):
- [ ] ALL CAPS handled correctly (brands extracted despite caps)
- [ ] Abbreviations expanded (S/Q → glass, T/P → tetra)
- [ ] Category assignment correct

### After Phase 4 (Cross-source matching):
- [ ] Known products match across website and Wolt
- [ ] Match rate > 50% for exact tier
- [ ] Website-only and Wolt-only products are genuinely different catalogs, not matching failures

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Low barcode coverage → poor Wolt intra-matching | High | Rely on name matching; check naming consistency first |
| Brand categories differ by branch | Medium | Create union of all branch categories; check dynamically |
| ALL CAPS abbreviations not fully cataloged | Medium | Profile website data thoroughly; iterate on abbreviation list |
| Neptun has products not in brand dictionary | Medium | Dry-run normalization, check warnings, expand dictionary |
| Wolt prices in different unit (cents vs AZN) | Low | WoltExtractor already divides by 100 |
| Website category structure too flat for mapping | Low | Use rule-based mapping for ambiguous categories |
