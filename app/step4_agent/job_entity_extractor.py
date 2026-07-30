"""
app/step4_agent/job_entity_extractor.py — Job posting → structured entities.

The job-side counterpart to app/step2_nlp/ner_extraction_3.py's resume
extraction. Before this module existed, matcher.py had no real job-side
entities at all: "skills" came from skills_detected (populated only for
RemoteOK; always [] for Adzuna, despite a comment claiming otherwise), and
"experience"/"projects"/"certifications" were all the same raw job
description text repeated three times. That meant nothing about a job
posting was actually structured before being embedded and compared.

Deterministic, keyword/regex-based on purpose — this runs once per job at
fetch time (app/step4_agent/job_source_fetcher.py), every scheduled scan
cycle, so it has to stay cheap. No LLM/paid API call here; vocab lives in
config/*.json (not hardcoded in this file) so it can be extended without a
code change.

Public surface is exactly one function: extract_job_entities(). Callers
(job_source_fetcher.py) never need to know HOW extraction works — the
internals here could be swapped for an LLM-based implementation later
without touching any caller.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Pattern

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


def _load_json(filename: str) -> Any:
    path = _CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _compile_keyword_pattern(term: str) -> Pattern:
    # Word-boundary match, case-insensitive. re.escape so terms containing
    # regex-special characters (e.g. "C++", "C#", ".NET") match literally.
    # Boundary is "not adjacent to a word character" only — NOT punctuation
    # like "." — a term at the end of a sentence ("...using PostgreSQL.")
    # must still match; only alphanumeric adjacency (e.g. "SQL" inside
    # "MySQL") should block a match.
    return re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE)


def _build_skill_matchers() -> Dict[str, List[tuple]]:
    """Returns {category: [(term, compiled_pattern), ...]}."""
    skills_config = _load_json("skills.json")
    return {
        category: [(term, _compile_keyword_pattern(term)) for term in terms]
        for category, terms in skills_config.items()
    }


def _build_certification_matchers() -> List[tuple]:
    certifications = _load_json("certifications.json")
    return [(term, _compile_keyword_pattern(term)) for term in certifications]


def _build_labeled_patterns(filename: str) -> List[Dict[str, Any]]:
    entries = _load_json(filename)
    return [
        {"pattern": re.compile(entry["pattern"], re.IGNORECASE), "label": entry["label"]}
        for entry in entries
    ]


# Loaded and compiled once at import time — same "load once" pattern
# app/step2_nlp/embeddings_4.py already uses for the sentence-transformer
# model — so per-job extraction below is just regex matching, not I/O.
_SKILL_MATCHERS = _build_skill_matchers()
_CERTIFICATION_MATCHERS = _build_certification_matchers()
_EDUCATION_PATTERNS = _build_labeled_patterns("education_patterns.json")
_EXPERIENCE_PATTERNS = _build_labeled_patterns("experience_patterns.json")

logger.info(
    "Job entity extractor loaded: %d skill categories, %d certifications, "
    "%d education patterns, %d experience patterns",
    len(_SKILL_MATCHERS), len(_CERTIFICATION_MATCHERS),
    len(_EDUCATION_PATTERNS), len(_EXPERIENCE_PATTERNS),
)


def _match_skills(text: str) -> Dict[str, List[str]]:
    matched: Dict[str, List[str]] = {}
    for category, terms in _SKILL_MATCHERS.items():
        found = [term for term, pattern in terms if pattern.search(text)]
        if found:
            matched[category] = found
    return matched


def _match_certifications(text: str) -> List[str]:
    return [term for term, pattern in _CERTIFICATION_MATCHERS if pattern.search(text)]


def _match_labeled_patterns(text: str, patterns: List[Dict[str, Any]]) -> List[str]:
    results: List[str] = []
    seen = set()
    for entry in patterns:
        match = entry["pattern"].search(text)
        if not match:
            continue
        # label == "__match__" means "use the actual matched text" (e.g. a
        # real "5+ years of experience" phrase) rather than a fixed
        # category label — preserves real specificity where it exists.
        value = match.group(0).strip() if entry["label"] == "__match__" else entry["label"]
        if value and value.lower() not in seen:
            seen.add(value.lower())
            results.append(value)
    return results


def extract_job_entities(title: str, description: str) -> Dict[str, List[str]]:
    """
    Deterministic structured-entity extraction from a job posting's raw
    text. Returns every key populated (possibly with an empty list — never
    missing), same "always all keys present" contract
    app/step2_nlp/ner_extraction_3.extract_entities() already follows for
    resumes.

    "skills" is the flat union of every matched skill category — this is
    what job_source_fetcher.py writes back into the existing
    skills_detected field, so every existing reader keeps working
    unchanged, just with real data now for every source instead of only
    RemoteOK's tags.
    """
    text = f"{title}\n{description}" if title else (description or "")
    if not text.strip():
        return {
            "skills": [], "languages": [], "frameworks": [], "cloud_platforms": [],
            "databases": [], "ai_ml_tools": [], "devops_tools": [],
            "certifications": [], "education_requirements": [], "experience_requirements": [],
        }

    by_category = _match_skills(text)
    flat_skills = sorted({term for terms in by_category.values() for term in terms}, key=str.lower)

    return {
        "skills": flat_skills,
        "languages": by_category.get("languages", []),
        "frameworks": by_category.get("frameworks", []),
        "cloud_platforms": by_category.get("cloud_platforms", []),
        "databases": by_category.get("databases", []),
        "ai_ml_tools": by_category.get("ai_ml_tools", []),
        "devops_tools": by_category.get("devops_tools", []),
        "certifications": _match_certifications(text),
        "education_requirements": _match_labeled_patterns(text, _EDUCATION_PATTERNS),
        "experience_requirements": _match_labeled_patterns(text, _EXPERIENCE_PATTERNS),
    }
