"""Unit tests for phonetic similarity service."""

import pytest
from app.services.phonetic_similarity import (
    build_clusters,
    build_similarity_edges,
    dolgopolsky_distance,
    format_word_for_response,
)


class TestDolgopolskyDistance:
    """Tests for Levenshtein-based consonant class distance."""

    def test_identical_strings(self) -> None:
        assert dolgopolsky_distance("KNS", "KNS") == 0.0

    def test_completely_different(self) -> None:
        assert dolgopolsky_distance("KNS", "PRT") == 1.0

    def test_empty_both(self) -> None:
        assert dolgopolsky_distance("", "") == 0.0

    def test_one_empty(self) -> None:
        assert dolgopolsky_distance("KN", "") == 1.0
        assert dolgopolsky_distance("", "PR") == 1.0

    def test_partial_match(self) -> None:
        dist = dolgopolsky_distance("KN", "KNS")
        assert 0.0 < dist < 1.0
        # Edit distance is 1 (insert S), normalized by max length 3
        assert dist == pytest.approx(1 / 3)

    def test_single_substitution(self) -> None:
        dist = dolgopolsky_distance("KN", "KR")
        assert dist == pytest.approx(0.5)  # 1 sub / 2 max len

    def test_symmetry(self) -> None:
        assert dolgopolsky_distance("PR", "KNS") == dolgopolsky_distance("KNS", "PR")


class TestBuildSimilarityEdges:
    """Tests for pairwise similarity edge computation."""

    def _word(self, word: str, lang: str, cc: str, f2: str) -> dict:
        return {
            "id": f"{word}:{lang}",
            "word": word,
            "lang": lang,
            "dolgo_consonants": cc,
            "dolgo_first2": f2,
        }

    def test_high_similarity_creates_edge(self) -> None:
        words = [
            self._word("ignis", "Latin", "KNS", "KN"),
            self._word("agni", "Sanskrit", "KN", "KN"),
        ]
        edges = build_similarity_edges(words, threshold=0.3)
        assert len(edges) == 1
        assert edges[0]["turchin_match"] is True
        assert edges[0]["similarity"] > 0.5

    def test_low_similarity_excluded(self) -> None:
        words = [
            self._word("fire", "English", "PR", "PR"),
            self._word("tuz", "Hungarian", "TS", "TS"),
        ]
        edges = build_similarity_edges(words, threshold=0.8)
        # PR vs TS — completely different, should be below 0.8
        assert len(edges) == 0

    def test_turchin_match_included_below_threshold(self) -> None:
        words = [
            self._word("a", "Lang1", "KN", "KN"),
            self._word("b", "Lang2", "KNPRST", "KN"),
        ]
        # Even if general similarity is low, turchin match forces inclusion
        edges = build_similarity_edges(words, threshold=0.9)
        assert len(edges) == 1
        assert edges[0]["turchin_match"] is True

    def test_empty_consonants_skipped(self) -> None:
        words = [
            self._word("a", "L1", "KN", "KN"),
            self._word("b", "L2", "", ""),
        ]
        edges = build_similarity_edges(words, threshold=0.0)
        assert len(edges) == 0

    def test_multiple_words_pairwise(self) -> None:
        words = [
            self._word("a", "L1", "K", "K"),
            self._word("b", "L2", "K", "K"),
            self._word("c", "L3", "K", "K"),
        ]
        edges = build_similarity_edges(words, threshold=0.0)
        # 3 words = 3 pairs
        assert len(edges) == 3


class TestBuildClusters:
    """Tests for Turchin clustering."""

    def test_groups_by_first2(self) -> None:
        words = [
            {"id": "a:L1", "dolgo_first2": "KN"},
            {"id": "b:L2", "dolgo_first2": "KN"},
            {"id": "c:L3", "dolgo_first2": "PR"},
        ]
        clusters = build_clusters(words)
        assert len(clusters) == 1  # Only KN has 2+ words
        assert clusters[0]["label"] == "K-N group"
        assert set(clusters[0]["words"]) == {"a:L1", "b:L2"}

    def test_single_member_excluded(self) -> None:
        words = [
            {"id": "a:L1", "dolgo_first2": "KN"},
            {"id": "b:L2", "dolgo_first2": "PR"},
        ]
        clusters = build_clusters(words)
        assert len(clusters) == 0

    def test_short_first2_excluded(self) -> None:
        words = [
            {"id": "a:L1", "dolgo_first2": "K"},
            {"id": "b:L2", "dolgo_first2": "K"},
        ]
        clusters = build_clusters(words)
        assert len(clusters) == 0


class TestFormatWordForResponse:
    """Tests for document-to-response transformation."""

    def test_basic_format(self) -> None:
        doc = {
            "word": "ignis",
            "lang": "Latin",
            "lang_code": "la",
            "pos": "noun",
            "phonetic": {
                "ipa": "ignis",
                "dolgo_classes": "VKNVS",
                "dolgo_consonants": "KNS",
                "dolgo_first2": "KN",
            },
            "etymology_text": "From Proto-Italic *eignis",
        }
        result = format_word_for_response(doc)
        assert result["id"] == "ignis:Latin"
        assert result["word"] == "ignis"
        assert result["ipa"] == "ignis"
        assert result["dolgo_consonants"] == "KNS"
        assert result["has_etymology"] is True

    def test_missing_phonetic(self) -> None:
        doc = {"word": "test", "lang": "English"}
        result = format_word_for_response(doc)
        assert result["ipa"] == ""
        assert result["dolgo_classes"] == ""
