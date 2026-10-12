"""Guarded dropdown/menu interaction pass for the website scraper."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from scraper import Clickable

log = logging.getLogger(__name__)

JS_EXTRACT_INTERACTIVE = r"""
() => {
  const cssEscape = (v) =>
    (window.CSS && CSS.escape) ? CSS.escape(v) : String(v).replace(/([^a-zA-Z0-9_-])/g, '\\$1');

  const cssPath = (el) => {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1) {
      const tag = node.tagName.toLowerCase();
      if (tag === 'html' || tag === 'body') { parts.unshift(tag); break; }
      if (node.id) { parts.unshift('#' + cssEscape(node.id)); break; }
      let part = tag;
      const parent = node.parentElement;
      if (parent) {
        const same = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
        if (same.length > 1) part += ':nth-of-type(' + (same.indexOf(node) + 1) + ')';
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(' > ');
  };

  const xPath = (el) => {
    const segs = [];
    let node = el;
    while (node && node.nodeType === 1) {
      const tag = node.tagName.toLowerCase();
      const parent = node.parentElement;
      if (!parent) { segs.unshift(tag); break; }
      const same = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
      segs.unshift(same.length > 1 ? tag + '[' + (same.indexOf(node) + 1) + ']' : tag);
      node = parent;
    }
    return '/' + segs.join('/');
  };

  const isVisible = (el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    const style = window.getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none';
  };

  const SELECTOR = [
    'a[href]', 'area[href]', 'button', 'input', 'select', 'textarea',
    '[role="button"]', '[role="link"]', '[role="combobox"]', '[role="menuitem"]',
    '[onclick]',
  ].join(', ');

  const elements = [];
  document.querySelectorAll(SELECTOR).forEach((el) => {
    const tag = el.tagName.toLowerCase();
    if (tag === 'input' && el.type === 'hidden') return;
    elements.push({
      tag,
      role_attr: el.getAttribute('role'),
      input_type: tag === 'input' ? (el.type || 'text') : null,
      text: String(el.innerText || el.value || '').trim().slice(0, 120),
      aria_label: el.getAttribute('aria-label'),
      name: el.getAttribute('name'),
      placeholder: el.getAttribute('placeholder'),
      visible: isVisible(el),
      aria_haspopup: el.getAttribute('aria-haspopup'),
      aria_expanded: el.getAttribute('aria-expanded'),
      aria_controls: el.getAttribute('aria-controls'),
      css: cssPath(el),
      xpath: xPath(el),
    });
  });
  return { elements };
}
"""


def extract_elements_live(page: Page, press_escape: bool = True) -> dict:
    if press_escape:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
    try:
        data = page.evaluate(JS_EXTRACT_INTERACTIVE)
    except Exception as exc:
        log.warning("Live element extraction failed: %s", exc)
        return {"elements": []}
    return {"elements": data.get("elements") or []}


def records_to_clickables(records: list[dict]) -> list[Clickable]:
    from scraper import Clickable

    clickables: list[Clickable] = []
    seen: set[str] = set()
    for record in records:
        xpath = record.get("xpath") or ""
        if not xpath or xpath in seen:
            continue
        seen.add(xpath)
        tag = record.get("tag") or "button"
        input_type = record.get("input_type")
        if tag == "a":
            ctype = "link"
        elif tag == "input":
            ctype = "input"
        elif tag == "select":
            ctype = "select"
        else:
            ctype = "button"
        text = (
            record.get("text")
            or record.get("aria_label")
            or record.get("placeholder")
            or record.get("name")
            or ""
        )[:100]
        clickables.append(
            Clickable(
                tag=tag,
                type=ctype,
                text=text,
                xpath=xpath,
                name=record.get("name"),
                placeholder=record.get("placeholder"),
                aria_label=record.get("aria_label"),
            )
        )
    return clickables


def interaction_pass(
    page: Page,
    *,
    normalise_url: Callable[[str], str],
    wait_for_page_ready: Callable[[Page], dict],
    max_expanders: int = 8,
) -> list[Clickable]:
    """Click menu expanders and return newly revealed controls as Clickables."""
    extraction = extract_elements_live(page)
    base_records = extraction.get("elements") or []

    def is_expander(record: dict) -> bool:
        if not record.get("visible"):
            return False
        if record.get("tag") in ("input", "select", "textarea"):
            return False
        if record.get("input_type") == "submit":
            return False
        return bool(
            (record.get("aria_haspopup") not in (None, "", "false"))
            or record.get("aria_expanded") == "false"
            or (record.get("role_attr") or "").lower() == "combobox"
            or (record.get("aria_controls") and record.get("tag") in ("button", "a"))
        )

    candidates = [record for record in base_records if is_expander(record)][:max_expanders]
    if not candidates:
        return []

    by_css = {record.get("css"): record for record in base_records if record.get("css")}
    url_before = normalise_url(page.url)
    revealed_records: list[dict] = []

    for candidate in candidates:
        css = candidate.get("css")
        if not css:
            continue
        try:
            page.locator(css).first.click(timeout=2000)
        except Exception:
            continue
        try:
            page.wait_for_timeout(400)
        except Exception:
            pass

        if normalise_url(page.url) != url_before:
            log.info("  Expander %r navigated — undoing and skipping", css)
            try:
                page.go_back(wait_until="domcontentloaded")
                wait_for_page_ready(page)
            except Exception:
                pass
            continue

        after = extract_elements_live(page, press_escape=False).get("elements") or []
        for record in after:
            record_css = record.get("css")
            if not record.get("visible") or not record_css:
                continue
            existing = by_css.get(record_css)
            if existing is None:
                record["revealed_by_css"] = css
                by_css[record_css] = record
                revealed_records.append(record)
            elif not existing.get("visible") and not existing.get("revealed_by_css"):
                existing["visible"] = True
                existing["revealed_by_css"] = css
                revealed_records.append(dict(existing))

        try:
            page.keyboard.press("Escape")
        except Exception:
            pass

    if revealed_records:
        log.info("  Interaction pass revealed %d hidden element(s)", len(revealed_records))
    return records_to_clickables(revealed_records)
