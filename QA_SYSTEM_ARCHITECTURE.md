# QA Automation — Detailed Architecture

> App-agnostic pipeline: Scrape website → UI Contract JSON → Test Plan → YAML Testcase → Playwright E2E spec → Run

---

## 1. High-Level System Overview

```mermaid
graph TD
    subgraph UI["React Frontend (port 3000)"]
        A1[Apps Page]
        A2[Extract Contract / NewRunPage]
        A3[App Workspace Page]
        A4[Job Detail Page]
        A5[App Artifacts Page]
    end

    subgraph API["FastAPI Backend (port 8000)"]
        B1["/api/jobs — jobs.py"]
        B2["/api/apps — apps.py"]
        B3["/api/apps/{slug}/... — workspace.py"]
        B4[Health Endpoint]
    end

    subgraph Core["Core Services"]
        C1[job_runner.py\nSingle-worker thread pool]
        C2[artifacts.py\nFile browser + download]
        C3[workspace_edit.py\nManual save plan/testcase]
    end

    subgraph Generators["Generators"]
        D1[test_plan_generator.py]
        D2[testcase_generator.py]
        D3[spec_generator.py]
    end

    subgraph Libs["Library Layer"]
        E1[lib/contract.py\nContract dataclass + slicing]
        E2[lib/intent_extractor.py\nJourney extraction]
        E3[lib/llm.py\nOpenAI gpt-4o-mini]
        E4[lib/workspace.py\nworkspace.json registry]
        E5[lib/playwright_run.py\nPlaywright execution]
        E6[lib/scrape_auth.py\nLogin detection]
        E7[scraper.py\nPlaywright crawler]
    end

    subgraph FS["Filesystem — data/"]
        F1["contracts/{app}-contract.json"]
        F2["output/{app}/workspace.json"]
        F3["output/{app}/tests/testplan/plan-{id}.md"]
        F4["output/{app}/tests/testcases/{id}/case.yaml"]
        F5["output/{app}/tests/scripts/e2e/{id}/case.e2e.spec.ts"]
        F6["output/{app}/tests/scripts/pages/*.ts (POMs)"]
        F7["jobs/{job_id}/status.json + job.log"]
    end

    UI --> API
    API --> Core
    Core --> Generators
    Core --> Libs
    Generators --> Libs
    Libs --> FS
    Core --> FS
```

---

## 2. Intent-Driven Workflow (Step by Step)

