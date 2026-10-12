import re
from typing import List, Dict, Any, Optional, Tuple

STOP_WORDS = {
    "a", "an", "the", "and", "or", "in", "on", "at", "to", "for", "with", "by", 
    "of", "from", "as", "is", "are", "was", "were", "it", "this", "that", "these", 
    "those", "then", "into", "over", "after", "before", "between", "both", "through",
    "during", "under", "above", "also", "using", "used", "uses", "can", "will", "be"
}

def tokenize(text: str) -> set:
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
    return {w for w in words if w not in STOP_WORDS}

def detect_bloom_suitability(text: str) -> str:
    t_lower = text.lower()
    if re.search(r'\b(design|formulate|construct|devise|synthesize|integrate|create)\b', t_lower):
        return "L6 - Create"
    if re.search(r'\b(evaluate|justify|critique|validate|assess|appraise|compare trade-offs)\b', t_lower):
        return "L5 - Evaluate"
    if re.search(r'\b(analyze|differentiate|distinguish|investigate|examine|complexity|bottleneck)\b', t_lower):
        return "L4 - Analyze"
    if re.search(r'\b(apply|implement|calculate|solve|compute|demonstrate|code|algorithm)\b', t_lower):
        return "L3 - Apply"
    if re.search(r'\b(explain|describe|illustrate|summarize|classify|discuss|overview)\b', t_lower):
        return "L2 - Understand"
    return "L1 - Remember"

def parse_syllabus_topics(topic_string: str) -> List[str]:
    norm = re.sub(r'[\u2010-\u2015\u2022\u25cf\u25cb\u25aa\u25ab\xb7\ufffd]|\s+-\s+|;', ' • ', str(topic_string or ""))
    topics = [t.strip() for t in re.split(r'[,•\n]', norm) if len(t.strip()) > 2]
    return [t for t in topics if not any(w in t.upper() for w in ['PO1', 'PSO', 'STRONG', 'MEDIUM', 'LOW'])]

def get_stems(words: set) -> set:
    stems = set()
    for w in words:
        if len(w) > 4 and w.endswith(('ing', 'ed', 'es', 'tion', 'tions')):
            for suf in ['ing', 'ed', 'es', 'tion', 'tions']:
                if w.endswith(suf):
                    stems.add(w[:-len(suf)])
                    break
        else:
            stems.add(w)
    return stems

