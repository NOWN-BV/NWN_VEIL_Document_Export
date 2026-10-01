# -*- coding: utf-8 -*-
"""Close the sub-millimetre gaps that print as one thick line.

Runs inside Rhino (IronPython 2.7) on VEIL_Standard Product Brochure.3dm:
    _-RunPythonScript <this>
Then LOOK, and only then save.

Thousands of layout-space strokes sit on top of each other, but they were
measured in the export at 2400dpi and a stroke drawn twice in the same place
renders exactly as one: same width, same black. Those are not the problem
and are left alone.

What prints heavy is a pair of hairlines a fraction of a millimetre apart.
Each is 0.127mm wide, so two of them 0.09mm apart make a solid band nearly
twice that and the eye reads one thick line.

Which of the two moves matters, because these are sides of rectangles and
moving a side resizes its rectangle. So the side that other linework already
lines up with stays, and the one standing on its own is brought onto it.
With equal support the higher coordinate gives way. Either way the move is
under a third of a millimetre and cannot be seen; the doubling can.

Lines of 5mm or less are ignored outright. On the 05-4 install sheets a
short pair a quarter of a millimetre apart is a material thickness drawn as
two lines, and closing it would delete what the drawing is saying. Of what
remains, only pairs that cannot be deliberate are touched:

    under 0.11mm apart      at 200dpi that is less than one printed pixel,
                            so it cannot be two lines on purpose
    25mm or longer          a run that long is a frame or a rule

Everything else is listed and left to you.
"""
import os
import codecs

import Rhino
import scriptcontext as sc

try:
    HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    HERE = os.path.dirname(sc.doc.Path or ".")
LOG = os.path.join(HERE, "snap_log.txt")

SAME = 0.004          # mm: nearer than this is already the same coordinate
MIN_SEG = 5.0         # mm: a line this short or shorter is not looked at
MAX_GAP = 0.35        # mm: beyond this they read as two lines, not one
MIN_RUN = 5.0         # mm: shorter than this and they do not run together
SURE_GAP = 0.11       # mm: under one printed pixel - cannot be deliberate
SURE_RUN = 25.0       # mm: long enough to be a frame rather than a detail

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
    st.HiddenObjects = False
    st.IncludeLights = False
    st.IncludeGrips = False
    return sc.doc.Objects.GetObjectList(st)


def straight_pieces(crv):
    out = []
    try:
        pieces = crv.DuplicateSegments()
    except Exception:
        pieces = None
    if not pieces:
        pieces = [crv]
    for c in pieces:
        if c is None or not c.IsLinear(SAME):
            continue
        a, b = c.PointAtStart, c.PointAtEnd
        if a.DistanceTo(b) <= MIN_SEG:
            continue
        out.append((a, b))
    return out


def shifted(p, axis, to):
    if axis == 0:
        return Rhino.Geometry.Point3d(to, p.Y, p.Z)
    return Rhino.Geometry.Point3d(p.X, to, p.Z)


def move_points(crv, axis, frm, to):
    """A copy of the curve with its points on `frm` moved to `to`.

    Returns None for a kind of curve whose points cannot be edited this way,
    so the caller can report it rather than damage it.
    """
    copy = crv.Duplicate()
    moved = 0

    if isinstance(copy, Rhino.Geometry.PolylineCurve):
        pl = copy.ToPolyline()
        pts = []
        for i in range(pl.Count):
            p = pl[i]
            v = p.X if axis == 0 else p.Y
            if abs(v - frm) <= SAME:
                p = shifted(p, axis, to)
                moved += 1
            pts.append(p)
        if not moved:
            return None
        return Rhino.Geometry.PolylineCurve(pts), moved

    if isinstance(copy, Rhino.Geometry.LineCurve):
        new = []
        for p in (copy.Line.From, copy.Line.To):
            v = p.X if axis == 0 else p.Y
            if abs(v - frm) <= SAME:
                p = shifted(p, axis, to)
                moved += 1
            new.append(p)
        if not moved:
            return None
        return Rhino.Geometry.LineCurve(new[0], new[1]), moved

    if isinstance(copy, Rhino.Geometry.NurbsCurve):
        for i in range(copy.Points.Count):
            cp = copy.Points[i]
            p = cp.Location
            v = p.X if axis == 0 else p.Y
            if abs(v - frm) <= SAME:
                copy.Points.SetPoint(i, shifted(p, axis, to), cp.Weight)
                moved += 1
        if not moved:
            return None
        return copy, moved

    return None


