#!/usr/bin/env python3
"""List the brochure's picture frames and where each one's image lives.

    python find_pictures.py            # writes charts/pictures.json

The frames on 04-3 and 04-4-B print as white boxes. Their images are not in
the .3dm: the file keeps a link to a PNG on N: and only some of the pictures
were embedded when it was saved, so the linked ones have nothing to draw.
The one on 04-1 is embedded and comes out fine, which is what tells the two
cases apart.

Fixing the file itself means re-saving it with textures embedded. Until then
this finds the source PNG for every frame so stamp_charts.py can put the
images back onto the printed PDF.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import rhino3dm as r3

HERE = Path(__file__).resolve().parent
BROCHURE = HERE / "live.3dm"
OUT = HERE / "charts" / "pictures.json"
EXTRACTED = HERE / "embedded"

# Where Rhino scattered the linked copies.
VEIL_DIR = Path(r"N:/Products/Development/Product Lab/VEIL")
SEARCH = sorted(VEIL_DIR.glob("**/*_embedded_files"))


def main() -> int:
    model = r3.File3dm.Read(str(BROCHURE))
    pages = {str(v.Viewport.Id): v.Name for v in model.Views}
    layers = {l.Index: l.Name for l in model.Layers}
    materials = {i: (model.Materials[i].Name or "") for i in range(len(model.Materials))}

    # A picture frame is a Brep wearing a picture material. Going by layer
    # misses the ones that were left on Default, and there is at least one.
    content = model.RenderContent
    picture_materials = set()
    for i in range(len(content)):
        c = content[i]
        if getattr(c, "TypeName", "") == "rdk-picture-material":
            picture_materials.add(getattr(c, "Name", ""))

    EXTRACTED.mkdir(exist_ok=True)
    embedded = {}
    files = model.EmbeddedFiles
    for i in range(len(files)):
        name = Path(str(files[i].Filename)).stem
        dest = EXTRACTED / ("%s.png" % name)
        if not dest.is_file():
            files[i].Write(str(dest))
        embedded[name] = dest

    found = []
    for obj in model.Objects:
        page = pages.get(str(obj.Attributes.ViewportId), "")
        layer = layers.get(obj.Attributes.LayerIndex, "")
        if not page:
            continue
        geom = obj.Geometry
        if geom.ObjectType != r3.ObjectType.Brep:
            continue
        name = materials.get(obj.Attributes.MaterialIndex, "")
        if name not in picture_materials:
            continue
        src = embedded.get(name)
        how = "embedded"
        if src is None:
            for base in SEARCH:
                cand = base / ("%s.png" % name)
                if cand.is_file():
                    src, how = cand, "linked"
                    break
        box = geom.GetBoundingBox()
        entry = {
            "page": page,
            "layer": layer,
            "material": name,
            "source": str(src) if src else None,
            "how": how if src else "missing",
            "box_mm": [round(box.Min.X, 3), round(box.Min.Y, 3),
                       round(box.Max.X, 3), round(box.Max.Y, 3)],
        }
        found.append(entry)
        print("  %-10s %-12s %-9s %s"
              % (page, layer, entry["how"],
                 os.path.basename(entry["source"]) if src else name[:40]))

    # Only the linked ones need help; the embedded ones already print.
    need = [f for f in found if f["how"] == "linked"]
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(found, indent=1), encoding="utf-8")
    print("")
    print("%d frame(s) on pages, %d of them print white and can be restored"
          % (len(found), len(need)))
    missing = [f for f in found if f["how"] == "missing"]
    if missing:
        print("%d have no image anywhere - they will stay blank:" % len(missing))
        for f in missing:
            print("   %-10s %s" % (f["page"], f["material"]))
    print("-> %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
