"""Overlap check between new plans/flows and existing YAML testcases."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)


def load_existing_flows(testcases_dir: Path) -> list[dict[str, Any]]:
    flows: list[dict[str, Any]] = []
    if not testcases_dir.exists():
        return flows
    for path in sorted(testcases_dir.rglob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        data["_path"] = str(path)
        flows.append(data)
    return flows


def extract_flow_ids_from_plan(plan_text: str) -> list[str]:
    ids: list[str] = []
    for line in plan_text.splitlines():
        stripped = line.strip()
        if "|" in stripped and not stripped.startswith("|--"):
            cells = [c.strip() for c in stripped.split("|") if c.strip()]
            if cells and "-" in cells[0] and cells[0][0].isalpha():
                flow_id = cells[0].split()[0]
                if flow_id.count("-") >= 1:
                    ids.append(flow_id)
    return ids


def check_overlaps(
    proposed_flow_ids: list[str],
    testcases_dir: Path,
) -> dict[str, list[str]]:
    existing = load_existing_flows(testcases_dir)
    existing_ids = {f.get("flow_id") for f in existing if f.get("flow_id")}

    exact = [fid for fid in proposed_flow_ids if fid in existing_ids]
    new = [fid for fid in proposed_flow_ids if fid not in existing_ids]

    report = {
        "exact_duplicates": exact,
        "new_flows": new,
        "existing_flow_ids": sorted(existing_ids),
    }

    if exact:
        log.warning("Overlap: exact duplicate flow IDs: %s", exact)
    else:
        log.info("Overlap check: %d new flow(s), no exact duplicates", len(new))

    return report
