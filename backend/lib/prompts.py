"""Versioned LLM prompt templates."""

import json
from typing import Any


def test_plan_contract_context(contract_slice: dict, module: str) -> str:
    """System message: slimmed UI contract as app metadata for grounding."""
    app = contract_slice.get("application", {})
    page_sequence = contract_slice.get("page_sequence", [])
    return f"""You are a senior QA engineer. You write E2E test plans grounded in a scraped UI contract.

The JSON below is CONTRACT METADATA for the application under test. It is the only source of truth for:
- pages (page_id, path, title, page_type)
- interactive elements (element_id, role, label, selectors, target_path)
- forms and fields
- home_navigation entries (when present)

Application: {app.get("name", "unknown")} ({app.get("base_url", "")})
Inferred module for this request: {module}
Relevant page sequence: {", ".join(page_sequence) if page_sequence else "(see pages below)"}

Rules for using this metadata:
- Map the user's natural-language request to concrete page_id and element_id values from this contract only.
- Do not invent pages, routes, elements, or selectors not present in the metadata.
- For navigation intents: prefer `home_navigation` over unrelated `route_index` entries.
- For content journeys: follow `page_sequence` order when describing user flows.

CONTRACT METADATA:
{json.dumps(contract_slice, indent=2)}"""


def test_plan_intent_request(user_intent: str, plan_id: str) -> str:
    """User message: what to test and how to format the plan."""
    return f"""The user wants to test the following on the application described in your contract metadata:

{user_intent}

Write a Markdown test plan with these sections exactly:
## Module purpose
## Actors
## Flows to test
(table: Flow ID | Description | Priority)
## Key assertions
## Per-flow notes

Rules:
- Plan ID / Flow ID (use as the only Flow ID): {plan_id}
- EXACTLY ONE row in the Flows to test table — flow ID must be `{plan_id}`
- EXACTLY ONE per-flow notes subsection for `{plan_id}`
- Interpret the user request using the contract metadata — reference real page_id, path, and element_id values
- Consolidate the entire user intent into this single flow (e.g. all nav links = one flow, not one per link)
- Priority P0
- E2E only (no API or integration flows)
- Output ONLY Markdown body (no frontmatter, no fences)"""


def build_test_plan_messages(
    user_intent: str,
    contract_slice: dict,
    plan_id: str,
    module: str,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": test_plan_contract_context(contract_slice, module)},
        {"role": "user", "content": test_plan_intent_request(user_intent, plan_id)},
    ]


def test_plan_intent_prompt(user_intent: str, contract_slice: dict, plan_id: str) -> str:
    """Legacy single-string prompt (metadata + request combined). Prefer build_test_plan_messages."""
    module = contract_slice.get("module", "content")
    return (
        test_plan_contract_context(contract_slice, module)
        + "\n\n---\n\n"
        + test_plan_intent_request(user_intent, plan_id)
    )


def test_plan_prompt(module: str, contract_slice: dict) -> str:
    return f"""
You are a senior QA engineer writing a test plan for module "{module}".

Use ONLY the UI contract slice below. Do not invent pages or elements not listed.

Contract slice:
{json.dumps(contract_slice, indent=2)}

Write a Markdown test plan with these sections exactly:
## Module purpose
## Actors
## Flows to test
(table: Flow ID | Description | Priority)
## Key assertions
## Per-flow notes
(one subsection per flow with page_id, path, element_id references)

Rules:
- Flow IDs for THIS module only: auth module → AUTH-01 only; navigation → NAV-01, NAV-02; content → CONTENT-01 only
- Do NOT include flows that belong to other modules
- Priority P0 for login and primary nav, P1 for secondary content
- Reference real element_id and form field_id values from the contract
- E2E only (no API or integration flows)
- Output ONLY Markdown, no fences
"""


