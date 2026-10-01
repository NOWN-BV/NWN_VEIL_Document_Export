#!/usr/bin/env python3
"""What 05-2-B prints, for the InLine linear fixture.

    python linear_led.py                        # show the default set
    python linear_led.py "InLine 5 W/ft - 4 ft"
    from linear_led import values               # what build_family.py uses

EVERY PHOTOMETRIC VALUE ON THIS PAGE IS CALCULATED, NOT MEASURED.

05-2-A rests on eight LM-79 goniophotometric tests of the backlit panel, and
its polar plot is drawn from those .ies files directly. There is no such test
for InLine. The only source is the Arktura tearsheet, which publishes lumens
per foot and efficacy - no beam angle, no candela distribution - so
everything below follows from the flux plus one assumption: a bare linear
extrusion with no lens radiates Lambertian.

    on-axis intensity   I0 = flux / pi          (hemispherical Lambertian)
    beam angle          120 deg                  (full width at half maximum
                                                  of cos(a), i.e. a = +/-60)
    illuminance         E  = I0 / h^2            (directly below, inverse square)
    beam width          w  = 2 h tan(60 deg)

The sheet says "(calculated)" beside the optic for that reason. If InLine is
ever put on a goniophotometer, replace this with the .ies the way 05-2-A was
done, and drop the note.

The set is the same on every pattern's sheet: the panel does not stand
between this fixture and the room, so nothing here varies with perforation.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
SPEC = HERE / "family_spec.json"
SPECS = HERE / "lighting_specs.csv"

DEFAULT = "InLine 10 W/ft - 4 ft"      # the 4 ft length matches a 2 x 4 ft panel
HEIGHTS = ("0.5", "1", "2", "3", "4", "5", "7.5", "10", "20")
HALF_ANGLE_DEG = 60.0                  # cos(a) is half its peak here
FT = 3.280839895


def trim(x: float) -> str:
    """One decimal, dropped when it would be a nought - the column is narrow."""
    t = "%.1f" % x
    return t[:-2] if t.endswith(".0") else t


def fixtures() -> dict:
    """The InLine options, off the tearsheet table.

    Eight rows, but one fixture: four outputs per foot in two lengths.
    """
    out = {}
    with SPECS.open(encoding="utf-8-sig") as fh:
        for row in csv.reader(fh):
            if len(row) < 6 or not row[0].startswith("InLine "):
                continue
            try:
                out[row[0]] = {"w_per_ft": float(row[1]), "watts": float(row[2]),
                               "lm_per_ft": float(row[3]), "flux": float(row[4]),
                               "lm_per_w": float(row[5])}
            except ValueError:
                continue
    return out


def values(which: str = DEFAULT) -> dict:
    """The document text 05-2-B needs, for one InLine configuration."""
    opts = fixtures()
    if which not in opts:
        raise KeyError(which)
    f = opts[which]

    peak = f["flux"] / math.pi
    beam_deg = 2 * HALF_ANGLE_DEG
    spread = 2 * math.tan(math.radians(HALF_ANGLE_DEG))

    out = {
        "Product.LinearLED_Fixture": which.replace("InLine ", "Arktura InLine "),
        "Product.LinearLED_Power": "%g W" % f["watts"],
        "Product.LinearLED_Optic": "%g° (calculated)" % beam_deg,
        "Product.LinearLED_BeamH": "%g°" % beam_deg,
        "Product.LinearLED_BeamV": "%g°" % beam_deg,
        "Product.LinearLED_PeakH": "0°",
        "Product.LinearLED_PeakV": "0°",
        # No Product.LinearLED_Flux: "Panel Output" heads the rows under it
        # rather than carrying a value of its own.
        "Product.LinearLED_TotalFlux": "%d lm" % round(f["flux"]),
        "Product.LinearLED_OnAxis": "%d cd" % round(peak),
        "Product.LinearLED_PeakIntensity": "%d cd" % round(peak),
        # The tearsheet publishes its own efficacy; a figure derived from the
        # flux instead would contradict the source on its own sheet.
        "Product.LinearLED_Efficacy": "%g lm/W" % f["lm_per_w"],
    }
    for h in HEIGHTS:
        hh = float(h)
        width = spread * hh
        pair = "%sm/%s'" % (trim(width), trim(width * FT))
        out["Product.LinearLED_BW_C0_%sm" % h] = pair
        out["Product.LinearLED_BW_C90_%sm" % h] = pair
        out["Product.LinearLED_Lux_%sm" % h] = "%d lx" % round(peak / (hh * hh))
    return out


def main(argv) -> int:
    which = " ".join(argv[1:]) or DEFAULT
    opts = fixtures()
    if which not in opts:
        print("unknown fixture: %s" % which)
        for k in opts:
            print("   %s" % k)
        return 2

    text = values(which)
    f = opts[which]
    print("%s  -  %g W, %d lm, peak %.0f cd (calculated, Lambertian)"
          % (which, f["watts"], f["flux"], f["flux"] / math.pi))
    for h in HEIGHTS:
        print("   %4s m   %-16s %s"
              % (h, text["Product.LinearLED_BW_C0_%sm" % h],
                 text["Product.LinearLED_Lux_%sm" % h]))

    if not SPEC.is_file():
        print("no family spec to write into")
        return 0
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    store = spec["jobs"][0].setdefault("usertext", {})
    for stale in [k for k in store
                  if k.startswith("Product.LinearLED_") and k not in text]:
        del store[stale]
    store.update(text)
    SPEC.write_text(json.dumps(spec, indent=1, ensure_ascii=False,
                               sort_keys=True), encoding="utf-8")
    print("%d value(s) written to %s" % (len(text), SPEC.name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
