import re
from typing import List, Dict, Any

BLOOM_VERBS = {
    "L1": ["define", "list", "state", "identify", "recall", "name", "label", "recognize", "mention"],
    "L2": ["explain", "describe", "discuss", "illustrate", "distinguish", "classify", "summarize", "interpret"],
    "L3": ["apply", "demonstrate", "calculate", "solve", "implement", "compute", "modify", "use", "determine"],
    "L4": ["analyze", "compare", "contrast", "differentiate", "examine", "investigate", "categorize", "separate"],
    "L5": ["evaluate", "justify", "assess", "appraise", "critique", "validate", "recommend", "verify"],
    "L6": ["design", "create", "construct", "formulate", "develop", "devise", "integrate", "synthesize"]
}

def detect_bloom_level(text: str) -> str:
    """Detect Bloom's taxonomy cognitive level from text based on action verbs."""
    text_lower = text.lower()
    
    # Check for explicit level notation like (L2), (K3), (BL - L2), (BTL 3)
    match = re.search(r'\b(?:L|K|BTL|BL)\s*[-:]?\s*([1-6])\b', text, re.IGNORECASE)
    if match:
        lvl_num = match.group(1)
        names = {
            "1": "L1 - Remember",
            "2": "L2 - Understand",
            "3": "L3 - Apply",
            "4": "L4 - Analyze",
            "5": "L5 - Evaluate",
            "6": "L6 - Create"
        }
        return names.get(lvl_num, f"L{lvl_num}")

    # Check action verbs
    for lvl, verbs in reversed(list(BLOOM_VERBS.items())):
        for verb in verbs:
            if re.search(r'\b' + re.escape(verb) + r'\b', text_lower):
                names = {
                    "L1": "L1 - Remember",
                    "2": "L2 - Understand",
                    "3": "L3 - Apply",
                    "4": "L4 - Analyze",
                    "5": "L5 - Evaluate",
                    "6": "L6 - Create"
                }
                return names.get(lvl, lvl)

    return "L2 - Understand"

def extract_course_outcomes(syllabus_text: str) -> List[Dict[str, Any]]:
    """
    Extract Course Outcomes (CO1, CO2, etc.) from syllabus text.
    If explicitly declared in the syllabus, parses them accurately.
    If not explicitly declared, auto-infers COs from course units.
    """
    outcomes = []
    lines = [line.strip() for line in syllabus_text.splitlines() if line.strip()]

    # 1. Look for explicit CO patterns like:
    # CO1: Understand ..., CO 1 - Explain ..., CO1. Apply ...
    co_pattern = re.compile(r'^(?:[\*\-•\s]*)?\b(CO\s*[1-6]|Course\s*Outcome\s*[1-6])[:\.\-\s]+(.+)$', re.IGNORECASE)
    
    in_co_section = False
    for line in lines:
        if re.search(r'\b(?:course\s*outcomes?|course\s*learning\s*outcomes?|c\.o\.s?)\b', line, re.IGNORECASE):
            in_co_section = True
            continue

        if in_co_section and re.search(r'\b(?:syllabus|mapping|text\s*books?|references?|course\s*designers?|prerequisite|curriculum)\b', line, re.IGNORECASE):
            in_co_section = False
            continue

        match = co_pattern.match(line)
        if match:
            raw_co = match.group(1).upper()
            co_id = re.sub(r'[^0-9]', '', raw_co)
            co_code = f"CO{co_id}" if co_id else "CO1"
            desc = match.group(2).strip()
            bloom = detect_bloom_level(desc)
            outcomes.append({
                "code": co_code,
                "description": desc,
                "bloom_level": bloom
            })
        elif in_co_section and outcomes and len(line) > 10 and not line.lower().startswith(('module', 'unit', 'text', 'reference')):
            # Check for numbered list under Course Outcomes section: e.g. "1. Analyze..."
            num_match = re.match(r'^(?:[1-6])[\.\)]\s*(.+)$', line)
            if num_match and len(outcomes) < 6:
                co_code = f"CO{len(outcomes) + 1}"
                desc = num_match.group(1).strip()
                bloom = detect_bloom_level(desc)
                # Avoid duplicates
                if not any(o["code"] == co_code for o in outcomes):
                    outcomes.append({
                        "code": co_code,
                        "description": desc,
                        "bloom_level": bloom
                    })

    # 2. If no explicit COs found or fewer than 3, infer from Units / Modules
    if len(outcomes) < 3:
        units = extract_syllabus_units(syllabus_text)
        if units:
            inferred = []
            default_blooms = ["L1 - Remember", "L2 - Understand", "L3 - Apply", "L4 - Analyze", "L5 - Evaluate", "L6 - Create"]
            for idx, unit in enumerate(units[:6], start=1):
                bloom = default_blooms[min(idx, len(default_blooms) - 1)]
                verb = "Understand" if idx <= 2 else ("Apply" if idx == 3 else ("Analyze" if idx == 4 else "Evaluate and design"))
                inferred.append({
                    "code": f"CO{idx}",
                    "description": f"{verb} fundamental concepts, methodologies, and problem-solving techniques in {unit['title']}.",
                    "bloom_level": bloom,
                    "unit_title": unit['title']
                })
            return inferred

    # Fallback standard outcomes if completely empty
    if not outcomes:
        return [
            {"code": "CO1", "description": "Recall and understand fundamental principles and theoretical foundations.", "bloom_level": "L2 - Understand"},
            {"code": "CO2", "description": "Apply algorithmic techniques and formal models to solve real-world problems.", "bloom_level": "L3 - Apply"},
            {"code": "CO3", "description": "Analyze performance efficiency, trade-offs, and computational complexity.", "bloom_level": "L4 - Analyze"},
            {"code": "CO4", "description": "Evaluate contemporary methodologies, frameworks, and system architectures.", "bloom_level": "L5 - Evaluate"},
            {"code": "CO5", "description": "Design and construct modular, scalable, and optimized engineering solutions.", "bloom_level": "L6 - Create"}
        ]

    # Deduplicate by code and sort
    seen = set()
    deduped = []
    for o in outcomes:
        if o["code"] not in seen:
            seen.add(o["code"])
            deduped.append(o)

    deduped.sort(key=lambda x: int(re.sub(r'[^0-9]', '', x["code"]) or 0))
    return deduped

