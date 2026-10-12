Generate API spec, integration spec, fixture stubs, and seed script from a YAML test case file. Specs include Allure annotations for reporting. Usage: /script-gen <module> <FLOW-ID>

Read tests/testcases/$ARGUMENTS.yaml.

PART A — API spec:
Write tests/scripts/api/{module}/{FLOW-ID}.api.spec.ts

File header (top of file):
  /**
   * AUTO-GENERATED — do not edit by hand.
   * Source:    testcases/{module}/{FLOW-ID}.yaml
   * Flow:      {flow_id} — {flow_name}
   * Generator: /script-gen {module} {FLOW-ID}
   */

Structure per test:
  import { allure } from 'allure-playwright'

  const YAML_SOURCE = 'testcases/{module}/{FLOW-ID}.yaml'

  test('{case_id}: {description}', async ({ request }) => {
    // --- Traceability ---
    await allure.tms('{case_id}', YAML_SOURCE + '#{case_id}')
    await allure.parameter('case_id',       '{case_id}')
    await allure.parameter('flow_id',       '{flow_id}')
    await allure.parameter('module',        '{module}')
    await allure.parameter('type',          '{case.type}')
    await allure.parameter('priority',      '{case.priority}')
    await allure.parameter('test_data_ref', '{case.test_data_ref}')
    await allure.parameter('yaml_source',   YAML_SOURCE)
    await allure.parameter('endpoint',      '{METHOD} {path}')  // API-specific: which endpoint

    // --- Report metadata ---
    await allure.epic('{module}')
    await allure.feature('{flow_name}')
    await allure.story('{case.title}')
    await allure.severity('{severity}')   // P0 → critical, P1 → normal, P2 → minor
    await allure.tag('{tag}')             // one call per tag in YAML case.tags
    await allure.description(
      '{case.coverage_note}\n\nSource: ' + YAML_SOURCE + '#{case_id}'
    )

    // ARRANGE
    const payload = fixtures['{case-id}'].payload;

    // ACT
    const response = await allure.step('{METHOD} {path}', async () =>
      request.{METHOD}(`${BASE_URL}{path}`, { data: payload, headers: authHeader })
    )

    // ASSERT — each assertion in its own allure.step
    await allure.step('Assert status {expected}', async () => {
      expect(response.status()).toBe({expected});
    })
    // map remaining assertions from YAML — each in its own allure.step('Assert: {name}', fn)
  });

Assertion mapping (apply these exact translations):
  *_rejected / *_not_allowed  → expect(response.status()).toBe(4xx)
  *_returns_correct_*         → expect(body.field).toBe(expected)
  *_exists / *_created        → expect(body.id).toBeDefined()
  *_matches_*                 → expect(body.field).toEqual(expected)
  unknown assertion           → // TODO: assert {name}

Include:
  - AUTO-GENERATED header with Source / Flow / Generator lines (as shown above)
  - YAML_SOURCE constant at file level — used in allure.tms() and allure.description()
  - import { allure } from 'allure-playwright' at the top of the file
  - Traceability block before report metadata block in every test body (order matters)
  - test.use({ storageState }) per actor
  - One test per happy_path, per edge_case, per rbac_check
  - Tags: @{FLOW-ID} @{module} @{priority} @smoke/@regression
  - Never hardcode credentials
  - Never use test.only() or test.skip()

PART B — Integration spec (if cases with test_type: integration exist):
Write tests/scripts/integration/{module}/{FLOW-ID}.int.spec.ts

File header: same AUTO-GENERATED block as Part A (Source / Flow / Generator).

For each integration case:
  - Import { allure } from 'allure-playwright'
  - Import { dbs, redis, kafka } from '../../helpers/connections'
  - Apply the full traceability block first (allure.tms + allure.parameter for all fields)
  - Apply report metadata after (epic/feature/story/severity/tag/description with Source appended)
  - Fire the trigger action via request.{METHOD}() wrapped in allure.step('Trigger: {action}', fn)
  - For each verify block in YAML, wrap in allure.step('Verify: {system} {field}={value}', fn):
      postgres: await dbs['{service}'].query(query, [resourceId])
      redis:    await redis.get(key)
      kafka:    consumer = await kafka.consumer(); await consumer.subscribe({topic})
               message = await waitForMessage(consumer, 5000)
  - Assert each field as specified in the verify.assert block
  - Tag: @{FLOW-ID} @integration @{priority}

PART C — Fixture stubs:
Write tests/scripts/fixtures/{module}/{FLOW-ID}.fixtures.ts
with typed placeholder objects for each case id.
Use const assertions (as const) for type safety.

PART D — Seed script:
Write tests/scripts/fixtures/seeds/{FLOW-ID}.seed.ts with:
  export async function seedData(flowId, request, baseUrl): SeedContext
  export async function teardownData(ctx, request, baseUrl): void
Use API calls (request.post) for most seeding.
Use dbs['{service}'].query() only for state impossible via API
(expired timestamps, zero-balance edge cases etc).
All seeded records must have name/key prefixed with qa-test-{runId}.

List all files written at the end.