def collect():
    """Every straight page-space piece, filed by sheet, axis and coordinate."""
    sheets = {}
    for pv in sc.doc.Views.GetPageViews():
        sheets[str(pv.MainViewport.Id)] = pv.PageName

    board = {}
    for obj in every_object():
        if obj.Attributes.Space != Rhino.DocObjects.ActiveSpace.PageSpace:
            continue
        page = sheets.get(str(obj.Attributes.ViewportId))
        if page is None:
            continue
        g = obj.Geometry
        if not isinstance(g, Rhino.Geometry.Curve):
            continue
        for a, b in straight_pieces(g):
            if abs(a.X - b.X) <= SAME:                # vertical: fixed x
                board.setdefault(page, {}).setdefault(0, {}) \
                     .setdefault(round(a.X, 3), []).append(
                         (min(a.Y, b.Y), max(a.Y, b.Y), obj))
            elif abs(a.Y - b.Y) <= SAME:              # horizontal: fixed y
                board.setdefault(page, {}).setdefault(1, {}) \
                     .setdefault(round(a.Y, 3), []).append(
                         (min(a.X, b.X), max(a.X, b.X), obj))
    return board


def pairs(board):
    todo, leave = [], []
    for page in sorted(board):
        for axis in sorted(board[page]):
            fam = board[page][axis]
            coords = sorted(fam)
            for i in range(len(coords) - 1):
                c0, c1 = coords[i], coords[i + 1]
                gap = c1 - c0
                if gap <= SAME or gap > MAX_GAP:
                    continue
                run = 0.0
                for s0 in fam[c0]:
                    for s1 in fam[c1]:
                        run = max(run, min(s0[1], s1[1]) - max(s0[0], s1[0]))
                if run < MIN_RUN:
                    continue
                # whichever coordinate carries less linework gives way
                if len(fam[c0]) < len(fam[c1]):
                    frm, to = c0, c1
                else:
                    frm, to = c1, c0
                item = (page, axis, gap, run, frm, to,
                        len(fam[c0]), len(fam[c1]), list(fam[frm]))
                sure = gap < SURE_GAP or run >= SURE_RUN
                (todo if sure else leave).append(item)
    return todo, leave


def main():
    log("document: %s" % sc.doc.Path)
    log("ignoring every line of %.0fmm or less" % MIN_SEG)
    todo, leave = pairs(collect())

    log("")
    log("=" * 70)
    log("closed")
    log("=" * 70)
    if not todo:
        log("   nothing met the test")
    changed = skipped = 0
    for (page, axis, gap, run, frm, to, n0, n1, segs) in todo:
        which = "x" if axis == 0 else "y"
        done_here = 0
        for seg in segs:
            obj = seg[2]
            made = move_points(obj.Geometry, axis, frm, to)
            if made is None:
                skipped += 1
                log("   %-12s %s %.3f -> %.3f  %s cannot be edited, left"
                    % (page, which, frm, to, obj.Geometry.GetType().Name))
                continue
            if sc.doc.Objects.Replace(obj.Id, made[0]):
                done_here += 1
        if done_here:
            changed += 1
            log("   %-12s %s %8.3f -> %8.3f  gap %.3f  run %5.1f  "
                "%d curve(s)  (support %d vs %d)"
                % (page, which, frm, to, gap, run, done_here, n0, n1))

    log("")
    log("=" * 70)
    log("left for you - short, and far enough apart to be two lines on purpose")
    log("=" * 70)
    if not leave:
        log("   none")
    for (page, axis, gap, run, frm, to, n0, n1, segs) in leave:
        log("   %-12s %s %8.3f / %8.3f  gap %.3f  run %5.1f"
            % (page, "x" if axis == 0 else "y", min(frm, to), max(frm, to),
               gap, run))

    log("")
    log("%d pair(s) closed, %d left, %d curve(s) of a kind this script"
        % (changed, len(leave), skipped))
    log("   will not edit.")
    log("")
    log("Nothing is saved. The moves are under %.2fmm, so the sheets should"
        % MAX_GAP)
    log("look unchanged except where a line was printing double. Check, then")
    log("save.")
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
