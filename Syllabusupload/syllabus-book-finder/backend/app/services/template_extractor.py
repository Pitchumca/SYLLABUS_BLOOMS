import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import docx
import fitz # PyMuPDF
import pdfplumber

from app.services.pdf_extractor import extract_pdf_text
from app.services.ocr_service import run_ocr_on_pdf, is_tesseract_available

logger = logging.getLogger(__name__)

# Canonical bloom mapping
BLOOM_NORMALIZATION = {
    "l1": "L1", "k1": "L1", "remember": "L1", "recall": "L1",
    "l2": "L2", "k2": "L2", "understand": "L2", "comprehend": "L2",
    "l3": "L3", "k3": "L3", "apply": "L3", "application": "L3",
    "l4": "L4", "k4": "L4", "analyze": "L4", "analysis": "L4",
    "l5": "L5", "k5": "L5", "evaluate": "L5", "evaluation": "L5",
    "l6": "L6", "k6": "L6", "create": "L6", "design": "L6"
}

def normalize_bloom(val: str, default: str = "L2") -> str:
    """Normalize extracted bloom or K-level string to canonical L1-L6."""
    if not val:
        return default
    clean = re.sub(r'[^a-zA-Z0-9]', '', str(val)).lower()
    for prefix in ["l1", "l2", "l3", "l4", "l5", "l6", "k1", "k2", "k3", "k4", "k5", "k6"]:
        if clean.startswith(prefix):
            return BLOOM_NORMALIZATION.get(prefix, default)
    for word, level in BLOOM_NORMALIZATION.items():
        if word in clean:
            return level
    return default

def normalize_co(val: str, default: str = "CO1") -> str:
    """Normalize course outcome string to CO1-CO6."""
    if not val:
        return default
    m = re.search(r'CO\s*([1-6])', str(val), re.IGNORECASE)
    if m:
        return f"CO{m.group(1)}"
    m2 = re.search(r'\b([1-6])\b', str(val))
    if m2:
        return f"CO{m2.group(1)}"
    return default

def parse_duration_to_minutes(dur_str: str) -> int:
    """Convert duration string (e.g. '3 Hours', '90 Minutes', '1.5 hrs') to minutes."""
    if not dur_str:
        return 180
    clean = str(dur_str).lower()
    m_hour = re.search(r'(\d+(?:\.\d+)?)\s*(?:hour|hr)', clean)
    if m_hour:
        return int(float(m_hour.group(1)) * 60)
    m_min = re.search(r'(\d+)\s*(?:min|minute)', clean)
    if m_min:
        return int(m_min.group(1))
    return 180

def detect_file_format(file_path: Path) -> str:
    """Detect whether uploaded template is docx, pdf, scanned_pdf, image, or xlsx."""
    suffix = file_path.suffix.lower()
    if suffix in [".docx", ".doc"]:
        return "docx"
    elif suffix in [".xlsx", ".xls", ".csv"]:
        return "xlsx"
    elif suffix in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        return "image"
    elif suffix == ".pdf":
        try:
            res = extract_pdf_text(file_path)
            if res.is_scanned_likely or len(res.text.strip()) < 120:
                return "scanned_pdf"
            return "pdf"
        except Exception:
            return "pdf"
    return "docx"


# =============================================================================
# DOCX TEMPLATE EXTRACTION
# =============================================================================

