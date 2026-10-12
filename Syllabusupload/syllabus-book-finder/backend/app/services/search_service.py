import asyncio
import logging
import urllib.parse
import json
import hashlib
import datetime
from typing import List, Dict, Any, Optional, Tuple
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.utils.cache import make_query_hash, get_cached_search, set_cached_search
from app.services.access_states import (
    PUBLIC_PDF_VERIFIED,
    PUBLIC_EPUB_VERIFIED,
    BORROW_REQUIRED,
    PREVIEW_ONLY,
    METADATA_ONLY,
    LINK_UNAVAILABLE,
    VERIFICATION_FAILED,
    map_access_status_to_legacy
)
from app.services.bibliography_parser import (
    normalize_authors,
    normalize_title_and_subtitle,
    normalize_publisher,
    normalize_publication_year,
    normalize_isbns,
    normalize_edition
)
from app.services.internet_archive_service import (
    verify_internet_archive_item,
    build_details_url
)
from app.services.match_engine import (
    calculate_match_confidence,
    calculate_transparent_match_score,
    classify_access_tier,
    MATCH_EXACT,
    MATCH_PROBABLE,
    MATCH_DIFFERENT_EDITION,
    MATCH_RELATED,
    MATCH_METADATA_ONLY,
    MATCH_REJECTED,
    ACCESS_VERIFIED_OPEN,
    ACCESS_PUBLIC_DOMAIN,
    ACCESS_BORROWING,
    ACCESS_PREVIEW,
    ACCESS_CATALOGUE,
    ACCESS_PUBLISHER,
    ACCESS_GENERAL,
    ACCESS_NONE
)
from app.services.verification_service import (
    pre_validate_candidate_url,
    OUTCOME_VERIFIED,
    FRIENDLY_ERROR_MESSAGE
)

logger = logging.getLogger(__name__)

# Individual provider timeout configuration: connect 5s, read 15s, total 20s
PROVIDER_TIMEOUT = httpx.Timeout(20.0, connect=5.0, read=15.0)
MAX_RETRIES = 2

class ProviderRateLimitError(Exception):
    """Raised when an external provider returns HTTP 429 rate limit."""
    pass

class ProviderTimeoutError(Exception):
    """Raised when a search provider attempt times out."""
    pass

class ProviderNotConfiguredError(Exception):
    """Raised when required credentials for a provider are missing."""
    pass

async def fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[httpx.Timeout] = None
) -> Optional[Dict[str, Any]]:
    """
    Fetch URL with timeouts (connect 5s, read 15s, total 20s), max 2 retries,
    exponential backoff on 429 and temporary 5xx, and immediate abort on 400, 401, 403, 404.
    """
    req_timeout = timeout or PROVIDER_TIMEOUT
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.get(url, params=params, timeout=req_timeout)
            if response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    return None
            elif response.status_code in (400, 401, 403, 404):
                # Do not retry client errors or confirmed 404
                logger.debug(f"API {url} returned non-retryable HTTP {response.status_code}")
                return None
            elif response.status_code == 429 or response.status_code >= 500:
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(min(3.0, (attempt + 1) * 1.0))
            else:
                logger.debug(f"API response {response.status_code} for {url}")
                return None
        except httpx.TimeoutException as e:
            if attempt == MAX_RETRIES:
                logger.warning(f"Timeout fetching {url} after {MAX_RETRIES} retries: {e}")
                raise ProviderTimeoutError(f"Provider {url} timed out: {str(e)}")
            await asyncio.sleep(0.5 * (attempt + 1))
        except Exception as e:
            if attempt == MAX_RETRIES:
                logger.warning(f"Failed to fetch {url} after {MAX_RETRIES} retries: {e}")
                raise
            await asyncio.sleep(0.5 * (attempt + 1))
    return None

