"""
Website Scraper with LLM Intelligence
--------------------------------------
Crawls a website, extracts all pages and clickable elements with XPaths,
and uses Claude Code CLI to intelligently decide what pages are worth crawling.
Output is a JSON file consumable by the test generator.
"""

import os
import re
import json
import time
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from typing import Optional

CONTRACT_VERSION = "1.2.0"

from bs4 import BeautifulSoup
from lxml import etree
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Page, Browser

from lib.contract_merge import merge_contracts, render_diff_markdown
from lib.crawl_rules import looks_like_login_redirect, select_crawl_urls, url_template, is_http_error_status, looks_like_error_page
from lib.llm import parse_json_response
from lib.playwright_run import resolve_scraper_headless
from lib.scraper_auth import authenticate_at_url, authenticate_page, is_login_gate, is_login_path, probe_authentication_at_url
from lib.scraper_credentials import (
    available_fillable_keys,
    button_probe_limit,
    default_login_url,
    resolve_auth_url,
    has_auth_credentials,
    load_scraper_credentials,
    merge_legacy_cli_credentials,
    navigation_timeout_ms,
)
from lib.scraper_interaction import interaction_pass
from lib.scraper_navigation import classify_link, discover_button_routes, extract_live_navigation

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

STATIC_ASSET_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg",
    ".zip", ".css", ".js", ".woff", ".woff2", ".ico", ".mp4",
    ".pptx", ".ppt", ".xlsx", ".xls", ".docx", ".doc", ".csv",
)

COMMON_STATIC_PATHS = (
    "/sitemap",
    "/privacypolicy",
    "/screenreaderaccess",
    "/accessibility-statement",
    "/login",
    "/home",
    "/about",
    "/contact",
    "/help",
    "/faq",
    "/faqs",
)
# ─────────────────────────────────────────────
# Data Models
# ─────────────────────────────────────────────

@dataclass
class Link:
    href: str                       # resolved absolute URL
    raw_href: str                   # value from DOM before resolution
    text: str
    tag: str                        # a | button | area
    category: str                   # internal_path | internal_hash | external | navigation_button | spa_route | mailto | tel
    crawlable: bool                 # safe to enqueue for multi-page crawl
    opens_new_tab: bool = False
    aria_label: Optional[str] = None
    region: str = "unknown"         # header | footer | nav | content | unknown

@dataclass
class Clickable:
    tag: str                        # button, a, input, select, etc.
    type: str                       # link | button | input | select | form
    text: str                       # visible label
    xpath: str                      # absolute XPath for Playwright
    href: Optional[str] = None      # for links
    name: Optional[str] = None      # for inputs/forms
    placeholder: Optional[str] = None
    aria_label: Optional[str] = None
    is_auth_required: bool = False  # flagged by LLM


@dataclass
class ScrapedPage:
    url: str
    title: str
    is_protected: bool              # requires login
    depth: int
    clickables: list[Clickable] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    elements: list[dict] = field(default_factory=list)
    forms: list[dict] = field(default_factory=list)
    page_type: str = "unknown"      # LLM-assigned: login | dashboard | list | detail | form | nav
    test_priority: str = "medium"   # LLM-assigned: high | medium | low
    llm_notes: str = ""             # LLM summary of what this page does
    auth_context: str = "anonymous"  # anonymous | authenticated
    scrape_status: str = "ok"       # ok | login_redirect | load_failed | http_error | error_page
    ready_state: str = "stable"       # stable | timeout | n/a


@dataclass
class SiteMap:
    base_url: str
    total_pages: int
    pages: list[ScrapedPage] = field(default_factory=list)
    auth_urls: list[str] = field(default_factory=list)     # protected pages
    public_urls: list[str] = field(default_factory=list)   # public pages
    all_links: list[Link] = field(default_factory=list)    # internal crawl dedup only
    wait_until: str = "load"


# ─────────────────────────────────────────────
# Link helpers
# ─────────────────────────────────────────────

