import os
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

from app.config import settings

def set_cell_background(cell, fill_hex: str):
    """Set background color of a table cell (e.g. '1E3A8A' or 'F1F5F9')."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set inner padding for table cell in twips."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tcPr.append(tcMar)

def create_default_template_file(output_path: Path) -> Path:
    """Generate a clean, standard institution question paper Word template."""
    doc = docx.Document()

    # Set 0.75 inch margins
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(0.75)
        s.bottom_margin = Inches(0.75)
        s.left_margin = Inches(0.75)
        s.right_margin = Inches(0.75)

    # University / Institution Header
    p_inst = doc.add_paragraph()
    p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_inst = p_inst.add_run("{{INSTITUTION_NAME}}")
    r_inst.bold = True
    r_inst.font.size = Pt(16)
    r_inst.font.color.rgb = RGBColor(30, 58, 138)

    p_dept = doc.add_paragraph()
    p_dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_dept = p_dept.add_run("DEPARTMENT OF {{DEPARTMENT}}\n{{EXAM_NAME}}")
    r_dept.bold = True
    r_dept.font.size = Pt(12)

    # Metadata Table
    meta_table = doc.add_table(rows=3, cols=4)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        [("Course Name:", True), ("{{COURSE_NAME}}", False), ("Course Code:", True), ("{{COURSE_CODE}}", False)],
        [("Semester / Year:", True), ("{{SEMESTER}} / {{ACADEMIC_YEAR}}", False), ("Date & Session:", True), ("{{DATE}}", False)],
        [("Duration:", True), ("{{DURATION}}", False), ("Max. Marks:", True), ("{{MAX_MARKS}}", False)]
    ]
    for row_idx, row in enumerate(meta_table.rows):
        for col_idx, cell in enumerate(row.cells):
            text, is_bold = meta_data[row_idx][col_idx]
            cell.text = text
            if is_bold:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.bold = True
            set_cell_background(cell, "F8FAFC" if is_bold else "FFFFFF")

    # Instructions
    doc.add_paragraph()
    p_inst = doc.add_paragraph()
    r_i_title = p_inst.add_run("Instructions: ")
    r_i_title.bold = True
    p_inst.add_run("{{INSTRUCTIONS}}")

    # Questions section marker
    p_sec = doc.add_paragraph()
    p_sec.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sec.add_run("{{QUESTIONS_TABLE}}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    return output_path

def replace_text_in_paragraph(paragraph, replacements: Dict[str, str]):
    """Safely replace text placeholders inside paragraph runs."""
    for key, val in replacements.items():
        if key in paragraph.text:
            # If replacement key is entirely contained in one run or split
            combined_text = paragraph.text.replace(key, str(val))
            # Clear runs and insert replaced text
            for i in range(len(paragraph.runs)):
                paragraph.runs[i].text = ""
            if paragraph.runs:
                paragraph.runs[0].text = combined_text
            else:
                paragraph.add_run(combined_text)

def format_bloom_level(raw_level: str) -> str:
    """Format Bloom's level to standard academic K-level / BTL notation."""
    if not raw_level:
        return "K2 - Understand"
    text = str(raw_level).strip()
    # Map L1-L6 to K1-K6
    replacements = {
        "L1": "K1", "L2": "K2", "L3": "K3",
        "L4": "K4", "L5": "K5", "L6": "K6"
    }
    for old_k, new_k in replacements.items():
        if text.startswith(old_k):
            return text.replace(old_k, new_k, 1)
    return text

