# -*- coding: utf-8 -*-
"""Take the mirror back off the four CONFIG slots.

Runs inside Rhino (IronPython 2.7) on VEIL_Standard Product Brochure.3dm:
    _-RunPythonScript <this>
Then SAVE.

flip_panels.py mirrored each slot through the panel's face, on the reasoning
that the DXF blocks run z -38..0 where the stand-ins they replaced ran 0..38.
The mirror does land the panel in the same place the stand-in did - that part
was measured and is true - but the sheets then print the back: the returns
show as a band down both long edges, with the torsion spring slots in them.

So the stand-ins were themselves the wrong way round, and matching them
carried the fault across. The DXF is the reference and needs no correction:
the mirror comes off.

The slot is only changed if it is actually mirrored, so running this after it
has already run does nothing. family_spec.json keeps flip_face false either
way - the export should not be applying a mirror of its own.
"""
import os
import codecs

import Rhino
import scriptcontext as sc
from Rhino.Geometry import Transform, Point3d, Vector3d

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(sc.doc.Path or ".")
LOG = os.path.join(HERE, "unflip_log.txt")
CONFIG = "Reference_Nown_Panel CONFIG_%s"

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


def det3(x):
    return (x.M00 * (x.M11 * x.M22 - x.M12 * x.M21)
            - x.M01 * (x.M10 * x.M22 - x.M12 * x.M20)
            + x.M02 * (x.M10 * x.M21 - x.M11 * x.M20))


def face_flip():
    return Transform.Mirror(Point3d(0, 0, 0), Vector3d(0, 0, 1))


def main():
    log("document: %s" % sc.doc.Path)
    flip = face_flip()
    undone, already = 0, 0

    for key in "ABCD":
        slot = sc.doc.InstanceDefinitions.Find(CONFIG % key, True)
        if slot is None:
            log("slot %s missing" % key)
            continue
        geoms, attrs, touched = [], [], False
        for obj in slot.GetObjects():
            g = obj.Geometry
            if isinstance(g, Rhino.Geometry.InstanceReferenceGeometry):
                d = det3(g.Xform)
                inner = sc.doc.InstanceDefinitions.FindId(g.ParentIdefId)
                name = inner.Name if inner else "?"
                if d < 0:
                    # mirroring again undoes it - a mirror is its own inverse
                    g = Rhino.Geometry.InstanceReferenceGeometry(
                        g.ParentIdefId, Transform.Multiply(g.Xform, flip))
                    touched = True
                    log("slot %s  %-22s  det %+.0f -> mirror removed"
                        % (key, name, d))
                else:
                    already += 1
                    log("slot %s  %-22s  det %+.0f -> already plain"
                        % (key, name, d))
            geoms.append(g)
            attrs.append(obj.Attributes.Duplicate())
        if touched and sc.doc.InstanceDefinitions.ModifyGeometry(
                slot.Index, geoms, attrs):
            undone += 1

    log("")
    log("mirrors removed: %d, already plain: %d" % (undone, already))
    log("Look at 02-3 and 02-4: no band should run down the panel edges.")
    log("Then SAVE.")
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
