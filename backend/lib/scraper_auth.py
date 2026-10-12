"""Playwright auth execution for the website scraper."""

from __future__ import annotations

import logging
import re
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from lib.scraper_credentials import (
    FILLABLE_KEYS,
    available_fillable_keys,
    has_auth_credentials,
    navigation_timeout_ms,
)

if TYPE_CHECKING:
    from playwright.sync_api import Page

    from scraper import WebScraper

log = logging.getLogger(__name__)


def _wait_for_stable_page(page: Page) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=navigation_timeout_ms())
    except Exception as exc:
        log.debug("domcontentloaded wait: %s", exc)
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except Exception:
        pass


def _page_html(page: Page) -> str:
    """Read page HTML; retry when SPA navigation is still in flight."""
    last: Exception | None = None
    for attempt in range(4):
        try:
            _wait_for_stable_page(page)
            return page.content()
        except Exception as exc:
            last = exc
            if "navigating" not in str(exc).lower():
                raise
            time.sleep(0.75 * (attempt + 1))
    assert last is not None
    raise last


LOGIN_PATH_RE = re.compile(r"/(?:login|signin|sign-in|auth)(?:/|$)", re.IGNORECASE)
AUTH_FIELD_HINTS = (
    "otp",
    "mobile",
    "phone",
    "email",
    "username",
    "password",
    "userid",
    "user_id",
)

# Fuzzy label hints — matched only against controls discovered on the current page.
CREDENTIAL_AFFINITY: dict[str, tuple[tuple[str, int], ...]] = {
    "QA_PASSWORD": (("password", 10),),
    "QA_USERNAME": (("username", 9), ("email", 8), ("user id", 7), ("userid", 7), ("login id", 6)),
    "QA_TEST_MOBILE": (("mobile", 10), ("phone", 9), ("tel", 8), ("contact", 7), ("cell", 6)),
    "QA_TEST_OTP": (
        ("otp", 10),
        ("one-time", 9),
        ("one time", 9),
        ("verification", 8),
        ("verify code", 8),
        ("pin", 6),
        ("passcode", 6),
    ),
}
INTERMEDIATE_ACTION_HINTS = (
    "send",
    "request",
    "get",
    "resend",
    "generate",
    "continue",
    "next",
    "proceed",
)
# Step 1 after mobile entry — label varies by app (Bihar Krishi uses "Login", others "Send OTP")
OTP_REQUEST_HINTS = (
    "login",
    "log in",
    "sign in",
    "signin",
    "send",
    "request",
    "get",
    "continue",
    "next",
    "proceed",
) + INTERMEDIATE_ACTION_HINTS
OTP_VERIFY_HINTS = ("verify", "submit", "confirm", "enter")
SPLIT_OTP_SELECTORS = (
    ".popup-module-main input.input-otp",
    "input.input-otp",
    "input.grm-otp-input-box",
    "input[aria-label*='OTP character']",
    "input[aria-label*='otp character']",
    "input[autocomplete='one-time-code']",
)
MODAL_OTP_VERIFY_SELECTORS = (
    ".popup-module-main button[type='submit']",
    ".popup-module-action-bar button[type='submit']",
    "button[form='modal-action']",
    ".popup-module-main button:has-text('Verify')",
)
LOGIN_REQUEST_SELECTORS = (
    "button[type='submit'][id*='login']",
    "button[type='submit'][id*='sign-in']",
    "button[type='submit'][id*='signin']",
    "#submitButton",
    "button[type='submit']",
)
# App landing page that only exposes "Sign in" before redirecting to IdP (e.g. Keycloak)
SSO_GATEWAY_HINTS = (
    "sign in",
    "signin",
    "log in",
    "login",
    "continue",
    "sso",
)
SUBMIT_ACTION_HINTS = ("login", "sign in", "signin", "verify", "submit", "enter", "confirm")
PRIORITY_SUBMIT_SELECTORS = (
    "#submitButton",
    "button[type='submit']",
    "input[type='submit']",
)
GENERIC_AUTH_SELECTORS = frozenset({"button", "a", "input", "form", "div", "span"})


def is_usable_auth_selector(selector: str) -> bool:
    """Reject bare tag selectors that match hidden chrome before the real submit button."""
    normalized = (selector or "").strip().lower()
    if not normalized or normalized in GENERIC_AUTH_SELECTORS:
        return False
    return True


def is_login_path(url: str) -> bool:
    return bool(LOGIN_PATH_RE.search(urlparse(url).path or ""))


def forms_have_auth_fields(forms: list[dict]) -> bool:
    for form in forms:
        for field in form.get("fields", []):
            field_type = (field.get("type") or "").lower()
            if field_type == "password":
                return True
            haystack = _label_haystack(field)
            if any(hint in haystack for hint in AUTH_FIELD_HINTS):
                return True
    return False


