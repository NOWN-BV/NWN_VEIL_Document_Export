# -*- coding: utf-8 -*-
"""Turn the two written paragraphs into fields, so they follow the pattern.

Runs inside Rhino (IronPython 2.7) on VEIL_Standard Product Brochure.3dm:
    _-RunPythonScript <this>
Then SAVE.

The copy was typed onto the sheets as fixed text, which means every pattern
would print Herringbone's description. This replaces each of those blocks
with the document field that carries it, leaving the text box, its width and
its style exactly as they are - only what is inside changes.

    02-3-1P / -2P / -4P / -8P-A / -8P-B   Product.Description_Pattern Copy
    02-4                                  Product.Description_Tile System

Blocks are found by what they say, not by where they sit, so moving one does
not hide it from this. Run it twice and the second run finds nothing left to
do, because a block that already holds the field no longer matches the
sentence.
"""
import os
import codecs

import Rhino
import scriptcontext as sc

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(sc.doc.Path or ".")
LOG = os.path.join(HERE, "copyfields_log.txt")

# a phrase that appears in the paragraph and nowhere else -> the field for it
MARKERS = [
    ("powder coated panels", "Product.Description_Pattern Copy"),
    ("The pattern surface is created using",
     "Product.Description_Tile System"),
]

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


def with_fields(g):
    """The text as authored - PlainText has any fields already evaluated."""
    for name in ("PlainTextWithFields", "RichText", "PlainText"):
        try:
            v = getattr(g, name, None)
        except Exception:
            continue
        if v:
            return u"%s" % v
    return u""


def field(key):
    return '%<DocumentText("' + key + '")>%'


def page_of(obj, pages):
    return pages.get(str(obj.Attributes.ViewportId), "")


def main():
    log("document: %s" % sc.doc.Path)
    pages = {}
    for pv in sc.doc.Views.GetPageViews():
        pages[str(pv.MainViewport.Id)] = pv.PageName

    found = []
    for obj in every_object():
        g = obj.Geometry
        if not isinstance(g, Rhino.Geometry.TextEntity):
            continue
        plain = (g.PlainText or "")
        authored = with_fields(g)
        for marker, key in MARKERS:
            if marker not in plain:
                continue
            if key in authored:
                log("  %-12s already a field" % page_of(obj, pages))
                break
            found.append((obj, key))
            break

    if not found:
        log("nothing to convert - the sheets already carry the fields")
        return

    changed = 0
    for obj, key in found:
        name = page_of(obj, pages) or "(model)"
        text = obj.Geometry.Duplicate()
        was = (text.PlainText or "")[:60]
        text.RichText = field(key)
        if sc.doc.Objects.Replace(obj.Id, text):
            changed += 1
            log("  %-12s -> %s" % (name, key))
            log("                 was: %s..." % was)
        else:
            log("  %-12s REPLACE FAILED" % name)

    log("")
    log("%d block(s) now read from the document text." % changed)
    log("Check 02-3 and 02-4, then SAVE.")
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
