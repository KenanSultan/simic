from scraping.mongo import db


# ── Market registry ──────────────────────────────────────────────

MARKETS = {
    "araz": {
        "name": "Araz",
        "matches": "araz_product_matches",
        "normalised": [
            ("wolt", "wolt_araz_normalised_products"),
            ("website", "website_araz_normalised_products"),
        ],
    },
    "neptun": {
        "name": "Neptun",
        "matches": "neptun_product_matches",
        "normalised": [
            ("wolt", "wolt_neptun_normalised_products"),
            ("website", "website_neptun_normalised_products"),
        ],
    },
    "bravo": {
        "name": "Bravo",
        "matches": "bravo_product_matches",
        "normalised": [
            ("wolt", "wolt_bravo_normalised_products"),
        ],
    },
}

DEFAULT_MARKET = "araz"


def _get_collections(market):
    """Return (product_matches_coll, [(source_name, normalised_coll), ...]) for a market."""
    cfg = MARKETS.get(market, MARKETS[DEFAULT_MARKET])
    matches = db[cfg["matches"]]
    normalised = [(s, db[c]) for s, c in cfg["normalised"]]
    return matches, normalised


# ── Helpers ──────────────────────────────────────────────────────

def _clean_remaining(remaining, product_type):
    """Strip product_type words from remaining text."""
    if not remaining or not product_type:
        return remaining
    import re
    import unicodedata

    def _normalize(s):
        return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()

    for word in product_type.split():
        stem = _normalize(word)
        if len(stem) < 3:
            continue
        words = remaining.split()
        cleaned_words = [w for w in words if not _normalize(w).startswith(stem)]
        remaining = " ".join(cleaned_words)

    remaining = remaining.strip(" .,;:-\u2013\u2014/\\*")
    return remaining or None


# ── Null filter helper ───────────────────────────────────────────

_NULL = "__null__"


def _is_null_filter(value):
    return value == _NULL


def _null_condition(field):
    """MongoDB condition for 'field is missing/null/empty'."""
    return {"$or": [{field: None}, {field: ""}, {field: {"$exists": False}}]}


# ── Query functions ──────────────────────────────────────────────

# Fields that live on normalised collections, not in golden_record
_NORMALISED_FIELDS = {"product_type", "flavor", "sparkling"}


def _build_mongo_query(filters, search):
    """Build MongoDB query dict from filters. Only golden_record fields."""
    query = {}
    and_conditions = []

    if filters:
        if filters.get("category_id"):
            query["golden_record.canonical_category_id"] = int(filters["category_id"])

        for param, path in [
            ("brand", "golden_record.brand"),
            ("match_type", "match_type"),
            ("size", "golden_record.size"),
            ("packaging", "golden_record.packaging"),
        ]:
            val = filters.get(param)
            if not val:
                continue
            if _is_null_filter(val):
                and_conditions.append(_null_condition(path))
            else:
                if param == "size":
                    try:
                        query[path] = float(val)
                    except (ValueError, TypeError):
                        query[path] = val
                else:
                    query[path] = val

    if search:
        and_conditions.append({
            "$or": [
                {"golden_record.product_name": {"$regex": search, "$options": "i"}},
                {"golden_record.original_name": {"$regex": search, "$options": "i"}},
                {"golden_record.brand": {"$regex": search, "$options": "i"}},
            ]
        })

    if and_conditions:
        if query:
            and_conditions.insert(0, query)
            return {"$and": and_conditions}
        elif len(and_conditions) == 1:
            return and_conditions[0]
        else:
            return {"$and": and_conditions}
    return query


def _has_normalised_filters(filters):
    """Check if any filter targets a normalised-only field."""
    if not filters:
        return False
    return any(filters.get(f) for f in _NORMALISED_FIELDS)


def _apply_normalised_filters(docs, filters):
    """Post-query filter on enriched normalised fields. Returns filtered list."""
    if not filters:
        return docs

    result = docs
    for param, field in [
        ("product_type", "product_type"),
        ("flavor", "flavor"),
        ("sparkling", "is_sparkling"),
    ]:
        val = filters.get(param)
        if not val:
            continue
        if _is_null_filter(val):
            result = [d for d in result if not d.get("golden_record", {}).get(field)]
        elif param == "sparkling":
            if val == "yes":
                result = [d for d in result if d.get("golden_record", {}).get(field) is True]
            elif val == "no":
                result = [d for d in result if d.get("golden_record", {}).get(field) is False]
        else:
            result = [d for d in result if d.get("golden_record", {}).get(field) == val]
    return result


