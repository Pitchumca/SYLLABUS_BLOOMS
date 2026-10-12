import re
import json
from typing import List, Dict, Any, Optional, Tuple

KNOWN_PUBLISHERS = [
    "Morgan Kaufmann", "Elsevier", "Academic Press", "Addison-Wesley", "Addison Wesley",
    "Pearson", "Pearson Education", "Prentice Hall", "Prentice-Hall", "PHI Learning", "PHI",
    "McGraw-Hill", "McGraw Hill", "Tata McGraw-Hill", "TMH", "Wiley", "John Wiley & Sons",
    "MIT Press", "Cambridge University Press", "Cambridge", "Oxford University Press", "Oxford", "OUP",
    "Springer", "O'Reilly", "O'Reilly Media", "CRC Press", "Taylor & Francis", "Cengage", "Cengage Learning",
    "Thomson", "Sybex", "W. H. Freeman", "W.H. Freeman", "Universities Press", "S. Chand",
    "Dhanpat Rai", "Khanna Publishers", "Laxmi Publications", "Vikas Publishing", "BPB Publications",
    "Dreamtech Press", "Packt", "Packt Publishing", "No Starch Press", "No Starch", "Routledge",
    "Sams", "Manning", "Bloomsbury"
]

CANONICAL_PUBLISHERS = {
    "morgan kaufmann publishers": "Morgan Kaufmann",
    "morgan kaufmann": "Morgan Kaufmann",
    "elsevier inc": "Elsevier",
    "elsevier": "Elsevier",
    "academic press": "Academic Press",
    "addison-wesley professional": "Addison-Wesley",
    "addison wesley": "Addison-Wesley",
    "addison-wesley": "Addison-Wesley",
    "pearson education": "Pearson",
    "pearson": "Pearson",
    "prentice hall of india": "Prentice Hall",
    "prentice-hall": "Prentice Hall",
    "prentice hall": "Prentice Hall",
    "phi learning": "PHI Learning",
    "phi": "PHI Learning",
    "mcgraw-hill education": "McGraw-Hill",
    "tata mcgraw-hill": "McGraw-Hill",
    "tata mcgraw hill": "McGraw-Hill",
    "mcgraw-hill": "McGraw-Hill",
    "mcgraw hill": "McGraw-Hill",
    "tmh": "McGraw-Hill",
    "john wiley & sons": "John Wiley & Sons",
    "john wiley and sons": "John Wiley & Sons",
    "john wiley": "John Wiley & Sons",
    "wiley": "Wiley",
    "mit press": "MIT Press",
    "cambridge university press": "Cambridge University Press",
    "cup": "Cambridge University Press",
    "oxford university press": "Oxford University Press",
    "oup": "Oxford University Press",
    "springer verlag": "Springer",
    "springer": "Springer",
    "o'reilly media": "O'Reilly",
    "o'reilly": "O'Reilly",
    "crc press": "CRC Press",
    "taylor & francis": "Taylor & Francis",
    "cengage learning": "Cengage",
    "cengage": "Cengage",
    "thomson": "Thomson",
    "sybex": "Sybex",
    "w. h. freeman": "W. H. Freeman",
    "w.h. freeman": "W. H. Freeman",
    "universities press": "Universities Press",
    "s. chand": "S. Chand",
    "dhanpat rai": "Dhanpat Rai",
    "khanna publishers": "Khanna Publishers",
    "laxmi publications": "Laxmi Publications",
    "vikas publishing": "Vikas Publishing",
    "bpb publications": "BPB Publications",
    "dreamtech press": "Dreamtech Press",
    "packt publishing": "Packt",
    "packt": "Packt",
    "no starch press": "No Starch Press",
    "no starch": "No Starch Press",
    "routledge": "Routledge",
    "bloomsbury": "Bloomsbury"
}

def clean_isbn(isbn_str: str) -> str:
    """Strip hyphens, spaces, and punctuation from ISBN."""
    return re.sub(r"[^0-9X-]", "", isbn_str.upper()).replace("-", "").strip()

def validate_isbn_10(isbn: str) -> bool:
    """Validate standard 10-digit ISBN."""
    cleaned = clean_isbn(isbn)
    if len(cleaned) != 10:
        return False
    if not (cleaned[:9].isdigit() and (cleaned[9].isdigit() or cleaned[9] == 'X')):
        return False
    total = sum((10 - i) * (int(c) if c != 'X' else 10) for i, c in enumerate(cleaned))
    return total % 11 == 0

