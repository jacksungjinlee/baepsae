# -*- coding: utf-8 -*-
"""The company-logo folder that the site serves (v19.3a, docs/tasks/v19.3-portfolio-pictures-accounts.md Part J):
what may be in it and how its index must look. Pure checks, no network, no Pillow (Deploy runs them too).

The folder `logos/` holds only:
  index.json         {"version": 1, "size": 128, "format": "webp", "source": "logo.dev", "logos": {code: entry}}
                     entry: {"file": "005930.webp", "name": the company's name in data.json at fetch time,
                             "route": "ticker" | "domain", "w": source width, "h": source height, "vector": bool,
                             "flags": [...], "via": issuer code (a preferred share reusing its issuer's file; optional)}
  <name>.webp|png    one square 128 x 128 picture per company that has a logo (a preferred share has no file of its own;
                     no two companies share a file)
Deploy keeps only the entries whose name still matches today's data.json (keep_current): a code that now belongs to
another company falls back to the letter mark.
Anything else (another name, a sub-folder, a link, an SVG) makes the folder unusable as a whole: the fetch tool does not
write it, tools/push_logos_branch.sh refuses to push it, and tools/assemble_site.py deploys the site without logos
(every company then shows its letter mark). SVG is never served: it could carry script on our own origin.

  python3 tools/logos/logo_index.py check DIR      # exit 1 and every problem printed when DIR is not a valid folder
Unit tests: tests/test_logo_fetch.py.
"""
import json
import os
import re
import stat
import sys

INDEX = "index.json"
VERSION = 1
SIZE = 128
FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,23}\.(webp|png)$")
CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,11}$")
ROUTES = ("ticker", "domain")
MIN_FILE_BYTES = 40
MAX_FILE_BYTES = 100_000
MAX_FILES = 10_000
MAX_TOTAL_BYTES = 80_000_000
MAX_INDEX_BYTES = 3_000_000
MAX_SOURCE_PX = 100_000


def _no_constants(x):
    raise ValueError(f"index.json has {x} outside quotes")


def parse_index(raw):
    """bytes -> dict, strict (no NaN or Infinity, UTF-8). Raises ValueError."""
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError(f"index.json is {len(raw):,} bytes (at most {MAX_INDEX_BYTES:,})")
    try:
        obj = json.loads(raw.decode("utf-8"), parse_constant=_no_constants)
    except UnicodeDecodeError as e:
        raise ValueError("index.json is not UTF-8") from e
    except json.JSONDecodeError as e:
        raise ValueError(f"index.json is not JSON ({e.msg}, line {e.lineno})") from e
    if not isinstance(obj, dict):
        raise ValueError("index.json is not an object")
    return obj


def image_size(name, b):
    """(width, height) from the header of a PNG or WebP file whose name says which it is; None when the bytes are not
    that kind of picture. Reads the header only (no decoding library)."""
    if name.endswith(".png"):
        if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24 and b[12:16] == b"IHDR":
            return int.from_bytes(b[16:20], "big"), int.from_bytes(b[20:24], "big")
        return None
    if name.endswith(".webp"):
        if len(b) < 30 or b[:4] != b"RIFF" or b[8:12] != b"WEBP":
            return None
        kind = b[12:16]
        if kind == b"VP8X":
            return 1 + int.from_bytes(b[24:27], "little"), 1 + int.from_bytes(b[27:30], "little")
        if kind == b"VP8L" and b[20] == 0x2F:
            v = int.from_bytes(b[21:25], "little")
            return 1 + (v & 0x3FFF), 1 + ((v >> 14) & 0x3FFF)
        if kind == b"VP8 " and b[23:26] == b"\x9d\x01\x2a":
            return int.from_bytes(b[26:28], "little") & 0x3FFF, int.from_bytes(b[28:30], "little") & 0x3FFF
        return None
    return None


def _int_px(v):
    return isinstance(v, int) and not isinstance(v, bool) and 0 < v <= MAX_SOURCE_PX


