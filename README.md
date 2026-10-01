# Product Document Export Setup

Prints a per-pattern product brochure from
`N:\Products\Development\Product Lab\VEIL\Collateral\VEIL_Standard Product Brochure.3dm`.

The brochure is one Rhino document of about thirty layout sheets. A pattern's
PDF is those sheets walked in order with the panels, the figures and the
copy swapped for that pattern's, so eighty-one patterns come out of one
file rather than eighty-one files.

## Running one

```
python build_family.py RAST_PLN          # writes family_spec.json
```

then, in Rhino 7 with the brochure open:

```
_-RunPythonScript export_family.py
```

The export prints each sheet, puts the document back the way it found it,
and never saves. It finishes by calling two CPython helpers itself, because
IronPython cannot load Pillow or PyMuPDF:

| | |
|---|---|
| `pdf_hairline.py` | every stroke to a true PDF hairline |
| `stamp_charts.py` | the polar plots, the SAC overlay and the brochure's own pictures |

## What is here

**Building the spec**

| | |
|---|---|
| `build_family.py` | turns one pattern into the ordered list of sheets, slots and document text |
| `intro_copy.py` / `.csv` | the opening paragraph on 01-1, one per family |
| `pattern_copy.py` / `.csv` | the paragraphs on 02-3 and 02-4 |
| `linear_led.py` | the InLine fixture figures, the same on every sheet |

**Figures**

| | |
|---|---|
| `make_charts.py` | the SAC overlay and the polar plots, into `charts/` |
| `polar_measured.py` | reads the .ies originals - a real C0/C90 envelope, not a tearsheet |
| `find_pictures.py` | finds the picture frames that print white, and where they sit |

**Printing**

| | |
|---|---|
| `export_family.py` | the exporter. Rhino, IronPython 2.7 |
| `pdf_hairline.py` | stroke widths to zero |
| `stamp_charts.py` | lays the figures onto the printed PDF |

**Preparing the brochure** - Rhino scripts, each run once against the
document and then saved. They are kept because the next brochure will need
them, and because each says in its own header what it found and why it did
what it did.

| | |
|---|---|
| `fix_glyphs.py` | characters Replica cannot set. `replica_cmap.json` is what the font covers |
| `rect_to_layer.py` | the sheet rectangles onto one layer, every line to the front |
| `snap_hairlines.py` | pairs of rules a fraction of a millimetre apart |
| `swap_8p_labels.py` | 02-3-8P-A to name the first four panels, -B the second four |
| `panel_label_fields.py` | the panel labels read from the document text |
| `intro_field.py` | 01-1's second paragraph becomes a field |
| `add_copy_fields.py` | the 02-3 and 02-4 paragraphs become fields |
| `unflip_panels.py` | takes a mirror back off the four CONFIG slots |

Each has a `_restore` companion where the change is one a person might want
back.

**Data**

| | |
|---|---|
| `usertext_81.json` | the eighty-one patterns: codes, panel counts, figures |
| `acoustic_pattern_81.csv` | SAC by band, per pattern |
| `lighting_81.csv`, `lighting_specs.csv` | photometrics |
| `panel_codes.csv` | the 157 panels under their four-letter family codes |

## charts/

`charts/_crop_*.png` are the brochure's own photographs. They are committed
because they are not reproducible: the Rhino document links them from
`%LOCALAPPDATA%\Temp`, so they exist only until that folder is cleared, and
the sheets print white without them. Embedding them in the .3dm is still
to do; until then this is where they live.

The SAC and polar PNGs are not committed. `make_charts.py` rebuilds them
from the test reports on N:.

## Two things worth knowing before changing any of it

**Stroke widths.** Every stroke is set to zero on the way out. A width of
zero in PDF is not an invisible line, it is the thinnest the device can
draw - one pixel, at every resolution. Rhino's default plot weight comes out
as 0.36pt, which on a screen is about half a pixel, so each rule lands on
one pixel or spills onto two depending where it falls and identical rules
print at visibly different weights. Measured over 40 rules at drifting
positions:

```
            96   120   150   200   400   800 dpi
0.36pt     1/2   1/2   1/2   1/2   2/3   4/5   px
0 w          1     1     1     1     1     1
```

This is right for a brochure read on a screen. One pixel at 2400dpi is
0.01mm, so if it goes to a printer, look at it again.

**Raster or vector.** `family_spec.json` carries a `raster` flag.
False - the default now - writes the page-space text and linework as vector
and rasterises only the shaded details: 13.1MB against 25.3MB, and the text
is real text. True bakes each sheet to one bitmap. The panel wall on 02-4
is a bitmap either way.
