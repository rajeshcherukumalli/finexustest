"""Intent-aware contract slimming for LLM test-plan and testcase prompts."""

from __future__ import annotations

import re
from typing import Any

from lib.contract import Contract, _slim_element

_STOPWORDS = frozenset({
    "a", "an", "the", "to", "and", "or", "for", "on", "in", "at", "is", "are", "be",
    "with", "from", "go", "open", "click", "verify", "confirm", "test", "all", "each",
    "every", "should", "must", "that", "this", "user", "page", "into", "via", "using",
    "then", "when", "after", "before", "their", "they", "them", "its", "it", "as",
    "by", "of", "up", "down", "out", "about", "what", "how", "can", "will", "want",
    "wants", "like", "make", "sure", "check", "see", "show", "display", "visible",
    "works", "work", "working", "navigate", "navigation", "link", "links", "menu",
    "header", "footer", "section", "content", "list", "load", "loads", "loading",
})

_NAV_INTENT_RE = re.compile(
    r"\b(nav|navigation|menu|links?|sitemap|routes?|header|footer|home\s*page)\b",
    re.I,
)
_AUTH_INTENT_RE = re.compile(
    r"\b(login|log\s*in|auth|sign\s*in|sign\s*up|register|otp|mobile|password|credential)\b",
    re.I,
)
_FILL_INTENT_RE = re.compile(r"\b(search|fill|type|enter|input|submit|query)\b", re.I)
_ALL_NAV_RE = re.compile(r"\b(all|every|each)\b.*\b(nav|link|menu|header)\b", re.I)


def infer_module_from_intent(user_intent: str) -> str:
    if _AUTH_INTENT_RE.search(user_intent):
        return "auth"
    if _NAV_INTENT_RE.search(user_intent):
        return "navigation"
    return "content"


def tokenize_intent(user_intent: str) -> list[str]:
    """Extract searchable tokens and quoted phrases from user intent."""
    text = user_intent.lower()
    phrases: list[str] = []
    for match in re.finditer(r'"([^"]+)"|\'([^\']+)\'', text):
        phrase = (match.group(1) or match.group(2) or "").strip().lower()
        if phrase:
            phrases.append(phrase)
            phrases.extend(_tokenize_fragment(phrase))

    bare = re.sub(r'"[^"]*"|\'[^\']*\'', " ", text)
    tokens = _tokenize_fragment(bare)
    seen: set[str] = set()
    ordered: list[str] = []
    for token in phrases + tokens:
        if token and token not in seen:
            seen.add(token)
            ordered.append(token)
    return ordered


def _tokenize_fragment(text: str) -> list[str]:
    raw = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in raw if len(t) > 1 and t not in _STOPWORDS]


def _normalize_path(path: str | None) -> str:
    if not path:
        return "/"
    cleaned = path.split("?")[0].split("#")[0]
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return cleaned.rstrip("/") or "/"


def _page_aliases(page: dict) -> set[str]:
    page_id = str(page.get("page_id", ""))
    path = _normalize_path(page.get("path"))
    aliases = {page_id, page_id.replace("_", "-"), page_id.replace("-", "_")}
    slug = path.strip("/").replace("-", "_")
    if slug:
        aliases.add(slug)
        aliases.add(slug.replace("_", ""))
        for part in slug.split("_"):
            if len(part) > 2:
                aliases.add(part)
    title = str(page.get("title", "")).lower()
    if title:
        aliases.update(_tokenize_fragment(title))
    return {a.lower() for a in aliases if a}


def _search_blob(*parts: str | None) -> str:
    return " ".join(p.lower() for p in parts if p).strip()


