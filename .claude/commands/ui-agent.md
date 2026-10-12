Generate Page Object Model classes and E2E Playwright specs from a YAML test case file. Usage: /ui-agent <module> <FLOW-ID>

Read tests/testcases/$ARGUMENTS.yaml.
Read all existing page files in tests/scripts/pages/ so you know
which POMs already exist and do not need regenerating.

For each flow in the YAML where test_type includes 'e2e'
and it has not been generated before (or has changed):

STEP 1 — For each page in ui_pages:
  a. Convert PageName to URL: remove 'Page' suffix → kebab-case
     → navigate to {QA_BASE_URL}/{kebab-path}
  b. Use Playwright MCP browser_navigate to open the page
     using auth state from tests/scripts/fixtures/auth/{first-actor}.json
  c. Use browser_evaluate to extract selectors in priority order:
     1. data-testid attributes → page.getByTestId('value')
     2. aria-label            → page.getByRole(..., { name: 'value' })
     3. input name/id         → page.locator('[name="value"]')
     4. button text           → page.getByRole('button', { name: 'value' })
     5. CSS fallback          → page.locator('selector') // FRAGILE
  d. Write tests/scripts/pages/{PageName}.page.ts with:
     - AUTO-GENERATED header with timestamp
     - Typed Locator properties for each element
     - Action methods: fillDetails(), submit(), waitForLoad()
     - Extends BasePage if it exists

STEP 2 — Write tests/scripts/e2e/{module}/{FLOW-ID}.e2e.spec.ts:
  - Import the POM class just written
  - Single actor: test.use({ storageState: 'fixtures/auth/{actor}.json' })
  - Multi-actor: browser.newContext({ storageState }) per role
  - beforeAll: import and call seedData('{FLOW-ID}', request, BASE_URL)
  - afterAll: call teardownData(seedCtx, request, BASE_URL)
  - afterEach: screenshot on failure to test-results/screenshots/
  - One test() block per happy_path in YAML
  - One test() block per edge_case in YAML
  - Tags: { tag: ['@{FLOW-ID}', '@{module}', '@{priority}', '@smoke'/'@regression'] }
  - Map assertions to expect() on POM locators
  - Add AUTO-GENERATED header

If a page cannot be reached, generate stub POM with // TODO: selector comments.
List all files written at the end.
