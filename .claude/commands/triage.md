Triage failing Playwright tests: classify each failure and route it to the right fix. Usage: /triage [paste failures, or leave empty to read the last report]

---

## Setup

1. Locate the active app: `ls -lt data/output/` → most recent directory with workspace.json.
2. Failure source, in order of preference:
   - $ARGUMENTS if failures were pasted
   - `data/output/{app}/test-results/` (error context, traces) and `playwright-report/`
   - otherwise ask the user to run /run-tests first
3. Read `data/output/{app}/workspace.json` → contract path; read the contract and, if present,
   the `-diff.md` report next to it.
4. For each failing test, read its spec file, the source YAML case (the `YAML_SOURCE` /
   `allure.tms` annotation points to it), and the relevant POM.

---

## Classification

Assign every failure exactly one category, with evidence:

| Category | Typical evidence | Route |
|---|---|---|
| STALE SELECTOR | locator timeout / strict-mode violation; element stale in contract or listed in diff report | /rescrape then /playwright-gen |
| TEST BUG | wrong assertion or step translation; app behaves correctly when you trace the flow | /fix-assertion (or /strengthen-assertion if the check is too weak) |
| FIXTURE / DATA | seed failed, placeholder data, duplicate-record collisions, `test_data_ref` stub | /fixture-fill or fix the seed script |
| ENV / SETUP | connection refused, DNS, 502s, missing .env value, missing auth storageState | fix .env.qa / auth fixture; re-run |
| FLAKY | timing-dependent, passes on retry, race on hydration | add proper wait in POM, not a sleep |
| LIKELY REAL DEFECT | app returns wrong result and the test, selector, data, and env all check out | report to the team — do NOT change the test to make it pass |

Rules:
- Check the contract diff FIRST — a stale selector explains failures faster than reading specs.
- LIKELY REAL DEFECT requires eliminating the other five categories; say what you ruled out.
- Never weaken or delete an assertion to make a test green.

---

## Output

1. **TRIAGE TABLE** — case_id | spec file | category | evidence (one line) | recommended action.
2. **GROUPED ACTIONS** — the deduplicated fix list (e.g. "one /rescrape covers these 4
   failures", "FLOW-X needs /fixture-fill"), in suggested execution order.
3. **DEFECT REPORTS** — for each LIKELY REAL DEFECT: steps to reproduce, expected vs actual,
   the YAML case and contract elements involved — ready to paste into a bug tracker.

Do not modify any file. Only produce the triage report; apply fixes only when the user
asks (e.g. by invoking the routed skill).
