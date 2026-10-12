import io
import csv
import json
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Canvas for adding page numbers and running footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Footer text
        footer_text = f"AI-Powered Syllabus Textbook Finder — Page {self._pageNumber} of {page_count}"
        self.drawString(36, 20, footer_text)
        
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.drawRightString(756, 20, f"Generated: {timestamp}")
        self.restoreState()

def generate_excel_report(syllabus_name: str, books_data: List[Dict[str, Any]]) -> bytes:
    """
    Generate professional Excel workbook with openpyxl:
    - Title banner and summary section
    - Styled column headers (#1E3A8A)
    - Auto-filters
    - Frozen panes
    - Text wrap and styled borders
    - Conditional color badges
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Book Access Audit"
    ws.views.sheetView[0].showGridLines = True

    # Colors
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    summary_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    white_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=16, bold=True, color="1E3A8A")
    subtitle_font = Font(name="Calibri", size=10, italic=True, color="475569")
    bold_font = Font(name="Calibri", size=10, bold=True, color="0F172A")
    regular_font = Font(name="Calibri", size=10, color="1E293B")
    link_font = Font(name="Calibri", size=10, color="2563EB", underline="single")

    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # 1. Title Block
    ws.merge_cells("A1:N1")
    ws["A1"] = "AI-Powered Syllabus Textbook & Reference Book Finder"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:N2")
    now_str = datetime.datetime.now().strftime("%B %d, %Y at %I:%M %p")
    ws["A2"] = f"Academic Audit Report • Syllabus: {syllabus_name} • Generated: {now_str}"
    ws["A2"].font = subtitle_font
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 18

    # 2. Summary KPI Block (Rows 4-5)
    total_books = len(books_data)
    textbooks = sum(1 for b in books_data if b.get("category") == "Textbook")
    ref_books = sum(1 for b in books_data if b.get("category") == "Reference Book")
    open_access = sum(1 for b in books_data if "open-access" in (b.get("access_type") or "").lower() or "public-domain" in (b.get("access_type") or "").lower())
    preview_borrow = sum(1 for b in books_data if "preview" in (b.get("access_type") or "").lower() or "borrowing" in (b.get("access_type") or "").lower())
    no_access = sum(1 for b in books_data if "no verified" in (b.get("access_type") or "").lower())

    summary_headers = ["Total Books Extracted", "Textbooks", "Reference Books", "Open Access / Public Domain", "Preview / Borrowing", "No Access Found"]
    summary_values = [total_books, textbooks, ref_books, open_access, preview_borrow, no_access]

    for col_idx, (sh, sv) in enumerate(zip(summary_headers, summary_values), start=1):
        col_letter = get_column_letter(col_idx * 2 - 1)
        next_col_letter = get_column_letter(col_idx * 2)
        merge_range_h = f"{col_letter}4:{next_col_letter}4"
        merge_range_v = f"{col_letter}5:{next_col_letter}5"
        ws.merge_cells(merge_range_h)
        ws.merge_cells(merge_range_v)
        
        ws[f"{col_letter}4"] = sh
        ws[f"{col_letter}4"].font = Font(name="Calibri", size=9, bold=True, color="475569")
        ws[f"{col_letter}4"].fill = summary_fill
        ws[f"{col_letter}4"].alignment = Alignment(horizontal="center", vertical="center")
        
        ws[f"{col_letter}5"] = sv
        ws[f"{col_letter}5"].font = Font(name="Calibri", size=13, bold=True, color="1E3A8A")
        ws[f"{col_letter}5"].fill = summary_fill
        ws[f"{col_letter}5"].alignment = Alignment(horizontal="center", vertical="center")

    ws.row_dimensions[4].height = 18
    ws.row_dimensions[5].height = 22

    # 3. Data Table Headers (Row 7)
    headers = [
        "S.No.", "Category", "Book Title", "Authors", "Edition", "Publisher",
        "Publication Year", "ISBN", "Source", "Access Type", "Access URL",
        "Match Confidence", "Verification Status", "Remarks"
    ]

    header_row = 7
    ws.row_dimensions[header_row].height = 26
    for col_num, h_text in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col_num)
        cell.value = h_text
        cell.font = white_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # 4. Data Rows
    current_row = 8
    for idx, b in enumerate(books_data, 1):
        ws.row_dimensions[current_row].height = 32

        row_vals = [
            idx,
            b.get("category", "Textbook"),
            b.get("title", ""),
            b.get("authors", ""),
            b.get("edition", "") or "—",
            b.get("publisher", "") or "—",
            b.get("publication_year", "") or "—",
            b.get("isbn", "") or "—",
            b.get("source", "") or "—",
            b.get("access_type", "No verified access found"),
            b.get("access_url", "") or "—",
            f"{b.get('confidence_score', 0):.1f}%" if b.get('confidence_score') is not None else "0.0%",
            b.get("verification_status", "Unverified"),
            b.get("remarks", "") or ""
        ]

        for col_num, val in enumerate(row_vals, 1):
            cell = ws.cell(row=current_row, column=col_num)
            cell.value = val
            cell.font = regular_font
            cell.border = thin_border
            
            # Alignments
            if col_num in (1, 5, 7, 8, 12):
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            elif col_num in (2, 9, 10, 13):
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            elif col_num == 11 and val.startswith("http"):
                cell.hyperlink = val
                cell.font = link_font
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

            # Soft color highlights on Access Type (col 10)
            if col_num == 10:
                acc = str(val).lower()
                if "open-access" in acc or "public-domain" in acc:
                    cell.fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid") # Soft green
                    cell.font = Font(name="Calibri", size=10, bold=True, color="166534")
                elif "borrowing" in acc or "preview" in acc:
                    cell.fill = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid") # Soft blue
                    cell.font = Font(name="Calibri", size=10, bold=True, color="1E40AF")
                elif "catalogue" in acc or "publisher" in acc:
                    cell.fill = PatternFill(start_color="FFEDD5", end_color="FFEDD5", fill_type="solid") # Soft orange
                    cell.font = Font(name="Calibri", size=10, bold=True, color="9A3412")
                elif "no verified" in acc:
                    cell.fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid") # Soft red
                    cell.font = Font(name="Calibri", size=10, bold=True, color="991B1B")

        current_row += 1

    # Freeze header row at Row 8
    ws.freeze_panes = "A8"

    # Enable Excel Auto-Filter on data range
    last_row = max(8, current_row - 1)
    ws.auto_filter.ref = f"A7:N{last_row}"

    # Auto-adjust column widths
    column_widths = {
        "A": 7,   # S.No.
        "B": 16,  # Category
        "C": 34,  # Title
        "D": 26,  # Authors
        "E": 14,  # Edition
        "F": 22,  # Publisher
        "G": 14,  # Year
        "H": 18,  # ISBN
        "I": 18,  # Source
        "J": 26,  # Access Type
        "K": 32,  # Access URL
        "L": 16,  # Match Confidence
        "M": 20,  # Verification Status
        "N": 38   # Remarks
    }
    for col_letter, width in column_widths.items():
        ws.column_dimensions[col_letter].width = width

    # Save to buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()

def generate_pdf_report(syllabus_name: str, books_data: List[Dict[str, Any]]) -> bytes:
    """
    Generate professional academic PDF report using ReportLab with:
    - Academic styled header & metadata
    - KPI Metrics Summary
    - Formatted tabular records
    - Running footer with page numbers
    """
    buffer = io.BytesIO()
    # Use landscape letter for wide academic tabular data
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AcademicTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1E3A8A")
    )
    subtitle_style = ParagraphStyle(
        "AcademicSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#475569")
    )
    cell_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#1E293B")
    )
    cell_bold_style = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0F172A")
    )
    badge_green = ParagraphStyle(
        "BadgeGreen",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#15803D")
    )
    badge_blue = ParagraphStyle(
        "BadgeBlue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#1D4ED8")
    )
    badge_orange = ParagraphStyle(
        "BadgeOrange",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#C2410C")
    )
    badge_red = ParagraphStyle(
        "BadgeRed",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor("#B91C1C")
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("AI-Powered Syllabus Textbook & Reference Book Finder", title_style))
    now_str = datetime.datetime.now().strftime("%B %d, %Y • %I:%M %p")
    story.append(Paragraph(f"Academic Book Verification & Lawful Access Report | Syllabus: <b>{syllabus_name}</b> | Generated: {now_str}", subtitle_style))
    story.append(Spacer(1, 14))

    # Summary Metrics
    total = len(books_data)
    tb_count = sum(1 for b in books_data if b.get("category") == "Textbook")
    rb_count = sum(1 for b in books_data if b.get("category") == "Reference Book")
    oa_count = sum(1 for b in books_data if "open-access" in (b.get("access_type") or "").lower() or "public-domain" in (b.get("access_type") or "").lower())
    pb_count = sum(1 for b in books_data if "preview" in (b.get("access_type") or "").lower() or "borrowing" in (b.get("access_type") or "").lower())

    summary_data = [
        [
            Paragraph("<b>Total Books</b>", cell_bold_style),
            Paragraph("<b>Textbooks</b>", cell_bold_style),
            Paragraph("<b>Reference Books</b>", cell_bold_style),
            Paragraph("<b>Open Access / Public Domain</b>", cell_bold_style),
            Paragraph("<b>Preview / Lending</b>", cell_bold_style)
        ],
        [
            Paragraph(f"<font size=12 color='#1E3A8A'><b>{total}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#1E3A8A'><b>{tb_count}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#1E3A8A'><b>{rb_count}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#166534'><b>{oa_count}</b></font>", cell_style),
            Paragraph(f"<font size=12 color='#1E40AF'><b>{pb_count}</b></font>", cell_style)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[140, 140, 140, 160, 140])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 14))

    # Books Table
    table_headers = ["#", "Category", "Book Title & Authors", "Edition / Pub / Year", "ISBN", "Source & Access Tier", "Confidence", "Access Link"]
    col_widths = [24, 75, 215, 120, 75, 120, 50, 60]

    rows = []
    # Header row
    header_row = [Paragraph(f"<b><font color='white'>{h}</font></b>", cell_bold_style) for h in table_headers]
    rows.append(header_row)

    for idx, b in enumerate(books_data, 1):
        cat = b.get("category", "Textbook")
        title_authors = f"<b>{b.get('title', '')}</b>"
        if b.get("authors"):
            title_authors += f"<br/><font color='#475569'>by {b.get('authors')}</font>"

        pub_parts = []
        if b.get("edition"):
            pub_parts.append(str(b.get("edition")))
        if b.get("publisher"):
            pub_parts.append(str(b.get("publisher")))
        if b.get("publication_year"):
            pub_parts.append(str(b.get("publication_year")))
        pub_info = ", ".join(pub_parts) if pub_parts else "—"

        isbn_val = b.get("isbn") or "—"
        
        # Access badge styling
        acc_type = b.get("access_type", "No verified access found")
        acc_lower = acc_type.lower()
        if "open-access" in acc_lower or "public-domain" in acc_lower:
            badge_p = Paragraph(f"<b>{b.get('source', '')}</b><br/>{acc_type}", badge_green)
        elif "borrowing" in acc_lower or "preview" in acc_lower:
            badge_p = Paragraph(f"<b>{b.get('source', '')}</b><br/>{acc_type}", badge_blue)
        elif "catalogue" in acc_lower or "publisher" in acc_lower:
            badge_p = Paragraph(f"<b>{b.get('source', '')}</b><br/>{acc_type}", badge_orange)
        else:
            badge_p = Paragraph(f"<b>{b.get('source', 'None')}</b><br/>{acc_type}", badge_red)

        conf_val = f"{b.get('confidence_score', 0):.0f}%" if b.get('confidence_score') is not None else "0%"
        
        access_url = b.get("access_url")
        if access_url and str(access_url).startswith("http"):
            link_p = Paragraph(f'<a href="{access_url}" color="#2563EB"><u>Access Link</u></a>', cell_style)
        else:
            link_p = Paragraph("—", cell_style)

        rows.append([
            Paragraph(str(idx), cell_style),
            Paragraph(cat, cell_bold_style),
            Paragraph(title_authors, cell_style),
            Paragraph(pub_info, cell_style),
            Paragraph(isbn_val, cell_style),
            badge_p,
            Paragraph(conf_val, cell_bold_style),
            link_p
        ])

    data_table = Table(rows, colWidths=col_widths, repeatRows=1)
    data_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
    ]))

    story.append(data_table)
    doc.build(story, canvasmaker=NumberedCanvas)
    
    buffer.seek(0)
    return buffer.read()

def generate_csv_report(books_data: List[Dict[str, Any]]) -> str:
    """Generate RFC 4180 compliant CSV export with UTF-8 BOM."""
    output = io.StringIO()
    # Write UTF-8 BOM for Excel
    output.write('\ufeff')
    writer = csv.writer(output)
    
    headers = [
        "S.No.", "Category", "Book Title", "Authors", "Edition", "Publisher",
        "Publication Year", "ISBN", "Source", "Access Type", "Access URL",
        "Match Confidence", "Verification Status", "Remarks"
    ]
    writer.writerow(headers)

    for idx, b in enumerate(books_data, 1):
        writer.writerow([
            idx,
            b.get("category", "Textbook"),
            b.get("title", ""),
            b.get("authors", ""),
            b.get("edition", ""),
            b.get("publisher", ""),
            b.get("publication_year", ""),
            b.get("isbn", ""),
            b.get("source", ""),
            b.get("access_type", "No verified access found"),
            b.get("access_url", ""),
            f"{b.get('confidence_score', 0):.1f}%" if b.get('confidence_score') is not None else "0.0%",
            b.get("verification_status", "Unverified"),
            b.get("remarks", "")
        ])

    return output.getvalue()

def generate_json_report(syllabus_name: str, books_data: List[Dict[str, Any]]) -> str:
    """Generate structured JSON report with metadata and records."""
    report = {
        "metadata": {
            "application": "AI-Powered Syllabus Textbook and Reference Book Finder",
            "syllabus_name": syllabus_name,
            "generated_at": datetime.datetime.utcnow().isoformat(),
            "total_records": len(books_data)
        },
        "books": books_data
    }
    return json.dumps(report, indent=2, ensure_ascii=False)
