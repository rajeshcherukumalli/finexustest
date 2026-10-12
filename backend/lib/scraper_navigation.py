"""Navigation discovery helpers: link scope, URL change detection, button route probing."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Literal
from urllib.parse import urlparse

if TYPE_CHECKING:
    from playwright.sync_api import Page

log = logging.getLogger(__name__)

BLOCKED_HOST_SUFFIXES = (
    "youtube.com",
    "youtu.be",
    "drive.google.com",
    "docs.google.com",
)

PROBE_BUTTON_DENYLIST = (
    "logout",
    "log out",
    "sign out",
    "signout",
    "delete",
    "remove",
    "submit",
    "cancel",
    "close",
    "dismiss",
    "pay",
    "purchase",
    "confirm payment",
)

UrlChangeKind = Literal["none", "hash_only", "pathname"]

LIVE_NAVIGATION_JS = """() => {
    const items = [];
    const probeCandidates = [];
    const seen = new Set();
    const seenProbe = new Set();

    const push = (item) => {
        const key = [item.tag, item.raw_href || '', item.text || '', item.aria_label || ''].join('|');
        if (seen.has(key)) return;
        seen.add(key);
        items.push(item);
    };

    const regionFor = (el) => {
        const nav = el.closest('header, footer, nav, [role="navigation"]');
        if (!nav) return 'content';
        const tag = nav.tagName.toLowerCase();
        return tag === 'nav' ? 'nav' : tag;
    };

    const isVisible = (el) => {
        if (!el || el.disabled) return false;
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return false;
        const style = window.getComputedStyle(el);
        return style.visibility !== 'hidden' && style.display !== 'none' && style.pointerEvents !== 'none';
    };

    const cssEscape = (value) => {
        if (typeof CSS !== 'undefined' && CSS.escape) return CSS.escape(value);
        return value.replace(/[^a-zA-Z0-9_-]/g, '\\\\$&');
    };

    const probeSelectorFor = (el) => {
        if (el.id) return `#${cssEscape(el.id)}`;
        const testId = el.getAttribute('data-testid');
        if (testId) return `[data-testid="${testId.replace(/"/g, '\\\\"')}"]`;
        const name = el.getAttribute('name');
        if (name) return `${el.tagName.toLowerCase()}[name="${name.replace(/"/g, '\\\\"')}"]`;
        const aria = el.getAttribute('aria-label');
        if (aria) return `[aria-label="${aria.replace(/"/g, '\\\\"')}"]`;
        const text = (el.innerText || el.value || '').trim().slice(0, 80);
        if (text) {
            const escaped = text.replace(/'/g, "\\\\'");
            return `${el.tagName.toLowerCase()}:has-text('${escaped}')`;
        }
        return null;
    };

    const inSubmitForm = (el) => !!el.closest('form');

    document.querySelectorAll('a[href], area[href], [role="link"][href]').forEach((el) => {
        if (!isVisible(el)) return;
        const raw = el.getAttribute('href') || '';
        push({
            tag: el.tagName.toLowerCase(),
            raw_href: raw,
            resolved_href: el.href || raw,
            text: (el.innerText || '').trim().slice(0, 120),
            aria_label: el.getAttribute('aria-label'),
            opens_new_tab: el.target === '_blank' || (el.getAttribute('rel') || '').includes('noopener'),
            region: regionFor(el),
        });
    });

    const buttonSelectors = 'button, input[type="button"], [role="button"], [role="menuitem"]';
    document.querySelectorAll(buttonSelectors).forEach((el) => {
        if (!isVisible(el)) return;
        const tag = el.tagName.toLowerCase();
        const inputType = (el.getAttribute('type') || '').toLowerCase();
        if (inputType === 'submit' || inputType === 'hidden') return;
        if (inSubmitForm(el) && (tag === 'button' || inputType === 'submit')) return;

        const raw = el.getAttribute('href') || el.dataset?.href || '';
        const text = (el.innerText || el.getAttribute('aria-label') || el.value || '').trim().slice(0, 120);
        if (!text && !raw) return;

        const item = {
            tag: tag === 'input' ? 'button' : tag,
            raw_href: raw,
            resolved_href: raw ? new URL(raw, window.location.href).href : '',
            text,
            aria_label: el.getAttribute('aria-label'),
            opens_new_tab: el.target === '_blank',
            region: regionFor(el),
        };
        push(item);

        if (!raw) {
            const selector = probeSelectorFor(el);
            if (!selector) return;
            const probeKey = selector + '|' + text;
            if (seenProbe.has(probeKey)) return;
            seenProbe.add(probeKey);
            probeCandidates.push({
                selector,
                text,
                aria_label: el.getAttribute('aria-label'),
                tag: item.tag,
                region: item.region,
                in_form: inSubmitForm(el),
            });
        }
    });

    return { items, probeCandidates };
}"""


def is_blocked_host(netloc: str) -> bool:
    host = (netloc or "").lower().split(":")[0]
    if not host:
        return False
    for suffix in BLOCKED_HOST_SUFFIXES:
        if host == suffix or host.endswith(f".{suffix}"):
            return True
    return False


def is_in_crawl_scope(resolved_url: str, base_domain: str, is_static_asset: Callable[[str], bool]) -> bool:
    if not resolved_url:
        return False
    parsed = urlparse(resolved_url)
    netloc = parsed.netloc or base_domain
    if netloc != base_domain:
        return False
    if is_blocked_host(netloc):
        return False
    if is_static_asset(resolved_url):
        return False
    lower = resolved_url.lower().strip()
    if lower.startswith(("mailto:", "tel:", "javascript:")):
        return False
    return True


def url_change_kind(before: str, after: str) -> UrlChangeKind:
    b = urlparse(before)
    a = urlparse(after)
    b_path = (b.path or "/").rstrip("/") or "/"
    a_path = (a.path or "/").rstrip("/") or "/"

    if b._replace(fragment="", query="").geturl() == a._replace(fragment="", query="").geturl():
        if b.fragment == a.fragment:
            return "none"
        return "hash_only"

    if b.netloc == a.netloc and b_path == a_path and a.fragment != b.fragment:
        return "hash_only"

    if b.netloc != a.netloc or b_path != a_path:
        return "pathname"

    return "none"


def classify_link(raw_href: str, resolved_href: str, base_domain: str, is_static_asset: Callable[[str], bool]) -> tuple[str, bool]:
    """Return (category, crawlable)."""
    if not raw_href and not resolved_href:
        return "navigation_button", False

    href = raw_href or resolved_href
    lower = href.lower().strip()

    if lower.startswith("mailto:"):
        return "mailto", False
    if lower.startswith("tel:"):
        return "tel", False
    if lower.startswith("javascript:") or lower in ("#", ""):
        return "internal_hash", False

    parsed = urlparse(resolved_href or href)
    if parsed.netloc and parsed.netloc != base_domain:
        return "external", False

    if parsed.fragment and (not parsed.path or parsed.path in ("", "/")):
        return "internal_hash", False
    if "#" in href and not parsed.path:
        return "internal_hash", False

    if not is_in_crawl_scope(resolved_href or href, base_domain, is_static_asset):
        if is_static_asset(resolved_href or href):
            return "internal_path", False
        if is_blocked_host(parsed.netloc):
            return "external", False
        return "external", False

    return "internal_path", True


def is_safe_to_probe_button(candidate: dict) -> bool:
    if candidate.get("in_form"):
        return False
    haystack = " ".join(
        [
            str(candidate.get("text") or ""),
            str(candidate.get("aria_label") or ""),
        ]
    ).lower()
    return not any(term in haystack for term in PROBE_BUTTON_DENYLIST)


@dataclass
class ButtonProbeCandidate:
    selector: str
    text: str
    aria_label: str | None
    tag: str
    region: str
    in_form: bool = False


def extract_live_navigation(page: Page) -> tuple[list[dict], list[ButtonProbeCandidate]]:
    """Extract anchors/buttons and no-href button probe candidates from live DOM."""
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass

    try:
        raw = page.evaluate(LIVE_NAVIGATION_JS)
    except Exception as exc:
        log.warning("Live navigation extraction failed: %s", exc)
        return [], []

    candidates = [
        ButtonProbeCandidate(
            selector=item["selector"],
            text=item.get("text") or "",
            aria_label=item.get("aria_label"),
            tag=item.get("tag") or "button",
            region=item.get("region") or "unknown",
            in_form=bool(item.get("in_form")),
        )
        for item in raw.get("probeCandidates", [])
        if item.get("selector")
    ]
    return raw.get("items", []), candidates


def _recover_page_state(
    page: Page,
    original_url: str,
    *,
    navigation_timeout_ms: int,
) -> None:
    try:
        page.go_back(wait_until="domcontentloaded", timeout=navigation_timeout_ms)
    except Exception:
        try:
            page.goto(original_url, wait_until="domcontentloaded", timeout=navigation_timeout_ms)
        except Exception as exc:
            log.warning("Failed to recover page state after button probe: %s", exc)


def discover_button_routes(
    page: Page,
    page_url: str,
    *,
    base_domain: str,
    normalise_url: Callable[[str], str],
    is_static_asset: Callable[[str], bool],
    delay: float,
    probe_limit: int,
    navigation_timeout_ms: int,
) -> list[dict]:
    """Click no-href buttons and return discovered route link dicts."""
    _items, candidates = extract_live_navigation(page)
    del _items

    original_url = page.url
    discovered: list[dict] = []
    seen_hrefs: set[str] = set()
    probed = 0

    for candidate in candidates:
        if probed >= probe_limit:
            break
        if not is_safe_to_probe_button(
            {
                "text": candidate.text,
                "aria_label": candidate.aria_label,
                "in_form": candidate.in_form,
            }
        ):
            continue

        probed += 1
        log.info(
            "Button probe %d/%d: %r (%s)",
            probed,
            probe_limit,
            candidate.text or candidate.aria_label or candidate.selector,
            candidate.selector,
        )
        try:
            page.locator(candidate.selector).first.click(timeout=10_000)
            time.sleep(delay)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=navigation_timeout_ms)
            except Exception:
                pass

            change = url_change_kind(original_url, page.url)
            if change == "pathname":
                new_url = page.url
                if is_in_crawl_scope(new_url, base_domain, is_static_asset):
                    norm = normalise_url(new_url)
                    if norm not in seen_hrefs:
                        seen_hrefs.add(norm)
                        discovered.append(
                            {
                                "href": new_url,
                                "raw_href": new_url,
                                "text": candidate.text,
                                "tag": candidate.tag,
                                "category": "spa_route",
                                "crawlable": True,
                                "opens_new_tab": False,
                                "aria_label": candidate.aria_label,
                                "region": candidate.region,
                            }
                        )
            elif change == "hash_only":
                new_url = page.url
                key = f"hash|{new_url}|{candidate.text}"
                if key not in seen_hrefs:
                    seen_hrefs.add(key)
                    discovered.append(
                        {
                            "href": new_url,
                            "raw_href": urlparse(new_url).fragment or "",
                            "text": candidate.text,
                            "tag": candidate.tag,
                            "category": "internal_hash",
                            "crawlable": False,
                            "opens_new_tab": False,
                            "aria_label": candidate.aria_label,
                            "region": candidate.region,
                        }
                    )
        except Exception as exc:
            log.debug("Button probe skipped for %r: %s", candidate.text or candidate.selector, exc)
        finally:
            if page.url != original_url:
                _recover_page_state(page, original_url, navigation_timeout_ms=navigation_timeout_ms)
                time.sleep(delay / 2)

    return discovered
