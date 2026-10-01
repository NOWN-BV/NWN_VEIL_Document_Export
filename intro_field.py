# -*- coding: utf-8 -*-
"""Make 01-1's opening follow the pattern being printed.

Runs inside Rhino (IronPython 2.7) on VEIL_Standard Product Brochure.3dm:
    _-RunPythonScript <this>
Then SAVE.

01-1 holds one text block with two paragraphs in it:

    VEIL(R) is a modular, accessible <material> panel system designed to
    work with torsion grid.

    <name> lets you use a standard panel tiling system to create a unique
    look on your standard Torsion Grid ceiling, or on a wall using the
    NOWN Channel System.

The first says what VEIL is and is true of every pattern, so it stays. The
second is the same sentence on all eighty-one, and makes the point 01-2 makes
again overleaf - that the tiling runs continuous across joints. It is
replaced by the field, which carries two paragraphs written for this pattern.

The block is split at the blank line, so the first paragraph keeps its own
wording and its fields. If the block is not shaped that way the script says
so and changes nothing, rather than guessing where to cut.
"""
import os
import codecs

import Rhino
import scriptcontext as sc

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(sc.doc.Path or ".")
LOG = os.path.join(HERE, "introfield_log.txt")

PAGE = "01-1"
KEY = "Product.Description_Intro"
MARKER = "lets you use a standard panel tiling system"

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


def field(key):
    return '%<DocumentText("' + key + '")>%'


def main():
    log("document: %s" % sc.doc.Path)
    vid = None
    for pv in sc.doc.Views.GetPageViews():
        if pv.PageName == PAGE:
            vid = str(pv.MainViewport.Id)
    if vid is None:
        log("%s not found" % PAGE)
        return

    done = 0
    for obj in every_object():
        if str(obj.Attributes.ViewportId) != vid:
            continue
        g = obj.Geometry
        if not isinstance(g, Rhino.Geometry.TextEntity):
            continue
        text = authored(g)
        if KEY in text:
            log("already a field")
            return
        if MARKER not in text:
            continue

        # Cut at the blank line before the sentence being replaced.
        cut = text.find(MARKER)
        head = text[:cut]
        split = head.rfind("\r\n\r\n")
        if split < 0:
            split = head.rfind("\n\n")
        if split < 0:
            log("the two paragraphs are not separated by a blank line -")
            log("nothing changed. The block reads:")
            log("   %r" % text[:200])
            return

        keep = text[:split]
        new = keep + "\r\n\r\n" + field(KEY)
        copy = g.Duplicate()
        copy.RichText = new
        if sc.doc.Objects.Replace(obj.Id, copy):
            done += 1
            log("replaced the second paragraph")
            log("   kept:    %r" % keep.strip()[:110])
            log("   dropped: %r" % text[split:].strip()[:110])

    if not done:
        log("no block on %s carries that sentence" % PAGE)
        return

    if not sc.doc.Strings.GetValue(KEY):
        sc.doc.Strings.SetString(KEY, u" ")
    log("")
    log("Check 01-1, then SAVE.")
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
