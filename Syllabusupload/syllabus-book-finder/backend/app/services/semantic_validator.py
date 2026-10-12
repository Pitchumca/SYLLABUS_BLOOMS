import re
import json
from typing import Dict, Any, List, Tuple, Optional
from app.services.grammar_validator import validate_question_grammar, validate_option_grammar

BLOOM_ACTION_VERBS = {
    "L1 - Remember": ["define", "identify", "list", "name", "recall", "state", "recognize", "select", "which", "what", "give"],
    "L2 - Understand": ["explain", "describe", "distinguish", "interpret", "summarize", "classify", "illustrate", "compare", "discuss", "outline", "what", "which", "how"],
    "L3 - Apply": ["apply", "calculate", "demonstrate", "implement", "execute", "solve", "use", "construct", "write", "compute", "perform", "show"],
    "L4 - Analyze": ["analyze", "analyse", "compare", "differentiate", "examine", "investigate", "decompose", "contrast", "infer", "distinguish", "deconstruct"],
    "L5 - Evaluate": ["evaluate", "justify", "assess", "critique", "recommend", "defend", "validate", "prioritize", "appraise"],
    "L6 - Create": ["design", "develop", "formulate", "construct", "create", "propose", "integrate", "devise", "synthesize"]
}

def validate_bloom_alignment(question_text: str, assigned_bloom: str) -> Tuple[float, Optional[str]]:
    """Verify that action verb and cognitive demand match assigned Bloom level."""
    text_lower = question_text.lower()
    norm_assigned = assigned_bloom[:2].upper() if len(assigned_bloom) >= 2 else "L2"
    
    expected_verbs = []
    for k, v in BLOOM_ACTION_VERBS.items():
        if k.startswith(norm_assigned):
            expected_verbs = v
            break
            
    has_expected_verb = any(re.search(r'\b' + re.escape(v) + r'\b', text_lower) for v in expected_verbs)
    
    if has_expected_verb:
        return 95.0, None
    
    # Check if a verb from adjacent level is used
    for k, v in BLOOM_ACTION_VERBS.items():
        if any(re.search(r'\b' + re.escape(verb) + r'\b', text_lower) for verb in v):
            detected_level = k[:2]
            if abs(int(detected_level[1]) - int(norm_assigned[1])) <= 1:
                return 88.0, None
            else:
                return 72.0, f"Question action verb suggests {k} but was assigned {assigned_bloom}."
                
    # If no explicit verb matched, check general phrasing
    return 86.0, None

def validate_marks_suitability(marks: int, question_text: str, question_type: str) -> Tuple[float, Optional[str]]:
    """Validate that expected depth matches the allocated marks."""
    words = len(question_text.split())
    
    if marks <= 2:
        # 1-2 marks: definition, identify, syntax recognition, simple output
        if question_type in ["mcq", "multiple_select", "true_false", "fill_blank", "very_short_answer"]:
            return 98.0, None
        if words > 45:
            return 82.0, "1-2 mark question appears excessively verbose for a short-answer format."
        return 94.0, None
        
    elif marks <= 5:
        # 3-5 marks: brief explanation, small code segment, comparison
        if words < 8:
            return 78.0, "3-5 mark question stem lacks sufficient detail or context."
        return 92.0, None
        
    elif marks <= 13:
        # 8-13 marks: multi-step explanation, program with explanation, worked example
        if words < 12:
            return 75.0, "8-13 mark question is too brief; high-mark questions require multi-part or structured tasks."
        if question_type == "mcq":
            return 60.0, "MCQ format is generally unsuitable for high-mark (8-13m) questions."
        return 94.0, None
        
    else:
        # 15-16 marks (Part C): integrated problem, case study, complete analytical workflow, design
        if words < 18:
            return 70.0, "Part C (15-16m) question lacks comprehensive scope required for design/evaluation."
        return 95.0, None

