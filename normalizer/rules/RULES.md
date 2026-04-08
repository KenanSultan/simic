# Product Normalization Rules System

## 1. Introduction

### What This System Does

Simic scrapes product data from multiple Azerbaijani grocery marketplaces (Araz, Bazarstore, Bravo, Neptun). Each marketplace names, categorizes, and structures products differently. The **rules system** transforms raw product names into structured, comparable data.

For example, the raw product name:

```
Coca-Cola® Portağal 500 ml Pet
```

Gets parsed into:

| Field | Value | Extracted By |
|---|---|---|
| brand | Coca-Cola | Brand dictionary (general) |
| flavor | Portağal | Flavor patterns (category: beverages) |
| size | 500.0 | Size regex (general) |
| unit | ml | Unit map (general) |
| packaging | pet | Packaging patterns (category: beverages) |
| is_sparkling | null | Sparkling patterns (category: beverages) |
| product_type | null | Product type patterns (category: beverages) |
| remaining_data | null | Everything unrecognized |
| normalized_name | coca cola | For matching across sources |

This structured data enables **product identification** — matching the same physical product across different marketplaces that name it differently.

### Why Rules Are Separated By Scope

Not all rules apply everywhere:
- **"Portağal" is a flavor** — but only for beverages. In a cleaning products category, "Portağal" might mean "orange-scented" and need different handling.
- **"Pet" means PET plastic bottle** — for beverages. In a pet food category, "Pet" means something else entirely.
- **Araz's category "Spirtsiz Içkilər"** maps to canonical ID 1405 (Cola & Soda) by default — but this mapping only applies to Araz's Wolt data.

By organizing rules into explicit scopes, we avoid cross-contamination and make it clear which rules affect which products.

---

## 2. Architecture Overview

### Scope Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│  GENERAL (rules/general/)                               │
│  Applies to ALL products, ALL categories, ALL markets   │
│  • Text normalization (diacritics, Unicode)              │
│  • Size/volume extraction (ml, l, kg, g)                │
│  • Brand dictionary (Coca-Cola, Pepsi, Sirab, ...)      │
│  • Piece count removal (1əd, 1 ədəd)                    │
│                                                         │
│  ┌───────────────────────────────────────────────────┐   │
│  │  CATEGORY (rules/category/beverages/)             │   │
│  │  Applies to ONE product category                  │   │
│  │  • Packaging (glass, pet, can, tetra)             │   │
│  │  • Sparkling/still detection                      │   │
│  │  • Flavor dictionary (portağal, limon, ...)       │   │
│  │  • Product types (kompot, nektar, limonad, ...)   │   │
│  │  • Stop words (su, içki, və)                      │   │
│  │  • Volume sanity checks (max 30L)                 │   │
│  │                                                   │   │
│  │  ┌─────────────────────────────────────────────┐  │   │
│  │  │  MARKET (rules/market/araz/)                │  │   │
│  │  │  Applies to ONE marketplace                 │  │   │
│  │  │  • Category mappings (Wolt → canonical)     │  │   │
│  │  │  • Category mappings (website → canonical)  │  │   │
│  │  │                                             │  │   │
│  │  │  ┌───────────────────────────────────────┐  │  │   │
│  │  │  │  BRAND (rules/brand/) — future        │  │  │   │
│  │  │  │  Brand-specific overrides             │  │  │   │
│  │  │  └───────────────────────────────────────┘  │  │   │
│  │  └─────────────────────────────────────────────┘  │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Directory Structure

```
scraping/normalization/rules/
├── __init__.py                    # RuleLoader class
├── RULES.md                       # This documentation
│
├── general/                       # Scope: ALL products
│   ├── text.py                    #   Text normalization functions
│   ├── size.py                    #   Size/volume regex patterns
│   ├── piece_count.py             #   Piece count removal
│   └── brands.json                #   Brand dictionary with aliases
│
├── category/                      # Scope: specific product category
│   └── beverages/                 #   Category: spirtsiz-ickiler
│       ├── flavors.json           #     Flavor detection patterns
│       ├── packaging.json         #     Packaging type patterns
│       ├── sparkling.json         #     Sparkling/still detection
│       ├── product_types.json     #     Product type classification
│       ├── stop_words.json        #     Noise words to remove
│       ├── prefixes.json          #     Product-type prefixes for brand extraction
│       └── sanity.py              #     Volume sanity checks (Python logic)
│
├── market/                        # Scope: specific marketplace
│   └── araz/                      #   Market: Araz
│       ├── wolt_categories.json   #     Wolt category → canonical mapping
│       └── website_categories.json#     Website category → canonical mapping
│
└── brand/                         # Scope: specific brand (future)
    └── (empty)
```

