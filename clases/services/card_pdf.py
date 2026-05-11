"""
Study Card PDF generators using ReportLab.

- generate_cards_pdf: A4 pages with 2 x A5 cards per page
- generate_registration_sheet: A4 table with student names and date columns
"""
import io
import os

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import black, grey
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# A4 dimensions
A4_WIDTH, A4_HEIGHT = A4
# A5 = half of A4
A5_HEIGHT = A4_HEIGHT / 2

# Margins
MARGIN = 15 * mm
CUT_MARGIN = 10 * mm  # min distance from content to cutting line
CODE_FONT_SIZE = 8
CODE_FONT = "Courier"
LABEL_FONT_SIZE = 7
LABEL_FONT = "Helvetica"


def _get_image_path(wagtail_image, max_width=800):
    """
    Get filesystem path for a Wagtail image.
    Uses rendition API for reasonable print resolution.
    """
    try:
        rendition = wagtail_image.get_rendition(f"width-{max_width}")
        return rendition.file.path
    except Exception:
        # Fallback to original file
        try:
            return wagtail_image.file.path
        except Exception:
            return None


def _get_scaled_height(wagtail_image):
    """Get the height an image would occupy when scaled to fit the available width."""
    img_path = _get_image_path(wagtail_image)
    if not img_path or not os.path.exists(img_path):
        return A5_HEIGHT  # Treat missing images as tall (single-slot)
    img = ImageReader(img_path)
    img_w, img_h = img.getSize()
    available_w = A4_WIDTH - 2 * MARGIN
    scale = available_w / img_w
    return img_h * scale


def _build_slots(items):
    """
    Pack items into A5 slots. Each slot is a list of 1 or 2 (image, code) tuples.

    If two consecutive images are short enough to stack within one A5 half
    (with margins and codes), they share a slot. Otherwise, one image per slot.
    """
    # Max height available in a single-image A5 slot
    single_slot_h = A5_HEIGHT - 2 * MARGIN - 10 * mm
    # When stacking 2 images, allow generous pairing for landscape images.
    # Images will be height-constrained in rendering (scaled down) but remain
    # legible — e.g. a 2:1 image renders at ~100mm wide on a 180mm card.
    double_slot_h = A5_HEIGHT * 0.7

    slots = []
    i = 0
    while i < len(items):
        h1 = _get_scaled_height(items[i][0])
        # Try pairing with next item
        if i + 1 < len(items):
            h2 = _get_scaled_height(items[i + 1][0])
            if h1 <= double_slot_h and h2 <= double_slot_h:
                # Both fit stacked — pack into one slot
                slots.append([items[i], items[i + 1]])
                i += 2
                continue
        # Single image in this slot
        slots.append([items[i]])
        i += 1
    return slots


def _build_a4_pages(items):
    """
    Pack items into full A4 pages. Each page is a list of (image, code, desc) tuples.

    Greedy bin-packing: keep adding images to the current page while total
    scaled height fits within the available A4 space. Short images share a page;
    tall images get their own page.
    """
    code_space = 12 * mm
    page_available_h = A4_HEIGHT - 2 * MARGIN
    gap = 5 * mm  # vertical gap between images on same page

    pages = []
    current_page = []
    current_h = 0

    for item in items:
        img = item[0]
        img_path = _get_image_path(img)
        if img_path and os.path.exists(img_path):
            reader = ImageReader(img_path)
            img_w, img_h = reader.getSize()
            is_tall = img_h > img_w * 1.2
            available_w = A4_WIDTH - 2 * MARGIN
            if is_tall:
                scale = min(available_w / img_h, (page_available_h - code_space) / img_w)
                scaled_h = img_w * scale
            else:
                scale = min(available_w / img_w, (page_available_h - code_space) / img_h)
                scaled_h = img_h * scale
        else:
            scaled_h = page_available_h  # missing image = full page

        needed_h = scaled_h + code_space
        if current_page:
            needed_h += gap  # gap before this image

        if current_page and current_h + needed_h > page_available_h:
            # Start new page
            pages.append(current_page)
            current_page = [item]
            current_h = scaled_h + code_space
        else:
            current_page.append(item)
            current_h += (gap if len(current_page) > 1 else 0) + scaled_h + code_space

    if current_page:
        pages.append(current_page)

    return pages