def validate_mcq_structure(question_dict: Dict[str, Any]) -> Tuple[bool, float, float, List[str]]:
    """
    Validate MCQ structural completeness, option uniqueness, labels, and option grammar.
    Returns:
      (is_structurally_valid: bool, structural_score: float, option_grammar_score: float, issues: List[str])
    """
    issues = []
    options_json = question_dict.get("options_json")
    if not options_json:
        return False, 0.0, 0.0, ["Missing MCQ options JSON."]

    try:
        options = json.loads(options_json) if isinstance(options_json, str) else options_json
    except Exception:
        return False, 0.0, 0.0, ["Invalid options JSON format."]

    if not isinstance(options, list):
        return False, 0.0, 0.0, ["MCQ options must be a JSON array."]

    if len(options) != 4 and len(options) != 5:
        issues.append(f"MCQ options count is {len(options)} (expected exactly 4 or 5 options).")

    # Inspect each option object or string
    parsed_options = []
    blank_found = False
    expected_labels = ["A", "B", "C", "D", "E"][:len(options)]
    actual_labels = []

    raw_key = str(question_dict.get("correct_answer_json") or question_dict.get("correct_option") or "").strip().upper()
    match_key = re.match(r'^([A-E])', raw_key)
    correct_key = match_key.group(1) if match_key else raw_key

    for idx, opt in enumerate(options):
        if isinstance(opt, dict):
            lbl = (opt.get("label") or chr(65 + idx)).strip().upper()
            txt = str(opt.get("text", "")).strip()
            is_corr = opt.get("is_correct")
            if is_corr is True or is_corr == 1 or is_corr == "1" or str(is_corr).lower() == "true":
                is_corr = True
            elif is_corr is False:
                is_corr = False
            else:
                is_corr = (lbl == correct_key) if correct_key else False
        else:
            opt_str = str(opt).strip()
            lbl = chr(65 + idx)
            txt = re.sub(r'^[A-E][\)\.]\s*', '', opt_str).strip()
            is_corr = (lbl == correct_key) if correct_key else False

        if not txt:
            blank_found = True
        actual_labels.append(lbl)
        parsed_options.append({"label": lbl, "text": txt, "is_correct": is_corr})

    if blank_found:
        issues.append("One or more MCQ options are blank.")

    # Validate labels
    if actual_labels != expected_labels:
        issues.append(f"MCQ labels {actual_labels} do not match expected sequential labels {expected_labels}.")

    # Check for duplicate option text (distractor duplication)
    clean_texts = [p["text"].lower() for p in parsed_options if p["text"]]
    if len(clean_texts) != len(set(clean_texts)):
        issues.append("Duplicate MCQ options or distractors detected.")

    # Check correct answer and question type
    q_type = question_dict.get("question_type", "mcq_single")

    if not correct_key and not any(p["is_correct"] for p in parsed_options):
        issues.append("Missing correct answer key.")

    explicit_correct = [p for p in parsed_options if p["is_correct"]]
    matching_key = [p for p in parsed_options if p["label"] == correct_key]

    if q_type in ["mcq", "mcq_single", "short_answer"]:
        if len(explicit_correct) > 1:
            issues.append("More than one correct option exists in a single-answer MCQ.")
        elif len(explicit_correct) == 0 and not matching_key:
            issues.append("No correct answer designated for single-answer MCQ.")
        elif len(explicit_correct) == 1 and matching_key and explicit_correct[0]["label"] != correct_key:
            issues.append(f"Designated correct option {explicit_correct[0]['label']} does not match correct answer key {correct_key}.")
    elif q_type in ["mcq_multiple", "multiple_select"]:
        if len(explicit_correct) < 2:
            issues.append("Multiple-select MCQ requires at least two correct options.")

    # Check answer explanation (can be in explanation, model_answer, or distractor_explanations_json)
    expl = str(question_dict.get("explanation") or question_dict.get("model_answer") or question_dict.get("distractor_explanations_json") or "").strip()
    if not expl or len(expl) < 5:
        issues.append("Answer explanation is missing or incomplete.")

    # Option grammar score
    opt_grammar_scores = []
    for p in parsed_options:
        if p["text"]:
            _, g_score, _ = validate_option_grammar(p["text"])
            opt_grammar_scores.append(g_score)
        else:
            opt_grammar_scores.append(0.0)

    avg_opt_grammar = sum(opt_grammar_scores) / len(opt_grammar_scores) if opt_grammar_scores else 0.0

    is_structurally_valid = len(issues) == 0
    structural_score = 100.0 if is_structurally_valid else 0.0

    return is_structurally_valid, structural_score, avg_opt_grammar, issues

