"""Validate and rewrite testcase flows against the UI contract (source of truth)."""

from __future__ import annotations

import re
from typing import Any

from lib.contract import Contract

NAV_INTENT_RE = re.compile(r"\b(nav|menu|link|sitemap|route|header|footer)\b", re.I)


def _expected_url_for_nav_entry(base_url: str, entry: dict) -> str:
    target = entry.get("target_path") or "/"
    base = base_url.rstrip("/")
    if target.startswith("/#"):
        return f"{base}{target[1:]}"
    if target == "/":
        return f"{base}/"
    return f"{base}{target}"


def _find_element_on_page(page: dict | None, element_id: str) -> dict | None:
    if not page:
        return None
    for el in page.get("elements", []):
        if el.get("element_id") == element_id:
            return el
    return None


def find_element(contract: Contract, element_id: str, page_id: str | None = None) -> dict | None:
    if page_id:
        el = _find_element_on_page(contract.get_page(page_id), element_id)
        if el:
            return el
    home = contract.get_page("home")
    el = _find_element_on_page(home, element_id)
    if el:
        return el
    for page in contract.pages:
        el = _find_element_on_page(page, element_id)
        if el:
            return el
    return None


def enforce_plan_module(flow: dict[str, Any], plan_meta: dict[str, Any]) -> dict[str, Any]:
    module = plan_meta.get("module")
    if module:
        flow["module"] = module
    return flow


def _prefer_home_header_element(
    ref: dict[str, Any],
    contract: Contract,
    element: dict,
    eid: str,
    page_id: str,
) -> tuple[dict, str, str]:
    """When the same label exists in the home header, prefer that for click steps."""
    if ref.get("action", "click") != "click":
        return element, eid, page_id
    home = contract.get_page("home")
    if not home:
        return element, eid, page_id
    on_home = _find_element_on_page(home, eid)
    if on_home and on_home.get("region") == "header":
        return on_home, eid, "home"
    label = (element.get("label") or "").strip()
    if not label:
        return element, eid, page_id
    for el in home.get("elements", []):
        if el.get("region") == "header" and (el.get("label") or "").strip() == label:
            return el, str(el["element_id"]), "home"
    return element, eid, page_id


def validate_element_ref(ref: dict[str, Any], contract: Contract) -> tuple[dict | None, str | None]:
    if not isinstance(ref, dict):
        return None, "invalid element_ref"
    eid = ref.get("element_id")
    if not eid:
        return None, "missing element_id"
    page_id = ref.get("page_id") or "home"
    element = find_element(contract, str(eid), str(page_id))
    if not element:
        return None, f"unknown element_id {eid!r}"
    element, eid, page_id = _prefer_home_header_element(ref, contract, element, str(eid), str(page_id))
    home = contract.get_page("home")
    resolved_page = "home" if _find_element_on_page(home, eid) else page_id
    fixed = {
        "element_id": eid,
        "action": ref.get("action", "click"),
        "page_id": resolved_page,
    }
    return fixed, None


def nav_links_from_home_navigation(contract: Contract) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for entry in contract.home_navigation:
        element_id = entry.get("element_id")
        if not element_id:
            continue
        target = entry.get("target_path") or "/"
        links.append({
            "element_id": element_id,
            "action": "click",
            "label": entry.get("label", ""),
            "route": target,
            "expected_url": _expected_url_for_nav_entry(contract.base_url, entry),
            "assert": entry.get("assert"),
            "raw_href": entry.get("raw_href"),
        })
    return links


def _enrich_nav_link(
    link: dict[str, Any],
    contract: Contract,
    home_nav_by_id: dict[str, dict],
) -> dict[str, Any] | None:
    eid = str(link.get("element_id") or "")
    entry = home_nav_by_id.get(eid) if eid else None
    if not entry:
        label = (link.get("label") or "").strip().lower()
        for nav in contract.home_navigation:
            if (nav.get("label") or "").strip().lower() == label:
                entry = nav
                eid = nav.get("element_id", "")
                break
    if not entry or not eid:
        return None
    target = entry.get("target_path") or link.get("route") or "/"
    return {
        "element_id": eid,
        "action": "click",
        "label": entry.get("label") or link.get("label", ""),
        "route": target,
        "expected_url": _expected_url_for_nav_entry(contract.base_url, entry),
        "assert": entry.get("assert"),
        "raw_href": entry.get("raw_href"),
    }


