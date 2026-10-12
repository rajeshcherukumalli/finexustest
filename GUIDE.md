# Junior QA Guide: Automating a New Project

Step-by-step instructions to take any web app from zero to running Playwright tests
using this repo. Follow the steps in order — each one verifies the previous one.

Throughout, replace `{app}` with a short slug for your project (e.g. `myshop`) and
`{url}` with the app's QA base URL. Slash commands (`/testplan-gen` etc.) run inside
Claude Code from the repo root.

---

## Step 0 — One-time setup

```bash
cd backend
pip install -r requirements.txt
playwright install chromium
cp ../.env.example ../.env        # app login credentials only — see step 1
```

**No API key needed.** The tooling shells out to the `claude` CLI, which uses your
Claude Code login. `ANTHROPIC_API_KEY` is only required if you run the dockerized
web UI, where the CLI has no interactive login.

**Done when:** `python pipeline.py --help` prints usage and `claude --version` works
(you are logged in to Claude Code).

---

## Step 1 — Scrape the app into a contract

The "contract" is a JSON inventory of every page and interactive element (with
selectors). Everything downstream is generated from it.

```
/rescrape {app} {url}
```

If some pages aren't linked from the home page, add seed paths:

```
/rescrape {app} {url} /admin/dashboard,/reports
```

If parts of the app need login, set the credentials in `.env` **before** scraping —
never type them into chat or commit them. Copy from `.env.example`.

### Scraper login styles (pick one per app)

Always set:

| Variable | Purpose |
|---|---|
| `QA_LOGIN_URL` | Canonical login page URL for this app |

Then pick **one** style and fill only those variables:

| Style | Variables | Notes |
|---|---|---|
| Username + password | `QA_USERNAME`, `QA_PASSWORD` | Standard form login |
| Email + password | `QA_USERNAME`, `QA_PASSWORD` | Put the email address in `QA_USERNAME` |
| Mobile + OTP | `QA_TEST_MOBILE`, `QA_TEST_OTP` | Same-page SPA: mobile → Login → OTP boxes → Verify (e.g. Bihar Krishi) |
| SSO gateway (Keycloak / OIDC) | `QA_USERNAME`, `QA_PASSWORD` | App shows **Sign in** only; scraper clicks through to IdP, then fills Keycloak form |

**SSO example** (e.g. `https://talk2fpa.beehyv.com/login` → Keycloak):

```env
QA_LOGIN_URL=https://talk2fpa.beehyv.com/login
QA_USERNAME=your_user
QA_PASSWORD=your_password
```

Test with `--auth-only` first; report should show `"sso_gateway": true` and a `phases` array.

**Examples** (in `qa-automation/.env`):

```env
# Username + password
QA_LOGIN_URL=https://app.example.com/login
QA_USERNAME=qa_user
QA_PASSWORD=secret

# Email + password
QA_LOGIN_URL=https://app.example.com/login
QA_USERNAME=qa@example.com
QA_PASSWORD=secret

# Mobile + OTP (e.g. Bihar Krishi staging — same page, split OTP boxes)
QA_LOGIN_URL=https://staging.biharkrishi.in
QA_TEST_MOBILE=9876543210
QA_TEST_OTP=123456
```

**Rules:**
- Do **not** set both password and OTP credential sets in the same `.env` — the scraper
  infers flow type from which keys are present. Use one style per app.
- `QA_AUTH_MODE` in `.env` is **planned** (`password` \| `email_password` \| `mobile_otp`
  \| `auto`) but not enforced in code yet.
- Scraper auth (above) is separate from **Playwright test auth** (step 10: `storageState`
  JSON files under `tests/scripts/fixtures/auth/`).

The scraper runs **two passes** when fillable credentials exist: anonymous crawl, then
login + authenticated crawl of protected pages.

### Fast auth testing (no full scrape)

Before a long crawl, verify login alone:

```bash
cd backend
python scraper.py https://your-qa-site.com --auth-only --login-url https://your-qa-site.com/login
```

With OTP creds in `.env`, add `--headed` to watch the browser. Prints a JSON report:
`plan_source`, `flow_type`, `steps` (selectors only, no secrets), `success`, `final_url`, `error`.

Exit code `0` = login succeeded; `1` = failed. Fix `.env` or selectors, then re-run until green,
then run a full `/rescrape`.

**Verify:** open `data/contracts/{app}-contract.json`.
- Are all the important pages listed under `pages`?
- Do elements have non-empty `selectors.playwright`?
- Pages with `scrape_status: "login_redirect"` were NOT scraped — set the auth
  variables in `.env` and re-run `/rescrape {app}`.

**Common mistake:** scraping only the public home page and wondering later why every
logged-in test has missing selectors.

---

## Step 2 — Add the API contract (if the app has an API)

Copy the project's Swagger/OpenAPI JSON into the contracts folder:

```bash
cp swagger.json data/contracts/{app}-api.json
```

Skip this step for UI-only testing — but then `/script-gen` (API tests) won't apply.

---

## Step 3 — Generate a test plan

One plan per module (a module = a functional area: auth, navigation, checkout, …).

```
/testplan-gen navigation
/testplan-gen auth "login and logout for the customer role only"
```

**Verify:** open `data/output/{app}/tests/testplan/{module}.md`.
- Does the "Flows to test" table cover what you'd test manually?
- Read the Warnings section — it lists elements with missing selectors already.

