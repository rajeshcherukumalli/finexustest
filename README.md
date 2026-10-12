# QA Automation

App-agnostic tooling: scrape a website → UI contract JSON → test plans → YAML testcases → Playwright E2E specs.

**Official workflow:** run each step locally in **Claude Code** or **Cursor** using [PROCESS.md](PROCESS.md) and the slash commands in `.claude/commands/`. No Docker or API key required when the `claude` CLI is installed and logged in. New to the process? Start with the step-by-step [GUIDE.md](GUIDE.md).

## Quick start (CLI + skills)

**Prerequisites**

1. [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) installed and logged in (`claude` on PATH). Uses your subscription — no `ANTHROPIC_API_KEY`.
2. Python 3.10+ and Node.js 20+ (for generated Playwright specs).

```bash
cd qa-automation/backend
pip install -r requirements.txt
playwright install chromium
cp ../.env.example ../.env
# Edit .env for scraper login if needed — see GUIDE.md step 1 (username/password, email/password, or mobile+OTP)
```

**End-to-end flow** — see [PROCESS.md](PROCESS.md):

| Step | Command (Claude Code / Cursor) |
|------|--------------------------------|
| 1 Scrape | `/rescrape <app> <url>` or `python scraper.py <url> --output ../data/contracts/<app>-contract.json` |
| 3 Test plan | `/testplan-gen <module>` |
| 4 Test cases | `/overlap-analysis <module>` then `/testcase-gen <module>` |
| 5 Selector audit | `/selector-audit <module>` |
| 6 Fix selectors | `/rescrape <app> [seed paths]` |
| 7 Test scripts | `/playwright-gen <module> <FLOW-ID>` (E2E), `/script-gen <module> <FLOW-ID>` (API) |
| 8 Fixtures | `/fixture-fill <module> <FLOW-ID>` |
| 9 Run + triage | `/run-tests <module>` then `/triage` |

Artifacts are written under `data/output/{app}/` (local, gitignored):

```
data/output/{app}/
  workspace.json
  tests/testplan/{module}.md
  tests/testcases/{module}/{FLOW-ID}.yaml
  tests/scripts/e2e/{module}/{FLOW-ID}.e2e.spec.ts
```

Canonical contract path: `data/contracts/{app}-contract.json`.

## Run generated Playwright tests (CLI)

```bash
cd data/output/{app}
cp .env.qa.example .env.qa   # set QA_UI_BASE_URL
npm install && npx playwright install chromium
npm run test:smoke           # or: npx playwright test
```

## Contract schema (v1.2.0)

Scrapes write `contract_version: 1.2.0` JSON with:

- **Per-page**: `auth_context`, `scrape_status`, `ready_state`
- **Per-element**: `raw_href`, `fragment`, `region`, `target_path`, `selectors.playwright`
- **`home_navigation`**: header/footer/nav links on `/` with `assert: { kind, value }`
- Re-scrapes merge into the existing contract and write `{app}-contract-diff.md`

v1.0.0 and v1.1.0 contracts still load.

## Project structure

```
qa-automation/
  PROCESS.md              # End-to-end process (official workflow)
  GUIDE.md                # Step-by-step guide for a new project (junior-friendly)
  .claude/commands/       # Slash-command skills for each step
  backend/
    scraper.py
    pipeline.py
    lib/llm.py            # shells out to `claude -p` (no API key in Python)
    generators/
  data/
    contracts/
    output/{app}/         # local workspace (gitignored)
  frontend/               # legacy web UI
  docker-compose.yml      # legacy Docker stack
```

## Legacy: Docker web UI (optional)

The React UI + FastAPI backend can still be run via Docker. This is **not** the team default workflow.

```bash
cp .env.example .env
# For Docker-only: set ANTHROPIC_API_KEY (claude CLI inside the container has no interactive login)

docker compose up --build
# UI: http://localhost:3000
# API: http://localhost:8000/api/health
```

Headed Playwright via Docker (X11 required):

```bash
xhost +local:docker
docker compose -f docker-compose.yml -f docker-compose.headed.yml up -d --build
```

See [QA_SYSTEM_ARCHITECTURE.md](QA_SYSTEM_ARCHITECTURE.md) for API and UI details.
