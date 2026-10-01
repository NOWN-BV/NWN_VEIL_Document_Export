# -*- coding: utf-8 -*-
"""Print one family's brochure, page by page, then put the file back.

Runs inside Rhino (IronPython 2.7) on VEIL_Standard Product Brochure.3dm:
    _-RunPythonScript <this>

A family's PDF walks the sheets in document order, but some of them repeat:
Basalt goes through 02-3 nine times, once per panel set. So the spec is an
ordered list of steps rather than a list of pages - each step says what the
four slots point at, what goes in the showcase grids, and which document text
changes, and contributes exactly one page.

Everything is undone at the end; the brochure is never saved.
"""
import os
import json
import codecs

import Rhino
import scriptcontext as sc
from Rhino.Geometry import Transform, Point3d, Vector3d

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(HERE, "family_spec.json")
LOG = os.path.join(HERE, "family_log.txt")
CONFIG_LAYER = "4 Panel Config"
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


def guid_empty():
    import System
    return System.Guid.Empty


def find_def(name):
    return sc.doc.InstanceDefinitions.Find(name, True)


def nested_of(idef):
    for obj in idef.GetObjects():
        if isinstance(obj.Geometry, Rhino.Geometry.InstanceReferenceGeometry):
            return obj.Geometry
    return None


def face_flip():
    """Mirror a panel through its own face, so the returns fall behind it.

    The detail looks at the side the returns are on, so a panel dropped in as
    it comes shows its lip. Turning it over fixes that but mirrors the cut
    pattern with it, and the tiling stops meeting across the seams. A
    reflection through the face leaves the pattern as drawn and only moves the
    returns to the other side.
    """
    return Transform.Mirror(Point3d(0, 0, 0), Vector3d(0, 0, 1))


def repoint(index, target_name, xform, flip):
    idef = sc.doc.InstanceDefinitions[index]
    target = find_def(target_name)
    if target is None:
        log("    block not found: %s" % target_name)
        return False
    geoms, attrs = [], []
    for obj in idef.GetObjects():
        g = obj.Geometry
        if isinstance(g, Rhino.Geometry.InstanceReferenceGeometry):
            use = Transform.Multiply(xform, face_flip()) if flip else xform
            g = Rhino.Geometry.InstanceReferenceGeometry(target.Id, use)
        geoms.append(g)
        attrs.append(obj.Attributes.Duplicate())
    return sc.doc.InstanceDefinitions.ModifyGeometry(index, geoms, attrs)


def read_slots():
    state = {}
    for key in "ABCD":
        idef = find_def(CONFIG % key)
        if idef is None:
            continue
        ref = nested_of(idef)
        if ref is None:
            continue
        inner = sc.doc.InstanceDefinitions.FindId(ref.ParentIdefId)
        state[key] = (idef.Index, inner.Name if inner else None, ref.Xform)
    return state


def showcase_regions():
    """The 4x4 blocks of CONFIG instances, keyed by centre x.

    Each cell keeps the world transform of the panel it shows - the instance
    transform combined with the nested reference's - so a replacement lands
    exactly where the original sat.
    """
    layer = sc.doc.Layers.FindName(CONFIG_LAYER)
    if layer is None:
        return {}
    cells = []
    for obj in sc.doc.Objects:
        if obj.Attributes.LayerIndex != layer.Index:
            continue
        g = obj.Geometry
        if not isinstance(g, Rhino.Geometry.InstanceReferenceGeometry):
            continue
        idef = sc.doc.InstanceDefinitions.FindId(g.ParentIdefId)
        if idef is None or "CONFIG" not in idef.Name:
            continue
        ref = nested_of(idef)
        world = Transform.Multiply(g.Xform, ref.Xform) if ref else g.Xform
        cells.append((g.Xform.M03, g.Xform.M23, obj.Id, world))

    groups = {}
    for item in sorted(cells, key=lambda c: (c[0], c[1])):
        for key in groups:
            if abs(key - item[0]) < 2000:
                groups[key].append(item)
                break
        else:
            groups[item[0]] = [item]

    out = {}
    for items in groups.values():
        if len(items) != 16:
            continue
        xs = sorted(set(round(i[0], 1) for i in items))
        zs = sorted(set(round(i[1], 1) for i in items), reverse=True)
        if len(xs) != 4 or len(zs) != 4:
            continue
        grid = {}
        for x, z, oid, world in items:
            grid[(zs.index(round(z, 1)), xs.index(round(x, 1)))] = (oid, world)
        out[sum(xs) / 4.0] = grid
    return out


