# Wiktionary link audit (SPC-00013)

A `wiktionary_reference.link_audit` field per fixture records what each ancestor in the etymology chain actually links to on Wiktionary — which namespace, whether the page exists, what notes about the link are worth preserving. Catches a class of gaps the chain-of-words view doesn't:

- **Reconstruction-namespace links** — asterisk-prefixed proto-forms live under `Reconstruction:` (e.g. `Reconstruction:Proto-Germanic/wīną`), not in the main namespace. The chain entry's `word` field has the `*` prefix; this audit makes the namespace explicit.
- **URL-encoding quirks** — Wiktionary URL-encodes the macron-bearing ancestor labels (`wīn` → `w%C4%ABn`), AND strips macrons on the URL path itself for some entries (`vīnum` → `vinum`). Either pattern can cause our pipeline's link-resolution to silently miss.
- **Deeper roots not captured by Kaikki templates** — Wiktionary often documents an additional level beyond what the structured `etymology_templates` reach (e.g. wine's `*wóyh₁nom` ← `*weh₁y-`). The audit pins that down.
- **Alternative origins from prose** — e.g. wine's PIE root may itself be a Proto-West-Semitic / Proto-Kartvelian borrowing. Our chain has no place for that; the audit records it.
- **Dead / red links** — if Wiktionary's etymology template references a word whose page doesn't exist, that's worth recording so the test suite can xfail the corresponding chain entry.

## Schema

```jsonc
"wiktionary_reference": {
  "etymology_section_text_excerpt": "...",
  "expected_chain_per_wiktionary": [ ... ],
  "alternative_theories": [ ... ],
  "link_audit": [
    {
      "lang": "Proto-Germanic",                 // mirrors chain entry
      "word": "*wīną",                          // mirrors chain entry
      "wiktionary_url": "https://en.wiktionary.org/wiki/Reconstruction:Proto-Germanic/w%C4%ABn%C4%85",
      "namespace": "Reconstruction",            // "main" | "Reconstruction" | "Appendix" | "redirect" | "missing"
      "page_exists": true,                      // false = red/dead link
      "note": "asterisk-prefixed reconstruction; URL-encoded"  // free-form, optional
    },
    ...
  ]
}
```

## Methodology

For each entry in `expected_chain_per_wiktionary`:

1. Construct the candidate Wiktionary URL:
   - Reconstructed forms (word starts with `*`) → `Reconstruction:<lang>/<word minus *>`
   - Other forms → `<word>` (main namespace)
   - URL-encode the path component.
2. Verify the page exists. Sandbox-friendly path: WebSearch for the URL — if Wiktionary returns it as the top result, the page exists.
3. Note the namespace, encoding quirks, and any deeper roots / alternatives the page reveals.
4. Append an entry to `link_audit` with the fields above.

For ancestors that appear in `alternative_theories` but not in the primary chain (e.g. wine's Latin-borrowing branch), also audit those links — they're equally valid Wiktionary nodes that our system may or may not surface.

## Worked example

See `wine.json` (after running `python scripts/apply_phase2_reference.py`): its `link_audit` covers all 5 primary-chain ancestors, the 2 Latin-borrowing-branch ancestors (`vīnum`, `*wīnom`), and the deeper `*weh₁y-` root from Wiktionary's prose. Two findings the chain alone wouldn't catch:

- The system chain stops at `*wóyh₁nom`; Wiktionary derives that from `*weh₁y-` ("to twist; to wrap").
- Some sources suggest `*wéyh₁ō` was borrowed from Proto-West-Semitic or Proto-Kartvelian — a Q1-style alternative the chain has no place for.

## When to add a link_audit

- **Strongly recommended** for new fixtures introducing a quirk class (eponyms, acronyms, blends, modern loans). The audit makes the Wiktionary side of the picture rigorous up front, so Phase 3 tests can assert against it later.
- **Optional** for fixtures whose chain is short and unambiguous (English-only compounds like `cupboard`, `blackbird`). The audit adds little when there's only one or two link targets.
- **Required** when discovering a new gap class — record what Wiktionary actually says about the relationship so future fixes have a clear target.

## Coverage status

| Fixture | link_audit | Findings |
|---|---|---|
| wine | ✅ (8 entries) | Deeper PIE root (*weh₁y-) and Semitic/Kartvelian alternative not in chain |
| hound | ✅ (6 entries) | Pre-Germanic *kun-tós has no Wiktionary page — Q8 is upstream, not just ours |
| alchemy | ✅ (6 entries) | Middle English alkamye has no entry (dead link); URL strips macrons inconsistently |
| cheese, fire, chemistry, dog, cupboard, blackbird, orange, chuckle | ⏳ TODO | — |
| smog, brunch, sandwich, karaoke, laser, cockroach, Hund | ⏳ TODO (fixtures still in flight on a sibling branch) | — |

Filling these is incremental — each fixture takes ~3–6 WebSearches to audit thoroughly. Pick up one or two per session as part of Phase 4 quirk-closure work; the three worked examples here cover the most representative patterns (clean chain with deeper root, Pre-Germanic Q8, Middle English dead link + macron URL inconsistency).

## Cross-fixture patterns from the three worked examples

| Pattern | Where it appears | Implication for the system |
|---|---|---|
| Reconstruction-namespace URLs | wine (4×), hound (3×) | All asterisk-prefixed PIE / Proto-Germanic / Proto-Italic / Proto-West-Germanic forms |
| URL path strips macrons | alchemy: alchēmia → /wiki/alchemia; wine: vīnum → /wiki/vinum | Confirms our Q13 normalisation matches Wiktionary's own URL convention |
| URL path preserves diacritics | hound: *ḱwṓ → URL with %E1%B8%B1 (ḱ) and %E1%B9%93 (ṓ) | URLs can carry full diacritics — depends on the entry. Asymmetric. |
| Dead / no-entry ancestor | hound: Pre-Germanic *kun-tós; alchemy: ME alkamye | Upstream-side gap. Catalogues these as Q3 instances. |
| Same URL, multiple language sections | hound: /wiki/hund hosts both Middle English and Old English | Node ID disambiguation lives in our `lang` field; URL alone isn't enough |