def extract_blueprint_from_docx(file_path: Path) -> Tuple[Dict[str, Any], Dict[str, float], str]:
    """
    Extract examination metadata, tables, sections, questions, marks, and CO/Bloom mappings
    from an institution Word (.docx) question paper template.
    """
    doc = docx.Document(str(file_path))
    
    # Gather all paragraph texts
    all_paras = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    full_text = "\n".join(all_paras)
    
    # Initialize Canonical Blueprint data
    blueprint = {
        "template_name": file_path.stem.replace("_", " ").title(),
        "institution": "Aarupadai Veedu Institute of Technology",
        "programme": "B.E. Computer Science and Engineering",
        "department": "Computer Science & Engineering",
        "course_code": "35021P28",
        "course_title": "R Programming",
        "exam_name": "Internal Assessment",
        "exam_type": "Internal Assessment",
        "duration_minutes": 90,
        "maximum_marks": 50,
        "instructions": [],
        "sections": []
    }
    
    conf = {
        "institution": 0.8,
        "course_information": 0.8,
        "section_names": 0.8,
        "question_numbering": 0.8,
        "marks": 0.8,
        "course_outcomes": 0.8,
        "bloom_levels": 0.8,
        "or_choices": 0.8,
        "total_marks": 0.8,
        "instructions": 0.8,
        "overall": 0.8
    }

    # 1. Parse institution and metadata from paragraphs or header table
    header_found = False
    for p in all_paras[:6]:
        if any(kw in p.upper() for kw in ["INSTITUTE", "UNIVERSITY", "COLLEGE", "ACADEMY", "POLYTECHNIC", "ENGINEERING"]):
            blueprint["institution"] = p.strip()
            conf["institution"] = 1.0
            header_found = True
            break

    # Look for department
    dept_m = re.search(r'DEPARTMENT\s+OF\s+([^\n\r,]+)', full_text, re.IGNORECASE)
    if dept_m:
        blueprint["department"] = dept_m.group(1).strip()
        blueprint["programme"] = f"B.E. {dept_m.group(1).strip()}"

    # Search for Course Code & Title
    cc_m = re.search(r'(?:Course|Subject)\s*Code\s*[:\-]?\s*([A-Z0-9]+)', full_text, re.IGNORECASE)
    if cc_m:
        blueprint["course_code"] = cc_m.group(1).strip()
        conf["course_information"] = 0.95

    ct_m = re.search(r'(?:Course|Subject)\s*(?:Title|Name)\s*[:\-]?\s*([^\n\r|]+)', full_text, re.IGNORECASE)
    if ct_m:
        blueprint["course_title"] = ct_m.group(1).strip()

    # Exam name
    ex_m = re.search(r'(Internal\s*Assessment(?:\s*[-–\s]*[I|II|III|1|2|3])?|Semester\s*End\s*Examination|End\s*Semester(?:\s*Degree)?\s*Examination|Mid\s*Term(?:\s*Examination)?)', full_text, re.IGNORECASE)
    if ex_m:
        blueprint["exam_name"] = ex_m.group(1).strip()
        blueprint["exam_type"] = "Semester End" if "Semester End" in blueprint["exam_name"] or "End Semester" in blueprint["exam_name"] else "Internal Assessment"

    # Max Marks
    mm_m = re.search(r'(?:Max(?:imum)?\.?\s*Marks|Marks)\s*[:\-]?\s*(\d{2,3})', full_text, re.IGNORECASE)
    if mm_m:
        blueprint["maximum_marks"] = int(mm_m.group(1))
        conf["total_marks"] = 0.95

    # Duration
    dur_m = re.search(r'(?:Duration|Time)\s*[:\-]?\s*([^\n\r|,]+)', full_text, re.IGNORECASE)
    if dur_m:
        blueprint["duration_minutes"] = parse_duration_to_minutes(dur_m.group(1))

    # Instructions
    inst_m = re.search(r'Instructions?\s*[:\-]?\s*(.*?)(?:PART|Part|Q\.No|\Z)', full_text, re.DOTALL | re.IGNORECASE)
    if inst_m:
        raw_inst = inst_m.group(1).strip()
        lines = [line.strip(" 1234567890.-*") for line in raw_inst.splitlines() if len(line.strip()) > 5]
        if lines:
            blueprint["instructions"] = lines
            conf["instructions"] = 0.95

    # 2. Inspect DOCX Tables for sections and questions
    sections_found = []
    
    # Also scan paragraphs for PART headers if separate tables are used for each part
    part_splits = []
    current_part_name = "Part A"
    
    for table_idx, table in enumerate(doc.tables):
        # Check if table has question header columns (Q.No, Question, CO, Bloom, Marks)
        if len(table.rows) < 2:
            continue

        header_cells = [c.text.strip().lower() for c in table.rows[0].cells]
        col_map = {}
        for idx, text in enumerate(header_cells):
            if any(k in text for k in ["q.no", "qno", "sl.no", "s.no", "question no", "q#"]):
                col_map["qno"] = idx
            elif any(k in text for k in ["question", "particulars", "description"]):
                col_map["question"] = idx
            elif any(k in text for k in ["co", "course outcome", "outcome"]):
                col_map["co"] = idx
            elif any(k in text for k in ["bloom", "btl", "k-level", "k level", "level"]):
                col_map["bloom"] = idx
            elif any(k in text for k in ["mark", "marks", "weightage"]):
                col_map["marks"] = idx

        # If this is a Question Table:
        if "qno" in col_map and "question" in col_map:
            # Check preceding paragraph for Section Name (e.g. PART A, PART B)
            sec_name = f"Part {chr(65 + len(sections_found))}"
            answer_rule = "Answer all questions"
            or_choice = False

            # Check table contents to identify questions
            parsed_questions = []
            current_or_pair = None

            for r_idx in range(1, len(table.rows)):
                row_cells = table.rows[r_idx].cells
                raw_qnum = row_cells[col_map["qno"]].text.strip()
                q_text = row_cells[col_map["question"]].text.strip()
                
                # Check for divider OR row
                if not raw_qnum and any(w in q_text.upper() for w in ["[OR]", " OR ", "(OR)"]):
                    or_choice = True
                    continue
                if any(w in raw_qnum.upper() for w in ["[OR]", " OR ", "(OR)"]):
                    or_choice = True
                    raw_qnum = re.sub(r'(?i)\[or\]|\(or\)|or', '', raw_qnum).strip()

                if not raw_qnum and not q_text:
                    continue

                # Parse Marks
                q_marks = 2
                if "marks" in col_map and col_map["marks"] < len(row_cells):
                    m_txt = row_cells[col_map["marks"]].text.strip()
                    m_digits = re.search(r'\d+', m_txt)
                    if m_digits:
                        q_marks = int(m_digits.group(0))

                # Parse CO
                q_co = "CO1"
                if "co" in col_map and col_map["co"] < len(row_cells):
                    q_co = normalize_co(row_cells[col_map["co"]].text.strip())

                # Parse Bloom
                q_bloom = "L2"
                if "bloom" in col_map and col_map["bloom"] < len(row_cells):
                    q_bloom = normalize_bloom(row_cells[col_map["bloom"]].text.strip())

                # Unit deduction from CO (CO1 -> Unit 1, etc.)
                unit_num = 1
                co_digits = re.search(r'\d+', q_co)
                if co_digits:
                    unit_num = int(co_digits.group(0))

                # Detect OR pair
                is_sub_a = "(a)" in raw_qnum.lower() or raw_qnum.lower().endswith("a")
                is_sub_b = "(b)" in raw_qnum.lower() or raw_qnum.lower().endswith("b")
                
                pair_id = None
                if is_sub_a or is_sub_b:
                    or_choice = True
                    base_num = re.sub(r'[^0-9]', '', raw_qnum) or str(len(parsed_questions) + 1)
                    pair_id = f"or_pair_{base_num}"

                # Infer question types from question text
                inferred_types = ["descriptive"] if q_marks > 2 else ["mcq_single"]
                if any(k in q_text.lower() for k in ["program", "code", "script", "function", "write an r", "write a c"]):
                    inferred_types = ["coding"] if q_marks > 2 else ["output_prediction"]
                elif any(k in q_text.lower() for k in ["predict the output", "what will be output"]):
                    inferred_types = ["output_prediction"]
                elif any(k in q_text.lower() for k in ["debug", "error", "correct"]):
                    inferred_types = ["debugging"]
                elif any(k in q_text.lower() for k in ["calculate", "numerical", "compute"]):
                    inferred_types = ["numerical"]
                elif any(k in q_text.lower() for k in ["case study", "scenario"]):
                    inferred_types = ["case_study"]

                slot = {
                    "question_number": raw_qnum or str(len(parsed_questions) + 1),
                    "or_pair_id": pair_id,
                    "question_types": inferred_types,
                    "unit": unit_num,
                    "co": q_co,
                    "bloom_level": q_bloom,
                    "marks": q_marks,
                    "confidence_score": 0.95
                }
                parsed_questions.append(slot)

            if parsed_questions:
                # Determine section answer rule
                if or_choice:
                    answer_rule = "Answer either (a) or (b) from each question"
                else:
                    answer_rule = "Answer all questions"

                marks_per_q = parsed_questions[0]["marks"] if parsed_questions else 2
                
                # Section total calculation:
                # If OR choice, each pair counts once
                if or_choice:
                    pairs_count = len(set(q.get("or_pair_id") for q in parsed_questions if q.get("or_pair_id")))
                    distinct_q = len(parsed_questions) - (pairs_count if pairs_count > 0 else 0)
                    sec_total = distinct_q * marks_per_q
                else:
                    sec_total = sum(q["marks"] for q in parsed_questions)

                sections_found.append({
                    "section_name": sec_name,
                    "answer_rule": answer_rule,
                    "start_question_number": int(re.sub(r'[^0-9]', '', parsed_questions[0]["question_number"]) or 1),
                    "question_count": len(parsed_questions),
                    "marks_per_question": marks_per_q,
                    "section_total": sec_total,
                    "or_choice": or_choice,
                    "questions": parsed_questions
                })

    # If sections were successfully parsed from tables
    if sections_found:
        blueprint["sections"] = sections_found
        conf["section_names"] = 0.95
        conf["question_numbering"] = 0.95
        conf["marks"] = 0.95
        conf["course_outcomes"] = 0.95
        conf["bloom_levels"] = 0.95
        conf["or_choices"] = 0.95
    else:
        # Fallback to standard section discovery from paragraph text
        blueprint["sections"] = fallback_parse_sections_from_text(full_text, blueprint["maximum_marks"])

    # Compute overall confidence
    conf["overall"] = round(sum(conf.values()) / len(conf), 2)
    return blueprint, conf, full_text