def page_left(det):
    """Where a detail sits on the sheet. Rhino 7 has no PageRect here."""
    return det.Geometry.GetBoundingBox(True).Min.X


def detail_targets(page_name):
    for pv in sc.doc.Views.GetPageViews():
        if pv.PageName == page_name:
            dets = sorted(list(pv.GetDetailViews()), key=page_left)
            return [d.Viewport.CameraTarget.X for d in dets]
    return []


def detail_extents(page_name):
    """What model-space rectangle each detail actually shows.

    The camera target says where a detail is aimed, not how much it takes
    in, so a grid can be dropped into the right block and still fall outside
    the frame. This reports the frame.
    """
    out = []
    for pv in sc.doc.Views.GetPageViews():
        if pv.PageName != page_name:
            continue
        for det in sorted(list(pv.GetDetailViews()), key=page_left):
            vp = det.Viewport
            try:
                rc = vp.GetNearRect()
            except Exception:
                out.append(None)
                continue
            pts = [p for p in rc if hasattr(p, "X")]
            if len(pts) < 3:
                out.append(None)
                continue
            xs = [p.X for p in pts]
            zs = [p.Z for p in pts]
            out.append((min(xs), max(xs), min(zs), max(zs)))
    return out


def fill(grid, cells, layer_index, placed, hidden, flip):
    ok, failed, first = 0, 0, None
    for r in range(4):
        for c in range(4):
            if (r, c) not in grid:
                continue
            spec = cells[r][c]
            target = find_def(spec["block"])
            if target is None:
                log("    missing %s" % spec["block"])
                failed += 1
                continue
            oid, world = grid[(r, c)]
            if sc.doc.Objects.Hide(oid, True):
                hidden.append(oid)
            x = Transform.Multiply(world, face_flip()) if flip else world
            att = Rhino.DocObjects.ObjectAttributes()
            att.LayerIndex = layer_index
            att.Space = Rhino.DocObjects.ActiveSpace.ModelSpace
            att.ViewportId = guid_empty()
            gid = sc.doc.Objects.AddInstanceObject(target.Index, x, att)
            if gid != guid_empty():
                # Adding while a layout is active can land the object in page
                # space whatever the attributes said, and a panel at model
                # coordinates is then drawn far outside a 420 x 297 sheet -
                # placed, on the right layer, in the right place, invisible.
                # Setting it again after the fact is what actually sticks.
                added = sc.doc.Objects.Find(gid)
                if added is not None:
                    a2 = added.Attributes.Duplicate()
                    if (a2.Space != Rhino.DocObjects.ActiveSpace.ModelSpace
                            or a2.ViewportId != guid_empty()):
                        if first is None:
                            log("      landed in %s, moving to model space"
                                % a2.Space)
                        a2.Space = Rhino.DocObjects.ActiveSpace.ModelSpace
                        a2.ViewportId = guid_empty()
                        sc.doc.Objects.ModifyAttributes(added, a2, True)
            if gid == guid_empty():
                # Silent until now: a refused Add looked exactly like a cell
                # that had been filled, because the original was hidden either
                # way and nothing said otherwise.
                failed += 1
                if failed == 1:
                    log("      AddInstanceObject refused %s (def %d)"
                        % (spec["block"], target.Index))
                continue
            placed.append(gid)
            ok += 1
            if first is None:
                first = (gid, spec["block"], x)
    if first is not None:
        gid, name, x = first
        obj = sc.doc.Objects.Find(gid)
        bb = obj.Geometry.GetBoundingBox(True) if obj else None
        log("      %d placed, %d refused; first %s at (%.0f, %.0f, %.0f)"
            % (ok, failed, name, x.M03, x.M13, x.M23))
        if bb is not None:
            log("        lands x%.0f~%.0f z%.0f~%.0f, layer %s, space %s"
                % (bb.Min.X, bb.Max.X, bb.Min.Z, bb.Max.Z,
                   sc.doc.Layers[obj.Attributes.LayerIndex].Name,
                   obj.Attributes.Space))
    else:
        log("      nothing placed (%d refused)" % failed)


