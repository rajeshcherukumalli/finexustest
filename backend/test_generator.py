"""
Test Generator (DEPRECATED)
---------------------------
Legacy page-level stub generator. Prefer the flow-based pipeline:

  python pipeline.py --contract <contract.json> --app <slug> --steps plan,yaml,spec

See generators/spec_generator.py and README.md.
"""

import os
import json
import logging
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def load_contract(path: str = "site_map.json") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _contract_base_url(contract: dict) -> str:
    return contract.get("application", {}).get("base_url") or contract.get("base_url", "")


def generate_tests_for_page(client: OpenAI, page: dict, base_url: str) -> str:
    """Ask LLM to generate a Playwright TypeScript test file for a single page."""

    elements_summary = [
        {
            "element_id": el.get("element_id"),
            "role": el.get("role"),
            "label": el.get("label"),
            "description": el.get("description"),
            "playwright": el.get("selectors", {}).get("playwright"),
            "xpath": el.get("selectors", {}).get("xpath"),
        }
        for el in page.get("elements", [])[:25]
    ]

    forms_summary = page.get("forms", [])[:5]

    prompt = f"""
You are a QA automation engineer. Generate a Playwright TypeScript test file for this page.

Page URL: {page.get('url')}
Page Title: {page.get('title')}
Page Type: {page.get('page_type')}
Test Priority: {page.get('test_priority')}
Is Protected (needs login): {page.get('is_protected')}
Page Description: {page.get('description', page.get('llm_notes', ''))}

Interactive elements (prefer playwright selectors; fall back to xpath):
{json.dumps(elements_summary, indent=2)}

Forms on page:
{json.dumps(forms_summary, indent=2)}

Rules:
1. Prefer page.getByRole / page.getByTestId / page.locator from selectors.playwright
2. Fall back to page.locator('xpath=...') only when playwright selector is empty
3. Tag tests: @smoke for high priority, @regression for medium, @integration for low
4. If is_protected is true, wrap tests in a describe block that uses adminAuth fixture
5. Generate:
   - 1 happy path test
   - 2-3 edge case tests relevant to the page type
   - 1 accessibility check (page has title, no broken links)
6. Use TypeScript, import from @playwright/test
7. Use descriptive test names informed by each element description
8. Add a comment at top with the page URL and page description
9. Do NOT use page.goto inside tests — assume the page is already loaded via beforeEach

Output ONLY valid TypeScript code, no explanation, no markdown fences.
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=1500,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning(f"Test generation failed for {page.get('url')}: {e}")
        return f"// Failed to generate tests for {page.get('url')}: {e}\n"


def generate_all_tests(
    sitemap_path: str = "site_map.json",
    output_dir: str = "generated_tests",
    priority_filter: str = "all",  # "high" | "medium" | "low" | "all"
) -> list[str]:
    """
    Consume UI action contract JSON and generate Playwright test files.
    """
    contract = load_contract(sitemap_path)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    base_url = _contract_base_url(contract)

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    generated_files = []
    pages = contract.get("pages", [])

    if priority_filter != "all":
        pages = [p for p in pages if p.get("test_priority") == priority_filter]

    priority_order = {"high": 0, "medium": 1, "low": 2}
    pages.sort(key=lambda p: priority_order.get(p.get("test_priority", "medium"), 1))

    log.info(f"Generating tests for {len(pages)} pages...")

    for i, page in enumerate(pages):
        page_id = page.get("page_id") or page.get("url", f"page_{i}")
        log.info(f"[{i+1}/{len(pages)}] Generating: {page_id}")

        safe_name = page_id or "home"
        filename = f"{output_dir}/{safe_name}.spec.ts"

        test_code = generate_tests_for_page(client, page, base_url)

        with open(filename, "w", encoding="utf-8") as f:
            f.write(test_code)

        generated_files.append(filename)
        log.info(f"  ✅ Written: {filename}")

    index_path = f"{output_dir}/_index.json"
    with open(index_path, "w") as f:
        json.dump({
            "contract_version": contract.get("contract_version"),
            "base_url": base_url,
            "total_generated": len(generated_files),
            "files": generated_files,
            "pages_summary": [
                {
                    "page_id": p.get("page_id"),
                    "url": p.get("url"),
                    "title": p.get("title"),
                    "page_type": p.get("page_type"),
                    "priority": p.get("test_priority"),
                    "is_protected": p.get("is_protected"),
                    "file": f"{output_dir}/{p.get('page_id', 'home')}.spec.ts",
                }
                for p in pages
            ],
        }, indent=2)

    log.info(f"\n✅ Done! {len(generated_files)} test files written to {output_dir}/")
    log.info(f"📋 Index: {index_path}")
    return generated_files


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate Playwright tests from UI action contract JSON")
    parser.add_argument("--sitemap", default="site_map.json", help="Path to contract JSON from scraper")
    parser.add_argument("--output", default="generated_tests", help="Output folder for test files")
    parser.add_argument("--priority", default="all", choices=["high", "medium", "low", "all"])
    args = parser.parse_args()

    generate_all_tests(
        sitemap_path=args.sitemap,
        output_dir=args.output,
        priority_filter=args.priority,
    )
