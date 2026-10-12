import re
from typing import Dict, Any, Optional, Tuple
from rapidfuzz import fuzz

# Access Classification Categories
ACCESS_VERIFIED_OPEN = "Verified open-access full text"
ACCESS_PUBLIC_DOMAIN = "Public-domain full text"
ACCESS_BORROWING = "Borrowing available"
ACCESS_PREVIEW = "Preview available"
ACCESS_CATALOGUE = "Catalogue record"
ACCESS_PUBLISHER = "Publisher or purchase page"
ACCESS_GENERAL = "General discovery link"
ACCESS_NONE = "No verified access found"

def get_access_color(access_type: str) -> str:
    """Return color designation for access classification tier."""
    if access_type in (ACCESS_VERIFIED_OPEN, ACCESS_PUBLIC_DOMAIN):
        return "green"
    elif access_type in (ACCESS_BORROWING, ACCESS_PREVIEW):
        return "blue"
    elif access_type in (ACCESS_CATALOGUE, ACCESS_PUBLISHER):
        return "orange"
    elif access_type == ACCESS_GENERAL:
        return "grey"
    return "red"

# Candidate Match Classifications
MATCH_EXACT = "Exact Match"
MATCH_PROBABLE = "Probable Match"
MATCH_DIFFERENT_EDITION = "Different Edition"
MATCH_RELATED = "Related Book"
MATCH_METADATA_ONLY = "Metadata Only"
MATCH_REJECTED = "Rejected Match"

# Transparent Match Weights (Specification Section 5)
WEIGHT_ISBN = 40.0      # 40%
WEIGHT_TITLE = 25.0     # 25%
WEIGHT_AUTHOR = 15.0    # 15%
WEIGHT_EDITION = 8.0    # 8%
WEIGHT_PUBLISHER = 5.0  # 5%
WEIGHT_YEAR = 4.0       # 4%
WEIGHT_TOPIC = 3.0      # 3%

def clean_str(val: Any) -> str:
    if not val:
        return ""
    return str(val).strip().lower()

