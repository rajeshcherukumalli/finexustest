"""Load and slice UI action contract JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

SUPPORTED_CONTRACT_VERSIONS = frozenset({"1.0.0", "1.1.0", "1.2.0"})
SUPPORTED_CONTRACT_VERSION = "1.2.0"

MODULE_PAGE_TYPES: dict[str, set[str]] = {
    "auth": {"login"},
    "navigation": {"nav", "dashboard"},
    "content": {"list", "detail", "form", "settings", "error", "unknown"},
}

DEFAULT_MODULES = ("auth", "navigation", "content")


def _slim_element(e: dict) -> dict:
    out = {
        "element_id": e.get("element_id"),
        "role": e.get("role"),
        "label": e.get("label"),
        "description": e.get("description"),
        "category": e.get("category"),
        "target_path": e.get("target_path"),
        "href": e.get("href"),
        "raw_href": e.get("raw_href"),
        "fragment": e.get("fragment"),
        "region": e.get("region"),
        "selectors": e.get("selectors", {}),
    }
    if e.get("assert"):
        out["assert"] = e["assert"]
    return out


@dataclass
class Contract:
    raw: dict
    path: Path

    @property
    def version(self) -> str:
        return self.raw.get("contract_version", "")

    @property
    def app_name(self) -> str:
        return self.raw.get("application", {}).get("name", "app")

    @property
    def base_url(self) -> str:
        return self.raw.get("application", {}).get("base_url", "").rstrip("/")

    @property
    def route_index(self) -> list[dict]:
        return self.raw.get("route_index", [])

    @property
    def pages(self) -> list[dict]:
        return self.raw.get("pages", [])

    @property
    def home_navigation(self) -> list[dict]:
        return self.raw.get("home_navigation", [])

    @property
    def scraped_at(self) -> str:
        return self.raw.get("extraction_metadata", {}).get("scraped_at", "")

    def validate(self) -> None:
        if self.version not in SUPPORTED_CONTRACT_VERSIONS:
            raise ValueError(
                f"Unsupported contract_version {self.version!r}; "
                f"expected one of {sorted(SUPPORTED_CONTRACT_VERSIONS)!r}"
            )
        if not self.base_url:
            raise ValueError("Contract missing application.base_url")

    def get_page(self, page_id: str) -> Optional[dict]:
        for page in self.pages:
            if page.get("page_id") == page_id:
                return page
        return None

    def pages_for_module(self, module: str) -> list[dict]:
        types = MODULE_PAGE_TYPES.get(module, set())
        matched = [p for p in self.pages if p.get("page_type") in types]
        if module == "content":
            matched = [
                p
                for p in self.pages
                if p.get("page_type") in types
                or p.get("page_id") in {"privacypolicy", "help", "faq", "screenreaderaccess"}
            ]
        if module == "navigation":
            home = self.get_page("home")
            matched = [home] if home else []
            if not matched:
                matched = list(
                    {p["page_id"]: p for p in self.pages if p.get("page_type") == "nav"}.values()
                )
                sitemap = self.get_page("sitemap")
                if sitemap and sitemap not in matched:
                    matched.append(sitemap)
        if module == "auth":
            login_pages = [p for p in self.pages if p.get("page_type") == "login" or p.get("page_id") == "home"]
            matched = list({p["page_id"]: p for p in login_pages}.values())
        return matched

    def slice_for_module(self, module: str, max_elements: int = 30) -> dict:
        pages = self.pages_for_module(module)
        slim_pages = []
        for page in pages:
            elements = page.get("elements", [])[:max_elements]
            slim_pages.append({
                "page_id": page.get("page_id"),
                "path": page.get("path"),
                "url": page.get("url"),
                "title": page.get("title"),
                "description": page.get("description"),
                "page_type": page.get("page_type"),
                "test_priority": page.get("test_priority"),
                "is_protected": page.get("is_protected"),
                "elements": [_slim_element(e) for e in elements],
                "forms": page.get("forms", []),
            })
        result: dict[str, Any] = {
            "contract_version": self.version,
            "application": self.raw.get("application", {}),
            "module": module,
            "route_index": [
                r for r in self.route_index
                if any(r.get("page_id") == p.get("page_id") for p in slim_pages)
            ],
            "pages": slim_pages,
        }
        if module == "navigation" and self.home_navigation:
            result["home_navigation"] = self.home_navigation
        return result

    def trim_for_prompt(self, max_pages: int = 8, max_elements: int = 20) -> dict:
        slim = []
        for page in self.pages[:max_pages]:
            slim.append({
                "page_id": page.get("page_id"),
                "path": page.get("path"),
                "title": page.get("title"),
                "page_type": page.get("page_type"),
                "test_priority": page.get("test_priority"),
                "description": page.get("description"),
                "elements": page.get("elements", [])[:max_elements],
                "forms": page.get("forms", []),
            })
        result: dict[str, Any] = {
            "application": self.raw.get("application", {}),
            "route_index": self.route_index,
            "pages": slim,
        }
        if self.home_navigation:
            result["home_navigation"] = self.home_navigation
        return result

    def slice_for_case(self, case: dict, max_elements: int = 40) -> dict:
        """Contract slice with only elements referenced by a testcase case."""
        element_ids: set[str] = set()
        for ref in case.get("element_refs", []):
            if isinstance(ref, dict) and ref.get("element_id"):
                element_ids.add(str(ref["element_id"]))
        for link in case.get("nav_links", []):
            if isinstance(link, dict) and link.get("element_id"):
                element_ids.add(str(link["element_id"]))

        pages_by_id: dict[str, dict] = {}
        for page in self.pages:
            matched = [
                _slim_element(e)
                for e in page.get("elements", [])
                if e.get("element_id") in element_ids
            ][:max_elements]
            if matched:
                pages_by_id[page["page_id"]] = {
                    "page_id": page.get("page_id"),
                    "path": page.get("path"),
                    "url": page.get("url"),
                    "title": page.get("title"),
                    "page_type": page.get("page_type"),
                    "elements": matched,
                }

        home = self.get_page("home")
        if home and "home" not in pages_by_id and element_ids:
            home_els = [
                _slim_element(e)
                for e in home.get("elements", [])
                if e.get("element_id") in element_ids
            ][:max_elements]
            if home_els:
                pages_by_id["home"] = {
                    "page_id": home.get("page_id"),
                    "path": home.get("path"),
                    "url": home.get("url"),
                    "title": home.get("title"),
                    "page_type": home.get("page_type"),
                    "elements": home_els,
                }

        slim_pages = list(pages_by_id.values())[:8]
        result: dict[str, Any] = {
            "contract_version": self.version,
            "application": self.raw.get("application", {}),
            "pages": slim_pages,
        }
        if case.get("nav_links") and self.home_navigation:
            result["home_navigation"] = self.home_navigation
        return result


def load_contract(path: str | Path) -> Contract:
    contract_path = Path(path)
    with contract_path.open(encoding="utf-8") as f:
        data = json.load(f)
    contract = Contract(raw=data, path=contract_path)
    contract.validate()
    return contract


def page_id_to_pom_name(page_id: str) -> str:
    parts = page_id.replace("-", "_").split("_")
    name = "".join(p.capitalize() for p in parts if p)
    return f"{name or 'Home'}Page"