def testcase_contract_context(contract_slice: dict, module: str) -> str:
    """System message: slimmed UI contract as app metadata for YAML testcase generation."""
    return test_plan_contract_context(contract_slice, module).replace(
        "You write E2E test plans grounded in a scraped UI contract.",
        "You generate structured YAML E2E testcase flows grounded in a scraped UI contract.",
        1,
    ) + (
        "\n\nWhen emitting element_refs and nav_links, use ONLY element_id, page_id, "
        "and route values from the contract metadata above."
    )


def testcase_yaml_request(
    module: str,
    plan_markdown: str,
    plan_id: str,
    user_intent: str = "",
) -> str:
    """User message: test plan + output schema for one YAML flow."""
    flow_id = plan_id or "FLOW-01"
    intent_block = f"\nOriginal user test intent:\n{user_intent}\n" if user_intent else ""
    return f"""Convert the test plan below into ONE YAML testcase flow for module "{module}".
{intent_block}
Test plan:
{plan_markdown}

Return ONLY JSON (no markdown). The root object IS the flow (do not wrap in "flow" or "flows"):
{{
  "module": "{module}",
  "flow_id": "{flow_id}",
  "flow_name": "snake_case_name",
  "priority": "P0",
  "type": ["e2e"],
  "tags": ["smoke", "regression"],
  "actors": ["public"],
  "environments": {{ "qa_ui": "${{QA_UI_BASE_URL}}" }},
  "ui_pages": ["HomePage"],
  "cases": [
    {{
      "id": "{flow_id}-H1",
      "title": "human readable case title",
      "type": "happy_path",
      "test_type": ["e2e"],
      "priority": "P0",
      "tags": ["smoke"],
      "preconditions": ["..."],
      "steps": ["..."],
      "assertions": ["page_title_visible"],
      "element_refs": [
        {{ "element_id": "...", "action": "click", "page_id": "home" }},
        {{ "element_id": "...", "action": "fill", "page_id": "assets_section", "value": "search term" }}
      ],
      "coverage_note": "why this case exists"
    }}
  ]
}}

Rules:
- Map plan steps to element_refs using contract metadata from your system context
- Return ONE flow only (not an array) — the entire plan maps to this single testcase file
- flow_id MUST be `{flow_id}`
- cases array may contain 1–12 case objects; YOU decide how to split based on plan scope
- Guidance (not hard rules): split by distinct user journeys, isolated nav links, or auth vs content; keep tightly coupled smoke in one case
- Case ids: `{flow_id}-H1`, `{flow_id}-H2`, … sequentially
- FORBIDDEN: inventing element_id, route, or page_id not in the contract metadata
- nav_links: ONLY when module is "navigation". For content or auth flows omit nav_links entirely (do not copy home_navigation)
- When module is "navigation" and contract includes `home_navigation`, nav_links MUST use only those entries
- nav_links MUST be objects with label, route, and element_id — never plain strings
- element_refs MUST match the plan steps — not unrelated header links
- element_refs[].page_id must be contract page_id (e.g. home), not PascalCase (not HomePage)
- Use semantic assertions: url_matches_route, page_title_visible, form_field_visible, login_button_clickable, link_visible, page_loads
- ui_pages use PascalCase Page names (e.g. home -> HomePage); include HomePage when the flow starts from the home page"""


def build_testcase_messages(
    module: str,
    plan_markdown: str,
    contract_slice: dict,
    user_intent: str = "",
    plan_id: str = "",
) -> list[dict[str, str]]:
    module = contract_slice.get("module", module)
    return [
        {"role": "system", "content": testcase_contract_context(contract_slice, module)},
        {
            "role": "user",
            "content": testcase_yaml_request(module, plan_markdown, plan_id, user_intent),
        },
    ]


def testcase_yaml_prompt(
    module: str,
    plan_markdown: str,
    contract_slice: dict,
    user_intent: str = "",
    plan_id: str = "",
) -> str:
    """Legacy single-string prompt. Prefer build_testcase_messages."""
    module = contract_slice.get("module", module)
    return (
        testcase_contract_context(contract_slice, module)
        + "\n\n---\n\n"
        + testcase_yaml_request(module, plan_markdown, plan_id, user_intent)
    )


