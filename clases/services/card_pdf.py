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


def generate_cards_pdf(items, output_path=None):
    """
    Generate A4 PDF with 2 x A5 study cards per page.

    Args:
        items: List of (wagtail_image, code_str) tuples
        output_path: Optional path. If None, returns bytes.

    Returns:
        str path if output_path given, else bytes
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for i in range(0, len(items), 2):
        # Top A5 card
        _draw_card(c, items[i][0], items[i][1], y_offset=A5_HEIGHT)

        # Bottom A5 card (if exists)
        if i + 1 < len(items):
            _draw_card(c, items[i + 1][0], items[i + 1][1], y_offset=0)

        # Draw cutting line
        c.setStrokeColor(grey)
        c.setLineWidth(0.5)
        c.setDash(3, 3)
        c.line(0, A5_HEIGHT, A4_WIDTH, A5_HEIGHT)

        c.showPage()

    c.save()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(buffer.getvalue())
        return output_path
    return buffer.getvalue()


def _draw_card(c, wagtail_image, code, y_offset):
    """Draw a single A5 card on the canvas."""
    img_path = _get_image_path(wagtail_image)
    if not img_path or not os.path.exists(img_path):
        # Draw placeholder
        c.setFont("Helvetica", 14)
        c.drawCentredString(
            A4_WIDTH / 2,
            y_offset + A5_HEIGHT / 2,
            f"[Image not found: {code}]"
        )
    else:
        # Calculate image dimensions to fit within A5 with margins
        img = ImageReader(img_path)
        img_w, img_h = img.getSize()

        available_w = A4_WIDTH - 2 * MARGIN
        available_h = A5_HEIGHT - 2 * MARGIN - 10 * mm  # extra space for code

        # Scale to fit
        scale = min(available_w / img_w, available_h / img_h)
        draw_w = img_w * scale
        draw_h = img_h * scale

        # Center horizontally and vertically within A5 area
        x = (A4_WIDTH - draw_w) / 2
        y = y_offset + (A5_HEIGHT - draw_h) / 2 + 5 * mm  # slight upward offset for code space

        c.drawImage(img_path, x, y, draw_w, draw_h, preserveAspectRatio=True)

    # Draw code in bottom-right corner
    c.setFont(CODE_FONT, CODE_FONT_SIZE)
    c.setFillColor(black)
    code_x = A4_WIDTH - MARGIN - c.stringWidth(code, CODE_FONT, CODE_FONT_SIZE)
    code_y = y_offset + MARGIN / 2
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
