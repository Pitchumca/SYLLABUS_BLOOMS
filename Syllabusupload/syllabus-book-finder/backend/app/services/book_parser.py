import re
from typing import List, Dict, Any, Optional, Tuple
from rapidfuzz import fuzz

# Common Academic Publishers
KNOWN_PUBLISHERS = [
    "No Starch Press", "No Starch", "Amazon Digital South Asia Services Inc", "Amazon Digital", "Amazon",
    "Pearson", "Pearson Education", "McGraw-Hill", "McGraw Hill", "Tata McGraw-Hill", "TMH",
    "Wiley", "John Wiley & Sons", "Prentice Hall", "Prentice-Hall", "PHI", "PHI Learning",
    "Oxford University Press", "Oxford", "OUP", "Cambridge University Press", "Cambridge", "CUP",
    "Springer", "MIT Press", "Addison-Wesley", "Addison Wesley", "O'Reilly", "O'Reilly Media",
    "CRC Press", "Taylor & Francis", "Elsevier", "Morgan Kaufmann", "Academic Press",
    "Cengage", "Cengage Learning", "Thomson", "Sybex", "W. H. Freeman", "W.H. Freeman",
    "Universities Press", "University Press", "S. Chand", "Dhanpat Rai", "Khanna Publishers",
    "Laxmi Publications", "Vikas Publishing", "BPB Publications", "Dreamtech Press", "Packt", "Packt Publishing",
    "Bloomsbury", "Routledge", "Sams", "Manning"
]

# Section Heading Patterns
TEXTBOOK_HEADERS = [
    r"text\s*books?",
    r"prescribed\s*books?",
    r"core\s*books?",
    r"course\s*books?",
    r"prescribed\s*text\s*books?",
    r"text\s*and\s*reference\s*books?",
    r"prescribed\s*texts?"
]

REFERENCE_HEADERS = [
    r"reference\s*books?",
    r"references?",
    r"suggested\s*readings?",
    r"additional\s*readings?",
    r"additional\s*resources?",
    r"recommended\s*books?",
    r"other\s*references?",
    r"supplementary\s*books?",
    r"web\s*references?"
]

SECTION_BREAKERS = [
    r"course\s*outcomes?",
    r"course\s*objectives?",
    r"prerequisites?",
    r"syllabus",
    r"module\s*[-–:]?\s*[1-5IVX]+",
    r"unit\s*[-–:]?\s*[1-5IVX]+",
    r"evaluation\s*scheme",
    r"continuous\s*assessment",
    r"laboratory",
    r"practical\s*sessions?",
    r"scheme\s*of\s*examination",
    r"question\s*paper\s*pattern",
    r"credits",
    r"course\s*code",
    r"course\s*designers?",
    r"faculty\s*(?:members?|details?)?",
    r"designers?",
    r"board\s*of\s*studies",
    r"web\s*references?",
    r"online\s*resources?",
    r"mooc",
    r"nptel",
    r"swayam",
    r"prepared\s*by",
    r"approved\s*by",
    r"s\.no\b"
]

def clean_text_lines(text: str) -> List[str]:
    """Clean and standardize text into non-empty stripped lines."""
    lines = []
    for line in text.splitlines():
        # Remove page delimiter lines like '--- Page 1 ---'
        if re.match(r"^---\s*Page\s*\d+.*---$", line.strip(), re.IGNORECASE):
            continue
        cleaned = line.replace('\ufffd', '-').replace('\u2013', '-').replace('\u2014', '-').replace('\uf0b7', '•').strip()
        if cleaned:
            lines.append(cleaned)
    return lines

