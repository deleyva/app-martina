#!/usr/bin/env python3
"""
Build book_manifest.json from a hand-marked scanned book.

Companion to prepare_marking.py. That script finds the ink bands; a human
says what each one is, in the browser UI; this one builds the manifest with
zero guessing left.

Band states:
    L  starts a reading      -> opens a new cropped image
    C  continues the one above -> folded into the open reading
    T  text                  -> emitted as a text item, from the page OCR
    X  ignore                -> running head, page number, scanner speckle

A page with no L at all ships as one full-page image plus its text, which is
the right call for theory pages: those set an exercise's prose on the left and
its staff on the right inside the same horizontal band, and no row projection
can separate columns.

Usage:
    uv run --no-project --with pymupdf --with numpy python \
        scripts/build_from_marking.py \
        --pdf-path book.pdf --marking /tmp/marcado/marcado.json \
        --chapters chapters.json --output-dir backups/book_extraction/<slug>
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pymupdf

SEG_DPI = 150     # the marking coordinates are in this space
OUT_DPI = 300
INK = 180
PAD_Y = 10

# The reading number is printed above and to the left of its first system, in
# a band of its own that the marking UI shows as text. OCR of the whole page
# misses it — it is tiny next to a full page — so each number is read from a
# small strip blown up to NUM_DPI, where Vision returns it at confidence 1.0.
NUM_DPI = 600
NUM_ABOVE = 75    # how far above the system the number sits, in SEG_DPI px
NUM_BELOW = 20
NUM_X0, NUM_X1 = 0.05, 0.42     # fraction of page width to search
NUMBER = re.compile(r"^\s*(\d{1,3})\s*[.,·]?\s*$")


def ensure_ocr(script_dir: Path) -> Path:
    """Same Vision helper prepare_marking.py uses, compiled on demand."""
    binary = script_dir / ".vision_ocr"
    source = script_dir / "vision_ocr.swift"
    if binary.exists() and binary.stat().st_mtime >= source.stat().st_mtime:
        return binary
    subprocess.run(["swiftc", "-O", "-o", str(binary), str(source)], check=True)
    return binary


def read_number(ocr_bin: Path, page, band_y0: int, tmp: Path) -> str | None:
    """The printed number of the reading starting at band_y0, or None."""
    f = 72 / SEG_DPI
    clip = pymupdf.Rect(NUM_X0 * page.rect.width, max(0, band_y0 - NUM_ABOVE) * f,
                        NUM_X1 * page.rect.width, (band_y0 + NUM_BELOW) * f)
    page.get_pixmap(dpi=NUM_DPI, clip=clip, colorspace=pymupdf.csGRAY).save(str(tmp))
    proc = subprocess.run([str(ocr_bin), str(tmp)], capture_output=True, text=True)
    for line in proc.stdout.strip().split("\n"):
        parts = line.split("\t")
        if len(parts) >= 5 and float(parts[3]) >= 0.5:
            hit = NUMBER.match(parts[4].strip())
            if hit:
                return hit.group(1)
    return None


def useful_box(doc, page_num: int) -> tuple[int, int, int, int, int, int]:
    """Page area minus the scanner's black edge bands, in SEG_DPI pixels."""
    pix = doc[page_num].get_pixmap(dpi=SEG_DPI, colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    h, w = arr.shape
    ink = arr < INK
    cd = ink.mean(axis=0)
    left = [x for x in range(int(0.20 * w)) if cd[x] > 0.35]
    right = [x for x in range(int(0.80 * w), w) if cd[x] > 0.35]
    x0 = max(left) + 3 if left else 0
    x1 = min(right) - 3 if right else w - 1
    rd = ink[:, x0:x1].mean(axis=1)
    top = [y for y in range(int(0.12 * h)) if rd[y] > 0.35]
    bottom = [y for y in range(int(0.88 * h), h) if rd[y] > 0.35]
    y0 = max(top) + 3 if top else 0
    y1 = min(bottom) - 3 if bottom else h - 1
    return x0, y0, x1, y1, w, h


def crop(doc, page_num, box, out_path: Path, seg_w: int, seg_h: int) -> None:
    x0, y0, x1, y1 = box
    page = doc[page_num]
    sx = page.rect.width / seg_w
    sy = page.rect.height / seg_h
    clip = pymupdf.Rect(x0 * sx, y0 * sy, x1 * sx, y1 * sy)
    page.get_pixmap(dpi=OUT_DPI, colorspace=pymupdf.csGRAY, clip=clip).save(str(out_path))


def resolve_numbers(readings: list[dict]) -> None:
    """Keep only the numbers that belong to the book's own series.

    OCR also reads the numbers of the theory exercises ("1)", "3.") on the
    pages before the readings start, which would caption a reading with a
    number the page never printed. The real series is the long descending
    chain that ends at the last reading, so walk backwards from there and
    accept a number only while it keeps stepping down; anything else is a
    stray. A single unnumbered reading between n and n+2 is n+1 — the number
    is on the page, OCR just missed it.
    """
    accepted: dict[int, str] = {}
    expected = None
    for i in range(len(readings) - 1, -1, -1):
        raw = readings[i]["_num"]
        if raw is None:
            continue
        n = int(raw)
        if expected is None or (n < expected and expected - n <= 3):
            accepted[i] = str(n)
            expected = n

    known = sorted(accepted)
    for a, b in zip(known, known[1:]):
        if b - a == 2 and int(accepted[b]) - int(accepted[a]) == 2:
            accepted[a + 1] = str(int(accepted[a]) + 1)

    for i, item in enumerate(readings):
        item["_num"] = accepted.get(i)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-path", required=True)
    ap.add_argument("--marking", required=True)
    ap.add_argument("--chapters", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    ocr_bin = ensure_ocr(Path(__file__).resolve().parent)
    doc = pymupdf.open(args.pdf_path)
    marking = json.loads(Path(args.marking).read_text(encoding="utf-8"))
    by_page = {p["page"]: p for p in marking["pages"]}
    spec = json.loads(Path(args.chapters).read_text(encoding="utf-8"))

    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    num_tmp = out_root / "_num.png"

    chapters_out = []
    readings: list[dict] = []
    seq = 0
    unmarked = []

    for chapter in spec["chapters"]:
        ch_dir = out_root / f"ch{chapter['number']:02d}"
        ch_dir.mkdir(exist_ok=True)
        short = chapter["title"].split("—")[-1].strip()
        items = []

        for page_num in range(chapter["first_page"], chapter["last_page"] + 1):
            marked = by_page.get(page_num)
            if marked is None:
                unmarked.append(page_num)
                continue

            x0, y0, x1, y1, w, h = useful_box(doc, page_num)
            bands = marked["bands"]

            # The black-edge detector reads a wide staff sitting in the bottom
            # 12% of the page as the scanner bed, and clips it. The human has
            # already said which bands are music, so let them widen the box:
            # the last reading of a page kept losing its bottom line otherwise.
            music = [b for b in bands if b["state"] in ("L", "C")]
            if music:
                y0 = max(0, min(y0, min(b["y0"] for b in music) - PAD_Y))
                y1 = min(h - 1, max(y1, max(b["y1"] for b in music) + PAD_Y))

            if not any(b["state"] == "L" for b in bands):
                name = f"pagina-{page_num:03d}.png"
                crop(doc, page_num, (x0, y0, x1, y1), ch_dir / name, w, h)
                items.append({"type": "image",
                              "file": f"ch{chapter['number']:02d}/{name}",
                              "caption": f"{short} (pág. {page_num + 1})"})
                for b in bands:
                    if b["state"] == "T" and b.get("text", "").strip():
                        items.append({"type": "text", "text": b["text"].strip()})
                continue

            # Sliced page: walk the bands and fold every C into the open L.
            open_reading = None

            def flush():
                nonlocal open_reading, seq
                if open_reading is None:
                    return
                start, end, num = open_reading
                seq += 1
                name = f"lectura-{seq:03d}.png"
                crop(doc, page_num,
                     (x0, max(y0, start - PAD_Y), x1, min(y1, end + PAD_Y)),
                     ch_dir / name, w, h)
                item = {"type": "image",
                        "file": f"ch{chapter['number']:02d}/{name}",
                        "caption": short,
                        "_num": num or read_number(ocr_bin, doc[page_num], start, num_tmp),
                        "_short": short}
                items.append(item)
                readings.append(item)
                open_reading = None

            for b in bands:
                state = b["state"]
                if state == "L":
                    flush()
                    open_reading = [b["y0"], b["y1"], b.get("num")]
                elif state == "C":
                    if open_reading is None:      # a stray C with no L above it
                        open_reading = [b["y0"], b["y1"], b.get("num")]
                    else:
                        open_reading[1] = b["y1"]
                elif state == "T":
                    flush()
                    if b.get("text", "").strip():
                        items.append({"type": "text", "text": b["text"].strip()})
                # X falls through, contributing nothing
            flush()

        chapters_out.append({"number": chapter["number"], "title": chapter["title"],
                             "intro": chapter.get("intro", ""), "items": items})
        print(f"ch{chapter['number']:02d}: {len(items)} items")

    num_tmp.unlink(missing_ok=True)

    # An unnumbered system — an exercise, a worked example, a heading with a
    # symbol in it — gets the section for a caption. Inventing a number would
    # clash with the numbers printed on the page.
    resolve_numbers(readings)
    for item in readings:
        label = item.pop("_num")
        short = item.pop("_short")
        item["caption"] = f"Lectura {label} — {short}" if label else short

    if unmarked:
        print(f"\nAVISO: sin marcar, saltadas: {unmarked}")

    manifest = {"book_title": spec["book_title"], "chapters": chapters_out}
    (out_root / "book_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(chapters_out)} capítulos, {seq} lecturas -> {out_root/'book_manifest.json'}")


if __name__ == "__main__":
    main()
