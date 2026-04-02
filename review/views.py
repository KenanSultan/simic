from django.shortcuts import render, redirect

from review.mongo_queries import (
    MARKETS,
    DEFAULT_MARKET,
    enrich_with_normalised_fields,
    get_golden_records,
    get_golden_record_by_id,
    get_branch_products_for_match,
    get_images_for_matches,
    get_products_with_warnings,
    get_single_branch_records,
    get_similar_groups,
    get_dashboard_stats,
    get_distinct_brands,
    get_distinct_sizes,
    get_distinct_packagings,
    get_distinct_product_types,
    get_distinct_flavors,
)
from review.categories import get_category_map, get_category_choices


def _base_context(market):
    """Common context every view needs for the sidebar market switcher."""
    return {
        "current_market": market,
        "market_name": MARKETS.get(market, {}).get("name", market),
        "markets": [(k, v["name"]) for k, v in MARKETS.items()],
    }


def market_redirect(request):
    return redirect("review:dashboard", market=DEFAULT_MARKET)


def dashboard(request, market):
    stats = get_dashboard_stats(market)
    category_map = get_category_map()
    stats["by_type"] = [
        {"type": item["_id"], "count": item["count"]}
        for item in stats["by_type"]
    ]
    stats["by_category"] = [
        {
            "category_id": item["_id"],
            "name": category_map.get(item["_id"], f"Unknown ({item['_id']})"),
            "count": item["count"],
        }
        for item in stats["by_category"]
    ]
    return render(request, "review/dashboard.html", {"stats": stats, **_base_context(market)})