def python_exe(spec):
    """The CPython that can run the stamper - Rhino's own cannot."""
    given = spec.get("python")
    if given and os.path.isfile(given):
        return given
    home = os.environ.get("LOCALAPPDATA", "")
    for version in ("313", "312", "311", "310"):
        cand = os.path.join(home, "Programs", "Python",
                            "Python%s" % version, "python.exe")
        if os.path.isfile(cand):
            return cand
    return None


def helper(spec, name, args, missing):
    """Run one of the CPython steps that finish a printed PDF.

    Rhino draws the panels and the text, but what comes after needs Pillow
    and PyMuPDF, which IronPython cannot load. So these run as a separate
    process rather than being left for someone to remember.
    """
    exe = python_exe(spec)
    script = os.path.join(HERE, name)
    if exe is None or not os.path.isfile(script):
        log("  %s" % missing)
        return
    import System.Diagnostics as diag
    psi = diag.ProcessStartInfo()
    psi.FileName = exe
    psi.Arguments = '"%s" %s' % (script, args)
    psi.WorkingDirectory = HERE
    psi.UseShellExecute = False
    psi.RedirectStandardOutput = True
    psi.RedirectStandardError = True
    psi.CreateNoWindow = True
    proc = diag.Process.Start(psi)
    out = proc.StandardOutput.ReadToEnd()
    err = proc.StandardError.ReadToEnd()
    proc.WaitForExit()
    for line in (out or "").splitlines():
        if line.strip():
            log("    %s" % line.rstrip())
    if proc.ExitCode != 0:
        log("  %s failed (exit %d)" % (name, proc.ExitCode))
        for line in (err or "").splitlines()[-6:]:
            log("    %s" % line.rstrip())


def hairline(spec, pdf_path):
    """Set every stroke to a true PDF hairline.

    A default plot weight comes out as 0.36pt, which on a screen is about
    half a pixel: each rule lands on one pixel or spills onto two depending
    where it falls, so rules that are identical in the file print at visibly
    different weights, and which ones are heavy changes with the zoom. A
    width of zero means the thinnest line the device can draw - one pixel,
    at every resolution - so they all agree.
    """
    helper(spec, "pdf_hairline.py", '"%s" --write' % pdf_path,
           "strokes NOT set to hairline - no CPython found")


def stamp(spec, pdf_path):
    """Lay the charts and the missing pictures onto the printed PDF.

    The polar plots, the acoustic figure and the brochure's own linked
    images go on afterwards, because a picture frame in a layout's page
    space does not survive the view capture.
    """
    helper(spec, "stamp_charts.py", '"%s"' % pdf_path,
           "charts NOT stamped - no CPython found, run stamp_charts.py")


def detail_modes(page_name):
    out = []
    for pv in sc.doc.Views.GetPageViews():
        if pv.PageName != page_name:
            continue
        for det in sorted(list(pv.GetDetailViews()), key=page_left):
            mode = det.Viewport.DisplayMode
            out.append(mode.EnglishName if mode else "?")
    return out


def page_view(name):
    for pv in sc.doc.Views.GetPageViews():
        if pv.PageName == name:
            return pv
    return None


# Whether a sheet is printed as one bitmap or as geometry. main() sets it
# from the spec; capture() is called from the page loop and cannot see it.
RASTER = True


