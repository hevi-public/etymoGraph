"""Vectorized (numpy) twin of phonetic_similarity.build_similarity_edges.

Performance-oriented port for SPC-00021 (server-side layout). The pairwise
Levenshtein distance computation (the O(n^2) hot path across all word pairs)
is batched: every pair's DP table is advanced one anti-diagonal-row at a time,
across ALL pairs simultaneously, using padded numpy arrays. The cheap
per-pair bookkeeping (Turchin match, shared prefix, threshold filter,
rounding) stays in a plain Python loop so its semantics are trivially
identical to the oracle in app/services/phonetic_similarity.py.

Must produce EXACTLY the same output (same edges, same order, same rounding)
as the oracle for any input — exact-equality-tested, not just "close enough".
"""

import numpy as np

# Sentinel codepoint used to pad strings to a common length. Chosen well
# outside the Unicode range used by real Dolgopolsky consonant-class letters
# so padding never spuriously matches real characters (padding vs. padding
# comparisons are masked out anyway, but this keeps the intent explicit).
_PAD_CODE = 0


def _encode_padded(strings: list[str], width: int) -> np.ndarray:
    """Encode strings as a (len(strings), width) int32 array of codepoints,
    right-padded with `_PAD_CODE`."""
    arr = np.full((len(strings), width), _PAD_CODE, dtype=np.int32)
    for row, s in enumerate(strings):
        if s:
            arr[row, : len(s)] = np.frombuffer(s.encode("utf-32-le"), dtype=np.uint32).astype(
                np.int32
            )
    return arr


def batch_levenshtein(pairs: list[tuple[str, str]]) -> np.ndarray:
    """Compute raw (unnormalized) Levenshtein edit distance for many pairs at once.

    Vectorizes the classic single-row DP recurrence across the *pair* axis:
    for a fixed DP row index `i`, all pairs advance their row simultaneously
    via numpy elementwise ops, while the (inherently sequential) scan over
    column `j` remains a Python loop of length `max_m` — same dependency
    structure as the oracle's per-pair DP, just batched across pairs.

    Args:
        pairs: List of (s1, s2) string pairs. Empty strings are allowed (the
            distance for an empty vs. non-empty pair equals the length of the
            other string, matching the classic Levenshtein base case — callers
            needing the oracle's `dolgopolsky_distance` empty-string edge
            cases (0.0 for both-empty, 1.0 for one-empty) handle that
            normalization themselves, since this function only returns raw
            edit distances).

    Returns:
        1D numpy array of raw edit distances, one per input pair, in the same
        order as `pairs`.
    """
    n_pairs = len(pairs)
    if n_pairs == 0:
        return np.zeros(0, dtype=np.int32)

    lens1 = np.array([len(a) for a, _ in pairs], dtype=np.int32)
    lens2 = np.array([len(b) for _, b in pairs], dtype=np.int32)
    max_n = int(lens1.max()) if n_pairs else 0
    max_m = int(lens2.max()) if n_pairs else 0

    if max_n == 0 or max_m == 0:
        # At least one side is all-empty-strings across every pair; distance
        # degenerates to the other side's length (standard Levenshtein base
        # case dp[0][m] = m / dp[n][0] = n).
        return np.maximum(lens1, lens2).astype(np.int32)

    a_codes = _encode_padded([a for a, _ in pairs], max_n)
    b_codes = _encode_padded([b for _, b in pairs], max_m)

    # Pairs have different (len(a), len(b)) lengths, so each pair's "answer"
    # sits at a different (row, column) cell of its own padded DP table.
    # _gather_final_distances runs the batched DP once (advancing every
    # pair's row in lockstep via numpy) and records all rows so each pair can
    # read off its own dp[len(a)][len(b)] cell afterward.
    return _gather_final_distances(a_codes, b_codes, lens1, lens2)