def generate_cards_pdf(items, output_path=None, fill_items=None, duplicate=False,
                       page_format="a5"):
    """
    Generate study card PDF.

    page_format="a5": A4 pages with 2 x A5 cards, dashed cutting line, duplex interleaved.
    page_format="a4": Full A4 pages, smart packing (short images share pages),
                      no cutting line, sequential duplex (print double-sided).

    Smart packing: if two consecutive images are short, they share one half/page
    (each with its own code).

    Args:
        items: List of (wagtail_image, code_str) or (wagtail_image, code_str, desc) tuples
        output_path: Optional path. If None, returns bytes.
        fill_items: Optional list of extra tuples to fill blank spaces.
        duplicate: If True (A5 only), each image printed twice on same A4.
        page_format: "a5" (default, half-page cards) or "a4" (full-page cards).

    Returns:
        str path if output_path given, else bytes
    """
    if page_format == "a4":
        return _generate_a4_pdf(items, output_path)

    slots = _build_slots(items)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    if duplicate:
        # Duplicate mode: each slot drawn on top AND bottom of the same A4 page
        for slot in slots:
            _draw_slot(c, slot, y_offset=A5_HEIGHT)
            _draw_slot(c, slot, y_offset=0)
            _draw_cutting_line(c)
            c.showPage()
    else:
        # Fill empty A5 halves so no page is left blank
        remainder = len(slots) % 4
        if remainder != 0 and fill_items:
            needed = 4 - remainder
            fill_slots = _build_slots(fill_items)
            slots.extend(fill_slots[:needed])

        # Process in groups of 4 slots (2 A5 halves per sheet, front+back = 4 slots)
        for i in range(0, len(slots), 4):
            group = slots[i:i + 4]

            # Front page: slots 1 and 3
            _draw_slot(c, group[0], y_offset=A5_HEIGHT)
            if len(group) > 2:
                _draw_slot(c, group[2], y_offset=0)

            _draw_cutting_line(c)
            c.showPage()

            # Back page: slots 2 and 4
            if len(group) > 1:
                _draw_slot(c, group[1], y_offset=A5_HEIGHT)
            if len(group) > 3:
                _draw_slot(c, group[3], y_offset=0)

            _draw_cutting_line(c)
            c.showPage()

    c.save()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())
        return output_path
    return buffer.getvalue()


def _generate_a4_pdf(items, output_path=None):
    """
    Generate full A4 PDF with smart packing. No cutting lines.

    Short images are packed onto shared pages; tall images get a full page.
    Pages are sequential — print double-sided for duplex.
    """
    pages = _build_a4_pages(items)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for page_items in pages:
        _draw_a4_page(c, page_items)
        c.showPage()

    c.save()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())
        return output_path
    return buffer.getvalue()


