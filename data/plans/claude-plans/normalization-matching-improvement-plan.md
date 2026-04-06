# Normalization & Matching Improvement Plan — Beverages

## Context

Cross-source matching quality is poor (Araz 68%, Neptun 29%). Root causes:
1. Not enough structured fields extracted → noise in `normalized_name` → exact matching fails
2. Category misassignment (hot coffee in cold coffee, etc.)
3. Fuzzy matcher is dead by design (0 matches across all markets)
4. Cross-source matching cascade is too rigid — one wrong field kills the match

**Decisions from brainstorming:**
- Normalization first, then matching redesign
- Get it right for beverages — this becomes the template
- Hybrid matching: cascade for high-confidence, scoring for the rest
- Different strategies for intra-marketplace (keep current) vs cross-source (redesign)
- Brand + size are hard requirements for cross-source
- Null handling depends on the field

---

## Part 1: Normalization Improvements

### 1.1 — Category Cleanup

**Problem**: Products landing in wrong subcategories.

**Fix A — Hot coffee in "Soyuq kofe" (1410)**:
- Araz has 91 products in 1410, most are instant coffee powder (Jacobs 12.5g, Carte Noire 8g)
- Detection: if `unit=g` and `size < 100`, it's powder, not a cold beverage
- Add to `inference.py`: skip products with gram units from beverage processing
- These belong in category 15 (Çay & Kofe) — will be handled in Phase 4

**Fix B — Milkis in "Spirtsiz pivə" (1407)**:
- Milkis is a dairy-flavored carbonated drink, not non-alcoholic beer
- Add brand-specific rule in inference.py: Milkis → 1405 (Cola & Soda) or 1411 (Digər)

**Fix C — Vitamin water in "Kompot" (1404)**:
- Sarıkız Plus Qazlı Su Vitamin C → should be 1402 (Qazlı su & Mineral su)
- Fix Bravo catch-all keyword rules

**Fix D — Audit all rule-based catch-all categories**:
- Check "Spirtsiz Içkilər" (Araz Wolt), "Diqər Spirtsiz İçkilər" (Neptun), "Soyuq Çaylar, Kofelər..." (Bravo)
- Sample 20+ products from each catch-all, verify category assignment

**Files**: `rules/category/beverages/inference.py`, `rules/market/*/wolt_categories.json`

### 1.2 — New Field: `is_sugar_free` (boolean)

**Extract from product names:**
- "Zero", "Şəkərsiz", "Sekersiz", "Sugar Free", "Diet", "Light", "0 calories"

**Impact**: Currently "Coca-Cola" and "Coca-Cola Zero" differ only in `normalized_name`. With `is_sugar_free` extracted, both would have `normalized_name: "coca cola"` but differ on `is_sugar_free: false vs true`.

**Implementation**:
- Add `sugar_free.json` to `rules/category/beverages/` with regex patterns
- Add extraction step in `parser.py` (after brand, before flavor)
- Remove matched text from name

**Null semantics**: `null` = false (has sugar). Products that don't say "zero"/"şəkərsiz" have sugar by default.

### 1.3 — New Field: `product_line` (string)

**Extract from product names:**
- "Pulpy", "Max", "Twist", "Classic", "Original", "Plus", "Exotic", "Premium", "Fresh", "Ekonomik", "Slim", "Extra"

**Impact**: Currently "Fanta" and "Fanta Exotic" differ in `normalized_name`. With `product_line` extracted, both have `normalized_name: "fanta"` but differ on `product_line: null vs "Exotic"`.

**Implementation**:
- Add `product_lines.json` to `rules/category/beverages/` with patterns
- Add extraction step in `parser.py` (after brand+size, before product_type)
- Remove matched text from name

**Null semantics**: `null` = standard/base product (no special line).

### 1.4 — Stop Words Refinement

**Already added** (safe): `napitok, plastik, qabda, paket, tebii, new`
**Reverted** (too aggressive): `meyve, meyvə`

**Fix "meyvə" properly**: Don't use as stop word. Instead ensure `product_types.json` pattern catches "meyvə şirəsi" / "meyve siresi" as a COMPLETE phrase. The issue is the product_type step removes "şirəsi" first, leaving "meyvə" orphaned. Fix: add "meyvə şirəsi" as a single pattern that matches the full phrase BEFORE individual words.

**File**: `rules/category/beverages/product_types.json` — reorder patterns, add complete phrase patterns first.

### 1.5 — Abbreviation Completeness

Already done:
- Neptun: S/Q, PL/Q, T/P, D/Q, M.SIRESI, PK
- Bazarstore: TP, BAN., M.ŞİRƏSİ

Remaining: Profile all website products for unhandled abbreviations.

---

## Part 2: Cross-Source Matching Redesign

### 2.0 — Intra-Marketplace: No Change

Current cascade works well:
- Barcode → Exact → Structured → Fuzzy → Single
- 97%+ handled by barcode+exact
- Keep as-is