def _gather_final_distances(
    a_codes: np.ndarray, b_codes: np.ndarray, lens1: np.ndarray, lens2: np.ndarray
) -> np.ndarray:
    """Run the batched DP while recording every row so each pair can read off
    its own dp[len(a)][len(b)] cell (pairs have different lengths, so the
    "answer" lives at a different row/column per pair)."""
    n_pairs = a_codes.shape[0]
    max_n = a_codes.shape[1]
    max_m = b_codes.shape[1]

    # all_rows[i, p, j] = dp value for pair p at DP row i, column j.
    all_rows = np.empty((max_n + 1, n_pairs, max_m + 1), dtype=np.int32)
    all_rows[0] = np.tile(np.arange(max_m + 1, dtype=np.int32), (n_pairs, 1))

    for i in range(1, max_n + 1):
        prev_row = all_rows[i - 1]
        a_char = a_codes[:, i - 1 : i]
        cost = (b_codes != a_char).astype(np.int32)

        sub_or_match = prev_row[:, :-1] + cost
        delete = prev_row[:, 1:] + 1
        candidate = np.minimum(sub_or_match, delete)

        row = np.empty((n_pairs, max_m + 1), dtype=np.int32)
        row[:, 0] = i
        prev_col = row[:, 0]
        for j in range(1, max_m + 1):
            prev_col = np.minimum(candidate[:, j - 1], prev_col + 1)
            row[:, j] = prev_col

        all_rows[i] = row

    pair_idx = np.arange(n_pairs)
    return all_rows[lens1, pair_idx, lens2].astype(np.int32)


def dolgopolsky_distance_vectorized(cc1: str, cc2: str) -> float:
    """Vectorized twin of phonetic_similarity.dolgopolsky_distance for a
    single pair (convenience wrapper around batch_levenshtein for callers
    that want the exact same edge-case handling as the oracle).

    Same edge cases and same result as the oracle for any input.
    """
    if not cc1 and not cc2:
        return 0.0
    if not cc1 or not cc2:
        return 1.0

    n, m = len(cc1), len(cc2)
    raw = batch_levenshtein([(cc1, cc2)])
    max_len = max(n, m)
    return float(raw[0]) / max_len if max_len > 0 else 0.0


def _shared_prefix(cc1: str, cc2: str) -> str:
    """Return the longest shared prefix of two consonant class strings.

    Identical logic to phonetic_similarity._shared_prefix; duplicated here
    (rather than imported) since it's O(min(n, m)) cheap bookkeeping, not part
    of the vectorized hot path, and keeping this module self-contained avoids
    a needless cross-import for a four-line helper.
    """
    prefix = []
    for a, b in zip(cc1, cc2, strict=False):
        if a == b:
            prefix.append(a)
        else:
            break
    return "".join(prefix)


def build_similarity_edges_vectorized(words: list[dict], threshold: float = 0.3) -> list[dict]:
    """Vectorized (numpy) twin of phonetic_similarity.build_similarity_edges.

    Must produce EXACTLY the same output (same edges, same order, same rounding)
    for any input — exact-equality-tested against that function as the oracle.
    """
    n_words = len(words)
    ids = [w["id"] for w in words]
    ccs = [w.get("dolgo_consonants", "") for w in words]
    f2s = [w.get("dolgo_first2", "") for w in words]

    # Build the candidate pair list in exactly the oracle's iteration order
    # (i ascending, then j ascending within i, j > i), skipping pairs where
    # either word's dolgo_consonants is empty/falsy — same skip semantics as
    # the oracle's `if not cc_i or not cc_j: continue`.
    pair_indices: list[tuple[int, int]] = []
    for i in range(n_words):
        if not ccs[i]:
            continue
        for j in range(i + 1, n_words):
            if not ccs[j]:
                continue
            pair_indices.append((i, j))

    if not pair_indices:
        return []

    pairs = [(ccs[i], ccs[j]) for i, j in pair_indices]
    raw_distances = batch_levenshtein(pairs)

    edges: list[dict] = []
    for (i, j), raw in zip(pair_indices, raw_distances, strict=True):
        cc_i, cc_j = ccs[i], ccs[j]
        f2_i, f2_j = f2s[i], f2s[j]

        max_len = max(len(cc_i), len(cc_j))
        distance = float(raw) / max_len if max_len > 0 else 0.0
        sim = 1.0 - distance
        turchin = len(f2_i) >= 2 and len(f2_j) >= 2 and f2_i == f2_j

        if sim >= threshold or turchin:
            edges.append(
                {
                    "source": ids[i],
                    "target": ids[j],
                    "similarity": round(sim, 3),
                    "turchin_match": turchin,
                    "shared_classes": _shared_prefix(cc_i, cc_j),
                }
            )

    return edges