def calculate_transparent_match_score(
    query_book: Dict[str, Any],
    candidate_item: Dict[str, Any],
    syllabus_topic: Optional[str] = None
) -> Tuple[float, str, str, Dict[str, float]]:
    """
    Calculate transparent match score across the 7 weighted components:
    - ISBN match:                 40%
    - Exact normalized title:     25%
    - Author match:               15%
    - Edition match:              8%
    - Publisher match:            5%
    - Publication-year match:     4%
    - Syllabus-topic relevance:   3%
    Total = 100%

    Returns (total_score, classification, summary_explanation, breakdown_dict)
    """
    breakdown = {
        "isbn": 0.0,
        "title": 0.0,
        "author": 0.0,
        "edition": 0.0,
        "publisher": 0.0,
        "year": 0.0,
        "topic": 0.0
    }
    factors = []

    # 1. ISBN Match (40%) - Highest Priority
    q_isbn = clean_str(query_book.get("isbn") or query_book.get("isbn_13") or query_book.get("isbn_10")).replace("-", "")
    c_isbn = clean_str(candidate_item.get("isbn") or candidate_item.get("isbn_13") or candidate_item.get("isbn_10")).replace("-", "")
    
    is_exact_isbn = False
    if q_isbn and c_isbn:
        if q_isbn == c_isbn or q_isbn in c_isbn or c_isbn in q_isbn:
            breakdown["isbn"] = WEIGHT_ISBN
            factors.append("Exact ISBN match (+40%)")
            is_exact_isbn = True
    elif not q_isbn and not c_isbn:
        # Neutral if neither specifies ISBN
        breakdown["isbn"] = 0.0

    # 2. Exact Normalized Title (25%)
    q_title = clean_str(query_book.get("title") or query_book.get("book_title"))
    c_title = clean_str(candidate_item.get("title") or candidate_item.get("book_title"))

    title_sim = 0.0
    if q_title and c_title:
        title_ratio = fuzz.token_set_ratio(q_title, c_title)
        title_sim = title_ratio
        if title_ratio >= 90:
            breakdown["title"] = WEIGHT_TITLE
            factors.append("Exact Title Match (+25%)")
        elif title_ratio >= 70:
            breakdown["title"] = round((title_ratio / 100.0) * WEIGHT_TITLE, 1)
            factors.append(f"Title Match ({round(title_ratio)}%)")
        else:
            breakdown["title"] = round((title_ratio / 100.0) * WEIGHT_TITLE * 0.5, 1)

    # 3. Author Match (15%)
    q_authors = clean_str(query_book.get("authors"))
    c_authors = clean_str(candidate_item.get("authors"))
    author_mismatch = False

    if q_authors and c_authors:
        author_ratio = max(fuzz.token_set_ratio(q_authors, c_authors), fuzz.partial_ratio(q_authors, c_authors))
        q_surnames = [w.strip(".,;:\"'()") for w in q_authors.split() if len(w) >= 3 and w not in ("and", "the", "edition", "vol")]
        has_surname = any(w in c_authors for w in q_surnames)

        if has_surname or author_ratio >= 80:
            breakdown["author"] = WEIGHT_AUTHOR
            factors.append("Author Match (+15%)")
        elif author_ratio >= 60:
            breakdown["author"] = round((author_ratio / 100.0) * WEIGHT_AUTHOR, 1)
            factors.append(f"Author Match ({round(author_ratio)}%)")
        else:
            author_mismatch = True
            breakdown["author"] = 0.0
            factors.append("Different Author")
    elif q_authors and not c_authors:
        breakdown["author"] = 0.0
    else:
        breakdown["author"] = 5.0 # Partial neutral credit

    # 4. Edition Match (8%)
    q_ed = clean_str(query_book.get("edition"))
    c_ed = clean_str(candidate_item.get("edition"))
    editions_differ = False

    if q_ed and c_ed:
        ed_q_nums = re.findall(r'\d+', q_ed)
        ed_c_nums = re.findall(r'\d+', c_ed)
        if ed_q_nums and ed_c_nums:
            if ed_q_nums[0] == ed_c_nums[0]:
                breakdown["edition"] = WEIGHT_EDITION
                factors.append("Exact Edition (+8%)")
            else:
                editions_differ = True
                breakdown["edition"] = 0.0
                factors.append(f"Edition Difference ({q_ed} vs {c_ed})")
        else:
            ed_sim = fuzz.partial_ratio(q_ed, c_ed)
            if ed_sim >= 80:
                breakdown["edition"] = WEIGHT_EDITION
                factors.append("Edition Match (+8%)")
            else:
                editions_differ = True
                factors.append("Different Edition")
    elif not q_ed or not c_ed:
        breakdown["edition"] = 4.0 # Neutral when edition unstated

    # 5. Publisher Match (5%)
    q_pub = clean_str(query_book.get("publisher"))
    c_pub = clean_str(candidate_item.get("publisher"))

    if q_pub and c_pub:
        pub_sim = fuzz.partial_ratio(q_pub, c_pub)
        if pub_sim >= 75:
            breakdown["publisher"] = WEIGHT_PUBLISHER
            factors.append("Publisher Match (+5%)")
        else:
            breakdown["publisher"] = round((pub_sim / 100.0) * WEIGHT_PUBLISHER, 1)
    else:
        breakdown["publisher"] = 2.5 # Neutral

    # 6. Publication-Year Match (4%)
    q_yr = clean_str(query_book.get("publication_year"))
    c_yr = clean_str(candidate_item.get("publication_year"))

    if q_yr and c_yr:
        try:
            diff = abs(int(re.findall(r'\d{4}', q_yr)[0]) - int(re.findall(r'\d{4}', c_yr)[0]))
            if diff == 0:
                breakdown["year"] = WEIGHT_YEAR
                factors.append("Year Match (+4%)")
            elif diff <= 2:
                breakdown["year"] = 2.0
                factors.append("Year +/-2")
        except Exception:
            pass
    else:
        breakdown["year"] = 2.0 # Neutral

    # 7. Syllabus-Topic Relevance (3%)
    if syllabus_topic and (q_title or c_title):
        top_clean = clean_str(syllabus_topic)
        if top_clean in q_title or top_clean in c_title or fuzz.partial_ratio(top_clean, c_title) >= 70:
            breakdown["topic"] = WEIGHT_TOPIC
            factors.append("Topic Relevance (+3%)")
        else:
            breakdown["topic"] = 1.5
    else:
        breakdown["topic"] = 1.5

    # Sum total score
    raw_sum = sum(breakdown.values())
    if not (q_isbn or c_isbn):
        total_score = min(100.0, round((raw_sum / 60.0) * 100.0, 1))
        if breakdown["title"] >= WEIGHT_TITLE and breakdown["author"] >= WEIGHT_AUTHOR:
            total_score = max(total_score, 88.0)
    else:
        total_score = raw_sum
        if is_exact_isbn and breakdown["title"] >= 15.0:
            total_score = 100.0

    total_score = min(100.0, max(0.0, round(total_score, 1)))

    # Classification
    if author_mismatch and total_score < 50.0:
        classification = MATCH_REJECTED
    elif is_exact_isbn and total_score >= 80.0:
        classification = MATCH_EXACT
    elif editions_differ and breakdown["title"] >= 20.0 and breakdown["author"] >= 10.0:
        classification = MATCH_DIFFERENT_EDITION
    elif total_score >= 82.0:
        classification = MATCH_EXACT
    elif total_score >= 60.0:
        classification = MATCH_PROBABLE
    elif total_score >= 38.0:
        classification = MATCH_RELATED
    elif candidate_item.get("access_status") == "METADATA_ONLY" or total_score >= 20.0:
        classification = MATCH_METADATA_ONLY
    else:
        classification = MATCH_REJECTED

    summary = "; ".join(factors) if factors else "Candidate scored"
    return total_score, classification, summary, breakdown