def align_chunk_to_syllabus(
    chunk: Dict[str, Any],
    syllabus_units: List[Dict[str, Any]],
    course_outcomes: List[Dict[str, Any]],
    filename: str
) -> Dict[str, Any]:
    """
    Align a single slide or page chunk against syllabus units, topics, and course outcomes.
    Calculates alignment confidence score (0.0 to 1.0) and classifies:
    >= 0.80: Strong alignment
    0.60 - 0.79: Review recommended
    < 0.60: Unmatched / Low confidence
    """
    chunk_title = chunk.get("title", "")
    chunk_text = f"{chunk_title} {chunk.get('content', '')}"
    chunk_tokens = tokenize(chunk_text)
    chunk_stems = get_stems(chunk_tokens)
    text_lower = chunk_text.lower()
    title_lower = chunk_title.lower()

    best_unit = None
    best_topic = ""
    best_unit_score = 0.0

    for unit in syllabus_units:
        unit_title = unit.get("title", "")
        unit_tokens = tokenize(unit_title)
        unit_stems = get_stems(unit_tokens)
        topic_string = unit.get("topics", "")
        topic_tokens = tokenize(topic_string)
        topics_list = parse_syllabus_topics(topic_string)

        title_match = bool(chunk_tokens.intersection(unit_tokens) or chunk_stems.intersection(unit_stems))

        best_subtopic = ""
        best_subtopic_score = 0.0

        for t in topics_list:
            t_lower = t.lower()
            t_toks = tokenize(t)
            if not t_toks:
                continue

            score = 0.0
            # 1. Exact phrase match
            if t_lower in title_lower:
                score = 0.95
            elif t_lower in text_lower:
                score = 0.85 if len(t_toks) > 1 else (0.85 if title_match else 0.70)
            else:
                # 2. Token and Stem Overlap
                t_stems = get_stems(t_toks)
                inter_exact = chunk_tokens.intersection(t_toks)
                inter_stems = chunk_stems.intersection(t_stems)
                overlap = max(len(inter_exact), len(inter_stems)) / max(len(t_toks), 1)
                if overlap >= 0.7:
                    score = 0.80
                elif overlap >= 0.4:
                    score = 0.65
                elif overlap > 0:
                    score = 0.45

            if score > best_subtopic_score:
                best_subtopic_score = score
                best_subtopic = t

        # Topic tokens overlap across entire unit
        inter_unit = chunk_tokens.intersection(topic_tokens)
        density = len(inter_unit) / max(min(len(chunk_tokens), 15), 1)

        unit_score = best_subtopic_score
        if title_match and unit_score > 0.4:
            unit_score = min(1.0, unit_score + 0.10)
        elif density > 0.3 and unit_score > 0.4:
            unit_score = min(1.0, unit_score + 0.08)

        if unit_score > best_unit_score:
            best_unit_score = unit_score
            best_unit = unit
            best_topic = best_subtopic or (topics_list[0] if topics_list else unit.get("title", ""))

    # If no unit had match, fallback
    if not best_unit and syllabus_units:
        best_unit = syllabus_units[0]
        best_topic = best_unit.get("title", "")
        best_unit_score = 0.20

    # Match Course Outcome
    best_co = f"CO{min(int(best_unit.get('number', 1)) if str(best_unit.get('number', 1)).isdigit() else 1, 5)}" if best_unit else "CO1"
    best_co_score = 0.0
    for co in course_outcomes:
        co_toks = tokenize(co.get("description", ""))
        if not co_toks:
            continue
        co_score = len(chunk_tokens.intersection(co_toks)) / max(len(co_toks), 1)
        if co_score > best_co_score:
            best_co_score = co_score
            best_co = co.get("code", best_co)

    # Normalized Confidence (0.0 to 1.0)
    confidence = min(0.98, max(0.15, (best_unit_score * 0.90) + (best_co_score * 0.10)))

    # Classification
    if confidence >= 0.80:
        classification = "Strong alignment"
    elif confidence >= 0.60:
        classification = "Review recommended"
    else:
        classification = "Unmatched"

    bloom_suitability = detect_bloom_suitability(chunk_text)

    # Clean excerpt for supporting passage
    lines = [l.strip() for l in chunk.get("content", "").splitlines() if len(l.strip()) > 15]
    excerpt = " ".join(lines[:3])[:300] if lines else chunk.get("content", "")[:300]

    return {
        "chunk_id": chunk.get("chunk_id", ""),
        "source_filename": filename,
        "slide_or_page_number": chunk.get("slide_or_page_number", 1),
        "unit_number": str(best_unit.get("number", "1")) if best_unit else "1",
        "unit_title": best_unit.get("title", "") if best_unit else "Unit 1",
        "syllabus_topic": best_topic,
        "subtopic": best_topic,
        "matched_co": best_co,
        "bloom_suitability": bloom_suitability,
        "confidence_score": round(confidence, 2),
        "classification": classification,
        "matched_excerpt": excerpt
    }

def align_content_file_to_syllabus(
    chunks: List[Dict[str, Any]],
    syllabus_units: List[Dict[str, Any]],
    course_outcomes: List[Dict[str, Any]],
    filename: str
) -> Dict[str, Any]:
    """Align all chunks of a file to the syllabus."""
    alignments = []
    strong_alignments = []
    review_alignments = []
    unmatched_chunks = []

    unit_coverage = {}
    topic_coverage = {}

    for chunk in chunks:
        align = align_chunk_to_syllabus(chunk, syllabus_units, course_outcomes, filename)
        alignments.append(align)

        if align["classification"] == "Strong alignment":
            strong_alignments.append(align)
        elif align["classification"] == "Review recommended":
            review_alignments.append(align)
        else:
            unmatched_chunks.append({
                "chunk_id": chunk.get("chunk_id"),
                "slide_or_page_number": chunk.get("slide_or_page_number"),
                "title": chunk.get("title"),
                "content_preview": chunk.get("content", "")[:180],
                "confidence_score": align["confidence_score"]
            })

        # Track coverage
        u_num = align["unit_number"]
        unit_coverage[u_num] = unit_coverage.get(u_num, 0) + 1
        t_name = align["syllabus_topic"]
        if t_name:
            topic_coverage[t_name] = topic_coverage.get(t_name, 0) + 1

    return {
        "filename": filename,
        "total_chunks": len(chunks),
        "strong_count": len(strong_alignments),
        "review_count": len(review_alignments),
        "unmatched_count": len(unmatched_chunks),
        "alignments": alignments,
        "unmatched_chunks": unmatched_chunks,
        "unit_coverage": unit_coverage,
        "topic_coverage": topic_coverage
    }

