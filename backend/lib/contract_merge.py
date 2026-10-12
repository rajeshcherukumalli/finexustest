"""Merge a freshly scraped contract with the previous run and report the diff.

Re-scrapes must be monotonic: anything the previous contract knew about is
either re-confirmed, or kept with ``stale: true`` — never silently dropped.
The diff report makes "something went missing this run" visible at scrape
time instead of surfacing later as a broken generated test.
"""

from __future__ import annotations

from typing import Any


def element_key(element: dict[str, Any]) -> str:
    """Identity of an element across runs: its most stable selector."""
    selectors = element.get("selectors") or {}
    return (
        selectors.get("playwright")
        or selectors.get("css")
        or selectors.get("xpath")
        or element.get("element_id")
        or ""
    )


def _route_entry(page: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "page_id": page.get("page_id"),
        "path": page.get("path"),
        "url": page.get("url"),
        "title": page.get("title"),
        "page_type": page.get("page_type"),
        "test_priority": page.get("test_priority"),
        "is_protected": page.get("is_protected"),
    }
    if page.get("stale"):
        entry["stale"] = True
    return entry


def _merge_page_elements(
    previous_page: dict[str, Any],
    current_page: dict[str, Any],
    previous_scraped_at: str,
) -> tuple[list[dict], list[str], list[str]]:
    """Return (merged_elements, added_labels, stale_labels) for one page."""
    current_elements = current_page.get("elements", [])
    previous_elements = previous_page.get("elements", [])

    current_keys = {element_key(e) for e in current_elements}
    previous_keys = {element_key(e) for e in previous_elements}
    current_ids = {e.get("element_id") for e in current_elements}

    added = [
        (e.get("label") or e.get("element_id") or "?")
        for e in current_elements
        if element_key(e) not in previous_keys
    ]

    stale_elements: list[dict] = []
    stale_labels: list[str] = []
    for element in previous_elements:
        if element_key(element) in current_keys:
            continue
        kept = dict(element)
        if not kept.get("stale"):
            kept["stale"] = True
            kept["last_seen"] = element.get("last_seen") or previous_scraped_at
        if kept.get("element_id") in current_ids:
            kept["element_id"] = f"{kept['element_id']}_stale"
        stale_elements.append(kept)
        stale_labels.append(kept.get("label") or kept.get("element_id") or "?")

    return current_elements + stale_elements, added, stale_labels


def merge_contracts(
    previous: dict[str, Any],
    current: dict[str, Any],
    mark_missing_pages_stale: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Union ``previous`` into ``current``; return (merged_contract, diff).

    Set ``mark_missing_pages_stale=False`` for partial/focused scrapes (e.g. an
    authenticated pass over one portal) — pages that weren't visited this run
    are then carried over untouched instead of being flagged stale.
    """
    previous_scraped_at = (previous.get("extraction_metadata") or {}).get("scraped_at", "")
    current_scraped_at = (current.get("extraction_metadata") or {}).get("scraped_at", "")

    previous_pages = {p.get("page_id"): p for p in previous.get("pages", [])}
    current_pages = {p.get("page_id"): p for p in current.get("pages", [])}

    diff: dict[str, Any] = {
        "previous_scraped_at": previous_scraped_at,
        "current_scraped_at": current_scraped_at,
        "pages_added": [],
        "pages_stale": [],
        "pages_revisited": [],
        "elements_added": {},
        "elements_stale": {},
    }

    merged_pages: list[dict] = []
    for page_id, current_page in current_pages.items():
        previous_page = previous_pages.get(page_id)
        if previous_page is None:
            diff["pages_added"].append(page_id)
            merged_pages.append(current_page)
            continue

        diff["pages_revisited"].append(page_id)
        merged_page = dict(current_page)
        merged_page.pop("stale", None)
        merged_page.pop("last_seen", None)
        elements, added, stale = _merge_page_elements(
            previous_page, current_page, previous_scraped_at
        )
        merged_page["elements"] = elements
        if added:
            diff["elements_added"][page_id] = added
        if stale:
            diff["elements_stale"][page_id] = stale
        merged_pages.append(merged_page)

    for page_id, previous_page in previous_pages.items():
        if page_id in current_pages:
            continue
        if not mark_missing_pages_stale:
            merged_pages.append(previous_page)
            continue
        kept = dict(previous_page)
        if not kept.get("stale"):
            kept["stale"] = True
            kept["last_seen"] = previous_page.get("last_seen") or previous_scraped_at
        diff["pages_stale"].append(page_id)
        merged_pages.append(kept)

    merged = dict(current)
    merged["pages"] = merged_pages
    merged["route_index"] = [_route_entry(p) for p in merged_pages]
    if not merged.get("home_navigation") and previous.get("home_navigation"):
        merged["home_navigation"] = previous["home_navigation"]
    return merged, diff


def render_diff_markdown(diff: dict[str, Any]) -> str:
    lines = [
        "# Contract scrape diff",
        "",
        f"- Previous scrape: {diff.get('previous_scraped_at') or 'n/a'}",
        f"- Current scrape:  {diff.get('current_scraped_at') or 'n/a'}",
        f"- Pages revisited: {len(diff.get('pages_revisited', []))}",
        "",
    ]

    def section(title: str, items: list[str]) -> None:
        lines.append(f"## {title} ({len(items)})")
        lines.append("")
        for item in items or ["_none_"]:
            lines.append(f"- {item}")
        lines.append("")

    section("Pages added", diff.get("pages_added", []))
    section(
        "Pages not re-found (kept as stale)",
        diff.get("pages_stale", []),
    )

    lines.append("## Elements changed per page")
    lines.append("")
    changed_pages = sorted(
        set(diff.get("elements_added", {})) | set(diff.get("elements_stale", {}))
    )
    if not changed_pages:
        lines.append("_no element-level changes_")
    for page_id in changed_pages:
        added = diff.get("elements_added", {}).get(page_id, [])
        stale = diff.get("elements_stale", {}).get(page_id, [])
        lines.append(f"### {page_id}")
        for label in added:
            lines.append(f"- + {label}")
        for label in stale:
            lines.append(f"- − {label} (stale)")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
