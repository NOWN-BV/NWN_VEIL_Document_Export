# -*- coding: utf-8 -*-
"""Make the panel labels on 02-3 follow the pattern being printed.

Runs inside Rhino (IronPython 2.7) on VEIL_Standard Product Brochure.3dm:
    _-RunPythonScript <this>
Then SAVE.

The labels under the panels read "Panel A" through "Panel H" and are typed
onto the sheets, so every pattern prints the same four words. The code that
names a panel is not the same on every pattern - RAST_PLNA, FUME_SPRA,
FUME_TSDC - so each label becomes the field that carries it.

    02-3-1P     Panel A              -> Panel Code A
    02-3-2P     Panel A, B           -> A, B
    02-3-4P     Panel A, B, C, D     -> A, B, C, D
    02-3-8P-A   Panel A, B, C, D     -> A, B, C, D
    02-3-8P-B   Panel E, F, G, H     -> E, F, G, H

The value is the part of the code that picks out the panel - SPRA rather than
FUME_SPRA - because the family already stands in the title above it.

Labels are found by what they say and which sheet they are on, so moving one
along the row does not hide it. Run it twice and the second run finds nothing,
because a label holding its field no longer reads "Panel X".
"""
import os
import codecs

import Rhino
import scriptcontext as sc

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(sc.doc.Path or ".")
LOG = os.path.join(HERE, "panellabel_log.txt")

KEY = "Product.Description_Panel Code %s"
SHEETS = {
    "02-3-1P": "A",
    "02-3-2P": "AB",
    "02-3-4P": "ABCD",
    "02-3-8P-A": "ABCD",
    "02-3-8P-B": "EFGH",
}

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


def field(key):
    return '%<DocumentText("' + key + '")>%'


def main():
    log("document: %s" % sc.doc.Path)
    pages = {}
    for pv in sc.doc.Views.GetPageViews():
        if pv.PageName in SHEETS:
            pages[str(pv.MainViewport.Id)] = pv.PageName

    changed, seen = 0, {}
    for obj in every_object():
        g = obj.Geometry
        if not isinstance(g, Rhino.Geometry.TextEntity):
            continue
        page = pages.get(str(obj.Attributes.ViewportId))
        if page is None:
            continue
        text = (g.PlainText or "").strip()
        if not text.startswith("Panel "):
            continue
        letter = text[len("Panel "):].strip()
        if letter not in SHEETS[page]:
            log("  [%-10s] %r is not one of this sheet's panels" % (page, text))
            continue
        copy = g.Duplicate()
        copy.RichText = field(KEY % letter)
        if sc.doc.Objects.Replace(obj.Id, copy):
            changed += 1
            seen.setdefault(page, []).append(letter)

    for page in sorted(seen):
        log("  %-12s %s" % (page, ", ".join(sorted(seen[page]))))
    log("")
    log("%d label(s) now read from the document text." % changed)

    # Make sure the keys exist, so a sheet opened before an export does not
    # show #### where a label used to be.
    for letter in "ABCDEFGH":
        if not sc.doc.Strings.GetValue(KEY % letter):
            sc.doc.Strings.SetString(KEY % letter, u" ")
    log("Check 02-3, then SAVE.")
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