### Data Flow

```
Raw product name
       │
       ▼
┌──────────────┐     ┌─────────────────┐
│  parser.py   │────▶│   RuleLoader    │
│  (orchestr.) │◀────│  (loads rules)  │
└──────┬───────┘     └─────────────────┘
       │
       │  Step 1: clean_text()                    ← general/text.py
       │  Step 2: extract_brand()                 ← general/brands.json + category/*/prefixes.json
       │  Step 3: extract_size()                  ← general/size.py
       │  Step 4: sanity_check_size()             ← category/*/sanity.py
       │  Step 5: extract_packaging()             ← category/*/packaging.json
       │  Step 6: extract_sparkling()             ← category/*/sparkling.json
       │  Step 7: extract_product_type()          ← category/*/product_types.json
       │  Step 8: extract_flavor()                ← category/*/flavors.json
       │  Step 9: remove stop words               ← category/*/stop_words.json
       │  Step 10: remove piece counts            ← general/piece_count.py
       │  Step 11: color-as-flavor fallback       ← parser.py (hardcoded)
       │
       ▼
Structured output (brand, flavor, size, unit, packaging, ...)
```

---

## 3. Understanding Rule Scopes

### General Scope (`rules/general/`)

**What it means**: These rules apply to every single product, regardless of category or marketplace.

**When to add a rule here**: When the rule is universally true. If you'd apply it to water, beer, shampoo, and rice — it belongs in general.

**What lives here**:
- **Text normalization** (`text.py`): Azerbaijani diacritics (ə→e, ş→s), Unicode handling, doubled consonant collapsing (cappuccino→capucino). These are language-level rules, not product-specific.
- **Size extraction** (`size.py`): Regex patterns for volume/weight (500ml, 1.5l, 250gr). Every packaged product has a size.
- **Brand dictionary** (`brands.json`): The brand list is shared across all categories. "Coca-Cola" is the same brand whether it's a cola or an ice cream.
- **Piece count** (`piece_count.py`): "1 ədəd" (1 piece) is meaningless — every product is 1 piece by default.

**Example**: The diacritics map `ə→e` must be general because every Azerbaijani product name contains these characters, regardless of what category it belongs to.

### Category Scope (`rules/category/<name>/`)

**What it means**: These rules apply only when processing products from a specific product category.

**When to add a rule here**: When the rule is true for one category but would be wrong or irrelevant for another.

**Currently defined categories**:
- `beverages/` → canonical category slug `spirtsiz-ickiler`

**What lives here (beverages example)**:
- **Flavors** (`flavors.json`): "Portağal" means orange flavor in beverages. In cleaning products, it would be a scent.
- **Packaging** (`packaging.json`): "Pet" means PET bottle in beverages. In pet supplies, it means something else.
- **Sparkling/still** (`sparkling.json`): Only relevant for beverages — doesn't apply to snacks or cleaning products.
- **Product types** (`product_types.json`): "Kompot", "Nektar", "Limonad" are beverage-specific classifications.
- **Stop words** (`stop_words.json`): "Su" (water) is noise in beverage names. In a bottled water category it's redundant. But "su" in "su pompası" (water pump) is essential.
- **Prefixes** (`prefixes.json`): "Soyuq kofe" (cold coffee) appears before brand names in beverages only.
- **Sanity checks** (`sanity.py`): "If volume > 30L, unit was probably wrong" — only makes sense for beverages.

