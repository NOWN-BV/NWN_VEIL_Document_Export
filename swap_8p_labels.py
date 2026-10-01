# -*- coding: utf-8 -*-
"""Put the first four panels on 02-3-8P-A and the second four on -B.

Runs inside Rhino (IronPython 2.7) on VEIL_Standard Product Brochure.3dm:
    _-RunPythonScript <this>
Then SAVE.

An eight-panel set needs two sheets, because a sheet shows four. The
brochure was drawn with E F G H on the -A sheet and A B C D on the -B, so a
reader meets the back half of the set first. The sheets are otherwise the
same, so the fix is to swap which half each one names:

    02-3-8P-A    E F G H  ->  A B C D
    02-3-8P-B    A B C D  ->  E F G H

build_family.py was changed to match, so the panels drawn on a sheet are the
ones its labels name.

The labels hold DocumentText fields rather than typed letters, so the swap
is on the key inside the field. It is read from PlainTextWithFields, because
RichText gives back the value the field resolved to and not the field.

Running it twice puts the sheets back as they were, so it checks what the
-A sheet holds first and stops if it already names A to D.
"""
import os
import codecs

import Rhino
import scriptcontext as sc

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(sc.doc.Path or ".")
LOG = os.path.join(HERE, "swap8p_log.txt")

KEY = "Product.Description_Panel Code %s"
SHEETS = {"02-3-8P-A": ("EFGH", "ABCD"),     # holds -> should hold
          "02-3-8P-B": ("ABCD", "EFGH")}

lines = []


def log(m):
    lines.append(u"%s" % m)
    print(m)
    try:
        f = codecs.open(LOG, "w", "utf-8")
        f.write(u"\n".join(lines))
        f.close()
    except Exception:
        pass


def every_object():
    st = Rhino.DocObjects.ObjectEnumeratorSettings()
    st.NormalObjects = True
    st.LockedObjects = True
    st.HiddenObjects = True
    st.IncludeLights = False
    st.IncludeGrips = False
    return sc.doc.Objects.GetObjectList(st)


def authored(g):
    for name in ("PlainTextWithFields", "RichText", "PlainText"):
        try:
            v = getattr(g, name, None)
        except Exception:
            continue
        if v:
            return u"%s" % v
    return u""


def field(letter):
    return '%<DocumentText("' + (KEY % letter) + '")>%'


def main():
    log("document: %s" % sc.doc.Path)
    pages = {}
    for pv in sc.doc.Views.GetPageViews():
        if pv.PageName in SHEETS:
            pages[str(pv.MainViewport.Id)] = pv.PageName
    missing = [s for s in SHEETS if s not in pages.values()]
    if missing:
        log("sheet(s) not in this document: %s" % ", ".join(sorted(missing)))
        return

    # What is on the two sheets, labels and everything else, before touching
    # anything - so a stray "Panel E" typed somewhere shows up here.
    found = {}
    for obj in every_object():
        g = obj.Geometry
        if not isinstance(g, Rhino.Geometry.TextEntity):
            continue
        page = pages.get(str(obj.Attributes.ViewportId))
        if page is None:
            continue
        text = authored(g)
        letter = None
        for c in "ABCDEFGH":
            if (KEY % c) in text:
                letter = c
        found.setdefault(page, []).append((obj, g, letter, text))

    for page in sorted(found):
        held = "".join(sorted(c for _, _, c, _ in found[page] if c))
        log("")
        log("%s holds %s" % (page, held or "no panel-code fields"))
        for _, _, c, text in found[page]:
            if c is None:
                log("    (other text) %r" % text.strip()[:70])

    holds = "".join(sorted(c for _, _, c, _ in found["02-3-8P-A"] if c))
    if holds == "ABCD":
        log("")
        log("02-3-8P-A already names A to D - nothing to swap.")
        return
    if holds != "EFGH":
        log("")
        log("02-3-8P-A names %r, which is neither half of the set." % holds)
        log("Nothing changed.")
        return

    swap = dict(zip("ABCDEFGH", "EFGHABCD"))
    changed = 0
    for page in sorted(found):
        for obj, g, letter, _ in found[page]:
            if letter is None:
                continue
            copy = g.Duplicate()
            copy.RichText = field(swap[letter])
            if sc.doc.Objects.Replace(obj.Id, copy):
                changed += 1
                log("  %-12s %s -> %s" % (page, letter, swap[letter]))

    log("")
    log("%d label(s) swapped." % changed)
    log("Check 02-3-8P-A reads A to D, then SAVE.")
    sc.doc.Views.Redraw()


try:
    main()
except Exception, e:                          # noqa: E999  (IronPython 2.7)
    import traceback
    log("EXCEPTION: %s" % e)
    log(traceback.format_exc())

f = codecs.open(LOG, "w", "utf-8")
f.write(u"\n".join(lines))
f.close()
