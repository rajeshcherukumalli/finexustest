"""Deterministic page resolution for Playwright codegen from slim contract + testcase YAML."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from lib.contract import Contract, page_id_to_pom_name
from lib.contract_validate import find_element

_PAGE_KEY_FIELDS = (
    "page_id",
    "path",
    "url",
    "title",
    "description",
    "page_type",
    "test_priority",
    "is_protected",
)


def pom_name_to_page_id(pom_name: str) -> str:
    if not pom_name:
        return ""
    stem = pom_name[:-4] if pom_name.endswith("Page") else pom_name
    return re.sub(r"(?<!^)(?=[A-Z])", "_", stem).lower()


def _normalize_path(path: str | None) -> str:
    if not path:
        return "/"
    cleaned = path.split("?")[0].split("#")[0]
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned.rstrip("/") or "/"


def _slim_pages_by_id(slim_slice: dict) -> dict[str, dict]:
    return {
        str(page["page_id"]): page
        for page in slim_slice.get("pages", [])
        if page.get("page_id")
    }


def _canonical_page_id(contract: Contract | None, page_id: str) -> str | None:
    if not page_id:
        return None
    if contract:
        page = contract.get_page(page_id) or contract.get_page(page_id.replace("_", "-"))
        if page:
            return str(page["page_id"])
    return page_id


def _fuzzy_match_slim_page_id(candidate: str, slim_ids: set[str]) -> str | None:
    if candidate in slim_ids:
        return candidate
    norm = candidate.replace("_", "").replace("-", "")
    for pid in slim_ids:
        if pid.replace("_", "").replace("-", "") == norm:
            return pid
    return None


def _route_to_page_id(
    slim_slice: dict,
    contract: Contract | None,
    route: str,
    slim_ids: set[str],
) -> str | None:
    norm = _normalize_path(route)
    for entry in slim_slice.get("route_index", []):
        if _normalize_path(entry.get("path")) == norm:
            pid = _canonical_page_id(contract, str(entry.get("page_id", "")))
            if pid and pid in slim_ids:
                return pid
    for page in slim_slice.get("pages", []):
        if _normalize_path(page.get("path")) == norm:
            pid = str(page["page_id"])
            if pid in slim_ids:
                return pid
    if contract:
        for entry in contract.route_index:
            if _normalize_path(entry.get("path")) == norm:
                pid = _canonical_page_id(contract, str(entry.get("page_id", "")))
                if pid and pid in slim_ids:
                    return pid
    return None


def _find_element_in_slim(
    slim_slice: dict,
    element_id: str,
    page_id: str | None = None,
) -> dict | None:
    pages = slim_slice.get("pages", [])
    if page_id:
        page = _slim_pages_by_id(slim_slice).get(page_id)
        pages = [page] if page else []
    for page in pages or slim_slice.get("pages", []):
        for element in page.get("elements", []):
            if element.get("element_id") == element_id:
                return element
    return None


def collect_flow_element_ids(flow: dict) -> set[str]:
    element_ids: set[str] = set()
    for case in flow.get("cases", []):
        for ref in case.get("element_refs", []):
            if isinstance(ref, dict) and ref.get("element_id"):
                element_ids.add(str(ref["element_id"]))
        for link in case.get("nav_links", []):
            if isinstance(link, dict) and link.get("element_id"):
                element_ids.add(str(link["element_id"]))
    return element_ids


def resolve_flow_page_ids(
    flow: dict,
    slim_slice: dict,
    plan_meta: dict[str, Any],
    contract: Contract | None = None,
) -> tuple[list[str], list[str]]:
    """Return ordered page_ids from slim slice referenced by plan + testcase."""
    slim_by_id = _slim_pages_by_id(slim_slice)
    slim_ids = set(slim_by_id)
    warnings: list[str] = []
    ordered: list[str] = []
    seen: set[str] = set()

    def add(page_id: str | None) -> bool:
        pid = _canonical_page_id(contract, str(page_id or ""))
        if not pid:
            return False
        matched = _fuzzy_match_slim_page_id(pid, slim_ids)
        if not matched:
            return False
        if matched not in seen:
            seen.add(matched)
            ordered.append(matched)
            return True
        return False

    page_sequence = plan_meta.get("page_sequence", "")
    if page_sequence:
        for raw in str(page_sequence).split(","):
            add(raw.strip())

    for pom in flow.get("ui_pages", []):
        pom_name = str(pom)
        pid = pom_name_to_page_id(pom_name)
        if add(pid):
            continue
        fuzzy = _fuzzy_match_slim_page_id(pid, slim_ids)
        if fuzzy and add(fuzzy):
            continue
        if contract:
            slug = pom_name.replace("Page", "").lower().replace("_", "-")
            page = contract.get_page(slug) or contract.get_page(pid.replace("_", "-"))
            if page and add(str(page["page_id"])):
                continue
        warnings.append(f"ui_pages entry {pom_name!r} did not map to a slim-slice page")

    for case in flow.get("cases", []):
        for ref in case.get("element_refs", []):
            if isinstance(ref, dict) and ref.get("page_id"):
                add(str(ref["page_id"]))

    for case in flow.get("cases", []):
        for link in case.get("nav_links", []):
            if not isinstance(link, dict):
                continue
            if link.get("element_id"):
                add("home")
            route = str(link.get("route") or "")
            if not route and link.get("expected_url"):
                route = str(link["expected_url"])
            if route:
                path = urlparse(route).path if "://" in route else route
                fragment = urlparse(route).fragment if "://" in route else ""
                if fragment:
                    path = f"/#{fragment}"
                pid = _route_to_page_id(slim_slice, contract, path, slim_ids)
                if pid:
                    add(pid)

    for case in flow.get("cases", []):
        for ref in case.get("element_refs", []):
            if not isinstance(ref, dict):
                continue
            eid = str(ref.get("element_id", ""))
            if not eid:
                continue
            page_id = str(ref.get("page_id", "")) or None
            element = _find_element_in_slim(slim_slice, eid, page_id)
            if not element and contract:
                element = find_element(contract, eid, page_id)
            if not element:
                continue
            target_path = element.get("target_path")
            if ref.get("action", "click") == "click" and target_path:
                dest = _route_to_page_id(slim_slice, contract, str(target_path), slim_ids)
                if dest:
                    add(dest)

    if not ordered and "home" in slim_ids:
        ordered.append("home")

    return ordered, warnings


def _filter_page_elements(page: dict, element_ids: set[str]) -> dict:
    elements = [
        element
        for element in page.get("elements", [])
        if element.get("element_id") in element_ids
    ]
    forms = []
    for form in page.get("forms", []):
        fields = [
            field
            for field in form.get("fields", [])
            if field.get("field_id") in element_ids
        ]
        if fields:
            forms.append({**form, "fields": fields})
    return {
        key: page[key]
        for key in _PAGE_KEY_FIELDS
        if key in page
    } | {
        "elements": elements,
        "forms": forms,
    }


def build_execution_slice(
    contract: Contract,
    slim_slice: dict,
    flow: dict,
    plan_meta: dict[str, Any],
) -> dict[str, Any]:
    """Build Playwright execution context: slim-slice pages + YAML-referenced elements only."""
    page_ids, warnings = resolve_flow_page_ids(flow, slim_slice, plan_meta, contract)
    element_ids = collect_flow_element_ids(flow)
    slim_by_id = _slim_pages_by_id(slim_slice)

    pages = []
    for page_id in page_ids:
        page = slim_by_id.get(page_id)
        if not page:
            continue
        pages.append(_filter_page_elements(page, element_ids))

    result: dict[str, Any] = {
        "contract_version": slim_slice.get("contract_version", contract.version),
        "application": slim_slice.get("application", contract.raw.get("application", {})),
        "module": slim_slice.get("module", flow.get("module")),
        "page_sequence": page_ids,
        "pages": pages,
    }
    if warnings:
        result["warnings"] = warnings

    route_ids = {page["page_id"] for page in pages}
    if slim_slice.get("route_index"):
        result["route_index"] = [
            entry
            for entry in slim_slice["route_index"]
            if entry.get("page_id") in route_ids
        ]

    has_nav_links = any(case.get("nav_links") for case in flow.get("cases", []))
    if has_nav_links and slim_slice.get("home_navigation"):
        nav_ids = element_ids
        filtered_nav = [
            entry
            for entry in slim_slice["home_navigation"]
            if entry.get("element_id") in nav_ids
        ]
        result["home_navigation"] = filtered_nav or list(slim_slice["home_navigation"])

    return result


def slice_execution_for_case(execution_slice: dict, case: dict) -> dict:
    """Narrow execution slice to one testcase case."""
    element_ids: set[str] = set()
    for ref in case.get("element_refs", []):
        if isinstance(ref, dict) and ref.get("element_id"):
            element_ids.add(str(ref["element_id"]))
    for link in case.get("nav_links", []):
        if isinstance(link, dict) and link.get("element_id"):
            element_ids.add(str(link["element_id"]))

    pages = []
    for page in execution_slice.get("pages", []):
        filtered = _filter_page_elements(page, element_ids)
        if filtered.get("elements") or filtered.get("forms"):
            pages.append(filtered)

    result = dict(execution_slice)
    result["pages"] = pages
    if case.get("nav_links") and execution_slice.get("home_navigation"):
        result["home_navigation"] = execution_slice["home_navigation"]
    return result


def canonical_ui_pages(page_ids: list[str]) -> list[str]:
    return [page_id_to_pom_name(page_id) for page_id in page_ids]
