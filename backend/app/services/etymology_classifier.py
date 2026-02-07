"""Classify etymology uncertainty and extract word mentions from Kaikki documents."""

import re
from dataclasses import dataclass

from app.services import lang_cache

# --- Uncertainty detection constants ---

# Templates that directly indicate unknown/uncertain origin
UNCERTAINTY_TEMPLATES = {"unk", "unc"}

# Text patterns indicating disputed etymology (strongest signal)
DISPUTED_TEXT_PATTERNS = [
    r"two interpretations",
    r"disputed",
    r"competing etymolog",
    r"multiple etymolog",
    r"alternative etymolog",
]

# Text patterns indicating uncertain origin
UNCERTAIN_TEXT_PATTERNS = [
    r"uncertain origin",
    r"unknown origin",
    r"of obscure origin",
    r"origin uncertain",
    r"origin unknown",
    r"etymology uncertain",
    r"etymology unknown",
    r"possibly from",
    r"perhaps from",
    r"maybe from",
    r"probably from",
    r"likely from",
]

# --- Word mention extraction constants ---

# Templates that mention words but don't establish ancestry
MENTION_TEMPLATES = {"m", "m+", "l"}

# Templates for affix-based word formation
AFFIX_TEMPLATES = {"af", "affix", "suffix", "prefix", "compound", "blend"}

# Ancestry templates (for exclusion from mentions)
ANCESTRY_TEMPLATES = {"inh", "bor", "der"}


@dataclass
class UncertaintyResult:
    """Result of uncertainty classification."""

    is_uncertain: bool
    uncertainty_type: str | None  # "unknown", "uncertain", "disputed"
    source: str | None  # e.g., "template:unk", "text:possibly from"
    confidence: str  # "high" (template), "medium" (text pattern)

    def to_dict(self) -> dict:
        return {
            "is_uncertain": self.is_uncertain,
            "type": self.uncertainty_type,
            "source": self.source,
            "confidence": self.confidence,
        }


@dataclass
class WordMention:
    """A word mentioned in etymology templates."""

    word: str
    lang: str
    lang_code: str
    source_template: str  # "m", "af", "cog", etc.
    role: str  # "component", "mention", "cognate"

    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "lang": self.lang,
            "lang_code": self.lang_code,
            "source_template": self.source_template,
            "role": self.role,
        }


def detect_uncertainty_from_templates(templates: list[dict]) -> UncertaintyResult | None:
    """Check etymology_templates for unk/unc markers.

    Returns UncertaintyResult if found, None otherwise.
    """
    for tmpl in templates:
        name = tmpl.get("name", "")
        if name in UNCERTAINTY_TEMPLATES:
            uncertainty_type = "unknown" if name == "unk" else "uncertain"
            return UncertaintyResult(
                is_uncertain=True,
                uncertainty_type=uncertainty_type,
                source=f"template:{name}",
                confidence="high",
            )
    return None


def detect_uncertainty_from_text(text: str) -> UncertaintyResult | None:
    """Check etymology_text for uncertainty patterns.

    Returns UncertaintyResult if found, None otherwise.
    Disputed patterns take precedence over uncertain patterns.
    """
    if not text:
        return None

    text_lower = text.lower()

    # Check disputed patterns first (stronger signal)
    for pattern in DISPUTED_TEXT_PATTERNS:
        if re.search(pattern, text_lower):
            return UncertaintyResult(
                is_uncertain=True,
                uncertainty_type="disputed",
                source=f"text:{pattern}",
                confidence="medium",
            )

    # Check uncertain patterns
    for pattern in UNCERTAIN_TEXT_PATTERNS:
        if re.search(pattern, text_lower):
            return UncertaintyResult(
                is_uncertain=True,
                uncertainty_type="uncertain",
                source=f"text:{pattern}",
                confidence="medium",
            )

    return None


def classify_etymology(doc: dict) -> UncertaintyResult:
    """Classify the etymology uncertainty of a document.

    Checks templates first (high confidence), then text patterns (medium confidence).
    Returns a result even if no uncertainty is found (is_uncertain=False).
    """
    templates = doc.get("etymology_templates", [])
    text = doc.get("etymology_text", "")

    # Templates take precedence (high confidence)
    template_result = detect_uncertainty_from_templates(templates)
    if template_result:
        return template_result

    # Fall back to text patterns (medium confidence)
    text_result = detect_uncertainty_from_text(text)
    if text_result:
        return text_result

    # No uncertainty detected
    return UncertaintyResult(
        is_uncertain=False,
        uncertainty_type=None,
        source=None,
        confidence="high",  # High confidence that it's NOT uncertain
    )


def _get_ancestry_words(templates: list[dict]) -> set[tuple[str, str]]:
    """Extract (word, lang_code) pairs from ancestry templates for exclusion."""
    ancestry_words = set()
    for tmpl in templates:
        if tmpl.get("name") not in ANCESTRY_TEMPLATES:
            continue
        args = tmpl.get("args", {})
        word = args.get("3", "")
        lang_code = args.get("2", "")
        if word and lang_code:
            ancestry_words.add((word, lang_code))
    return ancestry_words


def extract_word_mentions(doc: dict) -> list[WordMention]:
    """Extract word mentions from templates that aren't part of the ancestry chain.

    This captures words mentioned via m/m+/l templates and affix components,
    which may represent alternative etymological connections or related words.
    """
    templates = doc.get("etymology_templates", [])
    ancestry_words = _get_ancestry_words(templates)

    mentions = []
    seen = set()  # Deduplicate by (word, lang_code)

    for tmpl in templates:
        name = tmpl.get("name", "")
        args = tmpl.get("args", {})

        # Handle mention templates (m, m+, l)
        if name in MENTION_TEMPLATES:
            lang_code = args.get("1", "")
            word = args.get("2", "")
            if not word or not lang_code:
                continue
            key = (word, lang_code)
            if key in seen or key in ancestry_words:
                continue
            seen.add(key)
            mentions.append(
                WordMention(
                    word=word,
                    lang=lang_cache.code_to_name(lang_code),
                    lang_code=lang_code,
                    source_template=name,
                    role="mention",
                )
            )

        # Handle affix templates
        elif name in AFFIX_TEMPLATES:
            # Affix templates can have multiple components in args
            # Usually args["2"] is the base word
            lang_code = args.get("1", "")
            for key in ["2", "3", "4", "5"]:
                word = args.get(key, "")
                if not word or not lang_code:
                    continue
                # Skip affixes (starting with - or ending with -)
                if word.startswith("-") or word.endswith("-"):
                    continue
                mention_key = (word, lang_code)
                if mention_key in seen or mention_key in ancestry_words:
                    continue
                seen.add(mention_key)
                mentions.append(
                    WordMention(
                        word=word,
                        lang=lang_cache.code_to_name(lang_code),
                        lang_code=lang_code,
                        source_template=name,
                        role="component",
                    )
                )

    return mentions