def get_golden_records(market, filters=None, search=None, page=1, per_page=25):
    product_matches, _ = _get_collections(market)
    query = _build_mongo_query(filters, search)
    needs_full_scan = _has_normalised_filters(filters)

    if needs_full_scan:
        # Full scan: fetch all, enrich, filter in Python, paginate in Python
        docs = list(
            product_matches.find(query).sort("golden_record.brand", 1)
        )
        enrich_with_normalised_fields(market, docs)
        docs = _apply_normalised_filters(docs, filters)
        total = len(docs)
        skip = (page - 1) * per_page
        return docs[skip : skip + per_page], total, True  # True = already enriched
    else:
        total = product_matches.count_documents(query)
        skip = (page - 1) * per_page
        docs = list(
            product_matches.find(query)
            .sort("golden_record.brand", 1)
            .skip(skip)
            .limit(per_page)
        )
        return docs, total, False  # False = needs enrichment


def enrich_with_normalised_fields(market, match_docs):
    _, all_normalised = _get_collections(market)
    ref_map = {}
    for doc in match_docs:
        refs = doc.get("products", [])
        if refs:
            ref_map[doc["match_group_id"]] = refs[0]

    if not ref_map:
        return

    found = {}
    for _, coll in all_normalised:
        or_conds = [
            {
                "product_id": ref["product_id"],
                "branch": ref["branch"],
                "source_type": ref["source_type"],
            }
            for ref in ref_map.values()
        ]
        if not or_conds:
            continue
        for ndoc in coll.find(
            {"$or": or_conds},
            {"product_id": 1, "branch": 1, "source_type": 1, "is_sparkling": 1, "flavor": 1, "remaining": 1, "remaining_data": 1, "product_type": 1},
        ):
            for mgid, ref in ref_map.items():
                if (
                    ndoc["product_id"] == ref["product_id"]
                    and ndoc["branch"] == ref["branch"]
                ):
                    product_type = ndoc.get("product_type")
                    remaining = ndoc.get("remaining_data") or ndoc.get("remaining")
                    remaining = _clean_remaining(remaining, product_type)
                    found[mgid] = {
                        "is_sparkling": ndoc.get("is_sparkling"),
                        "flavor": ndoc.get("flavor"),
                        "remaining": remaining,
                        "product_type": product_type,
                    }

    for doc in match_docs:
        extra = found.get(doc["match_group_id"], {})
        doc["golden_record"]["is_sparkling"] = extra.get("is_sparkling")
        doc["golden_record"]["flavor"] = extra.get("flavor")
        doc["golden_record"]["remaining"] = extra.get("remaining")
        doc["golden_record"]["product_type"] = extra.get("product_type")


def get_golden_record_by_id(market, match_group_id):
    product_matches, _ = _get_collections(market)
    return product_matches.find_one({"match_group_id": match_group_id})


def get_branch_products_for_match(market, match_doc):
    _, all_normalised = _get_collections(market)
    product_refs = match_doc.get("products", [])
    if not product_refs:
        return []

    or_conditions = [
        {
            "product_id": ref["product_id"],
            "branch": ref["branch"],
            "source_type": ref["source_type"],
        }
        for ref in product_refs
    ]
    results = []
    for _, coll in all_normalised:
        results.extend(coll.find({"$or": or_conditions}))
    return results


def get_products_with_warnings(market, warning_type=None, source=None, page=1, per_page=50):
    _, all_normalised = _get_collections(market)
    if warning_type:
        query = {"parse_warnings": warning_type}
    else:
        query = {"parse_warnings": {"$exists": True, "$ne": []}}

    if source and source != "all":
        collections = [(s, c) for s, c in all_normalised if s == source]
    else:
        collections = all_normalised

    all_docs = []
    total = 0
    for _, coll in collections:
        total += coll.count_documents(query)
        all_docs.extend(coll.find(query).sort("original_name", 1))

    skip = (page - 1) * per_page
    docs = all_docs[skip : skip + per_page]
    return docs, total


def get_single_branch_records(market, page=1, per_page=25):
    product_matches, _ = _get_collections(market)
    query = {"match_type": "single"}
    total = product_matches.count_documents(query)
    skip = (page - 1) * per_page
    docs = list(
        product_matches.find(query)
        .sort("golden_record.brand", 1)
        .skip(skip)
        .limit(per_page)
    )
    return docs, total