```mermaid
flowchart TD
    START([User opens UI]) --> APPS[Apps Page\nLists apps from data/output/]
    APPS --> WS[Workspace Page]

    subgraph STEP0["Step 0 — Extract Contract"]
        S0A[User enters URL + optional auth] --> S0B["POST /api/jobs/scrape"]
        S0B --> S0C[scraper.py\nPlaywright headless crawl]
        S0C --> S0D["Login detection\nlib/scrape_auth.py\nLLM + heuristics"]
        S0D --> S0E["Builds contract v2.0.0 JSON\nper-page: elements, forms, links, inputs\nselectors: playwright + xpath\nregion: header/footer/nav/content"]
        S0E --> S0F["Writes data/contracts/{app}-contract.json"]
        S0F --> S0G[workspace.json created/updated]
    end

    subgraph STEP1["Step 1 — Generate Test Plan"]
        S1A[User types intent\ne.g. 'Verify all nav links'] --> S1B["POST /api/apps/{slug}/generate/plan\nbody: { user_intent }"]
        S1B --> S1C[job_runner: start_job 'plan']
        S1C --> S1D[load_contract → Contract dataclass]
        S1D --> S1E["intent_extractor.extract_journey()\nResolves page sequence\nfrom contract.resolve_target_pages()"]
        S1E --> S1F{"Journey route\nconstruction"}
        S1F --> S1G["_pick_nav_element()\nScores elements by\ntarget_path + label + region"]
        S1G --> S1H{"Ambiguous?\ntied score"}
        S1H -- Yes --> S1I["LLM disambiguate\nintent_journey_disambiguate_prompt"]
        S1H -- No --> S1J
        S1I --> S1J["Journey: page_sequence + route steps\n+ fill actions + assertions"]
        S1J --> S1K["contract.slice_for_journey()\nTrims contract to relevant pages\nfor LLM prompt"]
        S1K --> S1L["test_plan_intent_prompt()\n→ OpenAI gpt-4o-mini\ntemp=0.2, max_tokens=2500"]
        S1L --> S1M["Writes plan-uuid8.md\nwith YAML frontmatter:\nplan_id, user_intent, module,\npage_sequence, route, created_at"]
        S1M --> S1N["workspace.add_plan()\nRegisters in workspace.json"]
    end

    subgraph STEP2["Step 2 — Generate Test Case"]
        S2A["User selects plan from dropdown"] --> S2B["POST /api/apps/{slug}/generate/testcase\nbody: { plan_id }"]
        S2B --> S2C["job_runner: start_job 'testcase'"]
        S2C --> S2D["load plan markdown\nparse_plan_frontmatter()\nExtract journey from frontmatter"]
        S2D --> S2E{"Saved journey\nhas route?"}
        S2E -- Yes --> S2F["Reconstruct Journey\nfrom frontmatter steps"]
        S2E -- No --> S2G["Re-run extract_journey()\nwith LLM"]
        S2F --> S2H
        S2G --> S2H["contract.slice_for_journey()\nSlim contract slice"]
        S2H --> S2I["testcase_yaml_prompt()\n→ OpenAI gpt-4o-mini JSON mode\ntemp=0.0, max_tokens=8000"]
        S2I --> S2J["_extract_flow_from_llm_result()\nHandles wrapped flow/flows/testcase keys"]
        S2J --> S2K["_normalize_flow()\nAdds module, type, tags, actors,\nenvironments, case IDs"]
        S2K --> S2L["contract_validate.validate_flow()\nChecks page_ids + element_ids\nagainst contract"]
        S2L --> S2M["Writes case.yaml\ndata/output/{app}/tests/testcases/{plan_id}/case.yaml"]
        S2M --> S2N["workspace.register_testcases()"]
    end

    subgraph STEP3["Step 3 — Generate Playwright Spec"]
        S3A["User selects plan (optional: LLM toggle)"] --> S3B["POST /api/apps/{slug}/generate/spec\nbody: { plan_id, use_llm_spec }"]
        S3B --> S3C["job_runner: start_job 'spec'"]
        S3C --> S3D["scaffold_app()\nWrites package.json, tsconfig.json,\nplaywright.config.ts, helper TS files\nskips if exists"]
        S3D --> S3E["generate_spec_for_plan()\nLoads case.yaml"]
        S3E --> S3F{"Is nav case?\nmodule=navigation +\nstructured nav_links"}
        S3F -- Yes --> S3G["_emit_nav_case_body()\nFor each home_navigation link:\ngoto('/') → click → URL assert"]
        S3F -- No --> S3H["_emit_deterministic_case_body()\nResolves element_refs → locators\n→ action expressions"]
        S3G --> S3I
        S3H --> S3I{"use_llm_spec OR\ncoverage < 50%?"}
        S3I -- Yes --> S3J["spec_case_prompt() → LLM\ntemp=0.2, max_tokens=2000"]
        S3J --> S3Jb["_sanitize_llm_body()\nStrips invented POM methods\n+ non-contract selectors\nAdds .first() before actions"]
        S3Jb --> S3K
        S3I -- No --> S3K["Assemble test() block"]
        S3K --> S3L["Generate Page Object Models\ngenerate_pom() for each page\nLocator method per element_id"]
        S3L --> S3M["workspace.register_spec()"]
    end

    subgraph STEP4["Step 4 — Play (Run)"]
        S4A["User clicks Play button"] --> S4B["POST /api/apps/{slug}/run/spec\nbody: { plan_id, spec_path }"]
        S4B --> S4C["job_runner: start_job 'run'"]
        S4C --> S4D{"PLAYWRIGHT_HEADED\nenabled?"}
        S4D -- No --> S4E["Error: not enabled\nRequires docker-compose.headed.yml"]
        S4D -- Yes --> S4F["ensure_env_qa()\nWrites .env.qa with QA_UI_BASE_URL"]
        S4F --> S4G["ensure_node_deps()\nnpm install + playwright install chromium\ncached via .deps-installed marker"]
        S4G --> S4H["subprocess: npx playwright test\n--headed --reporter=html,list"]
        S4H --> S4I["Returns exit_code\npassed = exit_code == 0\nreport_path = playwright-report/index.html"]
        S4I --> S4J["Frontend shows Pass/Fail\n+ Show Report button\nserves HTML inline via iframe"]
    end

    WS --> STEP0
    STEP0 --> STEP1
    STEP1 --> STEP2
    STEP2 --> STEP3
    STEP3 --> STEP4
```

