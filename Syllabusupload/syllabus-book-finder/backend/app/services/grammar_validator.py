import re
from typing import Tuple, List, Dict, Any

# Generic enterprise phrases banned unless explicitly present in syllabus
BANNED_ENTERPRISE_PHRASES = [
    r'\barchitectural\s+viability\b',
    r'\bmission[- ]critical\s+enterprise\s+environments?\b',
    r'\benterprise\s+scalability\b',
    r'\bfault[- ]tolerance\s+criteria\b',
    r'\bhigh[- ]load\s+conditions?\b',
    r'\boperational\s+behaviou?r\b',
    r'\bmodern\s+methodologies\b',
    r'\boptimization\s+strategies\b',
    r'\bscalable\s+enterprise\b',
    r'\bproduction\s+ecosystems?\b'
]

# Clumsy or syllabus-artifact phrases to automatically normalize
SYLLABUS_PHRASE_CORRECTIONS = [
    (re.compile(r'\bIntroducing\s+to\s+R\b', re.IGNORECASE), "Introduction to R"),
    (re.compile(r'\bGeneralized\s+Linear\s+models\b', re.IGNORECASE), "generalized linear models"),
    (re.compile(r'\bNon\s*[-–]\s*linear\s+models\b', re.IGNORECASE), "nonlinear models"),
    (re.compile(r'\bApplying\s+Functions?\s+to\s+Matrix\s+Rows?\s+and\s+Columns?\b', re.IGNORECASE), "applying functions to matrix rows and columns"),
    (re.compile(r'\baccessing\s+keyboard\s+and\s+monitor\b', re.IGNORECASE), "reading input from the keyboard and displaying output on the monitor"),
    (re.compile(r'\bData\s+frames\b'), "data frames"),
    (re.compile(r'\bHigher\s+Dimensional\s+arrays\b', re.IGNORECASE), "higher-dimensional arrays"),
    (re.compile(r'\bVectorised\s+if-then\s+else\b', re.IGNORECASE), "vectorized ifelse() function"),
    (re.compile(r'\bVectorized\s+if-then\s+else\b', re.IGNORECASE), "vectorized ifelse() function"),
    (re.compile(r'\bEnvironment\s+and\s+Scope\s+issues?\b', re.IGNORECASE), "lexical scoping and environment management in R"),
    (re.compile(r'\bWriting\s+Upstairs\b', re.IGNORECASE), "superassignment operator (<<-) and closures in R"),
    (re.compile(r'\bTools\s+for\s+composing\s+function\s+code\b', re.IGNORECASE), "function composition and functional programming tools in R"),
    (re.compile(r'\bMath\s+and\s+Simulations\s+in\s+R\b', re.IGNORECASE), "mathematical computations and Monte Carlo simulations in R"),
    (re.compile(r'\bInterfacing\s+R\s+to\s+other\s+languages\b', re.IGNORECASE), "interfacing R with compiled languages (C, C++, or Python)"),
    (re.compile(r'\bParallel\s+R\b', re.IGNORECASE), "parallel computing and cluster execution in R"),
    (re.compile(r'\bTime\s+Series\s+and\s+Auto\s*[-–]?\s*correlation\b', re.IGNORECASE), "time series analysis and autocorrelation in R"),
    (re.compile(r'\bManaging\s+your\s+objects\b', re.IGNORECASE), "workspace and object management using ls() and rm() in R"),
    (re.compile(r'\bAvoiding\s+Dimension\s+Reduction\b', re.IGNORECASE), "preserving matrix dimensions using drop = FALSE"),
    (re.compile(r'\bVector/Matrix\s+Distinction\b', re.IGNORECASE), "the structural differences between vectors and matrices"),
    (re.compile(r'\bVector\s+Equality\b', re.IGNORECASE), "vector equality testing using identical() and all.equal()"),
    (re.compile(r'\bVector\s+Element\s+names\b', re.IGNORECASE), "named vector elements and the names() attribute")
]

def clean_academic_language(text: str) -> str:
    """Normalize clumsy syllabus phrases and strip banned jargon."""
    if not text:
        return ""
    
    cleaned = text
    # 1. Apply known syllabus phrase corrections
    for pattern, replacement in SYLLABUS_PHRASE_CORRECTIONS:
        cleaned = pattern.sub(replacement, cleaned)
    
    # 2. Eliminate banned enterprise buzzwords with clean academic wording
    cleaned = re.sub(r'(?i)\bthe\s+architectural\s+viability\s+of\b', "the practical suitability of", cleaned)
    cleaned = re.sub(r'(?i)\barchitectural\s+viability\b', "suitability and statistical assumptions", cleaned)
    cleaned = re.sub(r'(?i)\bfor\s+mission[- ]critical\s+enterprise\s+environments?\b', "for real-world data analysis", cleaned)
    cleaned = re.sub(r'(?i)\bmission[- ]critical\s+enterprise\s+environments?\b', "practical applications", cleaned)
    cleaned = re.sub(r'(?i)\bto\s+fulfil\s+enterprise\s+scalability\s+and\s+fault[- ]tolerance\s+criteria\b', "with proper data validation and statistical accuracy", cleaned)
    cleaned = re.sub(r'(?i)\benterprise\s+scalability\s+and\s+fault[- ]tolerance\s+criteria\b', "robust performance and validation requirements", cleaned)
    cleaned = re.sub(r'(?i)\benterprise\s+scalability\b', "computational efficiency", cleaned)
    cleaned = re.sub(r'(?i)\boperational\s+behaviou?r\b', "working mechanism", cleaned)
    cleaned = re.sub(r'(?i)\boptimization\s+strategies\b', "efficient data manipulation techniques", cleaned)
    cleaned = re.sub(r'(?i)\bmodern\s+methodologies\b', "standard statistical methods", cleaned)

    # 3. Clean multiple spaces, awkward punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    cleaned = re.sub(r'\s+([,.:;?!])', r'\1', cleaned)
    
    # Ensure standard sentence capitalization
    if cleaned and cleaned[0].islower():
        cleaned = cleaned[0].upper() + cleaned[1:]
    
    # Ensure terminating punctuation
    if cleaned and cleaned[-1] not in ".?!":
        cleaned += "."

    return cleaned

