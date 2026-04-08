from collections import defaultdict
from difflib import SequenceMatcher


def _similarity(a, b):
    """Token-based similarity: Jaccard on word tokens + SequenceMatcher."""
    if not a or not b:
        return 0.0
    tokens_a = set(a.split())
    tokens_b = set(b.split())
    if not tokens_a or not tokens_b:
        return 0.0
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
    seq = SequenceMatcher(None, a, b).ratio()
    return (jaccard + seq) / 2


def _barcodes_conflict(p1, p2):
    """Return True if both products have barcodes and they differ."""
    b1 = p1.get("barcode")
    b2 = p2.get("barcode")
    return b1 and b2 and b1 != b2


def match_by_fuzzy(products, threshold=0.85):
    """Fuzzy match on normalized name, requiring exact size+unit match.

    Args:
        products: List of normalized product dicts (unmatched from prior tiers).
        threshold: Minimum similarity score to consider a match.

    Returns:
        (matched_groups, unmatched, group_scores): matched groups are flagged
            for review. group_scores is a list of floats — the minimum pairwise
            similarity within each matched group.
    """
    if not products:
        return [], [], []

    # Group by (size, unit, packaging, flavor) first — fuzzy only within same structural fields
    by_size = defaultdict(list)
    for p in products:
        key = (p.get("size"), p.get("unit"), p.get("packaging"), p.get("flavor") or "")
        by_size[key].append(p)

    matched_groups = []
    group_scores = []
    unmatched = []

    for size_key, candidates in by_size.items():
        used = set()
        groups = []
        scores = []

        for i, p1 in enumerate(candidates):
            if i in used:
                continue
            group = [p1]
            group_min_score = 1.0
            used.add(i)

            name1 = p1.get("normalized_name", "")
            for j in range(i + 1, len(candidates)):
                if j in used:
                    continue
                if _barcodes_conflict(p1, candidates[j]):
                    continue
                name2 = candidates[j].get("normalized_name", "")
                score = _similarity(name1, name2)
                if score >= threshold:
                    group.append(candidates[j])
                    group_min_score = min(group_min_score, score)
                    used.add(j)

            if len(group) >= 2:
                groups.append(group)
                scores.append(round(group_min_score, 3))
            else:
                unmatched.extend(group)

        matched_groups.extend(groups)
        group_scores.extend(scores)

    return matched_groups, unmatched, group_scores