def _score_tokens(blob: str, tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    score = 0.0
    for token in tokens:
        if token in blob:
            score += 3.0
        elif len(token) > 3 and any(token in word or word in token for word in blob.split()):
            score += 1.5
    return score


def score_page(page: dict, tokens: list[str], intent_lower: str) -> float:
    aliases = _page_aliases(page)
    score = 0.0
    for token in tokens:
        if token in aliases:
            score += 10.0
        if any(token in alias or alias in token for alias in aliases if len(alias) > 2):
            score += 4.0

    blob = _search_blob(
        page.get("page_id"),
        page.get("path"),
        page.get("title"),
        page.get("description"),
        page.get("page_type"),
    )
    score += _score_tokens(blob, tokens)

    path = _normalize_path(page.get("path"))
    if path != "/" and path.strip("/") in intent_lower.replace(" ", ""):
        score += 6.0

    priority = str(page.get("test_priority", "")).lower()
    if priority == "high":
        score += 0.5
    return score


def score_element(
    element: dict,
    tokens: list[str],
    *,
    target_paths: set[str] | None = None,
) -> float:
    blob = _search_blob(
        element.get("element_id"),
        element.get("label"),
        element.get("description"),
        element.get("target_path"),
        element.get("role"),
        element.get("fragment"),
    )
    score = _score_tokens(blob, tokens)

    target_path = _normalize_path(element.get("target_path"))
    if target_paths and target_path in target_paths:
        score += 12.0

    role = str(element.get("role", "")).lower()
    if role in {"input", "textbox", "searchbox", "textarea"} and _FILL_INTENT_RE.search(
        " ".join(tokens)
    ):
        score += 6.0
    if role in {"button", "link"} and target_paths and target_path in target_paths:
        score += 8.0

    region = str(element.get("region", "")).lower()
    if region in {"header", "nav", "navigation"}:
        score += 1.0
    return score


def resolve_target_pages(
    contract: Contract,
    user_intent: str,
    module: str,
    *,
    max_pages: int = 6,
) -> list[str]:
    """Return ordered page_ids most relevant to the user intent."""
    tokens = tokenize_intent(user_intent)
    intent_lower = user_intent.lower()

    if module == "navigation":
        return _resolve_navigation_pages(contract, tokens, intent_lower, max_pages)
    if module == "auth":
        return _resolve_auth_pages(contract, max_pages)

    return _resolve_content_pages(contract, tokens, intent_lower, max_pages)


def _resolve_navigation_pages(
    contract: Contract,
    tokens: list[str],
    intent_lower: str,
    max_pages: int,
) -> list[str]:
    home = contract.get_page("home")
    sequence = ["home"] if home else []

    if contract.home_navigation:
        if _ALL_NAV_RE.search(intent_lower) or not tokens:
            return sequence[:max_pages]

        matched_paths: set[str] = set()
        for entry in contract.home_navigation:
            blob = _search_blob(
                entry.get("element_id"),
                entry.get("label"),
                entry.get("target_path"),
                entry.get("raw_href"),
            )
            if _score_tokens(blob, tokens) > 0:
                matched_paths.add(_normalize_path(entry.get("target_path")))

        if matched_paths:
            for route in contract.route_index:
                if _normalize_path(route.get("path")) in matched_paths:
                    pid = route.get("page_id")
                    if pid and pid not in sequence:
                        sequence.append(str(pid))
        return sequence[:max_pages]

    scored = [
        (score_page(page, tokens, intent_lower), page.get("page_id"))
        for page in contract.pages
        if page.get("page_type") in {"nav", "dashboard"} or page.get("page_id") == "home"
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    for _, page_id in scored:
        if page_id and page_id not in sequence:
            sequence.append(str(page_id))
        if len(sequence) >= max_pages:
            break
    return sequence[:max_pages]


def _resolve_auth_pages(contract: Contract, max_pages: int) -> list[str]:
    sequence: list[str] = []
    for page in contract.pages:
        if page.get("page_type") == "login" or page.get("is_protected"):
            pid = page.get("page_id")
            if pid and pid not in sequence:
                sequence.append(str(pid))
    if not sequence:
        home = contract.get_page("home")
        if home:
            sequence.append("home")
    return sequence[:max_pages]


def _resolve_content_pages(
    contract: Contract,
    tokens: list[str],
    intent_lower: str,
    max_pages: int,
) -> list[str]:
    home = contract.get_page("home")
    sequence = ["home"] if home else []

    scored: list[tuple[float, str]] = []
    for page in contract.pages:
        page_id = str(page.get("page_id", ""))
        if page_id == "home":
            continue
        score = score_page(page, tokens, intent_lower)
        if score > 0:
            scored.append((score, page_id))

    scored.sort(key=lambda item: item[0], reverse=True)
    if scored:
        top_score = scored[0][0]
        threshold = max(6.0, top_score * 0.45)
        for score, page_id in scored:
            if score < threshold and len(sequence) > 1:
                break
            if page_id not in sequence:
                sequence.append(page_id)
            if len(sequence) >= max_pages:
                break
    elif len(sequence) == 1:
        fallback = sorted(
            contract.pages,
            key=lambda p: 0 if p.get("page_id") == "home" else 1,
        )
        for page in fallback[1 : max_pages]:
            pid = page.get("page_id")
            if pid and pid not in sequence:
                sequence.append(str(pid))
    return sequence[:max_pages]


def _target_paths_for_sequence(contract: Contract, page_ids: list[str]) -> set[str]:
    paths: set[str] = set()
    for page_id in page_ids:
        page = contract.get_page(page_id)
        if page:
            paths.add(_normalize_path(page.get("path")))
    return paths


def _slim_page_elements(
    page: dict,
    tokens: list[str],
    *,
    target_paths: set[str],
    max_elements: int,
    include_nav_to_targets: bool,
) -> list[dict]:
    elements = page.get("elements", [])
    scored: list[tuple[float, dict]] = []
    for element in elements:
        score = score_element(element, tokens, target_paths=target_paths)
        if include_nav_to_targets:
            role = str(element.get("role", "")).lower()
            path = _normalize_path(element.get("target_path"))
            if role in {"link", "button"} and path in target_paths:
                score += 15.0
        if _FILL_INTENT_RE.search(" ".join(tokens)):
            role = str(element.get("role", "")).lower()
            if role in {"input", "textbox", "searchbox", "textarea"}:
                score += 5.0
        if score > 0:
            scored.append((score, element))

    scored.sort(key=lambda item: item[0], reverse=True)
    if not scored and elements:
        scored = [(0.0, e) for e in elements[:max_elements]]

    return [_slim_element(e) for _, e in scored[:max_elements]]


def _slim_forms(page: dict, tokens: list[str], max_forms: int = 3) -> list[dict]:
    forms = page.get("forms", [])
    if not forms:
        return []
    if not _FILL_INTENT_RE.search(" ".join(tokens)):
        return forms[:max_forms]

    scored: list[tuple[float, dict]] = []
    for form in forms:
        blob = _search_blob(form.get("form_id"), form.get("description"))
        for field in form.get("fields", []):
            blob += " " + _search_blob(
                field.get("field_id"),
                field.get("label"),
                field.get("description"),
            )
        scored.append((_score_tokens(blob, tokens), form))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [form for score, form in scored[:max_forms] if score > 0] or forms[:max_forms]


def _filter_home_navigation(
    contract: Contract,
    tokens: list[str],
    intent_lower: str,
    module: str,
) -> list[dict]:
    nav = contract.home_navigation
    if not nav:
        return []
    if module != "navigation":
        return []
    if _ALL_NAV_RE.search(intent_lower) or not tokens:
        return list(nav)

    filtered: list[dict] = []
    for entry in nav:
        blob = _search_blob(
            entry.get("element_id"),
            entry.get("label"),
            entry.get("target_path"),
            entry.get("raw_href"),
        )
        if _score_tokens(blob, tokens) > 0:
            filtered.append(entry)
    return filtered or list(nav)


def slim_contract_for_intent(
    contract: Contract,
    user_intent: str,
    *,
    max_pages: int = 6,
    max_elements_per_page: int = 25,
) -> tuple[str, dict[str, Any]]:
    """
    Build a minimal contract slice for LLM prompts from full contract + user intent.

    Returns (module, slice_dict). The slice keeps only pages, elements, forms, and
    navigation entries that match the stated test intent.
    """
    module = infer_module_from_intent(user_intent)
    tokens = tokenize_intent(user_intent)
    intent_lower = user_intent.lower()
    page_sequence = resolve_target_pages(
        contract, user_intent, module, max_pages=max_pages
    )
    target_paths = _target_paths_for_sequence(contract, page_sequence)

    primary_targets = set(page_sequence[1:]) if len(page_sequence) > 1 else set()

    slim_pages: list[dict] = []
    for page_id in page_sequence:
        page = contract.get_page(page_id)
        if not page:
            continue
        is_home = page_id == "home"
        element_cap = (
            min(max_elements_per_page, 12)
            if is_home and module == "content" and primary_targets
            else max_elements_per_page
        )
        elements = _slim_page_elements(
            page,
            tokens,
            target_paths=target_paths,
            max_elements=element_cap,
            include_nav_to_targets=is_home and module == "content",
        )
        slim_pages.append({
            "page_id": page.get("page_id"),
            "path": page.get("path"),
            "url": page.get("url"),
            "title": page.get("title"),
            "description": page.get("description"),
            "page_type": page.get("page_type"),
            "test_priority": page.get("test_priority"),
            "is_protected": page.get("is_protected"),
            "elements": elements,
            "forms": _slim_forms(page, tokens),
        })

    route_ids = {p.get("page_id") for p in slim_pages}
    route_index = [r for r in contract.route_index if r.get("page_id") in route_ids]

    result: dict[str, Any] = {
        "contract_version": contract.version,
        "application": contract.raw.get("application", {}),
        "module": module,
        "page_sequence": page_sequence,
        "route_index": route_index,
        "pages": slim_pages,
    }

    home_nav = _filter_home_navigation(contract, tokens, intent_lower, module)
    if home_nav:
        result["home_navigation"] = home_nav

    return module, result
