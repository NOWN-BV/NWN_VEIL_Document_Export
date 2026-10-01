# -*- coding: utf-8 -*-
"""Find the characters Replica cannot set, and put them back as ones it can.

Runs inside Rhino (IronPython 2.7) on VEIL_Standard Product Brochure.3dm:
    _-RunPythonScript <this>
Then LOOK, and only then save.

The Effective NRC formula on 05-3 is typed as

    SUM x(x1,x2,x3,x4)  over  N SUM x

and prints as "(1,2,3,4)" over "N ". The sigma and every x have gone. They
were never in the file's font: Replica carries 301 characters and the Greek
capital sigma is not among them, nor is the mathematical italic x, so the
export drops them silently and whatever is left closes up. The trailing
space after the N is where its sigma used to be.

Replica does carry the right characters for this. U+2211, the summation
sign, is the one a formula wants anyway - U+03A3 is the Greek letter, and
using it for a sum was the mistake. And an ordinary x is there; the
mathematical italic x is a separate character that almost no text font has.

So every text block and every document string is read, any character
outside the font is found, and the ones with a sound equivalent are
replaced:

    U+03A3  GREEK CAPITAL SIGMA   ->  U+2211  N-ARY SUMMATION
    U+1D465 MATHEMATICAL ITALIC X ->  x       and the rest of that block
    U+2300  DIAMETER SIGN         ->  U+00D8  O WITH STROKE
    U+2032  PRIME                 ->  '
    U+2033  DOUBLE PRIME          ->  "

Anything else that the font cannot set is reported and left alone, because
guessing at a replacement for a character nobody expected is worse than
saying where it is.

replica_cmap.json, beside this script, holds what the font covers - the
codepoints common to all six weights, read from the installed OTFs.
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
LOG = os.path.join(HERE, "glyph_log.txt")
CMAP = os.path.join(HERE, "replica_cmap.json")

SWAP = {
    0x03A3: u"∑",      # Greek sigma -> summation
    0x2300: u"Ø",      # diameter sign -> O with stroke
    0x2032: u"'",           # prime -> apostrophe (feet)
    0x2033: u'"',           # double prime -> quote (inches)
    0x00A0: u" ",           # no-break space -> space
    0x2212: u"-",           # minus sign -> hyphen
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


def authored(g):
    """The text as typed, with its field codes rather than their values."""
    for name in ("PlainTextWithFields", "RichText", "PlainText"):
        try:
            v = getattr(g, name, None)
        except Exception:
            continue
        if v:
            return u"%s" % v
    return u""


def codepoints(text):
    """(codepoint, the characters that carry it) through a string.

    IronPython 2.7 is a narrow build, so anything above U+FFFF is held as a
    surrogate pair. Reading it a character at a time sees two halves, each
    meaningless on its own - which is why the first run found U+D835 and
    U+DC65 where the mathematical italic x was, and had nothing to say about
    either. The pair has to be put back together before it can be matched.
    """
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        o = ord(c)
        if 0xD800 <= o <= 0xDBFF and i + 1 < n:
            lo = ord(text[i + 1])
            if 0xDC00 <= lo <= 0xDFFF:
                cp = 0x10000 + ((o - 0xD800) << 10) + (lo - 0xDC00)
                yield cp, text[i:i + 2]
                i += 2
                continue
        yield o, c
        i += 1


def math_letter(cp):
    """The plain letter or digit behind a Mathematical Alphanumeric one.

    U+1D400 onwards is the alphabet over and over in one style after
    another - bold, italic, script, fraktur - 26 capitals then 26 smalls
    each time, with the digits at the end. So the letter is the offset
    taken modulo 52. A few slots are holes, because those particular
    letters already existed elsewhere in Unicode and were not duplicated;
    the arithmetic is right either side of them and the formula on 05-3
    uses none of them.
    """
    if 0x1D7CE <= cp <= 0x1D7FF:
        return unichr(ord("0") + (cp - 0x1D7CE) % 10)
    if 0x1D400 <= cp <= 0x1D7CD:
        i = (cp - 0x1D400) % 52
        return unichr(ord("A") + i) if i < 26 else unichr(ord("a") + i - 26)
    return None


def fold(cp):
    """A plain-text stand-in for a codepoint, or None."""
    if cp in SWAP:
        return SWAP[cp]
    m = math_letter(cp)
    if m is not None:
        return m
    try:
        import unicodedata
        ch = unichr(cp) if cp <= 0xFFFF else None
        if ch is not None:
            f = unicodedata.normalize("NFKC", ch)
            if f and f != ch:
                return f
    except Exception:
        pass
    return None


def main():
    log("document: %s" % sc.doc.Path)
    if not os.path.isfile(CMAP):
        log("no %s - run the font check first" % os.path.basename(CMAP))
        return
    cmap = set(json.loads(codecs.open(CMAP, "r", "utf-8").read()))
    log("Replica covers %d codepoints" % len(cmap))

    def bad_chars(text):
        """Every codepoint in the text the font cannot set, with its chars."""
        out = {}
        for cp, chars in codepoints(text):
            if cp > 31 and cp not in cmap:
                out[cp] = chars
        return sorted(out.items())

    sheets = {}
    for pv in sc.doc.Views.GetPageViews():
        sheets[str(pv.MainViewport.Id)] = pv.PageName

    fixed = 0
    unmapped = {}
    log("")
    log("=" * 70)
    log("text blocks")
    log("=" * 70)
    for obj in every_object():
        g = obj.Geometry
        if not isinstance(g, Rhino.Geometry.TextEntity):
            continue
        text = authored(g)
        bad = bad_chars(text)
        if not bad:
            continue
        page = sheets.get(str(obj.Attributes.ViewportId), "model space")
        new = text
        done, left = [], []
        for cp, chars in bad:
            sub = fold(cp)
            if sub is not None and all(ord(c) in cmap for c in sub):
                new = new.replace(chars, sub)
                done.append((cp, sub))
            else:
                left.append(cp)
                unmapped.setdefault(cp, []).append(page)
        log("")
        log("  [%s] %r" % (page, text.strip()[:60]))
        for cp, sub in done:
            log("        U+%04X -> %r" % (cp, sub))
        for cp in left:
            log("        U+%04X has no stand-in - left alone" % cp)
        if new != text:
            copy = g.Duplicate()
            copy.RichText = new
            if sc.doc.Objects.Replace(obj.Id, copy):
                fixed += 1
                log("        now: %r" % new.strip()[:60])

    log("")
    log("=" * 70)
    log("document strings")
    log("=" * 70)
    keys = list(sc.doc.Strings.Keys) if sc.doc.Strings.Count else []
    hit = 0
    for key in keys:
        val = sc.doc.Strings.GetValue(key)
        if not val:
            continue
        bad = bad_chars(val)
        if not bad:
            continue
        hit += 1
        new = val
        for cp, chars in bad:
            sub = fold(cp)
            if sub is not None and all(ord(c) in cmap for c in sub):
                new = new.replace(chars, sub)
                log("  %s: U+%04X -> %r" % (key, cp, sub))
            else:
                unmapped.setdefault(cp, []).append(key)
                log("  %s: U+%04X has no stand-in" % (key, cp))
        if new != val:
            sc.doc.Strings.SetString(key, new)
    if not hit:
        log("  nothing - every document string sets in Replica")

    log("")
    log("=" * 70)
    if unmapped:
        log("characters with no stand-in - decide these by hand")
        for cp in sorted(unmapped):
            where = sorted(set(unmapped[cp]))
            log("   U+%04X  on %s" % (cp, ", ".join(where)[:56]))
    else:
        log("every character outside the font had a stand-in")

    log("")
    log("%d text block(s) changed. Nothing is saved - look at 05-3 first."
        % fixed)
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