def check_index(index, files):
    """index: the parsed index.json. files: {file name: bytes} of every other file in the folder.
    Returns a list of problems (empty = the folder is valid)."""
    bad = []
    if index.get("version") != VERSION:
        bad.append(f"version is {index.get('version')!r}, not {VERSION}")
    if index.get("size") != SIZE:
        bad.append(f"size is {index.get('size')!r}, not {SIZE}")
    logos = index.get("logos")
    if not isinstance(logos, dict):
        return bad + ["logos is not an object"]
    if len(logos) > MAX_FILES:
        bad.append(f"{len(logos):,} entries (at most {MAX_FILES:,})")
    used, owners = set(), {}
    for code, e in logos.items():
        if not CODE_RE.match(str(code)):
            bad.append(f"{code!r}: not a stock code")
            continue
        if not isinstance(e, dict):
            bad.append(f"{code}: entry is not an object")
            continue
        f = e.get("file")
        if not isinstance(f, str) or not FILE_RE.match(f):
            bad.append(f"{code}: file {f!r} is not a plain .webp or .png name")
            continue
        name = e.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            bad.append(f"{code}: name {name!r} is not the company's name (Deploy compares it with today's data.json)")
        if e.get("route") not in ROUTES:
            bad.append(f"{code}: route {e.get('route')!r} is not one of {ROUTES}")
        if not (_int_px(e.get("w")) and _int_px(e.get("h"))):
            bad.append(f"{code}: source size {e.get('w')!r} x {e.get('h')!r} is not two positive whole numbers")
        if not isinstance(e.get("vector", False), bool):
            bad.append(f"{code}: vector is not true or false")
        fl = e.get("flags", [])
        if not isinstance(fl, list) or not all(isinstance(x, str) for x in fl):
            bad.append(f"{code}: flags is not a list of words")
        via = e.get("via")
        if via is not None:
            issuer = logos.get(via) if isinstance(via, str) else None
            if not isinstance(issuer, dict) or issuer.get("file") != f or issuer.get("via") is not None:
                bad.append(f"{code}: via {via!r} is not an issuer in the index with the same file")
        if f not in files:
            bad.append(f"{code}: {f} is listed but not in the folder")
        used.add(f)
        if via is None:
            owners.setdefault(f, []).append(code)
    for f, codes in sorted(owners.items()):          # one file per company; only a preferred share (via) reuses one
        if len(codes) > 1:
            bad.append(f"{f}: the file of {len(codes)} codes ({', '.join(codes[:5])}); only a preferred share may reuse "
                       "its issuer's file (via)")
    for f in sorted(set(files) - used):
        bad.append(f"{f}: in the folder but not in index.json")
    total = 0
    for f, b in sorted(files.items()):
        total += len(b)
        if not FILE_RE.match(f):
            bad.append(f"{f}: not an allowed file name (only index.json and .webp or .png pictures)")
            continue
        if not MIN_FILE_BYTES <= len(b) <= MAX_FILE_BYTES:
            bad.append(f"{f}: {len(b):,} bytes (allowed {MIN_FILE_BYTES:,} to {MAX_FILE_BYTES:,})")
            continue
        px = image_size(f, b)
        if px is None:
            bad.append(f"{f}: not a {f.rsplit('.', 1)[1].upper()} picture")
        elif px != (SIZE, SIZE):
            bad.append(f"{f}: {px[0]} x {px[1]} px, not {SIZE} x {SIZE}")
    if total > MAX_TOTAL_BYTES:
        bad.append(f"the pictures add up to {total:,} bytes (at most {MAX_TOTAL_BYTES:,})")
    return bad


def stock_names(data):
    """{code: name} from a parsed data.json, the way the fetch tool names a company (nk, else ne, else the code)."""
    out = {}
    for s in (data.get("stocks") or []) if isinstance(data, dict) else []:
        if isinstance(s, dict) and s.get("t"):
            code = str(s["t"]).strip()
            out[code] = s.get("nk") or s.get("ne") or code
    return out


def keep_current(index, names):
    """(index, dropped codes): the entries whose name still matches names (today's data.json). A code reused by another
    company, or gone, is dropped; so is a preferred share whose issuer was dropped. Pure; the input is not changed."""
    logos = index.get("logos") or {}
    keep = {c: e for c, e in logos.items() if isinstance(e, dict) and names.get(c) == e.get("name")}
    keep = {c: e for c, e in keep.items() if e.get("via") is None or e.get("via") in keep}
    out = dict(index, logos=keep, count=len(keep))
    return out, sorted(set(logos) - set(keep))


def read_dir(path):
    """(index or None, {file name: bytes}, problems) for a folder on disk. Sub-folders, links and other kinds of entry
    are problems; nothing is followed."""
    bad, files, index = [], {}, None
    try:
        names = sorted(os.listdir(path))
    except OSError as e:
        return None, {}, [f"cannot read {path}: {type(e).__name__}"]
    for n in names:
        p = os.path.join(path, n)
        st = os.lstat(p)
        if not stat.S_ISREG(st.st_mode):
            bad.append(f"{n}: not a plain file (folder, link or other)")
            continue
        if n == INDEX:
            with open(p, "rb") as fh:
                raw = fh.read()
            try:
                index = parse_index(raw)
            except ValueError as e:
                bad.append(str(e))
            continue
        if not FILE_RE.match(n):
            bad.append(f"{n}: not an allowed file name (only index.json and .webp or .png pictures)")
            continue
        if st.st_size > MAX_FILE_BYTES:
            bad.append(f"{n}: {st.st_size:,} bytes (at most {MAX_FILE_BYTES:,})")
            continue
        with open(p, "rb") as fh:
            files[n] = fh.read()
    if index is None and not any(INDEX in b for b in bad):
        bad.append("index.json is missing")
    return index, files, bad


def validate_dir(path):
    """(index or None, problems) for a logo folder on disk."""
    index, files, bad = read_dir(path)
    if index is not None:
        bad += check_index(index, files)
    return (index if not bad else None), bad


def main(argv):
    if len(argv) != 2 or argv[0] != "check":
        raise SystemExit("usage: python3 tools/logos/logo_index.py check DIR")
    index, bad = validate_dir(argv[1])
    for b in bad[:50]:
        print("!! " + b)
    if bad:
        print(f"!! {argv[1]}: {len(bad)} problems — not a valid logo folder")
        return 1
    n = len(index["logos"])
    files = len({e["file"] for e in index["logos"].values()})
    print(f"· {argv[1]}: valid logo folder · {n:,} companies · {files:,} pictures")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
