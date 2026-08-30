#!/usr/bin/env python3
"""
Extract "Lecturas rítmicas" (Edgar Willems) from a scanned PDF into the
book_manifest.json shape consumed by `manage.py import_book_chapter`.

The source PDF is a pure scan: one bitmap per page, no text layer, no
outline. The generic `extract_pdf_book.py` cannot handle it — it would
emit seven full-page images. So this script does two things instead:

  1. Deterministic row segmentation. A horizontal ink projection at
     200 dpi splits each page into staff-line bands. Verified visually
     against annotated renders of all seven pages.

  2. A hand-verified band → reading map (BOOK below). Whether a band
     opens a new reading or continues the previous one cannot be
     inferred reliably: the left-gutter ink test works on p.49 but
     collapses on p.52, where the scan is skewed. So the mapping was
     read off the annotated pages by eye, once.

Text paragraphs that contain inline musical glyphs are emitted as images,
not as text — transcribing them would silently drop the notation.

Usage:
    uv run --no-project --with pymupdf --with numpy python \
        scripts/extract_willems_rhythm.py \
        --pdf-path /path/to/LecturasRitmicas.pdf \
        --output-dir backups/book_extraction/willems-lecturas-ritmicas
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pymupdf

# Segmentation parameters — validated at this dpi against annotated renders.
SEG_DPI = 200
OUT_DPI = 300
SCALE = OUT_DPI / SEG_DPI

INK_THRESHOLD = 180          # grayscale value below which a pixel counts as ink
PAD_Y = 12                   # vertical padding around a crop, in SEG_DPI pixels
PAD_X = 26                   # horizontal padding, in SEG_DPI pixels


# --------------------------------------------------------------------------
# The hand-verified structure.
#
# Chapters are numbered 1..N in reading order — the book's own "CAPÍTULO V" /
# "CAPÍTULO VIII" labels are deliberately dropped, per the principal.
#
# Item kinds:
#   ("text", "…")            plain paragraph
#   ("heading", "…")         section heading inside the chapter
#   ("reading", n, [bands])  one reading → one cropped image, bands joined
#   ("figure", label, [bands])  a paragraph carrying inline notation → image
# --------------------------------------------------------------------------
BOOK = {
    "book_title": "Lecturas rítmicas — Edgar Willems",
    "chapters": [
        {
            "number": 1,
            "title": "Capítulo 1 — El compás de dos tiempos (de carácter pendular)",
            "intro": "Lecturas con negra, blanca, silencio de negra y ligadura. Anacrusa, contratiempo y síncopa.",
            "page": 0,
            "items": [
                ("text", "Llevar el compás"),
                ("text", "Con gestos naturales llevaremos el compás, diciendo, tres veces:"),
                ("text", "a) uno abajo, dos arriba;"),
                ("text", "b) abajo, arriba;"),
                ("text", "c) uno, dos."),
                ("text", "Lecturas (negra, blanca, silencio de negra, ligadura)."),
                ("reading", 1, [9, 10]),
                ("reading", 2, [11, 12]),
                ("heading", "Anacrusa"),
                ("reading", 3, [14]),
                ("reading", 4, [15, 16]),
                ("heading", "Contratiempo"),
                ("reading", 5, [18]),
                ("reading", 6, [19, 20]),
                ("heading", "Síncopa"),
                ("reading", 7, [22, 23]),
                ("reading", 8, [24]),
                ("text", "El ejemplo natural y armónico del profesor es primordial; el control individual de los alumnos lo es también. El término «abajo» no significa ni muy abajo ni detrás."),
            ],
        },
        {
            "number": 2,
            "title": "Capítulo 2 — El compás de cuatro tiempos (de carácter narrativo)",
            "intro": "La redonda y sus silencios. Diferentes anacrusas, contratiempos y síncopas.",
            "page": 1,
            "items": [
                ("text", "Llevar el compás, diciendo:"),
                ("text", "a) uno abajo, dos adentro, tres afuera, cuatro arriba;"),
                ("text", "b) abajo, adentro, afuera, arriba;"),
                ("text", "c) uno, dos, tres, cuatro."),
                ("figure", "Valores", [7]),
                ("reading", 1, [8, 9]),
                ("reading", 2, [10, 11]),
                ("heading", "Diferentes anacrusas"),
                ("reading", 3, [13, 14]),
                ("reading", 4, [15, 16]),
                ("reading", 5, [17, 18]),
                ("heading", "Contratiempos y síncopas"),
                ("reading", 6, [20, 21]),
                ("reading", 7, [22, 23]),
                ("reading", 8, [24, 25]),
            ],
        },
        {
            "number": 3,
            "title": "Capítulo 3 — El compás de tres tiempos (de carácter rotatorio)",
            "intro": "La blanca con puntillo. Anacrusas, contratiempos y síncopas en compás ternario.",
            "page": 2,
            "items": [
                ("text", "Llevar el compás, diciendo:"),
                ("text", "a) uno abajo, dos afuera, tres arriba;"),
                ("text", "b) abajo, afuera, arriba;"),
                ("text", "c) uno, dos, tres."),
                ("figure", "Valores", [7, 8]),
                ("reading", 1, [9, 10]),
                ("reading", 2, [11, 12]),
                ("reading", 3, [13, 14]),
                ("heading", "Anacrusas"),
                ("reading", 4, [16, 17]),
                ("reading", 5, [18, 19]),
                ("heading", "Contratiempos y síncopas"),
                ("reading", 6, [21, 22]),
                ("reading", 7, [23, 24]),
                ("reading", 8, [25, 26]),
            ],
        },
        {
            "number": 4,
            "title": "Capítulo 4 — Reconocer compases",
            "intro": "Catorce lecturas sin indicación de compás: hay que reconocerlo a primera vista.",
            "page": 3,
            "items": (
                [("reading", n, [n + 1]) for n in range(1, 15)]
                + [("text", "En un momento dado de las lecturas musicales ya no se indicarán los compases y será necesario reconocerlos a primera vista.")]
            ),
        },
        {
            "number": 5,
            "title": "Capítulo 5 — Lecturas con corcheas",
            "intro": "El silencio de corchea, la negra con puntillo y el silencio de negra con puntillo.",
            "page": 4,
            "items": [
                ("figure", "Valores", [4]),
                ("figure", "La corchea", [5]),
                ("heading", "A. Lecturas de ritmos"),
                ("reading", 1, [7]),
                ("reading", 2, [8]),
                ("reading", 3, [9]),
                ("reading", 4, [10]),
                ("reading", 5, [11]),
                ("reading", 6, [12]),
                ("reading", 7, [13, 14]),
                ("reading", 8, [15]),
                ("reading", 9, [16]),
                ("reading", 10, [17]),
                ("reading", 11, [18]),
                ("reading", 12, [19]),
                ("text", "N.B. La lectura rítmica debe hacerse por frases, o como mínimo, por compases, y no nota por nota. No siempre se marca el acento de las síncopas."),
            ],
        },
        {
            "number": 6,
            "title": "Capítulo 6 — Lecturas con semicorcheas",
            "intro": "El silencio de semicorchea, la corchea con puntillo y el silencio de corchea con puntillo.",
            "page": 5,
            "items": [
                ("figure", "Valores", [4]),
                ("figure", "La semicorchea", [5, 6]),
                ("heading", "A. Lecturas de ritmos"),
                ("reading", 1, [8]),
                ("reading", 2, [9]),
                ("reading", 3, [10]),
                ("reading", 4, [11]),
                ("reading", 5, [12]),
                ("reading", 6, [13]),
                ("reading", 7, [14]),
                ("reading", 8, [15]),
                ("reading", 9, [16]),
                # continues on the next scanned page
                ("page", 6),
                ("reading", 10, [2]),
                ("reading", 11, [3]),
                ("reading", 12, [4]),
                ("reading", 13, [5]),
                ("reading", 14, [6]),
                ("reading", 15, [7, 8, 9]),
                ("reading", 16, [10, 11, 12]),
                ("reading", 17, [13, 14]),
                ("reading", 18, [15, 16, 17]),
            ],
        },
    ],
}


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------


def _runs(mask: np.ndarray, min_gap: int, min_h: int) -> list[tuple[int, int]]:
    """Group True rows into (start, end) runs, merging gaps under min_gap."""
    idx = np.where(mask)[0]
    if not len(idx):
        return []
    out: list[tuple[int, int]] = []
    start = prev = idx[0]
    for i in idx[1:]:
        if i - prev > min_gap:
            out.append((start, prev))
            start = i
        prev = i
    out.append((start, prev))
    return [b for b in out if b[1] - b[0] >= min_h]


def segment_page(doc: pymupdf.Document, page_num: int) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """Return (grayscale array at SEG_DPI, list of ink bands)."""
    pix = doc[page_num].get_pixmap(dpi=SEG_DPI, colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    h, w = arr.shape
    ink = arr < INK_THRESHOLD
    rows = ink[:, int(0.03 * w):int(0.97 * w)].sum(axis=1)
    bands = _runs(rows > max(3, int(0.004 * w)), int(0.004 * h), int(0.004 * h))
    return arr, bands


def band_hbounds(arr: np.ndarray, y0: int, y1: int) -> tuple[int, int]:
    """Leftmost and rightmost ink column within a band."""
    strip = arr[y0:y1 + 1, :] < INK_THRESHOLD
    cols = np.where(strip.sum(axis=0) > 0)[0]
    if not len(cols):
        return 0, arr.shape[1] - 1
    return int(cols[0]), int(cols[-1])


# --------------------------------------------------------------------------
# Cropping
# --------------------------------------------------------------------------


def crop(doc: pymupdf.Document, page_num: int, rect_seg: tuple[int, int, int, int], out_path: Path) -> None:
    """Render the given SEG_DPI rectangle at OUT_DPI and write it to disk."""
    x0, y0, x1, y1 = rect_seg
    page = doc[page_num]
    pix_full = page.get_pixmap(dpi=SEG_DPI, colorspace=pymupdf.csGRAY)
    sx = page.rect.width / pix_full.width
    sy = page.rect.height / pix_full.height
    clip = pymupdf.Rect(x0 * sx, y0 * sy, x1 * sx, y1 * sy)
    pix = page.get_pixmap(dpi=OUT_DPI, colorspace=pymupdf.csGRAY, clip=clip)
    pix.save(str(out_path))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf-path", required=True)
    ap.add_argument("--output-dir", required=True)
    args = ap.parse_args()

    pdf = Path(args.pdf_path)
    out_root = Path(args.output_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(pdf)
    pages: dict[int, tuple[np.ndarray, list[tuple[int, int]]]] = {}

    def page_data(pn: int):
        if pn not in pages:
            pages[pn] = segment_page(doc, pn)
        return pages[pn]

    manifest_chapters = []
    total_readings = 0

    for ch in BOOK["chapters"]:
        ch_dir = out_root / f"ch{ch['number']:02d}"
        ch_dir.mkdir(exist_ok=True)
        current_page = ch["page"]

        # A page-wide common horizontal frame keeps every reading in a chapter
        # rendered at the same scale. Computed from reading bands only, using a
        # median left edge so scan speckle in the margin cannot stretch it.
        frames: dict[int, tuple[int, int]] = {}

        def frame_for(pn: int) -> tuple[int, int]:
            if pn in frames:
                return frames[pn]
            arr, bands = page_data(pn)
            lefts, rights = [], []
            page_of = ch["page"]
            for item in ch["items"]:
                if item[0] == "page":
                    page_of = item[1]
                    continue
                if item[0] != "reading" or page_of != pn:
                    continue
                for b in item[2]:
                    l, r = band_hbounds(arr, *bands[b])
                    lefts.append(l)
                    rights.append(r)
            if not lefts:
                frames[pn] = (0, arr.shape[1] - 1)
                return frames[pn]
            x0 = max(0, int(np.median(lefts)) - PAD_X)
            x1 = min(arr.shape[1] - 1, max(rights) + PAD_X)
            frames[pn] = (x0, x1)
            return frames[pn]

        items_out = []
        for item in ch["items"]:
            kind = item[0]

            if kind == "page":
                current_page = item[1]
                continue

            if kind == "text":
                items_out.append({"type": "text", "text": item[1]})
                continue

            if kind == "heading":
                items_out.append({"type": "heading", "level": 3, "text": item[1]})
                continue

            arr, bands = page_data(current_page)
            band_idx = item[2]
            y0 = max(0, bands[band_idx[0]][0] - PAD_Y)
            y1 = min(arr.shape[0] - 1, bands[band_idx[-1]][1] + PAD_Y)

            if kind == "reading":
                n = item[1]
                x0, x1 = frame_for(current_page)
                fname = f"lectura-{n:02d}.png"
                crop(doc, current_page, (x0, y0, x1, y1), ch_dir / fname)
                chapter_name = ch["title"].split("—", 1)[-1].strip()
                items_out.append({
                    "type": "image",
                    "file": f"ch{ch['number']:02d}/{fname}",
                    "caption": f"Lectura {n} — {chapter_name}",
                })
                total_readings += 1

            elif kind == "figure":
                label = item[1]
                lefts, rights = [], []
                for b in band_idx:
                    l, r = band_hbounds(arr, *bands[b])
                    lefts.append(l)
                    rights.append(r)
                x0 = max(0, min(lefts) - PAD_X)
                x1 = min(arr.shape[1] - 1, max(rights) + PAD_X)
                slug = label.lower().replace(" ", "-").replace("á", "a").replace("é", "e")
                fname = f"nota-{slug}.png"
                crop(doc, current_page, (x0, y0, x1, y1), ch_dir / fname)
                chapter_name = ch["title"].split("—", 1)[-1].strip()
                items_out.append({
                    "type": "image",
                    "file": f"ch{ch['number']:02d}/{fname}",
                    "caption": f"{label} — {chapter_name}",
                })

            else:
                raise ValueError(f"unknown item kind {kind!r}")

        manifest_chapters.append({
            "number": ch["number"],
            "title": ch["title"],
            "intro": ch["intro"],
            "items": items_out,
        })
        print(f"ch{ch['number']:02d}: {len(items_out)} items → {ch_dir}")

    manifest = {"book_title": BOOK["book_title"], "chapters": manifest_chapters}
    (out_root / "book_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n{len(manifest_chapters)} chapters, {total_readings} readings")
    print(f"manifest → {out_root / 'book_manifest.json'}")


if __name__ == "__main__":
    main()
