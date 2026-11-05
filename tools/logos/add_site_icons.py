#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add our own website icons to the logo picker, append only:  python3 tools/logos/add_site_icons.py --source DIR

DIR is the icon collector's output (tools/logos/site_icons.py, branch claude/logos-site-icons): site_icons.csv with a
decision per code, kr/<code>.png (decision 'kept') and review/<code>.png ('needs_review': photo-like or hard to see).
Writes logo-review/icons/<code>.png and the manifest logo-review/icons.json, which build_review_page.py reads:
  "005930": "icons/005930.png"                            kept: a pre-pick candidate, last (after the providers)
  "003310": {"path": "icons/003310.png", "check": true}   needs a look: never pre-picked; offered in the Fix panel only,
                                                          as "Own icon (check)"
Jack's rules (2026-11-05): the icons are site files stored once (never re-committed daily), so this is append only —
a code already in the manifest is left exactly as it is and an existing file is never overwritten; re-run it with a
newer collection to add the codes that are new. The same picture is stored once: a preferred share (005935 next to
005930) or another code whose picture is pixel-for-pixel the same points to the file already there. When that other
code is a different company (a group logo, or a web host's default icon), the later one is stored as "check" (never
pre-picked) and said loudly. Each new PNG is
re-encoded losslessly when that makes it smaller (the decoded pixels are compared, so nothing changes visually):
Pillow, plus oxipng when it is installed (pip install pyoxipng; optional, about 20% smaller on the first collection).
Nothing here fetches anything. Run python3 tools/logos/build_review_page.py afterwards to put them in the page.
"""
import argparse
import csv
import hashlib
import io
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
from logo_ids import common_code, is_krx_code  # noqa: E402

OUT_DIR = ROOT / "logo-review" / "icons"
MANIFEST = ROOT / "logo-review" / "icons.json"
FOLDERS = (("kr", "kept", False), ("review", "needs_review", True))
MAX_SIDE = 512
try:
    import oxipng                                                # optional: pip install pyoxipng
except ImportError:
    oxipng = None


def rgba(png):
    """(size, RGBA bytes) of a PNG; raises ValueError for anything that is not a PNG of a sensible size."""
    from PIL import Image
    try:
        im = Image.open(io.BytesIO(png))
        fmt = im.format
        im.load()
    except Exception as e:                                       # noqa: BLE001 — reported by the caller
        raise ValueError(f"not readable ({type(e).__name__})") from None
    if fmt != "PNG":
        raise ValueError(f"not a PNG ({fmt})")
    if not (0 < im.width <= MAX_SIDE and 0 < im.height <= MAX_SIDE):
        raise ValueError(f"size {im.width}x{im.height}")
    return im.size, im.convert("RGBA").tobytes()


def pixel_key(png):
    size, px = rgba(png)
    return hashlib.sha256(f"{size[0]}x{size[1]}|".encode() + px).hexdigest()


def optimise(png):
    """The smallest of: the file as it is, Pillow's optimised RGBA encoding, and an exact palette encoding (only when
    the picture has at most 256 colours, transparency included). A candidate counts only if it decodes to exactly the
    same pixels."""
    from PIL import Image
    size, px = rgba(png)
    im = Image.frombytes("RGBA", size, px)
    best = png
    cands = []
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    cands.append(buf.getvalue())
    colors = im.getcolors(256)
    if colors:
        pal = [c for _, c in colors]
        index = {c: i for i, c in enumerate(pal)}
        p = Image.new("P", size)
        p.putpalette([v for c in pal for v in c[:3]])
        p.putdata([index[c] for c in getattr(im, "get_flattened_data", im.getdata)()])
        buf = io.BytesIO()
        p.save(buf, "PNG", optimize=True, transparency=bytes(c[3] for c in pal))
        cands.append(buf.getvalue())
    if oxipng:
        cands += [oxipng.optimize_from_memory(c, level=4) for c in [png] + cands]
    for c in cands:
        if len(c) < len(best) and rgba(c) == (size, px):
            best = c
    return best


def load_manifest(path):
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SystemExit(f"!! {path}: expected an object {{code: path}}")
    return raw


def entry_path(entry):
    return entry if isinstance(entry, str) else (entry or {}).get("path", "")


def write_manifest(path, manifest):
    """Written to a temporary file next to it, then swapped in: a stopped run never leaves half a manifest."""
    path = pathlib.Path(path)
    text = json.dumps(dict(sorted(manifest.items())), ensure_ascii=False, indent=1, allow_nan=False)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text + "\n", encoding="utf-8")
    os.replace(tmp, path)


def add_icons(source, out_dir=OUT_DIR, manifest_path=MANIFEST):
    """Append the collector's kept and needs-review icons. Returns (counts, log lines)."""
    source, out_dir = pathlib.Path(source), pathlib.Path(out_dir)
    with open(source / "site_icons.csv", newline="", encoding="utf-8") as f:
        decision = {str(r["code"]).strip().upper(): r["decision"] for r in csv.DictReader(f)}
    manifest = load_manifest(manifest_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    index = {}                                                   # pixel key -> "icons/<file>" already on disk
    for p in sorted(out_dir.glob("*.png")):
        index.setdefault(pixel_key(p.read_bytes()), f"icons/{p.name}")
    n = {"kept": 0, "check": 0, "files written": 0, "same picture as a file already there": 0,
         "already in the manifest (left as is)": 0, "same picture as another company's (stored as check)": 0,
         "refused": 0}
    log = []
    for folder, want, folder_check in FOLDERS:
        files = sorted((source / folder).glob("*.png"),
                       key=lambda p: (common_code(p.stem.upper()), p.stem.upper() != common_code(p.stem.upper()),
                                      p.stem.upper()))
        for f in files:
            code, check = f.stem.upper(), folder_check
            why = ("not a KRX code" if not is_krx_code(code) else
                   f"site_icons.csv says {decision.get(code, 'nothing')!r}, not {want!r}" if decision.get(code) != want else "")
            if why:
                n["refused"] += 1
                log.append(f"  !! {folder}/{f.name}: {why} — not added")
                continue
            if code in manifest:
                n["already in the manifest (left as is)"] += 1
                continue
            data = f.read_bytes()
            try:
                key = pixel_key(data)
            except ValueError as e:
                n["refused"] += 1
                log.append(f"  !! {folder}/{f.name}: {e} — not added")
                continue
            path = index.get(key)
            if path:
                n["same picture as a file already there"] += 1
                owner = pathlib.Path(path).stem.upper()
                if common_code(owner) != common_code(code) and not check:
                    check = True                                 # another company's picture: Jack looks at it first
                    n["same picture as another company's (stored as check)"] += 1
                    log.append(f"  !! {code}: the same picture as {owner}'s (another company: a group logo or a web "
                               f"host's default icon?) — stored as 'check', never pre-picked")
            else:
                target = out_dir / f"{code}.png"
                if target.exists():                              # a different picture under this name: never overwrite
                    n["refused"] += 1
                    log.append(f"  !! {target.name} already exists with another picture — {code} not added")
                    continue
                target.write_bytes(optimise(data))
                path = f"icons/{target.name}"
                index[key] = path
                n["files written"] += 1
            manifest[code] = {"path": path, "check": True} if check else path
            n["check" if check else "kept"] += 1
    write_manifest(manifest_path, manifest)
    files = sorted(out_dir.glob("*.png"))
    used = {entry_path(e) for e in manifest.values()}
    stray = [p.name for p in files if f"icons/{p.name}" not in used]
    if stray:
        log.append(f"  !! files not in the manifest: {len(stray)} ({', '.join(stray[:5])})")
    n["manifest entries"] = len(manifest)
    n["files in the folder"] = len(files)
    n["folder bytes"] = sum(p.stat().st_size for p in files)
    return n, log


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", required=True, help="the collector's folder (site_icons.csv, kr/, review/)")
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--manifest", default=str(MANIFEST))
    a = ap.parse_args(argv)
    print("· lossless optimisation: " + ("Pillow + oxipng" if oxipng else "Pillow only (pip install pyoxipng for smaller files)"))
    n, log = add_icons(a.source, a.out, a.manifest)
    for line in log:
        print(line)
    print("· " + " · ".join(f"{k} {v:,}" for k, v in n.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
