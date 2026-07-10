"""Exact-equality parity tests for the vectorized phonetic-similarity port.

phonetic_similarity.build_similarity_edges (pure Python, nested loops) is the
oracle. app.services.layout.phonetic_numpy.build_similarity_edges_vectorized
must produce byte-for-byte identical output (same edges, same order, same
rounding) for any input — this is a performance rewrite, not an approximation,
so every test here is an exact-equality check against the oracle.
"""

import random

import pytest
from app.services.layout.phonetic_numpy import (
    build_similarity_edges_vectorized,
    dolgopolsky_distance_vectorized,
)
from app.services.phonetic_similarity import (
    build_similarity_edges,
    dolgopolsky_distance,
)

# Small alphabet mimicking real Dolgopolsky consonant classes (P, T, K, B, D,
# G, M, N, S, Z, R are typical single-letter class codes in this codebase).
_ALPHABET = "ptkbdgmnszr"


def _random_word(rng: random.Random, idx: int) -> dict:
    """Build one synthetic word dict with random consonant-class-like fields."""
    cc_len = rng.randint(0, 6)
    consonants = "".join(rng.choice(_ALPHABET) for _ in range(cc_len))
    f2_len = rng.randint(0, 3)
    first2 = "".join(rng.choice(_ALPHABET) for _ in range(f2_len))
    return {
        "id": f"word{idx}:xx",
        "dolgo_consonants": consonants,
        "dolgo_first2": first2,
    }


@pytest.mark.tier0
def test_dolgopolsky_distance_vectorized_matches_oracle_basic_cases():
    """Spot-check the standalone distance function against the oracle,
    including both empty-string edge cases."""
    cases = [
        ("", ""),
        ("", "ptk"),
        ("ptk", ""),
        ("ptk", "ptk"),
        ("ptk", "ptg"),
        ("pt", "ptk"),
        ("kbd", "mns"),
    ]
    for s1, s2 in cases:
        expected = dolgopolsky_distance(s1, s2)
        actual = dolgopolsky_distance_vectorized(s1, s2)
        assert actual == expected, f"mismatch for {s1!r}, {s2!r}: {actual} != {expected}"


@pytest.mark.tier0
def test_build_similarity_edges_vectorized_matches_oracle_hand_built_cases():
    """Hand-built word list exercising: empty consonants (skip), identical
    consonants (sim=1.0 exactly), short dolgo_first2 (<2 chars, Turchin never
    fires), matching dolgo_first2 (Turchin fires), and near-threshold sims."""
    words = [
        {"id": "a:en", "dolgo_consonants": "ptk", "dolgo_first2": "pt"},
        {"id": "b:en", "dolgo_consonants": "ptk", "dolgo_first2": "pt"},  # identical to a
        {"id": "c:en", "dolgo_consonants": "", "dolgo_first2": "pt"},  # empty consonants: skip
        {"id": "d:de", "dolgo_consonants": "pdk", "dolgo_first2": "pd"},  # 1 substitution vs a
        {"id": "e:fr", "dolgo_consonants": "mns", "dolgo_first2": "mn"},  # very different
        {"id": "f:it", "dolgo_consonants": "p", "dolgo_first2": "p"},  # short f2 (<2 chars)
        {"id": "g:es", "dolgo_consonants": "ptkbd", "dolgo_first2": "pt"},  # matches a's f2
        {"id": "h:pt", "dolgo_consonants": "ptg", "dolgo_first2": ""},  # empty f2
    ]

    for threshold in (0.0, 0.2, 0.3, 0.5, 0.6, 1.0):
        expected = build_similarity_edges(words, threshold=threshold)
        actual = build_similarity_edges_vectorized(words, threshold=threshold)
        assert actual == expected, f"mismatch at threshold={threshold}"


@pytest.mark.tier0
def test_build_similarity_edges_vectorized_empty_word_list():
    """Empty input should short-circuit cleanly in both implementations."""
    assert build_similarity_edges_vectorized([]) == build_similarity_edges([])


@pytest.mark.tier0
def test_build_similarity_edges_vectorized_all_empty_consonants():
    """Every word has empty dolgo_consonants: every pair must be skipped,
    regardless of dolgo_first2 / Turchin matches."""
    words = [
        {"id": "a:en", "dolgo_consonants": "", "dolgo_first2": "pt"},
        {"id": "b:en", "dolgo_consonants": "", "dolgo_first2": "pt"},
        {"id": "c:en", "dolgo_consonants": "", "dolgo_first2": "mn"},
    ]
    expected = build_similarity_edges(words)
    actual = build_similarity_edges_vectorized(words)
    assert actual == expected == []


@pytest.mark.tier0
def test_build_similarity_edges_vectorized_single_word():
    """A single word has no pairs to compare; both implementations return []."""
    words = [{"id": "a:en", "dolgo_consonants": "ptk", "dolgo_first2": "pt"}]
    assert build_similarity_edges_vectorized(words) == build_similarity_edges(words) == []


@pytest.mark.tier0
@pytest.mark.parametrize("threshold", [0.2, 0.3, 0.5])
def test_build_similarity_edges_vectorized_matches_oracle_randomized(threshold):
    """Randomized comparison: generate ~40 synthetic words with a seeded RNG
    (reproducible, independent of the global random module and numpy's global
    RNG) and assert the vectorized implementation is byte-for-byte identical
    to the oracle across a range of thresholds."""
    rng = random.Random(42)
    words = [_random_word(rng, idx) for idx in range(40)]

    expected = build_similarity_edges(words, threshold=threshold)
    actual = build_similarity_edges_vectorized(words, threshold=threshold)

    assert actual == expected


@pytest.mark.tier0
def test_build_similarity_edges_vectorized_randomized_larger_population():
    """A second, larger randomized population (different seed) for extra
    confidence beyond the fixed hand-built cases, at the oracle's default
    threshold."""
    rng = random.Random(1337)
    words = [_random_word(rng, idx) for idx in range(50)]

    expected = build_similarity_edges(words)
    actual = build_similarity_edges_vectorized(words)

    assert actual == expected