def _draw_a4_page(c, page_items):
    """Draw one A4 page with one or more images packed vertically."""
    def _unpack(item):
        if len(item) >= 3:
            return item[0], item[1], item[2]
        return item[0], item[1], ""

    code_space = 12 * mm
    gap = 5 * mm
    page_available_h = A4_HEIGHT - 2 * MARGIN

    # Calculate total scaled heights to distribute space
    heights = []
    for item in page_items:
        img = item[0]
        img_path = _get_image_path(img)
        if img_path and os.path.exists(img_path):
            reader = ImageReader(img_path)
            img_w, img_h = reader.getSize()
            available_w = A4_WIDTH - 2 * MARGIN
            is_tall = img_h > img_w * 1.2
            if is_tall:
                scale = min(available_w / img_h, (page_available_h - code_space) / img_w)
                scaled_h = img_w * scale
            else:
                scale = min(available_w / img_w, (page_available_h - code_space) / img_h)
                scaled_h = img_h * scale
            heights.append(scaled_h)
        else:
            heights.append(page_available_h - code_space)

    n = len(page_items)
    total_code_space = n * code_space
    total_gaps = max(0, n - 1) * gap
    total_img_h = sum(heights)
    total_needed = total_img_h + total_code_space + total_gaps

    # If total exceeds available, scale down proportionally
    if total_needed > page_available_h:
        shrink = (page_available_h - total_code_space - total_gaps) / total_img_h
        heights = [h * shrink for h in heights]

    # Draw from top to bottom
    y_cursor = A4_HEIGHT - MARGIN

    for idx, item in enumerate(page_items):
        img, code, desc = _unpack(item)
        zone_h = heights[idx] + code_space
        y_offset = y_cursor - zone_h
        _draw_single_image(c, img, code, y_offset, zone_h, desc)
        y_cursor = y_offset - (gap if idx < n - 1 else 0)


def _draw_cutting_line(c):
    """Draw a dashed cutting line at the A5 midpoint."""
    c.setStrokeColor(grey)
    c.setLineWidth(0.5)
    c.setDash(3, 3)
    c.line(0, A5_HEIGHT, A4_WIDTH, A5_HEIGHT)


def _draw_slot(c, slot_items, y_offset):
    """
    Draw one A5 slot (1 or 2 images stacked) starting at y_offset.

    Single image: centered in the A5 half with code in bottom-right.
    Two images: stacked vertically, each with its own code below it.

    Each item is a tuple of (image, code) or (image, code, description).
    """
    def _unpack(item):
        """Unpack (image, code) or (image, code, description) tuples."""
        if len(item) >= 3:
            return item[0], item[1], item[2]
        return item[0], item[1], ""

    if len(slot_items) == 1:
        img, code, desc = _unpack(slot_items[0])
        _draw_single_image(c, img, code, y_offset, A5_HEIGHT, desc)
    else:
        # Two images stacked — split A5 half into two sub-zones
        sub_h = A5_HEIGHT / 2
        img1, code1, desc1 = _unpack(slot_items[0])
        img2, code2, desc2 = _unpack(slot_items[1])
        _draw_single_image(c, img1, code1, y_offset + sub_h, sub_h, desc1)
        _draw_single_image(c, img2, code2, y_offset, sub_h, desc2)


def _draw_single_image(c, wagtail_image, code, y_offset, zone_height, description=""):
    """Draw one image with its code (and optional description) within a vertical zone.

    Tall images (height > width * 1.2) are rotated 90° counter-clockwise
    so they fill the A5 card when held vertically after cutting.
    """
    img_path = _get_image_path(wagtail_image)
    if not img_path or not os.path.exists(img_path):
        c.setFont("Helvetica", 10)
        c.drawCentredString(
            A4_WIDTH / 2,
            y_offset + zone_height / 2,
            f"[Image not found: {code}]"
        )
    else:
        img = ImageReader(img_path)
        img_w, img_h = img.getSize()

        available_w = A4_WIDTH - 2 * MARGIN
        code_space = 12 * mm  # space reserved for code + description at bottom
        available_h = zone_height - MARGIN - code_space

        is_tall = img_h > img_w * 1.2

        if is_tall:
            # Rotate 90° CCW: image height becomes horizontal, width becomes vertical
            scale = min(available_w / img_h, available_h / img_w)
            draw_w = img_w * scale  # vertical extent after rotation
            draw_h = img_h * scale  # horizontal extent after rotation

            # Center of available zone
            cx = A4_WIDTH / 2
            cy = y_offset + code_space + available_h / 2

            c.saveState()
            c.translate(cx, cy)
            c.rotate(90)
            # In rotated coordinate system, draw centered at origin
            c.drawImage(img_path, -draw_w / 2, -draw_h / 2, draw_w, draw_h,
                        preserveAspectRatio=True, mask='auto')
            c.restoreState()
        else:
            scale = min(available_w / img_w, available_h / img_h)
            draw_w = img_w * scale
            draw_h = img_h * scale

            x = (A4_WIDTH - draw_w) / 2
            y = y_offset + code_space + (available_h - draw_h) / 2

            c.drawImage(img_path, x, y, draw_w, draw_h, preserveAspectRatio=True, mask='auto')

    # Code (+ optional description) in bottom-right of zone
    # CUT_MARGIN ensures enough distance from cutting line for safe trimming
    c.setFillColor(black)
    label = f"{code} · {description}" if description else code
    c.setFont(CODE_FONT, CODE_FONT_SIZE)
    label_w = c.stringWidth(label, CODE_FONT, CODE_FONT_SIZE)
    code_x = A4_WIDTH - MARGIN - label_w
    code_y = y_offset + CUT_MARGIN
    c.drawString(code_x, code_y, label)


