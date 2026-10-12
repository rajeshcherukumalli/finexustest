"""Tests for scraper env-backed authentication."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from lib.llm import parse_json_response
from lib.scraper_auth import (
    auth_success,
    build_mobile_otp_phase2_plan,
    detect_sso_gateway_selector,
    detect_split_otp_selector,
    execute_auth_plan,
    fallback_auth_plan,
    fill_split_otp_boxes,
    forms_have_auth_fields,
    is_login_gate,
    is_login_path,
    is_mobile_otp_credentials,
    is_usable_auth_selector,
    normalize_auth_selector,
    sanitize_auth_steps,
    _find_button_by_hints,
)
from lib.scraper_credentials import (
    available_fillable_keys,
    default_login_url,
    resolve_auth_url,
    has_auth_credentials,
    load_scraper_credentials,
    merge_legacy_cli_credentials,
)
from scraper import LLMAnalyzer


def test_load_scraper_credentials(monkeypatch):
    monkeypatch.setenv("QA_USERNAME", "user@example.com")
    monkeypatch.setenv("QA_PASSWORD", "secret")
    monkeypatch.delenv("QA_LOGIN_URL", raising=False)
    creds = load_scraper_credentials()
    assert creds["QA_USERNAME"] == "user@example.com"
    assert creds["QA_PASSWORD"] == "secret"
    assert "QA_LOGIN_URL" not in creds


def test_has_auth_credentials_requires_fillable_key():
    assert not has_auth_credentials({"QA_LOGIN_URL": "https://x.com/login"})
    assert has_auth_credentials({"QA_TEST_MOBILE": "9999999999"})


def test_default_login_url_only_from_env():
    creds = {"QA_LOGIN_URL": "https://app.test/login"}
    assert default_login_url(creds, "https://app.test") == "https://app.test/login"
    assert default_login_url({}, "https://app.test") is None


def test_resolve_auth_url_prefers_configured_login():
    creds = {"QA_LOGIN_URL": "https://app.test/login"}
    assert resolve_auth_url(creds, "https://app.test", "https://app.test/signin") == (
        "https://app.test/login"
    )
    assert resolve_auth_url({}, "https://app.test", "https://app.test/signin") == (
        "https://app.test/signin"
    )


def test_merge_legacy_cli_credentials():
    merged = merge_legacy_cli_credentials(
        {"QA_TEST_OTP": "123456"},
        login_url="https://app.test/signin",
        username="a@b.com",
        password="pw",
    )
    assert merged["QA_LOGIN_URL"] == "https://app.test/signin"
    assert merged["QA_USERNAME"] == "a@b.com"
    assert merged["QA_TEST_OTP"] == "123456"


@pytest.mark.parametrize(
    "path,expected",
    [
        ("https://app.test/login", True),
        ("https://app.test/sign-in", True),
        ("https://app.test/dashboard", False),
    ],
)
def test_is_login_path(path, expected):
    assert is_login_path(path) is expected


def test_is_login_gate_by_page_type():
    assert is_login_gate("https://app.test/home", "login", []) is True


def test_forms_have_auth_fields_detects_password():
    forms = [{"fields": [{"type": "password", "name": "password", "label": "Password"}]}]
    assert forms_have_auth_fields(forms) is True


def test_detect_sso_gateway_when_only_sign_in_button():
    """App shell with Sign in → Keycloak: no fields on landing page."""
    elements = [
        {
            "role": "button",
            "label": "Sign in",
            "selectors": {"playwright": "page.getByRole('button', { name: 'Sign in' })"},
        }
    ]
    sel = detect_sso_gateway_selector(
        [],
        elements,
        {"QA_USERNAME": "u", "QA_PASSWORD": "p"},
    )
    assert sel is not None

    # Landing page already has login fields — not a gateway
    forms = [
        {
            "fields": [
                {
                    "name": "username",
                    "type": "text",
                    "label": "Username",
                    "selectors": {"playwright": "page.locator('[name=\"username\"]')"},
                }
            ]
        }
    ]
    assert detect_sso_gateway_selector(forms, elements, {"QA_USERNAME": "u"}) is None


def test_sanitize_auth_steps_omits_secret_values():
    steps = [
        {"action": "fill", "selector": "#mobile", "credential_key": "QA_TEST_MOBILE", "value": "secret"},
        {"wait_ms": 500},
        {"action": "click", "selector": "button.login"},
    ]
    safe = sanitize_auth_steps(steps)
    assert safe == [
        {"action": "fill", "selector": "#mobile", "credential_key": "QA_TEST_MOBILE"},
        {"wait_ms": 500},
        {"action": "click", "selector": "button.login"},
    ]


def test_normalize_auth_selector_strips_page_locator_wrapper():
    assert normalize_auth_selector("page.locator('#username')") == "#username"
    assert normalize_auth_selector("#password") == "#password"


def test_execute_auth_plan_normalizes_page_locator_wrappers():
    page = MagicMock()
    plan = {
        "steps": [
            {"action": "fill", "selector": "page.locator('#username')", "credential_key": "QA_USERNAME"},
            {"action": "click", "selector": "page.locator('#kc-login')"},
        ]
    }
    creds = {"QA_USERNAME": "user", "QA_PASSWORD": "pass"}
    assert execute_auth_plan(page, plan, creds) is True
    locator_args = [call.args[0] for call in page.locator.call_args_list]
    assert "#username" in locator_args
    assert "#kc-login" in locator_args


def test_execute_auth_plan_runs_steps_in_order():
    page = MagicMock()
    plan = {
        "steps": [
            {"action": "fill", "selector": "#mobile", "credential_key": "QA_TEST_MOBILE"},
            {"wait_ms": 100},
            {"action": "fill", "selector": "#otp", "credential_key": "QA_TEST_OTP"},
            {"action": "click", "selector": "button[type=submit]"},
        ]
    }
    creds = {"QA_TEST_MOBILE": "9999999999", "QA_TEST_OTP": "123456"}
    assert execute_auth_plan(page, plan, creds) is True
    assert page.locator.return_value.first.fill.call_count == 2
    page.locator.return_value.first.click.assert_called_once()


def test_parse_json_response_ignores_trailing_text():
    payload = json_plan_otp() + "\n\nNote: use intermediate action before OTP."
    plan = parse_json_response(payload)
    assert plan["flow_type"] == "otp"
    assert len(plan["steps"]) == 5


def test_fallback_auth_plan_otp_from_discovered_controls():
    forms = [
        {
            "fields": [
                {
                    "field_id": "mobile",
                    "name": "mobileNumber",
                    "type": "tel",
                    "label": "Mobile Number",
                    "selectors": {"playwright": "page.locator('[name=\"mobileNumber\"]')"},
                },
                {
                    "field_id": "otp",
                    "name": "otp",
                    "type": "text",
                    "label": "Enter OTP",
                    "selectors": {"playwright": "page.locator('[name=\"otp\"]')"},
                },
            ]
        }
    ]
    elements = [
        {
            "role": "button",
            "label": "Send OTP",
            "selectors": {"playwright": "page.locator('button.send-otp')"},
        },
        {
            "role": "button",
            "label": "Login",
            "selectors": {"playwright": "page.locator('button.login')"},
        },
    ]
    plan = fallback_auth_plan(
        forms,
        elements,
        {"QA_TEST_MOBILE": "8827000000", "QA_TEST_OTP": "123456"},
    )
    keys = [step.get("credential_key") for step in plan["steps"] if step.get("action") == "fill"]
    assert keys == ["QA_TEST_MOBILE"]
    assert any(step.get("action") == "click" for step in plan["steps"])
    assert any(step.get("wait_ms") for step in plan["steps"])


def test_mobile_otp_phase2_split_boxes():
    page = MagicMock()
    locator = MagicMock()
    page.locator.return_value = locator
    locator.first = locator
    locator.count.return_value = 6
    locator.is_visible.return_value = True
    locator.is_enabled.return_value = True
    plan = build_mobile_otp_phase2_plan(
        page,
        "input.grm-otp-input-box",
        [{"role": "button", "label": "Verify", "field_id": "submitButton"}],
    )
    assert plan["steps"][0]["action"] == "fill_split_otp"
    assert plan["steps"][1]["action"] == "click"


def test_fill_split_otp_boxes():
    page = MagicMock()
    locator = MagicMock()
    page.locator.return_value = locator
    locator.count.return_value = 6
    nth = MagicMock()
    locator.nth.return_value = nth
    assert fill_split_otp_boxes(page, "123456", "input.grm-otp-input-box") is True
    assert nth.fill.call_count == 6


def test_is_mobile_otp_credentials():
    assert is_mobile_otp_credentials({"QA_TEST_MOBILE": "9", "QA_TEST_OTP": "1"})
    assert not is_mobile_otp_credentials({"QA_USERNAME": "u", "QA_PASSWORD": "p"})


def test_rejects_generic_button_selector():
    assert not is_usable_auth_selector("button")
    assert is_usable_auth_selector("#submitButton")


def test_find_button_prefers_submit_button_over_generic():
    page = MagicMock()
    locator = MagicMock()
    page.locator.return_value = locator
    locator.first = locator
    locator.count.return_value = 1
    locator.is_visible.return_value = True
    locator.is_enabled.return_value = True
    elements = [
        {
            "role": "button",
            "label": "Hidden login link",
            "selectors": {"playwright": "page.locator('button')"},
        },
        {
            "role": "button",
            "label": "Login",
            "field_id": "submitButton",
            "input_type": "submit",
        },
    ]
    selector = _find_button_by_hints(elements, ("login",), page=page)
    assert selector == "#submitButton"


def test_detect_split_otp_includes_modal_input_otp():
    page = MagicMock()
    page.locator.side_effect = lambda sel: MagicMock(
        count=MagicMock(return_value=6 if "input-otp" in sel else 0)
    )
    assert detect_split_otp_selector(page) == ".popup-module-main input.input-otp"


def test_fallback_auth_plan_empty_without_discovered_controls():
    plan = fallback_auth_plan([], [], {"QA_TEST_MOBILE": "8827000000", "QA_TEST_OTP": "123456"})
    assert plan["steps"] == []


def test_fallback_auth_plan_password_from_discovered_controls():
    forms = [
        {
            "form_id": "login_form",
            "fields": [
                {
                    "field_id": "email",
                    "name": "email",
                    "type": "email",
                    "label": "Email",
                    "selectors": {"playwright": "page.locator('[name=\"email\"]')"},
                },
                {
                    "field_id": "password",
                    "name": "password",
                    "type": "password",
                    "label": "Password",
                    "selectors": {"playwright": "page.locator('[name=\"password\"]')"},
                },
            ],
        }
    ]
    elements = [
        {
            "role": "button",
            "label": "Sign in",
            "selectors": {"playwright": "page.locator('button.sign-in')"},
        }
    ]
    plan = fallback_auth_plan(
        forms,
        elements,
        {"QA_USERNAME": "u", "QA_PASSWORD": "p"},
    )
    keys = [step.get("credential_key") for step in plan["steps"] if step.get("action") == "fill"]
    assert keys == ["QA_USERNAME", "QA_PASSWORD"]
    assert any(step.get("action") == "click" for step in plan["steps"])


def test_plan_auth_steps_uses_available_keys_only():
    analyzer = LLMAnalyzer()
    with patch.object(analyzer, "_run", return_value=json_plan_otp()) as mock_run:
        plan = analyzer.plan_auth_steps(
            url="https://app.test/login",
            title="Login",
            page_text="Enter mobile and OTP",
            forms=[
                {
                    "form_id": "otp_form",
                    "fields": [
                        {
                            "field_id": "mobile",
                            "name": "mobile",
                            "type": "tel",
                            "label": "Mobile",
                            "placeholder": "Mobile",
                            "selectors": {"playwright": "page.locator('[name=\"mobile\"]')"},
                        }
                    ],
                }
            ],
            elements=[{"element_id": "send_otp", "role": "button", "label": "Send OTP"}],
            available_keys=["QA_TEST_MOBILE", "QA_TEST_OTP"],
        )
    assert plan["flow_type"] == "otp"
    assert plan["steps"]
    prompt = mock_run.call_args[0][0]
    assert "QA_TEST_MOBILE" in prompt
    assert "9999999999" not in prompt


def json_plan_otp() -> str:
    import json

    return json.dumps(
        {
            "flow_type": "otp",
            "steps": [
                {"action": "fill", "selector": "[name='mobile']", "credential_key": "QA_TEST_MOBILE"},
                {"action": "click", "selector": "button.send-otp"},
                {"wait_ms": 1000},
                {"action": "fill", "selector": "[name='otp']", "credential_key": "QA_TEST_OTP"},
                {"action": "click", "selector": "button[type=submit]"},
            ],
            "success_hint": "url_path_not_login_or_dashboard",
        }
    )


def test_auth_success_after_redirect():
    assert auth_success("https://app.test/dashboard", "dashboard") is True
    assert auth_success("https://app.test/login", "unknown") is False


def test_available_fillable_keys():
    keys = available_fillable_keys(
        {"QA_USERNAME": "u", "QA_LOGIN_URL": "https://x", "QA_TEST_OTP": "1"}
    )
    assert keys == ["QA_USERNAME", "QA_TEST_OTP"]