### 2.1 — New Cross-Source Matching Strategy

**Hard requirements**: `brand + size + unit` must all match to even consider a pair.

**Tier 1: EXACT**
```
All extracted fields must be identical (both non-null and equal):
  normalized_brand, normalized_name, size, unit, packaging,
  flavor, is_sparkling, product_type, is_sugar_free, product_line

Confidence: 0.95
Action: auto-match
```

**Tier 2: EXACT-ON-SHARED**
```
Match on fields that are non-null on BOTH sides.
Skip any field where either side is null.
All shared fields must be identical.

Example: Website has packaging=tetra, Wolt has packaging=null
  → packaging is skipped, match on remaining fields

Confidence: 0.90
Action: auto-match
```

**Tier 3: SCORING**
```
Brand + size + unit already matched (hard requirement).

Score = weighted sum of field matches:
  +0.25  normalized_name token overlap (Jaccard on word tokens)
  +0.20  flavor match (exact or null=neutral)
  +0.15  packaging match (exact or null=neutral)
  +0.15  product_type match (exact or null=neutral)
  +0.10  is_sugar_free match (null=false)
  +0.10  product_line match (null=neutral)
  +0.05  price similarity (within 15%)

Score ≥ 0.70: auto-match, confidence = score
Score 0.50-0.70: match with needs_review=true
Score < 0.50: no match
```

**Tier 4: UNMATCHED**
```
Website product → create website-only golden record
```

### 2.2 — Per-Field Null Semantics

| Field | Null meaning | Null vs Null | Null vs Value |
|---|---|---|---|
| packaging | Unknown (often missing from Wolt) | Match | Neutral (skip) |
| flavor | Plain/original (context-dependent) | Match | Neutral (skip) |
| is_sparkling | Not applicable / unknown | Match | Neutral (skip) |
| product_type | Parser didn't detect | Match | Neutral (skip) |
| is_sugar_free | Has sugar (default false) | Match | Compare false vs value |
| product_line | Standard/base product | Match | Neutral (skip) |

### 2.3 — Implementation

**New file**: `scraping/identification/cross_source_matcher.py`
- `CrossSourceMatcher` class with configurable field weights
- Tier 1 (exact), Tier 2 (exact-on-shared), Tier 3 (scoring) as methods
- Returns match results with confidence and tier info

**Modified file**: `scraping/management/commands/match_products.py`
- Replace `_handle_cross_source` with call to new `CrossSourceMatcher`
- Keep same output format (update golden records, create website-only)

---

## Part 3: Execution Steps

### Step 1: Category Cleanup
1. Fix inference.py — filter gram-unit products from beverages
2. Fix Milkis brand rule
3. Fix Bravo catch-all keywords
4. Audit all catch-all categories with 20+ product samples
5. Re-normalize all markets, verify category distributions

### Step 2: Parser Field Additions
1. Add `is_sugar_free` extraction (sugar_free.json + parser step)
2. Add `product_line` extraction (product_lines.json + parser step)
3. Fix "meyvə şirəsi" product_type pattern ordering
4. Update extractors (wolt.py, araz_website.py, neptun_website.py, bazarstore_website.py) to pass new fields
5. Update golden.py consensus for new fields
6. Re-normalize all markets, check that normalized_names are cleaner

### Step 3: Cross-Source Matcher
1. Implement `CrossSourceMatcher` class
2. Implement Tier 1 (exact), Tier 2 (exact-on-shared), Tier 3 (scoring)
3. Update match_products.py command
4. Run cross-source for Araz and Neptun
5. Compare results: match rate, tier distribution, spot-check quality

### Step 4: Verification
1. Araz cross-source: target ≥75% match rate (up from 68%)
2. Neptun cross-source: target ≥45% match rate (up from 29%)
3. Category misassignment: target <1%
4. Spot-check 20 products per market in review UI
5. Check false positive rate: review 10 scoring-tier matches manually

---

## Files to Create/Modify

| File | Action | Step |
|---|---|---|
| `rules/category/beverages/inference.py` | Modify: gram-unit filter, Milkis rule | 1 |
| `rules/market/bravo/wolt_categories.json` | Modify: fix catch-all keywords | 1 |
| `rules/category/beverages/sugar_free.json` | Create: is_sugar_free patterns | 2 |
| `rules/category/beverages/product_lines.json` | Create: product_line patterns | 2 |
| `rules/category/beverages/product_types.json` | Modify: fix meyvə şirəsi ordering | 2 |
| `scraping/normalization/parser.py` | Modify: add is_sugar_free + product_line steps | 2 |
| `scraping/normalization/extractors/*.py` | Modify: pass new fields | 2 |
| `scraping/identification/golden.py` | Modify: consensus for new fields | 2 |
| `scraping/identification/cross_source_matcher.py` | Create: new scoring matcher | 3 |
| `scraping/management/commands/match_products.py` | Modify: use CrossSourceMatcher | 3 |