def validate_question_grammar(question_text: str) -> Tuple[str, float, List[str]]:
    """
    Validates academic grammar, syntax consistency, and absence of generic buzzwords.
    Returns:
        (corrected_text, grammar_score [0-100], issues_list)
    """
    issues = []
    deductions = 0.0

    if not question_text or len(question_text.strip()) < 10:
        return question_text, 0.0, ["Question text is empty or too short."]

    # Step 1: Detect banned enterprise buzzwords
    for pat in BANNED_ENTERPRISE_PHRASES:
        match = re.search(pat, question_text, re.IGNORECASE)
        if match:
            issues.append(f"Contains generic banned enterprise phrase: '{match.group(0)}'")
            deductions += 15.0

    # Step 2: Check for raw uncorrected syllabus artifacts
    if re.search(r'\bIntroducing\s+to\s+R\b', question_text, re.IGNORECASE):
        issues.append("Contains awkward phrasing 'Introducing to R' (should be 'Introduction to R').")
        deductions += 10.0

    if re.search(r'\baccessing\s+keyboard\s+and\s+monitor\b', question_text, re.IGNORECASE):
        issues.append("Contains literal syllabus heading 'accessing keyboard and monitor' without proper phrasing.")
        deductions += 10.0

    # Step 3: Check subject-verb & structural completeness
    tokens = question_text.split()
    if len(tokens) < 5:
        issues.append("Incomplete question stem (fewer than 5 words).")
        deductions += 20.0

    if not any(question_text.strip().endswith(p) for p in [".", "?", ":"]):
        issues.append("Missing terminal punctuation.")
        deductions += 5.0

    # Step 4: Check for repeated adjacent words (e.g., "in in", "the the")
    dup_match = re.search(r'\b([a-zA-Z]{2,})\s+\1\b', question_text, re.IGNORECASE)
    if dup_match:
        issues.append(f"Repeated adjacent word detected: '{dup_match.group(0)}'")
        deductions += 8.0

    # Clean the question text
    corrected_text = clean_academic_language(question_text)

    # Re-check after cleaning
    remaining_banned = any(re.search(pat, corrected_text, re.IGNORECASE) for pat in BANNED_ENTERPRISE_PHRASES)
    if not remaining_banned and issues:
        # Penalties softened if clean_academic_language successfully repaired the phrase
        deductions = max(0.0, deductions - 15.0)

    score = max(0.0, min(100.0, 100.0 - deductions))
    return corrected_text, round(score, 1), issues

def validate_option_grammar(option_text: str) -> Tuple[str, float, List[str]]:
    """
    Validates academic grammar and absence of generic buzzwords specifically for MCQ options.
    Allows concise answers, mathematical symbols (e.g. `%*%`), and code expressions.
    """
    issues = []
    deductions = 0.0
    trimmed = (option_text or "").strip()
    if not trimmed:
        return trimmed, 0.0, ["Option text is empty."]

    # Step 1: Detect banned enterprise buzzwords
    for pat in BANNED_ENTERPRISE_PHRASES:
        match = re.search(pat, trimmed, re.IGNORECASE)
        if match:
            issues.append(f"Contains generic banned enterprise phrase: '{match.group(0)}'")
            deductions += 25.0

    # Step 2: Check for raw uncorrected syllabus artifacts
    if re.search(r'\bIntroducing\s+to\s+R\b', trimmed, re.IGNORECASE):
        issues.append("Contains awkward phrasing 'Introducing to R'.")
        deductions += 15.0

    # Step 3: Check for repeated adjacent words
    dup_match = re.search(r'\b([a-zA-Z]{2,})\s+\1\b', trimmed, re.IGNORECASE)
    if dup_match:
        issues.append(f"Repeated adjacent word detected: '{dup_match.group(0)}'")
        deductions += 10.0

    corrected = clean_academic_language(trimmed)
    score = max(0.0, min(100.0, 100.0 - deductions))
    return corrected, round(score, 1), issues

