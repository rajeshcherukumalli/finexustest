Generate a test plan markdown file from the UI contract for a module. Usage: /testplan-gen <module> [optional intent, e.g. "footer links only"]

---

## Setup

1. Locate the active app: run `ls data/output/` and pick the directory that contains a workspace.json.
   If multiple exist, use the one most recently modified (`ls -lt data/output/`).
2. Read `data/output/{app}/workspace.json` → get `contract_path` and base URL.
3. Read the contract file (strip leading `/` if it is an absolute path under the repo root).
4. Read existing plans in `data/output/{app}/tests/testplan/` and existing YAML under
   `tests/testcases/` to learn the flow-ID conventions already in use and to avoid
   duplicating coverage (if overlap looks likely, suggest running /overlap-analysis first).

---

## Scope selection

From the contract, select pages and elements relevant to the module in $ARGUMENTS:
- Match on page_id, path, element labels, and regions (nav, footer, form, etc.).
- Respect any intent qualifier in $ARGUMENTS (e.g. "login flows for clerk actor only").
- Skip elements marked `stale: true` — flag them in the Warnings section instead.
- Note `is_protected: true` pages: their flows need an authenticated actor and an RBAC check.

---

## Output

Write `data/output/{app}/tests/testplan/{module}.md` (kebab-case the module name) with
exactly this structure — /testcase-gen depends on it:

```markdown
# Test plan: {module}

<!-- generated from {contract_filename} | app: {app_title} -->

## Module purpose
{2-4 sentences: what this module verifies and what is explicitly out of scope}

---

## Actors
| Actor | Description |
|---|---|

---

## Flows to test
| Flow ID | Description | Priority |
|---|---|---|

---

## Key assertions
- {bullet list of the cross-flow assertions, referencing contract fields}

---

## Per-flow notes

### {FLOW-ID} — {flow title}

**Page:** `{page_id}` | **Path:** `{path}`

{starting state and reset behaviour between steps}

| Step | Element ID | Label | Expected pathname | Assert kind |
|---|---|---|---|---|

**Selectors to use:**
- `{element_id}`: {selectors.playwright from contract, with disambiguation notes}

**Edge cases:**
- {bullets: protected redirects, duplicate selectors, dynamic content}
```

---

## Rules

- Flow IDs: short module prefix + two-digit number (e.g. NAV-01, AUTH-03); never reuse an
  ID that already exists in tests/testcases/ or another plan.
- Every element referenced in a step table must exist in the contract with its real
  `element_id` — never invent IDs.
- Copy selectors verbatim from `element.selectors.playwright`; if empty, write
  `MISSING SELECTOR` and list the element in Warnings.
- Use `QA_BASE_URL` placeholders in prose, but show the real base URL once in per-flow notes.
- Priorities: P0 for core happy paths, P1 for secondary navigation/variants, P2 for cosmetic.

---

After writing the file, print:
- A table: flow_id | description | priority | page_id
- Warnings: stale elements skipped, elements with missing selectors, suspected overlap
  with existing plans (with the suggested /overlap-analysis command).