def calculate_match_confidence(
    query_book: Dict[str, Any],
    candidate_item: Dict[str, Any]
) -> Tuple[float, str]:
    """Backward-compatible wrapper returning (confidence_score, summary)."""
    score, classification, summary, _ = calculate_transparent_match_score(query_book, candidate_item)
    return score, f"{classification}: {summary}"

def classify_access_tier(
    source: str,
    raw_metadata: Dict[str, Any],
    confidence: float
) -> Tuple[str, str, Optional[str]]:
    """
    Classify result into one of the 8 access tiers with lawful justification:
    Returns (access_type, verification_status, remarks)
    """
    if confidence < 35.0:
        return (
            ACCESS_NONE,
            "No verified access",
            "Search results did not meet confidence threshold for this title."
        )

    # Check for Open Access or Public Domain indicators
    is_open_access = raw_metadata.get("is_open_access", False)
    is_public_domain = raw_metadata.get("is_public_domain", False)
    viewability = raw_metadata.get("viewability", "").upper()
    can_borrow = raw_metadata.get("can_borrow", False)
    has_preview = raw_metadata.get("has_preview", False)
    has_fulltext = raw_metadata.get("has_fulltext", False)

    has_pdf = raw_metadata.get("has_pdf", False)

    if source == "Internet Archive" and has_pdf:
        return (
            ACCESS_VERIFIED_OPEN,
            "Direct PDF available",
            "Direct full-text scan / PDF download available on Internet Archive."
        )

    if "direct pdf" in source.lower() or "scholar (pdf)" in source.lower():
        return (
            ACCESS_VERIFIED_OPEN,
            "Direct PDF search",
            remarks or f"Targeted query for direct PDF matching exact title and author on {source}."
        )

    if is_open_access or viewability == "ALL_PAGES":
        return (
            ACCESS_VERIFIED_OPEN,
            "Verified open access",
            f"Full text is lawfully accessible under an Open Access licence via {source}."
        )

    if is_public_domain or viewability == "FULL_PUBLIC_DOMAIN":
        return (
            ACCESS_PUBLIC_DOMAIN,
            "Public domain verified",
            f"Work is in the public domain and freely available on {source}."
        )

    if can_borrow:
        return (
            ACCESS_BORROWING,
            "Lawful lending available",
            f"Controlled Digital Lending / borrowing available via {source}."
        )

    if has_preview or viewability == "PARTIAL":
        return (
            ACCESS_PREVIEW,
            "Preview available",
            f"Substantial preview and sample pages available lawfully on {source}."
        )

    if source in ("WorldCat", "Crossref", "Open Library"):
        return (
            ACCESS_CATALOGUE,
            "Catalogue record",
            f"Official bibliographic record and library location lookup on {source}."
        )

    if "publisher" in source.lower() or source in ("SpringerLink", "IEEE Xplore", "Wiley Online"):
        return (
            ACCESS_PUBLISHER,
            "Publisher landing page",
            f"Official publisher page for institutional subscription or purchase via {source}."
        )

    if raw_metadata.get("access_url"):
        return (
            ACCESS_GENERAL,
            "General discovery link",
            f"Bibliographic discovery link on {source}."
        )

    return (
        ACCESS_NONE,
        "No verified access",
        "No lawful direct full-text or preview link found."
    )