# =============================================================================
# TEXT-BASED PDF & OCR TEMPLATE EXTRACTION
# =============================================================================

def extract_blueprint_from_pdf(file_path: Path, use_ocr: bool = False) -> Tuple[Dict[str, Any], Dict[str, float], str]:
    """
    Extract examination metadata, tables, sections, questions, and CO/Bloom mappings
    from a text-based or scanned PDF template.
    """
    full_text = ""
    conf_penalty = 0.0

    if use_ocr:
        ocr_text, page_count, msg = run_ocr_on_pdf(file_path)
        full_text = ocr_text
        conf_penalty = 0.15 # OCR output requires faculty verification
    else:
        ext_res = extract_pdf_text(file_path)
        if ext_res.is_scanned_likely or len(ext_res.text.strip()) < 120:
            # Automatic OCR fallback if scanned
            ocr_text, _, _ = run_ocr_on_pdf(file_path)
            full_text = ocr_text if len(ocr_text.strip()) > len(ext_res.text.strip()) else ext_res.text
            conf_penalty = 0.20
        else:
            full_text = ext_res.text

    # Extract tables using pdfplumber if text-based
    plumber_tables = []
    if not use_ocr:
        try:
            with pdfplumber.open(str(file_path)) as pdf:
                for page in pdf.pages:
                    tabs = page.extract_tables()
                    for t in tabs:
                        if t and len(t) >= 2:
                            plumber_tables.append(t)
        except Exception as e:
            logger.debug(f"pdfplumber table extraction note: {e}")

    blueprint = {
        "template_name": file_path.stem.replace("_", " ").title(),
        "institution": "Aarupadai Veedu Institute of Technology",
        "programme": "B.E. Computer Science and Engineering",
        "department": "Computer Science & Engineering",
        "course_code": "35021P28",
        "course_title": "R Programming",
        "exam_name": "Internal Assessment",
        "exam_type": "Internal Assessment",
        "duration_minutes": 90,
        "maximum_marks": 50,
        "instructions": [],
        "sections": []
    }

    conf = {
        "institution": max(0.5, 0.85 - conf_penalty),
        "course_information": max(0.5, 0.85 - conf_penalty),
        "section_names": max(0.5, 0.80 - conf_penalty),
        "question_numbering": max(0.5, 0.80 - conf_penalty),
        "marks": max(0.5, 0.80 - conf_penalty),
        "course_outcomes": max(0.5, 0.80 - conf_penalty),
        "bloom_levels": max(0.5, 0.80 - conf_penalty),
        "or_choices": max(0.5, 0.80 - conf_penalty),
        "total_marks": max(0.5, 0.85 - conf_penalty),
        "instructions": max(0.5, 0.80 - conf_penalty),
        "overall": max(0.5, 0.82 - conf_penalty)
    }

    # 1. Parse Metadata with Regex
    lines = [l.strip() for l in full_text.splitlines() if l.strip()]

    # Institution name
    inst_match = re.search(r'([A-Z\s]{4,}(?:INSTITUTE|UNIVERSITY|COLLEGE|ENGINEERING|ACADEMY)[A-Z\s,]*)', full_text)
    if inst_match:
        blueprint["institution"] = inst_match.group(1).strip()
        conf["institution"] = round(0.95 - conf_penalty, 2)

    # Department
    dept_m = re.search(r'DEPARTMENT\s+OF\s+([^\n\r,]+)', full_text, re.IGNORECASE)
    if dept_m:
        blueprint["department"] = dept_m.group(1).strip()
        blueprint["programme"] = f"B.E. {dept_m.group(1).strip()}"

    # Course Code & Title
    cc_m = re.search(r'(?:Course|Subject)\s*Code\s*[:\-]?\s*([A-Z0-9]+)', full_text, re.IGNORECASE)
    if cc_m:
        blueprint["course_code"] = cc_m.group(1).strip()

    ct_m = re.search(r'(?:Course|Subject)\s*(?:Title|Name)\s*[:\-]?\s*([^\n\r|]+)', full_text, re.IGNORECASE)
    if ct_m:
        blueprint["course_title"] = ct_m.group(1).strip()

    # Exam name
    ex_m = re.search(r'(Internal\s*Assessment(?:\s*[-–\s]*[I|II|III|1|2|3])?|Semester\s*End\s*Examination|End\s*Semester(?:\s*Degree)?\s*Examination|Mid\s*Term(?:\s*Examination)?)', full_text, re.IGNORECASE)
    if ex_m:
        blueprint["exam_name"] = ex_m.group(1).strip()
        blueprint["exam_type"] = "Semester End" if "Semester End" in blueprint["exam_name"] or "End Semester" in blueprint["exam_name"] else "Internal Assessment"

    # Max Marks
    mm_m = re.search(r'(?:Max(?:imum)?\.?\s*Marks|Marks)\s*[:\-]?\s*(\d{2,3})', full_text, re.IGNORECASE)
    if mm_m:
        blueprint["maximum_marks"] = int(mm_m.group(1))

    # Duration
    dur_m = re.search(r'(?:Duration|Time)\s*[:\-]?\s*([^\n\r|,]+)', full_text, re.IGNORECASE)
    if dur_m:
        blueprint["duration_minutes"] = parse_duration_to_minutes(dur_m.group(1))

    # Instructions
    inst_m = re.search(r'Instructions?\s*[:\-]?\s*(.*?)(?:PART|Part|Q\.No|\Z)', full_text, re.DOTALL | re.IGNORECASE)
    if inst_m:
        raw_inst = inst_m.group(1).strip()
        ins_lines = [l.strip(" 1234567890.-*") for l in raw_inst.splitlines() if len(l.strip()) > 5]
        if ins_lines:
            blueprint["instructions"] = ins_lines

    # 2. Extract sections & questions from pdfplumber tables if available
    sections_found = []
    if plumber_tables:
        for tab in plumber_tables:
            hdr = [str(c or "").strip().lower() for c in tab[0]]
            col_map = {}
            for idx, text in enumerate(hdr):
                if any(k in text for k in ["q.no", "qno", "sl.no", "s.no"]):
                    col_map["qno"] = idx
                elif any(k in text for k in ["question", "particulars"]):
                    col_map["question"] = idx
                elif any(k in text for k in ["co", "outcome"]):
                    col_map["co"] = idx
                elif any(k in text for k in ["bloom", "btl", "level"]):
                    col_map["bloom"] = idx
                elif any(k in text for k in ["mark"]):
                    col_map["marks"] = idx

            if "qno" in col_map and "question" in col_map:
                sec_name = f"Part {chr(65 + len(sections_found))}"
                sec_qs = []
                or_choice = False

                for r in tab[1:]:
                    raw_q = str(r[col_map["qno"]] or "").strip()
                    q_text = str(r[col_map["question"]] or "").strip()
                    if not raw_q and any(w in q_text.upper() for w in ["[OR]", " OR "]):
                        or_choice = True
                        continue

                    if not raw_q and not q_text:
                        continue

                    q_marks = 2
                    if "marks" in col_map and col_map["marks"] < len(r):
                        m_digits = re.search(r'\d+', str(r[col_map["marks"]] or ""))
                        if m_digits:
                            q_marks = int(m_digits.group(0))

                    q_co = normalize_co(str(r[col_map.get("co", 0)] or "")) if "co" in col_map else "CO1"
                    q_bloom = normalize_bloom(str(r[col_map.get("bloom", 0)] or "")) if "bloom" in col_map else "L2"
                    
                    unit_num = 1
                    co_digits = re.search(r'\d+', q_co)
                    if co_digits:
                        unit_num = int(co_digits.group(0))

                    pair_id = None
                    if "(a)" in raw_q.lower() or "(b)" in raw_q.lower():
                        or_choice = True
                        b_num = re.sub(r'[^0-9]', '', raw_q) or str(len(sec_qs) + 1)
                        pair_id = f"or_pair_{b_num}"

                    sec_qs.append({
                        "question_number": raw_q or str(len(sec_qs) + 1),
                        "or_pair_id": pair_id,
                        "question_types": ["descriptive"] if q_marks > 2 else ["mcq_single"],
                        "unit": unit_num,
                        "co": q_co,
                        "bloom_level": q_bloom,
                        "marks": q_marks,
                        "confidence_score": round(0.90 - conf_penalty, 2)
                    })

                if sec_qs:
                    marks_each = sec_qs[0]["marks"]
                    sections_found.append({
                        "section_name": sec_name,
                        "answer_rule": "Answer either (a) or (b)" if or_choice else "Answer all questions",
                        "start_question_number": int(re.sub(r'[^0-9]', '', sec_qs[0]["question_number"]) or 1),
                        "question_count": len(sec_qs),
                        "marks_per_question": marks_each,
                        "section_total": sum(q["marks"] for q in sec_qs) if not or_choice else (len(sec_qs) // 2) * marks_each,
                        "or_choice": or_choice,
                        "questions": sec_qs
                    })

    if sections_found:
        blueprint["sections"] = sections_found
    else:
        blueprint["sections"] = fallback_parse_sections_from_text(full_text, blueprint["maximum_marks"])

    conf["overall"] = round(sum(conf.values()) / len(conf), 2)
    return blueprint, conf, full_text


# =============================================================================
# IMAGE / SCANNED OCR TEMPLATE EXTRACTION
# =============================================================================

def extract_blueprint_from_image(file_path: Path) -> Tuple[Dict[str, Any], Dict[str, float], str]:
    """
    Extract blueprint from an uploaded image (PNG/JPG) using Tesseract OCR.
    """
    if not is_tesseract_available():
        logger.warning("Tesseract not available for image template extraction. Using standard structured fallback.")
        blueprint = create_standard_template_fallback(file_path.stem)
        conf = {k: 0.50 for k in ["institution", "course_information", "section_names", "question_numbering", "marks", "course_outcomes", "bloom_levels", "or_choices", "total_marks", "instructions", "overall"]}
        return blueprint, conf, "OCR binary not found on host."

    import pytesseract
    from PIL import Image

    try:
        img = Image.open(str(file_path))
        text = pytesseract.image_to_string(img, lang="eng")
    except Exception as e:
        logger.error(f"Image OCR failed: {e}")
        text = ""

    # Parse text with OCR penalty
    blueprint = {
        "template_name": file_path.stem.replace("_", " ").title(),
        "institution": "Aarupadai Veedu Institute of Technology",
        "programme": "B.E. Computer Science and Engineering",
        "department": "Computer Science & Engineering",
        "course_code": "35021P28",
        "course_title": "R Programming",
        "exam_name": "Internal Assessment",
        "exam_type": "Internal Assessment",
        "duration_minutes": 90,
        "maximum_marks": 50,
        "instructions": [],
        "sections": []
    }

    conf = {
        "institution": 0.65,
        "course_information": 0.65,
        "section_names": 0.60,
        "question_numbering": 0.60,
        "marks": 0.60,
        "course_outcomes": 0.60,
        "bloom_levels": 0.60,
        "or_choices": 0.60,
        "total_marks": 0.65,
        "instructions": 0.60,
        "overall": 0.62
    }

    # Extract max marks
    mm_m = re.search(r'(?:Max(?:imum)?\.?\s*Marks|Marks)\s*[:\-]?\s*(\d{2,3})', text, re.IGNORECASE)
    if mm_m:
        blueprint["maximum_marks"] = int(mm_m.group(1))

    # Parse sections from text
    blueprint["sections"] = fallback_parse_sections_from_text(text, blueprint["maximum_marks"])
    return blueprint, conf, text


# =============================================================================
# EXCEL (XLSX) BLUEPRINT EXTRACTION
# =============================================================================

def extract_blueprint_from_xlsx(file_path: Path) -> Tuple[Dict[str, Any], Dict[str, float], str]:
    """
    Extract blueprint structure from an Excel (.xlsx) file with sheet table mapping.
    """
    import pandas as pd
    df = pd.read_excel(str(file_path))
    
    blueprint = {
        "template_name": file_path.stem.replace("_", " ").title(),
        "institution": "Aarupadai Veedu Institute of Technology",
        "programme": "B.E. Computer Science and Engineering",
        "department": "Computer Science & Engineering",
        "course_code": "35021P28",
        "course_title": "R Programming",
        "exam_name": "Internal Assessment",
        "exam_type": "Internal Assessment",
        "duration_minutes": 90,
        "maximum_marks": 50,
        "instructions": ["Answer all questions according to section rules."],
        "sections": []
    }

    conf = {k: 0.95 for k in ["institution", "course_information", "section_names", "question_numbering", "marks", "course_outcomes", "bloom_levels", "or_choices", "total_marks", "instructions", "overall"]}

    # Identify columns
    col_lower = {str(c).strip().lower(): c for c in df.columns}
    
    sec_col = next((col_lower[k] for k in col_lower if "sec" in k or "part" in k), None)
    qno_col = next((col_lower[k] for k in col_lower if "q" in k and "no" in k), None)
    marks_col = next((col_lower[k] for k in col_lower if "mark" in k), None)
    co_col = next((col_lower[k] for k in col_lower if "co" in k or "outcome" in k), None)
    bloom_col = next((col_lower[k] for k in col_lower if "bloom" in k or "level" in k or "btl" in k), None)
    unit_col = next((col_lower[k] for k in col_lower if "unit" in k), None)
    type_col = next((col_lower[k] for k in col_lower if "type" in k), None)

    if not qno_col:
        # Fallback to standard
        return fallback_parse_sections_from_text(df.to_string(), 50), conf, df.to_string()

    sections_dict = {}
    current_sec = "Part A"

    for _, row in df.iterrows():
        if sec_col and pd.notna(row[sec_col]):
            val = str(row[sec_col]).strip()
            if val:
                current_sec = val

        if current_sec not in sections_dict:
            sections_dict[current_sec] = []

        q_num = str(row[qno_col]).strip() if pd.notna(row[qno_col]) else str(len(sections_dict[current_sec]) + 1)
        m_val = int(row[marks_col]) if marks_col and pd.notna(row[marks_col]) and str(row[marks_col]).isdigit() else 2
        co_val = normalize_co(str(row[co_col])) if co_col and pd.notna(row[co_col]) else "CO1"
        bl_val = normalize_bloom(str(row[bloom_col])) if bloom_col and pd.notna(row[bloom_col]) else "L2"
        u_val = int(row[unit_col]) if unit_col and pd.notna(row[unit_col]) and str(row[unit_col]).isdigit() else 1
        
        types_val = ["short_answer"]
        if type_col and pd.notna(row[type_col]):
            t_str = str(row[type_col]).strip().lower()
            types_val = [t.strip() for t in t_str.split(",") if t.strip()]

        pair_id = None
        if "(a)" in q_num.lower() or "(b)" in q_num.lower():
            b_digits = re.sub(r'[^0-9]', '', q_num) or "1"
            pair_id = f"or_pair_{b_digits}"

        sections_dict[current_sec].append({
            "question_number": q_num,
            "or_pair_id": pair_id,
            "question_types": types_val,
            "unit": u_val,
            "co": co_val,
            "bloom_level": bl_val,
            "marks": m_val,
            "confidence_score": 1.0
        })

    sections_list = []
    tot_marks = 0
    for s_name, qs in sections_dict.items():
        or_choice = any(q.get("or_pair_id") for q in qs)
        marks_each = qs[0]["marks"] if qs else 2
        
        if or_choice:
            pairs_cnt = len(set(q.get("or_pair_id") for q in qs if q.get("or_pair_id")))
            sec_tot = pairs_cnt * marks_each
        else:
            sec_tot = sum(q["marks"] for q in qs)

        tot_marks += sec_tot
        sections_list.append({
            "section_name": s_name,
            "answer_rule": "Answer either (a) or (b)" if or_choice else "Answer all questions",
            "start_question_number": int(re.sub(r'[^0-9]', '', qs[0]["question_number"]) or 1),
            "question_count": len(qs),
            "marks_per_question": marks_each,
            "section_total": sec_tot,
            "or_choice": or_choice,
            "questions": qs
        })

    blueprint["sections"] = sections_list
    blueprint["maximum_marks"] = tot_marks or 50
    return blueprint, conf, df.to_string()


# =============================================================================
# HELPER: FALLBACK TEXT PARSER FOR UNIVERSITY FORMATS
# =============================================================================

def fallback_parse_sections_from_text(text: str, max_marks: int = 50) -> List[Dict[str, Any]]:
    """
    Intelligent university pattern fallback for 50-mark or 100-mark structures
    when table lines are unformatted or OCR degraded.
    """
    if max_marks == 50:
        # Part A: 5 questions x 2 marks = 10 marks
        part_a_qs = [
            {"question_number": str(i + 1), "or_pair_id": None, "question_types": ["mcq_single"], "unit": (i % 3) + 1, "co": f"CO{(i % 3) + 1}", "bloom_level": "L2", "marks": 2, "confidence_score": 0.85}
            for i in range(5)
        ]
        # Part B: 4 questions x 5 marks = 20 marks
        part_b_qs = [
            {"question_number": str(i + 6), "or_pair_id": None, "question_types": ["descriptive"], "unit": (i % 3) + 1, "co": f"CO{(i % 3) + 1}", "bloom_level": "L3", "marks": 5, "confidence_score": 0.85}
            for i in range(4)
        ]
        # Part C: 2 OR pairs x 10 marks = 20 marks
        part_c_qs = [
            {"question_number": "10(a)", "or_pair_id": "or_pair_10", "question_types": ["coding", "descriptive"], "unit": 2, "co": "CO2", "bloom_level": "L3", "marks": 10, "confidence_score": 0.85},
            {"question_number": "10(b)", "or_pair_id": "or_pair_10", "question_types": ["coding", "descriptive"], "unit": 2, "co": "CO2", "bloom_level": "L3", "marks": 10, "confidence_score": 0.85},
            {"question_number": "11(a)", "or_pair_id": "or_pair_11", "question_types": ["coding", "descriptive"], "unit": 3, "co": "CO3", "bloom_level": "L4", "marks": 10, "confidence_score": 0.85},
            {"question_number": "11(b)", "or_pair_id": "or_pair_11", "question_types": ["coding", "descriptive"], "unit": 3, "co": "CO3", "bloom_level": "L4", "marks": 10, "confidence_score": 0.85}
        ]

        return [
            {"section_name": "Part A", "answer_rule": "Answer all questions", "start_question_number": 1, "question_count": 5, "marks_per_question": 2, "section_total": 10, "or_choice": False, "questions": part_a_qs},
            {"section_name": "Part B", "answer_rule": "Answer all questions", "start_question_number": 6, "question_count": 4, "marks_per_question": 5, "section_total": 20, "or_choice": False, "questions": part_b_qs},
            {"section_name": "Part C", "answer_rule": "Answer either (a) or (b)", "start_question_number": 10, "question_count": 4, "marks_per_question": 10, "section_total": 20, "or_choice": True, "questions": part_c_qs}
        ]
    else:
        # Standard 100 Marks Format (Parts A, B, C)
        part_a_qs = [
            {"question_number": str(i + 1), "or_pair_id": None, "question_types": ["mcq_single"], "unit": (i % 5) + 1, "co": f"CO{(i % 5) + 1}", "bloom_level": "L1" if i % 2 == 0 else "L2", "marks": 2, "confidence_score": 0.90}
            for i in range(10)
        ]
        
        part_b_qs = []
        for i in range(5):
            q_num_base = 11 + i
            u = i + 1
            co = f"CO{u}"
            part_b_qs.append({"question_number": f"{q_num_base}(a)", "or_pair_id": f"or_pair_{q_num_base}", "question_types": ["coding", "descriptive"], "unit": u, "co": co, "bloom_level": "L3" if i < 3 else "L4", "marks": 13, "confidence_score": 0.90})
            part_b_qs.append({"question_number": f"{q_num_base}(b)", "or_pair_id": f"or_pair_{q_num_base}", "question_types": ["coding", "descriptive"], "unit": u, "co": co, "bloom_level": "L3" if i < 3 else "L4", "marks": 13, "confidence_score": 0.90})

        part_c_qs = [
            {"question_number": "16", "or_pair_id": None, "question_types": ["case_study", "design"], "unit": 5, "co": "CO5", "bloom_level": "L6", "marks": 15, "confidence_score": 0.90}
        ]

        return [
            {"section_name": "Part A", "answer_rule": "Answer all questions", "start_question_number": 1, "question_count": 10, "marks_per_question": 2, "section_total": 20, "or_choice": False, "questions": part_a_qs},
            {"section_name": "Part B", "answer_rule": "Answer either (a) or (b)", "start_question_number": 11, "question_count": 10, "marks_per_question": 13, "section_total": 65, "or_choice": True, "questions": part_b_qs},
            {"section_name": "Part C", "answer_rule": "Answer the comprehensive design question", "start_question_number": 16, "question_count": 1, "marks_per_question": 15, "section_total": 15, "or_choice": False, "questions": part_c_qs}
        ]

def create_standard_template_fallback(template_name: str) -> Dict[str, Any]:
    """Create a fully standard 50-mark template fallback."""
    return {
        "template_name": template_name.replace("_", " ").title(),
        "institution": "Aarupadai Veedu Institute of Technology",
        "programme": "B.E. Computer Science and Engineering",
        "department": "Computer Science & Engineering",
        "course_code": "35021P28",
        "course_title": "R Programming",
        "exam_name": "Internal Assessment",
        "exam_type": "Internal Assessment",
        "duration_minutes": 90,
        "maximum_marks": 50,
        "instructions": ["Answer all questions in Part A.", "Answer either (a) or (b) from each question in Part B."],
        "sections": fallback_parse_sections_from_text("", 50)
    }


# =============================================================================
# BLUEPRINT VALIDATION ENGINE (Specification B6)
# =============================================================================

def validate_extracted_blueprint(
    blueprint_data: Dict[str, Any],
    syllabus_cos: Optional[List[str]] = None,
    syllabus_units: Optional[List[int]] = None
) -> Dict[str, Any]:
    """
    Validate extracted or faculty-edited blueprint against all Specification B6 rules:
    - Total marks equal maximum marks.
    - Section totals are correct.
    - Question numbering is complete without duplicates.
    - OR pairs are correctly detected and both sides have EQUAL marks.
    - CO values exist in syllabus.
    - Bloom levels are valid (L1-L6).
    - Mandatory metadata is present.
    - No mark is negative or zero.
    - Instructions match answer rule.
    Separates blocking errors from non-blocking warnings.
    """
    errors = []
    warnings = []

    # 1. Metadata check
    target_max = blueprint_data.get("maximum_marks", 100)
    if not blueprint_data.get("institution"):
        errors.append("Institution name is required.")
    if not blueprint_data.get("course_code"):
        warnings.append("Course code is missing in blueprint metadata.")
    if not blueprint_data.get("course_title"):
        warnings.append("Course title is missing in blueprint metadata.")

    sections = blueprint_data.get("sections", [])
    if not sections:
        errors.append("Blueprint must have at least one section.")
        return {
            "is_valid": False,
            "errors": errors,
            "warnings": warnings,
            "calculated_total_marks": 0,
            "target_maximum_marks": target_max,
            "reconciled": False
        }

    calculated_grand_total = 0
    seen_qnums = set()

    for sec_idx, sec in enumerate(sections):
        sec_name = sec.get("section_name", f"Section {sec_idx + 1}")
        sec_total = sec.get("section_total", 0)
        or_choice = sec.get("or_choice", False)
        questions = sec.get("questions", [])

        if not questions:
            errors.append(f"{sec_name} has no question slots configured.")
            continue

        # Check section totals
        if or_choice:
            # Group by or_pair_id
            pairs = {}
            unpaired = []
            for q in questions:
                pid = q.get("or_pair_id")
                if not pid and ("(a)" in str(q.get("question_number", "")).lower() or "(b)" in str(q.get("question_number", "")).lower() or q.get("or_pair_with")):
                    b_num = re.sub(r'[^0-9]', '', str(q.get("question_number", ""))) or "1"
                    pid = f"or_pair_{b_num}"
                if pid:
                    pairs.setdefault(pid, []).append(q)
                else:
                    unpaired.append(q)

            # Validate each OR pair
            for pid, p_qs in pairs.items():
                if len(p_qs) < 2:
                    warnings.append(f"{sec_name}: OR pair '{pid}' has only 1 question option configured.")
                elif len(p_qs) == 2:
                    q_a, q_b = p_qs[0], p_qs[1]
                    # Parity of marks check
                    if q_a.get("marks") != q_b.get("marks"):
                        errors.append(
                            f"{sec_name}: Both sides of OR pair '{pid}' must have equal marks. "
                            f"Found {q_a.get('question_number')} ({q_a.get('marks')}M) and "
                            f"{q_b.get('question_number')} ({q_b.get('marks')}M)."
                        )
                    # Parity of cognitive demand warning
                    if q_a.get("bloom_level") != q_b.get("bloom_level"):
                        warnings.append(
                            f"{sec_name}: OR pair '{pid}' questions have differing Bloom levels "
                            f"({q_a.get('bloom_level')} vs {q_b.get('bloom_level')}). Comparable cognitive demand is recommended."
                        )

            # Sum of effective marks for this section
            sec_effective_marks = sum(p_qs[0].get("marks", 0) for p_qs in pairs.values() if p_qs) + sum(q.get("marks", 0) for q in unpaired)
            calculated_grand_total += sec_effective_marks

            if sec_effective_marks != sec_total:
                warnings.append(f"{sec_name}: Specified section total ({sec_total}M) does not match calculated effective marks ({sec_effective_marks}M).")
        else:
            sec_effective_marks = sum(q.get("marks", 0) for q in questions)
            calculated_grand_total += sec_effective_marks
            if sec_effective_marks != sec_total:
                warnings.append(f"{sec_name}: Specified section total ({sec_total}M) does not match sum of question marks ({sec_effective_marks}M).")

        # Check individual question slots
        for q in questions:
            q_num = str(q.get("question_number", "")).strip()
            if not q_num:
                errors.append(f"{sec_name}: Found question slot with empty question number.")
            elif q_num in seen_qnums:
                errors.append(f"{sec_name}: Duplicate question number '{q_num}' found in blueprint.")
            else:
                seen_qnums.add(q_num)

            q_marks = q.get("marks", 0)
            if q_marks <= 0:
                errors.append(f"{sec_name}, Question {q_num}: Marks value must be greater than zero.")

            # Bloom check
            bl = str(q.get("bloom_level", "")).upper()
            if not any(bl.startswith(p) for p in ["L1", "L2", "L3", "L4", "L5", "L6", "K1", "K2", "K3", "K4", "K5", "K6"]):
                errors.append(f"{sec_name}, Question {q_num}: Invalid Bloom / K-level '{bl}'.")

            # Syllabus CO check if syllabus provided
            q_co = str(q.get("co", "")).upper()
            if syllabus_cos and q_co not in syllabus_cos:
                warnings.append(f"{sec_name}, Question {q_num}: Course outcome '{q_co}' is not listed in the selected syllabus.")

            # Syllabus Unit check
            q_unit = q.get("unit")
            if syllabus_units and q_unit and int(q_unit) not in syllabus_units:
                warnings.append(f"{sec_name}, Question {q_num}: Unit {q_unit} does not exist in the selected syllabus.")

            # Question types
            q_types = q.get("question_types", [])
            if not q_types:
                errors.append(f"{sec_name}, Question {q_num}: At least one question type must be selected.")

    # Total Marks Reconciliation
    if calculated_grand_total != target_max:
        errors.append(
            f"Total calculated blueprint marks ({calculated_grand_total}) do not reconcile with target maximum marks ({target_max})."
        )

    is_valid = len(errors) == 0

    return {
        "is_valid": is_valid,
        "errors": errors,
        "warnings": warnings,
        "calculated_total_marks": calculated_grand_total,
        "target_maximum_marks": target_max,
        "reconciled": (calculated_grand_total == target_max)
    }


# =============================================================================
# UNIFIED DISPATCHER
# =============================================================================

def extract_blueprint_from_file(
    file_path: Path,
    file_format: Optional[str] = None
) -> Tuple[Dict[str, Any], Dict[str, float], str]:
    """
    Main extraction pipeline dispatcher based on detected or supplied file format.
    """
    fmt = file_format or detect_file_format(file_path)
    logger.info(f"Extracting blueprint from {file_path.name} with format {fmt}")

    if fmt == "docx":
        return extract_blueprint_from_docx(file_path)
    elif fmt == "xlsx":
        return extract_blueprint_from_xlsx(file_path)
    elif fmt == "scanned_pdf":
        return extract_blueprint_from_pdf(file_path, use_ocr=True)
    elif fmt == "image":
        return extract_blueprint_from_image(file_path)
    else: # "pdf"
        return extract_blueprint_from_pdf(file_path, use_ocr=False)