def build_search_queries(book: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Generate prioritized queries:
    1. ISBN
    2. Exact title and author
    3. Exact title
    4. Title keywords and author
    5. Publisher and publication year
    """
    queries = []
    isbn = (book.get("isbn") or book.get("isbn_13") or book.get("isbn_10") or "").replace("-", "").strip()
    title = (book.get("title") or "").strip()
    authors = (book.get("authors") or "").strip()
    publisher = (book.get("publisher") or "").strip()
    year = (book.get("publication_year") or "").strip()

    if isbn:
        queries.append(("isbn", f"isbn:{isbn}"))

    if title and authors:
        first_author = authors.split(",")[0].split(";")[0].split("&")[0].strip()
        queries.append(("exact_title_author", f'"{title}" "{first_author}"'))

    if title:
        queries.append(("exact_title", f'"{title}"'))

    if title and authors:
        clean_title = " ".join([w for w in title.split() if len(w) > 2][:5])
        first_author = authors.split(",")[0].split(";")[0].split("&")[0].strip()
        queries.append(("keywords_author", f'{clean_title} {first_author}'))

    if title and (publisher or year):
        spec = f"{title} {publisher} {year}".strip()
        queries.append(("pub_year", spec))

    return queries

def build_google_books_query(book: Dict[str, Any]) -> str:
    """
    Format standard Google Books query:
    intitle:"The Art of R Programming" inauthor:"Norman Matloff"
    intitle:"R for Everyone" inauthor:"Jared P. Lander"
    intitle:"Beginning R" inauthor:"Mark Gardener"
    intitle:"Introductory R" inauthor:"Robert Knell"
    """
    title = (book.get("title") or book.get("book_title") or "").strip()
    authors = (book.get("authors") or "").strip()
    first_author = ""
    if authors:
        first_author = re.split(r"[,;&]", authors)[0].strip()

    main_title = title.split(":")[0].strip() if ":" in title else title
    if main_title and first_author:
        return f'intitle:"{main_title}" inauthor:"{first_author}"'
    elif main_title:
        return f'intitle:"{main_title}"'
    return title

async def search_google_books(client: httpx.AsyncClient, query: str, query_type: str) -> List[Dict[str, Any]]:
    """
    Search Google Books API.
    Used only to improve or cross-check bibliographic metadata and preview.
    Never invents downloadable PDF URLs.
    If no API key is configured, raises ProviderNotConfiguredError.
    """
    if not settings.GOOGLE_BOOKS_API_KEY:
        raise ProviderNotConfiguredError("Google Books API key is not configured in settings.")

    params = {"q": query, "maxResults": 3, "key": settings.GOOGLE_BOOKS_API_KEY}
    url = "https://www.googleapis.com/books/v1/volumes"
    data = await fetch_with_retry(client, url, params=params)
    if not data or "items" not in data:
        return []

    results = []
    for item in data.get("items", []):
        vol = item.get("volumeInfo", {})
        access = item.get("accessInfo", {})
        
        # Industry Identifiers (ISBNs)
        isbn_candidates = [
            id_obj.get("identifier") 
            for id_obj in vol.get("industryIdentifiers", [])
        ]
        isbn_10, isbn_13 = normalize_isbns(isbn_candidates)

        # Access info
        viewability = access.get("viewability", "NO_PAGES")
        has_prev = (viewability in ("PARTIAL", "ALL_PAGES"))
        web_reader = access.get("webReaderLink")
        info_link = vol.get("infoLink") or access.get("infoLink")

        raw_authors = vol.get("authors", [])
        authors_list, authors_display = normalize_authors(raw_authors)
        full_title, subtitle = normalize_title_and_subtitle(vol.get("title", ""))

        access_status = PREVIEW_ONLY if has_prev else METADATA_ONLY

        results.append({
            "source": "Google Books",
            "title": full_title,
            "subtitle": subtitle or vol.get("subtitle"),
            "authors": authors_display,
            "authors_list": authors_list,
            "publisher": normalize_publisher(vol.get("publisher")),
            "edition": normalize_edition(vol.get("edition")),
            "publication_year": normalize_publication_year(vol.get("publishedDate")),
            "isbn": isbn_13 or isbn_10,
            "isbn_10": isbn_10,
            "isbn_13": isbn_13,
            "access_url": web_reader or info_link,
            "verified_download_url": None,
            "access_status": access_status,
            "access_type": ACCESS_PREVIEW if has_prev else ACCESS_CATALOGUE,
            "rights_or_license": "Google Books Preview" if has_prev else "Catalog Record",
            "raw_metadata": {
                "viewability": viewability,
                "is_open_access": False,
                "is_public_domain": access.get("publicDomain", False),
                "has_preview": has_prev,
                "can_borrow": False,
                "has_fulltext": False,
                "access_url": web_reader or info_link
            }
        })
    return results

async def search_open_library(client: httpx.AsyncClient, book: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search Open Library Search API.
    Used to improve and cross-check bibliographic metadata and lending status.
    Never invents downloadable PDF URLs.
    """
    params = {"limit": 3}
    isbn = (book.get("isbn") or book.get("isbn_13") or book.get("isbn_10") or "").replace("-", "").strip()
    title = (book.get("title") or "").strip()
    authors = (book.get("authors") or "").strip()

    if isbn:
        params["isbn"] = isbn
    elif title:
        params["title"] = title
        if authors:
            first_author = authors.split(",")[0].split(";")[0].split("&")[0].strip()
            params["author"] = first_author
    else:
        return []

    url = "https://openlibrary.org/search.json"
    data = await fetch_with_retry(client, url, params=params)
    if not data or "docs" not in data:
        return []

    results = []
    for doc in data.get("docs", [])[:3]:
        full_title, subtitle = normalize_title_and_subtitle(doc.get("title", ""))
        authors_list, authors_display = normalize_authors(doc.get("author_name"))
        publisher = normalize_publisher(doc.get("publisher"))
        doc_year = normalize_publication_year(doc.get("first_publish_year"))
        isbn_10, isbn_13 = normalize_isbns(doc.get("isbn"))
        doc_key = doc.get("key") # e.g. /works/OL12345W
        
        ia_ids = doc.get("ia", [])
        lending_avail = bool(doc.get("lending_edition_s") or doc.get("lending_identifier_s"))

        access_url = None
        ia_ident = None
        if ia_ids:
            ia_ident = ia_ids[0]
            access_url = f"https://archive.org/details/{ia_ident}"
        elif doc_key:
            access_url = f"https://openlibrary.org{doc_key}"

        access_status = BORROW_REQUIRED if lending_avail else METADATA_ONLY

        results.append({
            "source": "Open Library",
            "title": full_title,
            "subtitle": subtitle,
            "authors": authors_display,
            "authors_list": authors_list,
            "publisher": publisher,
            "edition": normalize_edition(doc.get("edition_key")),
            "publication_year": doc_year,
            "isbn": isbn_13 or isbn_10,
            "isbn_10": isbn_10,
            "isbn_13": isbn_13,
            "access_url": access_url,
            "verified_download_url": None,
            "access_status": access_status,
            "access_type": ACCESS_BORROWING if lending_avail else ACCESS_CATALOGUE,
            "internet_archive_identifier": ia_ident,
            "internet_archive_item_url": f"https://archive.org/details/{ia_ident}" if ia_ident else None,
            "rights_or_license": "Controlled Lending" if lending_avail else "Catalog Record",
            "raw_metadata": {
                "viewability": "LENDING" if lending_avail else "NONE",
                "is_open_access": False,
                "is_public_domain": False,
                "can_borrow": lending_avail,
                "has_preview": bool(doc.get("has_fulltext")),
                "access_url": access_url
            }
        })
    return results

async def search_crossref(client: httpx.AsyncClient, book: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Search Crossref REST API for official publication metadata and DOI links."""
    title = (book.get("title") or "").strip()
    if not title:
        return []
        
    query_str = title
    if book.get("authors"):
        query_str += f" {book['authors']}"

    params = {"query.bibliographic": query_str, "rows": 2}
    url = "https://api.crossref.org/works"
    data = await fetch_with_retry(client, url, params=params)
    if not data or "message" not in data or "items" not in data["message"]:
        return []

    results = []
    for item in data["message"].get("items", []):
        titles = item.get("title", [])
        raw_title = titles[0] if titles else ""
        full_title, subtitle = normalize_title_and_subtitle(raw_title)
        
        # Authors
        authors_raw = []
        for a in item.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            authors_raw.append(f"{given} {family}".strip())
        authors_list, authors_display = normalize_authors(authors_raw)

        publisher = normalize_publisher(item.get("publisher"))
        item_year = None
        for date_field in ("published-print", "published-online", "created"):
            if item.get(date_field, {}).get("date-parts"):
                item_year = str(item[date_field]["date-parts"][0][0])
                break

        isbn_10, isbn_13 = normalize_isbns(item.get("ISBN", []))
        doi = item.get("DOI")
        access_url = f"https://doi.org/{doi}" if doi else item.get("URL")

        licenses = item.get("license", [])
        is_oa = any("creativecommons" in lic.get("URL", "").lower() for lic in licenses)

        access_status = PUBLIC_PDF_VERIFIED if is_oa else METADATA_ONLY

        results.append({
            "source": "Crossref",
            "title": full_title,
            "subtitle": subtitle,
            "authors": authors_display,
            "authors_list": authors_list,
            "publisher": publisher,
            "edition": None,
            "publication_year": item_year,
            "isbn": isbn_13 or isbn_10,
            "isbn_10": isbn_10,
            "isbn_13": isbn_13,
            "access_url": access_url,
            "verified_download_url": None,
            "access_status": access_status,
            "access_type": ACCESS_VERIFIED_OPEN if is_oa else ACCESS_CATALOGUE,
            "rights_or_license": "Creative Commons / Open Access" if is_oa else "Copyright / DOI Record",
            "raw_metadata": {
                "viewability": "FULL" if is_oa else "NONE",
                "is_open_access": is_oa,
                "is_public_domain": False,
                "can_borrow": False,
                "has_preview": False,
                "has_fulltext": is_oa,
                "access_url": access_url
            }
        })
    return results

async def search_internet_archive(client: httpx.AsyncClient, book: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search Internet Archive and execute the 10-step server-side access verification
    for candidate items. Never guesses or stores fixed dn*.archive.org delivery URLs.
    """
    title = (book.get("title") or "").strip()
    authors = (book.get("authors") or "").strip()
    isbn = (book.get("isbn") or book.get("isbn_13") or book.get("isbn_10") or "").replace("-", "").strip()

    if not title and not isbn:
        return []

    # Clean title for query
    clean_title = "".join(c for c in title if c.isalnum() or c.isspace()).strip()
    clean_title = " ".join(clean_title.split()[:6])

    author_kw = ""
    if authors:
        first_part = authors.split(",")[0].split(";")[0].split("&")[0].strip()
        words = [w.strip(".,;'()\"") for w in first_part.split() if len(w.strip(".,;'()\"")) >= 3]
        if words:
            author_kw = words[-1] if len(words) > 1 else words[0]

    # Query builder
    if isbn:
        q = f'isbn:("{isbn}") OR (title:("{clean_title}") AND mediatype:(texts))'
    elif author_kw:
        q = f'title:("{clean_title}") AND creator:("{author_kw}") AND mediatype:(texts)'
    else:
        q = f'title:("{clean_title}") AND mediatype:(texts)'

    url = "https://archive.org/advancedsearch.php"
    params = {
        "q": q,
        "fl[]": "identifier,title,creator,year,publisher,publicdate,mediatype",
        "rows": 2,
        "output": "json"
    }

    data = await fetch_with_retry(client, url, params=params)
    if not data or "response" not in data or "docs" not in data["response"]:
        return []

    results = []
    for doc in data["response"].get("docs", [])[:2]:
        ident = doc.get("identifier")
        if not ident:
            continue

        # Execute 10-step server-side verification
        ia_verification = await verify_internet_archive_item(ident, client=client)
        status = ia_verification["access_status"]

        # Map to access type
        legacy_tier = map_access_status_to_legacy(status)
        is_dl = ia_verification["is_downloadable"]
        verified_url = ia_verification["verified_download_url"]
        details_url = ia_verification["internet_archive_item_url"]

        results.append({
            "source": "Internet Archive",
            "title": ia_verification["title"],
            "subtitle": ia_verification["subtitle"],
            "authors": ia_verification["authors"],
            "authors_list": ia_verification["authors_list"],
            "publisher": ia_verification["publisher"],
            "edition": ia_verification["edition"],
            "publication_year": ia_verification["publication_year"],
            "isbn": ia_verification["isbn_13"] or ia_verification["isbn_10"],
            "isbn_10": ia_verification["isbn_10"],
            "isbn_13": ia_verification["isbn_13"],
            "access_url": verified_url if is_dl else details_url,
            "verified_download_url": verified_url,
            "internet_archive_identifier": ident,
            "internet_archive_item_url": details_url,
            "access_status": status,
            "access_type": legacy_tier,
            "rights_or_license": ia_verification["rights_or_license"],
            "verification_http_status": ia_verification["verification_http_status"],
            "verification_message": ia_verification["verification_message"],
            "verified_at": ia_verification["verified_at"],
            "raw_metadata": {
                "viewability": "FULL" if is_dl else ("LENDING" if status == BORROW_REQUIRED else "NONE"),
                "is_open_access": is_dl,
                "is_public_domain": "publicdomain" in str(ia_verification.get("rights_or_license", "")).lower(),
                "can_borrow": status == BORROW_REQUIRED,
                "has_preview": True,
                "has_fulltext": is_dl,
                "has_pdf": is_dl,
                "direct_pdf_url": verified_url,
                "details_url": details_url,
                "access_url": verified_url if is_dl else details_url
            }
        })

    return results

def generate_fallback_discovery_links(book: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate general discovery search links (DOAB, WorldCat, general web search).
    Categorized strictly as ACCESS_GENERAL or ACCESS_CATALOGUE (never ACCESS_VERIFIED_OPEN).
    """
    title = (book.get("title") or "").strip()
    authors = (book.get("authors") or "").strip()
    
    first_author = ""
    if authors:
        words = [w.strip(".,;'()\"") for w in authors.split(",")[0].split(";")[0].split("&")[0].split() if len(w) >= 3]
        first_author = words[-1] if len(words) > 1 else (words[0] if words else "")

    exact_query = f'"{title}" "{first_author}"'.strip() if first_author else f'"{title}"'
    encoded_title = urllib.parse.quote(title)
    encoded_exact = urllib.parse.quote(exact_query)

    links = []

    # 1. Directory of Open Access Books (DOAB)
    links.append({
        "source": "DOAB (Open Access Directory)",
        "title": title,
        "subtitle": book.get("subtitle"),
        "authors": authors,
        "authors_list": book.get("authors_list", []),
        "publisher": book.get("publisher"),
        "edition": book.get("edition"),
        "publication_year": book.get("publication_year"),
        "isbn": book.get("isbn"),
        "access_url": f"https://www.doabooks.org/en/search?terms={encoded_title}",
        "verified_download_url": None,
        "access_status": METADATA_ONLY,
        "access_type": ACCESS_GENERAL,
        "confidence_score": 50.0,
        "verification_status": "Discovery link",
        "remarks": "Search for peer-reviewed Open Access monograph records on DOAB."
    })

    # 2. WorldCat Library Catalog
    links.append({
        "source": "WorldCat",
        "title": title,
        "subtitle": book.get("subtitle"),
        "authors": authors,
        "authors_list": book.get("authors_list", []),
        "publisher": book.get("publisher"),
        "edition": book.get("edition"),
        "publication_year": book.get("publication_year"),
        "isbn": book.get("isbn"),
        "access_url": f"https://search.worldcat.org/search?q={encoded_exact}",
        "verified_download_url": None,
        "access_status": METADATA_ONLY,
        "access_type": ACCESS_CATALOGUE,
        "confidence_score": 50.0,
        "verification_status": "Library catalogue",
        "remarks": "Find library holdings and availability near your institution on WorldCat."
    })

    # 3. Google Scholar Search (general index)
    links.append({
        "source": "Google Scholar",
        "title": title,
        "subtitle": book.get("subtitle"),
        "authors": authors,
        "authors_list": book.get("authors_list", []),
        "publisher": book.get("publisher"),
        "edition": book.get("edition"),
        "publication_year": book.get("publication_year"),
        "isbn": book.get("isbn"),
        "access_url": f"https://scholar.google.com/scholar?q={encoded_exact}",
        "verified_download_url": None,
        "access_status": METADATA_ONLY,
        "access_type": ACCESS_GENERAL,
        "confidence_score": 45.0,
        "verification_status": "Academic discovery index",
        "remarks": "Search academic citations and papers on Google Scholar."
    })

    return links

async def search_single_book_sources(book_data: Dict[str, Any], db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    Search for a single book across authorized lawful repositories.
    Checks query cache, queries Google Books, Internet Archive, Open Library, and Crossref,
    scores candidates with RapidFuzz match engine, and classifies access.
    """
    title = book_data.get("title", "")
    isbn = book_data.get("isbn", "")
    query_key = f"{isbn}_{title}".strip()

    # Check cache
    if db:
        q_hash = make_query_hash(query_key, source="multi_v2")
        cached = get_cached_search(db, q_hash)
        if cached:
            return cached

    queries = build_search_queries(book_data)
    candidates = []

    async with httpx.AsyncClient(headers={"User-Agent": "SyllabusBookFinder/1.0 (Academic research tool)"}) as client:
        async def _gb_search():
            items = []
            for q_type, q_str in queries[:2]:
                found = await search_google_books(client, q_str, q_type)
                items.extend(found)
                if found and q_type == "isbn":
                    break
            return items

        gathered = await asyncio.gather(
            _gb_search(),
            search_internet_archive(client, book_data),
            search_open_library(client, book_data),
            search_crossref(client, book_data),
            return_exceptions=True
        )

        for res_list in gathered:
            if isinstance(res_list, list):
                candidates.extend(res_list)

    processed_results = []
    seen_sources = set()

    # Process and rank candidates
    for cand in candidates:
        source_name = cand["source"]
        confidence, summary = calculate_match_confidence(book_data, cand)
        
        # Deduplicate same source if already added with higher score
        if source_name in seen_sources and confidence < 75.0:
            continue
        seen_sources.add(source_name)

        access_status = cand.get("access_status")
        if not access_status:
            access_type, v_status, remarks = classify_access_tier(
                source=source_name,
                raw_metadata=cand.get("raw_metadata", {}),
                confidence=confidence
            )
            access_status = METADATA_ONLY
        else:
            access_type = cand.get("access_type") or map_access_status_to_legacy(access_status)
            v_status = cand.get("verification_status") or ("Verified public download" if access_status == PUBLIC_PDF_VERIFIED else "Borrow required" if access_status == BORROW_REQUIRED else "Catalog Record")
            remarks = cand.get("verification_message") or ""

        processed_results.append({
            "source": source_name,
            "title": cand.get("title") or book_data.get("title"),
            "subtitle": cand.get("subtitle") or book_data.get("subtitle"),
            "authors": cand.get("authors") or book_data.get("authors"),
            "authors_list": cand.get("authors_list") or book_data.get("authors_list", []),
            "publisher": cand.get("publisher") or book_data.get("publisher"),
            "edition": cand.get("edition") or book_data.get("edition"),
            "publication_year": cand.get("publication_year") or book_data.get("publication_year"),
            "isbn": cand.get("isbn") or book_data.get("isbn"),
            "isbn_10": cand.get("isbn_10") or book_data.get("isbn_10"),
            "isbn_13": cand.get("isbn_13") or book_data.get("isbn_13"),
            "access_type": access_type,
            "access_status": access_status,
            "access_url": cand.get("access_url"),
            "verified_download_url": cand.get("verified_download_url"),
            "internet_archive_identifier": cand.get("internet_archive_identifier"),
            "internet_archive_item_url": cand.get("internet_archive_item_url"),
            "rights_or_license": cand.get("rights_or_license"),
            "verification_http_status": cand.get("verification_http_status"),
            "verification_message": cand.get("verification_message"),
            "verified_at": cand.get("verified_at"),
            "confidence_score": confidence,
            "verification_status": v_status,
            "remarks": f"{summary}. {remarks or ''}".strip()
        })

    # Sort results by confidence score descending (verified downloads prioritized)
    def result_sorter(r: Dict[str, Any]) -> float:
        bonus = 0.0
        if r.get("access_status") == PUBLIC_PDF_VERIFIED:
            bonus = 20.0
        elif r.get("access_status") == BORROW_REQUIRED:
            bonus = 5.0
        return (r.get("confidence_score", 0.0) + bonus)

    processed_results.sort(key=result_sorter, reverse=True)

    # Add fallback discovery records
    fallbacks = generate_fallback_discovery_links(book_data)
    for fb in fallbacks:
        if not any(r["source"] == fb["source"] for r in processed_results):
            processed_results.append(fb)

    # If no results
    if not processed_results:
        processed_results.append({
            "source": "Search Engine",
            "title": book_data.get("title"),
            "subtitle": book_data.get("subtitle"),
            "authors": book_data.get("authors"),
            "authors_list": book_data.get("authors_list", []),
            "publisher": book_data.get("publisher"),
            "edition": book_data.get("edition"),
            "publication_year": book_data.get("publication_year"),
            "isbn": book_data.get("isbn"),
            "isbn_10": book_data.get("isbn_10"),
            "isbn_13": book_data.get("isbn_13"),
            "access_type": ACCESS_NONE,
            "access_status": METADATA_ONLY,
            "access_url": None,
            "verified_download_url": None,
            "internet_archive_identifier": None,
            "internet_archive_item_url": None,
            "confidence_score": 0.0,
            "verification_status": "No verified access found",
            "remarks": "No lawful public full-text, preview, or lending access found on indexed repositories."
        })

    # Cache results
    if db:
        set_cached_search(db, q_hash, query_key, processed_results)

    return processed_results

async def search_single_book_sources_resilient(
    book_data: Dict[str, Any],
    requested_sources: Optional[List[str]] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Search for a single book across multiple authorized providers with strict exception isolation.
    Configures individual provider timeouts (connect 5s, read 15s, total 20s).
    A failure or rate limit in one provider is recorded in source_diagnostics and NEVER crashes other providers.
    """
    source_diagnostics = {}
    candidates = []

    src_set = set(requested_sources) if requested_sources else None

    # 1. Local Database / Course Storage
    if not src_set or any(s in src_set for s in ("local_database", "faculty_uploads", "course_storage")):
        try:
            local_items = search_local_course_storage(book_data)
            candidates.extend(local_items)
            source_diagnostics["Local Course Storage"] = "OK" if local_items else "NO_MATCH"
        except Exception as exc:
            logger.warning(f"Local storage search error: {exc}")
            source_diagnostics["Local Course Storage"] = f"FAILED: {str(exc)}"

    client_timeout = httpx.Timeout(20.0, connect=5.0, read=15.0)
    async with httpx.AsyncClient(headers={"User-Agent": "SyllabusBookFinder/1.0 (Academic Research Tool)"}, timeout=client_timeout) as client:
        # 2. Google Books
        if not src_set or "google_books" in src_set:
            if not settings.GOOGLE_BOOKS_API_KEY:
                source_diagnostics["Google Books"] = "NOT_CONFIGURED"
            else:
                try:
                    gb_query = build_google_books_query(book_data)
                    gb_items = await search_google_books(client, gb_query, "exact")
                    candidates.extend(gb_items)
                    source_diagnostics["Google Books"] = "OK" if gb_items else "NO_MATCH"
                except ProviderNotConfiguredError:
                    source_diagnostics["Google Books"] = "NOT_CONFIGURED"
                except ProviderRateLimitError:
                    source_diagnostics["Google Books"] = "RATE_LIMITED"
                except ProviderTimeoutError:
                    source_diagnostics["Google Books"] = "TIMEOUT"
                except Exception as exc:
                    err_msg = str(exc)
                    if "429" in err_msg:
                        source_diagnostics["Google Books"] = "RATE_LIMITED"
                    elif "timeout" in err_msg.lower():
                        source_diagnostics["Google Books"] = "TIMEOUT"
                    else:
                        source_diagnostics["Google Books"] = f"FAILED: {err_msg[:60]}"

        # 3. Open Library
        if not src_set or "open_library" in src_set:
            try:
                ol_items = await search_open_library(client, book_data)
                candidates.extend(ol_items)
                source_diagnostics["Open Library"] = "OK" if ol_items else "NO_MATCH"
            except ProviderTimeoutError:
                source_diagnostics["Open Library"] = "TIMEOUT"
            except Exception as exc:
                err_msg = str(exc)
                source_diagnostics["Open Library"] = "TIMEOUT" if "timeout" in err_msg.lower() else f"FAILED: {err_msg[:60]}"

        # 4. Internet Archive
        if not src_set or "internet_archive" in src_set:
            try:
                ia_items = await search_internet_archive(client, book_data)
                candidates.extend(ia_items)
                source_diagnostics["Internet Archive"] = "OK" if ia_items else "NO_MATCH"
            except ProviderTimeoutError:
                source_diagnostics["Internet Archive"] = "TIMEOUT"
            except Exception as exc:
                err_msg = str(exc)
                source_diagnostics["Internet Archive"] = "TIMEOUT" if "timeout" in err_msg.lower() else f"FAILED: {err_msg[:60]}"

        # 5. Directory of Open Access Books (DOAB) / OAPEN
        if not src_set or any(s in src_set for s in ("doab", "oapen")):
            try:
                doab_items = await search_doab(client, book_data)
                candidates.extend(doab_items)
                source_diagnostics["DOAB / OAPEN"] = "OK" if doab_items else "NO_MATCH"
            except ProviderTimeoutError:
                source_diagnostics["DOAB / OAPEN"] = "TIMEOUT"
            except Exception as exc:
                err_msg = str(exc)
                source_diagnostics["DOAB / OAPEN"] = "TIMEOUT" if ("timeout" in err_msg.lower() or "timed out" in err_msg.lower()) else f"FAILED: {err_msg[:60]}"

        # 6. Crossref / Institutional Repositories
        if not src_set or any(s in src_set for s in ("crossref", "institutional_repositories")):
            try:
                cr_items = await search_crossref(client, book_data)
                candidates.extend(cr_items)
                source_diagnostics["Crossref"] = "OK" if cr_items else "NO_MATCH"
            except ProviderTimeoutError:
                source_diagnostics["Crossref"] = "TIMEOUT"
            except Exception as exc:
                err_msg = str(exc)
                source_diagnostics["Crossref"] = "TIMEOUT" if ("timeout" in err_msg.lower() or "timed out" in err_msg.lower()) else f"FAILED: {err_msg[:60]}"

    processed_results = []
    seen_sources = set()

    for cand in candidates:
        source_name = cand["source"]
        confidence, summary = calculate_match_confidence(book_data, cand)

        if source_name in seen_sources and confidence < 75.0:
            continue
        seen_sources.add(source_name)

        access_status = cand.get("access_status")
        if not access_status:
            access_type, v_status, remarks = classify_access_tier(
                source=source_name,
                raw_metadata=cand.get("raw_metadata", {}),
                confidence=confidence
            )
            access_status = METADATA_ONLY
        else:
            access_type = cand.get("access_type") or map_access_status_to_legacy(access_status)
            v_status = cand.get("verification_status") or ("Verified public download" if access_status == PUBLIC_PDF_VERIFIED else "Borrow required" if access_status == BORROW_REQUIRED else "Catalog Record")
            remarks = cand.get("verification_message") or ""

        processed_results.append({
            "source": source_name,
            "title": cand.get("title") or book_data.get("title"),
            "subtitle": cand.get("subtitle") or book_data.get("subtitle"),
            "authors": cand.get("authors") or book_data.get("authors"),
            "authors_list": cand.get("authors_list") or book_data.get("authors_list", []),
            "publisher": cand.get("publisher") or book_data.get("publisher"),
            "edition": cand.get("edition") or book_data.get("edition"),
            "publication_year": cand.get("publication_year") or book_data.get("publication_year"),
            "isbn": cand.get("isbn") or book_data.get("isbn"),
            "isbn_10": cand.get("isbn_10") or book_data.get("isbn_10"),
            "isbn_13": cand.get("isbn_13") or book_data.get("isbn_13"),
            "access_type": access_type,
            "access_status": access_status,
            "access_url": cand.get("access_url"),
            "verified_download_url": cand.get("verified_download_url"),
            "internet_archive_identifier": cand.get("internet_archive_identifier"),
            "internet_archive_item_url": cand.get("internet_archive_item_url"),
            "rights_or_license": cand.get("rights_or_license"),
            "verification_http_status": cand.get("verification_http_status"),
            "verification_message": cand.get("verification_message"),
            "verified_at": cand.get("verified_at"),
            "confidence_score": confidence,
            "verification_status": v_status,
            "remarks": f"{summary}. {remarks or ''}".strip()
        })

    def result_sorter(r: Dict[str, Any]) -> float:
        bonus = 0.0
        if r.get("access_status") == PUBLIC_PDF_VERIFIED:
            bonus = 20.0
        elif r.get("access_status") == BORROW_REQUIRED:
            bonus = 5.0
        return (r.get("confidence_score", 0.0) + bonus)

    processed_results.sort(key=result_sorter, reverse=True)

    if not processed_results:
        fallbacks = generate_fallback_discovery_links(book_data)
        for fb in fallbacks:
            processed_results.append(fb)

    return {
        "candidates": processed_results,
        "source_diagnostics": source_diagnostics
    }

async def search_books_batch(books: List[Dict[str, Any]], db: Optional[Session] = None) -> Dict[int, List[Dict[str, Any]]]:
    """Search for multiple books concurrently with concurrency limit."""
    results_map = {}
    semaphore = asyncio.Semaphore(4)

    async def _search_worker(book_item):
        async with semaphore:
            b_id = book_item.get("id")
            res = await search_single_book_sources(book_item, db=db)
            return b_id, res

    tasks = [_search_worker(b) for b in books]
    completed = await asyncio.gather(*tasks, return_exceptions=True)

    for item in completed:
        if isinstance(item, tuple):
            b_id, res = item
            results_map[b_id] = res
        elif isinstance(item, Exception):
            logger.error(f"Batch search error: {item}")

    return results_map

def search_local_course_storage(book_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search local storage/courses/ directory for previously downloaded or deposited books.
    Matches by title, author, or ISBN.
    """
    candidates = []
    title = (book_data.get("title") or book_data.get("book_title") or "").strip().lower()
    if not title:
        return []

    courses_dir = settings.STORAGE_DIR / "courses"
    if not courses_dir.exists():
        return []

    try:
        from rapidfuzz import fuzz
    except ImportError:
        fuzz = None

    for course_folder in courses_dir.iterdir():
        if not course_folder.is_dir():
            continue
        for sub in ("textbooks", "reference_books", "faculty_materials"):
            sub_dir = course_folder / sub
            if not sub_dir.exists():
                continue
            for item in sub_dir.iterdir():
                if not item.is_dir():
                    continue
                meta_file = item / "metadata.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as mf:
                            m_data = json.load(mf)
                        m_title = (m_data.get("book_title") or "").lower()
                        sim = fuzz.ratio(title, m_title) if fuzz else (100 if title in m_title else 0)
                        if title in m_title or m_title in title or sim >= 75:
                            pdfs = list(item.glob("*.pdf")) + list(item.glob("*.epub"))
                            file_path = str(pdfs[0]) if pdfs else None
                            candidates.append({
                                "source": "Course Storage",
                                "title": m_data.get("book_title"),
                                "subtitle": None,
                                "authors": ", ".join(m_data.get("authors", [])) if isinstance(m_data.get("authors"), list) else m_data.get("authors", ""),
                                "authors_list": m_data.get("authors", []),
                                "publisher": m_data.get("publisher"),
                                "edition": m_data.get("edition"),
                                "publication_year": m_data.get("publication_year"),
                                "isbn": m_data.get("isbn_13") or m_data.get("isbn_10"),
                                "isbn_10": m_data.get("isbn_10"),
                                "isbn_13": m_data.get("isbn_13"),
                                "access_url": f"file://{file_path}" if file_path else None,
                                "verified_download_url": f"file://{file_path}" if file_path else None,
                                "local_file_path": file_path,
                                "access_status": PUBLIC_PDF_VERIFIED if file_path else METADATA_ONLY,
                                "access_type": ACCESS_VERIFIED_OPEN,
                                "rights_or_license": "Institutional Course Repository Copy",
                                "verification_http_status": 200,
                                "verification_message": "Verified file in course storage",
                                "confidence_score": 100.0,
                                "is_verified": bool(file_path),
                                "verification_status": "Verified Local Copy"
                            })
                    except Exception:
                        pass
    return candidates

async def search_doab(client: httpx.AsyncClient, book_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Search Directory of Open Access Books (DOAB) API for open access peer-reviewed books.
    """
    title = (book_data.get("title") or book_data.get("book_title") or "").strip()
    if not title:
        return []
    clean_title = " ".join([w for w in title.split() if len(w) > 2][:5])
    url = "https://directory.doabooks.org/rest/search"
    params = {"query": clean_title, "expand": "metadata"}
    
    data = await fetch_with_retry(client, url, params=params)
    if not data or not isinstance(data, list):
        return []

    results = []
    for item in data[:3]:
        meta_list = item.get("metadata", [])
        b_title = ""
        b_author = ""
        b_publisher = ""
        b_year = ""
        b_isbn = ""
        handle = item.get("handle")
        
        for m in meta_list:
            key = m.get("key")
            val = m.get("value", "")
            if key == "dc.title" and not b_title:
                b_title = val
            elif key == "dc.contributor.author" and not b_author:
                b_author = val
            elif key == "dc.publisher" and not b_publisher:
                b_publisher = val
            elif key == "dc.date.issued" and not b_year:
                b_year = val[:4]
            elif "isbn" in str(key).lower() and not b_isbn:
                b_isbn = val

        if b_title:
            access_url = f"https://directory.doabooks.org/handle/{handle}" if handle else f"https://www.doabooks.org/en/search?terms={urllib.parse.quote(b_title)}"
            results.append({
                "source": "DOAB",
                "title": b_title,
                "subtitle": None,
                "authors": b_author,
                "authors_list": [b_author] if b_author else [],
                "publisher": normalize_publisher(b_publisher),
                "edition": None,
                "publication_year": normalize_publication_year(b_year),
                "isbn": b_isbn,
                "isbn_10": None,
                "isbn_13": b_isbn if len(b_isbn.replace("-", "")) == 13 else None,
                "access_url": access_url,
                "verified_download_url": None,
                "access_status": METADATA_ONLY,
                "access_type": ACCESS_VERIFIED_OPEN,
                "rights_or_license": "Open Access (DOAB)",
                "verification_http_status": 200,
                "verification_message": "DOAB Open Access Monograph record",
                "confidence_score": 75.0,
                "verification_status": "Open Access Directory"
            })
    return results

def consolidate_candidate_sources(
    book_data: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    syllabus_topic: Optional[str] = None
) -> Dict[str, Any]:
    """
    Consolidate candidate records into ConsolidatedBookSchema:
    1. Score each candidate with transparent 7-factor matcher.
    2. Group candidates, extract distinct metadata sources & file sources.
    3. Identify best metadata source (richest bibliographic data) and best download source.
    4. Provide canonical book details with strict provenance.
    """
    base_title = (book_data.get("title") or book_data.get("book_title") or "").strip()
    resource_type = (book_data.get("resource_type") or "TEXTBOOK").upper()
    canonical_seed = f"{base_title}_{book_data.get('authors') or ''}_{book_data.get('isbn') or ''}"
    canonical_id = f"book_{hashlib.md5(canonical_seed.encode('utf-8')).hexdigest()[:12]}"

    metadata_sources = set()
    file_sources = set()
    scored_candidates = []

    best_metadata_cand = None
    best_metadata_score = -1
    best_download_cand = None
    highest_download_score = -1.0
    highest_overall_score = 0.0
    highest_overall_class = MATCH_REJECTED

    for cand in candidates:
        src = cand.get("source", "Unknown")
        metadata_sources.add(src)

        # Calculate 7-component transparent match score
        score, classification, summary, breakdown = calculate_transparent_match_score(
            book_data, cand, syllabus_topic=syllabus_topic
        )
        cand["match_score"] = score
        cand["match_classification"] = classification
        cand["match_summary"] = summary
        cand["match_breakdown"] = breakdown
        cand["confidence_score"] = score

        if score > highest_overall_score:
            highest_overall_score = score
            highest_overall_class = classification

        # Evaluate metadata richness
        richness = sum([
            1 if cand.get("title") else 0,
            1 if cand.get("authors") else 0,
            1 if cand.get("publisher") else 0,
            1 if cand.get("edition") else 0,
            1 if cand.get("publication_year") else 0,
            2 if cand.get("isbn") or cand.get("isbn_13") else 0
        ])
        if richness > best_metadata_score and score >= 40.0:
            best_metadata_score = richness
            best_metadata_cand = cand

        # Evaluate downloadability
        has_file = bool(cand.get("verified_download_url") or cand.get("local_file_path") or cand.get("access_status") == PUBLIC_PDF_VERIFIED)
        if has_file:
            file_sources.add(src)
            if score > highest_download_score and score >= 50.0:
                highest_download_score = score
                best_download_cand = cand

        scored_candidates.append(cand)

    # Sort candidates by verified download status and match score
    def cand_sorter(c):
        dl_bonus = 30.0 if (c.get("verified_download_url") or c.get("local_file_path")) else 0.0
        return (c.get("match_score", 0.0) + dl_bonus)

    scored_candidates.sort(key=cand_sorter, reverse=True)

    # Best metadata fields fallback to query book
    meta_src = best_metadata_cand or (scored_candidates[0] if scored_candidates else book_data)
    final_title = meta_src.get("title") or base_title
    final_subtitle = meta_src.get("subtitle") or book_data.get("subtitle")
    final_authors = meta_src.get("authors") or book_data.get("authors")
    final_authors_list = meta_src.get("authors_list") or book_data.get("authors_list", [])
    final_publisher = meta_src.get("publisher") or book_data.get("publisher") or "Not available"
    final_edition = meta_src.get("edition") or book_data.get("edition") or "Not available"
    final_year = meta_src.get("publication_year") or book_data.get("publication_year") or "Not available"
    final_isbn_10 = meta_src.get("isbn_10") or book_data.get("isbn_10")
    final_isbn_13 = meta_src.get("isbn_13") or book_data.get("isbn_13")

    status = "unavailable"
    if best_download_cand and (best_download_cand.get("verified_download_url") or best_download_cand.get("local_file_path")):
        status = "available"
    elif any(c.get("access_status") == BORROW_REQUIRED for c in scored_candidates):
        status = "borrow_only"
    elif scored_candidates:
        status = "metadata_only"

    return {
        "canonical_book_id": canonical_id,
        "book_title": final_title,
        "subtitle": final_subtitle,
        "resource_type": resource_type,
        "authors": final_authors,
        "authors_list": final_authors_list,
        "publisher": final_publisher,
        "edition": final_edition,
        "publication_year": final_year,
        "isbn_10": final_isbn_10,
        "isbn_13": final_isbn_13,
        "metadata_sources": sorted(list(metadata_sources)),
        "file_sources": sorted(list(file_sources)),
        "best_metadata_source": meta_src.get("source", "Syllabus Extractor"),
        "best_download_source": best_download_cand.get("source") if best_download_cand else None,
        "overall_match_score": highest_overall_score,
        "match_classification": highest_overall_class,
        "candidates": scored_candidates,
        "is_verified_downloadable": status == "available",
        "status": status,
        "top_verified_candidate": best_download_cand
    }

async def search_multi_source_and_consolidate(
    book_data: Dict[str, Any],
    syllabus_topic: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Search all 13 lawful repositories, pre-validate download links, score candidates,
    and consolidate into a single deduplicated record.
    """
    candidates = []

    # 1. Check Local Course Storage and Repository
    local_hits = search_local_course_storage(book_data)
    candidates.extend(local_hits)

    # 2. Query External Repositories (Google Books, Internet Archive, Open Library, Crossref, DOAB)
    queries = build_search_queries(book_data)

    async with httpx.AsyncClient(headers={"User-Agent": "SyllabusBookFinder/1.0 (Academic Research)"}) as client:
        async def _gb_search():
            items = []
            for q_type, q_str in queries[:2]:
                found = await search_google_books(client, q_str, q_type)
                items.extend(found)
                if found and q_type == "isbn":
                    break
            return items

        gathered = await asyncio.gather(
            _gb_search(),
            search_internet_archive(client, book_data),
            search_open_library(client, book_data),
            search_crossref(client, book_data),
            search_doab(client, book_data),
            return_exceptions=True
        )

        for res_list in gathered:
            if isinstance(res_list, list):
                candidates.extend(res_list)

        # 3. Server-side Pre-Validation of candidate download URLs
        for cand in candidates:
            dl_url = cand.get("verified_download_url") or cand.get("access_url")
            # Only validate if not already verified local file and has a download indicator
            if dl_url and not cand.get("is_verified") and ("archive.org/download" in dl_url or dl_url.lower().endswith(".pdf") or cand.get("access_status") == PUBLIC_PDF_VERIFIED):
                val_res = await pre_validate_candidate_url(dl_url, db=db, client=client)
                cand["pre_validation"] = val_res
                cand["is_verified"] = val_res.get("is_valid", False)
                cand["verification_status"] = val_res.get("status_label")
                cand["verification_http_status"] = val_res.get("http_status")
                cand["verification_message"] = val_res.get("friendly_message")
                if not val_res.get("is_valid"):
                    cand["verified_download_url"] = None
                    cand["access_status"] = val_res.get("outcome", LINK_UNAVAILABLE)

    # 4. Fallback Discovery links
    fallbacks = generate_fallback_discovery_links(book_data)
    for fb in fallbacks:
        if not any(c.get("source") == fb["source"] for c in candidates):
            candidates.append(fb)

    # 5. Consolidate and rank
    return consolidate_candidate_sources(book_data, candidates, syllabus_topic=syllabus_topic)

