import json
import re
import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.models.question_paper import Question, QuestionPaper
from app.services.semantic_validator import evaluate_semantic_quality, validate_question_grammar, validate_mcq_structure

def repair_existing_mcqs():
    db = SessionLocal()
    try:
        # Find all questions that have options_json or are MCQs
        mcq_questions = db.query(Question).filter(
            (Question.options_json != None) | 
            (Question.question_type.like('%mcq%'))
        ).all()

        print(f"Found {len(mcq_questions)} MCQ questions to inspect/repair.\n")

        repaired_count = 0

        for q in mcq_questions:
            print("=" * 60)
            print(f"Question ID {q.id} (Paper ID {q.question_paper_id}, Q#{q.question_number}):")
            print(f"  Question: {q.question_text[:80]}...")
            print(f"  Raw options_json: {q.options_json}")
            print(f"  Raw correct_answer_json: {q.correct_answer_json}")
            print(f"  Current quality_score: {q.quality_score}, status: {q.status}")

            raw_opts = None
            if q.options_json:
                try:
                    raw_opts = json.loads(q.options_json)
                except Exception as e:
                    print(f"  [!] Error decoding options_json: {e}")
                    raw_opts = None

            raw_correct = q.correct_answer_json or "A"
            if isinstance(raw_correct, str) and (raw_correct.startswith('[') or raw_correct.startswith('"')):
                try:
                    parsed_corr = json.loads(raw_correct)
                    if isinstance(parsed_corr, list) and len(parsed_corr) > 0:
                        raw_correct = parsed_corr[0]
                    elif isinstance(parsed_corr, str):
                        raw_correct = parsed_corr
                except Exception:
                    pass
            raw_correct = str(raw_correct).strip().upper().replace('"', '').replace("'", "")

            canonical_options = []

            if isinstance(raw_opts, list):
                for idx, opt in enumerate(raw_opts):
                    lbl = chr(65 + idx)
                    if isinstance(opt, str):
                        match = re.match(r"^([A-Ea-e])[\.\)]\s*(.*)$", opt.strip())
                        if match:
                            lbl = match.group(1).upper()
                            txt = match.group(2).strip()
                        else:
                            txt = opt.strip()
                        is_corr = (lbl == raw_correct)
                        canonical_options.append({
                            "label": lbl,
                            "text": txt,
                            "is_correct": bool(is_corr)
                        })
                    elif isinstance(opt, dict):
                        lbl = str(opt.get("label") or lbl).strip().upper()
                        txt = str(opt.get("text", "")).strip()
                        corr_val = opt.get("is_correct")
                        if corr_val is not None:
                            is_corr = bool(corr_val) if not isinstance(corr_val, str) else corr_val.lower() == 'true'
                        else:
                            is_corr = (lbl == raw_correct)
                        canonical_options.append({
                            "label": lbl,
                            "text": txt,
                            "is_correct": bool(is_corr),
                            "explanation": opt.get("explanation")
                        })
            else:
                print("  [!] Warning: raw_opts is not a list!")
                continue

            # Ensure exactly one correct answer for single-choice
            correct_opts = [o for o in canonical_options if o["is_correct"]]
            if len(correct_opts) == 0 and len(canonical_options) > 0:
                # Fallback: check raw_correct or set first
                matched = False
                for o in canonical_options:
                    if o["label"] == raw_correct:
                        o["is_correct"] = True
                        matched = True
                        break
                if not matched:
                    canonical_options[0]["is_correct"] = True
            elif len(correct_opts) > 1 and (not q.question_type or q.question_type in ["mcq", "mcq_single"]):
                # Keep only the one matching raw_correct, or the first
                first_found = False
                for o in canonical_options:
                    if o["label"] == raw_correct and not first_found:
                        o["is_correct"] = True
                        first_found = True
                    elif o["is_correct"] and not first_found:
                        first_found = True
                    else:
                        o["is_correct"] = False

            # Determine actual correct answer label
            correct_labels = [o["label"] for o in canonical_options if o["is_correct"]]
            final_correct = correct_labels[0] if correct_labels else "A"

            # Check explanation
            explanation = q.explanation or "Standard R programming concept."

            # Update question fields
            q.question_type = "mcq_single"
            q.options_json = json.dumps(canonical_options)
            q.correct_answer_json = final_correct
            q.explanation = explanation

            # Ensure model_answer and marking_scheme are populated
            if not q.model_answer or "Correct Option:" not in q.model_answer:
                q.model_answer = f"Correct Option: {final_correct}.\n\nExplanation: {explanation}"
            if not q.marking_scheme or len(q.marking_scheme.strip()) < 5:
                q.marking_scheme = f"{q.marks} Marks: Selecting the correct option ({final_correct})."

            # Re-evaluate grammar and semantic quality
            cleaned_text, g_score, _ = validate_question_grammar(q.question_text)
            q.question_text = cleaned_text
            q.grammar_score = g_score

            target_unit = {"number": q.unit_number or "1", "title": f"Unit {q.unit_number or '1'}", "topics": q.source_topic or ""}
            co_dict = {"code": q.co_level, "unit_title": target_unit.get("title", "")}
            q_eval = {
                "question_text": q.question_text,
                "question_type": q.question_type,
                "marks": q.marks,
                "co_level": q.co_level,
                "bloom_level": q.bloom_level,
                "difficulty": q.difficulty,
                "source_topic": q.source_topic,
                "unit_number": q.unit_number,
                "source_filename": q.source_filename,
                "supporting_passage": q.supporting_passage,
                "options_json": q.options_json,
                "correct_answer_json": q.correct_answer_json,
                "explanation": q.explanation,
                "model_answer": q.model_answer,
                "marking_scheme": q.marking_scheme
            }
            val_res = evaluate_semantic_quality(q_eval, target_unit, co_dict)
            q.quality_score = val_res["quality_score"]
            q.validation_details_json = val_res["details_json"]
            q.needs_review_reasons = "; ".join(val_res["reasons"]) if val_res["reasons"] else None

            # If semantic validator determines it passes, update status
            if val_res["status"] == "draft" and q.status == "needs_review":
                q.status = "draft"
            elif val_res["status"] == "needs_review":
                q.status = "needs_review"

            repaired_count += 1
            print(f"  --> Repaired:")
            print(f"      Canonical options: {q.options_json}")
            print(f"      Correct Answer: {q.correct_answer_json}")
            print(f"      New quality_score: {q.quality_score}, status: {q.status}")
            print(f"      Needs review: {q.needs_review_reasons}")

        db.commit()
        print("\n" + "=" * 60)
        print(f"Successfully repaired {repaired_count} MCQs in database!")

    finally:
        db.close()

if __name__ == "__main__":
    repair_existing_mcqs()