def generate_registration_sheet(student_names, title="Hoja de Registro", num_date_columns=8, output_path=None):
    """
    Generate A4 PDF registration sheet with student names and date columns.

    Args:
        student_names: List of student name strings
        title: Sheet title
        num_date_columns: Number of empty date columns
        output_path: Optional path. If None, returns bytes.

    Returns:
        str path if output_path given, else bytes
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(A4_HEIGHT, A4_WIDTH))  # Landscape

    page_w, page_h = A4_HEIGHT, A4_WIDTH  # Landscape dimensions

    # Title
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(page_w / 2, page_h - 20 * mm, title)

    # Table setup
    table_top = page_h - 30 * mm
    row_height = 8 * mm
    name_col_width = 50 * mm
    date_col_width = (page_w - name_col_width - 2 * MARGIN) / num_date_columns

    # Header row
    x_start = MARGIN
    c.setFont("Helvetica-Bold", 8)
    c.drawString(x_start + 2 * mm, table_top - row_height + 2 * mm, "Alumno/a")

    for col in range(num_date_columns):
        x = x_start + name_col_width + col * date_col_width
        c.drawCentredString(x + date_col_width / 2, table_top - row_height + 2 * mm, f"Fecha {col + 1}")

    # Draw header line
    c.setStrokeColor(black)
    c.setLineWidth(1)
    c.line(x_start, table_top, x_start + name_col_width + num_date_columns * date_col_width, table_top)
    c.line(x_start, table_top - row_height, x_start + name_col_width + num_date_columns * date_col_width, table_top - row_height)

    # Student rows
    c.setFont("Helvetica", 7)
    max_rows_per_page = int((table_top - row_height - MARGIN) / row_height)

    for row_idx, name in enumerate(student_names):
        # Check if we need a new page
        page_row = row_idx % max_rows_per_page
        if row_idx > 0 and page_row == 0:
            c.showPage()
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(page_w / 2, page_h - 20 * mm, title)
            c.setFont("Helvetica", 7)

        y = table_top - (page_row + 2) * row_height

        # Student name
        c.drawString(x_start + 2 * mm, y + 2 * mm, name)

        # Grid lines
        c.setStrokeColor(grey)
        c.setLineWidth(0.3)
        c.line(x_start, y, x_start + name_col_width + num_date_columns * date_col_width, y)

        # Vertical lines
        c.line(x_start + name_col_width, y, x_start + name_col_width, y + row_height)
        for col in range(num_date_columns):
            x = x_start + name_col_width + (col + 1) * date_col_width
            c.line(x, y, x, y + row_height)

    # Bottom line of last row
    last_y = table_top - (min(len(student_names), max_rows_per_page) + 1) * row_height
    c.line(x_start, last_y, x_start + name_col_width + num_date_columns * date_col_width, last_y)

    # Left border
    c.line(x_start, table_top, x_start, last_y)
    # Right border
    c.line(x_start + name_col_width + num_date_columns * date_col_width, table_top,
           x_start + name_col_width + num_date_columns * date_col_width, last_y)

    c.save()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())
        return output_path
    return buffer.getvalue()
