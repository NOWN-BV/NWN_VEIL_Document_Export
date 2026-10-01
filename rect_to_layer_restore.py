# -*- coding: utf-8 -*-
"""Put the rectangles back on the layers they came from.

Runs inside Rhino (IronPython 2.7):
    _-RunPythonScript <this>

Reads rect_move_backup.json, written by rect_to_layer.py, and returns each
object to its layer, to whatever print width it was carrying, and to
where it sat in the draw order. An object
that is no longer in the document is skipped.
"""
import os
import json
import codecs

import System
import Rhino
import scriptcontext as sc

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(sc.doc.Path or ".")
BACKUP = os.path.join(HERE, "rect_move_backup.json")


def main():
    if not os.path.isfile(BACKUP):
        print("no backup at %s - nothing to restore" % BACKUP)
        return
    record = json.loads(codecs.open(BACKUP, "r", "utf-8").read())
    done = gone = 0
    for row in record:
        obj = sc.doc.Objects.Find(System.Guid(row["id"]))
        if obj is None:
            gone += 1
            continue
        at = obj.Attributes.Duplicate()
        at.LayerIndex = int(row["layer"])
        at.PlotWeight = float(row["weight"])
        at.PlotWeightSource = \
            Rhino.DocObjects.ObjectPlotWeightSource(int(row["source"]))
        at.DisplayOrder = int(row.get("order", 0))
        if sc.doc.Objects.ModifyAttributes(obj.Id, at, True):
            done += 1
    print("%d object(s) put back, %d no longer in the document." % (done, gone))
    try:
        os.remove(BACKUP)
    except Exception:
        pass
    sc.doc.Views.Redraw()


try:
    main()
except Exception, e:                          # noqa: E999  (IronPython 2.7)
    import traceback
    print("EXCEPTION: %s" % e)
    print(traceback.format_exc())