def capture(pv, dpi):
    """How one sheet is printed.

    In raster mode the whole sheet is baked to a bitmap at `dpi`, which is
    what makes the file large: thirty A3 sheets at 200dpi are thirty
    photographs of about a megabyte each, and that is nearly the whole file.
    It also rasterises the text, so the type is only as sharp as the dpi.

    With it off Rhino writes the page-space text and linework as vector and
    rasterises only what it must. That is smaller and sharper, but a
    perforated panel is thousands of curves, so it can also go the other way
    and the shaded panels can lose their shading. Which happens is a question
    about this document, so it is a setting rather than a decision.
    """
    caps = Rhino.Display.ViewCaptureSettings(pv, dpi)
    caps.RasterMode = RASTER
    caps.OutputColor = Rhino.Display.ViewCaptureSettings.ColorMode.DisplayColor
    caps.DrawBackground = True
    return caps


def main():
    spec = json.loads(codecs.open(SPEC, "r", "utf-8").read())
    out_dir = spec["out_dir"]
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    dpi = spec.get("dpi", 200)
    flip = spec.get("flip_face", True)
    global RASTER
    RASTER = bool(spec.get("raster", True))
    log("dpi %d, %s mode" % (dpi, "raster" if RASTER else "vector"))

    regions = showcase_regions()
    layer_index = sc.doc.Layers.FindName(CONFIG_LAYER).Index
    slots = read_slots()
    log("regions %d, slots %s" % (len(regions),
        ", ".join("%s=%s" % (k, v[1]) for k, v in sorted(slots.items()))))

    for job in spec["jobs"]:
        log("")
        log("=== %s  (%d steps)" % (job["family"], len(job["sequence"])))
        imported, touched = [], {}
        try:
            # Once import_all.py has been run the patterns are already in
            # the file, so there is nothing to fetch and nothing to undo.
            # Anything still missing is imported for this run only.
            for stem in job["dxf"]:
                have = set(d.Name for d in sc.doc.InstanceDefinitions
                           if d is not None and not d.IsDeleted)
                # A one-panel system only ever has _A, so asking for A..D
                # would send it back to the DXF on every run.
                # The panel letter joins straight onto the code, so there is
                # no separator to look for: Reference_RING_PLN + A.
                if any(d.startswith("Reference_%s" % stem) for d in have):
                    continue
                path = os.path.join(spec["dxf_dir"], stem + ".dxf")
                objs_before = set(o.Id for o in sc.doc.Objects)
                if not sc.doc.Import(path):
                    log("  import FAILED %s" % stem)
                    continue
                after = set(d.Name for d in sc.doc.InstanceDefinitions
                            if d is not None and not d.IsDeleted)
                imported.extend(after - have)
                for oid in set(o.Id for o in sc.doc.Objects) - objs_before:
                    sc.doc.Objects.Delete(oid, True)
            if imported:
                log("  imported %d block(s) for this run" % len(imported))
            else:
                log("  all blocks already in the file")

            for k, v in job.get("usertext", {}).items():
                if k not in touched:
                    touched[k] = sc.doc.Strings.GetValue(k)
                sc.doc.Strings.SetString(k, u"%s" % v)

            # Every showcase cell in the document draws through the same four
            # CONFIG definitions, so until they are pointed at this family the
            # sheets show whatever the file was saved with. Point them once up
            # front; the sheets that need a different set still say so.
            opening = None
            for step in job["sequence"]:
                if step.get("slots"):
                    opening = step["slots"]
                    break
            if opening:
                for key in sorted(opening):
                    if key in slots:
                        repoint(slots[key][0], opening[key], slots[key][2], flip)
                log("  slots -> %s" % ", ".join(
                    "%s=%s" % (k, v.replace("Reference_", ""))
                    for k, v in sorted(opening.items())))

            pdf = Rhino.FileIO.FilePdf.Create()
            pages = 0
            printed = []
            for step in job["sequence"]:
                pv = page_view(step["page"])
                if pv is None:
                    log("  no such page: %s" % step["page"])
                    continue
                placed, hidden = [], []
                try:
                    for k, v in step.get("text", {}).items():
                        if k not in touched:
                            touched[k] = sc.doc.Strings.GetValue(k)
                        sc.doc.Strings.SetString(k, u"%s" % v)
                    for key in sorted(step.get("slots", {})):
                        repoint(slots[key][0], step["slots"][key], slots[key][2], flip)
                    if step.get("slots") or step.get("grids"):
                        log("    display mode: %s"
                            % ", ".join(detail_modes(step["page"])))
                    grids = step.get("grids") or []
                    if grids:
                        targets = detail_targets(step["page"])
                        frames = detail_extents(step["page"])
                        for i, fr in enumerate(frames):
                            log("    detail %d shows %s" % (i, "x%.0f~%.0f z%.0f~%.0f" % fr
                                                            if fr else "?"))
                        # Each detail looks at its own block of panels, so two
                        # of them must never be sent the same one - that is
                        # how a page ends up with a grid repeated and another
                        # slot left empty.
                        for i, g in enumerate(grids):
                            if i >= len(targets):
                                log("    grid %d has no detail to go in" % i)
                                break
                            # Prefer the block that falls inside what the
                            # detail frames; a camera target alone can point
                            # between two of them.
                            frame = frames[i] if i < len(frames) else None
                            inside = []
                            if frame:
                                x0, x1 = frame[0], frame[1]
                                inside = [k for k in regions if x0 <= k <= x1]
                            if len(inside) == 1:
                                best = inside[0]
                                how = "framed"
                            else:
                                best = min(regions.keys(),
                                           key=lambda k: abs(k - targets[i]))
                                how = "nearest %.0f away" % abs(best - targets[i])
                                if len(inside) > 1:
                                    how = "%d blocks in frame, took nearest" % len(inside)
                            log("    grid %d -> detail %d -> block x%.0f (%s)"
                                % (i, i, best, how))
                            fill(regions[best], g, layer_index, placed, hidden, flip)
                        if len(grids) < len(targets):
                            log("    %d detail(s) on this sheet have no grid"
                                % (len(targets) - len(grids)))
                    sc.doc.Views.Redraw()
                    pdf.AddPage(capture(pv, dpi))
                    pages += 1
                    printed.append(step)
                    log("  %2d  %-24s %s" % (pages, step["page"],
                        step.get("label", "")))
                finally:
                    for oid in placed:
                        sc.doc.Objects.Delete(oid, True)
                    for oid in hidden:
                        sc.doc.Objects.Show(oid, True)

            out = os.path.join(out_dir, "%s.pdf" % job["family"])
            pdf.Write(out)
            log("  %d page(s) -> %s  %s"
                % (pages, out, "ok" if os.path.exists(out) else "FAILED"))
            if os.path.exists(out):
                # A sheet the document no longer has is simply skipped, so the
                # page numbers in the PDF are not the step numbers in the
                # spec. Write down what actually came out, and let the stamper
                # place by that rather than by counting steps.
                manifest = os.path.splitext(out)[0] + "_pages.json"
                fh = codecs.open(manifest, "w", "utf-8")
                fh.write(json.dumps([{"page": st["page"],
                                      "chart": st.get("chart") or {}}
                                     for st in printed], indent=1))
                fh.close()
                log("  page list -> %s" % os.path.basename(manifest))
                # hairline first: stamping copies this file to the
                # charts version, so doing it here reaches both
                hairline(spec, out)
                stamp(spec, out)
        finally:
            for name in imported:
                idef = find_def(name)
                if idef is not None:
                    sc.doc.InstanceDefinitions.Delete(idef.Index, True, True)
            for key in sorted(slots):
                index, name, xform = slots[key]
                if name:
                    repoint(index, name, xform, False)
            for k, v in touched.items():
                sc.doc.Strings.SetString(k, v if v else u"")
            log("  restored")

    sc.doc.Views.Redraw()
    log("")
    log("done - close the brochure WITHOUT saving.")


try:
    main()
except Exception, e:                          # noqa: E999  (IronPython 2.7)
    import traceback
    log("EXCEPTION: %s" % e)
    log(traceback.format_exc())

f = codecs.open(LOG, "w", "utf-8")
f.write(u"\n".join(lines))
f.close()