def validate_mcq_quality(question_dict: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Enforce strict MCQ quality rules (compatibility wrapper)."""
    valid, score, _, issues = validate_mcq_structure(question_dict)
    return score, issues

def evaluate_semantic_quality(
    question_dict: Dict[str, Any],
    syllabus_unit: Dict[str, Any],
    co_dict: Dict[str, Any],
    existing_questions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Second-pass semantic quality validator evaluating 11 dimensions (0-100 each).
    Requires minimum thresholds:
      - syllabus_alignment >= 85%
      - source_support >= 80%
      - co_alignment >= 85%
      - bloom_alignment >= 85%
      - grammar_quality >= 90%
      - overall_quality >= 85%
    """
    reasons_for_review = []
    
    q_text = question_dict.get("question_text", "")
    q_type = question_dict.get("question_type", "short_answer")
    marks = question_dict.get("marks", 2)
    assigned_bloom = question_dict.get("bloom_level", "L2 - Understand")
    unit_num = str(question_dict.get("unit_number", "1"))
    co_code = str(question_dict.get("co_level", "CO1"))
    
    # 1. Grammar & Language Check
    cleaned_text, grammar_score, grammar_issues = validate_question_grammar(q_text)
    if grammar_issues:
        reasons_for_review.extend(grammar_issues)
        
    # 2. Syllabus Alignment
    unit_topics = syllabus_unit.get("topics", "")
    unit_title = syllabus_unit.get("title", "")
    full_unit_text = f"{unit_title} {unit_topics}".strip().lower()
    source_topic = (question_dict.get("source_topic", "") or "").lower()
    
    syllabus_align_score = 94.0
    if not source_topic or source_topic in full_unit_text:
        syllabus_align_score = 98.0
    elif any(w in full_unit_text for w in source_topic.split() if len(w) > 2):
        syllabus_align_score = 94.0
    elif any(w in source_topic for w in full_unit_text.split() if len(w) > 2):
        syllabus_align_score = 92.0
    elif unit_num == "1" and any(k in source_topic for k in ["intro", "basic", "r", "vector"]):
        syllabus_align_score = 92.0
    else:
        syllabus_align_score = 82.0
        reasons_for_review.append(f"Topic '{source_topic}' not explicitly found in Unit {unit_num} syllabus.")
        
    # 3. Source Support (PPT / Notes)
    source_file = question_dict.get("source_filename", "")
    supp_passage = question_dict.get("supporting_passage", "")
    source_score = 90.0
    if not source_file or source_file == "Approved Institutional Syllabus":
        source_score = 90.0
    elif len(supp_passage) > 20:
        source_score = 95.0
    else:
        source_score = 85.0
        
    # 4. CO Alignment (Strict Unit <-> CO check)
    co_align_score = 95.0
    expected_co_id = unit_num
    actual_co_id = re.sub(r'[^0-9]', '', co_code)
    if expected_co_id != actual_co_id:
        co_align_score = 70.0
        reasons_for_review.append(f"Unit {unit_num} conflicts with mapped outcome {co_code} (expected CO{expected_co_id}).")
        
    # 5. Bloom's Alignment
    bloom_score, bloom_issue = validate_bloom_alignment(q_text, assigned_bloom)
    if bloom_issue:
        reasons_for_review.append(bloom_issue)
        
    # 6. Topic Relevance (R Programming discipline checks)
    r_keywords = ["r", "vector", "matrix", "matrices", "data frame", "list", "factor", "s3", "s4", 
                  "glm", "linear model", "script", "apply", "plot", "function", "array", "recursion",
                  "package", "regression", "cluster", "time series", "dataset", "read.csv", "table"]
    is_r_relevant = any(re.search(r'\b' + re.escape(kw) + r'\b', q_text.lower()) for kw in r_keywords)
    topic_relevance_score = 95.0 if is_r_relevant else 78.0
    if not is_r_relevant:
        reasons_for_review.append("Question stem lacks clear R programming terminology or concepts.")
        
    # 7. Marks Suitability
    marks_score, marks_issue = validate_marks_suitability(marks, q_text, q_type)
    if marks_issue:
        reasons_for_review.append(marks_issue)
        
    # 8. Answerability
    model_ans = question_dict.get("model_answer", "")
    marking_sch = question_dict.get("marking_scheme", "")
    answerability_score = 95.0 if (len(model_ans) > 40 and len(marking_sch) > 20) else 75.0
    if answerability_score < 80.0:
        reasons_for_review.append("Model answer or marking scheme is incomplete.")
        
    # 9. Specificity
    specificity_score = 92.0
    if len(q_text.split()) < 7:
        specificity_score = 75.0
        reasons_for_review.append("Question prompt is overly broad or unspecific.")
        
    # 10. Duplication
    duplication_score = 98.0
    if existing_questions:
        q_norm = re.sub(r'[^a-zA-Z0-9]', '', q_text.lower())
        for prev in existing_questions:
            prev_norm = re.sub(r'[^a-zA-Z0-9]', '', prev.lower())
            if q_norm == prev_norm:
                duplication_score = 30.0
                reasons_for_review.append("Exact or near-duplicate question detected.")
                break
                
    # 11. Academic Quality & MCQ Structural Validity
    academic_score = 92.0
    is_mcq = q_type in ["mcq", "mcq_single", "mcq_multiple", "multiple_select"] or question_dict.get("options_json") is not None
    structural_valid = True
    opt_grammar_score = 100.0

    if is_mcq:
        is_struct_valid, struct_score, opt_grammar, mcq_issues = validate_mcq_structure(question_dict)
        structural_valid = is_struct_valid
        opt_grammar_score = opt_grammar
        academic_score = struct_score
        if not is_struct_valid:
            reasons_for_review.extend(mcq_issues)

    # Overall Quality Score
    if not structural_valid:
        overall_quality = 0.0
        passes_thresholds = False
        status = "needs_review"
    else:
        overall_quality = (
            0.20 * syllabus_align_score +
            0.15 * source_score +
            0.15 * co_align_score +
            0.15 * bloom_score +
            0.15 * grammar_score +
            0.20 * academic_score
        )
        passes_thresholds = (
            syllabus_align_score >= 85.0 and
            source_score >= 80.0 and
            co_align_score >= 85.0 and
            bloom_score >= 85.0 and
            grammar_score >= 90.0 and
            overall_quality >= 85.0
        )
        status = "draft" if passes_thresholds else "needs_review"

    details = {
        "syllabus_alignment": round(syllabus_align_score, 1),
        "source_support": round(source_score, 1),
        "co_alignment": round(co_align_score, 1),
        "bloom_alignment": round(bloom_score, 1),
        "grammar_quality": round(grammar_score, 1),
        "stem_grammar_score": round(grammar_score, 1),
        "option_grammar_score": round(opt_grammar_score, 1),
        "structural_validity": structural_valid,
        "topic_relevance": round(topic_relevance_score, 1),
        "marks_suitability": round(marks_score, 1),
        "answerability": round(answerability_score, 1),
        "specificity": round(specificity_score, 1),
        "duplication": round(duplication_score, 1),
        "academic_quality": round(academic_score, 1),
        "overall_quality": round(overall_quality, 1),
        "passes_thresholds": passes_thresholds
    }

    return {
        "cleaned_text": cleaned_text,
        "grammar_score": round(grammar_score, 1),
        "quality_score": round(overall_quality, 1),
        "status": status,
        "details_json": json.dumps(details),
        "reasons": reasons_for_review
    }

def evaluate_or_pair_equivalence(q_a: Dict[str, Any], q_b: Dict[str, Any]) -> Tuple[float, str]:
    """
    Computes an equivalence score (0 to 100) for internal choice pairs.
    Verifies:
      - Same marks (weight 25)
      - Same unit (weight 25)
      - Same CO (weight 20)
      - Same Bloom level (weight 15)
      - Comparable difficulty (weight 10)
      - Comparable cognitive demand & answer length (weight 5)
    Requires at least 85% equivalence.
    """
    score = 0.0
    notes = []
    
    # 1. Same Marks (25 points)
    if q_a.get("marks") == q_b.get("marks"):
        score += 25.0
    else:
        notes.append("Mark mismatch")
        
    # 2. Same Unit (25 points)
    if str(q_a.get("unit_number", "")) == str(q_b.get("unit_number", "")):
        score += 25.0
    else:
        notes.append("Unit mismatch")
        
    # 3. Same CO (20 points)
    if str(q_a.get("co_level", "")) == str(q_b.get("co_level", "")):
        score += 20.0
    else:
        notes.append("Course Outcome mismatch")
        
    # 4. Same Bloom level (15 points)
    bloom_a = str(q_a.get("bloom_level", ""))[:2]
    bloom_b = str(q_b.get("bloom_level", ""))[:2]
    if bloom_a == bloom_b:
        score += 15.0
    elif abs(int(bloom_a[1]) - int(bloom_b[1])) <= 1:
        score += 10.0
        notes.append("Minor Bloom difference")
    else:
        notes.append("Significant Bloom level divergence")
        
    # 5. Comparable Difficulty (10 points)
    diff_a = str(q_a.get("difficulty", "Medium")).lower()
    diff_b = str(q_b.get("difficulty", "Medium")).lower()
    if diff_a == diff_b:
        score += 10.0
    else:
        score += 6.0
        
    # 6. Comparable Answer Length (5 points)
    len_a = len(q_a.get("model_answer", ""))
    len_b = len(q_b.get("model_answer", ""))
    if max(len_a, len_b) > 0:
        ratio = min(len_a, len_b) / max(len_a, len_b)
        score += 5.0 * ratio
    else:
        score += 5.0
        
    u_val = q_a.get("unit_number", "1")
    marks_val = q_a.get("marks", 13)
    b_val = q_a.get("bloom_level", "L3 - Apply")
    summary = f"Unit {u_val} | {marks_val} Marks | Balanced Cognitive Load ({b_val}) | Equivalence: {round(score, 1)}%"
    if notes:
        summary += f" ({', '.join(notes)})"
        
    return round(score, 1), summary