def is_login_gate(url: str, page_type: str, forms: list[dict]) -> bool:
    if page_type == "login":
        return True
    if is_login_path(url):
        return True
    return forms_have_auth_fields(forms)


def is_mobile_otp_credentials(credentials: dict[str, str]) -> bool:
    keys = set(available_fillable_keys(credentials))
    return "QA_TEST_MOBILE" in keys and "QA_TEST_OTP" in keys


def detect_split_otp_selector(page: Page) -> str | None:
    """Return a selector when split OTP boxes appear (inline or in a modal)."""
    for selector in SPLIT_OTP_SELECTORS:
        try:
            if page.locator(selector).count() >= 4:
                return selector
        except Exception:
            continue
    return None


def _otp_modal_is_open(page: Page) -> bool:
    try:
        return detect_split_otp_selector(page) is not None
    except Exception:
        return False


def wait_for_split_otp_inputs(page: Page, timeout_ms: int = 25_000) -> str | None:
    """Poll until split OTP boxes appear (same page or modal popup)."""
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        selector = detect_split_otp_selector(page)
        if selector:
            log.info("OTP inputs ready (%s)", selector)
            return selector
        time.sleep(0.5)
    return None


def fill_split_otp_boxes(page: Page, otp: str, selector: str) -> bool:
    """Fill one digit per OTP box (inline or modal — e.g. Bihar Krishi, Dristi Kerala)."""
    digits = [ch for ch in (otp or "").strip() if ch.isdigit()]
    if not digits:
        return False
    boxes = page.locator(selector)
    count = boxes.count()
    if count == 0:
        return False
    for index, digit in enumerate(digits[:count]):
        box = boxes.nth(index)
        box.fill(digit)
        try:
            box.dispatch_event("input")
            box.dispatch_event("change")
        except Exception:
            pass
    time.sleep(0.3)
    return True


def mobile_otp_login_succeeded(page: Page) -> bool:
    """True when the OTP modal closed and the mobile login form is no longer visible."""
    if _otp_modal_is_open(page):
        return False
    try:
        mobile = page.locator("[name='mobileNumber'], #user_mobile").first
        if mobile.count() > 0 and mobile.is_visible():
            return False
    except Exception:
        pass
    return True


def auth_success_after_flow(
    page_url: str,
    page_type: str,
    *,
    forms: list[dict] | None = None,
) -> bool:
    """True when URL or post-login DOM no longer looks like a login gate."""
    if not is_login_path(page_url) and page_type != "login":
        return True
    if forms is not None and not is_login_gate(page_url, page_type, forms):
        return True
    return False


def auth_success(page_url: str, page_type: str) -> bool:
    return auth_success_after_flow(page_url, page_type)


def _label_haystack(item: dict) -> str:
    return " ".join(
        str(item.get(key) or "")
        for key in ("label", "name", "placeholder", "aria_label", "field_id", "text")
    ).lower()


def _selector_from_playwright(pw: str) -> str | None:
    if not pw:
        return None
    text = pw.strip()
    for prefix in ("page.locator(", "page.getByRole(", "page.getByLabel(", "page.getByPlaceholder("):
        if text.startswith(prefix):
            inner = text[len(prefix) :].rstrip(")").strip()
            if inner.startswith(("'", '"')):
                quote = inner[0]
                end = inner.index(quote, 1)
                return inner[1:end]
            return inner
    if text.startswith("page."):
        return None
    return text


def normalize_auth_selector(selector: str) -> str:
    """Strip page.locator(...) wrappers from LLM output; return CSS-ready selector."""
    raw = (selector or "").strip()
    if not raw:
        return raw
    normalized = _selector_from_playwright(raw)
    return normalized if normalized is not None else raw


def _selector_for_control(item: dict) -> str | None:
    selectors = item.get("selectors") or {}
    selector = _selector_from_playwright(selectors.get("playwright") or "")
    if selector and is_usable_auth_selector(selector):
        return selector
    name = item.get("name")
    if name:
        return f"[name='{name}']"
    field_id = item.get("field_id")
    if field_id:
        return f"#{field_id}"
    return None


def _score_field_for_credential(field: dict, credential_key: str) -> int:
    haystack = _label_haystack(field)
    field_type = (field.get("type") or "").lower()
    score = 0
    if credential_key == "QA_PASSWORD" and field_type == "password":
        score = max(score, 12)
    if credential_key == "QA_TEST_MOBILE" and field_type in ("tel", "number"):
        score = max(score, 11)
    for hint, weight in CREDENTIAL_AFFINITY.get(credential_key, ()):
        if hint in haystack:
            score = max(score, weight)
    return score


