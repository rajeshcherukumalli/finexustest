Audit test cases and the contract for missing, stale, or broken selectors before spec generation. Usage: /selector-audit [module]

---

## Setup

1. Locate the active app: run `ls data/output/` and pick the directory that contains a workspace.json
   (most recently modified if multiple).
2. Read `data/output/{app}/workspace.json` → get `contract_path`; read the contract.
3. Read YAML test cases under `data/output/{app}/tests/testcases/` — all modules, or only
   `tests/testcases/$ARGUMENTS/` if a module was given.
4. If `{contract_path}-diff.md` (or `*-contract-diff.md` next to the contract) exists, read it.

---

## Checks

For every element referenced by a test case (in `ui_pages`, step text containing element IDs
or playwright expressions, and `rbac_checks`):

1. **Missing from contract** — element_id not found on any contract page.
2. **Empty selector** — element exists but `selectors.playwright` is empty/missing
   (CSS/XPath-only elements count: flag as FRAGILE, they fall back to XPath in the POM).
3. **Stale** — element or its page is marked `stale: true` in the merged contract.
4. **Ambiguous** — two or more elements on the same page share the same playwright/CSS
   selector (multi-match risk at runtime).
5. **Protected page, no auth** — case touches a page with `is_protected: true` but the flow
   has only an anonymous actor or no storageState fixture under tests/scripts/fixtures/auth/.

Also scan the contract itself (pages in scope) for elements with empty playwright selectors
that no test case references yet — these will bite future generation.

---

## Report

Print a report with these sections (omit empty ones):

1. **BLOCKERS** — missing-from-contract and empty-selector refs.
   Table: case file | case id | element_id | page_id | problem
2. **STALE** — refs to stale elements/pages, with `last_seen` if present.
3. **FRAGILE / AMBIGUOUS** — XPath-only fallbacks and duplicate selectors, with a
   suggested disambiguation (role+name, region anchor).
4. **AUTH GAPS** — protected pages without an auth fixture.
5. **FIX PLAN** — grouped by page: which pages need a re-scrape, with the exact
   `/rescrape` invocation (seed paths for unlinked pages, auth flags for protected ones),
   and which elements need manual contract edits because the scraper cannot reach them.

Do not modify any file. Only produce the report.