def identify_sections(lines: List[str]) -> List[Tuple[str, List[str]]]:
    """
    Split text into logical sections based on headings:
    Returns list of tuples: (section_category, section_lines)
    where section_category is 'Textbook', 'Reference Book', or 'Other'
    """
    sections = []
    current_category = None
    current_lines = []

    textbook_regex = re.compile(r"^(?:[\d\.\-\*•\s]*)\b(" + "|".join(TEXTBOOK_HEADERS) + r")\b[:\s\-]*$", re.IGNORECASE)
    ref_regex = re.compile(r"^(?:[\d\.\-\*•\s]*)\b(" + "|".join(REFERENCE_HEADERS) + r")\b[:\s\-]*$", re.IGNORECASE)
    breaker_regex = re.compile(r"^(?:[\d\.\-\*•\s]*)\b(" + "|".join(SECTION_BREAKERS) + r")\b[:\s\-]*", re.IGNORECASE)

    for line in lines:
        # Check if line indicates section switch
        tb_match = textbook_regex.match(line)
        ref_match = ref_regex.match(line)
        breaker_match = breaker_regex.match(line)

        if tb_match:
            if current_category and current_lines:
                sections.append((current_category, current_lines))
            current_category = "Textbook"
            current_lines = []
            continue
        elif ref_match:
            if current_category and current_lines:
                sections.append((current_category, current_lines))
            current_category = "Reference Book"
            current_lines = []
            continue
        elif breaker_match and current_category:
            sections.append((current_category, current_lines))
            current_category = None
            current_lines = []
            continue

        if current_category:
            current_lines.append(line)
        else:
            # Check for inline indicators like T1:, R1:, TB1:, RB1:
            if re.match(r"^(?:T\d+|TB\d+|Textbook\s*\d+)[\.:\s]", line, re.IGNORECASE):
                sections.append(("Textbook", [line]))
            elif re.match(r"^(?:R\d+|RB\d+|Reference\s*\d+)[\.:\s]", line, re.IGNORECASE):
                sections.append(("Reference Book", [line]))

    if current_category and current_lines:
        sections.append((current_category, current_lines))

    # If no explicit headings found, check if text has list items or treat all lines as potential citations
    if not sections:
        # Fallback: scan for any citation-like lines
        sections.append(("Textbook", lines))

    return sections

def group_multiline_citations(lines: List[str]) -> List[str]:
    """
    Group multi-line citations together based on numbering patterns:
    - 1., [1], 1), (1), T1., R1., •, -
    Lines not starting with a new item marker are appended to the previous citation.
    """
    citations = []
    current_citation = []
    
    # Matches starting with 1., [1], 1), T1., R1., TB1:, •, etc.
    start_pattern = re.compile(
        r"^(?:(?:T|R|TB|RB)\s*\d+[\.:\s]|\[\d+\]|\(\d+\)|\d+[\.\)]|[-•\*\uf0b7])\s*",
        re.IGNORECASE
    )

    for line in lines:
        is_new_item = bool(start_pattern.match(line))
        
        # Also treat lines starting with known author patterns after an empty break as new items
        if is_new_item:
            if current_citation:
                citations.append(" ".join(current_citation))
            current_citation = [line]
        else:
            if current_citation:
                current_citation.append(line)
            else:
                # First line without bullet
                current_citation = [line]

    if current_citation:
        citations.append(" ".join(current_citation))

    return citations

def extract_isbn(text: str) -> Optional[str]:
    """Extract standard ISBN-10 or ISBN-13 from text."""
    # 1. Try ISBN-13 (starts with 978 or 979, with optional hyphens/spaces)
    isbn13_match = re.search(
        r"\b(?:ISBN(?:-13)?:?\s*)?(97[89][-\s]?[0-9]{1,5}[-\s]?[0-9]+[-\s]?[0-9]+[-\s]?[0-9])\b",
        text,
        re.IGNORECASE
    )
    if isbn13_match:
        cleaned = re.sub(r"[-\s]", "", isbn13_match.group(1))
        if len(cleaned) == 13 and cleaned.isdigit():
            return cleaned

    # 2. Try ISBN-10 (9 digits + 1 check digit 0-9 or X)
    isbn10_match = re.search(
        r"\b(?:ISBN(?:-10)?:?\s*)?([0-9]{1,5}[-\s]?[0-9]{1,7}[-\s]?[0-9]{1,7}[-\s]?[0-9X])\b",
        text,
        re.IGNORECASE
    )
    if isbn10_match:
        cleaned = re.sub(r"[-\s]", "", isbn10_match.group(1))
        if len(cleaned) == 10:
            return cleaned

    return None

def extract_year(text: str) -> Optional[str]:
    """Extract a 4-digit publication year (between 1960 and 2030)."""
    # Look for year in parentheses or isolated by commas/periods
    years = re.findall(r"\b(19[6-9]\d|20[0-2]\d)\b", text)
    if years:
        # Return the most plausible last year mentioned
        return years[-1]
    return None

def extract_edition(text: str) -> Optional[str]:
    """Extract edition information."""
    edition_pattern = re.compile(
        r"\b(\d+(?:st|nd|rd|th)?\s*(?:ed(?:\.|ition)?)|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|revised|international)\s*(?:ed(?:\.|ition)?)?\b",
        re.IGNORECASE
    )
    m = edition_pattern.search(text)
    if m:
        return m.group(0).strip()
    return None

