#!/usr/bin/env python3
"""
Extract an EPUB book into the `book_manifest.json` shape expected by the
`import_book_chapter` Django management command (whole-book mode).

Usage (via uv so bs4 is auto-fetched):

    uv run --with beautifulsoup4 python scripts/extract_epub_book.py \
        --epub-path "/path/to/book.epub" \
        --output-dir "backups/book_extraction/<slug>"

Output layout (under --output-dir):
    book_manifest.json        # chapters + items list
    cover.jpeg                # copied from EPUB if found
    ch01/img-001.jpeg         # chapter images, 1-indexed per chapter
    ch01/img-002.jpeg
    ch02/img-001.jpeg
    ...

Manifest shape (matches cms/management/commands/import_book_chapter.py):

    {
      "book_title": "...",
      "source_epub": "/path/to/book.epub",
      "chapters": [
        {
          "number": 1,
          "title_detected": "Week 1",
          "title": "Semana 1",
          "intro": "First paragraph of first day",
          "items": [
            {"type": "heading", "level": 2, "text": "Monday — Chord Vocabulary"},
            {"type": "text",    "text": "..."},
            {"type": "image",   "file": "ch01/img-001.jpeg", "caption": "..."},
            ...
          ]
        },
        ...
      ]
    }

Design notes
------------
- This extractor targets EPUBs produced by Calibre where the spine is a
  flat list of `index_split_NNN.html` files and the TOC points to one
  "chapter" per entry. It will handle any TOC where each entry delimits
  a range of spine files (chapter content = files between this entry
  and the next entry's href). In particular it was developed for
  "Ukulele Aerobics" (Hal Leonard / Chad Johnson) where each chapter
  is a "Week" and each spine file under a chapter is a single day.
- Only the stdlib + beautifulsoup4 are required.
- Other EPUB layouts (single-file-per-chapter, nested TOCs, etc.) may
  need a dedicated extractor — this script is intentionally explicit
  rather than trying to cover every shape.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import struct
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    from bs4 import BeautifulSoup
except ImportError:
    print(
        "ERROR: beautifulsoup4 is required. Run via:\n"
        "  uv run --with beautifulsoup4 python scripts/extract_epub_book.py ...",
        file=sys.stderr,
    )
    sys.exit(1)


NCX_NS = {"ncx": "http://www.daisy.org/z3986/2005/ncx/"}
OPF_NS = {
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
}


# ----------------------------------------------------------------------------
# Image dimension helpers (no PIL dependency)
# ----------------------------------------------------------------------------


def _get_image_dimensions(path: Path) -> tuple[int, int] | None:
    """Return (width, height) for JPEG/PNG without external deps. None on failure."""
    try:
        data = path.read_bytes()
    except OSError:
        return None

    # PNG: bytes 16-23 contain width (4 bytes) and height (4 bytes) in IHDR
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 24:
        w, h = struct.unpack(">II", data[16:24])
        return (w, h)

    # JPEG: scan for SOF0/SOF2 markers
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data) - 9:
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            if marker in (0xC0, 0xC2):  # SOF0 or SOF2
                h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                return (w, h)
            length = struct.unpack(">H", data[i + 2 : i + 4])[0]
            i += 2 + length
    return None


# ----------------------------------------------------------------------------
# EPUB parsing helpers
# ----------------------------------------------------------------------------


def unzip_epub(epub_path: Path) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="epub_extract_"))
    with zipfile.ZipFile(epub_path) as zf:
        zf.extractall(tmp)
    return tmp


def find_opf(root: Path) -> Path:
    container = root / "META-INF" / "container.xml"
    tree = ET.parse(container)
    ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfile = tree.getroot().find("c:rootfiles/c:rootfile", ns)
    if rootfile is None:
        raise RuntimeError(f"No rootfile in {container}")
    return root / rootfile.attrib["full-path"]


def read_metadata(opf_path: Path) -> dict:
    tree = ET.parse(opf_path)
    meta = tree.getroot().find("opf:metadata", OPF_NS)
    if meta is None:
        return {}
    out = {}
    title_el = meta.find("dc:title", OPF_NS)
    if title_el is not None and title_el.text:
        out["title"] = title_el.text.strip()
    creator_el = meta.find("dc:creator", OPF_NS)
    if creator_el is not None and creator_el.text:
        out["creator"] = creator_el.text.strip()
    return out


def read_spine(opf_path: Path) -> list[str]:
    """Return the spine as a list of idref hrefs, in order."""
    tree = ET.parse(opf_path)
    root = tree.getroot()
    manifest = root.find("opf:manifest", OPF_NS)
    spine = root.find("opf:spine", OPF_NS)
    if manifest is None or spine is None:
        raise RuntimeError(f"No manifest/spine in {opf_path}")

    id_to_href: dict[str, str] = {}
    for item in manifest.findall("opf:item", OPF_NS):
        id_to_href[item.attrib["id"]] = item.attrib["href"]

    hrefs: list[str] = []
    for itemref in spine.findall("opf:itemref", OPF_NS):
        idref = itemref.attrib["idref"]
        if idref in id_to_href:
            hrefs.append(id_to_href[idref])
    return hrefs


def read_toc(root: Path) -> list[tuple[str, str]]:
    """Return TOC as a list of (title, href) tuples in document order.

    Only flat level-1 navPoints are returned (nested navPoints are
    flattened to the top level). The href is stripped of its fragment
    identifier.
    """
    # Prefer toc.ncx (EPUB2 style) since Calibre-produced EPUBs include it.
    candidates = list(root.rglob("toc.ncx"))
    if not candidates:
        raise RuntimeError("No toc.ncx found in EPUB root")
    ncx = candidates[0]
    tree = ET.parse(ncx)
    nav_map = tree.getroot().find("ncx:navMap", NCX_NS)
    if nav_map is None:
        raise RuntimeError(f"No navMap in {ncx}")

    toc: list[tuple[str, str]] = []
    for np in nav_map.iter(f"{{{NCX_NS['ncx']}}}navPoint"):
        label_el = np.find("ncx:navLabel/ncx:text", NCX_NS)
        content_el = np.find("ncx:content", NCX_NS)
        if label_el is None or content_el is None or not label_el.text:
            continue
        href = content_el.attrib.get("src", "")
        href = href.split("#", 1)[0]
        if not href:
            continue
        toc.append((label_el.text.strip(), href))
    return toc


# ----------------------------------------------------------------------------
# Per-file HTML parsing
# ----------------------------------------------------------------------------


def _is_skip_paragraph(text: str) -> bool:
    """Return True if a paragraph should be skipped (boilerplate, empty, etc.)."""
    if not text or text.lower().startswith("tap music"):
        return True
    is_isbn_line = text.startswith("ISBN ") and len(text) < 80
    is_copyright_line = (
        "Hal Leonard" in text
        and len(text) < 80
        and ("Copyright" in text or "All Rights Reserved" in text)
    )
    return is_isbn_line or is_copyright_line


def _is_skip_image(img) -> bool:
    """Return True if an img element should be skipped (decorative icons)."""
    src = img.get("src", "")
    if not src:
        return True
    alt = (img.get("alt") or "").lower()
    if "logo" in alt or "weektxt" in alt or "hllogo" in alt:
        return True
    return False


def parse_day_file(html_path: Path) -> dict | None:
    """Extract structured content from a single day HTML file.

    Returns a dict with keys:
      - heading (str or None)
      - items: list of {"type": "text", "text": ...} or {"type": "image_src", "src": ...}
        in document order, preserving the interleaving of text and images.
    Returns None if the file has no usable content.
    """
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")

    h1 = soup.find("h1")
    heading = h1.get_text(" ", strip=True) if h1 else None

    # Walk the body in document order to preserve text/image interleaving.
    body = soup.find("body") or soup
    items: list[dict] = []
    has_image = False

    for el in body.descendants:
        if el.name == "h1":
            continue  # already captured as heading
        if el.name == "h2" or el.name == "h3" or el.name == "h4":
            text = el.get_text(" ", strip=True)
            if text:
                items.append({"type": "heading", "level": int(el.name[1]), "text": text})
        elif el.name == "p":
            text = el.get_text(" ", strip=True)
            if _is_skip_paragraph(text):
                continue
            items.append({"type": "text", "text": text})
        elif el.name == "img":
            if _is_skip_image(el):
                continue
            items.append({"type": "image_src", "src": el.get("src", "")})
            has_image = True

    if not heading and not has_image and not items:
        return None
    return {
        "heading": heading,
        "items": items,
    }


def clean_heading(raw: str) -> str:
    """Normalize a heading like 'MONDAY WEEK 1' → 'Monday'."""
    m = re.match(r"^(MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY)\b", raw, re.I)
    if m:
        return m.group(1).title()
    return raw.title()


def extract_topic(paragraph: str) -> tuple[str, str]:
    """Split 'Chord Vocabulary: ...' into ('Chord Vocabulary', '...').

    Returns ('', paragraph) if no topic prefix is found.
    """
    m = re.match(r"^([A-Z][A-Za-z /&-]{2,40}):\s*(.*)$", paragraph)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", paragraph


# ----------------------------------------------------------------------------
# Chapter building
# ----------------------------------------------------------------------------


def matches_chapter_pattern(title: str, pattern: re.Pattern[str]) -> bool:
    """Check if a TOC entry title matches the chapter detection pattern."""
    return bool(pattern.search(title.strip()))


def build_chapters(
    html_dir: Path,
    spine: list[str],
    toc: list[tuple[str, str]],
    chapter_pattern: re.Pattern[str],
) -> list[dict]:
    """Walk the spine and build chapter dicts from TOC entries matching a pattern.

    For each matching TOC entry, find its position in the spine and collect
    files up to (but not including) the next matching entry's file.
    """
    spine_basenames = [Path(h).name for h in spine]

    matched = [(t, Path(h).name) for t, h in toc if matches_chapter_pattern(t, chapter_pattern)]
    if not matched:
        raise RuntimeError(
            f"No TOC entries match pattern /{chapter_pattern.pattern}/. "
            "Adjust --chapter-pattern or check the EPUB TOC."
        )

    # Map matched file → spine index
    spine_positions: list[int] = []
    for _, basename in matched:
        try:
            pos = spine_basenames.index(basename)
        except ValueError:
            raise RuntimeError(f"TOC references {basename} but it's not in the spine")
        spine_positions.append(pos)

    chapters: list[dict] = []
    for idx, (title, _basename) in enumerate(matched):
        start = spine_positions[idx]
        end = (
            spine_positions[idx + 1]
            if idx + 1 < len(spine_positions)
            else len(spine)
        )
        chapter_files = spine_basenames[start:end]
        chapters.append(
            {
                "number": idx + 1,
                "title_raw": title,
                "files": chapter_files,
            }
        )
    return chapters


def render_chapter(
    chapter: dict,
    html_dir: Path,
    images_src_dir: Path,
    out_root: Path,
    min_image_area: int = 20000,
) -> dict:
    """Parse every HTML file in the chapter and emit manifest items.

    Copies referenced images into `chNN/img-KKK.jpeg` under out_root and
    returns a dict ready to be appended to the manifest `chapters` list.
    """
    num = chapter["number"]
    ch_dir_name = f"ch{num:02d}"
    ch_dir = out_root / ch_dir_name
    ch_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict] = []
    image_counter = 0
    intro_text = ""

    for filename in chapter["files"]:
        html_path = html_dir / filename
        if not html_path.exists():
            continue
        parsed = parse_day_file(html_path)
        if parsed is None:
            continue

        # Heading → normalized "Monday — Chord Vocabulary" if a topic is found.
        day_label = clean_heading(parsed["heading"]) if parsed["heading"] else ""

        if day_label:
            items.append({"type": "heading", "level": 2, "text": day_label})

        # Walk parsed items in document order (text, headings, and images interleaved)
        for raw_item in parsed["items"]:
            if raw_item["type"] == "text":
                text = raw_item["text"]
                if not text:
                    continue
                if not intro_text:
                    intro_text = text[:240]
                items.append({"type": "text", "text": text})
            elif raw_item["type"] == "heading":
                items.append(raw_item)
            elif raw_item["type"] == "image_src":
                src = raw_item["src"]
                image_counter += 1
                src_path = (html_path.parent / src).resolve()
                if not src_path.exists():
                    src_path = images_src_dir / Path(src).name
                if not src_path.exists():
                    print(f"  WARN: image not found: {src} (chapter {num}, file {filename})", file=sys.stderr)
                    image_counter -= 1
                    continue
                # Skip tiny decorative images (icons, bullets, checkmarks)
                dims = _get_image_dimensions(src_path)
                if dims is not None and dims[0] * dims[1] < min_image_area:
                    image_counter -= 1
                    continue
                ext = src_path.suffix.lower() or ".jpeg"
                dst_name = f"img-{image_counter:03d}{ext}"
                dst_path = ch_dir / dst_name
                shutil.copy2(src_path, dst_path)
                items.append(
                    {
                        "type": "image",
                        "file": f"{ch_dir_name}/{dst_name}",
                        "caption": day_label,
                    }
                )

    return {
        "number": num,
        "title_detected": chapter["title_raw"],
        "title": chapter["title_raw"],
        "intro": intro_text,
        "items": items,
    }


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1] if __doc__ else None)
    ap.add_argument("--epub-path", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument(
        "--book-title",
        default=None,
        help="Override the book title (defaults to EPUB dc:title + ' — ' + creator).",
    )
    ap.add_argument(
        "--min-image-area",
        type=int,
        default=20000,
        help=(
            "Minimum image area (width * height in pixels) for images to be included. "
            "Smaller images are skipped as decorative icons. Default: %(default)s."
        ),
    )
    ap.add_argument(
        "--chapter-pattern",
        default=r"(?i)^(chapter|week|capítulo)\s+\d+",
        help=(
            "Regex to filter which TOC entries become chapters. "
            "Default: %(default)s (matches 'Chapter N', 'Week N', 'Capítulo N')."
        ),
    )
    args = ap.parse_args()

    epub_path: Path = args.epub_path
    out_dir: Path = args.output_dir

    if not epub_path.is_file():
        print(f"ERROR: EPUB file not found: {epub_path}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Unzipping: {epub_path}")
    epub_root = unzip_epub(epub_path)

    try:
        try:
            opf_path = find_opf(epub_root)
            metadata = read_metadata(opf_path)
            spine = read_spine(opf_path)
            toc = read_toc(epub_root)
        except Exception as e:
            print(f"ERROR: failed to read EPUB structure: {e}", file=sys.stderr)
            return 1

        print(f"Metadata: {metadata}")
        print(f"Spine: {len(spine)} files, TOC: {len(toc)} entries")

        # Resolve the HTML directory (where spine files live) and images dir.
        html_dir = opf_path.parent
        images_src_dir = html_dir / "images"
        if not images_src_dir.is_dir():
            # Fallback: search anywhere
            found = list(epub_root.rglob("images"))
            if found:
                images_src_dir = found[0]

        # Build chapters from week TOC entries
        try:
            chapter_pattern = re.compile(args.chapter_pattern)
            raw_chapters = build_chapters(html_dir, spine, toc, chapter_pattern)
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1

        print(f"Detected {len(raw_chapters)} week chapters")

        rendered: list[dict] = []
        for ch in raw_chapters:
            rendered_ch = render_chapter(ch, html_dir, images_src_dir, out_dir, args.min_image_area)
            img_count = sum(1 for it in rendered_ch["items"] if it["type"] == "image")
            print(f"  Chapter {ch['number']}: {len(rendered_ch['items'])} items, {img_count} images")
            rendered.append(rendered_ch)

        # Copy cover image if present at the EPUB root or html_dir
        for cover_candidate in (
            html_dir / "cover.jpeg",
            html_dir / "cover.jpg",
            html_dir / "cover.png",
            images_src_dir / "cover.jpeg",
            images_src_dir / "cover.jpg",
            images_src_dir / "cover.png",
            epub_root / "cover.jpeg",
            epub_root / "cover.jpg",
            epub_root / "cover.png",
        ):
            if cover_candidate.is_file():
                shutil.copy2(cover_candidate, out_dir / f"cover{cover_candidate.suffix}")
                print(f"Copied cover: {cover_candidate.name}")
                break

        # Build final manifest
        if args.book_title:
            book_title = args.book_title
        elif metadata.get("title") and metadata.get("creator"):
            book_title = f"{metadata['title']} — {metadata['creator']}"
        else:
            book_title = metadata.get("title", epub_path.stem)

        manifest = {
            "book_title": book_title,
            "source_epub": str(epub_path),
            "chapters": rendered,
        }
        manifest_path = out_dir / "book_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Wrote manifest: {manifest_path}")
        print(f"Book title: {book_title}")
        return 0
    finally:
        # Always clean up the temp unzip directory, even on exceptions.
        shutil.rmtree(epub_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