def _quality_stats_for_collection(coll):
    total = coll.count_documents({})
    return {
        "total": total,
        "no_brand": coll.count_documents(
            {"$or": [{"brand": None}, {"brand": ""}, {"brand": {"$exists": False}}]}
        ),
        "no_size": coll.count_documents(
            {"$or": [{"size": None}, {"size": {"$exists": False}}]}
        ),
        "no_barcode": coll.count_documents(
            {"$or": [{"barcode": None}, {"barcode": ""}, {"barcode": {"$exists": False}}]}
        ),
        "no_image": coll.count_documents(
            {"$or": [{"image": None}, {"image": ""}, {"image": {"$exists": False}}]}
        ),
        "with_warnings": coll.count_documents(
            {"parse_warnings": {"$exists": True, "$ne": []}}
        ),
        "brand_not_found": coll.count_documents({"parse_warnings": "brand_not_found"}),
        "size_not_found": coll.count_documents({"parse_warnings": "size_not_found"}),
    }


def get_dashboard_stats(market):
    product_matches, all_normalised = _get_collections(market)
    quality_by_source = {}
    total_normalised = 0
    total_warnings = 0
    for source_name, coll in all_normalised:
        qs = _quality_stats_for_collection(coll)
        quality_by_source[source_name] = qs
        total_normalised += qs["total"]
        total_warnings += qs["with_warnings"]

    total_golden = product_matches.count_documents({})
    is_multi_source = len(all_normalised) > 1

    coverage = None
    if is_multi_source:
        has_any_website = product_matches.count_documents({"has_website": True}, limit=1)
        if has_any_website:
            both = product_matches.count_documents(
                {"has_website": True, "match_type": {"$ne": "website_only"}}
            )
            website_only = product_matches.count_documents({"match_type": "website_only"})
            wolt_only = total_golden - both - website_only
            coverage = {"both": both, "wolt_only": wolt_only, "website_only": website_only}

    return {
        "total_golden": total_golden,
        "total_normalised": total_normalised,
        "is_multi_source": is_multi_source,
        "normalised_by_source": {s: quality_by_source[s]["total"] for s in quality_by_source},
        "warnings_by_source": {s: quality_by_source[s]["with_warnings"] for s in quality_by_source},
        "coverage": coverage,
        "needs_review": product_matches.count_documents({"needs_review": True}),
        "by_type": list(
            product_matches.aggregate(
                [{"$group": {"_id": "$match_type", "count": {"$sum": 1}}}]
            )
        ),
        "by_category": list(
            product_matches.aggregate(
                [
                    {
                        "$group": {
                            "_id": "$golden_record.canonical_category_id",
                            "count": {"$sum": 1},
                        }
                    },
                    {"$sort": {"count": -1}},
                ]
            )
        ),
        "warnings_count": total_warnings,
        "quality": quality_by_source,
    }


def get_distinct_brands(market):
    product_matches, _ = _get_collections(market)
    return sorted(
        [b for b in product_matches.distinct("golden_record.brand") if b]
    )


def get_distinct_sizes(market):
    product_matches, _ = _get_collections(market)
    sizes = [s for s in product_matches.distinct("golden_record.size") if s is not None]
    return sorted(sizes)


def get_distinct_packagings(market):
    product_matches, _ = _get_collections(market)
    return sorted(
        [p for p in product_matches.distinct("golden_record.packaging") if p]
    )


def get_distinct_product_types(market):
    _, all_normalised = _get_collections(market)
    types = set()
    for _, coll in all_normalised:
        for v in coll.distinct("product_type"):
            if v:
                types.add(v)
    return sorted(types)


def get_distinct_flavors(market):
    _, all_normalised = _get_collections(market)
    flavors = set()
    for _, coll in all_normalised:
        for v in coll.distinct("flavor"):
            if v:
                flavors.add(v)
    return sorted(flavors)