def validate_isbn_13(isbn: str) -> bool:
    """Validate standard 13-digit ISBN (EAN)."""
    cleaned = clean_isbn(isbn)
    if len(cleaned) != 13 or not cleaned.isdigit():
        return False
    if not (cleaned.startswith("978") or cleaned.startswith("979")):
        return False
    total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(cleaned))
    return total % 10 == 0

def normalize_isbns(val: Any) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract independent isbn_10 and isbn_13 from string, list, or dict.
    Returns (isbn_10, isbn_13).
    """
    if not val:
        return None, None

    raw_candidates = []
    if isinstance(val, (list, tuple, set)):
        for item in val:
            if isinstance(item, str):
                raw_candidates.extend(re.split(r"[,;\s]+", item))
            elif isinstance(item, dict):
                raw_candidates.append(str(item.get("identifier") or ""))
    elif isinstance(val, str):
        raw_candidates = re.split(r"[,;\s]+", val)
    elif isinstance(val, dict):
        raw_candidates.append(str(val.get("identifier") or ""))

    isbn_10 = None
    isbn_13 = None

    for cand in raw_candidates:
        cand_clean = clean_isbn(cand)
        if len(cand_clean) == 13 and cand_clean.isdigit():
            if not isbn_13:
                isbn_13 = cand_clean
        elif len(cand_clean) == 10 and (cand_clean[:9].isdigit() and (cand_clean[9].isdigit() or cand_clean[9] == 'X')):
            if not isbn_10:
                isbn_10 = cand_clean

    return isbn_10, isbn_13

def normalize_single_author_name(author_str: str) -> str:
    """
    Normalize an individual author name.
    Converts "Han, Jiawei" -> "Jiawei Han".
    Preserves "Jiawei Han" as "Jiawei Han".
    Removes extraneous punctuation and whitespace.
    """
    name = author_str.strip().strip(",;.")
    if not name:
        return ""

    # Check for inverted "Last, First" format
    if "," in name:
        parts = [p.strip() for p in name.split(",") if p.strip()]
        if len(parts) == 2:
            last, first = parts[0], parts[1]
            if not any(w in last.lower() for w in ["press", "univ", "dept", "inc", "ltd"]):
                name = f"{first} {last}"

    name = re.sub(r"\s+", " ", name).strip()
    return name

def normalize_authors(val: Any) -> Tuple[List[str], str]:
    """
    Normalize author(s) from either list, tuple, or string.
    Returns (authors_list, authors_display_string).
    Example presentation: ["Jiawei Han", "Micheline Kamber"], "Jiawei Han; Micheline Kamber"
    """
    if not val:
        return [], ""

    raw_list: List[str] = []
    if isinstance(val, (list, tuple)):
        for item in val:
            if isinstance(item, str) and item.strip():
                raw_list.append(item.strip())
            elif isinstance(item, dict):
                n = item.get("name") or item.get("creator") or item.get("given")
                if n:
                    raw_list.append(str(n).strip())
    elif isinstance(val, str):
        text = val.strip()
        if ";" in text:
            raw_list = [p.strip() for p in text.split(";") if p.strip()]
        else:
            clean_text = re.sub(r",?\s*(?:and|&)\s+", " ### ", text)
            chunks = [c.strip() for c in clean_text.split(" ### ") if c.strip()]
            for chunk in chunks:
                comma_parts = [p.strip() for p in chunk.split(",") if p.strip()]
                if len(comma_parts) == 1:
                    raw_list.append(comma_parts[0])
                elif len(comma_parts) == 2:
                    raw_list.append(chunk)
                elif len(comma_parts) == 3:
                    raw_list.append(f"{comma_parts[0]}, {comma_parts[1]}")
                    raw_list.append(comma_parts[2])
                elif len(comma_parts) % 2 == 0:
                    for i in range(0, len(comma_parts), 2):
                        raw_list.append(f"{comma_parts[i]}, {comma_parts[i+1]}")
                else:
                    raw_list.append(chunk)

    normalized_list = []
    for a in raw_list:
        clean_name = normalize_single_author_name(a)
        if clean_name and clean_name not in normalized_list:
            normalized_list.append(clean_name)

    display_str = "; ".join(normalized_list) if normalized_list else ""
    return normalized_list, display_str

def normalize_title_and_subtitle(title_val: Any) -> Tuple[str, Optional[str]]:
    """
    Normalize title and subtitle from string or list.
    Handles colon separators without splitting haphazardly.
    Returns (normalized_full_title, subtitle).
    """
    if not title_val:
        return "", None

    if isinstance(title_val, (list, tuple)):
        title_str = str(title_val[0]).strip() if title_val else ""
    else:
        title_str = str(title_val).strip()

    if not title_str:
        return "", None

    cleaned = re.sub(r"\s*:\s*", ": ", title_str).strip()
    parts = cleaned.split(": ")
    main_title = parts[0].strip()
    subtitle = parts[1].strip() if len(parts) > 1 else None

    def cap_words(s: str) -> str:
        words = s.split()
        if not words:
            return s
        out = []
        lower_exceptions = {"a", "an", "the", "and", "but", "or", "for", "nor", "on", "at", "to", "by", "in", "of"}
        for i, w in enumerate(words):
            w_lower = w.lower()
            if i == 0 or i == len(words) - 1 or w_lower not in lower_exceptions:
                out.append(w.capitalize() if w.islower() else w)
            else:
                out.append(w_lower)
        return " ".join(out)

    norm_main = cap_words(main_title)
    norm_sub = cap_words(subtitle) if subtitle else None
    
    return norm_main, norm_sub

def normalize_publisher(pub_val: Any) -> Optional[str]:
    """
    Extract authoritative academic publisher from string or list and map to canonical name.
    E.g., "Morgan Kaufmann Publishers" and "Morgan Kaufmann" -> "Morgan Kaufmann"
    """
    if not pub_val:
        return None

    raw_text = ""
    if isinstance(pub_val, (list, tuple)):
        raw_text = " ; ".join(str(p) for p in pub_val if p)
    else:
        raw_text = str(pub_val).strip()

    if not raw_text:
        return None

    clean_raw = raw_text.lower().strip()
    # Direct canonical lookup
    for var, canon in sorted(CANONICAL_PUBLISHERS.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(r"\b" + re.escape(var) + r"\b", clean_raw):
            return canon

    matched = []
    for kp in sorted(KNOWN_PUBLISHERS, key=len, reverse=True):
        if re.search(r"\b" + re.escape(kp) + r"\b", raw_text, re.IGNORECASE):
            matched.append(kp)

    if matched:
        return matched[0]

    gen_match = re.search(r",\s*([A-Z][a-zA-Z\s&]+(?:Publishers?|Press|Publications?|Learning|Media|Books|Series|Inc|LLC|Ltd))\b", raw_text)
    if gen_match:
        return gen_match.group(1).strip()

    if ":" in raw_text and len(raw_text) < 60 and "," not in raw_text:
        sub = raw_text.split(":")[-1].strip()
        if len(sub) > 2:
            return sub

    return raw_text.strip() if len(raw_text) < 60 else None

def normalize_publication_year(date_val: Any, year_val: Any = None) -> Optional[str]:
    """Extract standard 4-digit publication year (1800-2035)."""
    candidates = []
    if year_val:
        if isinstance(year_val, (list, tuple)):
            candidates.extend(str(y) for y in year_val)
        else:
            candidates.append(str(year_val))

    if date_val:
        if isinstance(date_val, (list, tuple)):
            candidates.extend(str(d) for d in date_val)
        else:
            candidates.append(str(date_val))

    for cand in candidates:
        match = re.search(r"(?:^|[^\d])(1[89]\d\d|20[0-3]\d)(?:[^\d]|$)", str(cand))
        if match:
            return match.group(1)

    return None

ORDINAL_EDITIONS = {
    "first": "1st Edition",
    "second": "2nd Edition",
    "third": "3rd Edition",
    "fourth": "4th Edition",
    "fifth": "5th Edition",
    "sixth": "6th Edition",
    "seventh": "7th Edition",
    "eighth": "8th Edition",
    "ninth": "9th Edition",
    "tenth": "10th Edition",
    "revised": "Revised Edition",
    "international": "International Edition",
    "global": "Global Edition"
}

def normalize_edition(edition_val: Any) -> str:
    """
    Extract standard edition string e.g. '1st Edition', '2nd Edition', etc.
    Correctly normalizes variations:
    '2', '2nd', 'Second Edition' -> '2nd Edition'
    When unconfirmed or None, returns 'Not available'.
    """
    if not edition_val:
        return "Not available"
    val_str = str(edition_val[0] if isinstance(edition_val, (list, tuple)) else edition_val).strip()
    if not val_str:
        return "Not available"
    val_clean = val_str.lower().strip().strip(".,;")

    # Check words like "second edition", "2nd edition", "2nd ed", "second"
    for word, norm in ORDINAL_EDITIONS.items():
        if re.search(r"\b" + re.escape(word) + r"(?:\s*ed(?:ition|\.)?)?\b", val_clean):
            return norm

    # Check digits like "2", "2nd", "2nd edition", "3rd ed."
    num_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?(?:\s*ed(?:ition|\.)?)?\b", val_clean)
    if num_match:
        matched_str = num_match.group(0).strip()
        has_suffix_or_ed = bool(re.search(r"(?:st|nd|rd|th|\bed)", matched_str, re.IGNORECASE))
        if has_suffix_or_ed or val_clean == num_match.group(1):
            n = int(num_match.group(1))
            suffix = "th"
            if n % 10 == 1 and n % 100 != 11:
                suffix = "st"
            elif n % 10 == 2 and n % 100 != 12:
                suffix = "nd"
            elif n % 10 == 3 and n % 100 != 13:
                suffix = "rd"
            return f"{n}{suffix} Edition"

    return val_str if len(val_str) < 50 else "Not available"

def kp_match(pub: str, text: str) -> bool:
    return pub.lower() in text.lower() or text.lower() in pub.lower()

TITLE_INDICATORS = {
    "introduction", "introducing", "introductory", "fundamentals", "principles",
    "handbook", "guide", "programming", "algorithms", "data", "structures",
    "concepts", "techniques", "learning", "art", "science", "engineering",
    "analytics", "statistical", "statistics", "software", "design", "systems",
    "networks", "database", "modern", "complete", "applied", "advanced",
    "beginning", "action", "practice", "approach", "theory", "foundations",
    "visualisation", "visualization", "machine", "intelligence", "computing"
}

def is_likely_title_text(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    if ":" in t or " - " in t or " -- " in t or " – " in t or " — " in t:
        return True
    lower_words = set(re.findall(r"\b[a-z]+\b", t.lower()))
    return len(lower_words.intersection(TITLE_INDICATORS)) > 0

def is_likely_author(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    if ":" in t or " - " in t or " -- " in t or " – " in t or " — " in t:
        return False
    words = set(re.findall(r"\b[a-z]+\b", t.lower()))
    if len(words.intersection(TITLE_INDICATORS)) >= 1:
        return False
    if re.search(r"\b[A-Z]\.\s*[A-Z]?", t):
        return True
    parts = t.split()
    if 1 <= len(parts) <= 4 and all(w[0].isupper() or w in ["de", "van", "von", "al.", "and", "&", "Dr.", "Prof."] for w in parts if w):
        return True
    return False

def parse_structured_citation(raw_citation: str) -> Dict[str, Any]:
    """
    Parse a syllabus citation line without blind comma splitting.
    Keeps titles, subtitles, and author lists with commas intact.
    """
    text = raw_citation.strip()
    text = re.sub(r"^(?:(?:T|R|TB|RB)\s*\d+[\.:\s]|\[\d+\]|\(\d+\)|\d+[\.\)]|[-•\*\uf0b7])\s*", "", text).strip()

    isbn_10, isbn_13 = normalize_isbns(text)
    text_no_isbn = re.sub(r"\b(?:ISBN(?:-[103]{2})?:?\s*)?[0-9X-]{10,17}\b", "", text, flags=re.IGNORECASE).strip()

    year = normalize_publication_year(text_no_isbn)
    edition = normalize_edition(text_no_isbn)
    publisher = normalize_publisher(text_no_isbn)

    title = ""
    subtitle = None
    authors_list = []
    authors_display = ""

    # 1. Check for period-separated major segments (Author(s). Title. Publication details.)
    period_parts = [p.strip().strip(".") for p in re.split(r"(?<!\b[A-Z])\.\s+", text_no_isbn) if p.strip()]
    if len(period_parts) >= 2:
        p0 = period_parts[0]
        p1 = period_parts[1]
        is_p0_authors = not (publisher and publisher.lower() in p0.lower()) and not (year and year in p0)
        if is_p0_authors and len(p1) >= 3:
            authors_list, authors_display = normalize_authors(p0)
            title, subtitle = normalize_title_and_subtitle(p1)
            return {
                "title": title or text[:60],
                "subtitle": subtitle,
                "authors": authors_display,
                "authors_list": authors_list,
                "publisher": publisher,
                "edition": edition,
                "publication_year": year,
                "isbn_10": isbn_10,
                "isbn_13": isbn_13,
                "raw_citation": raw_citation
            }

    # Check for quotes around Title
    quote_match = re.search(r'["\u201c\']([^"\u201d\']{4,})["\u201d\']', text_no_isbn)
    if quote_match:
        raw_title = quote_match.group(1).strip()
        title, subtitle = normalize_title_and_subtitle(raw_title)
        before_title = text_no_isbn[:quote_match.start()].strip().strip(",;:")
        after_title = text_no_isbn[quote_match.end():].strip().strip(",;:")
        candidate_author = before_title or after_title
        if publisher:
            candidate_author = re.sub(re.escape(publisher), "", candidate_author, flags=re.IGNORECASE).strip()
        if year:
            candidate_author = re.sub(r"\b" + re.escape(year) + r"\b", "", candidate_author).strip()
        authors_list, authors_display = normalize_authors(candidate_author)
    else:
        chunks = [c.strip() for c in re.split(r"[,;]\s*", text_no_isbn) if c.strip()]
        filtered = []
        for c in chunks:
            if publisher and (kp_match(publisher, c) or c.lower() in publisher.lower()):
                continue
            if year and year in c:
                continue
            if edition and edition.lower() in c.lower():
                continue
            filtered.append(c)

        if len(filtered) >= 2:
            if is_likely_author(filtered[-1]) and not is_likely_author(filtered[0]):
                authors_list, authors_display = normalize_authors(filtered[-1])
                raw_title = ", ".join(filtered[:-1])
                title, subtitle = normalize_title_and_subtitle(raw_title)
            elif is_likely_author(filtered[0]) and not is_likely_author(filtered[-1]):
                authors_list, authors_display = normalize_authors(filtered[0])
                raw_title = ", ".join(filtered[1:])
                title, subtitle = normalize_title_and_subtitle(raw_title)
            elif is_likely_title_text(filtered[0]) and not is_likely_title_text(filtered[-1]):
                authors_list, authors_display = normalize_authors(filtered[-1])
                raw_title = ", ".join(filtered[:-1])
                title, subtitle = normalize_title_and_subtitle(raw_title)
            else:
                authors_list, authors_display = normalize_authors(filtered[0])
                raw_title = ", ".join(filtered[1:])
                title, subtitle = normalize_title_and_subtitle(raw_title)
        elif len(filtered) == 1:
            title, subtitle = normalize_title_and_subtitle(filtered[0])

    return {
        "title": title or text[:60],
        "subtitle": subtitle,
        "authors": authors_display,
        "authors_list": authors_list,
        "publisher": publisher,
        "edition": edition,
        "publication_year": year,
        "isbn_10": isbn_10,
        "isbn_13": isbn_13,
        "raw_citation": raw_citation
    }

def clean_citation_punctuation(text: str) -> str:
    """
    Remove duplicate punctuation, unnecessary quotation marks,
    while retaining meaningful title punctuation like colons, dashes, and hyphens.
    """
    if not text:
        return ""
    t = text.strip()
    t = re.sub(r'^["\'\u201c\u201d]+|["\'\u201c\u201d]+$', '', t).strip()
    t = re.sub(r',\s*,+', ', ', t)
    t = re.sub(r';\s*;+', '; ', t)
    t = re.sub(r'\.\s*\.+', '. ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def extract_volume(text: str) -> str:
    """Extract volume identifier e.g. 'Vol. 1', 'Volume 2'."""
    m = re.search(r'\b(?:vol(?:ume|\.)?)\s*([0-9IVX]+)\b', text, re.IGNORECASE)
    if m:
        return f"Vol. {m.group(1)}"
    return ""

def extract_doi(text: str) -> str:
    """Extract DOI identifier from citation text."""
    m = re.search(r'\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)\b', text)
    if m:
        return m.group(1).rstrip('.')
    return ""

def format_isbn_display(isbn: Optional[str]) -> str:
    """Format clean ISBN into standard hyphenated presentation for display."""
    if not isbn:
        return ""
    clean = clean_isbn(isbn)
    if len(clean) == 13:
        return f"{clean[:3]}-{clean[3]}-{clean[4:9]}-{clean[9:12]}-{clean[12]}"
    elif len(clean) == 10:
        return f"{clean[0]}-{clean[1:6]}-{clean[6:9]}-{clean[9]}"
    return clean

def parse_author_details(author_val: Any) -> List[Dict[str, Any]]:
    """
    Extract separated given_name, family_name, display_name, and role.
    Handles multiple authors, initials (e.g. 'J. Han' -> given_name='J.', family_name='Han'),
    and detects editors.
    """
    raw_list, _ = normalize_authors(author_val)
    authors_out = []

    for idx, auth_str in enumerate(raw_list):
        cleaned = clean_citation_punctuation(auth_str)
        role = "author"
        if re.search(r"\b(?:ed(?:s|\.)?|editors?)\b", cleaned, re.IGNORECASE):
            role = "editor"
            cleaned = re.sub(r"[\(\[\{]?(?:ed(?:s|\.)?|editors?)[\)\]\}]?", "", cleaned, flags=re.IGNORECASE).strip().strip(",;.")

        if not cleaned:
            continue

        parts = cleaned.split()
        if len(parts) == 1:
            given_name = ""
            family_name = parts[0]
            display_name = parts[0]
        elif len(parts) == 2:
            given_name = parts[0]
            family_name = parts[1]
            display_name = f"{given_name} {family_name}"
        else:
            given_name = " ".join(parts[:-1])
            family_name = parts[-1]
            display_name = f"{given_name} {family_name}"

        authors_out.append({
            "given_name": given_name,
            "family_name": family_name,
            "display_name": display_name,
            "role": role,
            "order_index": idx
        })

    return authors_out

def extract_structured_book(raw_citation: str, resource_type: str = "TEXTBOOK") -> Dict[str, Any]:
    """
    Extract a book citation into the strict required structured output schema:
    {
      "resource_type": "TEXTBOOK",
      "authors": [{"given_name": "Jiawei", "family_name": "Han", "display_name": "Jiawei Han"}],
      "book_title": "Data Mining: Concepts and Techniques",
      "subtitle": "",
      "publisher": "Morgan Kaufmann",
      "edition": "1st Edition",
      "publication_year": 2001,
      "isbn_10": "",
      "isbn_13": "",
      "volume": "",
      "doi": "",
      "original_citation": "",
      "metadata_confidence": 0.98
    }
    Never places author, title, publisher and edition in one unstructured field.
    When a field cannot be confirmed, displays 'Not available' or empty string.
    """
    cleaned_citation = clean_citation_punctuation(raw_citation)
    parsed = parse_structured_citation(cleaned_citation)

    raw_authors = parsed.get("authors_list") or []
    authors_details = parse_author_details(raw_authors if raw_authors else parsed.get("authors"))

    vol = extract_volume(raw_citation)
    doi = extract_doi(raw_citation)

    pub_year_val = parsed.get("publication_year")
    try:
        year_int = int(pub_year_val) if pub_year_val else None
    except Exception:
        year_int = None

    # Calculate metadata confidence (0.0 to 1.0)
    conf = 0.50
    if parsed.get("title") and len(parsed["title"]) > 5:
        conf += 0.20
    if authors_details:
        conf += 0.15
    if parsed.get("publisher"):
        conf += 0.05
    if year_int:
        conf += 0.04
    if parsed.get("edition"):
        conf += 0.03
    if parsed.get("isbn_13") or parsed.get("isbn_10"):
        conf += 0.03
    conf = min(0.99, round(conf, 2))

    return {
        "resource_type": resource_type,
        "authors": [
            {
                "given_name": a.get("given_name", ""),
                "family_name": a.get("family_name", ""),
                "display_name": a.get("display_name", "")
            }
            for a in authors_details
        ],
        "book_title": parsed.get("title") or "Not available",
        "subtitle": parsed.get("subtitle") or "",
        "publisher": parsed.get("publisher") or "Not available",
        "edition": parsed.get("edition") or "Not available",
        "publication_year": year_int if year_int is not None else "Not available",
        "isbn_10": parsed.get("isbn_10") or "",
        "isbn_13": parsed.get("isbn_13") or "",
        "volume": vol,
        "doi": doi,
        "original_citation": raw_citation,
        "metadata_confidence": conf
    }

def calculate_metadata_confidence(book: Dict[str, Any]) -> float:
    """
    Calculate bibliographic metadata confidence score (0-100%).
    Evaluates completeness and specificity across core bibliographic attributes.
    """
    score = 0.0
    if book.get("book_title") or book.get("title"):
        score += 35.0
    if book.get("authors") or book.get("authors_list"):
        score += 25.0
    if book.get("publisher") and book.get("publisher") != "Not available":
        score += 15.0
    if book.get("edition") and book.get("edition") != "Not available":
        score += 10.0
    if book.get("publication_year") and book.get("publication_year") != "Not available":
        score += 5.0
    if book.get("isbn") or book.get("isbn_13") or book.get("isbn_10"):
        score += 10.0
    return min(100.0, max(0.0, score))