def _collect_fields(forms: list[dict]) -> list[dict]:
    fields: list[dict] = []
    for form in forms:
        fields.extend(form.get("fields", []))
    return fields


def _match_credentials_to_fields(
    fields: list[dict],
    available_keys: list[str],
) -> list[tuple[dict, str]]:
    """Map discovered fields to env credential keys in DOM order."""
    pairs: list[tuple[dict, str]] = []
    used_keys: set[str] = set()
    for field in fields:
        best_key: str | None = None
        best_score = 0
        for key in available_keys:
            if key in used_keys:
                continue
            score = _score_field_for_credential(field, key)
            if score > best_score:
                best_score = score
                best_key = key
        if best_key and best_score > 0 and _selector_for_control(field):
            pairs.append((field, best_key))
            used_keys.add(best_key)
    return pairs


def _button_selector_from_element(element: dict) -> str | None:
    selectors = element.get("selectors") or {}
    selector = _selector_from_playwright(selectors.get("playwright") or "")
    if selector and not selector.startswith("page.") and is_usable_auth_selector(selector):
        return selector
    field_id = element.get("field_id")
    if field_id:
        return f"#{field_id}"
    name = element.get("name")
    if name:
        return f"[name='{name}']"
    label = (element.get("label") or element.get("text") or "").strip()
    if not label:
        return None
    escaped = label.replace("'", "\\'")
    tag = element.get("tag") or "button"
    if tag == "a":
        return f"a:has-text('{escaped}')"
    return f"button:has-text('{escaped}'), input[type='submit']:has-text('{escaped}')"


