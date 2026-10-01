#!/usr/bin/env python3
"""The opening paragraph on 01-1, written per family.

    python intro_copy.py              # every family
    python intro_copy.py RAST         # one
    from intro_copy import values     # what build_family.py uses

    Product.Description_Intro

01-1 is the first page about a pattern, and until now its second paragraph
said the same thing on every one of them - and said what 01-2 says again
overleaf, that the tiling runs continuous across joints. The sheet that
introduces a pattern is the only place in the book to say why someone would
choose this one, so that is what goes there.

The rest of the book already has its jobs: 02-3 says what the pattern looks
like, 02-4 how the tiles meet, 02-5 what it sits beside, 05 what it measures.
This paragraph stays out of all of that. No codes, no tile mechanics, no
figures - open area and Effective NRC are on 05-1 and do not need saying
twice.

One paragraph, and a short one - the box on 01-1 holds about six lines, and
two paragraphs with a blank line between them ran past the bottom of it and
printed one line on top of another. Two sentences written by hand per family,
saying what the surface does and what sort of room it suits, then one that
follows from the panel count, because how many tiles a set has is what
decides how a set behaves at scale.

It does not close on lighting and acoustics. 02-3 ends on those already, and
saying it twice within six pages reads as filler.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
USERTEXT = HERE / "usertext_81.json"
INTROS = HERE / "intro_copy.csv"

KEY = "Product.Description_Intro"

# How a set behaves at scale, which is a question of how many tiles it has.
TILES = {
    1: "A single tile, so the field keeps a steady beat across a ceiling.",
    2: "Two tiles alternate, so the eye stops counting panels.",
    4: ("Four tiles carry the field, so a wall resolves without an obvious"
        " repeat."),
    8: ("Eight tiles keep it quiet at scale: a large ceiling resolves without"
        " the repeat a shorter set would show."),
}

FALLBACK = "offers a perforated field across the panel face"


def families() -> dict:
    data = json.loads(USERTEXT.read_text(encoding="utf-8"))
    return {r["group"]: r for r in data}


def intros() -> dict:
    if not INTROS.is_file():
        return {}
    out = {}
    with INTROS.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("family") or "").strip()
            if name:
                out[name] = (row.get("intro") or "").strip()
    return out


def values(group: str) -> dict:
    rows = families()
    row = rows[group]
    name = row["Name_14"]
    panels = int(float(row.get("Panel System") or 1))
    first = intros().get(name) or ("VEIL® %s %s." % (name, FALLBACK))
    return {KEY: "%s %s" % (first, TILES.get(panels, TILES[1]))}


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("family", nargs="?")
    ap.add_argument("--missing", action="store_true")
    args = ap.parse_args(argv[1:])

    rows = families()
    written = intros()
    names = sorted(set(r["Name_14"] for r in rows.values()))

    if args.missing:
        todo = [n for n in names if not written.get(n)]
        print("%d famil(ies), %d still to write" % (len(names), len(todo)))
        for n in todo:
            print("   %s" % n)
        return 0

    wanted = [args.family] if args.family else names
    for name in wanted:
        group = next((g for g, r in rows.items() if r["Name_14"] == name), None)
        if group is None:
            print("unknown family: %s" % name)
            continue
        print("=== %s" % name)
        print(values(group)[KEY])
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
