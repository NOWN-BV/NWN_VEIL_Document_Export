#!/usr/bin/env python3
"""Polar plots drawn from the goniophotometry, not from a formula.

    python polar_measured.py Basalt-P10 25
    python polar_measured.py --check          # what the .ies files contain

WHAT THE THIRD CURVE IS

The Vapor plot has three: the C0-180 plane, the C90-270 plane, and a blue
outer trace. LUX-TSI's own plots draw that third one as the envelope - at
each angle off the fixture axis, the highest intensity found in any C-plane,
so the curve bounds the whole distribution rather than describing one slice
through it. The generator in the Panel Reference repo could not compute it,
having only a peak value to work from, and drew a circle at 98.5% of peak
with a sine wobble instead. That is why it was switched off: a drawn circle
reads on a spec sheet as a third measurement.

The .ies files hold what is needed to draw it properly - 25 C-planes at 73
vertical angles each - so here the envelope is the real one.

WHERE THE NUMBERS COME FROM

Eight LM-79 tests cover three open areas (10%, 19%, 40%) at 25 W and 45 W.
The shape of the distribution barely moves between them, because it is the
same LED ladder behind different perforation densities; what changes is the
magnitude, and that tracks open area. So a pattern's plot takes its shape
from the measured sample nearest its openness, normalised, and its magnitude
from the peak intensity already fitted across all three in lighting_81.csv.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
POLAR_SRC = HERE / "panelref" / "08_lighting"
OUT = HERE / "charts"
LIGHTING = HERE / "lighting_81.csv"

IES_DIR = Path("N:/Products/Products/Documents/Product Tests + Third-Party"
               " Verified Certifications/VAPOR LED Ladder Couleur LUX-TSI Testing")

# open area -> the sample measured at it, per power
SAMPLES = {
    "25": [(10.0, "25W/GNC-35698 (NOWN)-25W_VAPOR CLUSTER SPARSE).ies"),
           (19.0, "25W/GNC-35696 (NOWN)-25W_VAPOR SKY.ies"),
           (40.0, "25W/GNC-35699 (NOWN)-25W_VAPOR CLUSTER DENSE).ies")],
    "45": [(10.0, "45W/GNC-35786 (NOWN)-45W_VAPOR CLUSTER SPARSE - WRAPPED).ies"),
           (19.0, "45W/GNC-35787 (NOWN)-45W_VAPOR SKY WRAPPED).ies"),
           (40.0, "45W/GNC-35788 (NOWN)-45W_VAPOR CLUSTER DENSE - WRAPPED).ies")],
}

sys.path.insert(0, str(POLAR_SRC))
import generate_polar_plot as gpp  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

BOX_H_MM = 96.0
CIRCLE_D_MM = BOX_H_MM - 8.0
CANVAS_H_MM = BOX_H_MM
CANVAS_W_MM = round(CIRCLE_D_MM
                    + (gpp.DEFAULT_CANVAS_W_MM - gpp.DEFAULT_CIRCLE_DIAMETER_MM), 3)
TEXT_H_MM = 2.5
DPI = gpp.DEFAULT_DPI


class Photometry(object):
    """One .ies file: candela at every vertical angle in every C-plane."""

    def __init__(self, path):
        self.path = Path(path)
        text = self.path.read_text(errors="replace")
        nums = []
        started = False
        for line in text.splitlines():
            if not started:
                if line.strip().upper().startswith("TILT"):
                    started = True
                continue
            nums.extend(line.replace(",", " ").split())
        if not started:
            raise ValueError("no TILT line in %s" % self.path.name)
        v = [float(x) for x in nums[:10]]
        self.n_vert, self.n_horiz = int(v[3]), int(v[4])
        self.multiplier = v[2]
        off = 13                                   # 10 on the first row, 3 on the second
        self.vertical = [float(x) for x in nums[off:off + self.n_vert]]
        off += self.n_vert
        self.horizontal = [float(x) for x in nums[off:off + self.n_horiz]]
        off += self.n_horiz
        flat = [float(x) * self.multiplier
                for x in nums[off:off + self.n_vert * self.n_horiz]]
        # candela[c-plane index][vertical index]
        self.candela = [flat[i * self.n_vert:(i + 1) * self.n_vert]
                        for i in range(self.n_horiz)]

    def plane(self, c_deg):
        """The nearest measured C-plane to the one asked for."""
        i = min(range(self.n_horiz),
                key=lambda k: abs(self.horizontal[k] - c_deg))
        return self.candela[i]

    def envelope(self):
        """The most intense C-plane at each angle off the axis."""
        return [max(self.candela[c][k] for c in range(self.n_horiz))
                for k in range(self.n_vert)]

    @property
    def peak(self):
        return max(max(col) for col in self.candela)

    def at(self, values, gamma):
        """Read a profile at any angle, straight-line between measurements."""
        vs = self.vertical
        if gamma <= vs[0]:
            return values[0]
        if gamma >= vs[-1]:
            return values[-1]
        for i in range(len(vs) - 1):
            if vs[i] <= gamma <= vs[i + 1]:
                span = vs[i + 1] - vs[i]
                if span <= 0:
                    return values[i]
                t = (gamma - vs[i]) / span
                return values[i] + t * (values[i + 1] - values[i])
        return values[-1]


def rows(path):
    with path.open(encoding="utf-8-sig") as fh:
        return {r["group"]: r for r in csv.DictReader(fh)}


def num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def nearest_sample(power, openness_pct):
    best = min(SAMPLES[power], key=lambda s: abs(s[0] - openness_pct))
    return best[0], IES_DIR / best[1]


def render(profiles, peak, out_path, canvas_w_mm=CANVAS_W_MM,
           canvas_h_mm=CANVAS_H_MM, circle_d_mm=CIRCLE_D_MM,
           text_h_mm=TEXT_H_MM, dpi=DPI):
    """Draw the three measured curves on the ring grid.

    `profiles` maps a colour to a function of the angle off the fixture axis,
    returning candela. Plot 0 degrees is straight down, the direction the
    fixture aims, the same convention the Panel Reference plot uses.
    """
    SS = 3
    px_per_mm = dpi / 25.4 * SS
    W = int(round(canvas_w_mm * px_per_mm))
    H = int(round(canvas_h_mm * px_per_mm))
    cx, cy = W / 2.0, H / 2.0
    R = circle_d_mm / 2.0 * px_per_mm
    em_px = text_h_mm * px_per_mm / 0.72

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font_path = gpp.find_font(gpp._REPLICA_BOLD)
    font = (ImageFont.truetype(font_path, int(round(em_px)))
            if font_path else ImageFont.load_default())

    line_w = max(2, int(round(0.25 * px_per_mm)))
    grid_w = max(1, int(round(0.12 * px_per_mm)))

    rings = gpp.ring_values(peak)
    for value in rings:
        r = R * value / peak if peak else 0.0
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)],
                     outline=gpp.COLOR_GRID, width=grid_w)
    for ang in range(0, 360, 30):
        x, y = gpp.polar_to_xy(ang, R, cx, cy)
        draw.line([(cx, cy), (x, y)], fill=gpp.COLOR_GRID, width=grid_w)

    label_x = cx + R + gpp.RING_LABEL_X_OFFSET_MM * px_per_mm
    for value in rings:
        r = R * value / peak if peak else 0.0
        y = cy - r
        gpp.draw_dotted_line(draw, (cx + r, y), (label_x - 2 * px_per_mm, y),
                             gpp.COLOR_LEADER,
                             gpp.LEADER_DOT_DIAMETER_MM * px_per_mm / 2.0,
                             gpp.LEADER_DOT_SPACING_MM * px_per_mm)
        draw.text((label_x, y), str(int(round(value))),
                  fill=gpp.COLOR_TEXT, font=font, anchor="lm")

    for colour, profile in profiles:
        pts = []
        for deg in range(0, 361):
            gamma = deg if deg <= 180 else 360 - deg
            value = profile(gamma)
            r = R * value / peak if peak else 0.0
            pts.append(gpp.polar_to_xy(deg, r, cx, cy))
        draw.line(pts, fill=colour, width=line_w, joint="curve")

    img = img.resize((max(1, W // SS), max(1, H // SS)), Image.LANCZOS)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", dpi=(dpi, dpi), optimize=True)
    return out_path


def build(group, power, light):
    row = light[group]
    openness = num(row["open_pct"])
    sample_open, ies_path = nearest_sample(power, openness)
    if not ies_path.is_file():
        raise IOError("no photometry at %s" % ies_path)
    ies = Photometry(ies_path)

    peak = num(row["peak_cd_%sW" % power])
    scale = peak / ies.peak if ies.peak else 0.0

    c0 = ies.plane(0.0)
    c90 = ies.plane(90.0)
    env = ies.envelope()

    profiles = [
        (gpp.COLOR_BLUE, lambda g: ies.at(env, g) * scale),
        (gpp.COLOR_ORANGE, lambda g: ies.at(c0, g) * scale),
        (gpp.COLOR_GREEN, lambda g: ies.at(c90, g) * scale),
    ]
    out = OUT / ("%s_polar_%sW.png" % (group, power))
    render(profiles, peak, out)
    return {"openness_pct": openness, "sample_openness_pct": sample_open,
            "source": ies_path.name, "peak_cd": peak,
            "measured_peak_cd": round(ies.peak, 1), "out": out}


def check():
    for power, samples in SAMPLES.items():
        print("%s W" % power)
        for openness, rel in samples:
            path = IES_DIR / rel
            if not path.is_file():
                print("   %4.0f%%  MISSING  %s" % (openness, rel))
                continue
            ies = Photometry(path)
            env = ies.envelope()
            c0 = ies.plane(0.0)
            c90 = ies.plane(90.0)
            print("   %4.0f%%  peak %7.1f cd   C0 %7.1f   C90 %7.1f   "
                  "envelope %7.1f   %d planes x %d angles"
                  % (openness, ies.peak, c0[0], c90[0], env[0],
                     ies.n_horiz, ies.n_vert))
            wide = max(ies.vertical[k] for k in range(ies.n_vert)
                       if env[k] >= env[0] * 0.5)
            print("           half intensity at %.0f deg off axis (beam %.0f deg)"
                  % (wide, wide * 2))


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("group", nargs="?")
    ap.add_argument("power", nargs="?", default="45", choices=["25", "45"])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv[1:])

    if args.check or not args.group:
        check()
        return 0

    light = rows(LIGHTING)
    if args.group not in light:
        print("unknown pattern: %s" % args.group)
        return 2
    info = build(args.group, args.power, light)
    print("%s at %s W" % (args.group, args.power))
    print("   openness %.1f%%, shape from the %.0f%% sample (%s)"
          % (info["openness_pct"], info["sample_openness_pct"], info["source"]))
    print("   measured peak %.1f cd scaled to %.0f cd"
          % (info["measured_peak_cd"], info["peak_cd"]))
    print("   -> %s" % info["out"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
