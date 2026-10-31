"""Skills taxonomy loader and token-boundary extraction engine.

Handles precise token boundary matching for special symbols (C++, C#, .NET, Node.js, CI/CD),
prevents sub-token false positives (e.g., 'java' inside 'javascript'), supports aliases,
and performs guarded fuzzy typo matching with evidence weighting.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from rapidfuzz import fuzz

from src.config import TAXONOMY_PATH, SystemConfig
from src.models import SkillMatch


logger = logging.getLogger(__name__)

# Reserved short or ambiguous keywords that MUST never be matched fuzzily
SHORT_GUARDED_SKILLS: Set[str] = {
    "c",
    "r",
    "go",
    "git",
    "sql",
    "java",
    "rust",
    "php",
    "bash",
    "css",
    "html",
    "c++",
    "c#",
    ".net",
    "vue",
    "aws",
    "gcp",
    "etl",
    "llm",
    "nlp",
    "cv",
    "eda",
    "k8s",
    "xml",
    "tsv",
    "csv",
}


def build_token_regex(token: str) -> re.Pattern:
    """Build a compiled regex pattern for a skill token with symbol-safe boundaries.

    Ensures tokens like 'C++', 'C#', '.NET', 'Node.js', and 'CI/CD' match accurately
    while preventing substring false positives (e.g. 'java' inside 'javascript')
    and cleanly handling trailing sentence punctuation (e.g. 'CI/CD.').
    """
    escaped = re.escape(token)

    # Left boundary check (fixed-width 1-char lookbehind for Python re compatibility)
    if token.startswith((".", "+", "#", "/")):
        left = r"(?<![a-zA-Z0-9_])"
    else:
        left = r"(?<![a-zA-Z0-9_+#])"

    # Right boundary check
    if token.endswith((".", "/")):
        right = r"(?![a-zA-Z0-9_])"
    else:
        right = r"(?![a-zA-Z0-9_+#])"

    return re.compile(f"{left}{escaped}{right}", re.IGNORECASE)


class SkillTaxonomy:
    """Loads and manages the skill taxonomy, aliases, and regex patterns."""

    def __init__(self, taxonomy_path: Path = TAXONOMY_PATH) -> None:
        self.taxonomy_path = Path(taxonomy_path)
        self.categories: Dict[str, Dict[str, List[str]]] = {}
        # Mapping from token string (lowercased) -> (canonical_name, category)
        self.token_to_canonical: Dict[str, Tuple[str, str]] = {}
        # Precompiled regex patterns sorted longest to shortest
        self.patterns: List[Tuple[re.Pattern, str, str]] = []
        self._load_taxonomy()

    def _load_taxonomy(self) -> None:
        """Load taxonomy from JSON and build search indices and compiled patterns."""
        if not self.taxonomy_path.exists():
            logger.warning("Taxonomy file not found at %s. Using empty taxonomy.", self.taxonomy_path)
            return

        with open(self.taxonomy_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.categories = data.get("categories", {})
        raw_tokens: List[Tuple[str, str, str]] = []

        for category, skills in self.categories.items():
            for canonical, aliases in skills.items():
                canonical_lower = canonical.strip().lower()
                raw_tokens.append((canonical_lower, canonical_lower, category))
                self.token_to_canonical[canonical_lower] = (canonical_lower, category)

                for alias in aliases:
                    alias_lower = alias.strip().lower()
                    raw_tokens.append((alias_lower, canonical_lower, category))
                    self.token_to_canonical[alias_lower] = (canonical_lower, category)

        # Sort tokens by length in descending order to prioritize greedy matching
        raw_tokens.sort(key=lambda item: len(item[0]), reverse=True)

        for token, canonical, category in raw_tokens:
            try:
                compiled = build_token_regex(token)
                self.patterns.append((compiled, canonical, category))
            except re.error as err:
                logger.error("Failed to compile pattern for '%s': %s", token, err)

        logger.info(
            "Loaded taxonomy with %d unique canonical skills and %d total patterns.",
            len({c for _, c, _ in raw_tokens}),
            len(self.patterns),
        )


# Global singleton instance for performance
_TAXONOMY_INSTANCE: Optional[SkillTaxonomy] = None


def get_taxonomy(path: Path = TAXONOMY_PATH) -> SkillTaxonomy:
    """Retrieve or initialize the singleton SkillTaxonomy instance."""
    global _TAXONOMY_INSTANCE
    if _TAXONOMY_INSTANCE is None or _TAXONOMY_INSTANCE.taxonomy_path != path:
        _TAXONOMY_INSTANCE = SkillTaxonomy(path)
    return _TAXONOMY_INSTANCE


def extract_skills_from_text(
    text: str,
    sections: Optional[Dict[str, str]] = None,
    config: Optional[SystemConfig] = None,
    taxonomy: Optional[SkillTaxonomy] = None,
) -> Dict[str, SkillMatch]:
    """Extract canonical skills from text and sections with evidence tracking.

    Args:
        text: Full raw or cleaned document text.
        sections: Optional mapping of section name -> section text.
        config: System configuration for fuzzy matching thresholds and weights.
        taxonomy: Optional taxonomy instance (uses default if None).

    Returns:
        Dictionary mapping canonical skill name to SkillMatch objects.
    """
    if not text:
        return {}

    tax = taxonomy or get_taxonomy()
    cfg = config or SystemConfig()

    matches: Dict[str, SkillMatch] = {}
    lower_text = text.lower()

    # Step 1: Exact token-boundary matching using compiled regex patterns
    for pattern, canonical, category in tax.patterns:
        found_spans = list(pattern.finditer(lower_text))
        if found_spans:
            count = len(found_spans)
            first_match_text = found_spans[0].group(0)

            if canonical not in matches:
                matches[canonical] = SkillMatch(
                    canonical_name=canonical,
                    category=category,
                    count=count,
                    locations=[],
                    is_demonstrated=False,
                    matched_variant=first_match_text,
                )
            else:
                matches[canonical].count += count

    # Step 2: Section-aware evidence tracking
    if sections:
        for canonical, match_obj in matches.items():
            for sec_name, sec_text in sections.items():
                if not sec_text:
                    continue
                sec_lower = sec_text.lower()
                token_to_check = match_obj.matched_variant or canonical
                sec_pat = build_token_regex(token_to_check)
                if sec_pat.search(sec_lower):
                    sec_clean = sec_name.strip().lower()
                    if sec_clean not in match_obj.locations:
                        match_obj.locations.append(sec_clean)
                    if any(key in sec_clean for key in ["experience", "project", "work", "employment"]):
                        match_obj.is_demonstrated = True
    else:
        for match_obj in matches.values():
            match_obj.locations = ["body"]

    # Step 3: Guarded fuzzy typo matching (rapidfuzz)
    if cfg.enable_fuzzy_matching:
        _perform_guarded_fuzzy_matching(
            text=lower_text,
            matches=matches,
            tax=tax,
            threshold=cfg.fuzzy_match_threshold,
        )

    return matches


def _perform_guarded_fuzzy_matching(
    text: str,
    matches: Dict[str, SkillMatch],
    tax: SkillTaxonomy,
    threshold: int = 92,
) -> None:
    """Find near-miss typos in words and map them to taxonomy skills.

    Guards:
    - Never match words with len < 5.
    - Never fuzzy-match tokens in SHORT_GUARDED_SKILLS (e.g. 'java' vs 'javascript').
    - Only words with length difference <= 2.
    """
    words = set(re.findall(r"\b[a-z]{5,}\b", text))

    for word in words:
        if word in SHORT_GUARDED_SKILLS:
            continue

        for canonical, (can_name, category) in tax.token_to_canonical.items():
            if can_name in matches:
                continue
            if canonical in SHORT_GUARDED_SKILLS:
                continue
            if len(canonical) < 5 or abs(len(word) - len(canonical)) > 2:
                continue

            sim = fuzz.ratio(word, canonical)
            if sim >= threshold:
                logger.debug("Fuzzy matched typo '%s' -> canonical '%s' (score %d)", word, can_name, sim)
                matches[can_name] = SkillMatch(
                    canonical_name=can_name,
                    category=category,
                    count=1,
                    locations=["fuzzy_body"],
                    is_demonstrated=False,
                    matched_variant=word,
                )
                break


def compute_skill_evidence_multiplier(
    skill_match: SkillMatch,
    config: Optional[SystemConfig] = None,
) -> float:
    """Calculate the evidence multiplier for an extracted skill.

    Skills demonstrated in experience/projects receive full weight (1.0).
    Skills found only in a list or summary receive reduced weight (default 0.6).
    """
    cfg = config or SystemConfig()
    if skill_match.is_demonstrated:
        return cfg.evidence.demonstrated_in_experience_or_projects
    return cfg.evidence.skills_section_only