def get_images_for_matches(market, match_docs):
    _, all_normalised = _get_collections(market)
    ref_to_group = {}
    all_or = []
    for doc in match_docs:
        gid = doc["match_group_id"]
        for ref in doc.get("products", []):
            key = (ref["product_id"], ref["branch"], ref["source_type"])
            ref_to_group[key] = gid
            all_or.append(
                {
                    "product_id": ref["product_id"],
                    "branch": ref["branch"],
                    "source_type": ref["source_type"],
                }
            )

    if not all_or:
        return {}

    images = {}
    for _, coll in all_normalised:
        cursor = coll.find(
            {"$or": all_or},
            {"product_id": 1, "branch": 1, "source_type": 1, "image": 1, "local_image": 1},
        )
        for p in cursor:
            key = (p["product_id"], p["branch"], p["source_type"])
            gid = ref_to_group.get(key)
            if gid and p.get("image"):
                images.setdefault(gid, []).append(
                    {"url": p["image"], "local_image": p.get("local_image"), "branch": p["branch"]}
                )

    return images


def get_similar_groups(market, brand=None, has_website=False, page=1, per_page=20):
    product_matches, all_normalised = _get_collections(market)
    pipeline = [
        {"$match": {"golden_record.brand": {"$ne": None}}},
    ]
    if brand:
        pipeline[0]["$match"]["golden_record.brand"] = brand

    pipeline += [
        {
            "$group": {
                "_id": {
                    "brand": "$golden_record.brand",
                    "size": "$golden_record.size",
                    "unit": "$golden_record.unit",
                },
                "products": {
                    "$push": {
                        "match_group_id": "$match_group_id",
                        "product_name": "$golden_record.product_name",
                        "normalized_name": "$golden_record.normalized_name",
                        "original_name": "$golden_record.original_name",
                        "image": "$golden_record.image",
                        "local_image": "$golden_record.local_image",
                        "canonical_category_id": "$golden_record.canonical_category_id",
                        "branch_count": "$golden_record.branch_count",
                        "match_type": "$match_type",
                        "product_refs": "$products",
                    }
                },
                "distinct_names": {"$addToSet": "$golden_record.normalized_name"},
                "match_types": {"$addToSet": "$match_type"},
                "count": {"$sum": 1},
            }
        },
        {"$match": {"count": {"$gte": 2}}},
        {"$addFields": {"distinct_count": {"$size": "$distinct_names"}}},
        {"$match": {"distinct_count": {"$gte": 2}}},
    ]

    if has_website:
        pipeline.append({"$match": {"match_types": "website_only"}})

    pipeline.append({"$sort": {"_id.brand": 1, "_id.size": 1}})

    all_groups = list(product_matches.aggregate(pipeline))
    total = len(all_groups)
    skip = (page - 1) * per_page
    groups = all_groups[skip : skip + per_page]

    for g in groups:
        g["brand"] = g["_id"]["brand"]
        g["size"] = g["_id"]["size"]
        g["unit"] = g["_id"]["unit"] or ""
        del g["_id"]

    ref_lookup = {}
    for g in groups:
        for p in g["products"]:
            refs = p.pop("product_refs", [])
            if refs:
                ref_lookup[p["match_group_id"]] = refs[0]

    for _, coll in all_normalised:
        or_conditions = [
            {
                "product_id": ref["product_id"],
                "branch": ref["branch"],
                "source_type": ref["source_type"],
            }
            for ref in ref_lookup.values()
        ]
        if not or_conditions:
            continue
        for doc in coll.find(
            {"$or": or_conditions},
            {
                "product_id": 1, "branch": 1, "price": 1,
                "product_type": 1, "flavor": 1, "packaging": 1,
                "is_sparkling": 1, "remaining": 1, "remaining_data": 1,
            },
        ):
            for mgid, ref in ref_lookup.items():
                if (
                    doc["product_id"] == ref["product_id"]
                    and doc["branch"] == ref["branch"]
                ):
                    product_type = doc.get("product_type")
                    remaining = doc.get("remaining_data") or doc.get("remaining")
                    remaining = _clean_remaining(remaining, product_type)
                    ref["_extra"] = {
                        "price": doc.get("price"),
                        "product_type": product_type,
                        "flavor": doc.get("flavor"),
                        "packaging": doc.get("packaging"),
                        "is_sparkling": doc.get("is_sparkling"),
                        "remaining": remaining,
                    }

    extra_map = {
        mgid: ref.get("_extra", {}) for mgid, ref in ref_lookup.items()
    }
    for g in groups:
        for p in g["products"]:
            extra = extra_map.get(p["match_group_id"], {})
            p["price"] = extra.get("price")
            p["product_type"] = extra.get("product_type")
            p["flavor"] = extra.get("flavor")
            p["packaging"] = extra.get("packaging")
            p["is_sparkling"] = extra.get("is_sparkling")
            p["remaining"] = extra.get("remaining")

    return groups, total