def extract_publisher(text: str) -> Optional[str]:
    """Extract academic publisher from citation."""
    for pub in KNOWN_PUBLISHERS:
        pattern = re.compile(r"\b" + re.escape(pub) + r"\b", re.IGNORECASE)
        if pattern.search(text):
            return pub
    
    # Generic publisher pattern after edition or comma
    gen_match = re.search(r",\s*([A-Z][a-zA-Z\s&]+(?:Publishers?|Press|Publications?|Learning|Media|Books|Series|Inc|LLC|Ltd))\b", text)
    if gen_match:
        return gen_match.group(1).strip()
    return None

TITLE_KEYWORDS = {
    "introduction", "introducing", "introductory", "fundamentals", "principles",
    "handbook", "guide", "programming", "algorithms", "data", "structures",
    "concepts", "techniques", "learning", "art", "science", "engineering",
    "analytics", "statistical", "statistics", "software", "design", "systems",
    "networks", "database", "modern", "complete", "applied", "advanced",
    "beginning", "action", "practice", "approach", "theory", "foundations",
    "methods", "manual", "primer", "applications", "everyone", "visualisation",
    "visualization", "machine", "intelligence", "computing", "development"
}

def is_likely_title(text: str) -> bool:
    """Determine if a text segment resembles a book title rather than an author name."""
    if not text:
        return False
    t = text.strip()
    if ":" in t or " - " in t or " -- " in t or " – " in t or " — " in t:
        return True
    low = t.lower()
    if any(low.startswith(p) for p in [
        "the ", "a ", "an ", "introduction", "introductory", "beginning ",
        "fundamentals ", "principles ", "advanced ", "learning ", "r for "
    ]):
        return True
    words = set(re.findall(r"\b[a-zA-Z]+\b", low))
    return len(words & TITLE_KEYWORDS) >= 1

def is_likely_author(text: str) -> bool:
    """Determine if a text segment resembles author name(s) rather than a book title."""
    if not text:
        return False
    t = text.strip()
    if ":" in t:
        return False
    words = set(re.findall(r"\b[a-zA-Z]+\b", t.lower()))
    if len(words & TITLE_KEYWORDS) >= 1:
        return False
    if re.search(r"\b[A-Z]\.\s*[A-Z]?", t):
        return True
    parts = t.split()
    if 1 <= len(parts) <= 4 and all(w[0].isupper() or w in ["de", "van", "von", "al.", "and", "&", "Dr.", "Prof."] for w in parts if w):
        return True
    return False

def parse_single_citation(raw_citation: str, category: str = "Textbook") -> Dict[str, Any]:
    """
    Parse a single raw citation string into structured bibliographic metadata.
    Avoids blind comma-splitting so titles and author lists containing commas are preserved.
    """
    citation_clean = raw_citation.strip()
    
    # Strip any accidental trailing section breaker headers attached to citation
    for breaker in [r"\bCOURSE\s*DESIGNERS\b.*", r"\bS\.No\b.*Name\s+of\s+the\s+Faculty.*", r"\bCOURSE\s*OUTCOMES?\b.*"]:
        citation_clean = re.sub(breaker, "", citation_clean, flags=re.IGNORECASE).strip()

    # 1. Strip leading list numbers/bullets: "1.", "[1]", "T1:", "•", etc.
    cleaned_body = re.sub(
        r"^(?:(?:T|R|TB|RB)\s*\d+[\.:\s]|\[\d+\]|\(\d+\)|\d+[\.\)]|[-•\*\uf0b7])\s*",
        "",
        citation_clean,
        flags=re.IGNORECASE
    ).strip()

    from app.services.bibliography_parser import parse_structured_citation
    parsed = parse_structured_citation(citation_clean)

    title = parsed.get("title") or ""
    subtitle = parsed.get("subtitle")
    authors = parsed.get("authors") or ""
    authors_list = parsed.get("authors_list") or []
    publisher = parsed.get("publisher") or extract_publisher(cleaned_body)
    year = parsed.get("publication_year") or extract_year(cleaned_body)
    edition = parsed.get("edition") or extract_edition(cleaned_body)
    isbn = parsed.get("isbn_13") or parsed.get("isbn_10") or extract_isbn(cleaned_body)
    isbn_10 = parsed.get("isbn_10")
    isbn_13 = parsed.get("isbn_13")

    if not title:
        title = cleaned_body[:100]

    # Compute a parsing confidence score (0-100)
    score = 30.0 # Base score for finding citation
    if title and len(title) > 5:
        score += 25.0
    if authors and len(authors) > 2:
        score += 15.0
    if publisher:
        score += 10.0
    if year:
        score += 10.0
    if edition:
        score += 5.0
    if isbn:
        score += 5.0

    from app.services.bibliography_parser import parse_author_details, extract_volume, extract_doi
    authors_structured = parse_author_details(authors_list if authors_list else authors)
    vol = extract_volume(citation_clean)
    doi = extract_doi(citation_clean)
    res_type = "TEXTBOOK" if category == "Textbook" else "REFERENCE_BOOK"

    return {
        "category": category,
        "resource_type": res_type,
        "title": title,
        "subtitle": subtitle,
        "authors": authors or None,
        "authors_list": authors_list,
        "authors_structured": authors_structured,
        "edition": edition or None,
        "publisher": publisher or None,
        "publication_year": year or None,
        "isbn": isbn or None,
        "isbn_10": isbn_10 or None,
        "isbn_13": isbn_13 or None,
        "volume": vol or None,
        "doi": doi or None,
        "raw_citation": citation_clean,
        "confidence_score": round(score, 1)
    }

