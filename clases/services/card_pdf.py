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
CODE_FONT_SIZE = 8
CODE_FONT = "Courier"


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
    # When stacking 2 images, each gets half the space minus gap for code between them
    double_slot_h = (A5_HEIGHT - 2 * MARGIN - 20 * mm) / 2  # half-slot per image

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


def generate_cards_pdf(items, output_path=None):
    """
    Generate A4 PDF with 2 x A5 study cards per page, laid out for duplex printing.

    Smart packing: if two consecutive images are short, they share one A5 half
    (each with its own code). A student cutting one A5 gets 2 or 4 correlative
    images depending on their height.

    Duplex layout ("flip on short edge") works on SLOTS (1 or 2 images each):
      Page 1 (front): top=slot1, bottom=slot3
      Page 2 (back):  top=slot2, bottom=slot4

    When cut in half, each A5 piece has correlative content (front/back):
      Top half  → front=slot1, back=slot2
      Bottom half → front=slot3, back=slot4

    Args:
        items: List of (wagtail_image, code_str) tuples
        output_path: Optional path. If None, returns bytes.

    Returns:
        str path if output_path given, else bytes
    """
    slots = _build_slots(items)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

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
    """
    if len(slot_items) == 1:
        _draw_single_image(c, slot_items[0][0], slot_items[0][1], y_offset, A5_HEIGHT)
    else:
        # Two images stacked — split A5 half into two sub-zones
        sub_h = A5_HEIGHT / 2
        # Top sub-zone: first image
        _draw_single_image(c, slot_items[0][0], slot_items[0][1], y_offset + sub_h, sub_h)
        # Bottom sub-zone: second image
        _draw_single_image(c, slot_items[1][0], slot_items[1][1], y_offset, sub_h)


def _draw_single_image(c, wagtail_image, code, y_offset, zone_height):
    """Draw one image with its code within a vertical zone."""
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
        code_space = 8 * mm
        available_h = zone_height - MARGIN - code_space

        scale = min(available_w / img_w, available_h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale

        x = (A4_WIDTH - draw_w) / 2
        y = y_offset + code_space + (available_h - draw_h) / 2

        c.drawImage(img_path, x, y, draw_w, draw_h, preserveAspectRatio=True)

    # Code in bottom-right of this zone
    c.setFont(CODE_FONT, CODE_FONT_SIZE)
    c.setFillColor(black)
    code_x = A4_WIDTH - MARGIN - c.stringWidth(code, CODE_FONT, CODE_FONT_SIZE)
    code_y = y_offset + 2 * mm
    c.drawString(code_x, code_y, code)


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
