Generate Playwright E2E spec and Page Object Model files from a YAML test case and contract selectors — no live browser required. Specs include Allure annotations for reporting. Usage: /playwright-gen <module> <FLOW-ID>

---

## Setup

1. Locate the active app: run `ls data/output/` and pick the directory that contains a workspace.json.
   If multiple exist, use the one most recently modified (check via `ls -lt data/output/`).
2. Read `data/output/{app}/tests/testcases/{module}/{FLOW-ID}.yaml` — this is the source of truth.
3. Read `data/output/{app}/workspace.json` → get `contract_path`.
4. Read the contract file at the path from step 3 (strip leading `/` if it is an absolute path under the repo root).
5. Read all existing files in `data/output/{app}/tests/scripts/pages/` to avoid overwriting unchanged POMs.

---

## STEP 1 — Page Object Model (one file per page in ui_pages)

For each `page_id` in the YAML `ui_pages` list:

a. Find the matching page in `contract.pages` (match on `page_id`).
   If not found, generate a stub POM with `// TODO: page not in contract — selectors need manual wiring`.

b. Derive `ClassName`: PascalCase the `page_id` and append `Page`
   (e.g. `login_otp` → `LoginOtpPage`, `home` → `HomePage`).

c. Write `data/output/{app}/tests/scripts/pages/{ClassName}.page.ts`:

```typescript
/** AUTO-GENERATED from contract — re-run /playwright-gen {module} {FLOW-ID} to refresh */
import { type Page, type Locator, expect } from '@playwright/test'

export class {ClassName} {
  constructor(readonly page: Page) {}

  // --- locators ---
  // One getter per element in contract page.elements, named after element_id in camelCase.
  // Selector priority (use first available):
  //   1. element.selectors.playwright → strip leading "page." → this.page.{rest}
  //   2. element.role + element.label  → this.page.getByRole('{role}', { name: '{label}' })
  //   3. element.selectors.css         → this.page.locator('{css}')
  //   4. fallback                      → this.page.locator('[data-element-id="{element_id}"]') // FRAGILE
  {elementId}(): Locator { return this.page.{selector} }

  // --- page actions ---
  async goto(baseURL: string): Promise<void> {
    await this.page.goto(baseURL + '{page.path}')
  }

  async expectLoaded(): Promise<void> {
    await expect(this.page).toHaveURL(new RegExp('{page.path}'.replace('/', '\\/')))
  }
}
```

Rules for locator getters:
- Convert `element_id` to camelCase for the method name.
- If `element.selectors.playwright` is `page.locator('...')`, strip `page.` → `this.page.locator('...')`.
- Skip elements with `region: "hidden"` or `is_interactive: false` if they add no test value.

---

## STEP 2 — E2E spec file

Write `data/output/{app}/tests/scripts/e2e/{module}/{FLOW-ID}.e2e.spec.ts`:

```typescript
/**
 * AUTO-GENERATED — do not edit by hand.
 * Source:    testcases/{module}/{FLOW-ID}.yaml
 * Flow:      {flow_id} — {flow_name}
 * Contract:  {contract_filename} v{contract_version}
 * Generator: /playwright-gen {module} {FLOW-ID}
 */
import { test, expect } from '@playwright/test'
import { allure } from 'allure-playwright'
import { {ClassName} } from '../../pages/{ClassName}.page'   // one import per ui_page

const BASE_URL = process.env.QA_BASE_URL ?? 'http://localhost:3000'
const YAML_SOURCE = 'testcases/{module}/{FLOW-ID}.yaml'   // traceability anchor for every test

test.describe('{flow_id} {flow_name}', {
  tag: ['@{FLOW-ID}', '@{module}', '@{priority}', '@{tag}', ...],   // flow-level tags from YAML
}, () => {
  // Single-actor flows: set storageState once
  test.use({ storageState: 'tests/scripts/fixtures/auth/{first-actor}.json' })
  // Multi-actor flows: use browser.newContext({ storageState }) inside the test body instead

  test.beforeEach(async ({ page }) => {
    const primaryPage = new {PrimaryPageClass}(page)
    await primaryPage.goto(BASE_URL)
  })

  // --- one test block per case in YAML cases list ---
  // Test name format: "{case_id}: {title}" — case_id is the stable traceability key
  test('{case_id}: {title}', {
    tag: ['@{case_tags}'],   // case-level tags if different from flow
  }, async ({ page }) => {
    // --- Traceability (one allure.tms + allure.parameter block per test) ---
    await allure.tms('{case_id}', YAML_SOURCE + '#{case_id}')  // links report entry → YAML case
    await allure.parameter('case_id',       '{case_id}')        // YAML: cases[n].id
    await allure.parameter('flow_id',       '{flow_id}')        // YAML: flow_id
    await allure.parameter('module',        '{module}')          // YAML: module
    await allure.parameter('type',          '{case.type}')       // happy_path | edge_case | negative
    await allure.parameter('priority',      '{case.priority}')   // P0 | P1 | P2
    await allure.parameter('test_data_ref', '{case.test_data_ref}') // YAML: cases[n].test_data_ref
    await allure.parameter('yaml_source',   YAML_SOURCE)         // file-level source pointer

    // --- Allure report metadata ---
    await allure.epic('{module}')                        // YAML: module
    await allure.feature('{flow_name}')                  // YAML: flow_name
    await allure.story('{case.title}')                   // YAML: cases[n].title
    await allure.severity('{severity}')                  // P0 → critical, P1 → normal, P2 → minor
    await allure.tag('{tag}')                            // one call per tag in YAML cases[n].tags
    await allure.description(
      '{case.coverage_note}\n\n' +
      'Source: ' + YAML_SOURCE + '#{case_id}'
    )

    // Instantiate POMs for pages referenced in this case's steps
    const {pageVar} = new {ClassName}(page)

    // Wrap each YAML step in an allure.step() block.
    // Steps that already contain Playwright expressions (page.locator, page.getByRole, etc.)
    // should be lifted verbatim as await {expression} inside the step callback.
    // Steps that describe actions in prose should be translated idiomatically:
    //   "Navigate to QA_BASE_URL{/path}"  → await page.goto(BASE_URL + '{/path}')
    //   "Navigate back to QA_BASE_URL"    → await page.goBack()
    //   "Click {expr}"                    → await {expr}
    //   "Assert {expr} is visible"        → await expect({expr}).toBeVisible()
    //   "Fill {field} with {value}"       → await {expr}.fill('{value}')
    //   "Assert page.url pathname equals {path}" → await expect(page).toHaveURL(new RegExp('{path}'))
    //   "Record actual landing pathname"  → const landingURL = page.url()
    //   Unknown step                      → // TODO: {step text}
    await allure.step('{step text}', async () => {
      // translated Playwright code for this step
    })

    // Assertion mapping (after steps, each in its own allure.step):
    //   *_visible / *_displayed           → await expect({pom}.{element}()).toBeVisible()
    //   *_hidden / *_not_visible          → await expect({pom}.{element}()).not.toBeVisible()
    //   url_contains_{x} / url_pathname_equals_{x}
    //                                     → await expect(page).toHaveURL(/{x}/)
    //   *_stays_at_* / same_page_*        → await expect(page).toHaveURL(new RegExp(currentPath))
    //   *_redirects_to_*                  → await expect(page).toHaveURL(...)
    //   *_error_* / *_error_boundary_*    → await expect(page.locator('[role="alert"]')).toBeVisible()
    //   no_error_boundary_*               → await expect(page.locator('[role="alert"]')).not.toBeVisible()
    //   *_success_*                       → await expect(page.locator('[data-status="success"]')).toBeVisible()
    //   Unknown assertion                 → // TODO: assert {assertion_name}
    await allure.step('Assert: {assertion_name}', async () => {
      // expect() call for this assertion
    })
  })
})
```