---

## 3. Job Runner — Single Worker Model

```mermaid
sequenceDiagram
    participant UI as React Frontend
    participant API as FastAPI Route
    participant JR as job_runner.py
    participant FS as Filesystem jobs/
    participant EX as Job Executor Thread

    UI->>API: POST /api/apps/{slug}/generate/plan
    API->>JR: start_job("plan", request)
    JR->>JR: Acquire _lock\nCheck _active_job_id
    alt Job already running
        JR-->>API: raise RuntimeError
        API-->>UI: 409 Conflict
    else Slot free
        JR->>JR: job_id = uuid4 hex 12 chars
        JR->>FS: Write status.json {status: queued}
        JR->>EX: threading.Thread(_run_job).start()
        JR-->>API: JobResponse {status: queued}
        API-->>UI: 202 Accepted + job_id
    end

    EX->>FS: Update status.json {status: running}
    EX->>FS: Attach FileHandler to job.log
    EX->>EX: _execute_job() → _run_plan()
    EX->>FS: Update status.json {status: completed, result}
    EX->>EX: Release _active_job_id = None

    loop Poll every ~2s
        UI->>API: GET /api/jobs/{job_id}
        API->>FS: Read status.json
        API-->>UI: JobResponse
        UI->>UI: Check status == completed or failed
    end

    UI->>API: GET /api/jobs/{job_id}/logs?offset=N
    API->>FS: Read job.log from offset
    API-->>UI: {content, offset, eof}
```

---

## 4. Contract Data Model (v2.0.0)

```mermaid
erDiagram
    CONTRACT {
        string contract_version "2.0.0"
        string app_name
        string base_url
        string scraped_at
    }
    URL_ENTRY {
        string page_key "snake_case key"
        string page_id
        string path
        string url
        string title
        string page_type "login|nav|dashboard|list|detail|form|unknown"
        string test_priority "high|medium|low"
        bool is_protected
        list aliases
    }
    PAGE_BUNDLE {
        string page_id
        string path
        string title
        string description
        string page_type
        list elements
        list forms
        list links "derived from elements role=link"
        list inputs "derived from elements role=input/textbox"
        list navigation "header/footer nav links"
    }
    ELEMENT {
        string element_id
        string role "button|link|textbox"
        string label
        string description
        string category "navigation|action"
        string target_path "resolved path incl fragment"
        string href
        string raw_href
        string fragment
        string region "header|footer|nav|content"
        object selectors
        object assert "kind + value for nav assertions"
    }
    SELECTORS {
        string playwright "page.getByRole expression"
        string xpath "xpath expression"
    }
    FORM {
        string form_id
        list fields
    }
    FORM_FIELD {
        string field_id
        string label
        string type "text|email|password"
        object selectors
    }

    CONTRACT ||--o{ URL_ENTRY : "urls[]"
    CONTRACT ||--o{ PAGE_BUNDLE : "pages keyed by page_key"
    PAGE_BUNDLE ||--o{ ELEMENT : "elements[]"
    PAGE_BUNDLE ||--o{ FORM : "forms[]"
    ELEMENT ||--|| SELECTORS : "selectors"
    FORM ||--o{ FORM_FIELD : "fields[]"
```