def _first_actionable_selector(page: Page, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible() and locator.is_enabled():
                return selector
        except Exception:
            continue
    return None


def _selector_is_actionable(page: Page, selector: str) -> bool:
    try:
        locator = page.locator(selector).first
        return locator.count() > 0 and locator.is_visible() and locator.is_enabled()
    except Exception:
        return False


def _dismiss_blocking_overlays(page: Page) -> None:
    """Close cookie/consent popups — never dismiss the OTP entry modal."""
    if _otp_modal_is_open(page):
        return
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass
    for selector in (
        "button:has-text('Close')",
        "button:has-text('Got it')",
        "button:has-text('OK')",
        "[aria-label='Close']",
    ):
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible():
                locator.click(timeout=2_000)
                time.sleep(0.3)
                return
        except Exception:
            continue


def _wait_for_actionable(page: Page, selector: str, timeout_ms: int = 15_000) -> bool:
    deadline = time.monotonic() + timeout_ms / 1000.0
    while time.monotonic() < deadline:
        if _selector_is_actionable(page, selector):
            return True
        time.sleep(0.25)
    return False


def _fill_auth_field(page: Page, selector: str, value: str) -> None:
    field = page.locator(selector).first
    field.fill(value)
    try:
        field.dispatch_event("input")
        field.dispatch_event("change")
        field.press("Tab")
    except Exception:
        pass
    time.sleep(0.3)


def _click_auth_selector(page: Page, selector: str) -> None:
    if not _wait_for_actionable(page, selector):
        if not _otp_modal_is_open(page):
            _dismiss_blocking_overlays(page)
        _wait_for_actionable(page, selector, timeout_ms=5_000)
    locator = page.locator(selector).first
    try:
        locator.click(timeout=navigation_timeout_ms())
    except Exception:
        if not _otp_modal_is_open(page):
            _dismiss_blocking_overlays(page)
        locator.click(timeout=navigation_timeout_ms(), force=True)


def _score_button_element(element: dict, hints: tuple[str, ...]) -> int:
    haystack = _label_haystack(element)
    score = 0
    for hint in hints:
        if hint in haystack:
            score = max(score, 10)
    field_id = (element.get("field_id") or "").strip()
    field_id_lower = field_id.lower()
    if field_id == "submitButton":
        score += 25
    elif field_id and any(token in field_id_lower for token in ("login", "sign-in", "signin", "submit")):
        score += 18
    elif field_id:
        score += 8
    if (element.get("input_type") or "").lower() == "submit":
        score += 15
    label = (element.get("label") or element.get("text") or "").strip()
    if label.lower() in {hint for hint in hints if len(hint) > 2}:
        score += 12
    return score


def _find_button_by_hints(
    elements: list[dict],
    hints: tuple[str, ...],
    *,
    page: Page | None = None,
    require_actionable: bool = True,
) -> str | None:
    ranked: list[tuple[int, str]] = []
    for element in elements:
        if element.get("role") not in ("button", "link", None) and element.get("tag") not in (
            "button",
            "input",
            "a",
        ):
            continue
        score = _score_button_element(element, hints)
        if score <= 0:
            continue
        selector = _button_selector_from_element(element)
        if not selector or not is_usable_auth_selector(selector):
            continue
        ranked.append((score, selector))

    ranked.sort(key=lambda item: item[0], reverse=True)
    if page is not None and require_actionable:
        for _score, selector in ranked:
            if _selector_is_actionable(page, selector):
                return selector
        for hint in hints:
            if len(hint) < 3:
                continue
            try:
                pattern = hint.replace("'", "\\'")
                candidate = f"button:visible:has-text('{pattern}')"
                locator = page.locator(candidate).first
                if locator.count() > 0 and locator.is_visible() and locator.is_enabled():
                    return candidate
            except Exception:
                continue
        actionable = _first_actionable_selector(page, PRIORITY_SUBMIT_SELECTORS)
        if actionable:
            return actionable

    return ranked[0][1] if ranked else None


def _first_visible_selector(page: Page, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible():
                return selector
        except Exception:
            continue
    return None


def _find_login_request_selector(page: Page | None, elements: list[dict]) -> str | None:
    """Mobile OTP step 1 submit — may be disabled until the mobile field is filled."""
    selector = _find_button_by_hints(
        elements,
        OTP_REQUEST_HINTS,
        page=page,
        require_actionable=False,
    )
    if selector:
        return selector
    if page is not None:
        return _first_visible_selector(page, LOGIN_REQUEST_SELECTORS)
    return None


def _find_modal_otp_verify_selector(page: Page) -> str | None:
    """Verify button inside OTP modal (e.g. Dristi Kerala popup-module-main)."""
    for selector in MODAL_OTP_VERIFY_SELECTORS:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0 and locator.is_visible():
                return selector
        except Exception:
            continue
    return None


def extract_live_auth_controls(page: Page) -> tuple[list[dict], list[dict]]:
    """Read inputs and buttons from the live DOM (SPA-friendly, app-agnostic)."""
    try:
        raw = page.evaluate(
            """() => {
        const fields = [];
        for (const el of document.querySelectorAll('input, textarea, select')) {
            const type = (el.type || 'text').toLowerCase();
            if (type === 'hidden' || type === 'submit' || type === 'button') continue;
            fields.push({
                type,
                name: el.name || '',
                field_id: el.id || '',
                label: (el.labels && el.labels[0] ? el.labels[0].innerText : '') || el.getAttribute('aria-label') || '',
                placeholder: el.placeholder || '',
            });
        }
        const buttons = [];
        const pushButton = (el) => {
            const text = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim();
            if (!text) return;
            buttons.push({
                tag: el.tagName.toLowerCase(),
                role: 'button',
                label: text.slice(0, 120),
                name: el.name || '',
                field_id: el.id || '',
                input_type: (el.type || '').toLowerCase(),
            });
        };
        document.querySelectorAll('button, input[type=submit], input[type=button]').forEach(pushButton);
        document.querySelectorAll('a[role=button]').forEach(pushButton);
        return { fields, buttons };
    }"""
        )
    except Exception as exc:
        log.debug("Live auth control extraction failed: %s", exc)
        return [], []
    if not isinstance(raw, dict):
        return [], []
    live_forms = [{"fields": raw.get("fields", [])}] if raw.get("fields") else []
    live_elements = raw.get("buttons", []) or []
    if not isinstance(live_elements, list):
        live_elements = []
    return live_forms, live_elements


def fallback_auth_plan(
    forms: list[dict],
    elements: list[dict],
    credentials: dict[str, str],
    *,
    page: Page | None = None,
) -> dict[str, Any]:
    """Build auth steps only from controls discovered on the page (static HTML + live DOM)."""
    available_keys = available_fillable_keys(credentials)
    if not available_keys:
        return {"flow_type": "unknown", "steps": [], "success_hint": "url_path_not_login"}

    merged_forms = list(forms)
    merged_elements = list(elements)
    if page is not None:
        live_forms, live_elements = extract_live_auth_controls(page)
        merged_forms.extend(live_forms)
        merged_elements.extend(live_elements)

    field_pairs = _match_credentials_to_fields(_collect_fields(merged_forms), available_keys)
    if not field_pairs:
        return {"flow_type": "unknown", "steps": [], "success_hint": "url_path_not_login"}

    steps: list[dict[str, Any]] = []
    is_otp_flow = {"QA_TEST_MOBILE", "QA_TEST_OTP"} <= set(available_keys)

    if is_otp_flow:
        mobile_pairs = [(field, key) for field, key in field_pairs if key == "QA_TEST_MOBILE"]
        if not mobile_pairs:
            return {"flow_type": "otp", "steps": [], "success_hint": "url_path_not_login"}
        field, credential_key = mobile_pairs[0]
        selector = _selector_for_control(field)
        if selector:
            steps.append(
                {"action": "fill", "selector": selector, "credential_key": credential_key}
            )
        request_selector = _find_login_request_selector(page, merged_elements)
        if request_selector:
            steps.append({"action": "click", "selector": request_selector})
        steps.append({"wait_ms": 2500})
        return {
            "flow_type": "otp",
            "steps": steps,
            "success_hint": "otp_inputs_visible",
        }

    keys_in_order = [key for _field, key in field_pairs]
    needs_intermediate_action = (
        "QA_TEST_MOBILE" in keys_in_order and "QA_TEST_OTP" in keys_in_order
    )

    for index, (field, credential_key) in enumerate(field_pairs):
        if (
            needs_intermediate_action
            and credential_key == "QA_TEST_OTP"
            and "QA_TEST_MOBILE" in keys_in_order[:index]
        ):
            intermediate = _find_button_by_hints(
                merged_elements, INTERMEDIATE_ACTION_HINTS, page=page
            )
            if intermediate:
                steps.append({"action": "click", "selector": intermediate})
                steps.append({"wait_ms": 2000})

        selector = _selector_for_control(field)
        if selector:
            steps.append(
                {"action": "fill", "selector": selector, "credential_key": credential_key}
            )

    submit_selector = _find_button_by_hints(
        merged_elements, SUBMIT_ACTION_HINTS, page=page
    )
    if submit_selector:
        steps.append({"action": "click", "selector": submit_selector})

    flow_type = (
        "otp"
        if {"QA_TEST_MOBILE", "QA_TEST_OTP"} <= set(available_keys)
        else "password"
        if {"QA_USERNAME", "QA_PASSWORD"} <= set(available_keys)
        else "mixed"
    )
    return {
        "flow_type": flow_type,
        "steps": steps,
        "success_hint": "url_path_not_login_or_dashboard",
    }


def build_mobile_otp_phase2_plan(
    page: Page,
    otp_selector: str,
    elements: list[dict],
) -> dict[str, Any]:
    """Phase 2: fill split OTP boxes (or single field) and click Verify."""
    steps: list[dict[str, Any]] = [
        {
            "action": "fill_split_otp",
            "selector": otp_selector,
            "credential_key": "QA_TEST_OTP",
        }
    ]
    live_elements: list[dict] = []
    try:
        _live_forms, live_elements = extract_live_auth_controls(page)
    except Exception:
        pass
    merged_elements = list(elements) + live_elements
    verify_selector = _find_modal_otp_verify_selector(page)
    if not verify_selector:
        verify_selector = _find_button_by_hints(
            merged_elements,
            OTP_VERIFY_HINTS,
            page=page,
            require_actionable=False,
        )
    if verify_selector:
        steps.append({"action": "click", "selector": verify_selector})
    return {"flow_type": "otp", "steps": steps, "success_hint": "url_path_not_login_or_dashboard"}


def build_mobile_otp_phase2_single_field_plan(
    forms: list[dict],
    elements: list[dict],
    credentials: dict[str, str],
    *,
    page: Page | None = None,
) -> dict[str, Any]:
    """Phase 2 fallback when OTP is one input instead of split boxes."""
    available_keys = ["QA_TEST_OTP"]
    merged_forms = list(forms)
    merged_elements = list(elements)
    if page is not None:
        live_forms, live_elements = extract_live_auth_controls(page)
        merged_forms.extend(live_forms)
        merged_elements.extend(live_elements)
    otp_pairs = [
        pair
        for pair in _match_credentials_to_fields(_collect_fields(merged_forms), available_keys)
        if pair[1] == "QA_TEST_OTP"
    ]
    steps: list[dict[str, Any]] = []
    if otp_pairs:
        field, _key = otp_pairs[0]
        selector = _selector_for_control(field)
        if selector:
            steps.append(
                {"action": "fill", "selector": selector, "credential_key": "QA_TEST_OTP"}
            )
    verify_selector = _find_modal_otp_verify_selector(page) if page is not None else None
    if not verify_selector:
        verify_selector = _find_button_by_hints(
            merged_elements,
            OTP_VERIFY_HINTS,
            page=page,
            require_actionable=False,
        )
    if verify_selector:
        steps.append({"action": "click", "selector": verify_selector})
    return {"flow_type": "otp", "steps": steps, "success_hint": "url_path_not_login_or_dashboard"}


def detect_sso_gateway_selector(
    forms: list[dict],
    elements: list[dict],
    credentials: dict[str, str],
    *,
    page: Page | None = None,
) -> str | None:
    """
    Return a Sign-in button selector when the page has a gateway entry point but no
    fillable credential fields yet (typical app shell → Keycloak / OIDC redirect).
    """
    available_keys = available_fillable_keys(credentials)
    if not available_keys:
        return None

    merged_forms = list(forms)
    merged_elements = list(elements)
    if page is not None:
        live_forms, live_elements = extract_live_auth_controls(page)
        merged_forms.extend(live_forms)
        merged_elements.extend(live_elements)

    if _match_credentials_to_fields(_collect_fields(merged_forms), available_keys):
        return None

    return _find_button_by_hints(merged_elements, SSO_GATEWAY_HINTS)


def execute_sso_gateway_click(page: Page, selector: str) -> None:
    """Click through app 'Sign in' and wait for IdP (e.g. Keycloak) to load."""
    log.info("SSO gateway: clicking %s", selector)
    try:
        with page.expect_navigation(timeout=navigation_timeout_ms()):
            page.locator(selector).first.click()
    except Exception:
        page.locator(selector).first.click()
        time.sleep(2.0)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=navigation_timeout_ms())
    except Exception as exc:
        log.warning("SSO gateway navigation wait: %s", exc)
    time.sleep(0.5)


def sanitize_auth_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return auth steps safe to log or save (no credential values)."""
    safe: list[dict[str, Any]] = []
    for step in steps or []:
        if step.get("wait_ms") is not None:
            safe.append({"wait_ms": step["wait_ms"]})
            continue
        entry: dict[str, Any] = {"action": step.get("action")}
        if step.get("selector"):
            entry["selector"] = step["selector"]
        if step.get("credential_key"):
            entry["credential_key"] = step["credential_key"]
        safe.append(entry)
    return safe


def _execute_mobile_otp_phased_flow(
    scraper: WebScraper,
    page: Page,
    ctx: dict[str, Any],
    credentials: dict[str, str],
    meta: dict[str, Any],
) -> bool:
    """Mobile → request OTP (same page) → split/single OTP → Verify."""
    phase1 = fallback_auth_plan(
        ctx["forms"],
        ctx["elements"],
        credentials,
        page=page,
    )
    meta["phases"].append(
        {
            "phase": "mobile_request",
            "plan_source": "fallback",
            "flow_type": "otp",
            "steps": sanitize_auth_steps(phase1.get("steps") or []),
        }
    )
    if not phase1.get("steps"):
        meta["error"] = "no_mobile_otp_phase1_plan"
        return False
    if not execute_auth_plan(page, phase1, credentials):
        meta["error"] = "mobile_otp_phase1_failed"
        return False

    otp_selector = wait_for_split_otp_inputs(page)
    if otp_selector:
        log.info("Split OTP inputs detected (%s)", otp_selector)
        phase2 = build_mobile_otp_phase2_plan(page, otp_selector, ctx["elements"])
        meta["phases"].append(
            {
                "phase": "otp_verify",
                "plan_source": "fallback",
                "flow_type": "otp",
                "otp_selector": otp_selector,
                "steps": sanitize_auth_steps(phase2.get("steps") or []),
            }
        )
    else:
        log.info("No split OTP boxes — planning single OTP field")
        ctx2 = _extract_auth_context_from_page(scraper, page, page.url)
        phase2 = build_mobile_otp_phase2_single_field_plan(
            ctx2["forms"],
            ctx2["elements"],
            credentials,
            page=page,
        )
        meta["phases"].append(
            {
                "phase": "otp_verify",
                "plan_source": "fallback",
                "flow_type": "otp",
                "steps": sanitize_auth_steps(phase2.get("steps") or []),
            }
        )

    if not phase2.get("steps"):
        meta["error"] = "no_mobile_otp_phase2_plan"
        return False
    return execute_auth_plan(page, phase2, credentials)


def plan_authentication(
    scraper: WebScraper,
    page: Page,
    *,
    url: str,
    title: str,
    page_text: str,
    forms: list[dict],
    elements: list[dict],
) -> tuple[dict[str, Any], str]:
    """Build login steps from LLM or page-derived fallback. Returns (plan, source)."""
    available_keys = available_fillable_keys(scraper.credentials)
    if not available_keys:
        return {"flow_type": "unknown", "steps": []}, "none"

    log.info("Planning authentication for %s (keys: %s)", url, ", ".join(available_keys))
    plan = scraper.llm.plan_auth_steps(
        url=url,
        title=title,
        page_text=page_text,
        forms=forms,
        elements=elements,
        available_keys=available_keys,
    )
    source = "llm"
    if not plan.get("steps"):
        plan = fallback_auth_plan(
            forms,
            elements,
            scraper.credentials,
            page=page,
        )
        source = "fallback" if plan.get("steps") else "none"
        if plan.get("steps"):
            log.info(
                "Using page-derived fallback auth plan (%d steps, flow=%s)",
                len(plan["steps"]),
                plan.get("flow_type", "unknown"),
            )
    for step in plan.get("steps") or []:
        if step.get("selector"):
            step["selector"] = normalize_auth_selector(step["selector"])
    return plan, source


def execute_auth_plan(page: Page, plan: dict[str, Any], credentials: dict[str, str]) -> bool:
    steps = plan.get("steps") or []
    if not steps:
        return False

    for step in steps:
        if step.get("wait_ms"):
            time.sleep(max(0, int(step["wait_ms"])) / 1000.0)
            continue

        action = step.get("action")
        selector = normalize_auth_selector(step.get("selector") or "")
        if not selector:
            log.warning("Auth step missing selector: %s", step)
            return False

        if action == "fill":
            key = step.get("credential_key")
            if key not in FILLABLE_KEYS:
                log.warning("Auth fill step has invalid credential_key: %s", key)
                return False
            value = credentials.get(key or "")
            if not value:
                log.warning("Missing credential value for %s", key)
                return False
            _fill_auth_field(page, selector, value)
        elif action == "fill_split_otp":
            key = step.get("credential_key", "QA_TEST_OTP")
            if key not in FILLABLE_KEYS:
                log.warning("Auth split OTP step has invalid credential_key: %s", key)
                return False
            value = credentials.get(key or "")
            if not value:
                log.warning("Missing credential value for %s", key)
                return False
            if not fill_split_otp_boxes(page, value, selector):
                log.warning("Failed to fill split OTP boxes with %s", selector)
                return False
        elif action == "click":
            _click_auth_selector(page, selector)
            time.sleep(0.5)
        else:
            log.warning("Unknown auth step action: %s", action)
            return False

    try:
        page.wait_for_load_state("domcontentloaded", timeout=navigation_timeout_ms())
    except Exception as exc:
        log.warning("Auth wait after steps failed: %s", exc)
    return True


def authenticate_page(
    scraper: WebScraper,
    page: Page,
    *,
    url: str,
    title: str,
    page_text: str,
    analysis: dict[str, Any],
    forms: list[dict],
    elements: list[dict],
) -> bool:
    if scraper.authenticated:
        return True
    if scraper._auth_attempted:
        return False
    if not has_auth_credentials(scraper.credentials):
        return False

    scraper._auth_attempted = True
    success, _meta = _run_authentication_flow(scraper, page, page.url or url)
    if success:
        scraper.authenticated = True
        log.info("Authentication succeeded at %s", page.url)
    return success


def _extract_auth_context_from_page(scraper: WebScraper, page: Page, url: str) -> dict[str, Any]:
    """Parse the current page DOM for auth planning (no navigation)."""
    from scraper import (
        build_contract_forms,
        build_unified_elements,
        extract_clickables,
        extract_links_from_page,
    )
    from bs4 import BeautifulSoup

    html = _page_html(page)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title else url
    page_text = soup.get_text(separator=" ", strip=True)
    page_links = extract_links_from_page(page, url, scraper.base_domain)
    clickables, raw_forms = extract_clickables(soup, url)
    analysis = scraper.llm.analyze_page(url, title, page_text, clickables)
    elements = build_unified_elements(page_links, clickables, scraper.base_url)
    contract_forms = build_contract_forms(raw_forms, scraper.base_url)
    return {
        "url": url,
        "title": title,
        "page_text": page_text,
        "analysis": analysis,
        "forms": contract_forms,
        "elements": elements,
    }


def _run_authentication_flow(
    scraper: WebScraper,
    page: Page,
    url: str,
) -> tuple[bool, dict[str, Any]]:
    """
    Plan and execute login, including SSO gateway → IdP (Keycloak) when the app
    landing page only shows a Sign-in button before the real login form.
    """
    meta: dict[str, Any] = {
        "sso_gateway": False,
        "plan_source": "none",
        "flow_type": "unknown",
        "steps": [],
        "phases": [],
    }

    ctx = _extract_auth_context_from_page(scraper, page, url)
    gateway_selector = detect_sso_gateway_selector(
        ctx["forms"],
        ctx["elements"],
        scraper.credentials,
        page=page,
    )

    if gateway_selector:
        meta["sso_gateway"] = True
        execute_sso_gateway_click(page, gateway_selector)
        meta["phases"].append(
            {"phase": "sso_gateway", "selector": gateway_selector, "url_after": page.url}
        )
        ctx = _extract_auth_context_from_page(scraper, page, page.url)

    if is_mobile_otp_credentials(scraper.credentials) and not gateway_selector:
        meta["flow_type"] = "mobile_otp"
        meta["plan_source"] = "fallback"
        try:
            if not _execute_mobile_otp_phased_flow(
                scraper, page, ctx, scraper.credentials, meta
            ):
                meta["final_url"] = page.url
                if "error" not in meta:
                    meta["error"] = "mobile_otp_flow_failed"
                return False, meta
            meta["final_url"] = page.url
            post_ctx = _extract_auth_context_from_page(scraper, page, page.url)
            page_type = post_ctx["analysis"].get("page_type", "unknown")
            if auth_success_after_flow(
                page.url,
                page_type,
                forms=post_ctx["forms"],
            ) or mobile_otp_login_succeeded(page):
                return True, meta
            meta["error"] = (
                "otp_modal_still_open" if _otp_modal_is_open(page) else "still_on_login_like_page"
            )
            return False, meta
        except Exception as exc:
            meta["error"] = str(exc)
            meta["final_url"] = page.url
            log.warning("Mobile OTP authentication failed for %s: %s", url, exc)
            return False, meta

    plan, source = plan_authentication(
        scraper,
        page,
        url=ctx["url"],
        title=ctx["title"],
        page_text=ctx["page_text"],
        forms=ctx["forms"],
        elements=ctx["elements"],
    )
    meta["plan_source"] = source
    meta["flow_type"] = (
        "sso_keycloak" if meta["sso_gateway"] else plan.get("flow_type", "unknown")
    )
    meta["steps"] = sanitize_auth_steps(plan.get("steps") or [])
    meta["phases"].append(
        {
            "phase": "credentials",
            "plan_source": source,
            "flow_type": plan.get("flow_type"),
            "url": ctx["url"],
        }
    )

    if not plan.get("steps"):
        meta["error"] = "no_auth_plan"
        meta["final_url"] = page.url
        return False, meta

    try:
        if not execute_auth_plan(page, plan, scraper.credentials):
            meta["error"] = "execute_auth_plan_returned_false"
            meta["final_url"] = page.url
            return False, meta
        meta["final_url"] = page.url
        page_type = ctx["analysis"].get("page_type", "unknown")
        if not is_login_path(page.url):
            page_type = "unknown"
        if auth_success(page.url, page_type):
            return True, meta
        meta["error"] = "still_on_login_like_page"
        return False, meta
    except Exception as exc:
        meta["error"] = str(exc)
        meta["final_url"] = page.url
        log.warning("Authentication failed for %s: %s", url, exc)
        return False, meta


def _load_login_page_context(scraper: WebScraper, page: Page, url: str) -> dict[str, Any] | None:
    """Navigate to login URL and extract page context for auth planning."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=navigation_timeout_ms())
        _wait_for_stable_page(page)
        time.sleep(scraper.delay)
    except Exception as exc:
        log.warning("Failed to open auth URL %s: %s", url, exc)
        return None

    return _extract_auth_context_from_page(scraper, page, url)


def probe_authentication_at_url(scraper: WebScraper, page: Page, url: str) -> dict[str, Any]:
    """
    Run auth planning + execution only (no crawl). Returns a JSON-safe report.
    Use for fast iteration on login flows before a full scrape.
    """
    report: dict[str, Any] = {
        "login_url": url,
        "available_keys": available_fillable_keys(scraper.credentials),
        "plan_source": "none",
        "flow_type": "unknown",
        "steps": [],
        "success": False,
        "final_url": "",
        "error": None,
    }

    if not has_auth_credentials(scraper.credentials):
        report["error"] = "no_fillable_credentials_in_env"
        return report

    ctx = _load_login_page_context(scraper, page, url)
    if ctx is None:
        report["error"] = "failed_to_load_login_url"
        return report

    scraper._auth_attempted = True
    success, meta = _run_authentication_flow(scraper, page, url)
    report.update(meta)
    report["success"] = success
    if success:
        scraper.authenticated = True
        log.info("Auth probe succeeded at %s", page.url)
    return report


def authenticate_at_url(scraper: WebScraper, page: Page, url: str) -> bool:
    """Load a URL and run the auth planner/executor once."""
    if scraper.authenticated:
        return True

    ctx = _load_login_page_context(scraper, page, url)
    if ctx is None:
        return False

    return authenticate_page(
        scraper,
        page,
        url=ctx["url"],
        title=ctx["title"],
        page_text=ctx["page_text"],
        analysis=ctx["analysis"],
        forms=ctx["forms"],
        elements=ctx["elements"],
    )
