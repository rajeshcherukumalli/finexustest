Generate YAML DSL test case files from a test plan. Usage: /yaml-dsl-gen <module>

Read the test plan at tests/testplan/$ARGUMENTS.md.
Read all existing YAML files in tests/testcases/ for context.

For each flow described in the test plan, generate a YAML file
at tests/testcases/$ARGUMENTS/{FLOW-ID}.yaml following this structure:

module: $ARGUMENTS
flow_id: {FLOW-ID}
flow_name: {snake_case_name}
priority: P0 | P1 | P2
type: [api, e2e, integration]
tags: [smoke, regression]
actors: [{actor-id}]

environments:
  qa: {QA_BASE_URL}

api_endpoints:
  - method: GET | POST | PUT | DELETE
    path: /resource/action
    service: {service-name}

ui_pages: [{PageName}]

cases:
  - id: {FLOW-ID}-H1
    title: {description}
    type: happy_path | edge_case
    test_type: [api] | [e2e] | [integration] | [api, e2e]
    priority: P1
    tags: [smoke, regression]
    preconditions: [{what state must exist before this test}]
    steps: [{what happens}]
    assertions: [{named_assertion}]
    test_data_ref: {FLOW-ID}-H1
    coverage_note: >
      Explain why this case exists — what does it cover that
      existing tests do not?

  # For integration cases add:
  - id: {FLOW-ID}-INT-1
    test_type: [integration]
    trigger:
      action: POST /resource/action
      payload_ref: {FLOW-ID}-H1
    verify:
      - system: postgres
        service: {service-name}
        connection: QA_{SERVICE}_PG
        query: SELECT * FROM {table} WHERE id = :resourceId
        assert: [{field: status, equals: EXPECTED}]
      - system: kafka
        topic: {resource}-{action}
        timeout_ms: 5000
        assert: [{field: eventType, equals: EXPECTED_EVENT}]

rbac_checks:
  - id: {FLOW-ID}-RBAC-1
    actor: {actor-without-permission}
    endpoint: POST /resource/action
    expected_status: 403
  - id: {FLOW-ID}-RBAC-2
    actor: unauthenticated
    endpoint: POST /resource/action
    expected_status: 401

After writing all files, list every file created and note any gaps
or warnings you noticed in the test plan.