---

## 5. Workspace Registry (workspace.json)

```mermaid
erDiagram
    WORKSPACE {
        string app_slug
        string contract_path
        list plans
    }
    PLAN_ENTRY {
        string id "plan-uuid8"
        string user_intent
        string plan_path "tests/testplan/plan-id.md"
        string created_at
        list testcases
        list specs
    }
    TESTCASE_ENTRY {
        string flow_id "= plan_id"
        string path "tests/testcases/id/case.yaml"
        string title
        string case_count
        string case_titles
    }
    SPEC_ENTRY {
        string flow_id "= plan_id"
        string path "tests/scripts/e2e/id/case.e2e.spec.ts"
    }

    WORKSPACE ||--o{ PLAN_ENTRY : "plans[]"
    PLAN_ENTRY ||--o{ TESTCASE_ENTRY : "testcases[]"
    PLAN_ENTRY ||--o{ SPEC_ENTRY : "specs[]"
```

---

## 6. Intent Extractor — Journey Resolution

```mermaid
flowchart TD
    A["extract_journey(contract, user_intent)"] --> B["resolve_page_sequence()\ncontract.resolve_target_pages()\nScores pages by page_id, path, title, aliases\ntoken matching"]
    B --> C["seq = page_key list\ne.g. home, farmers_list"]
    C --> D["For each consecutive pair from-to:\n_pick_nav_element()"]
    D --> E["_nav_element_candidates(from_page, to_path, to_aliases)\nSearches: page.navigation + links + elements role=link/button"]
    E --> F["_score_nav_element()\n+10 exact target_path match\n+8 path_candidates_from_label match\n+5 alias substring match\n+2 region=header bonus"]
    F --> G{"Multiple tied\ncandidates?"}
    G -- "Yes + LLM" --> H["_disambiguate_with_llm()\nintent_journey_disambiguate_prompt\n→ OpenAI returns element_id"]
    G -- No --> I
    H --> I["JourneyStep(page_id, element_id,\naction=click, expect_path)"]
    I --> J{"Last page +\nfill value in intent?"}
    J -- Yes --> K["_find_input_on_page()\nScores inputs: search label +5, role +2\n→ JourneyStep(action=fill, value)"]
    J -- No --> L
    K --> L["Build assertions:\nurl_matches_route:{path}\nform_field_visible if fill step"]
    L --> M["_validate_journey()\nDrops steps where element not in contract\nEnsures min assertion: page_title_visible"]
    M --> N["Journey{page_sequence, route, assertions, warnings}"]
```

---

## 7. Spec Generator — Deterministic vs LLM Path

```mermaid
flowchart TD
    A["generate_spec_for_plan(contract, app_slug, plan_id)"] --> B["Load case.yaml\nParse flow: module, ui_pages, cases"]
    B --> C["scaffold_app()\npackage.json, tsconfig, playwright.config.ts,\nenv.ts, auth-fixture.ts\nskip if already exists"]
    C --> D["For each case in flow.cases:"]
    D --> E{"_is_nav_case?\nmodule=navigation +\nstructured nav_links with element_id or assert"}
    E -- Yes --> F["_emit_nav_case_body()\nFor each nav_link with route != '/':\n1. page.goto(start_path)\n2. click element\n3. assert URL or hash or title"]
    E -- No --> G["_emit_deterministic_case_body()\nFor each element_ref:\n  resolve → contract element\n  build action expression\n  URL assert from target_path\n  title assert"]
    F --> H["_case_element_coverage()\ncoverage = resolved_refs / total_refs"]
    G --> H
    H --> I{"use_llm_spec OR\ncoverage < 0.5?"}
    I -- Yes --> J["contract.slice_for_case(case)\nSlim contract to case pages/elements"]
    J --> K["spec_case_prompt() → LLM\ntemp=0.2, max_tokens=2000"]
    K --> L["_sanitize_llm_body()\nStrip invented POM methods\nStrip non-contract selectors\nAdd .first() before actions"]
    L --> M
    I -- No --> M["Assemble test() block\n_test_open_line(case_id, title)\nbody lines + closing bracket"]
    M --> N["Wrap in describe() block:\n_build_nav_links_constant()\n_resolve_start_path()\npage.goto(startPath)\nauth fixture setup"]
    N --> O["Generate Page Object Models\ngenerate_pom(page, ClassName)\nLocator methods per element_id\nForm field locators"]
    O --> P["Write case.e2e.spec.ts\nWrite PageName.ts POMs\nRegister spec in workspace.json"]
```

