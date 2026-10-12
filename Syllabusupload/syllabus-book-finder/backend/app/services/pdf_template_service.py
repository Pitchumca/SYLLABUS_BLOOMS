import os
import uuid
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch

from app.config import settings

def format_bloom_k_level(raw_level: str) -> str:
    """Format Bloom's level to K-level / BTL notation."""
    if not raw_level:
        return "K2 - Understand"
    text = str(raw_level).strip()
    replacements = {
        "L1": "K1", "L2": "K2", "L3": "K3",
        "L4": "K4", "L5": "K5", "L6": "K6"
    }
    for old_k, new_k in replacements.items():
        if text.startswith(old_k):
            return text.replace(old_k, new_k, 1)
    return text

def generate_question_paper_pdf(
    paper_data: Dict[str, Any],
    questions: Optional[List[Dict[str, Any]]] = None,
    export_type: str = "question_paper", # "question_paper", "with_answer_key", "evaluation_scheme"
    export_approved_only: bool = True
) -> Path:
    """
    Generate the finalized PDF Question Paper using ReportLab.
    Supports Question Paper (approved only), With Answer Key, and Evaluation Scheme.
    Student-facing export strictly excludes answers, rubrics, and provenance.
    """
    if questions is None:
        questions = paper_data.get("questions", [])

    if export_approved_only:
        approved = [
            q for q in questions 
            if str(q.get("status", "")).lower() == "approved" or q.get("is_validated") is True
        ]
        if approved:
            questions = approved

    safe_code = "".join(c for c in (paper_data.get("course_code") or "QP") if c.isalnum() or c in "_-")
    prefix_map = {
        "question_paper": "QuestionPaper",
        "with_answer_key": "QP_With_AnswerKey",
        "evaluation_scheme": "QP_EvaluationScheme"
    }
    file_prefix = prefix_map.get(export_type, "QuestionPaper")
    out_filename = f"{file_prefix}_{safe_code}_{uuid.uuid4().hex[:8]}.pdf"
    out_path = settings.EXPORT_DIR / out_filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Document setup: A4 with 0.5 inch margins
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        alignment=1, # Center
        textColor=colors.HexColor('#1E3A8A')
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        alignment=1,
        textColor=colors.HexColor('#334155')
    )

    dept_style = ParagraphStyle(
        'DocDept',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        alignment=1,
        textColor=colors.HexColor('#0F172A')
    )

    meta_label_style = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#1E293B')
    )

    meta_val_style = ParagraphStyle(
        'MetaVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0F172A')
    )

    section_hdr_style = ParagraphStyle(
        'SecHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        alignment=0,
        textColor=colors.HexColor('#1E3A8A')
    )

    table_th_style = ParagraphStyle(
        'TableTH',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.white
    )

    cell_style = ParagraphStyle(
        'CellText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )

    cell_center = ParagraphStyle(
        'CellCenter',
        parent=cell_style,
        alignment=1
    )

    option_style = ParagraphStyle(
        'OptText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        leftIndent=12,
        textColor=colors.HexColor('#1E293B')
    )

    elements = []

    # 1. Header Information
    inst_name = str(paper_data.get("institution_name") or "AARUPADAI VEEDU INSTITUTE OF TECHNOLOGY").strip().upper()
    elements.append(Paragraph(inst_name, title_style))
    elements.append(Spacer(1, 2))

    dept_name = str(paper_data.get("department") or "COMPUTER SCIENCE AND ENGINEERING").strip().upper()
    exam_name = str(paper_data.get("exam_name") or "END SEMESTER DEGREE EXAMINATION").strip().upper()
    academic_year = str(paper_data.get("academic_year") or "").strip()
    elements.append(Paragraph(f"DEPARTMENT OF {dept_name}", subtitle_style))
    elements.append(Paragraph(f"{exam_name} {('- ' + academic_year) if academic_year else ''}".strip(), dept_style))
    elements.append(Spacer(1, 6))

    # 2. Metadata Table
    course_name = str(paper_data.get("course_name") or "").strip()
    course_code = str(paper_data.get("course_code") or "").strip()
    semester = str(paper_data.get("semester") or "").strip()
    programme = str(paper_data.get("programme") or "B.E. Computer Science & Engineering").strip()
    regulation = str(paper_data.get("regulation") or "2021 (Autonomous)").strip()
    duration = str(paper_data.get("duration") or "3 Hours").strip()
    max_marks = str(paper_data.get("max_marks") or "100").strip()
    exam_date = str(paper_data.get("exam_date") or "").strip()

    meta_table_data = [
        [
            Paragraph("Degree & Branch:", meta_label_style),
            Paragraph(programme, meta_val_style),
            Paragraph("Regulations:", meta_label_style),
            Paragraph(regulation, meta_val_style)
        ],
        [
            Paragraph("Course Code & Title:", meta_label_style),
            Paragraph(f"{course_code} - {course_name}".strip(" -"), meta_val_style),
            Paragraph("Semester / Year:", meta_label_style),
            Paragraph(f"{semester} / {academic_year}".strip(" /"), meta_val_style)
        ],
        [
            Paragraph("Date & Session:", meta_label_style),
            Paragraph(exam_date or "FN Session", meta_val_style),
            Paragraph("Duration & Marks:", meta_label_style),
            Paragraph(f"{duration} | Max. {max_marks} M", meta_val_style)
        ]
    ]

    t_meta = Table(meta_table_data, colWidths=[110, 180, 95, 137])
    t_meta.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 6))

    # 3. General Instructions
    instructions = str(paper_data.get("instructions") or "Answer all questions according to section regulations.").strip()
    p_inst = Paragraph(f"<b>Instructions:</b> {instructions}", ParagraphStyle(
        'InstText', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor('#475569')
    ))
    elements.append(p_inst)
    elements.append(Spacer(1, 8))

    # 4. Group questions by section and render tables
    sections_dict = {}
    for q in questions:
        sec = q.get("section_name", "Part A")
        sections_dict.setdefault(sec, []).append(q)

    # Column widths for question table: Q.No(40), Question(310), CO(45), Bloom(75), Marks(42)
    q_col_widths = [38, 325, 42, 75, 42]

    for sec_name, q_list in sections_dict.items():
        elements.append(Spacer(1, 4))
        elements.append(Paragraph(f"<b>PART - {sec_name.replace('Part ', '').strip()}</b>", section_hdr_style))
        elements.append(Spacer(1, 3))

        q_table_data = [
            [
                Paragraph("Q.No", table_th_style),
                Paragraph("Question Text", ParagraphStyle('THLeft', parent=table_th_style, alignment=0)),
                Paragraph("CO", table_th_style),
                Paragraph("Bloom's", table_th_style),
                Paragraph("Marks", table_th_style)
            ]
        ]

        table_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('BOX', (0, 0), (-1, -1), 0.75, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]

        row_idx = 1
        for q in q_list:
            raw_qnum = str(q.get("question_number", "")).strip()
            clean_qnum = raw_qnum.replace("[OR]", "").replace("[or]", "").strip()

            if "[OR]" in raw_qnum:
                # Add [ OR ] divider row
                q_table_data.append([
                    Paragraph("", cell_center),
                    Paragraph("<b>[ OR ]</b>", ParagraphStyle('OrDivider', parent=styles['Normal'], alignment=1, fontSize=8, fontName='Helvetica-Bold', textColor=colors.HexColor('#475569'))),
                    Paragraph("", cell_center),
                    Paragraph("", cell_center),
                    Paragraph("", cell_center)
                ])
                table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor('#F8FAFC')))
                row_idx += 1

            # Prepare question text flowables (stem + options)
            q_flowables = [Paragraph(str(q.get("question_text", "")).strip(), cell_style)]

            # MCQ Options if present (NEVER show correct answer or explanation in student QP)
            opts_raw = q.get("options_json")
            if opts_raw:
                try:
                    opts = json.loads(opts_raw) if isinstance(opts_raw, str) else opts_raw
                    if isinstance(opts, list):
                        for idx, opt in enumerate(opts):
                            if isinstance(opt, dict):
                                lbl = str(opt.get("label", "")).strip().upper() or chr(65 + idx)
                                txt = str(opt.get("text", "")).strip()
                                opt_str = f"<b>{lbl}.</b> {txt}"
                            else:
                                opt_str = str(opt).strip()
                            q_flowables.append(Paragraph(opt_str, option_style))
                except Exception:
                    pass

            b_formatted = format_bloom_k_level(q.get("bloom_level", "K2 - Understand"))

            q_table_data.append([
                Paragraph(clean_qnum, cell_center),
                q_flowables,
                Paragraph(str(q.get("co_level", "CO1")), cell_center),
                Paragraph(b_formatted, cell_center),
                Paragraph(str(q.get("marks", 2)), cell_center)
            ])
            row_idx += 1

        t_questions = Table(q_table_data, colWidths=q_col_widths)
        t_questions.setStyle(TableStyle(table_styles))
        elements.append(t_questions)
        elements.append(Spacer(1, 8))

    # 5. CO & Bloom Distribution Summary Tables
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("<b>Course Outcome (CO) & Cognitive Level Distribution Summary</b>", section_hdr_style))
    elements.append(Spacer(1, 4))

    co_marks = {}
    bloom_marks = {
        "K1 - Remember": 0, "K2 - Understand": 0, "K3 - Apply": 0,
        "K4 - Analyze": 0, "K5 - Evaluate": 0, "K6 - Create": 0
    }
    processed_qnums = set()
    total_effective_marks = 0

    for q in questions:
        raw_num = str(q.get("question_number", "")).strip()
        base_num = raw_num.split("(")[0].strip() if "(" in raw_num else raw_num.split("[")[0].strip()
        marks = int(q.get("marks", 2))
        co = str(q.get("co_level", "CO1")).strip()
        btl = format_bloom_k_level(q.get("bloom_level", "K2 - Understand"))
        matched_btl_key = "K2 - Understand"
        for k in bloom_marks.keys():
            if btl.startswith(k[:2]):
                matched_btl_key = k
                break

        if "[OR]" not in raw_num and not (raw_num.endswith("(b)") and base_num in processed_qnums):
            co_marks[co] = co_marks.get(co, 0) + marks
            bloom_marks[matched_btl_key] = bloom_marks.get(matched_btl_key, 0) + marks
            total_effective_marks += marks
            processed_qnums.add(base_num)
        else:
            if co not in co_marks:
                co_marks[co] = 0

    if total_effective_marks == 0:
        total_effective_marks = int(max_marks) if max_marks.isdigit() else 100

    co_table_rows = [
        [Paragraph("CO", table_th_style), Paragraph("Total Marks", table_th_style), Paragraph("Weightage (%)", table_th_style)]
    ]
    for co in sorted(co_marks.keys()):
        m = co_marks[co]
        pct = round((m / total_effective_marks) * 100, 1) if total_effective_marks > 0 else 0
        co_table_rows.append([
            Paragraph(co, cell_center),
            Paragraph(f"{m} M", cell_center),
            Paragraph(f"{pct}%", cell_center)
        ])

    t_co = Table(co_table_rows, colWidths=[174, 174, 174])
    t_co.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#334155')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_co)

    # 6. Extended Sections for Answer Key and Evaluation Scheme
    if export_type == "with_answer_key":
        elements.append(PageBreak())
        elements.append(Paragraph("<b>SECTION II: OFFICIAL ANSWER KEY & MODEL SOLUTIONS</b>", title_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph("Instructional Reference & Model Answers Grounded in Syllabus & Faculty Courseware", ParagraphStyle(
            'SubRef', parent=styles['Normal'], alignment=1, fontSize=8.5, fontName='Helvetica-Oblique', textColor=colors.HexColor('#64748B')
        )))
        elements.append(Spacer(1, 10))

        for q in questions:
            q_num = str(q.get("question_number", "")).strip()
            marks = q.get("marks", 2)
            co = q.get("co_level", "CO1")
            bloom = q.get("bloom_level", "L2 - Understand")

            q_ans_flowables = [
                Paragraph(f"<b>Question {q_num} [{co} | {bloom} | {marks} Marks]</b>", ParagraphStyle('AnsQH', parent=styles['Normal'], fontSize=9.5, fontName='Helvetica-Bold', textColor=colors.HexColor('#1E3A8A'))),
                Spacer(1, 2),
                Paragraph(f"<i>{q.get('question_text', '').strip()}</i>", ParagraphStyle('AnsQT', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#334155'))),
                Spacer(1, 4)
            ]

            correct_key = q.get("correct_option") or q.get("correct_answer_json")
            if correct_key and q.get("options_json"):
                q_ans_flowables.append(Paragraph(f"<b>Correct Answer:</b> Option {correct_key}", ParagraphStyle('CorrOpt', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.HexColor('#166534'))))
                expl = q.get("explanation")
                if expl:
                    q_ans_flowables.append(Paragraph(f"<b>Explanation:</b> {expl}", ParagraphStyle('ExpT', parent=styles['Normal'], fontSize=8.5, textColor=colors.HexColor('#1E293B'))))
            else:
                ans_text = q.get("model_answer") or q.get("stepwise_solution") or "Refer to standard prescribed textbook for derivation."
                q_ans_flowables.append(Paragraph("<b>Model Solution:</b>", ParagraphStyle('MSHead', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.HexColor('#166534'))))
                q_ans_flowables.append(Paragraph(ans_text.replace('\n', '<br/>'), ParagraphStyle('MSText', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#0F172A'))))

            # Grounding context
            src_file = q.get("source_filename") or "Approved Syllabus"
            src_slide = q.get("source_page_or_slide") or ""
            conf = q.get("alignment_confidence", 1.0)
            conf_str = f"{int(float(conf)*100)}%" if conf else "100%"
            q_ans_flowables.append(Spacer(1, 2))
            q_ans_flowables.append(Paragraph(f"<i>Source Grounding: {src_file} ({src_slide}) | Confidence: {conf_str}</i>", ParagraphStyle('SrcT', parent=styles['Normal'], fontSize=7.5, fontName='Helvetica-Oblique', textColor=colors.HexColor('#64748B'))))
            q_ans_flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=6, spaceAfter=8))

            elements.append(KeepTogether(q_ans_flowables))

    elif export_type == "evaluation_scheme":
        elements.append(PageBreak())
        elements.append(Paragraph("<b>SECTION II: FACULTY EVALUATION SCHEME & SCORING RUBRICS</b>", title_style))
        elements.append(Spacer(1, 4))
        elements.append(Paragraph("Stepwise Marking Breakdown and Criterion-Referenced Evaluation Matrix", ParagraphStyle(
            'SubES', parent=styles['Normal'], alignment=1, fontSize=8.5, fontName='Helvetica-Oblique', textColor=colors.HexColor('#64748B')
        )))
        elements.append(Spacer(1, 10))

        for q in questions:
            q_num = str(q.get("question_number", "")).strip()
            marks = q.get("marks", 2)
            co = q.get("co_level", "CO1")
            bloom = q.get("bloom_level", "L2 - Understand")

            q_es_flowables = [
                Paragraph(f"<b>Question {q_num} [{co} | {bloom} | Total: {marks} Marks]</b>", ParagraphStyle('ESQH', parent=styles['Normal'], fontSize=9.5, fontName='Helvetica-Bold', textColor=colors.HexColor('#1E3A8A'))),
                Spacer(1, 2)
            ]

            scheme_text = q.get("marking_scheme") or f"{marks} Marks: Complete technical explanation and correctness."
            q_es_flowables.append(Paragraph("<b>Marking Breakdown:</b>", ParagraphStyle('MBH', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.HexColor('#0E7490'))))
            q_es_flowables.append(Paragraph(scheme_text.replace('\n', '<br/>'), ParagraphStyle('MBT', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor('#0F172A'))))

            rubric_raw = q.get("rubric_json")
            if rubric_raw:
                try:
                    r_data = json.loads(rubric_raw) if isinstance(rubric_raw, str) else rubric_raw
                    criteria = r_data.get("criteria", [])
                    if criteria:
                        r_table_data = [
                            [Paragraph("Criterion", table_th_style), Paragraph("Marks", table_th_style), Paragraph("Descriptor", table_th_style)]
                        ]
                        for c in criteria:
                            r_table_data.append([
                                Paragraph(str(c.get("criterion", "")), cell_style),
                                Paragraph(f"{c.get('marks', 1)} M", cell_center),
                                Paragraph(str(c.get("description", "")), cell_style)
                            ])
                        t_rub = Table(r_table_data, colWidths=[150, 60, 312])
                        t_rub.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#475569')),
                            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
                            ('TOPPADDING', (0, 0), (-1, -1), 3),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                        ]))
                        q_es_flowables.append(Spacer(1, 3))
                        q_es_flowables.append(t_rub)
                except Exception:
                    pass

            q_es_flowables.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=6, spaceAfter=8))
            elements.append(KeepTogether(q_es_flowables))

    # Build the PDF document
    doc.build(elements)
    return out_path
