Generate YAML DSL test cases from a test plan with full tag taxonomy. Usage: /testcase-gen <module>

Read the test plan at tests/testplans/$ARGUMENTS.md.
Read all existing YAML files under tests/testcases/ for naming and id conventions.

---

## Tag taxonomy (apply to every case)

### test_type — what layer the case exercises (pick all that apply):
- `e2e`          — browser interaction, navigates real pages via Playwright
- `api`          — HTTP request/response, no browser required
- `integration`  — cross-system side-effects (DB, Kafka, Redis, downstream service)

### tags — test-suite membership (pick all that apply):
- `smoke`        — fast P0 subset; runs on every deploy; must complete in < 60 s total
- `regression`   — full suite; runs on every PR merge
- `integration`  — marks cases that touch more than one system (can overlap with test_type)

Tag assignment rules:
- Every happy-path P0 case → `[smoke, regression]`
- Every edge-case or P1/P2 case → `[regression]`
- Any case whose steps verify a database, queue, or downstream service → add `integration` to tags and `integration` to test_type
- UI navigation or form-submission cases → `e2e` in test_type
- Pure API cases with no browser → `api` in test_type

---

## Output location

Write one YAML file per flow to:
  tests/testcases/$ARGUMENTS/{FLOW-ID}.yaml

---

## YAML schema (follow exactly)

```yaml
module: $ARGUMENTS
flow_id: {FLOW-ID}
flow_name: {snake_case_name}
priority: P0 | P1 | P2
test_type: [e2e]                   # one or more of: e2e, api, integration
tags: [smoke, regression]          # one or more of: smoke, regression, integration

actors:
  - id: {actor-id}
    description: {one line}

environments:
  qa: {QA_BASE_URL}

# include only if the flow exercises API calls directly
api_endpoints:
  - method: GET | POST | PUT | DELETE
    path: /resource/action
    service: {service-name}

ui_pages: [{PageId from contract}]

cases:
  - id: {FLOW-ID}-H1
    title: {description}
    type: happy_path | edge_case | negative
    test_type: [e2e]               # case-level override if different from flow
    priority: P0 | P1 | P2
    tags: [smoke, regression]      # case-level tags per taxonomy above
    preconditions:
      - {what state must exist before this test runs}
    steps:
      - {numbered action the test performs}
    assertions:
      - {named_assertion_snake_case}
    test_data_ref: {FLOW-ID}-H1
    coverage_note: >
      One sentence: what does this case cover that others do not?

  # Add for any case that verifies cross-system side-effects:
  - id: {FLOW-ID}-INT-1
    title: {description}
    type: integration
    test_type: [integration]
    priority: P1
    tags: [regression, integration]
    trigger:
      action: POST /resource/action
      payload_ref: {FLOW-ID}-H1
    verify:
      - system: postgres
        service: {service-name}
        connection: QA_{SERVICE}_PG
        query: SELECT * FROM {table} WHERE id = :resourceId
        assert:
          - field: status
            equals: EXPECTED
      - system: kafka
        topic: {resource}-{action}
        timeout_ms: 5000
        assert:
          - field: eventType
            equals: EXPECTED_EVENT

# include only if the flow has role-based access control checks
rbac_checks:
  - id: {FLOW-ID}-RBAC-1
    actor: unauthenticated
    endpoint: GET /protected-path
    expected_status: 401
  - id: {FLOW-ID}-RBAC-2
    actor: {actor-without-permission}
    endpoint: POST /resource/action
    expected_status: 403
```

---

## Generation rules

1. Create one YAML file per flow listed in the test plan's "Flows to test" table.
2. Map each step block in the plan into `cases` entries:
   - Main happy path → `{FLOW-ID}-H1`, type: `happy_path`
   - Alternative success variants → `{FLOW-ID}-H2`, `H3`, …
   - Negative/invalid inputs → `{FLOW-ID}-E1`, `E2`, …, type: `edge_case` or `negative`
3. Derive `priority` from the plan's flow table; propagate to each case (edge cases may be P1 even in a P0 flow).
4. Apply tag taxonomy strictly — do not add tags not listed above.
5. For protected pages (is_protected: true in the contract), always include an `rbac_checks` block with at least one unauthenticated check (expected_status: 401).
6. Keep `assertions` as snake_case named identifiers (e.g., `login_button_visible`, `url_contains_login_path`), not prose.
7. Use `QA_BASE_URL` as the environments.qa value (do not hardcode the domain).
8. Never add `test.only()`, `test.skip()`, or hardcoded credentials.

---

After writing all files, print:
- A table: flow_id | file path | case count | tags applied
- Any gaps or warnings found in the test plan (missing selectors, ambiguous steps, etc.)