---

## 8. Scraper — Website Crawl & Contract Extraction

```mermaid
flowchart TD
    A["scrape_website(base_url, output_path, max_pages)"] --> B["Playwright: launch Chromium headless"]
    B --> C{"username + password\nprovided?"}
    C -- Yes --> D["Navigate to base_url\nLLM login detection\nFallback: heuristic_detect_login_form()\nFill credentials and submit"]
    C -- No --> E
    D --> E["BFS crawl from base_url\nUp to max_pages (default 20)"]
    E --> F["For each page:\n1. Extract all href links\n2. Classify: internal vs external\n3. Assign region: header/footer/nav/content\nfrom DOM ancestor\n4. Assign target_path incl. fragment\n5. Extract elements + forms + inputs\n6. Generate selectors: playwright + xpath\n7. LLM: classify page_type, test_priority"]
    F --> G["Build contract v2.0.0 JSON:\napplication: {name, base_url}\nurls: list of URL_ENTRY\npages: {page_key: PAGE_BUNDLE}\nextraction_metadata: {scraped_at, page_count}"]
    G --> H["Write to data/contracts/{app}-contract.json"]
    H --> I["Copy to data/output/{app}/{app}-contract.json\nartifact browser sync"]
    I --> J["ensure_workspace(app_slug)\nCreate or update workspace.json"]
```

---

## 9. API Route Map

```mermaid
graph LR
    subgraph JOBS["/api/jobs"]
        J1["POST /scrape → start_scrape_job"]
        J2["POST /pipeline → start_pipeline_job legacy"]
        J3["GET / → list_jobs limit=50"]
        J4["GET /{id} → get_job"]
        J5["GET /{id}/logs?offset → read_job_logs"]
    end

    subgraph APPS["/api/apps"]
        A1["GET / → list_apps"]
        A2["GET /{slug} → get_app_detail"]
        A3["GET /{slug}/files → list_files"]
        A4["GET /{slug}/files/content?path → read_file_content"]
        A5["GET /{slug}/files/download?path → download or zip"]
        A6["GET /{slug}/playwright-report/info"]
        A7["GET /{slug}/playwright-report/{path} → serve inline"]
    end

    subgraph WS["/api/apps/{slug} workspace"]
        W1["GET /workspace → sync_plans_from_disk + contract info"]
        W2["GET /contract → contract metadata + pages"]
        W3["POST /generate/plan → start_job plan"]
        W4["POST /generate/testcase → start_job testcase"]
        W5["POST /generate/spec → start_job spec"]
        W6["POST /run/spec → start_job run"]
        W7["PUT /plans/{plan_id} → write_plan manual edit"]
        W8["PUT /plans/{plan_id}/testcase → write_testcase + validate"]
    end
```

---

## 10. Filesystem Artifact Layout