def spec_execution_context(execution_slice: dict) -> str:
    """System message: execution contract metadata for Playwright codegen."""
    app = execution_slice.get("application", {})
    page_sequence = execution_slice.get("page_sequence", [])
    return f"""You generate Playwright TypeScript E2E test code grounded in a scraped UI contract execution slice.

The JSON below is EXECUTION CONTRACT METADATA for this flow. It is the only source of truth for:
- pages in scope (page_id, path, title)
- interactive elements (element_id, role, label, selectors.playwright, target_path, assert)
- forms and fields referenced by the testcase
- home_navigation entries when present

Application: {app.get("name", "unknown")} ({app.get("base_url", "")})
Resolved page sequence: {", ".join(page_sequence) if page_sequence else "(see pages below)"}

Rules for using this metadata:
- Use ONLY selectors.playwright from this execution slice — do NOT invent selectors or method names
- FORBIDDEN: semantic POM helpers (e.g. clickAssetsButton, fillSearchInput, submitSearch)
- element_id values must match the metadata exactly

EXECUTION CONTRACT METADATA:
{json.dumps(execution_slice, indent=2)}"""


def spec_case_request(
    case: dict,
    pom_names: list[str],
    flow_id: str = "",
) -> str:
    return f"""Generate the body of ONE Playwright TypeScript test() block (no imports, no describe wrapper).

Flow ID: {flow_id}
POM classes available: {", ".join(pom_names)}

Case:
{json.dumps(case, indent=2)}

Rules:
- Output ONLY statements inside the test body — do NOT include test(...) or closing }}); lines
- Use page.getByRole / page.locator patterns exactly as in execution metadata selectors.playwright
- Do NOT use page.goto inside the test — assume beforeEach navigates to the start page
- Include url/hash assertions from contract assert metadata when clicking nav links
- Output ONLY code, no markdown fences"""


def spec_body_request(flow_yaml: dict, pom_names: list[str]) -> str:
    return f"""Generate the body of a Playwright TypeScript E2E spec (imports and describe wrapper exist).

Flow YAML:
{json.dumps(flow_yaml, indent=2)}

POM classes available: {", ".join(pom_names)}

Rules:
- Output ONLY TypeScript test() blocks inside the describe (no imports, no describe wrapper)
- Use POM instances where possible
- Tag each test with flow case id in the test name
- Use test.skip for auth flows when actor needs login and no fixture note says otherwise
- Do NOT use page.goto inside tests — assume beforeEach navigates
- Output ONLY code, no markdown fences"""


def build_spec_case_messages(
    case: dict,
    execution_slice: dict,
    pom_names: list[str],
    flow_id: str = "",
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": spec_execution_context(execution_slice)},
        {"role": "user", "content": spec_case_request(case, pom_names, flow_id)},
    ]


def build_spec_body_messages(
    flow_yaml: dict,
    execution_slice: dict,
    pom_names: list[str],
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": spec_execution_context(execution_slice)},
        {"role": "user", "content": spec_body_request(flow_yaml, pom_names)},
    ]


def spec_case_prompt(
    case: dict,
    contract_slice: dict,
    pom_names: list[str],
    flow_id: str = "",
) -> str:
    """Legacy single-string prompt. Prefer build_spec_case_messages."""
    return (
        spec_execution_context(contract_slice)
        + "\n\n---\n\n"
        + spec_case_request(case, pom_names, flow_id)
    )


def spec_body_prompt(flow_yaml: dict, contract_slice: dict, pom_names: list[str]) -> str:
    """Legacy single-string prompt. Prefer build_spec_body_messages."""
    return (
        spec_execution_context(contract_slice)
        + "\n\n---\n\n"
        + spec_body_request(flow_yaml, pom_names)
    )
