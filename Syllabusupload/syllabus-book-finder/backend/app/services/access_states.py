"""
Access state definitions and mappings according to the lawful access specification.

States:
- PUBLIC_PDF_VERIFIED: Server-side verified public download (HTTP 200/206 with %PDF- header).
- PUBLIC_EPUB_VERIFIED: Server-side verified public EPUB download.
- BORROW_REQUIRED: Item requires digital borrowing / lending (HTTP 401/403 or lending collection).
- PREVIEW_ONLY: Only sample/preview pages accessible.
- METADATA_ONLY: Bibliographic catalog record only.
- LINK_UNAVAILABLE: Resource not found / 404.
- VERIFICATION_FAILED: Download endpoint returned HTML, bad format, or timed out.
"""

PUBLIC_PDF_VERIFIED = "PUBLIC_PDF_VERIFIED"
PUBLIC_EPUB_VERIFIED = "PUBLIC_EPUB_VERIFIED"
BORROW_REQUIRED = "BORROW_REQUIRED"
PREVIEW_ONLY = "PREVIEW_ONLY"
METADATA_ONLY = "METADATA_ONLY"
LINK_UNAVAILABLE = "LINK_UNAVAILABLE"
VERIFICATION_FAILED = "VERIFICATION_FAILED"

ALL_ACCESS_STATES = [
    PUBLIC_PDF_VERIFIED,
    PUBLIC_EPUB_VERIFIED,
    BORROW_REQUIRED,
    PREVIEW_ONLY,
    METADATA_ONLY,
    LINK_UNAVAILABLE,
    VERIFICATION_FAILED
]

ACCESS_STATE_TO_LEGACY_TIER = {
    PUBLIC_PDF_VERIFIED: "Verified open-access full text",
    PUBLIC_EPUB_VERIFIED: "Verified open-access full text",
    BORROW_REQUIRED: "Borrowing available",
    PREVIEW_ONLY: "Preview available",
    METADATA_ONLY: "Catalogue record",
    LINK_UNAVAILABLE: "No verified access found",
    VERIFICATION_FAILED: "No verified access found"
}

def map_access_status_to_legacy(access_status: str) -> str:
    return ACCESS_STATE_TO_LEGACY_TIER.get(access_status, "No verified access found")
