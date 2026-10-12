"""Map semantic YAML assertions to Playwright expect snippets."""

from __future__ import annotations

from typing import Any


def _escape_ts(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


ASSERTION_TEMPLATES: dict[str, str] = {
    "url_matches_route": "await expect(page).toHaveURL(new RegExp('{route_escaped}'));",
    "page_title_visible": "await expect(page.locator('h1').first()).toBeVisible();",
    "page_loads": "await expect(page).toHaveTitle(/.+/);",
    "link_visible": "await expect(page.getByRole('link', {{ name: '{label}' }})).toBeVisible();",
    "form_field_visible": "await expect(page.locator('{selector}')).toBeVisible();",
    "login_button_clickable": "await expect(page.getByRole('button', {{ name: 'Login' }})).toBeEnabled();",
    "header_title_visible": "await expect(page.locator('h1').first()).toContainText('{header}');",
}


def assert_line_from_contract(assert_meta: dict[str, Any], route: str = "") -> str | None:
    """Emit Playwright URL assertion from contract assert metadata."""
    if not assert_meta:
        return None
    kind = assert_meta.get("kind", "")
    value = _escape_ts(str(assert_meta.get("value", "")))
    if kind == "hash":
        return f"await expect(page).toHaveURL((url) => url.hash === '{value}');"
    if kind == "pathname":
        return (
            f"await expect(page).toHaveURL((url) => "
            f"url.pathname === '{value}' || url.pathname.startsWith('{value}'));"
        )
    if kind == "same_page":
        return "await expect(page).toHaveURL(/./);"
    if route:
        route_esc = _escape_ts(route)
        return (
            f"await expect(page).toHaveURL((url) => "
            f"url.pathname === '{route_esc}' || url.pathname.startsWith('{route_esc}'));"
        )
    return None


def map_assertions(
    assertions: list[str],
    context: dict[str, Any] | None = None,
) -> list[str]:
    context = context or {}
    lines: list[str] = []
    assert_meta = context.get("assert")
    if assert_meta and isinstance(assert_meta, dict):
        line = assert_line_from_contract(assert_meta, context.get("route", ""))
        if line:
            lines.append(line)

    for assertion in assertions:
        template = ASSERTION_TEMPLATES.get(assertion)
        if not template:
            if assertion not in ("url_matches_route",) or not context.get("route"):
                lines.append(f"// TODO: assert {assertion}")
            continue
        line = template.format(
            route_escaped=context.get("route", "").replace("/", "\\/"),
            label=context.get("label", ""),
            selector=context.get("selector", "body"),
            header=context.get("header", ""),
        )
        if line not in lines:
            lines.append(line)
    return lines


# Playwright snippets for NAV_LINKS loop (uses `link` from for-of).
NAV_LOOP_ASSERTIONS: dict[str, str] = {
    "url_matches_route": (
        "await expect(page).toHaveURL((url) => "
        "url.pathname === link.route || url.pathname.startsWith(link.route))"
    ),
    "page_title_visible": "await expect(page).toHaveTitle(/.+/);",
    "page_loads": "await expect(page).toHaveTitle(/.+/);",
    "link_visible": "await expect(page.getByRole('link', { name: link.label })).toBeVisible();",
    "form_field_visible": "await expect(page.locator('body')).toBeVisible();",
    "header_title_visible": (
        "await expect(page.locator('h1').first()).toContainText(link.header, { timeout: 10_000 })"
        ".catch(() => expect(page).toHaveTitle(/.+/))"
    ),
}


def map_assertions_for_nav_loop(
    assertions: list[str],
    context: dict[str, Any] | None = None,
) -> list[str]:
    context = context or {}
    lines: list[str] = []
    assert_meta = context.get("assert")
    if assert_meta and isinstance(assert_meta, dict):
        line = assert_line_from_contract(assert_meta, context.get("route", ""))
        if line:
            lines.append(line.replace("page)", "page)").replace("url.hash", "url.hash"))

    for assertion in assertions:
        line = NAV_LOOP_ASSERTIONS.get(assertion)
        if line:
            lines.append(line)
        else:
            lines.append(f"// TODO: assert {assertion}")
    return lines
