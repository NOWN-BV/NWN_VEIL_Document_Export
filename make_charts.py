#!/usr/bin/env python3
"""Render the polar plots the brochure's lighting sheets ask for.

    python make_charts.py                 # every pattern
    python make_charts.py Basalt-P10 ...  # just these

Runs OUTSIDE Rhino, before export_family.py: the plot comes from the
Panel Reference generator, which is CPython and needs Pillow, and Rhino's
IronPython 2.7 can run neither.

Two things go on the spec sheets and only one of them is an image. The
acoustic sheet already carries its own grid, axes and labels, so its curve is
drawn as Rhino geometry at export time and nothing is rendered here. The
"Polar Plots" box on 05-2-A and 05-2-B is empty - 163.4 x 96.0 mm of nothing -
so that one is a transparent PNG, exactly as Vapor's datasheet does it.

The canvas is Vapor's, scaled to the height of Veil's box so the plot keeps
its proportions, and the SAC series each pattern needs at export time is
written out beside the images.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLAR_SRC = HERE / "panelref" / "08_lighting"
NRC_SRC = Path(r"C:/dev/NRC Testing")
OUT = HERE / "charts"
LIGHTING = HERE / "lighting_81.csv"
SPECS = HERE / "lighting_specs.csv"
ACOUSTIC = HERE / "acoustic_pattern_81.csv"

BANDS = (80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
         1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000)

# The empty box on 05-2-A / 05-2-B, measured off the brochure.
BOX_W_MM = 163.4
BOX_H_MM = 96.0

sys.path.insert(0, str(POLAR_SRC))
import generate_polar_plot as gpp  # noqa: E402

# The acoustic sheet's chart is not a line - it is the figure NRC Testing
# already draws: a dashed SAC trace, a marked rectangle per band shaded by
# its A/B/C/D group, a wide marker at each group average x1..x4, the fills
# between them, and the Effective NRC rule across the whole width. Its canvas
# is 172.9688 x 76.875 mm on 6.41 x 5.13 mm cells, which is the grid printed
# on 05-3 to the millimetre, so the overlay drops straight on.
sys.path.insert(0, str(NRC_SRC))
import render_true_nrc_chart as nrc  # noqa: E402

# The backlighting plot comes off the .ies files rather than a falloff
# formula, which is also what lets its third curve - the envelope over all
# 25 C-planes - be the measured one instead of a drawn circle.
import polar_measured as pm  # noqa: E402

# Vapor's canvas is 136.65 x 123.0 with a 102.5 mm circle. Veil's box is
# shorter, so everything shrinks by the same factor and the plot still reads
# as the same drawing.
# The box is 163.4 wide but only 96.0 tall, so height is what limits the
# plot - the spare width goes to the ring labels. Vapor leaves 10mm of air
# above and below its circle; 4mm is enough here and buys a bigger plot.
CANVAS_H_MM = BOX_H_MM
CIRCLE_D_MM = BOX_H_MM - 8.0
SCALE = CIRCLE_D_MM / gpp.DEFAULT_CIRCLE_DIAMETER_MM

# The ring labels sit a fixed distance outside the circle, so the margin they
# need is the same whatever size the circle is - scaling the width along with
# the circle cuts them off. Vapor's own canvas is its circle plus this much.
LABEL_MARGIN_MM = gpp.DEFAULT_CANVAS_W_MM - gpp.DEFAULT_CIRCLE_DIAMETER_MM
CANVAS_W_MM = round(CIRCLE_D_MM + LABEL_MARGIN_MM, 3)
TEXT_H_MM = 2.5                      # cap height stays legible, unscaled

# The blue curve the generator calls an "envelope" is not measured: it is a
# circle at 98.5% of peak with a sine wobble added for texture. Two of the
# three curves are real (the C0-180 and C90-270 planes); this one would read
# as a third measurement on a spec sheet, so it is off here.
DRAW_ENVELOPE = False

# --- 05-2-B, the InLine linear fixture --------------------------------------
#
# 05-2-A stands on eight LM-79 goniophotometric tests. 05-2-B does not: the
# only InLine source is the Arktura tearsheet, and it publishes lumens per
# foot and efficacy - no beam angle, no candela distribution. So this plot is
# CALCULATED, not measured. A bare linear extrusion with no lens is Lambertian,
# which puts the on-axis intensity at flux / pi and the falloff at cos(a)^1,
# and that is all this draws. If InLine is ever put on a goniophotometer,
# replace this with the .ies the way 05-2-A was.
INLINE_FALLOFF = 1.0
LAMBERTIAN_PEAK = math.pi        # flux = pi x I0 over the hemisphere


def log_interp(sac: dict[int, float], freq: int) -> float:
    """A band the test does not report, read off the two that surround it.

    The chart wants 750 Hz and 1500 Hz so its dashed trace has a vertex in
    the gap columns, and neither is a third-octave band, so neither is in the
    measured set. Frequency is logarithmic, so the interpolation is too.
    """
    known = sorted(sac)
    below = [f for f in known if f <= freq]
    above = [f for f in known if f >= freq]
    if not below or not above:
        return sac[known[0] if not below else known[-1]]
    lo, hi = below[-1], above[0]
    if lo == hi:
        return sac[lo]
    t = (math.log(freq) - math.log(lo)) / (math.log(hi) - math.log(lo))
    return sac[lo] + t * (sac[hi] - sac[lo])


def render_nrc_overlay(group: str, row: dict) -> dict:
    """The Effective NRC figure for one pattern, as a transparent overlay."""
    sac = {b: num(row["SAC_%d" % b]) for b in BANDS}
    for gap in (f for _, f in nrc.GAP_CELL_FREQ):
        if gap not in sac:
            sac[gap] = log_interp(sac, gap)

    groups = {"x1": "x_A", "x2": "x_B", "x3": "x_C", "x4": "x_D"}
    avgs = {k: num(row[v]) for k, v in groups.items()}
    raw = sum(avgs.values()) / 4.0
    # NRC is quoted to the nearest 0.05, and the sheet's rule sits on that
    # value, so the number printed beside it has to be the same one.
    rounded = round(raw * 20) / 20

    nrc.render(sac, avgs, raw, rounded, OUT / ("%s_nrc_overlay.png" % group))
    return {"x": avgs, "effective_nrc_raw": round(raw, 4),
            "effective_nrc": rounded}


def rows(path: Path) -> dict[str, dict]:
    with path.open(encoding="utf-8-sig") as fh:
        return {r["group"]: r for r in csv.DictReader(fh)}


def num(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def inline_options() -> list[dict]:
    """The eight InLine fixtures, off the tearsheet table."""
    out = []
    with SPECS.open(encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            if len(row) < 6 or not row[0].startswith("InLine "):
                continue
            try:
                flux = float(row[4])
            except ValueError:
                continue
            slug = (row[0].replace("InLine ", "").replace(" ", "")
                    .replace("/", "").replace("-", "_"))
            out.append({"name": row[0], "slug": slug, "flux_lm": flux,
                        "peak_cd": round(flux / LAMBERTIAN_PEAK, 1)})
    return out


def render_inline() -> list[dict]:
    opts = inline_options()
    for o in opts:
        gpp.render(0.0, "25", OUT / ("InLine_%s_polar.png" % o["slug"]),
                   canvas_w_mm=CANVAS_W_MM, canvas_h_mm=CANVAS_H_MM,
                   circle_d_mm=CIRCLE_D_MM, text_h_mm=TEXT_H_MM,
                   dpi=gpp.DEFAULT_DPI, envelope=DRAW_ENVELOPE,
                   peak=o["peak_cd"], falloff=INLINE_FALLOFF)
    return opts


def main(argv: list[str]) -> int:
    light = rows(LIGHTING)
    acoustic = rows(ACOUSTIC)

    wanted = argv[1:] or sorted(light)
    unknown = [g for g in wanted if g not in light]
    if unknown:
        print("unknown pattern(s): %s" % ", ".join(unknown))
        return 2

    OUT.mkdir(exist_ok=True)
    print("canvas %.1f x %.1f mm, circle %.1f mm (Vapor x %.3f)"
          % (CANVAS_W_MM, CANVAS_H_MM, CIRCLE_D_MM, SCALE))

    series = {}
    for group in wanted:
        for power in ("25", "45"):
            info = pm.build(group, power, light)
            print("  %-36s %s W  shape from the %.0f%% sample, peak %.0f cd"
                  % (group, power, info["sample_openness_pct"],
                     info["peak_cd"]))
        a = acoustic.get(group)
        if a is None:
            print("  %-36s no acoustic row - curve will be skipped" % group)
            continue
        over = render_nrc_overlay(group, a)
        series[group] = {
            "sac": [num(a["SAC_%d" % b]) for b in BANDS],
            "effective_nrc": over["effective_nrc"],
            "effective_nrc_raw": over["effective_nrc_raw"],
            "x": over["x"],
            "effective_nrc_csv": num(a["Effective_NRC"]),
            "nrc": num(a["NRC"]),
            "openness_pct": num(light[group]["open_pct"]),
            "peak_cd_25W": num(light[group]["peak_cd_25W"]),
            "peak_cd_45W": num(light[group]["peak_cd_45W"]),
        }
        print("  %-36s openness %5.1f%%  eNRC %.2f (raw %.3f)" % (
            group, num(light[group]["open_pct"]),
            series[group]["effective_nrc"], series[group]["effective_nrc_raw"]))

    inline = render_inline()
    print("InLine (calculated, Lambertian - no measured photometry exists):")
    for o in inline:
        print("  %-28s %6.0f lm -> peak %6.1f cd" % (o["name"], o["flux_lm"], o["peak_cd"]))

    meta = {
        "bands": list(BANDS),
        "inline": inline,
        "canvas_w_mm": CANVAS_W_MM,
        "canvas_h_mm": CANVAS_H_MM,
        "patterns": series,
    }
    (OUT / "charts.json").write_text(
        json.dumps(meta, indent=1, sort_keys=True), encoding="utf-8")
    print("%d pattern(s) -> %s" % (len(wanted), OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
