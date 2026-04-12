#!/usr/bin/env python3
"""
Extract a PDF book into the `book_manifest.json` shape expected by the
`import_book_chapter` Django management command (whole-book mode).

Usage (via uv so pymupdf is auto-fetched):

    uv run --no-project --with pymupdf python scripts/extract_pdf_book.py \
        --pdf-path "/path/to/book.pdf" \
        --output-dir "backups/book_extraction/<slug>"

Chapter detection (tried in order):
  1. PDF outline / bookmarks  (--chapter-pattern filters entries by regex)
  2. Text-based heuristic     (--chapter-pattern scans page text)
  3. Manual JSON               (--chapters-json overrides everything)

Manual chapters JSON format:
    [
      {"title": "Chapter 1 — Foo", "start_page": 8, "end_page": 25},
      {"title": "Chapter 2 — Bar", "start_page": 26, "end_page": 39}
    ]
Pages are 0-indexed. end_page is inclusive.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

try:
    import pymupdf  # PyMuPDF >= 1.24 uses this import
except ImportError:
    try:
        import fitz as pymupdf  # older PyMuPDF
    except ImportError:
        print(
            "ERROR: pymupdf is required. Run via:\n"
            "  uv run --no-project --with pymupdf python scripts/extract_pdf_book.py ...",
            file=sys.stderr,
        )
        sys.exit(1)


# Minimum image area (width × height) to keep. Filters out tiny symbols,
# logos, and decorative elements. Notation examples are typically 600+ px
# wide and 80+ px tall = ~48000 px². Default threshold is conservative.
DEFAULT_MIN_IMAGE_AREA = 20_000


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def dedup_consecutive_lines(text: str) -> str:
    """Remove consecutive duplicate lines from extracted PDF text.

    Many PDFs (especially those produced by certain layout engines) yield
    every line twice when extracted with PyMuPDF. This function drops a
    line if it's identical to the immediately preceding line.
    """
    lines = text.split("\n")
    deduped: list[str] = []
    prev = None
    for line in lines:
        if line == prev:
            continue
        deduped.append(line)
        prev = line
    return "\n".join(deduped)


def paragraphs_from_text(text: str) -> list[str]:
    """Split text into paragraphs (double-newline separated), stripping empties."""
    raw = dedup_consecutive_lines(text)
    parts: list[str] = []
    for chunk in raw.split("\n\n"):
        clean = chunk.strip()
        if clean:
            parts.append(clean)
    return parts


# ---------------------------------------------------------------------------
# Chapter detection
# ---------------------------------------------------------------------------


def chapters_from_outline(
    doc: pymupdf.Document,
    pattern: re.Pattern[str],
) -> list[dict] | None:
    """Try to build chapters from the PDF's outline (bookmarks).

    Returns None if the PDF has no outline or no entries match the pattern.
    """
    toc = doc.get_toc()
    if not toc:
        return None

    # toc entries: [level, title, page_number (1-indexed)]
    matched: list[tuple[str, int]] = []
    for level, title, page in toc:
        if level == 1 and pattern.search(title):
            matched.append((title, page - 1))  # convert to 0-indexed

    if not matched:
        return None

    chapters: list[dict] = []
    for idx, (title, start) in enumerate(matched):
        end = (
            matched[idx + 1][1] - 1
            if idx + 1 < len(matched)
            else len(doc) - 1
        )
        chapters.append({
            "title": title,
            "start_page": start,
            "end_page": end,
        })
    return chapters


def chapters_from_text_scan(
    doc: pymupdf.Document,
    pattern: re.Pattern[str],
    start_page: int = 0,
) -> list[dict] | None:
    """Scan page text for chapter headings using the given pattern.

    Only considers lines that are short (< 80 chars) to avoid matching
    the chapter name when it appears inside body text or a TOC listing.
    Skips pages before start_page (useful to skip front matter).

    Returns None if no pages match.
    """
    hits: list[tuple[str, int]] = []
    for pn in range(start_page, len(doc)):
        text = doc[pn].get_text()
        text_deduped = dedup_consecutive_lines(text)
        for line in text_deduped.split("\n"):
            stripped = line.strip()
            if len(stripped) > 80:
                continue  # skip body-text mentions
            m = pattern.search(stripped)
            if not m:
                continue
            # Only accept matches near the START of the line (within first
            # 5 chars) to avoid matching chapter names inside body text like
            # "(discussed in Chapter Two)".
            if m.start() > 5:
                continue
            hits.append((stripped, pn))
            break  # one match per page

    if not hits:
        return None

    chapters: list[dict] = []
    for idx, (title, start) in enumerate(hits):
        end = (
            hits[idx + 1][1] - 1
            if idx + 1 < len(hits)
            else len(doc) - 1
        )
        chapters.append({
            "title": title,
            "start_page": start,
            "end_page": end,
        })
    return chapters


def load_manual_chapters(path: Path) -> list[dict]:
    """Load chapters from a user-provided JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path}: expected a JSON list of chapter objects.")
    for i, ch in enumerate(data):
        for key in ("title", "start_page", "end_page"):
            if key not in ch:
                raise ValueError(f"{path}: chapter {i} missing '{key}'.")
    return data