def detect_and_parse_books(full_text: str) -> List[Dict[str, Any]]:
    """
    Main extraction pipeline:
    1. Clean lines
    2. Identify Textbook vs Reference Book sections
    3. Group multiline citations
    4. Parse each citation into fields
    5. Flag potential duplicates
    """
    lines = clean_text_lines(full_text)
    sections = identify_sections(lines)
    
    extracted_books = []
    
    for category, sec_lines in sections:
        grouped_citations = group_multiline_citations(sec_lines)
        for cit in grouped_citations:
            # Skip very short noise lines
            if len(cit.strip()) < 10:
                continue
            book = parse_single_citation(cit, category=category)
            # Filter out non-book noise (e.g. headers or URLs alone)
            if book["title"].lower().startswith("http") or book["title"].lower() in ["text books", "reference books"]:
                continue
            extracted_books.append(book)

    # Flag duplicates
    flag_duplicates(extracted_books)

    return extracted_books

def flag_duplicates(books: List[Dict[str, Any]]):
    """Detect similar or duplicate books within the parsed list using RapidFuzz."""
    for i in range(len(books)):
        books[i]["is_duplicate"] = False

    for i in range(len(books)):
        for j in range(i + 1, len(books)):
            b1 = books[i]
            b2 = books[j]
            
            # 1. ISBN match
            if b1.get("isbn") and b2.get("isbn") and b1["isbn"] == b2["isbn"]:
                books[j]["is_duplicate"] = True
                continue

            # 2. High title similarity
            title_sim = fuzz.token_set_ratio(b1["title"], b2["title"])
            if title_sim > 88:
                # If authors also similar or missing
                if b1.get("authors") and b2.get("authors"):
                    author_sim = fuzz.partial_ratio(b1["authors"], b2["authors"])
                    if author_sim > 70:
                        books[j]["is_duplicate"] = True
                else:
                    books[j]["is_duplicate"] = True

def detect_and_parse_books_structured(full_text: str) -> List[Dict[str, Any]]:
    """
    Extract textbooks and reference books separately into the exact required structured schema:
    {
      "resource_type": "TEXTBOOK",
      "authors": [
        {"given_name": "Jiawei", "family_name": "Han", "display_name": "Jiawei Han"}
      ],
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
    """
    from app.services.bibliography_parser import extract_structured_book
    lines = clean_text_lines(full_text)
    sections = identify_sections(lines)
    
    structured_books = []
    for category, sec_lines in sections:
        grouped_citations = group_multiline_citations(sec_lines)
        res_type = "TEXTBOOK" if category == "Textbook" else "REFERENCE_BOOK"
        for cit in grouped_citations:
            if len(cit.strip()) < 10:
                continue
            book_obj = extract_structured_book(cit, resource_type=res_type)
            if book_obj["book_title"].lower().startswith("http") or book_obj["book_title"].lower() in ["text books", "reference books"]:
                continue
            structured_books.append(book_obj)

    # Deduplicate structured list
    for i in range(len(structured_books)):
        structured_books[i]["is_duplicate"] = False

    for i in range(len(structured_books)):
        for j in range(i + 1, len(structured_books)):
            b1 = structured_books[i]
            b2 = structured_books[j]
            isbn1 = b1.get("isbn_13") or b1.get("isbn_10")
            isbn2 = b2.get("isbn_13") or b2.get("isbn_10")
            if isbn1 and isbn2 and isbn1 == isbn2:
                structured_books[j]["is_duplicate"] = True
                continue
            title_sim = fuzz.token_set_ratio(b1["book_title"], b2["book_title"])
            if title_sim > 88:
                structured_books[j]["is_duplicate"] = True

    return structured_books