### Allure metadata mapping

**Traceability (applied first in every test body):**

| YAML field | Allure call | Purpose |
|---|---|---|
| `cases[n].id` | `allure.tms(case_id, yaml_source + '#' + case_id)` | Clickable link from report → YAML case |
| `cases[n].id` | `allure.parameter('case_id', ...)` | Filterable in Allure UI |
| `flow_id` | `allure.parameter('flow_id', ...)` | Trace test → flow |
| `module` | `allure.parameter('module', ...)` | Trace test → module |
| `cases[n].type` | `allure.parameter('type', ...)` | happy_path / edge_case / negative |
| `cases[n].priority` | `allure.parameter('priority', ...)` | P0 / P1 / P2 as raw string |
| `cases[n].test_data_ref` | `allure.parameter('test_data_ref', ...)` | Links to fixture entry |
| YAML file path | `allure.parameter('yaml_source', YAML_SOURCE)` | Full path to source file |

**Report metadata (applied after traceability):**

| YAML field | Allure call | Notes |
|---|---|---|
| `module` | `allure.epic()` | Groups all flows in the module |
| `flow_name` | `allure.feature()` | Groups cases within the flow |
| `cases[n].title` | `allure.story()` | Individual test story |
| `cases[n].priority` | `allure.severity()` | P0 → `critical`, P1 → `normal`, P2 → `minor` |
| `cases[n].tags` | `allure.tag()` | One call per tag |
| `cases[n].coverage_note` | `allure.description()` | Appended with `Source: {yaml_source}#{case_id}` |
| Each step in `cases[n].steps` | `allure.step(stepText, fn)` | Step text verbatim from YAML |
| Each name in `cases[n].assertions` | `allure.step('Assert: {name}', fn)` | Assertion label in timeline |

### playwright.config.ts reporter entry

When generating or updating `playwright.config.ts`, include the Allure reporter:

```typescript
reporter: [
  ['list'],
  ['allure-playwright', {
    detail: true,
    outputFolder: 'allure-results',
    suiteTitle: true,
  }],
],
```

Also ensure `package.json` (or `package.json` at the scripts root) has:
```json
"devDependencies": {
  "allure-playwright": "^3.0.0"
}
```

And add these npm scripts:
```json
"scripts": {
  "report": "allure generate allure-results --clean -o allure-report && allure open allure-report"
}
```

---

## Rules

- Never emit `test.only()` or `test.skip()`.
- Never hardcode credentials, passwords, or tokens.
- Import only POMs that appear in this flow's `ui_pages`.
- For actors: if `actors` has one entry use `test.use({ storageState })` at describe level;
  if multiple actors interact in one test, use `browser.newContext({ storageState })` per role inside the test body.
- If `anonymous_user` or any unauthenticated actor is the only actor, omit storageState entirely.
- Preserve YAML case order in the spec (happy paths first, edge cases after).
- For steps that contain raw Playwright expressions in the YAML (e.g. `page.locator('...')`, `page.getByRole(...)`),
  lift them as-is with `await` — do not re-interpret as prose.

---

## Output summary

After writing all files, print a Markdown table:

| File | Cases | Pages / Notes |
|------|-------|---------------|
| tests/scripts/pages/{ClassName}.page.ts | — | {element count} locators |
| tests/scripts/e2e/{module}/{FLOW-ID}.e2e.spec.ts | {N} | happy:{h} edge:{e} |

List any TODOs or warnings (missing contract pages, unresolvable selectors, unknown assertions).