# ---------------------------------------------------------------------------
# Image extraction
# ---------------------------------------------------------------------------


def extract_page_images(
    doc: pymupdf.Document,
    page_num: int,
    min_area: int,
) -> list[dict]:
    """Extract embedded images from a page that exceed the minimum area.

    Returns a list of dicts with keys: xref, width, height, ext, image_bytes.
    """
    page = doc[page_num]
    results: list[dict] = []
    seen_xrefs: set[int] = set()

    for img_tuple in page.get_images(full=True):
        xref = img_tuple[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)

        w, h = img_tuple[2], img_tuple[3]
        if w * h < min_area:
            continue

        try:
            extracted = doc.extract_image(xref)
        except Exception:
            continue
        if not extracted or not extracted.get("image"):
            continue

        results.append({
            "xref": xref,
            "width": w,
            "height": h,
            "ext": extracted.get("ext", "jpeg"),
            "image_bytes": extracted["image"],
        })
    return results


# ---------------------------------------------------------------------------
# Chapter rendering
# ---------------------------------------------------------------------------


def detect_caption(text: str) -> str:
    """Try to find a caption like 'Example 1a – ...' near an image."""
    for line in text.split("\n"):
        stripped = line.strip()
        if re.match(r"^Example\s+\d", stripped, re.I):
            return stripped
    return ""