```mermaid
graph TD
    ROOT["data/"]
    ROOT --> CONTRACTS["contracts/\napp-contract.json\ncanonical source of truth"]
    ROOT --> JOBS["jobs/\njob_id/\n  status.json\n  job.log"]
    ROOT --> OUTPUT["output/\napp/"]

    OUTPUT --> WS["workspace.json\nplan registry"]
    OUTPUT --> MANIFEST["manifest.json\npipeline_version, steps_run,\nflows_generated, contract_hash"]
    OUTPUT --> CONTRACT_COPY["app-contract.json\nartifact browser copy"]
    OUTPUT --> PKG["package.json\ntsconfig.json\nplaywright.config.ts\n.env.qa"]
    OUTPUT --> PW_REPORT["playwright-report/\nindex.html + assets"]
    OUTPUT --> TESTS["tests/"]

    TESTS --> TESTPLAN["testplan/\nplan-id.md\nYAML frontmatter + Markdown body"]
    TESTS --> TESTCASES["testcases/\nplan_id/\n  case.yaml"]
    TESTS --> SCRIPTS["scripts/"]

    SCRIPTS --> E2E["e2e/\nplan_id/\n  case.e2e.spec.ts"]
    SCRIPTS --> PAGES["pages/\nPageName.ts POMs"]
    SCRIPTS --> HELPERS["helpers/\nenv.ts\nauth-fixture.ts"]
    SCRIPTS --> FIXTURES["fixtures/\nauth/\n  actor.json Playwright storage state"]
```

---

## 11. Frontend Component Map

```mermaid
graph TD
    subgraph Router["App.tsx React Router"]
        R1["/ → AppsPage"]
        R2["/run → NewRunPage Extract Contract"]
        R3["/apps/:slug → AppArtifactsPage"]
        R4["/apps/:slug/workspace → AppWorkspacePage"]
        R5["/jobs/:id → JobDetailPage"]
    end

    subgraph WP["AppWorkspacePage — 4 cards"]
        Card0["Contract info\nbase_url, page count, page list"]
        Card1["1. Test Plan\nIntent textarea\nGenerate button\nPlan dropdown\nArtifactEditor plan.md"]
        Card2["2. Test Case\nPlan dropdown shared\nGenerate/Regenerate button\nArtifactEditor case.yaml"]
        Card3["3. Playwright\nPlan dropdown shared\nSpec list\nLLM toggle\nGenerate + Play buttons\nSpec code viewer\nRun result + Show Report"]
    end

    subgraph Polling["pollJobUntilDone()"]
        P1["GET /api/jobs/{id} every 2s\nUntil status = completed or failed\nTimeout: 10 min"]
    end

    subgraph Components["Shared Components"]
        C1["ArtifactEditor\nTextarea with Save/Discard\nDirty tracking + warnings"]
        C2["GenerateButton\nLoading spinner state"]
        C3["PlaywrightReportModal\niframe to playwright-report endpoint"]
    end

    Router --> WP
    WP --> Polling
    WP --> Components
```

---

## 12. LLM Usage Summary

| Step | Prompt Function | Model | temp | max_tokens | Output |
|------|----------------|-------|------|------------|--------|
| Journey disambiguation | `intent_journey_disambiguate_prompt` | gpt-4o-mini | 0.0 | 500 | `{element_id}` JSON |
| Test Plan | `test_plan_intent_prompt` | gpt-4o-mini | 0.2 | 2500 | Markdown body |
| Test Case | `testcase_yaml_prompt` | gpt-4o-mini | 0.0 | 8000 | JSON flow object |
| Playwright spec body | `spec_case_prompt` / `spec_body_prompt` | gpt-4o-mini | 0.2 | 2000 | TypeScript body |
| Login detection (scrape) | inline | gpt-4o-mini | 0.0 | 300 | JSON login form fields |

---

## 13. Contract Version Compatibility

```mermaid
flowchart LR
    A["load_contract(path)"] --> B["Read JSON\ncheck contract_version"]
    B --> C{"version?"}
    C -- "1.0.0 or 1.1.0\narray pages" --> D["_normalize_contract_v1()\nUpgrade to v2 in memory:\n- Build pages dict by page_key\n- Build urls list\n- Enrich target_paths\n- Strip route_index key"]
    C -- "2.0.0 list pages" --> D
    C -- "2.0.0 dict pages" --> E["_normalize_contract_v2_keys()\nNormalize page_key suffixes\nEnrich target_paths"]
    D --> F["Contract dataclass\n.validate()"]
    E --> F
```
