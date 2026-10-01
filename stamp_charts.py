#!/usr/bin/env python3
"""Stamp the polar plots onto the exported brochure.

    python stamp_charts.py smoke/Basalt-P10.pdf

Rhino draws the SAC curve itself - 05-3 already has the grid and axes on the
sheet, so the curve goes on as geometry and stays vector. The polar plots are
a different case: their box is empty, the plot is a raster, and a picture
frame added to a layout's page space does not come through the capture. So
they go on here instead, which is what the Panel Reference pipeline does too,
and the placement is exact because the box was measured off the sheet.

Reads the same charts/charts.json and family_spec.json the export used, so
the plot on a page is the one that page's spec asked for.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import fitz
from PIL import Image

HERE = Path(__file__).resolve().parent
CHARTS = HERE / "charts"
SPEC = HERE / "family_spec.json"
PICTURES = CHARTS / "pictures.json"
MM = 72.0 / 25.4
TARGET_DPI = 200          # what the brochure prints at
JPEG_QUALITY = 85
OPAQUE_ALPHA_SHARE = 0.005  # below this, the alpha channel is not doing anything

# The empty "Polar Plots" box, measured off 05-2-A and 05-2-B (mm, from the
# bottom-left of the sheet the way Rhino counts).
BOX_MM = (256.6, 20.5, 420.0, 116.5)
INSET_MM = 0.5          # keep the plot just off the ruled box edge

# The acoustic chart's grid, measured off 05-3: 27 x 15 cells of
# 6.40625 x 5.125 mm. The overlay is drawn at exactly this size, so it goes
# on corner to corner with no fitting.
SAC_BOX_MM = (247.03, 95.625, 420.00, 172.50)


def printed_steps(pdf: Path, spec: dict) -> list[dict]:
    """The sheets the export actually printed, in order.

    A sheet the document no longer has is skipped at print time, so counting
    steps in the spec puts every later page one out. The export writes down
    what it printed; fall back to the spec only when that file is absent.
    """
    manifest = pdf.with_name(pdf.stem + "_pages.json")
    if manifest.is_file():
        return json.loads(manifest.read_text(encoding="utf-8"))
    print("  no page list beside the pdf - falling back to the spec order")
    return [{"page": s["page"], "chart": s.get("chart") or {}}
            for s in spec["jobs"][0]["sequence"]]


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    pdf = Path(argv[1])
    if not pdf.is_file():
        print("no such pdf: %s" % pdf)
        return 2
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    job = spec["jobs"][0]

    doc = fitz.open(pdf)
    steps = printed_steps(pdf, spec)
    if len(steps) != doc.page_count:
        print("  page list has %d entries but the pdf has %d - not stamping"
              % (len(steps), doc.page_count))
        return 1
    pages = {}
    for i, step in enumerate(steps):
        pages.setdefault(step["page"], i)
    h_pt = doc[0].rect.height

    def place(page, png_path, box, fit):
        bx0, by0, bx1, by1 = box
        if fit:
            with fitz.open(png_path) as img:
                iw, ih = img[0].rect.width, img[0].rect.height
            bw = (bx1 - bx0 - 2 * INSET_MM) * MM
            bh = (by1 - by0 - 2 * INSET_MM) * MM
            scale = min(bw / iw, bh / ih)
            w, h = iw * scale, ih * scale
            cx = (bx0 + bx1) / 2.0 * MM
            cy = h_pt - (by0 + by1) / 2.0 * MM
            r = fitz.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        else:
            r = fitz.Rect(bx0 * MM, h_pt - by1 * MM, bx1 * MM, h_pt - by0 * MM)
        page.insert_image(r, filename=str(png_path), keep_proportion=fit,
                          overlay=True)
        return r.width / MM, r.height / MM

    done = 0
    for step in steps:
        chart = step.get("chart") or {}
        name = chart.get("sac")
        if name:
            src = CHARTS / ("%s_nrc_overlay.png" % name)
            if not src.is_file():
                print("  %-8s missing %s" % (step["page"], src.name))
            else:
                idx = pages[step["page"]]
                w, h = place(doc[idx], src, SAC_BOX_MM, fit=False)
                print("  p%-3d %-8s %-32s %.2f x %.2f mm"
                      % (idx + 1, step["page"], src.name, w, h))
                done += 1
        png = chart.get("polar")
        if not png:
            continue
        src = CHARTS / png
        if not src.is_file():
            print("  %-8s missing %s" % (step["page"], png))
            continue
        idx = pages[step["page"]]
        w, h = place(doc[idx], src, BOX_MM, fit=True)
        print("  p%-3d %-8s %-32s %.1f x %.1f mm"
              % (idx + 1, step["page"], png, w, h))
        done += 1

    def fit_for_print(src, w_mm, h_mm):
        """Re-encode a picture at the size it is actually printed.

        These are photographs carrying an alpha channel that turns out to be
        doing nothing - not one pixel in ten thousand is transparent - and
        they arrive as lossless PNG. Stored as they are they cost six
        megabytes; resampled to the slot at print resolution and written as
        JPEG they cost half of one, and nothing about the printed page
        changes. The charts are left alone: those really are mostly
        transparent and have to stay PNG.
        """
        with Image.open(src) as im:
            if im.mode in ("RGBA", "LA"):
                alpha = im.getchannel("A")
                counts = alpha.histogram()
                total = sum(counts) or 1
                if sum(counts[:250]) / float(total) > OPAQUE_ALPHA_SHARE:
                    return src, "png, has transparency"
            want_w = max(1, int(round(w_mm / 25.4 * TARGET_DPI)))
            want_h = max(1, int(round(h_mm / 25.4 * TARGET_DPI)))
            flat = im.convert("RGB")
            if flat.width > want_w or flat.height > want_h:
                flat = flat.resize((min(flat.width, want_w),
                                    min(flat.height, want_h)), Image.LANCZOS)
            out = CHARTS / ("_print_%s.jpg" % Path(src).stem)
            flat.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return out, "jpeg %dx%d" % (flat.width, flat.height)

    def white_area(page, box):
        """The blank rectangle a missing picture actually leaves on the page.

        A frame is taller than the image it shows - the label strip under a
        row of swatches sits inside the frame's bounding box - so stamping the
        whole frame buries the labels. What is genuinely missing is the white
        that got printed instead of the picture, and that is exactly the area
        to put back.
        """
        bx0, by0, bx1, by1 = box
        r = fitz.Rect(max(0, bx0) * MM, h_pt - by1 * MM,
                      min(420.0, bx1) * MM, h_pt - by0 * MM)
        pix = page.get_pixmap(clip=r, dpi=72)
        if pix.width < 4 or pix.height < 4:
            return None
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        g = im.convert("L")
        w, hh = g.size
        px = g.load()
        cols = [x for x in range(w)
                if sum(1 for y in range(hh) if px[x, y] > 244) > hh * 0.5]
        rows_ = [y for y in range(hh)
                 if sum(1 for x in range(w) if px[x, y] > 244) > w * 0.5]
        if not cols or not rows_:
            return None
        fx0, fx1 = cols[0] / float(w), (cols[-1] + 1) / float(w)
        fy0, fy1 = rows_[0] / float(hh), (rows_[-1] + 1) / float(hh)
        return fx0, fy0, fx1, fy1, r

    # The brochure's own pictures, for the frames whose image is linked rather
    # than embedded and so prints as a white box. The Rhino page arrives as
    # one raster, so there is no slipping underneath it - these go on top,
    # covering the white box exactly where the frame sits.
    if PICTURES.is_file():
        for pic in json.loads(PICTURES.read_text(encoding="utf-8")):
            if pic["how"] != "linked" or pic["page"] not in pages:
                continue
            src = Path(pic["source"])
            if not src.is_file():
                print("  %-8s source gone: %s" % (pic["page"], src.name))
                continue
            idx = pages[pic["page"]]
            area = white_area(doc[idx], pic["box_mm"])
            if area is None:
                print("  %-8s %s leaves no white box - skipped"
                      % (pic["page"], src.name[:28]))
                continue
            fx0, fy0, fx1, fy1, frame = area
            rect = fitz.Rect(frame.x0 + fx0 * frame.width,
                             frame.y0 + fy0 * frame.height,
                             frame.x0 + fx1 * frame.width,
                             frame.y0 + fy1 * frame.height)
            # Crop the source to the same fraction of the frame, so the image
            # still lines up with the frame the designer placed.
            with Image.open(src) as img:
                iw, ih = img.size
                crop = img.crop((int(fx0 * iw), int(fy0 * ih),
                                 max(int(fx0 * iw) + 1, int(fx1 * iw)),
                                 max(int(fy0 * ih) + 1, int(fy1 * ih))))
                tmp = CHARTS / ("_crop_%s" % src.name)
                crop.save(tmp)
            tmp, how = fit_for_print(tmp, rect.width / MM, rect.height / MM)
            doc[idx].insert_image(rect, filename=str(tmp),
                                  keep_proportion=False, overlay=True)
            print("  p%-3d %-8s picture %-26s %.0f x %.0f mm  %s"
                  % (idx + 1, pic["page"], src.name[:26],
                     rect.width / MM, rect.height / MM, how))
            done += 1

    if not done:
        print("nothing to stamp")
        return 1
    out = pdf.with_name(pdf.stem + "_charts.pdf")
    doc.save(out, garbage=3, deflate=True)
    doc.close()
    print("%d plot(s) -> %s" % (done, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
