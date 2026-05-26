"""Apply SPC-00013 Phase 2: hand-encoded Wiktionary reference + known_gaps recalibration.

One-shot script. Reads each fixture, overwrites:
  - wiktionary_reference.etymology_section_text_excerpt
  - wiktionary_reference.expected_chain_per_wiktionary
  - wiktionary_reference.alternative_theories
  - wiktionary_reference.link_audit (NEW — see tests/fixtures/wiktionary/LINK_AUDIT.md)
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
        # Worked-example link audit. Each entry mirrors a chain entry plus the
        # alternative-borrowing-path ancestors (Latin → Proto-Italic → PIE). See
        # tests/fixtures/wiktionary/LINK_AUDIT.md for the schema and methodology.
        "link_audit": [
            {"lang": "Middle English", "word": "wyn",
             "wiktionary_url": "https://en.wiktionary.org/wiki/wyn",
             "namespace": "main", "page_exists": True,
             "note": "main-namespace entry; also lists 'wynn' as a variant marker"},
            {"lang": "Old English", "word": "wīn",
             "wiktionary_url": "https://en.wiktionary.org/wiki/w%C4%ABn",
             "namespace": "main", "page_exists": True},
            {"lang": "Proto-West Germanic", "word": "*wīn",
             "wiktionary_url": "https://en.wiktionary.org/wiki/Reconstruction:Proto-West_Germanic/w%C4%ABn",
             "namespace": "Reconstruction", "page_exists": True,
             "note": "asterisk-prefixed reconstruction lives in Reconstruction:"},
            {"lang": "Proto-Germanic", "word": "*wīną",
             "wiktionary_url": "https://en.wiktionary.org/wiki/Reconstruction:Proto-Germanic/w%C4%ABn%C4%85",
             "namespace": "Reconstruction", "page_exists": True},
            {"lang": "Latin", "word": "vīnum",
             "wiktionary_url": "https://en.wiktionary.org/wiki/vinum",
             "namespace": "main", "page_exists": True,
             "note": "macron stripped in URL (Wiktionary normalizes to vinum)"},
            {"lang": "Proto-Italic", "word": "*wīnom",
             "wiktionary_url": "https://en.wiktionary.org/wiki/Reconstruction:Proto-Italic/w%C4%ABnom",
             "namespace": "Reconstruction", "page_exists": True,
             "note": "reached only via the Latin-borrowing branch"},
            {"lang": "Proto-Indo-European", "word": "*wóyh₁nom",
             "wiktionary_url": "https://en.wiktionary.org/wiki/Reconstruction:Proto-Indo-European/w%C3%B3yh%E2%82%81nom",
             "namespace": "Reconstruction", "page_exists": True,
             "note": "PIE root; Wiktionary's wine page derives this from deeper "
                     "*weh₁y- ('to twist; to wrap'). System chain stops at *wóyh₁nom."},
            {"lang": "Proto-Indo-European", "word": "*weh₁y-",
             "wiktionary_url": "https://en.wiktionary.org/wiki/Reconstruction:Proto-Indo-European/weh%E2%82%81y-",
             "namespace": "Reconstruction", "page_exists": True,
             "note": "deeper PIE root mentioned in prose; some sources suggest "
                     "*wéyh₁ō may have been borrowed from Proto-West Semitic or "
                     "Proto-Kartvelian — a Q1-style alternative our system misses"},
        ],
        "gaps": {"missing_alternative_origins": True, "missing_doublet_link": True},
        "notes": ("Phase 2: Wiktionary presents 'either/or' between direct PIE inheritance and "
                  "early Latin borrowing. Our /chain commits to the borrowing path "
                  "(*wīną ← der ← vīnum). Doublet 'vine' present as `doublet` template, not "
                  "surfaced as graph edge. Link audit reveals a deeper-still root "
                  "(*weh₁y-) and a non-IE borrowing hypothesis (Semitic/Kartvelian) "
                  "neither of which appears in our chain."),
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
        "link_audit": [
            {"lang": "Middle English", "word": "hound",
             "wiktionary_url": "https://en.wiktionary.org/wiki/hound",
             "namespace": "main", "page_exists": True,
             "note": "shares the page with the English entry — different language sections"},
            {"lang": "Old English", "word": "hund",
             "wiktionary_url": "https://en.wiktionary.org/wiki/hund",
             "namespace": "main", "page_exists": True,
             "note": "multilingual page; Old English section"},
            {"lang": "Proto-West Germanic", "word": "*hund",
             "wiktionary_url": "https://en.wiktionary.org/wiki/Reconstruction:Proto-West_Germanic/hund",
             "namespace": "Reconstruction", "page_exists": True},
            {"lang": "Proto-Germanic", "word": "*hundaz",
             "wiktionary_url": "https://en.wiktionary.org/wiki/Reconstruction:Proto-Germanic/hundaz",
             "namespace": "Reconstruction", "page_exists": True},
            {"lang": "Pre-Germanic", "word": "*kun-tós",
             "wiktionary_url": None,
             "namespace": "missing", "page_exists": False,
             "note": "Pre-Germanic is not a Wiktionary language — no link target. "
                     "The form is mentioned in prose on the PGmc *hundaz page only."},
            {"lang": "Proto-Indo-European", "word": "*ḱwṓ",
             "wiktionary_url": "https://en.wiktionary.org/wiki/Reconstruction:Proto-Indo-European/%E1%B8%B1w%E1%B9%93",
             "namespace": "Reconstruction", "page_exists": True,
             "note": "URL path is heavily percent-encoded (ḱ → %E1%B8%B1, ṓ → %E1%B9%93). "
                     "Sanity-check that our node IDs preserve the un-encoded form."},
        ],
        "gaps": {},
        "notes": ("Phase 2: Pre-Germanic *kun-tós/*ḱwn̥tós described in prose only — "
                  "no template, so our chain jumps PGmc → PIE directly. Cognates "
                  "(Old Armenian սկունդ etc.) listed inline as `cog` templates, visible in "
                  "tree_inh_bor_der_cog but not /chain. Q13 fix verified: *hundaz resolves "
                  "via the asterisk-normalised lookup. Link audit confirms Pre-Germanic "
                  "has no Wiktionary page — Q8 is upstream (Wiktionary), not just our gap."),
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
            "'art of alloying metals'), from χύμα (khúma, 'ingot, bar'). "
            "Doublet of chemistry via the shared Greek root."
        ),
        "chain": [
            {"lang": "Middle English", "word": "alkamye",
             "note": "intermediate skipped by our /chain — Kaikki has no `inh` ME template"},
            {"lang": "Old French", "word": "alkimie"},
            {"lang": "Medieval Latin", "word": "alchēmia",
             "note": "lang_cache miss — system has lang code `la-med`, not 'Medieval Latin'"},
            {"lang": "Arabic", "word": "اَلْكِيمِيَاء",
             "note": "Arabic diacritic stripping — system has bare form `كيمياء`"},
            {"lang": "Ancient Greek", "word": "χυμείᾱ"},
            {"lang": "Ancient Greek", "word": "χύμα",
             "note": "deeper root — system chain stops at χυμείᾱ"},
        ],
        "alternative_theories": [],
        "link_audit": [
            {"lang": "Middle English", "word": "alkamye",
             "wiktionary_url": "https://en.wiktionary.org/wiki/alkamye",
             "namespace": "main", "page_exists": False,
             "note": "no Wiktionary entry confirmed via search — Q3 dead link. "
                     "Wiktionary's `alchemy` etymology references the ME form only in prose."},
            {"lang": "Old French", "word": "alkimie",
             "wiktionary_url": "https://en.wiktionary.org/wiki/alkimie",
             "namespace": "main", "page_exists": True,
             "note": "verified — Old French entry exists"},
            {"lang": "Medieval Latin", "word": "alchēmia",
             "wiktionary_url": "https://en.wiktionary.org/wiki/alchemia",
             "namespace": "main", "page_exists": True,
             "note": "Wiktionary URL strips the macron (alchēmia → alchemia); "
                     "the entry includes the Medieval Latin section"},
            {"lang": "Arabic", "word": "اَلْكِيمِيَاء",
             "wiktionary_url": "https://en.wiktionary.org/wiki/%D8%A7%D9%84%D9%83%D9%8A%D9%85%D9%8A%D8%A7%D8%A1",
             "namespace": "main", "page_exists": True,
             "note": "URL path encodes the bare form `الكيمياء` (no harakat). "
                     "Our system stores it the same way, but the template arg "
                     "carries the fully-vocalised form — the gap is at lookup time."},
            {"lang": "Ancient Greek", "word": "χυμείᾱ",
             "wiktionary_url": "https://en.wiktionary.org/wiki/%CF%87%CF%85%CE%BC%CE%B5%CE%AF%CE%B1",
             "namespace": "main", "page_exists": True,
             "note": "Wiktionary URL drops the macron on the final alpha (χυμείᾱ → χυμεία)"},
            {"lang": "Ancient Greek", "word": "χύμα",
             "wiktionary_url": "https://en.wiktionary.org/wiki/%CF%87%CF%8D%CE%BC%CE%B1",
             "namespace": "main", "page_exists": True,
             "note": "deeper root reached only by Wiktionary's prose; our chain "
                     "stops at χυμείᾱ"},
        ],
        "gaps": {"missing_doublet_link": True},
        "notes": ("Phase 2: Doublet of `chemistry` via Greek χυμεία — not surfaced. "
                  "Chain truncated before deepest Greek root χύμα. Two bonus quirks "
                  "found: (a) lang_cache miss for `la-med` (Medieval Latin); (b) Arabic "
                  "diacritic stripping — system stores bare form `كيمياء` while "
                  "Wiktionary template uses fully-vocalised `اَلْكِيمِيَاء`. Middle English "
                  "alkamye absent from chain because Kaikki has no ME→OE `inh` template "
                  "(jumps English ← Old French directly)."),
    },
    "chemistry": {
        "excerpt": (
            "First attested 1605, from chemist + -ry. Doublet of alchemy via the "
            "same ultimate Greek/Arabic root."
        ),
        "chain": [
            {"lang": "English", "word": "chemist",
             "note": "compound component — also missing from /tree (SPC-00012 doesn't normalize `suf`/`derived`)"},
            {"lang": "English", "word": "-ry",
             "note": "compound component (suffix) — also missing from /tree"},
        ],
        "alternative_theories": [],
        "gaps": {"missing_compound_components": True, "missing_doublet_link": True},
        "notes": ("Phase 2: System /chain is EMPTY despite Wiktionary clearly stating "
                  "'chemist + -ry'. Surprise finding: main SPC-00012 ALSO misses this — "
                  "templates are `suf`/`derived` not `compound`/`suffix`, and SPC-00012 "
                  "doesn't normalize those variants. So Q2 is OPEN at /tree too for "
                  "chemistry. Doublet of alchemy not surfaced as edge."),
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
            {"lang": "English", "word": "chuck",
             "note": "compound component — appears in /tree via SPC-00012 (verified)"},
            {"lang": "English", "word": "-le",
             "note": "compound component (frequentative suffix) — missing from /tree (no -le entry)"},
        ],
        "alternative_theories": [],
        "gaps": {"missing_compound_components": True},
        "notes": ("Phase 2: Empty /chain as expected (only `af` template). Components: "
                  "`chuck` DOES surface in /tree_inh_bor_der_cog as a `component` edge "
                  "(SPC-00012 works here). `-le` does NOT — suffix has no Kaikki doc, "
                  "so the component edge dangles."),
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
        "link_audit": data.get("link_audit", []),
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