Plans are markdown — edit them by hand if a flow is wrong or missing before moving on.
Fixing the plan now is much cheaper than fixing generated tests later.

---

## Step 4 — Generate YAML test cases

First check you're not duplicating existing coverage, then generate:

```
/overlap-analysis {module}
/testcase-gen {module}
```

**Verify:** open the files under `data/output/{app}/tests/testcases/{module}/`.
- One YAML per flow; happy path cases (`-H1`) plus edge cases (`-E1`…).
- Each case has `test_data_ref` — that's a *pointer* to test data, filled in step 8.

---

## Step 5 — Audit selectors (do not skip)

```
/selector-audit {module}
```

This cross-checks every element your test cases reference against the contract and
reports: missing selectors, stale elements, ambiguous selectors, and protected pages
without auth. Broken selectors found now cost minutes; found at test runtime they cost
hours of confusing failures.

**Done when:** the BLOCKERS section is empty. Otherwise → step 6.

---

## Step 6 — Fix what the audit found

The audit's FIX PLAN tells you which pages need a re-scrape (auth comes from `.env`,
set in step 1):

```
/rescrape {app} /the/missing/path
```

The re-scrape **merges** into the existing contract (nothing is deleted; vanished
elements are marked `stale`) and prints which test cases are affected. Read the
generated `{app}-contract-diff.md` to see exactly what changed.

Only edit the contract JSON by hand for elements the scraper genuinely can't reach
(e.g. revealed only by complex interactions).

Repeat steps 5–6 until the audit is clean.

---

## Step 7 — Generate test scripts

Per flow:

```
/playwright-gen {module} {FLOW-ID}     # browser E2E spec + page objects
/script-gen {module} {FLOW-ID}         # API/integration specs + fixture stubs + seed script (needs step 2)
```

**Verify:** files appear under `data/output/{app}/tests/scripts/` (`e2e/`, `pages/`,
`api/`, `fixtures/`). Skim one spec — every test should map to a YAML case ID.

⚠️ The fixture files generated here are **empty stubs**. Tests will compile but fail
until step 8.

---

## Step 8 — Fill fixtures and seed data (most-forgotten step)

Test cases reference data by name (`test_data_ref`); this step provides the actual data.

```
/fixture-fill {module} {FLOW-ID}
```

This fills each stub with *scenario-correct* data: valid realistic values for happy
paths, deliberately duplicated/expired/oversized values for edge cases, low-permission
actors for RBAC checks.

**Verify:** open `tests/scripts/fixtures/{module}/{FLOW-ID}.fixtures.ts` — no empty
strings or TODOs left. Check the seed script (`fixtures/seeds/`) creates any records
that edge cases assume already exist (e.g. the "duplicate" a duplicate-test collides with).

**Common mistake:** running tests with unfilled stubs. The failures look like app bugs
("required field missing") but are just empty fixture strings.

---

## Step 9 — Compile check

```bash
cd data/output/{app}
npm install
npx tsc --noEmit
```

Errors? Paste them into `/compile-fix <output>` — it fixes types without touching test
logic. Never debug test failures on code that doesn't compile.

---

## Step 10 — Environment and auth setup

```bash
cd data/output/{app}
cp .env.qa.example .env.qa     # set QA_UI_BASE_URL to the app's QA URL
npx playwright install chromium
```

For tests on protected pages, capture a login session once per actor:

```bash
npx playwright codegen {url}/login --save-storage=tests/scripts/fixtures/auth/{actor}.json
```

Log in manually in the window that opens, then close it. The specs reference these
files via `storageState` — the actor names must match the YAML `actors`.

---

## Step 11 — Run the tests

```
/run-tests {module}          # or a FLOW-ID, or @smoke
```

This re-checks env/deps/compile/auth fixtures, runs the scoped suite, and prints a
pass/fail summary. Manually: `npx playwright test tests/scripts/e2e/{module}/` from
`data/output/{app}/`. Reports: `playwright-report/` (HTML), `npm run report` (Allure).

---

## Step 12 — Triage failures

Do not start "fixing" failing tests one by one. Classify them first:

```
/triage
```

Every failure lands in one bucket with a recommended action:

| Bucket | Meaning | Fix |
|---|---|---|
| STALE SELECTOR | app's DOM changed | `/rescrape` → regenerate spec |
| TEST BUG | the test itself is wrong | `/fix-assertion` |
| FIXTURE / DATA | bad or missing test data | `/fixture-fill` / fix seed |
| ENV / SETUP | wrong URL, missing auth file | fix `.env.qa` / step 10 |
| FLAKY | timing race | add proper wait in the page object |
| LIKELY REAL DEFECT | the app is broken | file a bug — never change the test to pass |

Golden rule: **never weaken or delete an assertion to make a test green.**

---

## When the app changes later

```
/rescrape {app}        → read the diff
/selector-audit        → see which tests are affected
regenerate affected specs (/playwright-gen) → /run-tests → /triage
```

---

## Final checklist

- [ ] Contract covers all pages, including logged-in ones
- [ ] Swagger contract added (if API tests wanted)
- [ ] One test plan per module, reviewed by a human
- [ ] YAML cases generated, overlap checked
- [ ] `/selector-audit` shows zero blockers
- [ ] Specs generated (E2E + API)
- [ ] Fixtures filled — no empty stubs
- [ ] `tsc --noEmit` passes
- [ ] `.env.qa` + auth storage states in place
- [ ] Suite runs; failures triaged, not patched over
