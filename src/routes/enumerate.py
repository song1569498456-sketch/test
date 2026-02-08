from __future__ import annotations

from typing import Iterable


def _all_whitelisted(tokens: dict, symbols: Iterable[str]) -> bool:
    return all(sym in tokens for sym in symbols)


def enumerate_loops2(config: dict) -> list[tuple[str, str]]:
    token_map = config["tokens"]
    loops = []
    for pair in config["route_sets"]["loops2"]:
        if len(pair) != 2:
            continue
        a, b = pair
        if _all_whitelisted(token_map, [a, b]):
            loops.append((a, b))
    return loops


def enumerate_triangles3(config: dict) -> list[tuple[str, str, str]]:
    rules = config["path_enum_rules"]
    token_map = config["tokens"]
    seen: set[tuple[str, ...]] = set()
    out: list[tuple[str, str, str]] = []
    per_base_counter: dict[str, int] = {}

    for tri in config["route_sets"]["triangles3"]:
        if len(tri) != 3:
            continue
        a, b, c = tri
        if rules.get("triangle_only_if_all_tokens_whitelisted", True) and not _all_whitelisted(token_map, [a, b, c]):
            continue

        base = a
        if per_base_counter.get(base, 0) >= rules.get("max_triangles_per_base_token", 50):
            continue

        key = tuple(sorted([a, b, c])) if rules.get("dedup_by_sorted_symbols", True) else (a, b, c)
        if key in seen:
            continue

        seen.add(key)
        per_base_counter[base] = per_base_counter.get(base, 0) + 1
        out.append((a, b, c))

    return out
