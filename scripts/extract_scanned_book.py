#!/usr/bin/env python3
"""
Extract a SCANNED book (no text layer) into the book_manifest.json shape that
`manage.py import_book_chapter` consumes.

`extract_pdf_book.py` assumes embedded images plus a text layer. A scan has
neither: one bitmap per page, no text, no outline. This script gets the text
back with OCR and decides, page by page, whether the page can be sliced.

The page-level rule, agreed with the principal:

  * More than half the ink bands are notation  -> READINGS page. Slice it into
    one image per reading, grouping the systems that belong together.
  * Otherwise                                  -> THEORY page. Ship the whole
    page as one image plus its OCR text underneath, so it stays searchable.

The reason for the split is layout, not laziness: theory pages set the text of
an exercise on the left and its staff on the right, inside the same horizontal
band. A row projection cannot separate columns, so slicing those pages would
drop the staves. Shipping the page whole loses nothing and keeps the original
spread.

OCR runs through `vision_ocr.swift` (macOS Vision, es-ES). Vision beats
tesseract on skewed scans and needs no extra language packs installed.

Usage:
    uv run --no-project --with pymupdf --with numpy python \
        scripts/extract_scanned_book.py \
        --pdf-path /path/to/book.pdf \
        --output-dir backups/book_extraction/<slug> \
        --chapters chapters.json

chapters.json:
    {"book_title": "...",
     "chapters": [{"number": 1, "title": "...", "intro": "...",
                   "first_page": 0, "last_page": 2}]}
Pages are 0-indexed and inclusive.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pymupdf

SEG_DPI = 150          # segmentation; thresholds below are tuned at this dpi
OUT_DPI = 300          # what actually gets written
OCR_DPI = 200

INK = 180              # grayscale value below which a pixel counts as ink
MIN_CONF = 0.5         # OCR confidence floor for "this band holds text"
SYSTEM_SPAN = 0.5      # a staff system spans at least this much of the page
MAX_DENSITY = 0.45     # over this, the band is a black bar off the scanner, not music
GROUP_FACTOR = 0.45    # gap over this fraction of a system's height splits readings
PAD_Y = 10
PAD_X = 24


# ---------------------------------------------------------------- OCR helper


def ensure_ocr_binary(script_dir: Path) -> Path:
    """Compile vision_ocr.swift on first use; the binary is not versioned."""
    binary = script_dir / ".vision_ocr"
    source = script_dir / "vision_ocr.swift"
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    if not source.exists():
        sys.exit(f"missing {source}")
    subprocess.run(
        ["swiftc", "-O", "-o", str(binary), str(source)],
        check=True,
    )
    return binary


def ocr_page(binary: Path, doc, page_num: int, tmp: Path) -> list[tuple[float, float, str]]:
    """Return (y0, confidence, text) per recognised line, y0 normalised 0..1."""
    doc[page_num].get_pixmap(dpi=OCR_DPI).save(str(tmp))
    proc = subprocess.run([str(binary), str(tmp)], capture_output=True, text=True)
    out = []
    for line in proc.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        try:
            out.append((float(parts[0]), float(parts[3]), parts[4]))
        except ValueError:
            continue
    return out


# ------------------------------------------------------------- segmentation


def ink_runs(mask: np.ndarray, min_gap: int, min_h: int) -> list[tuple[int, int]]:
    idx = np.where(mask)[0]
    if not len(idx):
        return []
    out: list[tuple[int, int]] = []
    start = prev = idx[0]
    for i in idx[1:]:
        if i - prev > min_gap:
            out.append((int(start), int(prev)))
            start = i
        prev = i
    out.append((int(start), int(prev)))
    return [b for b in out if b[1] - b[0] >= min_h]


def useful_columns(ink: np.ndarray) -> tuple[int, int]:
    """Drop the scanner's black edge bands.

    The band does not start at column 0 — there are a few white pixels first —
    so walking in from the edge and stopping at the first light column trims
    nothing. Take the LAST dark column inside the margin instead.
    """
    h, w = ink.shape
    density = ink.mean(axis=0)
    left = [x for x in range(int(0.20 * w)) if density[x] > 0.35]
    right = [x for x in range(int(0.80 * w), w) if density[x] > 0.35]
    return (max(left) + 3 if left else 0), (min(right) - 3 if right else w - 1)


def useful_rows(ink: np.ndarray, x0: int, x1: int) -> tuple[int, int]:
    """Same trim as useful_columns, for the black bars along top and bottom."""
    h = ink.shape[0]
    density = ink[:, x0:x1].mean(axis=1)
    top = [y for y in range(int(0.12 * h)) if density[y] > 0.35]
    bottom = [y for y in range(int(0.88 * h), h) if density[y] > 0.35]
    return (max(top) + 3 if top else 0), (min(bottom) - 3 if bottom else h - 1)


def analyse_page(doc, page_num: int, ocr_lines) -> dict:
    page = doc[page_num]
    pix = page.get_pixmap(dpi=SEG_DPI, colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    h, w = arr.shape
    ink = arr < INK
    x0, x1 = useful_columns(ink)
    usable = x1 - x0

    bands = ink_runs(
        ink[:, x0:x1].sum(axis=1) > max(3, int(0.004 * usable)),
        int(0.005 * h),
        int(0.004 * h),
    )

    systems, text_bands = [], []
    for y0, y1 in bands:
        has_text = any(
            conf >= MIN_CONF and len(txt) > 2 and (y0 / h - 0.012) <= y <= (y1 / h + 0.004)
            for (y, conf, txt) in ocr_lines
        )
        if has_text:
            text_bands.append((y0, y1))
            continue
        strip = ink[y0:y1 + 1, x0:x1]
        cols = np.where(strip.sum(axis=0) > 0)[0]
        span = (cols[-1] - cols[0]) / usable if len(cols) else 0.0
        if span < SYSTEM_SPAN:
            continue  # scanner speckle, not a staff
        if strip.mean() > MAX_DENSITY:
            continue  # a solid black bar off the scanner bed spans the page too
        systems.append((y0, y1))

    y0, y1 = useful_rows(ink, x0, x1)
    kind = "readings" if len(systems) > len(bands) / 2 else "theory"
    return {
        "page": page_num, "w": w, "h": h, "x0": x0, "x1": x1, "y0": y0, "y1": y1,
        "kind": kind, "systems": systems, "n_bands": len(bands),
    }


def group_systems(systems: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    """Group staff systems into readings by vertical gap.

    Systems of one reading sit closer to each other than to the next reading.
    The threshold is relative to system height, so it survives pages set at
    different sizes.
    """
    if not systems:
        return []
    heights = [b - a for a, b in systems]
    threshold = GROUP_FACTOR * float(np.median(heights))
    groups = [[systems[0]]]
    for prev, cur in zip(systems, systems[1:]):
        if cur[0] - prev[1] > threshold:
            groups.append([cur])
        else:
            groups[-1].append(cur)
    return groups


# ------------------------------------------------------------------ output


def paragraphs(ocr_lines) -> list[str]:
    """Join OCR lines into paragraphs, dropping running heads and page numbers."""
    keep = [
        (y, txt) for (y, conf, txt) in sorted(ocr_lines)
        if conf >= MIN_CONF and len(txt.strip()) > 2
        and not re.match(r"^\s*\d{1,3}\s*$", txt)
        and "EDGAR WILLEMS" not in txt.upper()
        and "SOLFEO - CURSO" not in txt.upper()
    ]
    out: list[str] = []
    prev_y = None
    for y, txt in keep:
        if prev_y is not None and (y - prev_y) < 0.022:
            out[-1] = f"{out[-1]} {txt.strip()}"
        else:
            out.append(txt.strip())
        prev_y = y
    return [p for p in out if len(p) > 3]


def crop(doc, page_num: int, rect_seg, out_path: Path, seg_w: int, seg_h: int) -> None:
    x0, y0, x1, y1 = rect_seg
    page = doc[page_num]
    sx = page.rect.width / seg_w
    sy = page.rect.height / seg_h
    clip = pymupdf.Rect(x0 * sx, y0 * sy, x1 * sx, y1 * sy)
    page.get_pixmap(dpi=OUT_DPI, colorspace=pymupdf.csGRAY, clip=clip).save(str(out_path))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-path", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--chapters", required=True)
    args = ap.parse_args()

    script_dir = Path(__file__).resolve().parent
    binary = ensure_ocr_binary(script_dir)

    doc = pymupdf.open(args.pdf_path)
    spec = json.loads(Path(args.chapters).read_text(encoding="utf-8"))
    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    tmp = out_root / "_ocr_tmp.png"

    chapters_out = []
    n_readings = n_pages = 0

    for chapter in spec["chapters"]:
        ch_dir = out_root / f"ch{chapter['number']:02d}"
        ch_dir.mkdir(exist_ok=True)
        items = []

        for page_num in range(chapter["first_page"], chapter["last_page"] + 1):
            lines = ocr_page(binary, doc, page_num, tmp)
            info = analyse_page(doc, page_num, lines)
            n_pages += 1

            if info["kind"] == "theory":
                name = f"pagina-{page_num:03d}.png"
                crop(doc, page_num,
                     (info["x0"], info["y0"], info["x1"], info["y1"]),
                     ch_dir / name, info["w"], info["h"])
                items.append({
                    "type": "image",
                    "file": f"ch{chapter['number']:02d}/{name}",
                    "caption": f"{chapter['title'].split('—')[-1].strip()} (pág. {page_num + 1})",
                })
                for para in paragraphs(lines):
                    items.append({"type": "text", "text": para})
            else:
                groups = group_systems(info["systems"])
                for group in groups:
                    n_readings += 1
                    y0 = max(0, group[0][0] - PAD_Y)
                    y1 = min(info["h"] - 1, group[-1][1] + PAD_Y)
                    name = f"lectura-{n_readings:03d}.png"
                    # Padding only where nothing was trimmed: widening past a
                    # trimmed edge drags the scanner's black band back in.
                    left = info["x0"] if info["x0"] else PAD_X // 2
                    right = info["x1"] if info["x1"] < info["w"] - 1 else info["w"] - 1 - PAD_X // 2
                    crop(doc, page_num, (left, y0, right, y1),
                         ch_dir / name, info["w"], info["h"])
                    items.append({
                        "type": "image",
                        "file": f"ch{chapter['number']:02d}/{name}",
                        "caption": f"Lectura {n_readings} — {chapter['title'].split('—')[-1].strip()}",
                    })

            print(f"  p{page_num:03d} {info['kind']:8s} bandas={info['n_bands']:2d} "
                  f"sistemas={len(info['systems']):2d}")

        chapters_out.append({
            "number": chapter["number"],
            "title": chapter["title"],
            "intro": chapter.get("intro", ""),
            "items": items,
        })
        print(f"ch{chapter['number']:02d}: {len(items)} items")

    tmp.unlink(missing_ok=True)
    manifest = {"book_title": spec["book_title"], "chapters": chapters_out}
    (out_root / "book_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n{len(chapters_out)} capítulos, {n_pages} páginas, {n_readings} lecturas")


if __name__ == "__main__":
    main()