def case_has_nav_intent(
    case: dict[str, Any],
    flow: dict[str, Any],
    plan_meta: dict[str, Any],
) -> bool:
    """True only when the plan/flow is a navigation test — not when the LLM copies home_navigation into a content case."""
    module = flow.get("module") or plan_meta.get("module") or ""
    if module in ("content", "auth"):
        return False
    if module == "navigation":
        return True
    intent = plan_meta.get("user_intent", "")
    return bool(NAV_INTENT_RE.search(intent))


def rewrite_nav_case(
    case: dict[str, Any],
    contract: Contract,
    *,
    full_replace: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    case = dict(case)
    home_nav = contract.home_navigation
    if not home_nav:
        warnings.append(f"{case.get('id')}: no home_navigation in contract")
        return case, warnings

    by_id = {e["element_id"]: e for e in home_nav if e.get("element_id")}
    raw_links = case.get("nav_links") or []

    if full_replace or not raw_links:
        links = nav_links_from_home_navigation(contract)
        case["nav_links"] = links
        case["element_refs"] = [
            {"element_id": n["element_id"], "action": "click", "page_id": "home"}
            for n in links
        ]
        return case, warnings

    enriched: list[dict[str, Any]] = []
    valid_refs: list[dict[str, Any]] = []
    for link in raw_links:
        if not isinstance(link, dict):
            continue
        item = _enrich_nav_link(link, contract, by_id)
        if item:
            enriched.append(item)
            valid_refs.append({
                "element_id": item["element_id"],
                "action": "click",
                "page_id": "home",
            })
        else:
            warnings.append(
                f"{case.get('id')}: dropped nav link {link.get('element_id') or link.get('label')!r}"
            )

    if enriched:
        case["nav_links"] = enriched
        case["element_refs"] = valid_refs
    else:
        links = nav_links_from_home_navigation(contract)
        case["nav_links"] = links
        case["element_refs"] = [
            {"element_id": n["element_id"], "action": "click", "page_id": "home"}
            for n in links
        ]
        warnings.append(f"{case.get('id')}: replaced invalid nav_links with home_navigation")

    return case, warnings


def validate_flow(
    flow: dict[str, Any],
    contract: Contract,
    plan_meta: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    flow = enforce_plan_module(dict(flow), plan_meta)
    flow_id = flow.get("flow_id", "FLOW-01")
    cases_out: list[dict[str, Any]] = []

    for i, raw_case in enumerate(flow.get("cases", [])):
        case = dict(raw_case)
        if not case.get("id"):
            case["id"] = f"{flow_id}-H{i + 1}"

        if case_has_nav_intent(case, flow, plan_meta) and contract.home_navigation:
            multi = len(flow.get("cases", [])) > 1 and len(case.get("nav_links") or []) <= 1
            case, w = rewrite_nav_case(case, contract, full_replace=not multi)
            warnings.extend(w)
        else:
            if case.get("nav_links"):
                case = dict(case)
                case.pop("nav_links", None)
                warnings.append(
                    f"{case.get('id')}: removed nav_links from non-navigation flow (module={flow.get('module')!r})"
                )
            valid_refs: list[dict[str, Any]] = []
            for ref in case.get("element_refs", []):
                fixed, err = validate_element_ref(ref, contract)
                if fixed:
                    action = ref.get("action", "click") if isinstance(ref, dict) else "click"
                    fixed["action"] = action
                    if isinstance(ref, dict) and ref.get("value") is not None:
                        fixed["value"] = ref["value"]
                    valid_refs.append(fixed)
                elif err:
                    warnings.append(f"{case.get('id')}: {err}")
            if flow.get("module") == "content" and contract.home_navigation:
                home_nav_ids = {
                    e["element_id"] for e in contract.home_navigation if e.get("element_id")
                }
                non_nav = [r for r in valid_refs if r["element_id"] not in home_nav_ids]
                if len(non_nav) < len(valid_refs):
                    dropped = len(valid_refs) - len(non_nav)
                    warnings.append(
                        f"{case.get('id')}: dropped {dropped} "
                        "home_navigation element_refs from content flow"
                    )
                    valid_refs = non_nav
                if not valid_refs:
                    warnings.append(
                        f"{case.get('id')}: no content element_refs after validation — "
                        "regenerate testcase; LLM must reference plan steps, not header nav"
                    )
            case["element_refs"] = valid_refs

        cases_out.append(case)

    flow["cases"] = cases_out
    return flow, warnings
