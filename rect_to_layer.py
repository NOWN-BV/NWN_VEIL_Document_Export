# -*- coding: utf-8 -*-
"""Gather the sheet rectangles onto one layer, and draw every line on top.

Runs inside Rhino (IronPython 2.7) on VEIL_Standard Product Brochure.3dm:
    _-RunPythonScript <this>
Then LOOK, and only then save.

Two things, in one pass over the page-space curves.

The rules on a sheet come from a dozen layers at four different print
widths, so one table can carry 0.127mm and 0.35mm side by side and nothing
can set them together. Putting the rectangles on one layer makes the weight
a single setting instead of a hunt.

And every line is brought to the front. A fill drawn over a rule hides part
of its width, so the same line reads thinner where something sits on it and
full weight where nothing does - which looks like the weights differ when
they do not. Lines on top removes that.

The layer weights this script's predecessor changed are put back first, so
the starting point is the file as it was rather than a half-applied
experiment. An object carrying its own print width is set back to following
its layer, because otherwise it sits on the new layer and still ignores it.

What is left alone:

  NOPRINT and SCRIPT      their curves are there to be invisible. Moving
                          them onto a printing layer would print them, and
                          bringing them forward would show them
  model space             the details draw through those layers; this is a
                          decision about the sheets
  anything not a rectangle keeps its layer. It still comes forward

Everything changed goes to rect_move_backup.json, and
rect_to_layer_restore.py puts each object back as it was.
"""
import os
import json
import codecs

import Rhino
import scriptcontext as sc

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(sc.doc.Path or ".")
LOG = os.path.join(HERE, "rect_log.txt")
BACKUP = os.path.join(HERE, "rect_move_backup.json")
WEIGHTS = os.path.join(HERE, "plot_weight_backup.json")

TARGET = "RECTANGLE"
SQUARE = 0.02         # how far off a right angle a corner may be
FRONT = 1             # display order: above anything left at 0
NEVER = ("NOPRINT", "SCRIPT")

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


def spend(path):
    """Mark a backup as used.

    Deleting it is the tidy ending, but something on this machine holds
    these files often enough that a failed delete stopped the work before it
    started once already. Emptying it is what matters - a re-run then
    restores nothing - and the delete is allowed to fail.
    """
    try:
        f = codecs.open(path, "w", "utf-8")
        f.write(u"{}")
        f.close()
    except Exception:
        pass
    try:
        os.remove(path)
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


def undo_weights():
    """Put back what plot_weight.py changed, so this starts from the file."""
    if not os.path.isfile(WEIGHTS):
        return 0
    try:
        was = json.loads(codecs.open(WEIGHTS, "r", "utf-8").read())
    except Exception:
        return 0
    done = 0
    for key, old in was.items():
        li = int(key)
        if 0 <= li < sc.doc.Layers.Count:
            layer = sc.doc.Layers[li]
            layer.PlotWeight = float(old)
            if sc.doc.Layers.Modify(layer, li, True):
                done += 1
    spend(WEIGHTS)
    return done


def is_rectangle(crv):
    """Four straight sides, closed, corners square. Any rotation."""
    if not crv.IsClosed:
        return False
    try:
        segs = crv.DuplicateSegments()
    except Exception:
        return False
    if not segs or len(segs) != 4:
        return False
    dirs = []
    for s in segs:
        if not s.IsLinear(0.001):
            return False
        v = s.PointAtEnd - s.PointAtStart
        if v.Length < 1e-6:
            return False
        v.Unitize()
        dirs.append(v)
    for i in range(4):
        a, b = dirs[i], dirs[(i + 1) % 4]
        if abs(a.X * b.X + a.Y * b.Y + a.Z * b.Z) > SQUARE:
            return False
    return True


def find_layer(name):
    layer = sc.doc.Layers.FindName(name, -1)
    if layer is not None:
        return layer
    for i in range(sc.doc.Layers.Count):
        if sc.doc.Layers[i].Name == name:
            return sc.doc.Layers[i]
    return None


def main():
    log("document: %s" % sc.doc.Path)
    n = undo_weights()
    if n:
        log("put %d layer print width(s) back first" % n)

    target = find_layer(TARGET)
    if target is None:
        log("no layer called %r - nothing done" % TARGET)
        return
    log("target layer: %s   print width %.3f mm"
        % (target.FullPath, target.PlotWeight))

    sheets = {}
    for pv in sc.doc.Views.GetPageViews():
        sheets[str(pv.MainViewport.Id)] = pv.PageName

    moved, fronted, kept = {}, {}, {}
    record = []
    for obj in every_object():
        if obj.Attributes.Space != Rhino.DocObjects.ActiveSpace.PageSpace:
            continue
        if str(obj.Attributes.ViewportId) not in sheets:
            continue
        g = obj.Geometry
        if not isinstance(g, Rhino.Geometry.Curve):
            continue

        li = obj.Attributes.LayerIndex
        layer = sc.doc.Layers[li]
        name = layer.FullPath
        if any(w in name.upper() for w in NEVER) or layer.PlotWeight < 0:
            kept[name] = kept.get(name, 0) + 1
            continue

        at = obj.Attributes.Duplicate()
        before = {
            "id": str(obj.Id),
            "layer": li,
            "weight": at.PlotWeight,
            "source": int(at.PlotWeightSource),
            "order": at.DisplayOrder,
        }
        touched = False

        if is_rectangle(g) and li != target.Index:
            at.LayerIndex = target.Index
            # on the new layer but still carrying its own width is no better
            at.PlotWeightSource = \
                Rhino.DocObjects.ObjectPlotWeightSource.PlotWeightFromLayer
            moved[name] = moved.get(name, 0) + 1
            touched = True

        if at.DisplayOrder != FRONT:
            at.DisplayOrder = FRONT
            fronted[name] = fronted.get(name, 0) + 1
            touched = True

        if touched and sc.doc.Objects.ModifyAttributes(obj.Id, at, True):
            record.append(before)

    log("")
    log("moved onto %s" % TARGET)
    if not moved:
        log("   nothing")
    for name in sorted(moved, key=lambda k: -moved[k]):
        log("   %-50s %5d" % (name[:50], moved[name]))
    log("   %d rectangle(s) in all" % sum(moved.values()))

    log("")
    log("brought to the front")
    for name in sorted(fronted, key=lambda k: -fronted[k])[:14]:
        log("   %-50s %5d" % (name[:50], fronted[name]))
    log("   %d curve(s) in all" % sum(fronted.values()))

    if kept:
        log("")
        log("left alone - these are meant not to print")
        for name in sorted(kept, key=lambda k: -kept[k]):
            log("   %-50s %5d" % (name[:50], kept[name]))

    if record:
        f = codecs.open(BACKUP, "w", "utf-8")
        f.write(json.dumps(record, indent=1))
        f.close()
        log("")
        log("%d object(s) recorded in %s" % (len(record), BACKUP))

    log("")
    log("The weight is now one setting: %s is at %.3f mm. Change that layer"
        % (TARGET, target.PlotWeight))
    log("and every rectangle on every sheet follows.")
    log("")
    log("Nothing is saved.")
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
