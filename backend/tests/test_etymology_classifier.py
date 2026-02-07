"""Tests for etymology classification functions."""

from app.services.etymology_classifier import (
    UncertaintyResult,
    classify_etymology,
    detect_uncertainty_from_templates,
    detect_uncertainty_from_text,
    extract_word_mentions,
)


def test_detect_uncertainty_from_templates_unk():
    """Test detection of 'unk' (unknown) template."""
    templates = [{"name": "unk"}]
    result = detect_uncertainty_from_templates(templates)

    assert result is not None
    assert result.is_uncertain is True
    assert result.uncertainty_type == "unknown"
    assert result.source == "template:unk"
    assert result.confidence == "high"


def test_detect_uncertainty_from_templates_unc():
    """Test detection of 'unc' (uncertain) template."""
    templates = [{"name": "unc"}]
    result = detect_uncertainty_from_templates(templates)

    assert result is not None
    assert result.is_uncertain is True
    assert result.uncertainty_type == "uncertain"
    assert result.source == "template:unc"
    assert result.confidence == "high"


def test_detect_uncertainty_from_templates_none():
    """Test no uncertainty detected from templates."""
    templates = [{"name": "inh", "args": {"1": "en", "2": "enm", "3": "test"}}]
    result = detect_uncertainty_from_templates(templates)

    assert result is None


def test_detect_uncertainty_from_text_disputed():
    """Test detection of disputed etymology from text."""
    text = "There are two interpretations of this word's origin."
    result = detect_uncertainty_from_text(text)

    assert result is not None
    assert result.is_uncertain is True
    assert result.uncertainty_type == "disputed"
    assert "two interpretations" in result.source
    assert result.confidence == "medium"


def test_detect_uncertainty_from_text_uncertain():
    """Test detection of uncertain origin from text."""
    text = "The etymology uncertain for this word."
    result = detect_uncertainty_from_text(text)

    assert result is not None
    assert result.is_uncertain is True
    assert result.uncertainty_type == "uncertain"
    assert result.confidence == "medium"


def test_detect_uncertainty_from_text_none():
    """Test no uncertainty detected from text."""
    text = "From Latin testum, from Proto-Indo-European *test-."
    result = detect_uncertainty_from_text(text)

    assert result is None


def test_classify_etymology_template_priority():
    """Test that template detection takes precedence over text patterns."""
    doc = {
        "etymology_templates": [{"name": "unk"}],
        "etymology_text": "possibly from Latin",  # Would trigger text pattern
    }
    result = classify_etymology(doc)

    # Template should win
    assert result.uncertainty_type == "unknown"
    assert result.source == "template:unk"
    assert result.confidence == "high"


def test_classify_etymology_not_uncertain():
    """Test classification of word with clear etymology."""
    doc = {
        "etymology_templates": [{"name": "inh", "args": {"1": "en", "2": "enm", "3": "test"}}],
        "etymology_text": "From Middle English test.",
    }
    result = classify_etymology(doc)

    assert result.is_uncertain is False
    assert result.uncertainty_type is None
    assert result.source is None
    assert result.confidence == "high"


def test_extract_word_mentions_from_m_template():
    """Test extraction of word mentions from 'm' template."""
    doc = {
        "etymology_templates": [
            {"name": "m", "args": {"1": "la", "2": "testum"}},
        ],
    }

    mentions = extract_word_mentions(doc)

    assert len(mentions) == 1
    assert mentions[0].word == "testum"
    assert mentions[0].lang_code == "la"
    assert mentions[0].source_template == "m"
    assert mentions[0].role == "mention"


def test_extract_word_mentions_excludes_ancestry():
    """Test that mentions exclude words already in ancestry chain."""
    doc = {
        "etymology_templates": [
            {"name": "inh", "args": {"1": "en", "2": "enm", "3": "test"}},  # Ancestry
            {"name": "m", "args": {"1": "enm", "2": "test"}},  # Should be excluded
            {"name": "m", "args": {"1": "la", "2": "testum"}},  # Should be included
        ],
    }

    mentions = extract_word_mentions(doc)

    # Should only include "testum", not "test" (which is in ancestry)
    assert len(mentions) == 1
    assert mentions[0].word == "testum"


def test_extract_word_mentions_from_affix_template():
    """Test extraction of components from affix templates."""
    doc = {
        "etymology_templates": [
            {"name": "af", "args": {"1": "en", "2": "test", "3": "able"}},
        ],
    }

    mentions = extract_word_mentions(doc)

    # Should extract both "test" and "able" as components
    assert len(mentions) == 2
    words = {m.word for m in mentions}
    assert "test" in words
    assert "able" in words
    assert all(m.role == "component" for m in mentions)


def test_extract_word_mentions_skips_affixes():
    """Test that affix extraction skips actual affixes (with hyphens)."""
    doc = {
        "etymology_templates": [
            {"name": "suffix", "args": {"1": "en", "2": "test", "3": "-able"}},
        ],
    }

    mentions = extract_word_mentions(doc)

    # Should only include "test", not "-able" (it's an affix)
    assert len(mentions) == 1
    assert mentions[0].word == "test"


def test_uncertainty_result_to_dict():
    """Test serialization of UncertaintyResult to dict."""
    result = UncertaintyResult(
        is_uncertain=True,
        uncertainty_type="disputed",
        source="text:two interpretations",
        confidence="medium",
    )

    d = result.to_dict()

    assert d["is_uncertain"] is True
    assert d["type"] == "disputed"
    assert d["source"] == "text:two interpretations"
    assert d["confidence"] == "medium"
