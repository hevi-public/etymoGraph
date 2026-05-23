"""Apply SPC-00013 Phase 2: hand-encoded Wiktionary reference + known_gaps recalibration.

One-shot script. Reads each fixture, overwrites:
  - wiktionary_reference.etymology_section_text_excerpt
  - wiktionary_reference.expected_chain_per_wiktionary
  - wiktionary_reference.alternative_theories
  - known_gaps (per-key override)
  - meta.notes (append/replace)

Does not touch raw_kaikki or system_output — those stay as collected.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIX_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "wiktionary"

# Per-word Phase 2 ground truth. Sources cited in PR description and decision-log.
PHASE2: dict[str, dict[str, Any]] = {
    "wine": {
        "excerpt": (
            "From Middle English wyn, win, from Old English wīn ('wine'), from "
            "Proto-West Germanic *wīn, from Proto-Germanic *wīną, either inherited "
            "from Proto-Indo-European *wóyh₁nom ('wine'), or as an early borrowing "
            "into Proto-Germanic from Latin vīnum (from Proto-Italic *wīnom, from "
            "the same PIE root)."
        ),
        "chain": [
            {"lang": "Middle English", "word": "wyn"},
            {"lang": "Old English", "word": "wīn"},
            {"lang": "Proto-West Germanic", "word": "*wīn"},
            {"lang": "Proto-Germanic", "word": "*wīną"},
            {"lang": "Proto-Indo-European", "word": "*wóyh₁nom",
             "note": "direct inheritance — the alternative to Latin borrowing"},
        ],
        "alternative_theories": [
            {"summary": "Proto-Germanic *wīną borrowed early from Latin vīnum "
                        "(← Proto-Italic *wīnom ← PIE *wóyh₁nom); this is the path our /chain captures.",
             "kaikki_template_present": True},
        ],
        "gaps": {"missing_alternative_origins": True, "missing_doublet_link": True},
        "notes": ("Phase 2: Wiktionary presents 'either/or' between direct PIE inheritance and "
                  "early Latin borrowing. Our /chain commits to the borrowing path "
                  "(*wīną ← der ← vīnum). Doublet 'vine' present as `doublet` template, not "
                  "surfaced as graph edge."),
    },
    "hound": {
        "excerpt": (
            "From Middle English hound, hund, from Old English hund ('dog'), from "
            "Proto-West Germanic *hund, from Proto-Germanic *hundaz ('dog'), from "
            "Pre-Germanic *kun-tós, *ḱwn̥tós, an enlargement of Proto-Indo-European "
            "*ḱwṓ ('dog')."
        ),
        "chain": [
            {"lang": "Middle English", "word": "hound"},
            {"lang": "Old English", "word": "hund"},
            {"lang": "Proto-West Germanic", "word": "*hund"},
            {"lang": "Proto-Germanic", "word": "*hundaz"},
            {"lang": "Pre-Germanic", "word": "*kun-tós",
             "note": "prose-only intermediate; not a structured Kaikki template (Q8)"},
            {"lang": "Proto-Indo-European", "word": "*ḱwṓ"},
        ],
        "alternative_theories": [],
        "gaps": {},
        "notes": ("Phase 2: Pre-Germanic *kun-tós/*ḱwn̥tós described in prose only — "
                  "no template, so our chain jumps PGmc → PIE directly. Cognates "
                  "(Old Armenian սկունդ etc.) listed inline as `cog` templates, visible in "
                  "tree_inh_bor_der_cog but not /chain. Q13 fix verified: *hundaz resolves "
                  "via the asterisk-normalised lookup."),
    },
    "cheese": {
        "excerpt": (
            "From Middle English chese, from Anglian Old English ċīese ('cheese'), "
            "from Proto-West Germanic *kāsī, borrowed from Latin cāseus ('cheese')."
        ),
        "chain": [
            {"lang": "Middle English", "word": "chese"},
            {"lang": "Old English", "word": "ċīese"},
            {"lang": "Proto-West Germanic", "word": "*kāsī"},
            {"lang": "Latin", "word": "cāseus", "note": "borrowed"},
        ],
        "alternative_theories": [],
        "gaps": {"missing_doublet_link": True},
        "notes": ("Phase 2: Clean borrowing chain matches Wiktionary. Doublets with queso "
                  "(Spanish), Käse (German), kaas (Dutch) via shared Latin root are present "
                  "as `doublet` template, not surfaced as edges. Q13 fix verified: ċīese "
                  "with diacritic resolves."),
    },
    "fire": {
        "excerpt": (
            "From Middle English fyr, fier, from Old English fȳr ('fire'), from "
            "Proto-West Germanic *fuir, from *fuïr (regularised from Proto-Germanic "
            "*fōr 'fire'), ultimately from Proto-Indo-European *péh₂wr̥ ('fire')."
        ),
        "chain": [
            {"lang": "Middle English", "word": "fyr"},
            {"lang": "Old English", "word": "fȳr"},
            {"lang": "Proto-West Germanic", "word": "*fuir"},
            {"lang": "Proto-Germanic", "word": "*fōr"},
            {"lang": "Proto-Indo-European", "word": "*péh₂wr̥"},
        ],
        "alternative_theories": [],
        "gaps": {},
        "notes": ("Phase 2: Full inh chain to PIE. Many cognates (Sanskrit, Greek πῦρ, "
                  "Hittite paḫḫur, etc.) listed as `cog` templates — visible in "
                  "tree_inh_bor_der_cog as separate edges. No doublets."),
    },
    "alchemy": {
        "excerpt": (
            "From Middle English alkamye, from Old French alkimie, arquemie "
            "(French alchimie), from Medieval Latin alchēmia, from Arabic اَلْكِيمِيَاء "
            "(al-kīmiyāʔ), from article اَل (al-) + Ancient Greek χυμείᾱ (khumeíā, "  # noqa: RUF001
            "'art of alloying metals'), from χύμα (khúma, 'ingot, bar')."
        ),
        "chain": [
            {"lang": "Middle English", "word": "alkamye",
             "note": "intermediate skipped by our /chain — Kaikki has no `inh` ME template"},
            {"lang": "Old French", "word": "alkimie"},
            {"lang": "Medieval Latin", "word": "alchēmia"},
            {"lang": "Arabic", "word": "اَلْكِيمِيَاء"},
            {"lang": "Ancient Greek", "word": "χυμείᾱ"},
            {"lang": "Ancient Greek", "word": "χύμα",
             "note": "deeper root — system chain stops at χυμείᾱ"},
        ],
        "alternative_theories": [],
        "gaps": {"missing_doublet_link": True},
        "notes": ("Phase 2: Doublet of `chemistry` via Greek χυμεία — not surfaced. "
                  "Chain truncated before deepest Greek root χύμα. Foreign script "
                  "(Arabic اَلْكِيمِيَاء, كيمياء) in node IDs round-trips through API. "
                  "Middle English alkamye absent from chain because Kaikki has no ME→OE `inh` "
                  "template (jumps English ← Old French directly)."),
    },
    "chemistry": {
        "excerpt": (
            "First attested 1605, from chemist + -ry. Doublet of alchemy via the "
            "same ultimate Greek/Arabic root."
        ),
        "chain": [
            {"lang": "English", "word": "chemist", "note": "component (compound)"},
            {"lang": "English", "word": "-ry", "note": "component (suffix)"},
        ],
        "alternative_theories": [],
        "gaps": {"missing_compound_components": True, "missing_doublet_link": True},
        "notes": ("Phase 2: System /chain is EMPTY despite Wiktionary clearly stating "
                  "'chemist + -ry'. Main SPC-00012 precomputed compound edges only show "
                  "in /tree — /chain still misses them. Doublet of alchemy not surfaced."),
    },
    "dog": {
        "excerpt": (
            "From Middle English dogge, from Old English dogga, docga, of uncertain "
            "origin. The original meaning seems to have been a common dog, as opposed "
            "to a well-bred one, possibly a pet-form diminutive with suffix -ga, "
            "appended to a base *dog-, *doc- of unclear origin."
        ),
        "chain": [
            {"lang": "Middle English", "word": "dogge"},
            {"lang": "Old English", "word": "docga", "note": "of uncertain origin"},
        ],
        "alternative_theories": [
            {"summary": "from Old English dox ('dark, swarthy') — our /chain captures this "
                        "branch as a `der` edge from dogga.",
             "kaikki_template_present": True},
            {"summary": "from Proto-West Germanic *dugan ('to be suitable'); epithet meaning "
                        "'good/useful animal' used by children.",
             "kaikki_template_present": False},
            {"summary": "related to *docce ('stock, muscle') from Proto-West Germanic *dokkā, "
                        "whence English dock ('stumpy tail').",
             "kaikki_template_present": False},
        ],
        "gaps": {"missing_alternative_origins": True},
        "notes": ("Phase 2: Classic Q1 case. Wiktionary lists THREE parallel hypotheses for "
                  "docga. System surfaces only the 'dox' branch as a `der` edge. The other "
                  "two (*dugan, *dokkā) appear only in prose. is_uncertain=true flag "
                  "correctly set by classifier."),
    },
    "cupboard": {
        "excerpt": (
            "From Middle English cuppeborde, cupbord, equivalent to cup + board."
        ),
        "chain": [
            {"lang": "Middle English", "word": "cuppeborde"},
            {"lang": "English", "word": "cup",
             "note": "compound component — visible in tree_inh_bor_der_cog only"},
            {"lang": "English", "word": "board",
             "note": "compound component — visible in tree_inh_bor_der_cog only"},
        ],
        "alternative_theories": [],
        "gaps": {"missing_compound_components": True},
        "notes": ("Phase 2: Q2 PARTIAL. /chain returns only [cupboard → cuppeborde]; the "
                  "compound components 'cup' and 'board' do not appear there. They DO "
                  "appear in /tree_inh_bor_der_cog (verified: cup:English, board:English "
                  "with their own ancestries) thanks to main SPC-00012's precomputed "
                  "etymology_edges. So /chain still has the gap; /tree closes it."),
    },
    "blackbird": {
        "excerpt": (
            "From Middle English blakebird, blacbrid ('ouzel; Eurasian blackbird'), "
            "equivalent to black + bird."
        ),
        "chain": [
            {"lang": "Middle English", "word": "blakebird"},
            {"lang": "English", "word": "black",
             "note": "compound component — visible in tree_inh_bor_der_cog only"},
            {"lang": "English", "word": "bird",
             "note": "compound component — visible in tree_inh_bor_der_cog only"},
        ],
        "alternative_theories": [],
        "gaps": {"missing_compound_components": True},
        "notes": ("Phase 2: Same Q2 pattern as cupboard. /chain stops at the ME parent; "
                  "components black + bird only in /tree."),
    },
    "orange": {
        "excerpt": (
            "From Middle English orenge, orange, from Old French pome orenge ('fruit "
            "orange'), influenced by the place name Orange and calqued from Old "
            "Italian melarancio (mela 'apple' + un'arancia 'an orange'), from Arabic "
            "نَارَنْج (nāranj), from Early Classical Persian نَارَنْگ (nārang), from "
            "Sanskrit नारङ्ग (nāraṅga, 'orange tree'), ultimately from a Dravidian source."
        ),
        "chain": [
            {"lang": "Middle English", "word": "orenge"},
            {"lang": "Old French", "word": "pome orenge"},
            {"lang": "Old Occitan", "word": "auranja"},
            {"lang": "Old Italian", "word": "melarancio",
             "note": "calque source — surfaced in our chain as `roa-oit` (raw lang code, lang_cache miss)"},
            {"lang": "Arabic", "word": "نَارَنْج"},
            {"lang": "Early Classical Persian", "word": "نَارَنْگ",
             "note": "surfaced as `fa-cls` lang code (lang_cache miss)"},
            {"lang": "Sanskrit", "word": "नारङ्ग"},
        ],
        "alternative_theories": [],
        "gaps": {"missing_calques": True},
        "notes": ("Phase 2: Three quirks observed. (Q4) System captured Etymology 1 "
                  "(fruit); Etymology 2 (color, sense extension within English) not "
                  "represented. (Q5) Foreign-script ancestors نَارَنْج (Arabic), नारङ्ग "
                  "(Sanskrit) preserved in node IDs. (Q6) Calque relationship "
                  "'calqued from Old Italian melarancio' captured as `der` edge in our chain, "
                  "losing the calque semantic — system has no `cal` edge label. Also: "
                  "'influenced by the place name Orange' dropped entirely. Bonus finding: "
                  "lang_cache returns raw codes for `roa-oit` (Old Italian) and `fa-cls` "
                  "(Early Classical Persian) instead of human-readable names."),
    },
    "chuckle": {
        "excerpt": (
            "From chuck ('laugh') + -le (frequentative suffix)."
        ),
        "chain": [
            {"lang": "English", "word": "chuck", "note": "compound base"},
            {"lang": "English", "word": "-le", "note": "frequentative suffix"},
        ],
        "alternative_theories": [],
        "gaps": {"missing_compound_components": True},
        "notes": ("Phase 2: Empty /chain as expected (no ancestry templates, only `af`). "
                  "Frequentative formation chuck + -le. Components would surface in /tree "
                  "if main SPC-00012 indexed them — verify on regen."),
    },
}


def update_fixture(path: Path) -> None:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    word = fixture["query"]["word"]
    if word not in PHASE2:
        print(f"  skip: no Phase 2 data for {word}")
        return

    data = PHASE2[word]

    fixture["wiktionary_reference"] = {
        "etymology_section_text_excerpt": data["excerpt"],
        "expected_chain_per_wiktionary": data["chain"],
        "alternative_theories": data["alternative_theories"],
    }

    # Apply known_gaps overrides on top of what the collector heuristic produced.
    fixture["known_gaps"].update(data["gaps"])
    fixture["known_gaps"]["notes"] = "Phase 2 cross-check: see meta.notes for details."

    fixture["meta"]["notes"] = data["notes"]

    serialized = json.dumps(fixture, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.write_text(serialized, encoding="utf-8")
    print(f"  wrote {word}.json")


def main() -> None:
    for path in sorted(FIX_DIR.glob("*.json")):
        update_fixture(path)


if __name__ == "__main__":
    main()
