#!/usr/bin/env python3
"""Make every stroke in an exported brochure a true PDF hairline.

    python pdf_hairline.py smoke/RAST_PLN.pdf            # report only
    python pdf_hairline.py smoke/RAST_PLN.pdf --write

Rhino writes a default plot weight as 0.36pt, which is 0.127mm. On an A3
sheet in a browser that is about half a pixel, so each rule lands on one
pixel or spills onto two depending where it falls on the grid, and a rule
beside it that landed differently looks twice as heavy. Change the zoom and
which rules look heavy changes with it. The file is even - at 800dpi every
rule on 05-2-A measures the same 5 pixels - and nothing in Rhino can fix
what the renderer is doing.

PDF has an answer for exactly this. A stroke width of zero does not mean an
invisible line: it means the thinnest line the device can draw, which is one
pixel, always, at every resolution and every zoom. Measured against 0.36pt
over 40 rules at drifting positions:

    0.36pt   1/2  1/2  1/2  1/2  2/3  4/5   pixels at 96..800dpi
    0 w        1    1    1    1    1    1

So the widths are rewritten to zero in the content streams. Nothing else
about the page changes - same geometry, same colour, same text.

The cost is the usual one for hairlines: one pixel at 2400dpi on a press is
0.01mm and can print faint or drop out. This is right for a brochure read on
a screen, and should be looked at again if it goes to a printer.

Width tokens are found by scanning rather than by a plain search, because a
text string on the page can contain something that looks like one and
rewriting inside a string would corrupt the words.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import fitz

NUMBER = re.compile(rb"[-+]?(?:\d+\.?\d*|\.\d+)\Z")
WSP = b"\x00\t\n\x0c\r "
DELIM = b"()<>[]{}/%"


def set_widths(doc: fitz.Document, write: bool) -> tuple[int, int]:
    """Rewrite width operands to zero. Returns (streams touched, widths set)."""
    streams = widths = 0
    seen = set()
    for page in doc:
        for xref in page.get_contents():
            if xref in seen:
                continue
            seen.add(xref)
            raw = doc.xref_stream(xref)
            if raw is None:
                continue
            new, count = zero_widths(raw)
            if count:
                widths += count
                streams += 1
                if write:
                    doc.update_stream(xref, new)
    return streams, widths


def zero_widths(stream: bytes) -> tuple[bytes, int]:
    """Replace the operand of every `w` operator with 0."""
    tokens = []            # (start, end) of each token in the output so far
    out = bytearray()
    i, n = 0, len(stream)
    depth = 0
    count = 0
    while i < n:
        c = stream[i:i + 1]
        if depth:
            out += c
            if c == b"\\" and i + 1 < n:
                out += stream[i + 1:i + 2]
                i += 2
                continue
            if c == b"(":
                depth += 1
            elif c == b")":
                depth -= 1
            i += 1
            continue
        if c == b"(":
            depth = 1
            tokens = []
            out += c
            i += 1
            continue
        if c == b"%":
            j = i
            while j < n and stream[j:j + 1] not in b"\r\n":
                j += 1
            out += stream[i:j]
            i = j
            tokens = []
            continue
        if c in WSP:
            out += c
            i += 1
            continue
        if c in DELIM:
            out += c
            tokens = []
            i += 1
            continue
        j = i
        while j < n and stream[j:j + 1] not in WSP and stream[j:j + 1] not in DELIM:
            j += 1
        token = stream[i:j]
        if token == b"w" and tokens:
            s, e = tokens[-1]
            if NUMBER.match(bytes(out[s:e])):
                out[s:e] = b"0"
                count += 1
                tokens = []
                out += token
                i = j
                continue
        start = len(out)
        out += token
        tokens.append((start, len(out)))
        i = j
    return bytes(out), count


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv[1:])

    pdf = Path(args.pdf)
    if not pdf.is_file():
        print("no such pdf: %s" % pdf)
        return 2

    doc = fitz.open(pdf)
    before = {}
    for page in doc:
        for p in page.get_drawings():
            if p["type"] in ("s", "fs") and p.get("width") is not None:
                before[round(p["width"], 2)] = \
                    before.get(round(p["width"], 2), 0) + len(p["items"])
    print("%s" % pdf.name)
    print("   widths now: %s" % ", ".join(
        "%.2fpt x%d" % (k, v) for k, v in sorted(before.items())))

    streams, widths = set_widths(doc, args.write)
    print("   %d width operand(s) across %d content stream(s)"
          % (widths, streams))

    if not args.write:
        doc.close()
        print("   nothing written - pass --write")
        return 0

    out = pdf.with_name(pdf.stem + "_hairline.pdf")
    doc.save(out, garbage=4, deflate=True)
    doc.close()

    check = fitz.open(out)
    after = {}
    for page in check:
        for p in page.get_drawings():
            if p["type"] in ("s", "fs") and p.get("width") is not None:
                after[round(p["width"], 2)] = \
                    after.get(round(p["width"], 2), 0) + len(p["items"])
    check.close()
    print("   widths after: %s" % ", ".join(
        "%.2fpt x%d" % (k, v) for k, v in sorted(after.items())))
    os.replace(out, pdf)
    print("   written to %s" % pdf.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