def build_coverage_matrix(
    blueprint: Dict[str, Any],
    syllabus_units: List[Dict[str, Any]],
    course_outcomes: List[Dict[str, Any]],
    all_alignments: List[Dict[str, Any]],
    generation_mode: str = "syllabus_ppt"
) -> Dict[str, Any]:
    """
    Construct coverage matrix before question generation.
    Validates whether blueprint requirements (Unit, Topic, CO, Bloom Level)
    can be adequately supported by aligned content.
    """
    warnings = []
    matrix_rows = []

    # Aggregate supporting chunks by (unit_number, topic)
    aligned_by_unit_topic = {}
    aligned_by_co = {}
    aligned_by_bloom = {}

    for a in all_alignments:
        if a.get("classification") in ["Strong alignment", "Review recommended"]:
            u_num = str(a.get("unit_number", "1"))
            topic = a.get("syllabus_topic", "")
            key = (u_num, topic)
            aligned_by_unit_topic[key] = aligned_by_unit_topic.get(key, 0) + 1

            co = a.get("matched_co", "CO1")
            aligned_by_co[co] = aligned_by_co.get(co, 0) + 1

            b_lvl = a.get("bloom_suitability", "L2 - Understand")
            aligned_by_bloom[b_lvl] = aligned_by_bloom.get(b_lvl, 0) + 1

    # Extract required topics from blueprint
    sections = blueprint.get("sections", [])
    required_allocations = []
    for s_idx, sec in enumerate(sections, start=1):
        sec_name = sec.get("name", f"Part {chr(64 + s_idx)}")
        q_count = sec.get("questions_count", 5)
        co_dist = sec.get("co_distribution", [])
        bloom_dist = sec.get("bloom_distribution", [])

        for i in range(q_count):
            co = co_dist[i % len(co_dist)] if co_dist else f"CO{(i % 5) + 1}"
            bloom = bloom_dist[i % len(bloom_dist)] if bloom_dist else "L2 - Understand"
            required_allocations.append({
                "section": sec_name,
                "co": co,
                "bloom": bloom
            })

    # Check each syllabus unit and its topics
    for unit in syllabus_units:
        u_num = str(unit.get("number", "1"))
        u_title = unit.get("title", "")
        raw_topics = unit.get("topics", "")
        topics = parse_syllabus_topics(raw_topics)
        if not topics:
            topics = [u_title]

        for topic in topics[:4]: # Sample primary topics
            key = (u_num, topic)
            sources_count = aligned_by_unit_topic.get(key, 0)
            
            # Count allocations requiring this unit/co
            unit_co = f"CO{min(int(u_num) if u_num.isdigit() else 1, 5)}"
            req_count = sum(1 for a in required_allocations if a["co"] == unit_co)

            status = "Ready"
            if generation_mode in ["syllabus_ppt", "all_sources"]:
                if sources_count == 0:
                    status = "No PPT Content"
                    warnings.append(f"Unit {u_num} topic '{topic}': No aligned faculty PPT/notes found. Question will fallback to syllabus text.")
                elif sources_count < req_count:
                    status = "Partial Coverage"

            matrix_rows.append({
                "unit": f"Unit {u_num}",
                "unit_title": u_title,
                "topic": topic,
                "co": unit_co,
                "bloom_level": "L2 - Understand" if u_num in ["1", "2"] else ("L3 - Apply" if u_num in ["3", "4"] else "L4 - Analyze"),
                "source_available": f"{sources_count} slide(s)/page(s)" if sources_count > 0 else "Syllabus Only",
                "questions_required": max(1, req_count),
                "status": status
            })

    # Validate CO and Bloom Coverage
    for co in ["CO1", "CO2", "CO3", "CO4", "CO5"]:
        req_co = sum(1 for a in required_allocations if a["co"] == co)
        avail_co = aligned_by_co.get(co, 0)
        if req_co > 0 and avail_co == 0 and generation_mode in ["syllabus_ppt", "all_sources"]:
            warnings.append(f"Course Outcome {co} requires {req_co} question(s) but has minimal supporting instructional slides.")

    is_ready = len([w for w in warnings if "No PPT Content" in w]) <= len(matrix_rows) // 2

    return {
        "coverage_rows": matrix_rows,
        "warnings": warnings,
        "is_ready_for_generation": True, # Warnings are informative; allow generation with warnings
        "total_blueprint_questions": len(required_allocations),
        "generation_mode": generation_mode
    }