def extract_syllabus_units(syllabus_text: str) -> List[Dict[str, Any]]:
    """Extract units or modules with their titles and associated topics."""
    clean = re.sub(r'--- Page \d+ ---', '', syllabus_text)
    clean = clean.replace('\ufffd', ' • ')
    
    # 1. First try standard UNIT/MODULE regex
    unit_regex = re.compile(r'^(?:(?:UNIT|MODULE|CHAPTER|PART)\s*[-–:]?\s*([0-9IVX]+)|([0-9IVX]+)\s*[-–:]\s*(?:UNIT|MODULE))[:\s\-]*(.*)$', re.IGNORECASE)
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    units = []
    current_unit = None
    current_content = []

    for line in lines:
        # Ignore textbook/reference section
        if re.search(r'^(?:text\s*books?|reference\s*books?|references?)\b', line, re.IGNORECASE):
            break

        match = unit_regex.match(line)
        if match:
            if current_unit:
                u_n = str(current_unit["number"])
                u_t = current_unit["title"] or f"Unit {u_n}"
                units.append({
                    "number": u_n,
                    "title": u_t,
                    "topics": " ".join(current_content).strip()
                })
            unit_num = match.group(1) or match.group(2)
            title = match.group(3).strip() if match.group(3) else f"Unit {unit_num}"
            current_unit = {"number": unit_num, "title": title}
            current_content = []
        elif current_unit:
            current_content.append(line)

    if current_unit:
        u_n = str(current_unit["number"])
        u_t = current_unit["title"] or f"Unit {u_n}"
        units.append({
            "number": u_n,
            "title": u_t,
            "topics": " ".join(current_content).strip()
        })

    if units:
        return units

    # 2. Look for SYLLABUS block with capitalized module headings
    syl_match = re.search(r'\bSYLLABUS\b(.*?)(?=\b(?:TEXT\s*BOOKS?|REFERENCES?)\b|$)', clean, re.DOTALL | re.IGNORECASE)
    if syl_match:
        syl_body = syl_match.group(1).strip()
        lines = [l.strip() for l in syl_body.splitlines() if l.strip()]
        unit_idx = 1
        curr_title = ''
        curr_body = []
        for l in lines:
            if l.isupper() and 2 < len(l) < 60 and not any(k in l for k in ['PO1', 'PSO', 'STRONG', 'MEDIUM', 'LOW']):
                if curr_title:
                    units.append({
                        "number": str(unit_idx),
                        "title": curr_title.title(),
                        "topics": " ".join(curr_body).strip()
                    })
                    unit_idx += 1
                curr_title = l
                curr_body = []
            elif curr_title:
                curr_body.append(l)
        if curr_title:
            units.append({
                "number": str(unit_idx),
                "title": curr_title.title(),
                "topics": " ".join(curr_body).strip()
            })

    # 3. Fallback to logical paragraphs if still empty
    if not units:
        clean_text = re.sub(r'(?:text\s*books?|references?).*$', '', clean, flags=re.IGNORECASE | re.DOTALL)
        paragraphs = [p.strip() for p in clean_text.split("\n\n") if len(p.strip()) > 30 and not any(k in p for k in ['PO1', 'PSO', 'STRONG', 'MEDIUM', 'LOW'])]
        for idx, p in enumerate(paragraphs[:5], start=1):
            first_line = p.splitlines()[0]
            title = first_line[:60].strip()
            units.append({
                "number": str(idx),
                "title": title or f"Unit {idx}",
                "topics": p
            })

    return units