def render_chapter(
    doc: pymupdf.Document,
    chapter: dict,
    chapter_num: int,
    out_root: Path,
    min_area: int,
) -> dict:
    """Process one chapter: extract text + images, build manifest items."""
    ch_dir_name = f"ch{chapter_num:02d}"
    ch_dir = out_root / ch_dir_name
    ch_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict] = []
    image_counter = 0
    intro_text = ""
    global_seen_xrefs: set[int] = set()

    start = chapter["start_page"]
    end = chapter["end_page"]

    for pn in range(start, end + 1):
        page = doc[pn]
        text = page.get_text()
        paras = paragraphs_from_text(text)

        # Extract images from this page (dedup across chapter)
        page_images: list[dict] = []
        for img in extract_page_images(doc, pn, min_area):
            if img["xref"] in global_seen_xrefs:
                continue
            global_seen_xrefs.add(img["xref"])
            page_images.append(img)

        # Skip the first page's first line if it matches the chapter title
        # (to avoid duplicating the title that's already in the heading)
        skip_first = pn == start

        for para in paras:
            if skip_first:
                skip_first = False
                # Check if this paragraph IS the chapter title (or close)
                if len(para) < 80:
                    continue

            if not intro_text and para:
                intro_text = para[:240]

            # Detect headings: short lines (< 60 chars), no period, UPPERCASE
            # or title-cased — common in music book section headers.
            if len(para) < 60 and not para.endswith(".") and para == para.title():
                items.append({"type": "heading", "level": 2, "text": para})
            else:
                items.append({"type": "text", "text": para})

        # Place images after this page's text
        caption_text = text  # use full page text for caption detection
        for img in page_images:
            image_counter += 1
            ext = img["ext"]
            dst_name = f"img-{image_counter:03d}.{ext}"
            dst_path = ch_dir / dst_name
            dst_path.write_bytes(img["image_bytes"])

            caption = detect_caption(caption_text)
            items.append({
                "type": "image",
                "file": f"{ch_dir_name}/{dst_name}",
                "caption": caption,
                "pixel_size": [img["width"], img["height"]],
            })

    return {
        "number": chapter_num,
        "title_detected": chapter["title"],
        "title": chapter.get("display_title", chapter["title"]),
        "intro": intro_text,
        "pdf_pages": [start, end],
        "items": items,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Extract a PDF book into book_manifest.json + images."
    )
    ap.add_argument("--pdf-path", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument(
        "--book-title",
        default=None,
        help="Override the book title (defaults to PDF metadata title or filename).",
    )
    ap.add_argument(
        "--chapter-pattern",
        default=r"(?i)chapter|capítulo|cap[ií]tulo",
        help=(
            "Regex for chapter detection. Used to filter PDF outline entries "
            "and to scan page text. Default: %(default)s"
        ),
    )
    ap.add_argument(
        "--chapters-json",
        default=None,
        type=Path,
        help=(
            "Path to a JSON file with manual chapter definitions. "
            "Overrides outline and text-based detection."
        ),
    )
    ap.add_argument(
        "--min-image-area",
        default=DEFAULT_MIN_IMAGE_AREA,
        type=int,
        help="Minimum image area (w×h pixels) to extract. Default: %(default)s",
    )
    ap.add_argument(
        "--start-page",
        default=0,
        type=int,
        help=(
            "0-indexed page to start chapter scanning from (skips front matter). "
            "Only used for text-based chapter detection. Default: %(default)s"
        ),
    )
    args = ap.parse_args()

    pdf_path: Path = args.pdf_path
    out_dir: Path = args.output_dir

    if not pdf_path.is_file():
        print(f"ERROR: PDF file not found: {pdf_path}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = re.compile(args.chapter_pattern)

    doc = pymupdf.open(str(pdf_path))
    print(f"Opened: {pdf_path} ({len(doc)} pages)")

    # --- detect chapters ---------------------------------------------------
    chapters: list[dict] | None = None

    if args.chapters_json:
        try:
            chapters = load_manual_chapters(args.chapters_json)
        except (ValueError, json.JSONDecodeError) as e:
            print(f"ERROR: {e}", file=sys.stderr)
            doc.close()
            return 1
        print(f"Loaded {len(chapters)} chapters from {args.chapters_json}")
    else:
        chapters = chapters_from_outline(doc, pattern)
        if chapters:
            print(f"Detected {len(chapters)} chapters from PDF outline")
        else:
            chapters = chapters_from_text_scan(doc, pattern, start_page=args.start_page)
            if chapters:
                print(f"Detected {len(chapters)} chapters from text scan")

    if not chapters:
        print(
            "ERROR: No chapters detected. Provide --chapters-json or adjust --chapter-pattern.",
            file=sys.stderr,
        )
        doc.close()
        return 1

    # --- render chapters ---------------------------------------------------
    rendered: list[dict] = []
    for idx, ch in enumerate(chapters, start=1):
        rendered_ch = render_chapter(doc, ch, idx, out_dir, args.min_image_area)
        img_count = sum(1 for it in rendered_ch["items"] if it["type"] == "image")
        txt_count = sum(1 for it in rendered_ch["items"] if it["type"] == "text")
        print(
            f"  Chapter {idx}: pages {ch['start_page']}-{ch['end_page']}, "
            f"{len(rendered_ch['items'])} items ({img_count} img, {txt_count} txt)"
        )
        rendered.append(rendered_ch)

    # --- cover: render first page as cover image ---------------------------
    cover_path = out_dir / "cover.jpeg"
    try:
        pix = doc[0].get_pixmap(dpi=150)
        pix.save(str(cover_path))
        print(f"Saved cover: {cover_path.name}")
    except Exception as e:
        print(f"WARN: could not render cover: {e}", file=sys.stderr)

    # --- metadata ----------------------------------------------------------
    meta = doc.metadata or {}
    if args.book_title:
        book_title = args.book_title
    elif meta.get("title") and meta.get("author"):
        book_title = f"{meta['title']} — {meta['author']}"
    elif meta.get("title"):
        book_title = meta["title"]
    else:
        book_title = pdf_path.stem

    manifest = {
        "book_title": book_title,
        "source_pdf": str(pdf_path),
        "chapters": rendered,
    }
    manifest_path = out_dir / "book_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Wrote manifest: {manifest_path}")
    print(f"Book title: {book_title}")

    doc.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
