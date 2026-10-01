#!/usr/bin/env python3
"""Write the print spec for one pattern.

    python build_family.py Herringbone
    python build_family.py --list

The brochure walks the same sheets whatever is being printed; what changes is
which panels go in the four slots, whether there is a compatible-patterns
sheet at all, and the numbers on the two lighting sheets and the acoustic one.

The slot sheet follows the panel count, because a system with one panel has
nothing to alternate:

    1 panel   02-3-1P    A A A A
    2 panels  02-3-2P    A B B A
    4 panels  02-3-4P    A B C D
    8 panels  02-3-8P-A    A B C D
                02-3-8P-B    E F G H

A pattern that has no compatible partners does not get 02-5: a page headed
COMPATIBLE PATTERNS showing four copies of the same panel says nothing.
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
sys.path.insert(0, str(HERE))
import linear_led  # noqa: E402
import pattern_copy  # noqa: E402
import intro_copy  # noqa: E402
SPEC = HERE / "family_spec.json"
USERTEXT = HERE / "usertext_81.json"
ACOUSTIC = HERE / "acoustic_pattern_81.csv"
LIGHTING = HERE / "lighting_81.csv"
CHARTS = HERE / "charts"

DXF_DIR = ("N:/Products/Development/Product Lab/VEIL/VEIL_Pattern Development"
           "/Pattern Export/New Pattern Set")
OUT_DIR = str(HERE / "smoke").replace("\\", "/")
PREFIX = "Reference_"

BANDS = (80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
         1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000)
HEIGHTS = ("0.5", "1", "2", "3", "4", "5", "7.5", "10", "20")
FT = 3.280839895

# panel count -> the slot sheet, and which panel each of the four slots shows
SLOT_SHEETS = {
    1: [("02-3-1P", "AAAA")],
    2: [("02-3-2P", "ABBA")],
    4: [("02-3-4P", "ABCD")],
    8: [("02-3-8P-A", "ABCD"), ("02-3-8P-B", "EFGH")],
}

PAGES = ["TITLE", "01-1", "01-2", "02-TITLE", "02-1", "02-2",
         "@slots", "02-4", "@compatible",
         "03-TITLE", "03-1", "03-2", "03-3", "03-4",
         "04-TITLE", "04-1", "04-2", "04-3", "04-4-A", "04-4-B",
         "04-5-A", "04-5-B",
         "05-TITLE", "05-1", "05-2-A", "05-2-B", "05-3",
         "05-4-A", "05-4-B", "05-4-C", "00-A-C"]

# 05-2-B is the InLine fixture, the same on every sheet.
INLINE_POLAR = "InLine_10Wft_4ft_polar.png"

# 02-4 shows a wall built from a 4 x 4 block of panels, and it draws it
# through the four CONFIG slots. A set of eight cannot go through four, so
# that sheet repeats A to D and the other half of the set is never seen. For
# an eight-panel system the cells are named one by one instead.
#
# The set is laid four across and two down - A1 B1 C1 D1 over A2 B2 C2 D2 in
# the old labels, which sort to A C E G over B D F H. Two of those fill the
# four-by-four.
EIGHT_WIDE = ["ACEG", "BDFH"]


def variant_of(group: str) -> str:
    """The three characters after the family tag: FUME_SPR -> SPR."""
    return group.split("_", 1)[1] if "_" in group else group


def trim(x: float) -> str:
    t = "%.1f" % x
    return t[:-2] if t.endswith(".0") else t


def rows(path: Path) -> dict:
    with path.open(encoding="utf-8-sig") as fh:
        return {r["group"]: r for r in csv.DictReader(fh)}


def num(v, default=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def panel_count(group: str) -> int:
    """How many panels the set has, counted from the blocks on disk."""
    n = 0
    for letter in "ABCDEFGH":
        if (Path(DXF_DIR) / ("%s.dxf" % group)).is_file():
            n = 0
            break
    # the DXF holds all of them, so read the count off the user text instead
    return n


def usertext_rows() -> dict:
    data = json.loads(USERTEXT.read_text(encoding="utf-8"))
    return {r["group"]: r for r in data}


def build(group: str) -> dict:
    users = usertext_rows()
    if group not in users:
        raise KeyError(group)
    u = users[group]
    acoustic = rows(ACOUSTIC)[group]
    light = rows(LIGHTING)[group]

    panels = int(num(u.get("Panel System"), 1))
    if panels not in SLOT_SHEETS:
        raise ValueError("%s claims %d panels, which has no sheet"
                         % (group, panels))

    openness = num(light["open_pct"])
    x = {k: num(acoustic["x_%s" % k]) for k in "ABCD"}
    raw = sum(x.values()) / 4.0
    effective = round(raw * 20) / 20        # NRC is quoted to the nearest 0.05

    text = {
        "Product.Name_14": u["Name_14"],
        "Product.Description_Panel Set": u["Name_14"],
        "Product.Description_03-Configurability": u["Configurability"],
        # The document key is spelled correctly; usertext_81.json keeps its
        # own column names, typo and all, because that file is the source.
        "Product.Description_04-Compatible Pattern": u["Compatable Pattern"],
        "Product.Description_04-B-Compatible Pattern Name":
            u["Compatable Pattern Name"] or u["Name_14"],
        "Product.Description_05-Panel System": str(panels),
        "Product.Description_06-Pattern Type": u["Pattern Type"],
        "Product.Description_06-Openness": "%.1f%%" % openness,
        "Product.Acoustic_EffectiveNRC": "%.2f" % effective,
    }
    for b in BANDS:
        text["Product.Acoustic_SAC_%d" % b] = acoustic["SAC_%d" % b]

    power = "45"
    peak = num(light["peak_cd_%sW" % power])
    flux = num(light["lumens_%sW" % power])
    text.update({
        "Product.Lighting_Openness": "%.1f%%" % openness,
        "Product.Lighting_Power": "%s W" % power,
        "Product.Lighting_Optic": "115\u00b0",
        "Product.Lighting_OnAxis": "%d cd" % round(peak),
        "Product.Lighting_PeakIntensity": "%d cd" % round(peak),
        "Product.Lighting_TotalFlux": "%d lm" % round(flux),
        "Product.Lighting_Efficacy": "%.1f lm/W"
                                     % num(light["efficacy_%sW_lmW" % power]),
    })
    for h in HEIGHTS:
        width = num(light["beam_m_%sm" % h])
        pair = "%sm/%s'" % (trim(width), trim(width * FT))
        text["Product.Lighting_BW_C0_%sm" % h] = pair
        text["Product.Lighting_BW_C90_%sm" % h] = pair
        text["Product.Lighting_Lux_%sm" % h] = \
            "%d lx" % round(num(light["lux_%sW_%sm" % (power, h)]))

    # 05-2-B is the same fixture on every sheet, but its values still have to
    # be in the document: a DocumentText field with no key behind it prints
    # as ####, which is what the whole sheet did when this was left out.
    text.update(linear_led.values())

    # The panel labels on 02-3. They read "Panel A" today, which is the same
    # on every sheet; the code is not, so each one becomes a field. The value
    # is the part of the code that identifies the panel - FUME_SPRA shows as
    # SPRA, because the family is already in the title above it.
    for i, letter in enumerate("ABCDEFGH"):
        key = "Product.Description_Panel Code %s" % letter
        # A slot the set does not reach prints as nothing. It cannot be
        # an empty string: Rhino shows an unset document key as ####, so the
        # value is a single space.
        text[key] = ("%s%s" % (variant_of(group), letter)
                     if i < panels else " ")

    # The two paragraphs on 02-3. Only one phrase in the first changes
    # between patterns; the second follows from the panel count.
    text.update(pattern_copy.values(group))

    # 01-1's opening paragraph. It used to be the same words on every
    # pattern, and the same point 01-2 makes overleaf.
    text.update(intro_copy.values(group))

    sequence = []
    for page in PAGES:
        if page == "@slots":
            for sheet, letters in SLOT_SHEETS[panels]:
                sequence.append({
                    "page": sheet,
                    "label": u["Name_14"],
                    # The panel letter joins straight on: RING_PLN + A.
                    # The only underscore in a code is the one after the
                    # family tag.
                    "slots": dict(zip("ABCD",
                                      ["%s%s%s" % (PREFIX, group, v)
                                       for v in letters])),
                })
            continue
        if page == "@compatible":
            # Nothing to be compatible with, nothing to show.
            if u["Compatable Pattern"].strip().upper() != "YES":
                continue
            sequence.append({"page": "02-5-Transition only"})
            continue
        step = {"page": page}
        if page == "02-4" and panels == 8:
            step["grids"] = [[[{"block": "%s%s%s" % (PREFIX, group, v)}
                               for v in row]
                              for row in EIGHT_WIDE * 2]]
            step["label"] = "8 tiles, 4 across"
        if page == "05-2-A":
            step["chart"] = {"polar": "%s_polar_%sW.png" % (group, power)}
        elif page == "05-2-B":
            step["chart"] = {"polar": INLINE_POLAR}
        elif page == "05-3":
            step["chart"] = {"sac": group}
        sequence.append(step)

    return {
        "dpi": 200,
        # False writes vector text and linework instead of baking the
        # sheet to a bitmap. See capture() in export_family.py.
        "raster": True,
        "flip_face": True,
        # Rhino calls this to lay the charts on once the PDF is written; its
        # own IronPython cannot load Pillow or PyMuPDF.
        "python": sys.executable,
        "dxf_dir": DXF_DIR,
        "out_dir": OUT_DIR,
        "jobs": [{
            "family": group,
            "dxf": [group],
            "usertext": text,
            "sequence": sequence,
        }],
    }


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("group", nargs="?")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args(argv[1:])

    users = usertext_rows()
    if args.list or not args.group:
        by = {}
        for g, u in users.items():
            by.setdefault(int(num(u.get("Panel System"), 1)), []).append(g)
        for n in sorted(by):
            print("%d panel(s): %d pattern(s)" % (n, len(by[n])))
            for g in sorted(by[n]):
                print("   %s" % g)
        return 0

    if args.group not in users:
        print("unknown pattern: %s" % args.group)
        return 2

    spec = build(args.group)
    SPEC.write_text(json.dumps(spec, indent=1, ensure_ascii=False,
                               sort_keys=True), encoding="utf-8")
    job = spec["jobs"][0]
    u = users[args.group]
    print("%s - %s panel system, %d page(s)"
          % (args.group, u["Panel System"], len(job["sequence"])))
    for step in job["sequence"]:
        extra = ""
        if step.get("slots"):
            extra = " <- " + ", ".join(
                "%s=%s" % (k, v[len(PREFIX):]) for k, v in sorted(step["slots"].items()))
        if step.get("chart"):
            extra = " <- " + str(step["chart"])
        if extra:
            print("   %-24s%s" % (step["page"], extra))
    print("")
    print("Effective NRC %s, openness %s"
          % (job["usertext"]["Product.Acoustic_EffectiveNRC"],
             job["usertext"]["Product.Description_06-Openness"]))
    print("-> %s" % SPEC.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