def generate_question_paper_docx(
    paper_data: Dict[str, Any],
    questions: Optional[List[Dict[str, Any]]] = None,
    template_path: Optional[Path] = None,
    export_type: str = "question_paper", # "question_paper", "with_answer_key", "evaluation_scheme"
    export_approved_only: bool = True,
    include_citations: bool = False
) -> Path:
    """
    Generate the finalized Word (.docx) Question Paper.
    Adheres strictly to Aarupadai Veedu Institute of Technology (AVIT) /
    Vinayaka Mission's Research Foundation (VMRF) academic layout.
    Supports Question Paper (approved only), With Answer Key, and Evaluation Scheme.
    """
    if questions is None:
        questions = paper_data.get("questions", [])

    # Filter questions if required: official export excludes draft and rejected questions
    if export_approved_only:
        approved = [
            q for q in questions 
            if str(q.get("status", "")).lower() == "approved" or q.get("is_validated") is True
        ]
        if approved:
            questions = approved

    inst_name = str(paper_data.get("institution_name") or "").strip()
    if not inst_name or inst_name == "Department Examination":
        inst_header_line1 = "AARUPADAI VEEDU INSTITUTE OF TECHNOLOGY, PAIYANOOR"
        inst_header_line2 = "VINAYAKA MISSION'S RESEARCH FOUNDATION"
        inst_header_line3 = "(Deemed to be University under section 3 of the UGC Act 1956)"
    else:
        inst_header_line1 = inst_name.upper()
        inst_header_line2 = "VINAYAKA MISSION'S RESEARCH FOUNDATION"
        inst_header_line3 = "Accredited by NAAC & Approved by AICTE"

    dept_name = str(paper_data.get("department") or "Computer Science and Engineering").strip().upper()
    exam_name = str(paper_data.get("exam_name") or "END SEMESTER DEGREE EXAMINATION").strip().upper()
    course_name = str(paper_data.get("course_name") or "").strip()
    course_code = str(paper_data.get("course_code") or "").strip()
    semester = str(paper_data.get("semester") or "").strip()
    academic_year = str(paper_data.get("academic_year") or "").strip()
    programme = str(paper_data.get("programme") or "B.E. Computer Science & Engineering").strip()
    regulation = str(paper_data.get("regulation") or "2021 (Autonomous)").strip()
    duration = str(paper_data.get("duration") or "3 Hours").strip()
    max_marks = str(paper_data.get("max_marks") or "100").strip()
    exam_date = str(paper_data.get("exam_date") or "").strip()
    instructions = str(paper_data.get("instructions") or "1. Answer ALL questions in Part A.\n2. Answer either (a) or (b) from each question in Part B.\n3. Show neat sketches and step-by-step calculations wherever necessary.").strip()

    replacements = {
        "{{INSTITUTION_NAME}}": inst_header_line1,
        "{{DEPARTMENT}}": dept_name,
        "{{EXAM_NAME}}": exam_name,
        "{{COURSE_NAME}}": course_name,
        "{{COURSE_CODE}}": course_code,
        "{{SEMESTER}}": semester,
        "{{ACADEMIC_YEAR}}": academic_year,
        "{{DATE}}": exam_date,
        "{{TIME}}": duration,
        "{{DURATION}}": duration,
        "{{MAX_MARKS}}": max_marks,
        "{{INSTRUCTIONS}}": instructions
    }

    is_custom_docx = False
    is_reconstructed = paper_data.get("is_reconstructed", False)
    if template_path and template_path.is_file():
        if template_path.suffix.lower() == ".docx":
            try:
                doc = docx.Document(str(template_path))
                is_custom_docx = True
            except Exception:
                doc = docx.Document()
                is_reconstructed = True
        else:
            doc = docx.Document()
            is_reconstructed = True
    else:
        doc = docx.Document()

    if not is_custom_docx:
        for s in doc.sections:
            s.top_margin = Inches(0.6)
            s.bottom_margin = Inches(0.6)
            s.left_margin = Inches(0.7)
            s.right_margin = Inches(0.7)

        if is_reconstructed:
            p_rec = doc.add_paragraph()
            p_rec.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            p_rec.paragraph_format.space_after = Pt(2)
            orig_name = paper_data.get("original_template_name") or (template_path.name if template_path else "Template")
            r_rec = p_rec.add_run(f"Reconstructed from uploaded template: {orig_name}")
            r_rec.italic = True
            r_rec.font.name = "Calibri"
            r_rec.font.size = Pt(8)
            r_rec.font.color.rgb = RGBColor(148, 163, 184)

        # Build Standard AVIT / VMRF Header
        p_inst = doc.add_paragraph()
        p_inst.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_inst.paragraph_format.space_before = Pt(0)
        p_inst.paragraph_format.space_after = Pt(1)
        r_inst = p_inst.add_run(inst_header_line1)
        r_inst.bold = True
        r_inst.font.name = "Calibri"
        r_inst.font.size = Pt(14)
        r_inst.font.color.rgb = RGBColor(30, 58, 138) # Deep navy

        p_vmrf = doc.add_paragraph()
        p_vmrf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_vmrf.paragraph_format.space_before = Pt(0)
        p_vmrf.paragraph_format.space_after = Pt(1)
        r_vmrf = p_vmrf.add_run(inst_header_line2)
        r_vmrf.bold = True
        r_vmrf.font.name = "Calibri"
        r_vmrf.font.size = Pt(12)
        r_vmrf.font.color.rgb = RGBColor(71, 85, 105)

        p_deemed = doc.add_paragraph()
        p_deemed.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_deemed.paragraph_format.space_before = Pt(0)
        p_deemed.paragraph_format.space_after = Pt(4)
        r_deemed = p_deemed.add_run(inst_header_line3)
        r_deemed.italic = True
        r_deemed.font.name = "Calibri"
        r_deemed.font.size = Pt(9.5)
        r_deemed.font.color.rgb = RGBColor(100, 116, 139)

        p_dept = doc.add_paragraph()
        p_dept.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_dept.paragraph_format.space_before = Pt(2)
        p_dept.paragraph_format.space_after = Pt(2)
        r_dept = p_dept.add_run(f"DEPARTMENT OF {dept_name}")
        r_dept.bold = True
        r_dept.font.name = "Calibri"
        r_dept.font.size = Pt(11)
        r_dept.font.color.rgb = RGBColor(15, 23, 42)

        p_exam = doc.add_paragraph()
        p_exam.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_exam.paragraph_format.space_before = Pt(0)
        p_exam.paragraph_format.space_after = Pt(6)
        r_exam = p_exam.add_run(f"{exam_name} {('- ' + academic_year) if academic_year else ''}".strip())
        r_exam.bold = True
        r_exam.font.name = "Calibri"
        r_exam.font.size = Pt(11)

        # Examination Metadata Table
        meta_table = doc.add_table(rows=4, cols=4)
        meta_table.style = 'Table Grid'
        meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        meta_grid = [
            [("Degree & Branch:", True), (programme, False), ("Regulations:", True), (regulation, False)],
            [("Course Code & Name:", True), (f"{course_code} - {course_name}".strip(" -"), False), ("Semester / Year:", True), (f"{semester} / {academic_year}".strip(" /"), False)],
            [("Date & Session:", True), (f"{exam_date} (FN)" if exam_date else "Session FN", False), ("Duration:", True), (duration, False)],
            [("Max. Marks:", True), (f"{max_marks} Marks", False), ("Target Outcomes:", True), ("CO1, CO2, CO3, CO4, CO5", False)]
        ]
        col_w = [Inches(1.8), Inches(2.2), Inches(1.5), Inches(1.5)]
        for r_i, row in enumerate(meta_table.rows):
            for c_i, cell in enumerate(row.cells):
                cell.width = col_w[c_i]
                lbl, is_bold = meta_grid[r_i][c_i]
                cell.text = str(lbl or "")
                if is_bold:
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.bold = True
                            r.font.name = "Calibri"
                            r.font.size = Pt(9)
                else:
                    for p in cell.paragraphs:
                        for r in p.runs:
                            r.font.name = "Calibri"
                            r.font.size = Pt(9)
                set_cell_background(cell, "F1F5F9" if is_bold else "FFFFFF")
                set_cell_margins(cell, top=50, bottom=50, left=80, right=80)

        # General Instructions
        p_inst_block = doc.add_paragraph()
        p_inst_block.paragraph_format.space_before = Pt(8)
        p_inst_block.paragraph_format.space_after = Pt(8)
        r_lbl = p_inst_block.add_run("General Instructions:\n")
        r_lbl.bold = True
        r_lbl.font.name = "Calibri"
        r_lbl.font.size = Pt(9.5)
        r_inst_txt = p_inst_block.add_run(instructions)
        r_inst_txt.font.name = "Calibri"
        r_inst_txt.font.size = Pt(9)

    # Replace placeholders in existing paragraphs and tables (if custom template was used)
    for p in doc.paragraphs:
        replace_text_in_paragraph(p, replacements)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    replace_text_in_paragraph(p, replacements)

    # Group questions by section (Part A, Part B, Part C)
    sections_dict = {}
    for q in questions:
        sec = q.get("section_name", "Part A")
        if sec not in sections_dict:
            sections_dict[sec] = []
        sections_dict[sec].append(q)

    # Insert Section Headers and Questions Table
    for sec_name, q_list in sections_dict.items():
        # Compute section marks summary
        sec_marks_each = q_list[0].get("marks", 2) if q_list else 2
        # Section title paragraph
        p_sec = doc.add_paragraph()
        p_sec.paragraph_format.space_before = Pt(12)
        p_sec.paragraph_format.space_after = Pt(3)
        r_sec = p_sec.add_run(f"PART - {sec_name.replace('Part ', '').strip()} ")
        r_sec.bold = True
        r_sec.font.name = "Calibri"
        r_sec.font.size = Pt(11)
        r_sec.font.color.rgb = RGBColor(30, 58, 138)

        # Question table with standard academic columns:
        # Q.No | Questions | Course Outcome (CO) | Bloom's Level (BTL) | Marks
        q_table = doc.add_table(rows=1, cols=5)
        q_table.style = 'Table Grid'
        q_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        
        # Header row
        hdr_cells = q_table.rows[0].cells
        hdr_labels = ["Q.No", "Question Text", "CO", "Bloom's Level", "Marks"]
        col_widths = [Inches(0.7), Inches(4.3), Inches(0.6), Inches(1.1), Inches(0.6)]

        for idx, (cell, label, width) in enumerate(zip(hdr_cells, hdr_labels, col_widths)):
            cell.text = label
            cell.width = width
            set_cell_background(cell, "1E3A8A")
            set_cell_margins(cell, top=80, bottom=80, left=70, right=70)
            for p in cell.paragraphs:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER if idx != 1 else WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    r.bold = True
                    r.font.name = "Calibri"
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = RGBColor(255, 255, 255)

        # Data rows with OR choice handling
        for q in q_list:
            raw_qnum = str(q.get("question_number", "")).strip()
            is_or_choice = "[OR]" in raw_qnum or "(b)" in raw_qnum.lower()
            clean_qnum = raw_qnum.replace("[OR]", "").replace("[or]", "").strip()

            # If this is the second question of an internal OR pair, add a divider row first
            if "[OR]" in raw_qnum:
                div_row = q_table.add_row().cells
                for c, w in zip(div_row, col_widths):
                    c.width = w
                    set_cell_background(c, "F8FAFC")
                    set_cell_margins(c, top=40, bottom=40, left=60, right=60)
                div_row[1].text = "[ OR ]"
                div_p = div_row[1].paragraphs[0]
                div_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                if div_p.runs:
                    div_p.runs[0].bold = True
                    div_p.runs[0].italic = True
                    div_p.runs[0].font.name = "Calibri"
                    div_p.runs[0].font.size = Pt(9)
                    div_p.runs[0].font.color.rgb = RGBColor(71, 85, 105)

            new_row = q_table.add_row()
            try:
                trPr = new_row._tr.get_or_add_trPr()
                trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
            except Exception:
                pass
            row_cells = new_row.cells
            for c, w in zip(row_cells, col_widths):
                c.width = w
                set_cell_margins(c, top=60, bottom=60, left=60, right=60)

            # Q.No
            row_cells[0].text = clean_qnum
            row_cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Question Text & MCQ Options
            p_q = row_cells[1].paragraphs[0]
            p_q.text = str(q.get("question_text", "")).strip()

            if include_citations and (q.get("source_filename") or q.get("source_page_or_slide")):
                src_fn = q.get("source_filename") or "Prescribed Curriculum Textbook"
                src_pg = q.get("source_page_or_slide") or ""
                cit_text = f" [Source: {src_fn} {src_pg}]".strip()
                cit_run = p_q.add_run(f"\n{cit_text}")
                cit_run.italic = True
                cit_run.font.name = "Calibri"
                cit_run.font.size = Pt(8)
                cit_run.font.color.rgb = RGBColor(100, 116, 139)
            p_q.alignment = WD_ALIGN_PARAGRAPH.LEFT

            opts_raw = q.get("options_json")
            if opts_raw:
                try:
                    import json, re
                    opts = json.loads(opts_raw) if isinstance(opts_raw, str) else opts_raw
                    if isinstance(opts, list) and len(opts) >= 2:
                        for idx, opt in enumerate(opts):
                            if isinstance(opt, dict):
                                lbl = str(opt.get("label", "")).strip().upper() or chr(65 + idx)
                                txt = str(opt.get("text", "")).strip()
                                opt_str = f"{lbl}. {txt}"
                            else:
                                opt_str = str(opt).strip()
                                m_prefix = re.match(r'^([A-E])[\)\.]\s*(.*)', opt_str)
                                if m_prefix:
                                    opt_str = f"{m_prefix.group(1)}. {m_prefix.group(2)}"
                            p_opt = row_cells[1].add_paragraph()
                            p_opt.paragraph_format.space_before = Pt(1.5)
                            p_opt.paragraph_format.space_after = Pt(1.5)
                            p_opt.paragraph_format.left_indent = Inches(0.2)
                            r_opt = p_opt.add_run(opt_str)
                            r_opt.font.name = "Calibri"
                            r_opt.font.size = Pt(9)
                            r_opt.font.color.rgb = RGBColor(30, 41, 59)
                except Exception:
                    pass

            # CO Level
            row_cells[2].text = str(q.get("co_level", "CO1")).strip()
            row_cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Bloom's Level (Formatted to K-Level)
            b_formatted = format_bloom_level(q.get("bloom_level", "K2 - Understand"))
            row_cells[3].text = b_formatted
            row_cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Marks
            row_cells[4].text = str(q.get("marks", 2))
            row_cells[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

            # Font styling for data cells
            for c in row_cells:
                for p in c.paragraphs:
                    for r in p.runs:
                        r.font.name = "Calibri"
                        r.font.size = Pt(9.5)

    # -------------------------------------------------------------------------
    # SUMMARY / MAPPING TABLES AT END OF QUESTION PAPER
    # -------------------------------------------------------------------------
    p_sum_title = doc.add_paragraph()
    p_sum_title.paragraph_format.space_before = Pt(18)
    p_sum_title.paragraph_format.space_after = Pt(4)
    r_sum = p_sum_title.add_run("--- COURSE OUTCOME (CO) & BLOOM'S TAXONOMY DISTRIBUTION SUMMARY ---")
    r_sum.bold = True
    r_sum.font.name = "Calibri"
    r_sum.font.size = Pt(10.5)
    r_sum.font.color.rgb = RGBColor(30, 58, 138)

    # Calculate CO distributions
    # Note: for OR questions, count one choice toward mark distribution
    co_marks = {}
    bloom_marks = {
        "K1 - Remember": 0,
        "K2 - Understand": 0,
        "K3 - Apply": 0,
        "K4 - Analyze": 0,
        "K5 - Evaluate": 0,
        "K6 - Create": 0
    }
    
    # Track which questions were included to avoid double counting OR-choice marks in total
    processed_qnums = set()
    total_effective_marks = 0

    for q in questions:
        raw_num = str(q.get("question_number", "")).strip()
        base_num = raw_num.split("(")[0].strip() if "(" in raw_num else raw_num.split("[")[0].strip()
        marks = int(q.get("marks", 2))
        co = str(q.get("co_level", "CO1")).strip()
        btl = format_bloom_level(q.get("bloom_level", "K2 - Understand"))
        
        # Find matching bloom key
        matched_btl_key = "K2 - Understand"
        for k in bloom_marks.keys():
            if btl.startswith(k[:2]):
                matched_btl_key = k
                break

        # Accumulate marks per CO and Bloom
        if "[OR]" not in raw_num and not (raw_num.endswith("(b)") and base_num in processed_qnums):
            co_marks[co] = co_marks.get(co, 0) + marks
            bloom_marks[matched_btl_key] = bloom_marks.get(matched_btl_key, 0) + marks
            total_effective_marks += marks
            processed_qnums.add(base_num)
        else:
            # Still record CO presence
            if co not in co_marks:
                co_marks[co] = 0

    if total_effective_marks == 0:
        total_effective_marks = int(max_marks) if max_marks.isdigit() else 100

    # Table 1: Course Outcomes (CO) Distribution
    p_co_tbl = doc.add_paragraph()
    p_co_tbl.paragraph_format.space_before = Pt(6)
    p_co_tbl.paragraph_format.space_after = Pt(2)
    r_co_lbl = p_co_tbl.add_run("Table 1: Course Outcome (CO) Marks Distribution")
    r_co_lbl.bold = True
    r_co_lbl.font.name = "Calibri"
    r_co_lbl.font.size = Pt(9.5)

    co_table = doc.add_table(rows=1, cols=4)
    co_table.style = 'Table Grid'
    co_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    co_hdr = co_table.rows[0].cells
    co_hdr_labels = ["Course Outcome", "Cognitive Domain / Focus", "Total Marks", "Weightage (%)"]
    co_widths = [Inches(1.5), Inches(3.2), Inches(1.2), Inches(1.1)]

    for idx, (c, lbl, w) in enumerate(zip(co_hdr, co_hdr_labels, co_widths)):
        c.text = lbl
        c.width = w
        set_cell_background(c, "334155") # Slate gray header
        set_cell_margins(c, top=60, bottom=60, left=60, right=60)
        for p in c.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if idx != 1 else WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.bold = True
                r.font.name = "Calibri"
                r.font.size = Pt(9)
                r.font.color.rgb = RGBColor(255, 255, 255)

    sorted_cos = sorted(co_marks.keys())
    co_domain_map = {
        "CO1": "Foundations, Core Terminology & Basic Mechanisms",
        "CO2": "Conceptual Frameworks, Models & Implementations",
        "CO3": "Application to Algorithmic Problems & Solutions",
        "CO4": "Performance Analysis, Complexity & Trade-offs",
        "CO5": "Critical Evaluation & Architectural Formulations",
        "CO6": "Creative Design, Synthesis & Advanced Solutions"
    }

    running_co_marks = 0
    for co in sorted_cos:
        m = co_marks[co]
        running_co_marks += m
        pct = round((m / total_effective_marks) * 100, 1) if total_effective_marks > 0 else 0
        r_cells = co_table.add_row().cells
        for c, w in zip(r_cells, co_widths):
            c.width = w
            set_cell_margins(c, top=40, bottom=40, left=50, right=50)

        r_cells[0].text = co
        r_cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cells[1].text = co_domain_map.get(co, f"Mastery of {course_name} curriculum module")
        r_cells[2].text = f"{m} Marks"
        r_cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cells[3].text = f"{pct}%"
        r_cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        for c in r_cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(8.5)

    # CO Total Row
    tot_co_cells = co_table.add_row().cells
    for c, w in zip(tot_co_cells, co_widths):
        c.width = w
        set_cell_background(c, "F1F5F9")
        set_cell_margins(c, top=50, bottom=50, left=50, right=50)
    tot_co_cells[0].text = "Total"
    tot_co_cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    tot_co_cells[1].text = "Across All Course Outcomes"
    tot_co_cells[2].text = f"{running_co_marks} Marks"
    tot_co_cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    tot_co_cells[3].text = "100.0%"
    tot_co_cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for c in tot_co_cells:
        for p in c.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.name = "Calibri"
                r.font.size = Pt(9)

    # Table 2: Bloom's Taxonomy Distribution
    p_btl_tbl = doc.add_paragraph()
    p_btl_tbl.paragraph_format.space_before = Pt(8)
    p_btl_tbl.paragraph_format.space_after = Pt(2)
    r_btl_lbl = p_btl_tbl.add_run("Table 2: Bloom's Taxonomy Cognitive Level (BTL) Distribution")
    r_btl_lbl.bold = True
    r_btl_lbl.font.name = "Calibri"
    r_btl_lbl.font.size = Pt(9.5)

    btl_table = doc.add_table(rows=1, cols=4)
    btl_table.style = 'Table Grid'
    btl_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    btl_hdr = btl_table.rows[0].cells
    btl_hdr_labels = ["Cognitive Level (BTL)", "Cognitive Domain", "Total Marks", "Percentage (%)"]
    btl_widths = [Inches(1.8), Inches(2.9), Inches(1.2), Inches(1.1)]

    for idx, (c, lbl, w) in enumerate(zip(btl_hdr, btl_hdr_labels, btl_widths)):
        c.text = lbl
        c.width = w
        set_cell_background(c, "334155")
        set_cell_margins(c, top=60, bottom=60, left=60, right=60)
        for p in c.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if idx != 1 else WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.bold = True
                r.font.name = "Calibri"
                r.font.size = Pt(9)
                r.font.color.rgb = RGBColor(255, 255, 255)

    btl_domain_names = {
        "K1 - Remember": "Recall facts, basic definitions and concepts",
        "K2 - Understand": "Explain ideas, mechanisms and relationships",
        "K3 - Apply": "Execute, compute and implement solutions",
        "K4 - Analyze": "Differentiate, organize, relate and deconstruct",
        "K5 - Evaluate": "Critique, assess and make judgments on quality",
        "K6 - Create": "Design, formulate and construct novel solutions"
    }

    running_btl_marks = 0
    for btl_key, btl_desc in btl_domain_names.items():
        m = bloom_marks.get(btl_key, 0)
        running_btl_marks += m
        pct = round((m / total_effective_marks) * 100, 1) if total_effective_marks > 0 else 0
        r_cells = btl_table.add_row().cells
        for c, w in zip(r_cells, btl_widths):
            c.width = w
            set_cell_margins(c, top=40, bottom=40, left=50, right=50)

        r_cells[0].text = btl_key
        r_cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cells[1].text = btl_desc
        r_cells[2].text = f"{m} Marks"
        r_cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cells[3].text = f"{pct}%"
        r_cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        for c in r_cells:
            for p in c.paragraphs:
                for r in p.runs:
                    r.font.name = "Calibri"
                    r.font.size = Pt(8.5)

    # BTL Total Row
    tot_btl_cells = btl_table.add_row().cells
    for c, w in zip(tot_btl_cells, btl_widths):
        c.width = w
        set_cell_background(c, "F1F5F9")
        set_cell_margins(c, top=50, bottom=50, left=50, right=50)
    tot_btl_cells[0].text = "Total"
    tot_btl_cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    tot_btl_cells[1].text = "Across All Cognitive Levels"
    tot_btl_cells[2].text = f"{running_btl_marks} Marks"
    tot_btl_cells[2].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    tot_btl_cells[3].text = "100.0%"
    tot_btl_cells[3].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for c in tot_btl_cells:
        for p in c.paragraphs:
            for r in p.runs:
                r.bold = True
                r.font.name = "Calibri"
                r.font.size = Pt(9)

    # -------------------------------------------------------------------------
    # OPTIONAL EXTENDED SECTIONS: ANSWER KEY & EVALUATION SCHEME
    # -------------------------------------------------------------------------
    if export_type == "with_answer_key":
        doc.add_page_break()
        p_ak_h = doc.add_paragraph()
        p_ak_h.paragraph_format.space_before = Pt(12)
        p_ak_h.paragraph_format.space_after = Pt(4)
        r_ak = p_ak_h.add_run("SECTION II: OFFICIAL ANSWER KEY & MODEL SOLUTIONS")
        r_ak.bold = True
        r_ak.font.name = "Calibri"
        r_ak.font.size = Pt(13)
        r_ak.font.color.rgb = RGBColor(30, 58, 138)

        p_ak_sub = doc.add_paragraph()
        p_ak_sub.paragraph_format.space_after = Pt(12)
        r_ak_sub = p_ak_sub.add_run("Instructional Reference & Model Answers Grounded in Syllabus & Faculty Courseware")
        r_ak_sub.italic = True
        r_ak_sub.font.name = "Calibri"
        r_ak_sub.font.size = Pt(9.5)
        r_ak_sub.font.color.rgb = RGBColor(100, 116, 139)

        for q in questions:
            q_num = str(q.get("question_number", "")).strip()
            marks = q.get("marks", 2)
            co = q.get("co_level", "CO1")
            bloom = q.get("bloom_level", "L2 - Understand")

            p_qhdr = doc.add_paragraph()
            p_qhdr.paragraph_format.space_before = Pt(8)
            p_qhdr.paragraph_format.space_after = Pt(2)
            r_qh = p_qhdr.add_run(f"Question {q_num}  [{co} | {bloom} | {marks} Marks]")
            r_qh.bold = True
            r_qh.font.name = "Calibri"
            r_qh.font.size = Pt(10)
            r_qh.font.color.rgb = RGBColor(15, 23, 42)

            p_qtxt = doc.add_paragraph()
            p_qtxt.paragraph_format.space_after = Pt(4)
            r_qt = p_qtxt.add_run(f"Q: {q.get('question_text', '').strip()}")
            r_qt.italic = True
            r_qt.font.name = "Calibri"
            r_qt.font.size = Pt(9.5)

            # Model Answer / MCQ Key
            p_ans = doc.add_paragraph()
            p_ans.paragraph_format.space_after = Pt(4)

            correct_key = q.get("correct_option") or q.get("correct_answer_json")
            if correct_key and q.get("options_json"):
                r_albl = p_ans.add_run(f"Correct Answer: {correct_key}\n\n")
                r_albl.bold = True
                r_albl.font.name = "Calibri"
                r_albl.font.size = Pt(10)
                r_albl.font.color.rgb = RGBColor(22, 101, 52)

                expl = q.get("explanation")
                if expl:
                    r_exp_lbl = p_ans.add_run("Explanation:\n")
                    r_exp_lbl.bold = True
                    r_exp_lbl.font.size = Pt(9.5)
                    r_exp_txt = p_ans.add_run(f"{expl}\n\n")
                    r_exp_txt.font.size = Pt(9)

                dist_raw = q.get("distractor_explanations_json")
                if dist_raw:
                    try:
                        import json
                        dist_data = json.loads(dist_raw) if isinstance(dist_raw, str) else dist_raw
                        if isinstance(dist_data, dict):
                            r_d_lbl = p_ans.add_run("Distractor Rationales:\n")
                            r_d_lbl.bold = True
                            r_d_lbl.font.size = Pt(8.5)
                            r_d_lbl.font.color.rgb = RGBColor(100, 116, 139)
                            for d_key, d_text in dist_data.items():
                                if d_key != correct_key:
                                    r_d_opt = p_ans.add_run(f"• Option {d_key}: {d_text}\n")
                                    r_d_opt.font.size = Pt(8.5)
                                    r_d_opt.font.color.rgb = RGBColor(100, 116, 139)
                    except Exception:
                        pass
            else:
                ans_text = q.get("model_answer") or q.get("stepwise_solution") or "Refer to standard prescribed textbook for comprehensive derivation."
                r_albl = p_ans.add_run("Model Solution:\n")
                r_albl.bold = True
                r_albl.font.name = "Calibri"
                r_albl.font.size = Pt(9.5)
                r_albl.font.color.rgb = RGBColor(22, 101, 52)
                r_atxt = p_ans.add_run(ans_text)
                r_atxt.font.name = "Calibri"
                r_atxt.font.size = Pt(9)

            # Source Grounding Provenance
            src_file = q.get("source_filename") or "Approved Syllabus"
            src_slide = q.get("source_page_or_slide") or ""
            conf = q.get("alignment_confidence", 1.0)
            conf_str = f"{int(float(conf)*100)}%" if conf else "100%"
            passage = q.get("supporting_passage", "")

            p_src = doc.add_paragraph()
            p_src.paragraph_format.space_after = Pt(8)
            r_slbl = p_src.add_run(f"Source Grounding: {src_file} ({src_slide}) | Confidence: {conf_str}\n")
            r_slbl.bold = True
            r_slbl.font.name = "Calibri"
            r_slbl.font.size = Pt(8.5)
            r_slbl.font.color.rgb = RGBColor(71, 85, 105)
            if passage:
                r_ptxt = p_src.add_run(f"Supporting Context: \"{passage[:240]}\"")
                r_ptxt.italic = True
                r_ptxt.font.name = "Calibri"
                r_ptxt.font.size = Pt(8.5)
                r_ptxt.font.color.rgb = RGBColor(100, 116, 139)

    elif export_type == "evaluation_scheme":
        doc.add_page_break()
        p_es_h = doc.add_paragraph()
        p_es_h.paragraph_format.space_before = Pt(12)
        p_es_h.paragraph_format.space_after = Pt(4)
        r_es = p_es_h.add_run("SECTION II: FACULTY EVALUATION SCHEME & SCORING RUBRICS")
        r_es.bold = True
        r_es.font.name = "Calibri"
        r_es.font.size = Pt(13)
        r_es.font.color.rgb = RGBColor(30, 58, 138)

        p_es_sub = doc.add_paragraph()
        p_es_sub.paragraph_format.space_after = Pt(12)
        r_es_sub = p_es_sub.add_run("Stepwise Marking Breakdown and Criterion-Referenced Evaluation Matrix")
        r_es_sub.italic = True
        r_es_sub.font.name = "Calibri"
        r_es_sub.font.size = Pt(9.5)
        r_es_sub.font.color.rgb = RGBColor(100, 116, 139)

        for q in questions:
            q_num = str(q.get("question_number", "")).strip()
            marks = q.get("marks", 2)
            co = q.get("co_level", "CO1")
            bloom = q.get("bloom_level", "L2 - Understand")

            p_qhdr = doc.add_paragraph()
            p_qhdr.paragraph_format.space_before = Pt(8)
            p_qhdr.paragraph_format.space_after = Pt(2)
            r_qh = p_qhdr.add_run(f"Question {q_num}  [{co} | {bloom} | Total: {marks} Marks]")
            r_qh.bold = True
            r_qh.font.name = "Calibri"
            r_qh.font.size = Pt(10)
            r_qh.font.color.rgb = RGBColor(15, 23, 42)

            # Marking Scheme Breakdown
            scheme_text = q.get("marking_scheme") or f"{marks} Marks: Complete technical accuracy and explanation."
            p_sch = doc.add_paragraph()
            p_sch.paragraph_format.space_after = Pt(4)
            r_slbl = p_sch.add_run("Marking Breakdown:\n")
            r_slbl.bold = True
            r_slbl.font.name = "Calibri"
            r_slbl.font.size = Pt(9.5)
            r_slbl.font.color.rgb = RGBColor(14, 116, 144) # Cyan/teal
            r_stxt = p_sch.add_run(scheme_text)
            r_stxt.font.name = "Calibri"
            r_stxt.font.size = Pt(9)

            # Rubric Criteria Table if available
            rubric_raw = q.get("rubric_json")
            if rubric_raw:
                try:
                    import json
                    r_data = json.loads(rubric_raw) if isinstance(rubric_raw, str) else rubric_raw
                    criteria = r_data.get("criteria", [])
                    if criteria:
                        r_table = doc.add_table(rows=1, cols=3)
                        r_table.style = 'Table Grid'
                        r_table.alignment = WD_TABLE_ALIGNMENT.CENTER
                        r_widths = [Inches(2.0), Inches(1.0), Inches(3.5)]
                        r_hdr = r_table.rows[0].cells
                        r_labels = ["Evaluation Criterion", "Marks", "Performance Descriptor"]
                        for idx, (rc, rlbl, rw) in enumerate(zip(r_hdr, r_labels, r_widths)):
                            rc.text = rlbl
                            rc.width = rw
                            set_cell_background(rc, "475569")
                            set_cell_margins(rc, top=40, bottom=40, left=50, right=50)
                            for p in rc.paragraphs:
                                for r in p.runs:
                                    r.bold = True
                                    r.font.name = "Calibri"
                                    r.font.size = Pt(8.5)
                                    r.font.color.rgb = RGBColor(255, 255, 255)

                        for crit in criteria:
                            row_c = r_table.add_row().cells
                            for c, w in zip(row_c, r_widths):
                                c.width = w
                                set_cell_margins(c, top=30, bottom=30, left=40, right=40)
                            row_c[0].text = str(crit.get("criterion", ""))
                            row_c[1].text = f"{crit.get('marks', 1)} M"
                            row_c[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
                            row_c[2].text = str(crit.get("description", ""))
                            for c in row_c:
                                for p in c.paragraphs:
                                    for r in p.runs:
                                        r.font.name = "Calibri"
                                        r.font.size = Pt(8.5)
                except Exception:
                    pass

    # Save output
    safe_code = "".join(c for c in (paper_data.get("course_code") or "QP") if c.isalnum() or c in "_-")
    prefix_map = {
        "question_paper": "QuestionPaper",
        "with_answer_key": "QP_With_AnswerKey",
        "evaluation_scheme": "QP_EvaluationScheme"
    }
    file_prefix = prefix_map.get(export_type, "QuestionPaper")
    out_filename = f"{file_prefix}_{safe_code}_{uuid.uuid4().hex[:8]}.docx"
    out_path = settings.EXPORT_DIR / out_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out_path))

    return out_path