def _is_static_asset(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(path.endswith(ext) for ext in STATIC_ASSET_EXTENSIONS)


def _classify_link(raw_href: str, resolved_href: str, base_domain: str) -> tuple[str, bool]:
    """Return (category, crawlable)."""
    return classify_link(raw_href, resolved_href, base_domain, _is_static_asset)


def _link_from_dict(item: dict) -> Link:
    return Link(
        href=item.get("href") or "",
        raw_href=item.get("raw_href") or "",
        text=item.get("text") or "",
        tag=item.get("tag") or "a",
        category=item.get("category") or "navigation_button",
        crawlable=bool(item.get("crawlable")),
        opens_new_tab=bool(item.get("opens_new_tab")),
        aria_label=item.get("aria_label"),
        region=item.get("region") or "unknown",
    )


def _raw_items_to_links(raw_items: list[dict], page_url: str, base_domain: str) -> list[Link]:
    links: list[Link] = []
    for item in raw_items:
        raw_href = (item.get("raw_href") or "").strip()
        resolved = (item.get("resolved_href") or "").strip()
        if raw_href and not resolved:
            resolved = urljoin(page_url, raw_href)
        if not raw_href and not resolved:
            category = "navigation_button"
            crawlable = False
        else:
            category, crawlable = _classify_link(raw_href, resolved, base_domain)

        links.append(
            Link(
                href=resolved or raw_href,
                raw_href=raw_href,
                text=item.get("text", ""),
                tag=item.get("tag", "a"),
                category=category,
                crawlable=crawlable,
                opens_new_tab=bool(item.get("opens_new_tab")),
                aria_label=item.get("aria_label"),
                region=item.get("region") or "unknown",
            )
        )
    return links


def extract_links_from_page(page: Page, page_url: str, base_domain: str) -> list[Link]:
    """Extract anchors and navigation buttons from the live DOM."""
    raw_items, _probe_candidates = extract_live_navigation(page)
    if not raw_items:
        log.warning("Live DOM link extraction returned no items for %s", page_url)
    return _raw_items_to_links(raw_items, page_url, base_domain)


def merge_unique_links(existing: list[Link], new_links: list[Link]) -> list[Link]:
    seen: set[str] = set()
    merged: list[Link] = []
    for link in existing + new_links:
        key = f"{link.category}|{link.href}|{link.raw_href}|{link.text}|{link.tag}"
        if key in seen:
            continue
        seen.add(key)
        merged.append(link)
    return merged


# ─────────────────────────────────────────────
# Contract builders
# ─────────────────────────────────────────────

NOISE_LABELS = {
    "previous", "next", "left", "right", "play or pause", "search",
}


def _slugify(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")
    return slug[:48] or fallback


def _clean_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    return parsed._replace(query="", fragment="").geturl().rstrip("/")


def _normalize_href_for_storage(resolved: str, raw: str) -> str:
    """Store href with fragment preserved (unlike _clean_url used for crawl dedup)."""
    if not resolved and not raw:
        return ""
    primary = resolved or raw
    parsed = urlparse(primary)
    frag = parsed.fragment
    raw = (raw or "").strip()
    if not frag and raw:
        if raw.startswith("/#"):
            frag = raw[2:].split("?")[0]
        elif raw.startswith("#"):
            frag = raw[1:].split("?")[0]
    if frag:
        return parsed._replace(query="", fragment=frag).geturl()
    return parsed._replace(query="", fragment="").geturl().rstrip("/")


def _fragment_from_href(href: str, raw_href: str) -> Optional[str]:
    parsed = urlparse(href or raw_href)
    if parsed.fragment:
        return parsed.fragment
    raw = (raw_href or "").strip()
    if raw.startswith("/#"):
        return raw[2:].split("?")[0] or None
    if raw.startswith("#"):
        return raw[1:].split("?")[0] or None
    return None


def _page_path(url: str, base_url: str) -> str:
    base = _clean_url(base_url)
    full = _clean_url(url)
    if full == base:
        return "/"
    if full.startswith(base + "/"):
        return full[len(base):]
    parsed = urlparse(full)
    return parsed.path or "/"


def _page_id_from_path(path: str) -> str:
    cleaned = path.strip("/")
    return _slugify(cleaned.replace("/", "_"), "home")


def _element_label(tag: str, text: str, aria_label: Optional[str], name: Optional[str], placeholder: Optional[str]) -> str:
    return (text or aria_label or name or placeholder or "").strip()


def _escape_js_string(value: str) -> str:
    value = value.replace("\\", "\\\\").replace("'", "\\'")
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n")
    return value


def _build_playwright_selector(
    tag: str,
    role: str,
    label: str,
    aria_label: Optional[str],
    name: Optional[str],
    element_id: Optional[str],
    data_testid: Optional[str],
    raw_href: Optional[str] = None,
) -> str:
    if data_testid:
        return f"page.getByTestId('{_escape_js_string(data_testid)}')"
    if element_id:
        return f"page.locator('#{_escape_js_string(element_id)}')"
    if raw_href and role == "link" and tag == "a":
        return f"page.locator('a[href=\"{_escape_js_string(raw_href)}\"]')"
    if name and tag in ("input", "select", "textarea"):
        return f"page.locator('[name=\"{_escape_js_string(name)}\"]')"
    visible_label = aria_label or label
    if visible_label:
        playwright_role = {
            "link": "link",
            "button": "button",
            "input": "textbox",
            "select": "combobox",
            "textarea": "textbox",
        }.get(role, "button")
        return (
            f"page.getByRole('{playwright_role}', "
            f"{{ name: '{_escape_js_string(visible_label)}', exact: true }})"
        )
    return ""


def _heuristic_description(role: str, label: str, category: str, target_path: Optional[str]) -> str:
    lower = label.lower()
    if "skip" in lower and "content" in lower:
        return "Accessibility link that jumps focus to the main page content."
    if "screen reader" in lower:
        return "Accessibility entry point for screen reader users."
    if role == "link" and category == "external":
        return f"External link to {label or 'a related resource'}."
    if "login" in lower:
        return "Starts the user login/authentication flow."
    if "password" in lower and "reset" in lower:
        return "Opens the password reset request flow for users who cannot log in."
    if category == "navigation" and target_path:
        return f"Navigates to the {label or target_path.strip('/')} section of the application."
    if role == "button":
        return f"Button that triggers the '{label or 'action'}' action on this page."
    if role == "link":
        return f"Link to {label or (target_path or 'another page')}."
    if role in ("input", "textbox"):
        return f"Input field for entering {label or 'user-provided data'}."
    if role == "combobox":
        return f"Dropdown for selecting {label or 'an option'}."
    return f"Interactive {role} used for {label or 'page interaction'}."


def _is_noise_element(label: str, aria_label: Optional[str]) -> bool:
    candidate = (label or aria_label or "").strip().lower()
    if not candidate:
        return True
    if candidate in NOISE_LABELS:
        return True
    if candidate.isdigit() and len(candidate) <= 2:
        return True
    return False


def _target_path_from_href(
    href: str,
    base_url: str,
    *,
    raw_href: str = "",
    category: str = "",
) -> Optional[str]:
    if not href and not raw_href:
        return None

    raw = (raw_href or "").strip()
    if raw.startswith("/#") or (raw.startswith("#") and category == "internal_hash"):
        frag = raw.lstrip("/#").split("?")[0]
        return f"/#{frag}" if frag else None

    if category == "internal_hash":
        frag = _fragment_from_href(href, raw_href)
        if frag:
            return f"/#{frag}"

    cleaned = _clean_url(href or raw)
    base = _clean_url(base_url)
    if not cleaned.startswith(base):
        return None
    path = _page_path(cleaned, base)
    return path if path != "/" else None


HOME_NAV_REGIONS = frozenset({"header", "footer", "nav"})

HOME_NAV_SKIP_LABELS = frozenset({
    "skip to content",
    "skip to main",
    "skip to main content",
})


def _assert_spec_for_link(
    raw_href: str,
    target_path: Optional[str],
    category: str,
) -> dict:
    if target_path and target_path.startswith("/#"):
        return {"kind": "hash", "value": f"#{target_path[2:]}"}
    if category == "internal_hash":
        frag = _fragment_from_href("", raw_href)
        if frag:
            return {"kind": "hash", "value": f"#{frag}"}
    if target_path and target_path not in ("/", ""):
        return {"kind": "pathname", "value": target_path}
    return {"kind": "same_page", "value": "/"}


def build_home_navigation(home_elements: list[dict]) -> list[dict]:
    """Build top-level home_navigation from home page header/footer/nav links."""
    entries: list[dict] = []
    seen: set[str] = set()

    for el in home_elements:
        if el.get("role") != "link":
            continue
        region = el.get("region", "unknown")
        if region not in HOME_NAV_REGIONS:
            continue
        category = el.get("category", "")
        if category in ("mailto", "tel", "external"):
            continue
        raw_href = (el.get("raw_href") or "").strip()
        if raw_href.lower().startswith(("mailto:", "tel:", "javascript:")):
            continue
        if raw_href in ("", "#"):
            continue

        label = (el.get("label") or "").strip()
        if label.lower() in HOME_NAV_SKIP_LABELS or label.lower().startswith("skip to"):
            continue

        key = f"{label}|{raw_href}"
        if key in seen:
            continue
        seen.add(key)

        target_path = el.get("target_path")
        entries.append({
            "element_id": el.get("element_id"),
            "label": el.get("label"),
            "raw_href": raw_href,
            "target_path": target_path,
            "assert": _assert_spec_for_link(raw_href, target_path, category),
        })

    return entries


def build_unified_elements(
    links: list[Link],
    clickables: list[Clickable],
    base_url: str,
) -> list[dict]:
    """Merge links + clickables into a single deduplicated element list."""
    elements: list[dict] = []
    seen: set[str] = set()

    def add_element(candidate: dict):
        dedupe_key = "|".join([
            candidate.get("role", ""),
            candidate.get("label", ""),
            candidate.get("target_path", "") or "",
            candidate.get("selectors", {}).get("xpath", ""),
            candidate.get("href", "") or "",
        ])
        if dedupe_key in seen:
            return
        seen.add(dedupe_key)
        elements.append(candidate)

    xpath_lookup = {
        (c.tag, c.text, c.aria_label, c.name): c for c in clickables
    }

    for index, link in enumerate(links):
        label = _element_label(link.tag, link.text, link.aria_label, None, None)
        if not label or label == link.tag:
            if link.raw_href:
                label = link.raw_href.lstrip("#/") or link.raw_href
            elif link.aria_label:
                label = link.aria_label
        if _is_noise_element(label, link.aria_label):
            continue

        matched = xpath_lookup.get((link.tag, link.text, link.aria_label, None))
        xpath = matched.xpath if matched else (
            f"//{link.tag}[@aria-label='{link.aria_label}']" if link.aria_label
            else (f"//{link.tag}[contains(text(),'{label[:30]}')]" if label else f"//{link.tag}")
        )
        role = "link" if link.tag == "a" else "button"
        category = (
            "navigation"
            if link.category in ("internal_path", "navigation_button", "spa_route")
            else link.category
        )
        stored_href = _normalize_href_for_storage(link.href, link.raw_href)
        target_path = _target_path_from_href(
            stored_href,
            base_url,
            raw_href=link.raw_href,
            category=link.category,
        )
        fragment = _fragment_from_href(stored_href, link.raw_href)
        element_id = f"{_slugify(label or link.category)}_{index}"

        add_element({
            "element_id": element_id,
            "role": role,
            "tag": link.tag,
            "label": label,
            "description": "",
            "category": category,
            "href": stored_href,
            "raw_href": link.raw_href or "",
            "fragment": fragment,
            "target_path": target_path,
            "region": link.region or "unknown",
            "actions": ["click"],
            "opens_new_tab": link.opens_new_tab,
            "selectors": {
                "playwright": _build_playwright_selector(
                    link.tag,
                    role,
                    label,
                    link.aria_label,
                    None,
                    None,
                    None,
                    raw_href=link.raw_href or None,
                ),
                "xpath": xpath,
            },
        })

    for index, clickable in enumerate(clickables):
        label = _element_label(
            clickable.tag,
            clickable.text,
            clickable.aria_label,
            clickable.name,
            clickable.placeholder,
        )
        if _is_noise_element(label, clickable.aria_label):
            continue

        role = {
            "link": "link",
            "button": "button",
            "input": "input",
            "select": "combobox",
        }.get(clickable.type, clickable.type)
        category = "form_control" if clickable.type in ("input", "select") else "action"
        if clickable.type == "link":
            category = "navigation"
        element_id = f"{_slugify(label or clickable.type)}_{index}"
        clickable_href = clickable.href or ""
        stored_href = _normalize_href_for_storage(clickable_href, clickable_href)
        target_path = _target_path_from_href(stored_href, base_url, category=category)
        fragment = _fragment_from_href(stored_href, clickable_href)

        add_element({
            "element_id": element_id,
            "role": role,
            "tag": clickable.tag,
            "label": label,
            "description": "",
            "category": category,
            "href": stored_href,
            "raw_href": clickable_href,
            "fragment": fragment,
            "target_path": target_path,
            "region": "unknown",
            "actions": ["click"] if clickable.type in ("link", "button") else ["fill", "type"],
            "input_type": clickable.type if clickable.type == "input" else None,
            "name": clickable.name,
            "placeholder": clickable.placeholder,
            "aria_label": clickable.aria_label,
            "is_auth_related": clickable.is_auth_required,
            "selectors": {
                "playwright": _build_playwright_selector(
                    clickable.tag,
                    role,
                    label,
                    clickable.aria_label,
                    clickable.name,
                    None,
                    None,
                ),
                "xpath": clickable.xpath,
            },
        })

    return elements


def build_contract_forms(raw_forms: list[dict], base_url: str) -> list[dict]:
    contract_forms: list[dict] = []
    for index, form in enumerate(raw_forms):
        fields = []
        for field_index, field in enumerate(form.get("fields", [])):
            field_label = field.get("placeholder") or field.get("name") or f"field_{field_index}"
            field_id = _slugify(field.get("name") or field_label, f"field_{field_index}")
            fields.append({
                "field_id": field_id,
                "name": field.get("name", ""),
                "type": field.get("type", "text"),
                "label": field_label,
                "description": "",
                "required": field.get("required", False),
                "placeholder": field.get("placeholder", ""),
                "selectors": {
                    "playwright": _build_playwright_selector(
                        "input",
                        "input",
                        field_label,
                        None,
                        field.get("name"),
                        field.get("element_id") or None,
                        field.get("data_testid") or None,
                    ),
                    "xpath": field.get("xpath", ""),
                },
            })

        form_label = fields[0]["label"] if fields else f"form_{index}"
        contract_forms.append({
            "form_id": _slugify(form_label, f"form_{index}"),
            "description": "",
            "action": _clean_url(form.get("action", "")) or base_url,
            "method": form.get("method", "GET"),
            "selectors": {"xpath": form.get("xpath", "")},
            "fields": fields,
        })
    return contract_forms


def apply_descriptions(
    elements: list[dict],
    forms: list[dict],
    descriptions: dict,
):
    element_desc = descriptions.get("elements", {})
    form_desc = descriptions.get("forms", {})
    field_desc = descriptions.get("fields", {})

    for element in elements:
        desc = element_desc.get(element["element_id"])
        if desc:
            element["description"] = desc
        else:
            element["description"] = _heuristic_description(
                element.get("role", ""),
                element.get("label", ""),
                element.get("category", ""),
                element.get("target_path"),
            )

    for form in forms:
        desc = form_desc.get(form["form_id"])
        form["description"] = desc or f"Form used to collect and submit {form['form_id'].replace('_', ' ')} data."
        for field in form.get("fields", []):
            field_key = f"{form['form_id']}.{field['field_id']}"
            field["description"] = (
                field_desc.get(field_key)
                or field_desc.get(field["field_id"])
                or _heuristic_description("input", field.get("label", ""), "form_control", None)
            )


# ─────────────────────────────────────────────
# XPath Generator
# ─────────────────────────────────────────────

def get_xpath(element) -> str:
    """Generate absolute XPath for a BeautifulSoup element via lxml."""
    try:
        # Re-parse with lxml to get proper XPath
        html = str(element)
        tree = etree.fromstring(f"<root>{html}</root>")
        nodes = tree.xpath("//*")
        if nodes:
            return etree.getpath(nodes[0]).replace("/root/", "/html/body/")
    except Exception:
        pass

    # Fallback: build XPath from tag + attributes
    tag = element.name
    attrs = []
    if element.get("id"):
        return f"//{tag}[@id='{element['id']}']"
    if element.get("name"):
        attrs.append(f"@name='{element['name']}'")
    if element.get("data-testid"):
        attrs.append(f"@data-testid='{element['data-testid']}'")
    if element.get("aria-label"):
        attrs.append(f"@aria-label='{element['aria-label']}'")
    if attrs:
        return f"//{tag}[{' and '.join(attrs)}]"

    # Last resort: positional
    text = element.get_text(strip=True)[:30]
    if text:
        return f"//{tag}[contains(text(),'{text}')]"
    return f"//{tag}"


# ─────────────────────────────────────────────
# Clickable Extractor
# ─────────────────────────────────────────────

def extract_clickables(soup: BeautifulSoup, base_url: str) -> tuple[list[Clickable], list[dict]]:
    """Extract all interactive elements and return (clickables, forms)."""
    clickables = []
    forms = []
    seen_xpaths = set()

    # --- Links ---
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"])
        xpath = get_xpath(a)
        if xpath in seen_xpaths:
            continue
        seen_xpaths.add(xpath)
        clickables.append(Clickable(
            tag="a",
            type="link",
            text=a.get_text(strip=True)[:100],
            xpath=xpath,
            href=href,
            aria_label=a.get("aria-label"),
        ))

    # --- Buttons ---
    for btn in soup.find_all(["button", "input"], attrs={"type": lambda t: t in (None, "button", "submit", "reset")}):
        xpath = get_xpath(btn)
        if xpath in seen_xpaths:
            continue
        seen_xpaths.add(xpath)
        text = btn.get_text(strip=True) or btn.get("value", "") or btn.get("aria-label", "")
        clickables.append(Clickable(
            tag=btn.name,
            type="button",
            text=text[:100],
            xpath=xpath,
            name=btn.get("name"),
            aria_label=btn.get("aria-label"),
        ))

    # --- Inputs ---
    for inp in soup.find_all("input"):
        input_type = inp.get("type", "text")
        if input_type in ("button", "submit", "reset", "hidden"):
            continue
        xpath = get_xpath(inp)
        if xpath in seen_xpaths:
            continue
        seen_xpaths.add(xpath)
        clickables.append(Clickable(
            tag="input",
            type="input",
            text=inp.get("placeholder", inp.get("aria-label", inp.get("name", ""))),
            xpath=xpath,
            name=inp.get("name"),
            placeholder=inp.get("placeholder"),
            aria_label=inp.get("aria-label"),
        ))

    # --- Selects ---
    for sel in soup.find_all("select"):
        xpath = get_xpath(sel)
        if xpath in seen_xpaths:
            continue
        seen_xpaths.add(xpath)
        clickables.append(Clickable(
            tag="select",
            type="select",
            text=sel.get("name", sel.get("aria-label", "")),
            xpath=xpath,
            name=sel.get("name"),
        ))

    # --- Forms ---
    for form in soup.find_all("form"):
        form_data = {
            "action": urljoin(base_url, form.get("action", "")),
            "method": form.get("method", "get").upper(),
            "xpath": get_xpath(form),
            "fields": []
        }
        for field_el in form.find_all(["input", "select", "textarea"]):
            form_data["fields"].append({
                "name": field_el.get("name", ""),
                "type": field_el.get("type", field_el.name),
                "placeholder": field_el.get("placeholder", ""),
                "required": field_el.has_attr("required"),
                "xpath": get_xpath(field_el),
                "element_id": field_el.get("id", ""),
                "data_testid": field_el.get("data-testid", ""),
            })
        forms.append(form_data)

    return clickables, forms


# ─────────────────────────────────────────────
# LLM Intelligence Layer
# ─────────────────────────────────────────────

class LLMAnalyzer:
    def __init__(self):
        self.model = "claude-haiku-4-5-20251001"  # fast and cheap for analysis

    def _run(self, prompt: str) -> str:
        result = subprocess.run(
            ["claude", "-p", "--output-format", "json", "--model", self.model],
            input=prompt,
            capture_output=True, text=True, check=True,
        )
        return json.loads(result.stdout)["result"].strip()

    def decide_which_urls_to_crawl(self, discovered_urls: list[str], base_url: str, already_crawled: list[str]) -> list[str]:
        """Ask LLM to pick the most important URLs to crawl next."""
        if not discovered_urls:
            return []

        prompt = f"""
You are helping build a QA test suite for a web application.
Base URL: {base_url}
Already crawled: {json.dumps(already_crawled[:20])}
Newly discovered URLs: {json.dumps(discovered_urls[:50])}

Select URLs worth crawling for thorough QA coverage. Prioritise:
1. Unique functional pages (login, dashboard, forms, lists, detail views)
2. Pages with different URL patterns (avoid duplicates like /item/1, /item/2)
3. Protected/auth pages
4. Skip: static assets, external links, pagination duplicates, logout

Return ONLY a JSON array of selected URLs, no explanation.
Maximum 15 URLs.
"""
        try:
            content = self._run(prompt)
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            log.warning(f"LLM URL selection failed: {e}, falling back to first 10")
            return discovered_urls[:10]

    def analyze_page(self, url: str, title: str, page_text: str, clickables: list[Clickable]) -> dict:
        """Ask LLM to classify the page and assign test priority."""
        clickable_summary = [{"type": c.type, "text": c.text, "tag": c.tag} for c in clickables[:30]]

        prompt = f"""
You are a QA analyst reviewing a web page for test planning.

URL: {url}
Title: {title}
Page text (truncated): {page_text[:500]}
Interactive elements: {json.dumps(clickable_summary)}

Respond ONLY with a JSON object (no markdown):
{{
  "page_type": "<one of: login | dashboard | list | detail | form | nav | settings | error | unknown>",
  "test_priority": "<one of: high | medium | low>",
  "is_protected": <true if this page likely requires authentication, else false>,
  "notes": "<one sentence: what this page does and why it matters for QA>"
}}
"""
        try:
            content = self._run(prompt)
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            log.warning(f"LLM page analysis failed for {url}: {e}")
            return {"page_type": "unknown", "test_priority": "medium", "is_protected": False, "notes": ""}

    def describe_interactive_elements(
        self,
        url: str,
        title: str,
        page_type: str,
        page_notes: str,
        elements: list[dict],
        forms: list[dict],
    ) -> dict:
        """Generate short purpose descriptions for elements, forms, and fields."""
        if not elements and not forms:
            return {"elements": {}, "forms": {}, "fields": {}}

        element_summary = [
            {
                "element_id": el["element_id"],
                "role": el.get("role"),
                "label": el.get("label"),
                "category": el.get("category"),
                "target_path": el.get("target_path"),
            }
            for el in elements[:40]
        ]
        form_summary = [
            {
                "form_id": form["form_id"],
                "method": form.get("method"),
                "fields": [
                    {
                        "field_id": field["field_id"],
                        "name": field.get("name"),
                        "type": field.get("type"),
                        "label": field.get("label"),
                    }
                    for field in form.get("fields", [])[:10]
                ],
            }
            for form in forms[:5]
        ]

        prompt = f"""
You are documenting a web application for QA test planning.

Page URL: {url}
Page title: {title}
Page type: {page_type}
Page summary: {page_notes}

Interactive elements:
{json.dumps(element_summary, indent=2)}

Forms:
{json.dumps(form_summary, indent=2)}

Return ONLY JSON (no markdown) with this shape:
{{
  "elements": {{ "<element_id>": "<one short sentence describing purpose for QA>" }},
  "forms": {{ "<form_id>": "<one short sentence describing what the form is for>" }},
  "fields": {{
    "<form_id>.<field_id>": "<one short sentence describing what the user enters/selects>"
  }}
}}

Rules:
- One sentence per item, max 20 words.
- Focus on user-visible purpose, not implementation.
- Include every element_id, form_id, and form_id.field_id listed above.
"""
        try:
            content = self._run(prompt)
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            log.warning(f"LLM element description failed for {url}: {e}")
            return {"elements": {}, "forms": {}, "fields": {}}

    def plan_auth_steps(
        self,
        *,
        url: str,
        title: str,
        page_text: str,
        forms: list[dict],
        elements: list[dict],
        available_keys: list[str],
    ) -> dict:
        """Plan login steps mapping env credential keys to form fields (no secret values)."""
        if not available_keys:
            return {"flow_type": "unknown", "steps": [], "success_hint": ""}

        form_summary = [
            {
                "form_id": form.get("form_id"),
                "method": form.get("method"),
                "fields": [
                    {
                        "field_id": field.get("field_id"),
                        "name": field.get("name"),
                        "type": field.get("type"),
                        "label": field.get("label"),
                        "placeholder": field.get("placeholder"),
                        "selectors": field.get("selectors"),
                    }
                    for field in form.get("fields", [])[:12]
                ],
            }
            for form in forms[:4]
        ]
        button_summary = [
            {
                "element_id": el.get("element_id"),
                "role": el.get("role"),
                "label": el.get("label"),
                "selectors": el.get("selectors"),
            }
            for el in elements
            if el.get("role") in ("button", "link")
            or (el.get("label") or "").lower()
            in ("login", "sign in", "send otp", "verify", "submit", "continue")
        ][:20]

        prompt = f"""
You are planning a Playwright login flow for QA web scraping.

Page URL: {url}
Page title: {title}
Page text (truncated): {page_text[:800]}

Forms:
{json.dumps(form_summary, indent=2)}

Buttons/links:
{json.dumps(button_summary, indent=2)}

Available credential keys (values are NOT provided — reference keys only):
{json.dumps(available_keys)}

Return ONLY JSON (no markdown):
{{
  "flow_type": "password | otp | mixed | unknown",
  "steps": [
    {{"action": "fill", "selector": "<css selector>", "credential_key": "<one of available keys>"}},
    {{"action": "fill_split_otp", "selector": "input.grm-otp-input-box", "credential_key": "QA_TEST_OTP"}},
    {{"action": "click", "selector": "<css selector>", "label_hint": "<button label>"}},
    {{"wait_ms": 1500}}
  ],
  "success_hint": "url_path_not_login_or_dashboard"
}}

Credential key meanings (values are never provided):
- QA_USERNAME: username, email, or user identifier field
- QA_PASSWORD: password field
- QA_TEST_MOBILE: phone/mobile number field (often before an OTP step)
- QA_TEST_OTP: one-time password, verification code, or PIN field

Rules:
- Infer the login flow from the forms and buttons on THIS page only.
- If the page only shows a "Sign in" / "Log in" button with no username/password fields visible yet, plan ONLY that click (and optional wait_ms) — the scraper will re-plan on the IdP page (e.g. Keycloak) after redirect.
- Use only credential_key values from the available keys list.
- Prefer stable CSS selectors from field selectors or [name=...], [id=...], [data-testid=...].
- Selectors must be raw CSS only (e.g. `#username`, `[name=\"login\"]`) — never `page.locator(...)` or other Playwright API syntax.
- Multi-step flows: fill fields in UI order; insert click steps for intermediate actions (e.g. request code) and wait_ms when a field appears after an action.
- Mobile + OTP on the **same URL** (SPA): plan phase 1 only (mobile fill → Login/Send click → wait_ms). The scraper waits for OTP inputs, then fills split boxes (`fill_split_otp` with `.grm-otp-input-box` or `input[aria-label*='OTP character']`) and clicks Verify.
- Button labels vary by app — use selectors from the page (`#submitButton`, `[type=submit]`, `:has-text('Verify')`), not hard-coded copy.
- If this is not a login page, return "steps": [].
- Maximum 8 steps.
"""
        try:
            content = self._run(prompt)
            plan = parse_json_response(content)
            if not isinstance(plan.get("steps"), list):
                plan["steps"] = []
            return plan
        except Exception as e:
            log.warning(f"LLM auth planning failed for {url}: {e}")
            return {"flow_type": "unknown", "steps": [], "success_hint": ""}


# ─────────────────────────────────────────────
# Core Scraper
# ─────────────────────────────────────────────

class WebScraper:
    def __init__(
        self,
        base_url: str,
        login_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        username_selector: str = "input[type='email'], input[name='username'], input[name='email']",
        password_selector: str = "input[type='password']",
        submit_selector: str = "button[type='submit']",
        max_pages: int = 30,
        delay: float = 0.5,
        wait_until: str = "load",
        credentials: Optional[dict[str, str]] = None,
        headed: bool = False,
        seed_paths: Optional[list[str]] = None,
        interact: bool = True,
        probe_common_paths: bool = False,
        ready_timeout: float = 12.0,
        max_expanders: int = 8,
    ):
        self.base_url = base_url.rstrip("/")
        self.base_domain = urlparse(base_url).netloc
        self.wait_until = wait_until
        self.username_selector = username_selector
        self.password_selector = password_selector
        self.submit_selector = submit_selector
        self.max_pages = max_pages
        self.delay = delay
        self.seed_paths = list(seed_paths or [])
        self.interact = interact
        self.probe_common_paths = probe_common_paths
        self.ready_timeout = ready_timeout
        self.max_expanders = max_expanders
        self.credentials = merge_legacy_cli_credentials(
            credentials if credentials is not None else load_scraper_credentials(),
            login_url=login_url,
            username=username,
            password=password,
        )
        self.login_url = login_url or default_login_url(self.credentials, self.base_url)
        self.username = username or self.credentials.get("QA_USERNAME")
        self.password = password or self.credentials.get("QA_PASSWORD")
        self.authenticated = False
        self._auth_attempted = False
        self.headless = resolve_scraper_headless(headed)
        self.llm = LLMAnalyzer()
        self.visited: set[tuple[str, str]] = set()
        self.scraped_page_urls: set[str] = set()
        self.seen_templates: set[str] = set()
        self.pending_protected: set[str] = set()
        self.pages_attempted = 0
        self.sitemap = SiteMap(base_url=base_url, total_pages=0, wait_until=wait_until)

    def _is_same_domain(self, url: str) -> bool:
        return urlparse(url).netloc == self.base_domain

    def _normalise_url(self, url: str) -> str:
        parsed = urlparse(url)
        return parsed._replace(fragment="", query="").geturl().rstrip("/")

    def _wait_for_page_ready(self, page: Page) -> dict:
        """SPA readiness: network idle, then stable interactive-element count."""
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

        count_js = (
            "() => document.querySelectorAll("
            "'a[href], button, input, select, textarea, [role=\"button\"], [role=\"link\"]'"
            ").length"
        )
        last = -1
        stable_polls = 0
        state = "timeout"
        deadline = time.monotonic() + self.ready_timeout
        while time.monotonic() < deadline:
            try:
                count = page.evaluate(count_js)
            except Exception:
                count = -1
            if count >= 0 and count == last:
                stable_polls += 1
                if stable_polls >= 2:
                    state = "stable"
                    break
            else:
                stable_polls = 0
            last = count
            time.sleep(0.3)
        return {"ready_state": state, "interactive_count": max(last, 0)}

    def _try_recover_crawl_page(self, page: Page, recovery_url: str | None) -> None:
        """After a bad navigation, return to the last good page so the crawl can continue."""
        try:
            page.evaluate("() => document.readyState")
        except Exception:
            log.warning("  Page context unusable after failed navigation — remaining queue may fail")
            return
        if not recovery_url:
            return
        try:
            if self._normalise_url(page.url) != self._normalise_url(recovery_url):
                page.goto(
                    recovery_url,
                    wait_until="domcontentloaded",
                    timeout=navigation_timeout_ms(),
                )
                self._wait_for_page_ready(page)
        except Exception as exc:
            log.debug("Crawl recovery navigation: %s", exc)

    def _get_page_html(
        self, page: Page, url: str, *, recovery_url: str | None = None
    ) -> tuple[Optional[str], Optional[str], dict]:
        """Load a page and return (html, final_url_after_redirects, ready_meta)."""
        meta: dict = {}
        response = None

        def _goto(wait_until: str) -> bool:
            nonlocal response
            try:
                response = page.goto(url, wait_until=wait_until, timeout=navigation_timeout_ms())
                return True
            except Exception as e:
                log.warning(f"Failed to load {url} with wait_until={wait_until}: {e}")
                return False

        if not _goto(self.wait_until):
            if self.wait_until != "domcontentloaded":
                _goto("domcontentloaded")
            if response is None:
                self._try_recover_crawl_page(page, recovery_url)
                meta["skip_reason"] = "load_failed"
                return None, None, meta

        if is_http_error_status(response.status if response else None):
            status = response.status if response else None
            log.warning("  HTTP %s — skipping: %s", status, url)
            self._try_recover_crawl_page(page, recovery_url)
            meta["skip_reason"] = "http_error"
            meta["http_status"] = status
            return None, None, meta

        ready_meta = self._wait_for_page_ready(page)
        time.sleep(self.delay)
        html = page.content()
        final_url = self._normalise_url(page.url)
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title else final_url
        page_text = soup.get_text(separator=" ", strip=True)
        if looks_like_error_page(title, page_text, response.status if response else None):
            log.warning("  Error page detected — skipping: %s", url)
            self._try_recover_crawl_page(page, recovery_url)
            meta["skip_reason"] = "error_page"
            meta.update(ready_meta)
            return None, None, meta

        meta.update(ready_meta)
        return html, final_url, meta

    def _seed_urls(self) -> list[str]:
        urls: list[str] = []
        for path in self.seed_paths:
            candidate = (
                path if path.startswith("http") else urljoin(self.base_url + "/", path.lstrip("/"))
            )
            normalised = self._normalise_url(candidate)
            if self._is_same_domain(normalised):
                urls.append(normalised)
        return urls

    def _probe_common_paths_list(self) -> list[str]:
        if not self.probe_common_paths:
            return []
        return [
            self._normalise_url(urljoin(self.base_url + "/", path.lstrip("/")))
            for path in COMMON_STATIC_PATHS
        ]

    def _extract_scraped_page(
        self,
        page: Page,
        page_url: str,
        html: str,
        depth: int,
        *,
        allow_auth: bool = False,
        auth_context: str = "anonymous",
        scrape_status: str = "ok",
        ready_state: str = "stable",
    ) -> ScrapedPage:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.string.strip() if soup.title else page_url
        page_text = soup.get_text(separator=" ", strip=True)

        page_links = extract_links_from_page(page, page_url, self.base_domain)
        self.sitemap.all_links = merge_unique_links(self.sitemap.all_links, page_links)
        clickables, forms = extract_clickables(soup, page_url)
        if self.interact:
            extra = interaction_pass(
                page,
                normalise_url=self._normalise_url,
                wait_for_page_ready=self._wait_for_page_ready,
                max_expanders=self.max_expanders,
            )
            seen_xpaths = {c.xpath for c in clickables}
            for clickable in extra:
                if clickable.xpath not in seen_xpaths:
                    clickables.append(clickable)
                    seen_xpaths.add(clickable.xpath)
        analysis = self.llm.analyze_page(page_url, title, page_text, clickables)

        if analysis.get("is_protected"):
            for c in clickables:
                if any(w in c.text.lower() for w in ["login", "sign in", "logout", "account", "profile"]):
                    c.is_auth_required = True

        elements = build_unified_elements(page_links, clickables, self.base_url)
        contract_forms = build_contract_forms(forms, self.base_url)

        if (
            allow_auth
            and not self.authenticated
            and has_auth_credentials(self.credentials)
            and is_login_gate(page_url, analysis.get("page_type", "unknown"), contract_forms)
        ):
            auth_url = resolve_auth_url(self.credentials, self.base_url, page_url)
            if default_login_url(self.credentials, self.base_url):
                auth_ok = authenticate_at_url(self, page, auth_url)
            else:
                auth_ok = authenticate_page(
                    self,
                    page,
                    url=page_url,
                    title=title,
                    page_text=page_text,
                    analysis=analysis,
                    forms=contract_forms,
                    elements=elements,
                )
            if auth_ok:
                html, refreshed_url, ready_meta = self._get_page_html(page, page_url)
                if html:
                    return self._extract_scraped_page(
                        page,
                        refreshed_url or page_url,
                        html,
                        depth,
                        allow_auth=False,
                        auth_context=auth_context,
                        ready_state=ready_meta.get("ready_state", "unknown"),
                    )

        descriptions = self.llm.describe_interactive_elements(
            url=page_url,
            title=title,
            page_type=analysis.get("page_type", "unknown"),
            page_notes=analysis.get("notes", ""),
            elements=elements,
            forms=contract_forms,
        )
        apply_descriptions(elements, contract_forms, descriptions)

        is_protected = auth_context == "authenticated" or analysis.get("is_protected", False)
        return ScrapedPage(
            url=page_url,
            title=title,
            is_protected=is_protected,
            depth=depth,
            clickables=clickables,
            links=page_links,
            elements=elements,
            forms=contract_forms,
            page_type=analysis.get("page_type", "unknown"),
            test_priority=analysis.get("test_priority", "medium"),
            llm_notes=analysis.get("notes", ""),
            auth_context=auth_context,
            scrape_status=scrape_status,
            ready_state=ready_state,
        )

    def _discover_crawl_urls(
        self,
        soup: BeautifulSoup,
        current_url: str,
        page_links: list[Link],
    ) -> list[str]:
        """Collect same-domain path URLs worth enqueueing for crawl."""
        crawl_urls: set[str] = set()

        for link in page_links:
            if link.crawlable and self._is_same_domain(link.href):
                crawl_urls.add(self._normalise_url(link.href))

        for a in soup.find_all("a", href=True):
            href = urljoin(current_url, a["href"])
            normalised = self._normalise_url(href)
            if self._is_same_domain(normalised) and classify_link(
                a["href"], href, self.base_domain, _is_static_asset
            )[1]:
                crawl_urls.add(normalised)

        return sorted(crawl_urls)

    def _discover_button_routes(self, page: Page, page_url: str) -> list[Link]:
        """Probe no-href buttons; record SPA routes discovered via URL change."""
        if is_login_path(page_url) and not self.authenticated:
            return []

        limit = button_probe_limit()
        if limit <= 0:
            return []

        route_dicts = discover_button_routes(
            page,
            page_url,
            base_domain=self.base_domain,
            normalise_url=self._normalise_url,
            is_static_asset=_is_static_asset,
            delay=self.delay,
            probe_limit=limit,
            navigation_timeout_ms=navigation_timeout_ms(),
        )
        return [_link_from_dict(item) for item in route_dicts]

    def _visited_urls(self) -> set[str]:
        return {url for _ctx, url in self.visited}

    def _crawl(self, page: Page, initial_queue: list[str], auth_context: str) -> None:
        queue: list[str] = []
        for url in initial_queue:
            normalised = self._normalise_url(url)
            if normalised not in queue:
                queue.append(normalised)

        last_good_url: str | None = None

        while queue and self.pages_attempted < self.max_pages:
            url = queue.pop(0)
            if _is_static_asset(url):
                log.info("  Skipping static/download URL: %s", url)
                continue

            visit_key = (auth_context, url)
            if visit_key in self.visited:
                continue
            self.visited.add(visit_key)
            self.pages_attempted += 1

            log.info(
                f"[{self.pages_attempted}/{self.max_pages}] ({auth_context}) Scraping: {url}"
            )

            try:
                html, final_url, ready_meta = self._get_page_html(
                    page, url, recovery_url=last_good_url
                )
            except Exception as exc:
                log.warning("  Crawl step failed for %s: %s", url, exc)
                self._try_recover_crawl_page(page, last_good_url)
                continue

            if not html:
                reason = ready_meta.get("skip_reason", "load_failed")
                log.info("  Skipping bad page (%s): %s", reason, url)
                continue

            page_url = final_url or url
            if auth_context == "anonymous" and looks_like_login_redirect(url, page_url):
                log.info(f"  Redirected to login — marked protected: {url}")
                self.pending_protected.add(url)
                continue

            if page_url in self.scraped_page_urls:
                log.info(f"  Skipping duplicate resolved page: {page_url}")
                continue
            self.scraped_page_urls.add(page_url)
            self.seen_templates.add(url_template(page_url))
            last_good_url = page_url

            scraped = self._extract_scraped_page(
                page,
                page_url,
                html,
                depth=self.pages_attempted,
                allow_auth=(auth_context == "authenticated"),
                auth_context=auth_context,
                ready_state=ready_meta.get("ready_state", "unknown"),
            )
            self.sitemap.pages.append(scraped)

            if scraped.is_protected:
                self.sitemap.auth_urls.append(page_url)
            else:
                self.sitemap.public_urls.append(page_url)

            button_links = self._discover_button_routes(page, page_url)
            if button_links:
                scraped.links = merge_unique_links(scraped.links, button_links)
                self.sitemap.all_links = merge_unique_links(self.sitemap.all_links, button_links)
                scraped.elements = build_unified_elements(
                    scraped.links, scraped.clickables, self.base_url
                )

            soup = BeautifulSoup(html, "html.parser")
            crawl_candidates = self._discover_crawl_urls(soup, page_url, scraped.links)
            visited_urls = self._visited_urls() | set(queue)
            selected = select_crawl_urls(crawl_candidates, self.seen_templates, visited_urls)
            for candidate in selected:
                key = (auth_context, candidate)
                if key not in self.visited and candidate not in queue:
                    queue.append(candidate)

            href_crawlable = sum(
                1
                for link in scraped.links
                if link.crawlable and link.category in ("internal_path", "spa_route")
            )
            button_routes = sum(1 for link in scraped.links if link.category == "spa_route")
            log.info(
                f"  Found {len(scraped.elements)} element(s), {len(scraped.forms)} form(s), "
                f"ready={scraped.ready_state}, "
                f"({href_crawlable} crawlable path(s), {button_routes} button route(s)), "
                f"enqueued {len(selected)} new URL(s)"
            )

    def probe_auth(self, login_url: Optional[str] = None) -> dict:
        """
        Auth-only: open login page, plan and run login steps, return a report.
        No crawl, no contract write. Use to iterate on login before a full scrape.
        """
        target = login_url or self.login_url or default_login_url(self.credentials, self.base_url)
        if not target:
            return {
                "login_url": "",
                "available_keys": available_fillable_keys(self.credentials),
                "plan_source": "none",
                "flow_type": "unknown",
                "steps": [],
                "success": False,
                "final_url": "",
                "error": "no_login_url_set_QA_LOGIN_URL",
            }

        self.authenticated = False
        self._auth_attempted = False

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self.headless)
            page = browser.new_page()
            try:
                return probe_authentication_at_url(self, page, target)
            finally:
                if not self.headless:
                    log.info("Headed auth probe: holding browser open for 10s before close")
                    time.sleep(10)
                browser.close()

    def scrape(self) -> SiteMap:
        with sync_playwright() as pw:
            browser: Browser = pw.chromium.launch(headless=self.headless)

            context = browser.new_context(accept_downloads=False)
            page = context.new_page()
            initial = [self._normalise_url(self.base_url)]
            initial += self._probe_common_paths_list()
            initial += self._seed_urls()
            self._crawl(page, initial, auth_context="anonymous")
            context.close()

            if has_auth_credentials(self.credentials):
                login_target = default_login_url(self.credentials, self.base_url)
                if login_target:
                    context = browser.new_context(accept_downloads=False)
                    page = context.new_page()
                    self.authenticated = False
                    self._auth_attempted = False
                    if authenticate_at_url(self, page, login_target):
                        auth_queue = sorted(self.pending_protected)
                        landing = self._normalise_url(page.url)
                        if landing not in auth_queue:
                            auth_queue.insert(0, landing)
                        self._crawl(page, auth_queue, auth_context="authenticated")
                    else:
                        log.warning("Authentication failed — protected pages recorded as stubs")
                    context.close()

            browser.close()

        auth_visited = {url for ctx, url in self.visited if ctx == "authenticated"}
        for url in sorted(self.pending_protected):
            if url in auth_visited or url in self.scraped_page_urls:
                continue
            self.sitemap.pages.append(
                ScrapedPage(
                    url=url,
                    title=url,
                    is_protected=True,
                    depth=0,
                    page_type="protected",
                    test_priority="high",
                    llm_notes=(
                        "Redirected to login during anonymous crawl; "
                        "supply credentials to scrape this page."
                    ),
                    auth_context="anonymous",
                    scrape_status="login_redirect",
                    ready_state="n/a",
                )
            )
            self.sitemap.auth_urls.append(url)

        self.sitemap.total_pages = len(self.sitemap.pages)
        return self.sitemap


# ─────────────────────────────────────────────
# Output Serialiser
# ─────────────────────────────────────────────

def save_sitemap(sitemap: SiteMap, output_path: str = "site_map.json", merge: bool = True):
    """Serialise UI action contract JSON for test generation."""
    base_url = _clean_url(sitemap.base_url)
    app_name = sitemap.pages[0].title if sitemap.pages else urlparse(base_url).netloc

    route_index = []
    contract_pages = []

    for p in sitemap.pages:
        path = _page_path(p.url, base_url)
        page_id = _page_id_from_path(path)
        route_index.append({
            "page_id": page_id,
            "path": path,
            "url": _clean_url(p.url),
            "title": p.title,
            "page_type": p.page_type,
            "test_priority": p.test_priority,
            "is_protected": p.is_protected,
        })
        contract_pages.append({
            "page_id": page_id,
            "path": path,
            "url": _clean_url(p.url),
            "title": p.title,
            "description": p.llm_notes,
            "page_type": p.page_type,
            "test_priority": p.test_priority,
            "is_protected": p.is_protected,
            "depth": p.depth,
            "auth_context": p.auth_context,
            "scrape_status": p.scrape_status,
            "ready_state": p.ready_state,
            "elements": p.elements,
            "forms": p.forms,
        })

    home_elements: list[dict] = []
    for page in contract_pages:
        if page.get("path") == "/":
            home_elements = page.get("elements", [])
            break

    data = {
        "contract_version": CONTRACT_VERSION,
        "application": {
            "name": app_name,
            "base_url": base_url,
        },
        "extraction_metadata": {
            "tool": "qa-automation/scraper.py",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "total_pages": sitemap.total_pages,
            "wait_until": sitemap.wait_until,
            "deterministic_frontier": True,
        },
        "route_index": route_index,
        "home_navigation": build_home_navigation(home_elements),
        "pages": contract_pages,
    }

    out = Path(output_path)
    if merge and out.exists():
        try:
            previous = json.loads(out.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Could not read previous contract for merge: %s", exc)
            previous = None
        if previous and previous.get("pages"):
            data, diff = merge_contracts(previous, data)
            diff_path = out.with_name(out.stem + "-diff.md")
            diff_path.write_text(render_diff_markdown(diff), encoding="utf-8")
            log.info(
                "Merged with previous contract: +%d page(s), %d stale page(s), "
                "%d page(s) with element changes — diff at %s",
                len(diff["pages_added"]),
                len(diff["pages_stale"]),
                len(set(diff["elements_added"]) | set(diff["elements_stale"])),
                diff_path,
            )

    out.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    log.info(f"UI action contract saved to {output_path}")
    return str(out)


# ─────────────────────────────────────────────
# Public API — entry point for test generator
# ─────────────────────────────────────────────

def scrape_website(
    base_url: str,
    output_path: str = "site_map.json",
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    username_selector: str = "input[type='email'], input[name='username'], input[name='email']",
    password_selector: str = "input[type='password']",
    submit_selector: str = "button[type='submit']",
    max_pages: int = 30,
    wait_until: str = "load",
    credentials: Optional[dict[str, str]] = None,
    headed: bool = False,
    seed_paths: Optional[list[str]] = None,
    interact: bool = True,
    merge: bool = True,
    probe_common_paths: bool = False,
) -> str:
    """
    Scrape a website and save a JSON sitemap for test generation.

    Args:
        base_url:           The website to scrape (e.g. https://myapp.com)
        output_path:        Where to save the JSON output
        login_url:          URL of the login page (for protected pages)
        username:           Login username/email
        password:           Login password
        username_selector:  CSS selector for username field
        password_selector:  CSS selector for password field
        submit_selector:    CSS selector for submit button
        max_pages:          Max pages to crawl (default 30)
        seed_paths:         Extra entry-point paths/URLs to enqueue
        interact:           Run dropdown/menu interaction pass
        merge:              Union with existing contract and write -diff.md
        probe_common_paths: Probe well-known static routes (/sitemap, /faq, …)

    Returns:
        Path to the saved JSON file
    """
    scraper = WebScraper(
        base_url=base_url,
        login_url=login_url,
        username=username,
        password=password,
        username_selector=username_selector,
        password_selector=password_selector,
        submit_selector=submit_selector,
        max_pages=max_pages,
        wait_until=wait_until,
        credentials=credentials,
        headed=headed,
        seed_paths=seed_paths,
        interact=interact,
        probe_common_paths=probe_common_paths,
    )
    sitemap = scraper.scrape()
    return save_sitemap(sitemap, output_path, merge=merge)


def probe_scraper_auth(
    base_url: str,
    *,
    login_url: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
    credentials: Optional[dict[str, str]] = None,
    headed: bool = False,
) -> dict:
    """Run auth probe only (no crawl). Returns a JSON-safe report dict."""
    scraper = WebScraper(
        base_url=base_url,
        login_url=login_url,
        username=username,
        password=password,
        max_pages=1,
        credentials=credentials,
        headed=headed,
        interact=False,
    )
    return scraper.probe_auth(login_url)


# ─────────────────────────────────────────────
# CLI runner
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape a website and generate a QA sitemap")
    parser.add_argument("url", help="Base URL to scrape")
    parser.add_argument("--output", default="site_map.json", help="Output JSON path")
    parser.add_argument("--login-url", help="Login page URL")
    parser.add_argument("--username", help="Login username")
    parser.add_argument("--password", help="Login password")
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument(
        "--wait-until",
        default="load",
        choices=["load", "domcontentloaded", "networkidle"],
        help="Playwright navigation wait strategy (default: load)",
    )
    parser.add_argument(
        "--seed-paths",
        default="",
        help="Comma-separated extra entry paths to crawl",
    )
    parser.add_argument("--no-interact", action="store_true", help="Skip dropdown/menu interaction pass")
    parser.add_argument("--no-merge", action="store_true", help="Overwrite contract instead of merging")
    parser.add_argument(
        "--probe-common-paths",
        action="store_true",
        help="Probe well-known static routes (/sitemap, /faq, …)",
    )
    parser.add_argument(
        "--auth-only",
        action="store_true",
        help="Only test login (no crawl, no contract). Prints JSON report to stdout.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show browser window during scrape or auth probe",
    )
    args = parser.parse_args()

    if args.auth_only:
        import json as _json

        report = probe_scraper_auth(
            base_url=args.url,
            login_url=args.login_url,
            username=args.username,
            password=args.password,
            headed=args.headed,
        )
        print(_json.dumps(report, indent=2))
        raise SystemExit(0 if report.get("success") else 1)

    path = scrape_website(
        base_url=args.url,
        output_path=args.output,
        login_url=args.login_url,
        username=args.username,
        password=args.password,
        max_pages=args.max_pages,
        wait_until=args.wait_until,
        seed_paths=[s.strip() for s in args.seed_paths.split(",") if s.strip()],
        interact=not args.no_interact,
        merge=not args.no_merge,
        probe_common_paths=args.probe_common_paths,
        headed=args.headed,
    )
    print(f"\n✅ Done! Sitemap saved to: {path}")
