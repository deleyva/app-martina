#!/usr/bin/env python3
"""
Prepare a scanned book for hand marking.

Where a reading starts and ends is a visual decision, not a geometric one.
Detecting the ink bands works; guessing what each band *is* does not — the
2026-08-30 melodic import split two-system readings in half and printed a
caption between the halves. So the machine finds the bands and the human
says what they are.

This writes a folder with one PNG per page, a marking.json holding the
detected bands with a pre-filled guess, and the marking UI. Serve it and
mark:

    uv run --no-project --with pymupdf --with numpy python \
        scripts/prepare_marking.py --pdf-path book.pdf --output-dir /tmp/marcado
    cd /tmp/marcado && python3 -m http.server 8777
    # open http://localhost:8777 , mark, download marcado.json

Then feed marcado.json to extract_scanned_book.py --marking.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pymupdf

SEG_DPI = 150
VIEW_DPI = 150      # the UI overlays band coordinates on this render, so it
                    # must match SEG_DPI exactly or the boxes drift
OCR_DPI = 200
INK = 180
MIN_CONF = 0.5
SYSTEM_SPAN = 0.5
MAX_DENSITY = 0.45
GROUP_FACTOR = 0.45


def ink_runs(mask, min_gap, min_h):
    idx = np.where(mask)[0]
    if not len(idx):
        return []
    out, start, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - prev > min_gap:
            out.append((int(start), int(prev)))
            start = i
        prev = i
    out.append((int(start), int(prev)))
    return [b for b in out if b[1] - b[0] >= min_h]


def useful_columns(ink):
    h, w = ink.shape
    d = ink.mean(axis=0)
    left = [x for x in range(int(0.20 * w)) if d[x] > 0.35]
    right = [x for x in range(int(0.80 * w), w) if d[x] > 0.35]
    return (max(left) + 3 if left else 0), (min(right) - 3 if right else w - 1)


def ensure_ocr(script_dir: Path) -> Path:
    binary = script_dir / ".vision_ocr"
    source = script_dir / "vision_ocr.swift"
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    subprocess.run(["swiftc", "-O", "-o", str(binary), str(source)], check=True)
    return binary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-path", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--first", type=int, default=0)
    ap.add_argument("--last", type=int, default=None)
    ap.add_argument("--book-title", default="")
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    ocr_bin = ensure_ocr(script_dir)

    out = Path(args.output_dir)
    (out / "pages").mkdir(parents=True, exist_ok=True)
    shutil.copy(script_dir / "marking_ui.html", out / "index.html")

    doc = pymupdf.open(args.pdf_path)
    last = args.last if args.last is not None else len(doc) - 1
    tmp = out / "_tmp.png"
    pages = []

    for pn in range(args.first, last + 1):
        page = doc[pn]

        page.get_pixmap(dpi=OCR_DPI).save(str(tmp))
        proc = subprocess.run([str(ocr_bin), str(tmp)], capture_output=True, text=True)
        lines = []
        for line in proc.stdout.strip().split("\n"):
            parts = line.split("\t")
            if len(parts) >= 5:
                try:
                    lines.append((float(parts[0]), float(parts[3]), parts[4]))
                except ValueError:
                    pass

        pix = page.get_pixmap(dpi=SEG_DPI, colorspace=pymupdf.csGRAY)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        h, w = arr.shape
        ink = arr < INK
        x0, x1 = useful_columns(ink)
        usable = x1 - x0

        raw = ink_runs(ink[:, x0:x1].sum(axis=1) > max(3, int(0.004 * usable)),
                       int(0.005 * h), int(0.004 * h))

        bands = []
        for y0, y1 in raw:
            hits = [t for (y, c, t) in lines
                    if c >= MIN_CONF and len(t) > 2 and (y0 / h - 0.012) <= y <= (y1 / h + 0.004)]
            strip = ink[y0:y1 + 1, x0:x1]
            cols = np.where(strip.sum(axis=0) > 0)[0]
            span = (cols[-1] - cols[0]) / usable if len(cols) else 0.0
            if hits:
                state = "T"
            elif span < SYSTEM_SPAN or strip.mean() > MAX_DENSITY:
                state = "X"      # speckle or a black bar off the scanner bed
            else:
                state = "L"      # a staff system; the human says L or C
            bands.append({"y0": y0, "y1": y1, "state": state,
                          "num": None, "text": " ".join(hits)[:200]})

        # Pre-fill C on systems that sit close to the one above. It is only a
        # guess to save keystrokes — the human overrides it.
        heights = [b["y1"] - b["y0"] for b in bands if b["state"] == "L"]
        if heights:
            threshold = GROUP_FACTOR * float(np.median(heights))
            prev = None
            for b in bands:
                if b["state"] != "L":
                    prev = None
                    continue
                if prev is not None and b["y0"] - prev["y1"] <= threshold:
                    b["state"] = "C"
                prev = b

        page.get_pixmap(dpi=VIEW_DPI).save(str(out / "pages" / f"p{pn:03d}.png"))
        pages.append({"page": pn, "image": f"p{pn:03d}.png", "bands": bands, "touched": False})
        print(f"p{pn:03d}: {len(bands)} bandas "
              f"(L={sum(1 for b in bands if b['state']=='L')} "
              f"C={sum(1 for b in bands if b['state']=='C')} "
              f"T={sum(1 for b in bands if b['state']=='T')} "
              f"X={sum(1 for b in bands if b['state']=='X')})")

    tmp.unlink(missing_ok=True)
    (out / "marking.json").write_text(
        json.dumps({"book": args.book_title, "pages": pages}, ensure_ascii=False),
        encoding="utf-8")
    print(f"\n{len(pages)} páginas listas en {out}")
    print(f"  cd {out} && python3 -m http.server 8777")
    print("  y abre http://localhost:8777")


if __name__ == "__main__":
    main()
