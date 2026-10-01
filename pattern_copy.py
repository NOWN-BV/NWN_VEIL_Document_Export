#!/usr/bin/env python3
"""The two paragraphs on 02-3, written per pattern.

    python pattern_copy.py                 # every pattern
    python pattern_copy.py Herringbone     # just this one
    python pattern_copy.py --missing       # families still without a clause

Two document keys:

    Product.Description_Pattern Copy    the paragraph about the pattern
    Product.Description_Tile System     how the tiles go together

Only one phrase in the first paragraph changes between patterns - what the
perforations do - and that phrase cannot be derived from the geometry, so it
is written by hand, once per family, in pattern_copy.csv. The 81 patterns
share 31 families, so that is 31 lines rather than 81. The two sentences
about lighting and acoustics are the same on every sheet.

The second paragraph is not written at all: it follows from the panel count
and from whether the panels are interchangeable, both of which are already
recorded. A one-tile pattern says nothing about interchangeability - with a
single tile there is nothing to interchange.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
USERTEXT = HERE / "usertext_81.json"
CLAUSES = HERE / "pattern_copy.csv"

KEY_COPY = "Product.Description_Pattern Copy"
KEY_TILE = "Product.Description_Tile System"

TAIL = ("Add illumination with our integrated InLine Lighting or Backlighting"
        " options, or acoustic absorption with our high performance Asoft®"
        " backers.")

WORDS = {1: "one", 2: "two", 3: "three", 4: "four",
         5: "five", 6: "six", 7: "seven", 8: "eight"}

# Used when a family has no clause yet, so a sheet still reads as a sentence.
FALLBACK = "carry a perforated pattern across the panel face"


def families() -> dict:
    data = json.loads(USERTEXT.read_text(encoding="utf-8"))
    return {r["group"]: r for r in data}


def clauses() -> dict:
    if not CLAUSES.is_file():
        return {}
    out = {}
    with CLAUSES.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("family") or "").strip()
            if name:
                out[name] = (row.get("clause") or "").strip()
    return out


def paragraph(name: str, clause: str) -> str:
    return "VEIL® %s's powder coated panels %s. %s" % (name, clause, TAIL)


def tile_sentence(panels: int, interchangeable: bool) -> str:
    word = WORDS.get(panels, str(panels))
    if panels <= 1:
        # Nothing to interchange, so nothing to say about it.
        return ("The pattern surface is created using one tile, drawn so the"
                " pattern continues across every joint.")
    if interchangeable:
        return ("The pattern surface is created using %s tiles, drawn so the"
                " pattern continues across every joint. Panels are"
                " interchangeable; there is no sequence to hold." % word)
    return ("The pattern surface is created using %s unique tiles in a"
            " specific arrangement that minimizes visual repetition across"
            " your space." % word)


def values(group: str) -> dict:
    row = families()[group]
    name = row["Name_14"]
    clause = clauses().get(name) or FALLBACK
    panels = int(row.get("Panel System") or 1)
    interchangeable = (row.get("Configurability") or "").strip().upper() == "YES"
    return {
        KEY_COPY: paragraph(name, clause),
        KEY_TILE: tile_sentence(panels, interchangeable),
    }


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("group", nargs="?")
    ap.add_argument("--missing", action="store_true")
    args = ap.parse_args(argv[1:])

    fam = families()
    written = clauses()

    if args.missing:
        names = sorted(set(r["Name_14"] for r in fam.values()))
        todo = [n for n in names if not written.get(n)]
        print("%d famil(ies), %d still to write" % (len(names), len(todo)))
        for n in todo:
            print("   %s" % n)
        return 0

    groups = [args.group] if args.group else sorted(fam)
    unknown = [g for g in groups if g not in fam]
    if unknown:
        print("unknown pattern(s): %s" % ", ".join(unknown))
        return 2

    for g in groups:
        v = values(g)
        print("=== %s" % g)
        print("   %s" % v[KEY_COPY])
        print("")
        print("   %s" % v[KEY_TILE])
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
