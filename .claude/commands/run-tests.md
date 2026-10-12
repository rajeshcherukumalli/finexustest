Pre-flight check, run Playwright tests scoped to a module/flow/tag, and summarize the report. Usage: /run-tests [module | FLOW-ID | @tag] (no argument = full suite)

---

## Setup

Locate the active app: `ls -lt data/output/` and pick the most recently modified directory
containing a workspace.json. All commands below run **locally** from `data/output/{app}/`
(no Docker required).

---

## Pre-flight (fix what you can, report what you can't)

1. `.env.qa` exists and sets `QA_UI_BASE_URL` — if missing, copy `.env.qa.example` and STOP:
   ask the user to fill in the real URL (do not guess production URLs).
2. `node_modules/` present — if not, run `npm install`.
3. Playwright browsers installed — if `npx playwright test --list` complains, run
   `npx playwright install chromium`.
4. TypeScript compiles: `npx tsc --noEmit`. If it fails, STOP and suggest /compile-fix
   with the error output — never run tests that don't compile.
5. Auth fixtures: grep the in-scope specs for `storageState`; verify each referenced file
   under tests/scripts/fixtures/auth/ exists. Missing ones are a blocker for those specs —
   report them, skip those specs, continue with the rest.

---

## Run

Scope from $ARGUMENTS:
- module      → `npx playwright test tests/scripts/e2e/{module}/`
- FLOW-ID     → `npx playwright test --grep "{FLOW-ID}"`
- @tag        → `npx playwright test --grep "@{tag}"` (e.g. @smoke)
- no argument → `npx playwright test`

Run headless by default; add `--headed` only if the user asked for it.

---

## Report

After the run, parse the output (and `playwright-report/` if needed) and print:

1. **SUMMARY** — passed / failed / skipped counts, duration, scope used.
2. **FAILURES** — table: case_id (from test title) | spec file | failing step or assertion |
   one-line error excerpt.
3. **SKIPPED FOR AUTH** — specs skipped in pre-flight, with the missing fixture path.
4. If anything failed, suggest `/triage` as the next step.
5. If allure-results/ was produced, mention `npm run report` for the Allure report.

Report results faithfully — never re-run flaky tests silently; if you retry, say so.