**How to create a new category**: See [Section 5: How-To Guides](#adding-a-new-product-category).

### Market Scope (`rules/market/<name>/`)

**What it means**: These rules apply only to one marketplace's data.

**When to add a rule here**: When the rule maps that marketplace's internal structure to the canonical structure.

**What lives here**:
- **Category mappings**: Each marketplace has its own category hierarchy. These JSON files map marketplace-specific categories to canonical category IDs.

**Two-layer mapping system**: Marketplace categories are often imprecise. A single Wolt category "Spirtsiz Içkilər" contains sodas, juices, teas, and coffees mixed together. The mapping system handles this:

1. **Direct mappings** (clean 1:1): `"Cola və Sodalar" → 1405`
2. **Rule-based mappings** (catch-all categories): If the product name contains "kompot" → 1404, "ice tea" → 1409, else default to 1405

### Brand Scope (`rules/brand/`) — Future

**What it would mean**: Rules that apply only to products from a specific brand. For example, "Red Bull" products always have size in ml and are always carbonated — you could encode this as brand-specific defaults.

**Not implemented yet** — the directory exists as a placeholder.

---

## 4. Rule File Reference

### `general/brands.json` — Brand Dictionary

**Purpose**: Maps brand name aliases to a single canonical name. Used for brand extraction from product names.

**Schema**:
```json
{
    "version": 1,
    "description": "Human-readable description",
    "brands": [
        {
            "canonical": "Coca-Cola",
            "aliases": ["Coca-Cola®", "Coca-Cola", "Coca Cola", "CocaCola", "Cola-Сola®"]
        }
    ]
}
```

**Field details**:
| Field | Type | Description |
|---|---|---|
| `canonical` | string | The standardized brand name used in output |
| `aliases` | string[] | All known spellings/variations. Include trademark symbols, transliterations, common typos |

**Important**: Multi-word brands must come before their component words in the dictionary. The RuleLoader sorts by alias length (longest first) automatically, so "Full Ice Tea" will be tried before "Full".

---

### `category/*/flavors.json` — Flavor Patterns

**Purpose**: Extract flavor/taste information from product names. Supports single flavors and multi-flavor products.

**Schema**:
```json
{
    "scope": "category",
    "category": "spirtsiz-ickiler",
    "description": "Human-readable description",
    "compound_patterns": [
        {
            "patterns": ["qara\\s+qarağat", "qara\\s+qaragat", "black\\s*currant"],
            "canonical": "Qara qarağat"
        }
    ],
    "single_patterns": [
        {
            "patterns": ["portağal", "portagal", "apelsin", "orange"],
            "canonical": "Portağal"
        }
    ]
}
```

**Field details**:
| Field | Type | Description |
|---|---|---|
| `compound_patterns` | array | Multi-word flavor patterns. **Checked before single patterns** to prevent partial matches |
| `single_patterns` | array | Single-word flavor patterns |
| `patterns` | string[] | Regex alternatives (without `\b` word boundaries — added automatically by RuleLoader) |
| `canonical` | string | Standardized flavor name in output |

**Multi-flavor behavior**: The parser finds ALL matching flavors and joins them with `-`. Example: "Çiyələk və Yemiş" → `"Çiyələk-Yemiş"`.

**Regex tips**:
- Use `\\s+` for whitespace between words (not literal space — handles tab, multiple spaces)
- Use `[\\s-]+` to match both space and hyphen (for "Mango-Ananas" and "Mango Ananas")
- Include Azerbaijani, Turkish, Russian, and English variants of the same flavor
- No need to add `\\b` — the RuleLoader wraps each pattern in `\b...\b` automatically

---

### `category/*/packaging.json` — Packaging Type Patterns

**Purpose**: Detect the container/packaging material. Extracted and **removed** from the product name.

**Schema**:
```json
{
    "scope": "category",
    "category": "spirtsiz-ickiler",
    "description": "Human-readable description",
    "patterns": [
        {"regex": "\\bşüşə\\b", "type": "glass"},
        {"regex": "\\bpet\\b", "type": "pet"},
        {"regex": "\\bbanka\\b", "type": "can"},
        {"regex": "\\btetra\\s*pa[rc]k\\b", "type": "tetra"}
    ]
}
```

**Field details**:
| Field | Type | Description |
|---|---|---|
| `regex` | string | Full regex pattern (include `\b` boundaries yourself) |
| `type` | string | Standardized packaging type: `glass`, `pet`, `can`, `tetra` |

**Order matters**: More specific patterns must come first. `"şüşə qabda"` (in glass container) should precede `"şüşə"` (glass) to avoid partial matches.

---

### `category/*/sparkling.json` — Sparkling/Still Detection

**Purpose**: Detect whether a beverage is carbonated or still.

**Schema**:
```json
{
    "scope": "category",
    "category": "spirtsiz-ickiler",
    "patterns": [
        {"regex": "\\bqazl[ıi]\\b", "value": true},
        {"regex": "\\bqazsız\\b", "value": false}
    ]
}
```

**Field details**:
| Field | Type | Description |
|---|---|---|
| `regex` | string | Full regex pattern |
| `value` | boolean | `true` = sparkling/carbonated, `false` = still/non-carbonated |

---

### `category/*/product_types.json` — Product Type Classification

**Purpose**: Classify what type of product this is within the category (e.g., "Kompot" vs "Nektar" within juices). Detected and **removed** from the product name.

**Schema**:
```json
{
    "scope": "category",
    "category": "spirtsiz-ickiler",
    "patterns": [
        {"regex": "\\bkompot(?:u|lar)?\\b", "type": "Kompot"},
        {"regex": "\\blimonad(?:ı)?\\b", "type": "Limonad"}
    ]
}
```

**Field details**:
| Field | Type | Description |
|---|---|---|
| `regex` | string | Full regex pattern (include common suffixes like possessive markers) |
| `type` | string | Human-readable product type name |

**Note on suffixes**: Azerbaijani adds possessive/plural suffixes to words. "Kompot" can appear as "Kompotu" (possessive), "Kompotlar" (plural). Include common variants in the regex: `kompot(?:u|lar)?`.

---

### `category/*/stop_words.json` — Noise Removal

**Purpose**: Remove words and phrases from product names that add no identifying information.

**Schema**:
```json
{
    "scope": "category",
    "category": "spirtsiz-ickiler",
    "phrases": [
        "enerji\\s+(?:içkisi|ickisi|ichkisi)",
        "qazl[ıi]\\s+(?:içki|icki)"
    ],
    "words": ["su", "içki", "və", "ve"]
}
```

**Field details**:
| Field | Type | Description |
|---|---|---|
| `phrases` | string[] | Multi-word regex patterns. Processed first (before single words) |
| `words` | string[] | Single words. Compiled into one regex with word boundaries |

**When to add a stop word**: When a word appears in the product name but doesn't help identify the product. "Su" (water) in "Sirab Qazsız Su 500ml" is redundant — everyone knows Sirab is water. But be careful: the same word might be important in a different category.

---

### `category/*/prefixes.json` — Brand Extraction Prefixes

**Purpose**: Product-type descriptors that appear before the brand name. The parser strips these prefixes to find the brand.

**Schema**:
```json
{
    "scope": "category",
    "category": "spirtsiz-ickiler",
    "prefixes": ["soyuq kofe", "qazlı içki", "sok", "mineral", "su"]
}
```

**Example**: In "Soyuq Kofe MacCoffee Latte 240ml", the prefix "Soyuq Kofe" (Cold Coffee) is stripped, allowing "MacCoffee" to be recognized as the brand.

---

### `market/*/wolt_categories.json` — Wolt Category Mapping

**Purpose**: Map Wolt delivery app categories to canonical category IDs.

**Schema**:
```json
{
    "version": 2,
    "market": "araz",
    "source_type": "wolt",
    "direct_mappings": [
        {
            "wolt_category": "Cola və Sodalar",
            "canonical_category_id": 1405,
            "canonical_category_name": "Cola & Soda"
        }
    ],
    "rule_based_mappings": [
        {
            "wolt_category": "Spirtsiz Içkilər",
            "rules": [
                {
                    "keywords": ["kompot", "kompotu"],
                    "canonical_category_id": 1404,
                    "canonical_category_name": "Kompot"
                }
            ],
            "default_canonical_category_id": 1405,
            "default_canonical_category_name": "Cola & Soda"
        }
    ]
}
```

**Two-layer system**:
- **`direct_mappings`**: For categories that map cleanly 1:1. Use when every product in that Wolt category belongs to the same canonical category.
- **`rule_based_mappings`**: For "catch-all" categories containing mixed products. Each rule has `keywords` (matched against the normalized product name) and a target `canonical_category_id`. Rules are checked in order; first match wins. If no rule matches, `default_canonical_category_id` is used.

---

## 5. How-To Guides

### Adding a New Brand

1. Open `rules/general/brands.json`
2. Add a new entry to the `"brands"` array:
```json
{"canonical": "NewBrand", "aliases": ["NewBrand", "NEWBRAND", "New Brand", "Нью Бренд"]}
```
3. Include all known spellings: with/without diacritics, with/without spaces, Cyrillic transliterations, trademark symbols
4. If the brand is multi-word (e.g., "Red Bull"), also add shorter aliases if they're unambiguous
5. Test:
```bash
python -c "
from scraping.normalization.rules import RuleLoader
from scraping.normalization.parser import parse_product_name
loader = RuleLoader(category_slug='spirtsiz-ickiler', market='araz')
r = parse_product_name('NewBrand Portağal 500ml', loader)
print(f'brand={r[\"brand\"]}')
"
```

### Adding a New Flavor

**Single flavor**:
1. Open `rules/category/beverages/flavors.json`
2. Add to `"single_patterns"`:
```json
{"patterns": ["avokado", "avocado"], "canonical": "Avokado"}
```

**Compound flavor** (multi-word):
1. Add to `"compound_patterns"` (these are checked FIRST):
```json
{"patterns": ["yaşıl\\s+alma", "green\\s+apple"], "canonical": "Yaşıl alma"}
```

**Important**: If your flavor contains a word that's also a single-word flavor (e.g., "Yaşıl Alma" contains "Alma"), the compound pattern MUST be in `compound_patterns` so it matches before the single "Alma" pattern.

### Adding a New Packaging Type

1. Open `rules/category/beverages/packaging.json`
2. Add a new pattern:
```json
{"regex": "\\bnew_package\\b", "type": "new_type"}
```
3. If the pattern is more specific than existing ones (e.g., "şüşə qabda" vs "şüşə"), add it **before** the shorter pattern.

### Adding a New Product Type

1. Open `rules/category/beverages/product_types.json`
2. Add a new pattern:
```json
{"regex": "\\bnew_type(?:u|lar)?\\b", "type": "New Type Name"}
```
3. Include common Azerbaijani suffixes: possessive (`-u`, `-ı`), plural (`-lar`, `-lər`)

### Adding a New Stop Word

1. Open `rules/category/beverages/stop_words.json`
2. For a single word: add to `"words"` array
3. For a multi-word phrase: add regex to `"phrases"` array
4. **Be careful**: verify the word is truly noise. Test that removing it doesn't cause false matches between different products.

### Adding a New Market

1. Create directory: `rules/market/<market_name>/`
2. Create `__init__.py` (empty)
3. Create `wolt_categories.json` with category mappings (if marketplace is on Wolt)
4. Create `website_categories.json` with website category mappings (if marketplace has a website)
5. Use the same JSON schema as `rules/market/araz/wolt_categories.json`

### Adding a New Product Category

1. Create directory: `rules/category/<category_name>/`
2. Create `__init__.py` (empty)
3. Create whichever JSON rule files are relevant (you don't need all of them):
   - `flavors.json` — if products have flavors/variants
   - `packaging.json` — if packaging type matters
   - `sparkling.json` — if there's a binary attribute like sparkling/still
   - `product_types.json` — if products have subtypes within the category
   - `stop_words.json` — if category-specific words are noise
   - `prefixes.json` — if product names have category descriptors before the brand
   - `sanity.py` — if you need Python logic for validation
4. Register the category in `rules/__init__.py`:
```python
_CATEGORY_DIR_MAP = {
    "spirtsiz-ickiler": "beverages",
    "your-category-slug": "your_directory_name",   # ← add this
}
```

---

## 6. The Parser Pipeline

### Extraction Order (and Why It Matters)

The parser processes the product name in a specific order. Each step removes or modifies text, affecting what subsequent steps see.

| Step | Extracts | Removes from name? | Why this order? |
|---|---|---|---|
| 1. Clean text | — | Normalizes whitespace, Unicode | Must be first — all regex depends on clean input |
| 2. Brand | `brand` | Yes | Brand is typically the first word(s) — extract before anything else |
| 3. Size/unit | `size`, `unit`, `pack_size` | Yes | Size patterns like "500ml" are unambiguous — remove early |
| 4. Sanity check | — | — | Fix size errors before they propagate |
| 5. Packaging | `packaging` | Yes | "Pet", "Şüşə" must be removed before flavor extraction (otherwise "Pet" could be mistaken for something else) |
| 6. Sparkling | `is_sparkling` | Yes | "Qazlı"/"Qazsız" removed before flavor — they're not flavors |
| 7. Product type | `product_type` | Yes | "Kompot", "Limonad" removed — they're category metadata, not flavor |
| 8. Flavor | `flavor` | Yes | Extracted after all non-flavor text is removed — what remains is the descriptor |
| 9. Stop words | — | Yes | Final cleanup of noise |
| 10. Piece count | — | Yes | "1əd" removal |
| 11. Color fallback | `flavor` (if null) | Yes | Last resort — if no flavor found, a color word might indicate the variant |

### Worked Example

Input: `"Qızıl Quyu Düşes Limonad 500ml şüşə"`

| Step | Name After | Extracted |
|---|---|---|
| Clean | `Qızıl Quyu Düşes Limonad 500ml şüşə` | — |
| Brand | `Düşes Limonad 500ml şüşə` | brand=Qızıl Quyu |
| Size | `Düşes Limonad şüşə` | size=500.0, unit=ml |
| Packaging | `Düşes Limonad` | packaging=glass |
| Sparkling | `Düşes Limonad` | is_sparkling=null |
| Product type | `Düşes` | product_type=Limonad |
| Flavor | (empty) | flavor=Düşes |
| Stop words | (empty) | — |
| Final | remaining_data=null | |

**Output**:
```json
{
    "brand": "Qızıl Quyu",
    "size": 500.0,
    "unit": "ml",
    "packaging": "glass",
    "is_sparkling": null,
    "product_type": "Limonad",
    "flavor": "Düşes",
    "remaining_data": null,
    "normalized_name": "qizil quyu"
}
```

### Fallback Mechanisms

1. **Brand prefix stripping**: If brand not found at start, strip known prefixes (e.g., "Soyuq Kofe") and try again
2. **Brand anywhere search**: If still not found, search for brand anywhere in the name (handles "Feyxoa Kompotu Bağdan 1l" where brand is at the end)
3. **Bare volume fallback**: If no unit found, bare decimals like "0.33" assumed to be liters → 330ml
4. **Size sanity check**: If volume > 30L, likely a unit error → divide by 1000
5. **Color as flavor**: If no flavor found, color words (Red, Blue, Black) used as flavor variant indicator

---

## 7. The RuleLoader API

### Constructor

```python
from scraping.normalization.rules import RuleLoader

loader = RuleLoader(
    category_slug="spirtsiz-ickiler",  # optional: enables category-specific rules
    market="araz",                      # optional: enables market-specific rules
)
```

### Methods Reference

| Method | Scope | Returns | Reads From |
|---|---|---|---|
| `get_brands()` | General | `[(alias, canonical), ...]` sorted by length | `general/brands.json` |
| `get_prefixes()` | Category | `["prefix1", "prefix2", ...]` | `category/*/prefixes.json` |
| `get_packaging_rules()` | Category | `[(compiled_re, type_str), ...]` | `category/*/packaging.json` |
| `get_sparkling_rules()` | Category | `[(compiled_re, bool), ...]` | `category/*/sparkling.json` |
| `get_product_type_rules()` | Category | `[(compiled_re, type_str), ...]` | `category/*/product_types.json` |
| `get_flavor_rules()` | Category | `[(compiled_re, canonical_str), ...]` | `category/*/flavors.json` |
| `get_stop_words()` | Category | `([compiled_phrases], compiled_word_re)` | `category/*/stop_words.json` |
| `get_sanity_checker()` | Category | `function(size, unit)` or `None` | `category/*/sanity.py` |
| `get_category_mapping_path(src)` | Market | `Path` object | `market/*/` |

**Caching**: All JSON files are cached on first load. Call `RuleLoader()` with different parameters to get a fresh loader, but within one loader instance, files are read only once.

**Graceful degradation**: If `category_slug` is not set or the category directory doesn't exist, category-specific methods return empty lists/None. The parser handles this — it just skips those extraction steps.

---

## 8. Testing & Verification

### Quick Test: Parse a Single Product

```bash
source .venv/bin/activate
python -c "
from scraping.normalization.rules import RuleLoader
from scraping.normalization.parser import parse_product_name
loader = RuleLoader(category_slug='spirtsiz-ickiler', market='araz')
r = parse_product_name('Your Product Name 500ml', loader)
for k, v in r.items():
    if v is not None and v != []:
        print(f'{k}: {v}')
"
```

### Re-run Normalization After Rule Changes

```bash
# Re-normalize Wolt products
python manage.py normalize_products --market araz --source-type wolt --category spirtsiz-ickiler

# Re-normalize website products
python manage.py normalize_products --market araz --source-type website --category spirtsiz-ickiler

# Re-run matching
python manage.py match_products --scope intra_marketplace --market araz --source-type wolt --category spirtsiz-ickiler
python manage.py match_products --scope cross_source --market araz --category spirtsiz-ickiler
```

### What to Check After Adding Rules

1. **Parse warnings**: Look at `brand_not_found` and `size_not_found` counts — they should decrease after adding rules
2. **remaining_data field**: Query products where `remaining_data` is not null — this is unrecognized text that might need new rules
3. **Spot-check known products**: Parse specific products and verify all fields are correct
4. **Match counts**: After re-running matching, the number of exact matches should increase (or at least not decrease)

### Common Mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Forgot `\\b` in regex | Pattern matches inside other words | Add word boundaries: `\\bword\\b` |
| Single pattern before compound | "Alma" matches before "Yaşıl Alma" | Move compound to `compound_patterns` section |
| Stop word is too aggressive | Different products now match incorrectly | Remove the stop word; test with both product names |
| Regex not case-insensitive | Pattern fails on uppercase input | RuleLoader adds `re.IGNORECASE` automatically for JSON rules |
| Forgot Azerbaijani suffixes | "Kompotu" not matched by "kompot" | Add suffix variants: `kompot(?:u\|lar)?` |
| Brand alias too short | "Mia" matches inside "Premium" | Add longer context or verify word boundary behavior |

---

## 9. Design Principles

### Why Longest Match First
Brand aliases are sorted by length (longest first). "Coca-Cola®" is tried before "Coca Cola" before "Coca". This prevents shorter aliases from matching prematurely and consuming part of a longer alias.

### Why Compound Flavors Before Single
"Qara Qarağat" (blackcurrant) must be matched as a compound before "Qarağat" alone. If single patterns ran first, "Qarağat" would match and be removed, leaving orphaned "Qara" in the remaining text.

### Why Some Things Are Removed, Others Only Detected
- **Removed**: packaging, sparkling, flavor, product type, stop words — these are extracted into separate fields and would cause noise in `normalized_name` if left in
- **Not removed**: Nothing currently falls in this category after the product_type fix, but the principle is: if a word helps distinguish products during matching, keep it in the name

### Why Doubled Consonants Are Collapsed
Different sources spell the same word differently: "Cappuccino" vs "Capuccino" vs "Kapuçino". Collapsing `pp→p`, `cc→c` etc. in the normalized form makes these match. Only consonants are collapsed — vowels like `ee` in "coffee" become `cofee` but both sources collapse identically.

### Why Colors Are Fallback Flavors
Energy drinks and some sodas use colors as variant names ("Red Bull Red", "Bizon Black Diamond", "Full Blue"). When no flavor pattern matches, checking for color words catches these variants without needing brand-specific rules.