def golden_list(request, market):
    filters = {}
    param_names = ["category", "brand", "match_type", "size", "packaging",
                   "product_type", "flavor", "sparkling"]
    raw = {p: request.GET.get(p, "") for p in param_names}
    search = request.GET.get("q", "").strip()

    if raw["category"]:
        filters["category_id"] = raw["category"]
    for key in ["brand", "match_type", "size", "packaging", "product_type", "flavor", "sparkling"]:
        if raw[key]:
            filters[key] = raw[key]

    page = int(request.GET.get("page", 1))
    per_page = int(request.GET.get("per_page", 25))
    if per_page not in (10, 25, 50, 100):
        per_page = 25

    docs, total, already_enriched = get_golden_records(
        market, filters=filters, search=search, page=page, per_page=per_page
    )

    total_pages = max(1, (total + per_page - 1) // per_page)
    if not already_enriched:
        enrich_with_normalised_fields(market, docs)
    category_map = get_category_map()
    for doc in docs:
        gr = doc.get("golden_record", {})
        cat_id = gr.get("canonical_category_id")
        gr["category_name"] = category_map.get(cat_id, f"Unknown ({cat_id})")

    context = {
        "records": docs,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous_page": page - 1,
        "next_page": page + 1,
        "page_range": range(max(1, page - 3), min(total_pages + 1, page + 4)),
        "per_page": per_page,
        "per_page_options": [10, 25, 50, 100],
        "showing_start": (page - 1) * per_page + 1 if total else 0,
        "showing_end": min(page * per_page, total),
        "current_filters": {**raw, "q": search},
        "categories": get_category_choices(),
        "brands": get_distinct_brands(market),
        "match_types": ["barcode", "exact", "fuzzy", "single"],
        "sizes": get_distinct_sizes(market),
        "packagings": get_distinct_packagings(market),
        "product_types": get_distinct_product_types(market),
        "flavors": get_distinct_flavors(market),
        **_base_context(market),
    }
    return render(request, "review/golden_list.html", context)


def golden_detail(request, market, match_group_id):
    doc = get_golden_record_by_id(market, match_group_id)
    if not doc:
        return render(request, "review/404.html", status=404)

    branch_products = get_branch_products_for_match(market, doc)
    branch_products.sort(key=lambda p: p.get("branch", ""))

    category_map = get_category_map()
    gr = doc.get("golden_record", {})
    cat_id = gr.get("canonical_category_id")
    gr["category_name"] = category_map.get(cat_id, f"Unknown ({cat_id})")

    prices = [p["price"] for p in branch_products if p.get("price")]

    context = {
        "match": doc,
        "golden": gr,
        "branch_products": branch_products,
        "price_min": min(prices) if prices else None,
        "price_max": max(prices) if prices else None,
        "price_count": len(prices),
        **_base_context(market),
    }
    return render(request, "review/golden_detail.html", context)


def warnings(request, market):
    warning_type = request.GET.get("type", "")
    source = request.GET.get("source", "")
    page = int(request.GET.get("page", 1))
    per_page = 50

    docs, total = get_products_with_warnings(
        market,
        warning_type=warning_type or None,
        source=source or None,
        page=page,
        per_page=per_page,
    )

    total_pages = max(1, (total + per_page - 1) // per_page)
    category_map = get_category_map()
    for doc in docs:
        cat_id = doc.get("canonical_category_id")
        doc["category_name"] = category_map.get(cat_id, f"Unknown ({cat_id})")

    context = {
        "products": docs,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous_page": page - 1,
        "next_page": page + 1,
        "page_range": range(max(1, page - 3), min(total_pages + 1, page + 4)),
        "current_type": warning_type,
        "current_source": source,
        "warning_types": ["brand_not_found", "size_not_found"],
        "sources": ["wolt", "website"],
        **_base_context(market),
    }
    return render(request, "review/warnings.html", context)


def image_gallery(request, market):
    filters = {}
    category_id = request.GET.get("category")
    brand = request.GET.get("brand")
    search = request.GET.get("q", "").strip()

    if category_id:
        filters["category_id"] = category_id
    if brand:
        filters["brand"] = brand

    page = int(request.GET.get("page", 1))
    per_page = 20

    docs, total = get_golden_records(
        market, filters=filters, search=search, page=page, per_page=per_page
    )

    total_pages = max(1, (total + per_page - 1) // per_page)

    images_map = get_images_for_matches(market, docs)

    category_map = get_category_map()
    records = []
    for doc in docs:
        gr = doc.get("golden_record", {})
        cat_id = gr.get("canonical_category_id")
        records.append(
            {
                "match_group_id": doc["match_group_id"],
                "brand": gr.get("brand", ""),
                "product_name": gr.get("product_name") or gr.get("original_name", ""),
                "size": gr.get("size"),
                "unit": gr.get("unit", ""),
                "category_name": category_map.get(cat_id, f"Unknown ({cat_id})"),
                "images": images_map.get(doc["match_group_id"], []),
            }
        )

    context = {
        "records": records,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous_page": page - 1,
        "next_page": page + 1,
        "page_range": range(max(1, page - 3), min(total_pages + 1, page + 4)),
        "current_filters": {
            "category": category_id or "",
            "brand": brand or "",
            "q": search,
        },
        "categories": get_category_choices(),
        "brands": get_distinct_brands(market),
        **_base_context(market),
    }
    return render(request, "review/image_gallery.html", context)


def singles(request, market):
    page = int(request.GET.get("page", 1))
    per_page = 25

    docs, total = get_single_branch_records(market, page=page, per_page=per_page)

    total_pages = max(1, (total + per_page - 1) // per_page)
    category_map = get_category_map()
    for doc in docs:
        gr = doc.get("golden_record", {})
        cat_id = gr.get("canonical_category_id")
        gr["category_name"] = category_map.get(cat_id, f"Unknown ({cat_id})")

    context = {
        "records": docs,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous_page": page - 1,
        "next_page": page + 1,
        "page_range": range(max(1, page - 3), min(total_pages + 1, page + 4)),
        **_base_context(market),
    }
    return render(request, "review/singles.html", context)


def similar(request, market):
    brand = request.GET.get("brand", "")
    has_website = request.GET.get("has_website") == "1"
    page = int(request.GET.get("page", 1))
    per_page = 20

    groups, total = get_similar_groups(
        market, brand=brand or None, has_website=has_website, page=page, per_page=per_page
    )

    total_pages = max(1, (total + per_page - 1) // per_page)
    category_map = get_category_map()
    for group in groups:
        for p in group.get("products", []):
            cat_id = p.get("canonical_category_id")
            p["category_name"] = category_map.get(cat_id, f"Unknown ({cat_id})")

    context = {
        "groups": groups,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "has_previous": page > 1,
        "has_next": page < total_pages,
        "previous_page": page - 1,
        "next_page": page + 1,
        "page_range": range(max(1, page - 3), min(total_pages + 1, page + 4)),
        "current_brand": brand,
        "has_website": has_website,
        "brands": get_distinct_brands(market),
        **_base_context(market),
    }
    return render(request, "review/similar.html", context)
