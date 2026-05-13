"""
Resume Parser & Evaluator
=========================
Stack  : PyMuPDF (text extraction) + pdfplumber (fallback)
         Groq Cloud API – llama-3.3-70b-versatile  (free tier, no credit card needed)
         Pure-Python regex pre-pass for deterministic fields
         requests + BeautifulSoup4 for Behance portfolio scraping
Output : Structured JSON + ranked summary table

Usage
-----
  Single file       : python resume_parser.py --input resume.pdf
  Folder            : python resume_parser.py --input ./resumes/
  Disable LLM       : python resume_parser.py --input ./resumes/ --no-llm
  API key           : set env var GROQ_API_KEY=gsk_...
                      OR pass --api-key gsk_...
"""

from __future__ import annotations

import argparse
from datetime import date
from io import BytesIO
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

# ── third-party ────────────────────────────────────────────────────────────
try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_SCRAPER = True
except ImportError:
    HAS_SCRAPER = False

# ── logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger("ResumeParser")

_TODAY = date.today()
_CURRENT_YEAR = _TODAY.year
_CURRENT_MONTH = _TODAY.month


def _ensure_pdf_extractors_available() -> None:
    """Fail lazily so the module can still be imported for testing."""
    if not HAS_FITZ and not HAS_PDFPLUMBER:
        raise RuntimeError("install at least one of: pymupdf  pdfplumber")

# ══════════════════════════════════════════════════════════════════════════
# 1.  PDF TEXT EXTRACTION
# ══════════════════════════════════════════════════════════════════════════

def extract_text_pymupdf(path: str) -> str:
    """Extract text page-by-page with PyMuPDF."""
    doc = fitz.open(path)
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return "\n".join(pages)


def extract_text_pdfplumber(path: str) -> str:
    """Extract text with pdfplumber (better for multi-column layouts)."""
    with pdfplumber.open(path) as pdf:
        return "\n".join(
            page.extract_text() or "" for page in pdf.pages
        )


def get_ocr_status() -> dict[str, Any]:
    """Return OCR runtime availability details for API health checks."""
    status: dict[str, Any] = {
        "python_package": False,
        "tesseract_binary": False,
        "render_backend": "pymupdf" if HAS_FITZ else None,
        "binary_path": None,
        "available": False,
        "detail": None,
    }

    if not HAS_FITZ:
        status["detail"] = "OCR fallback currently requires PyMuPDF for page rendering."
        return status

    try:
        import pytesseract
    except ImportError:
        status["detail"] = "Install pytesseract to enable OCR."
        return status

    status["python_package"] = True

    tesseract_cmd = os.environ.get("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        status["binary_path"] = tesseract_cmd
    else:
        status["binary_path"] = shutil.which("tesseract")

    try:
        pytesseract.get_tesseract_version()
        status["tesseract_binary"] = True
    except Exception as exc:
        status["detail"] = (
            "Tesseract binary not found. Install Tesseract OCR and, if needed, "
            "set TESSERACT_CMD to the executable path."
        )
        return status

    status["available"] = True
    return status


def _looks_like_low_quality_text(text: str) -> bool:
    """
    Detect low-signal extracted text that should trigger OCR fallback.

    Scanned resumes often produce tiny, fragmented, or mostly-symbol text rather
    than a completely empty string, so relying only on blank checks misses them.
    """
    stripped = text.strip()
    if not stripped:
        return True

    words = re.findall(r"\b[\w@.+\-]+\b", stripped, flags=re.UNICODE)
    alpha_chars = sum(ch.isalpha() for ch in stripped)
    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    sample = lines[: min(12, len(lines))]
    noisy_lines = 0
    for line in sample:
        meaningful_chars = sum(ch.isalpha() for ch in line)
        if meaningful_chars <= 2 or len(re.findall(r"\b\w\b", line)) >= 5:
            noisy_lines += 1

    if len(stripped) < 120 or len(words) < 25 or alpha_chars < 80:
        return True
    if sample and noisy_lines / len(sample) >= 0.5:
        return True
    return False


def _extract_text_ocr(path: str) -> str:
    """
    OCR fallback for image-based / scanned PDFs.

    Uses PyMuPDF to render pages to images and pytesseract to read them. This
    keeps the runtime lighter than pdf2image/poppler and fits the API flow.
    """
    ocr_status = get_ocr_status()
    if not ocr_status["available"]:
        log.warning("OCR unavailable: %s", ocr_status["detail"])
        return ""

    try:
        from PIL import Image
        import pytesseract

        doc = fitz.open(path)
        pages = []
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            image = Image.open(BytesIO(pix.tobytes("png")))
            image.load()
            pages.append(pytesseract.image_to_string(image, lang="eng"))
        doc.close()
        return "\n".join(pages)
    except Exception as exc:
        log.warning("OCR failed for %s: %s", path, exc)
        return ""


def extract_text(path: str) -> str:
    """
    Try PyMuPDF → pdfplumber → OCR (for scanned PDFs).
    Raises ValueError only if all three methods yield no text.
    """
    _ensure_pdf_extractors_available()
    text = ""

    if HAS_FITZ:
        try:
            text = extract_text_pymupdf(path)
        except Exception as exc:
            log.warning("PyMuPDF failed (%s), trying pdfplumber …", exc)

    if not text.strip() and HAS_PDFPLUMBER:
        try:
            text = extract_text_pdfplumber(path)
        except Exception as exc:
            log.warning("pdfplumber failed (%s), trying OCR …", exc)

    should_try_ocr = not text.strip() or _looks_like_low_quality_text(text)
    if should_try_ocr:
        if text.strip():
            log.warning("Low-quality text extracted — attempting OCR for: %s", path)
        else:
            log.warning("No text extracted via standard methods — attempting OCR for: %s", path)
        ocr_text = _extract_text_ocr(path)
        if ocr_text.strip() and len(ocr_text.strip()) >= len(text.strip()):
            text = ocr_text

    if not text.strip():
        ocr_status = get_ocr_status()
        if not ocr_status["available"]:
            raise ValueError(
                f"Could not extract text from: {path}. OCR is unavailable: "
                f"{ocr_status['detail']}"
            )
        raise ValueError(f"Could not extract text from: {path}")

    return text


# ══════════════════════════════════════════════════════════════════════════
# 2.  REGEX PRE-PASS  (deterministic, runs before LLM)
# ══════════════════════════════════════════════════════════════════════════

# ── patterns ──────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I
)
_PHONE_RE = re.compile(
    r"(?:\+?\d[\d\s\-().]{7,}\d)"
)
# Pre-compiled pattern to reject date ranges misidentified as phones
# e.g. "2022 - 2025", "2019-2022", "2025-09 - 2026-01"
_DATE_RANGE_LOOKALIKE = re.compile(
    r"^\s*(?:19|20)\d{2}\s*[-–]\s*(?:(?:19|20)\d{2}|0[1-9]|1[0-2]|\d{1,2}[-–]\d{4})\s*$"
)
_LINKEDIN_RE = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+/?", re.I
)
_BEHANCE_RE = re.compile(
    r"(?:https?://)?(?:www\.)?behance\.net/[\w\-]+/?", re.I
)
_YEAR_RE = re.compile(r"\b(19[89]\d|20[0-3]\d)\b")

# date-range: "Jan 2019 – Mar 2022"  or  "2015 – Present"  or  "2018-2020"
_DATE_RANGE_RE = re.compile(
    r"(?:"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s*)?"
    r"(19[89]\d|20[0-3]\d)"
    r"\s*[-–—to]+\s*"
    r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?"
    r"|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\s*)?"
    r"(20[0-3]\d|19[89]\d|[Pp]resent|[Cc]urrent|[Nn]ow)",
    re.I,
)


def _clean_text(raw: str) -> str:
    """
    Production-safe text cleaning.

    Preserves:
      - Unicode letters (accented, Arabic, Urdu, CJK, etc.)  [constraint 7]
      - International names and scripts

    Removes only:
      - Control characters and unreadable binary artifacts
      - Excessive whitespace
      - Repeated OCR noise patterns                          [constraint 6]
    """
    text = raw

    # ── line ending normalisation ──────────────────────────────────────────
    text = re.sub(r"\r\n|\r", "\n", text)

    # ── strip true control characters ONLY (not printable Unicode) ─────────
    # \x00-\x08 \x0b \x0c \x0e-\x1f \x7f  — keep \t(\x09) \n(\x0a)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)

    # ── strip unreadable binary artifacts (replacement char, private use) ──
    text = re.sub(r"[\ufffd\ue000-\uf8ff]", " ", text)

    # ── collapse horizontal whitespace (tabs → space, multi-space → one) ───
    text = re.sub(r"[ \t]{2,}", " ", text)

    # ── OCR noise: lines that are pure punctuation / symbols (no letters) ──
    # e.g. "--------", "• • • •", "|||||||"                 [constraint 6]
    text = re.sub(r"(?m)^[^\w\u0600-\u06ff\u0080-\u024f\n]{3,}$", "", text)

    # ── repeated word/phrase spam (keyword stuffing) ───────────────────────
    # e.g. "python python python python" → "python"          [constraint 6]
    text = re.sub(r"\b(\w+)(?:\s+\1){3,}\b", r"\1", text, flags=re.I)

    # ── collapse blank lines ───────────────────────────────────────────────
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


_MONTH_LOOKUP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_DATE_CONNECTOR_RE = r"(?:-|–|—|\bto\b|\bthrough\b|\btill\b)"
_DATE_SPAN_RE = re.compile(
    rf"(?P<start_month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    rf"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    rf"Nov(?:ember)?|Dec(?:ember)?)?\s*"
    rf"(?P<start_year>(?:19|20)\d{{2}})"
    rf"\s*{_DATE_CONNECTOR_RE}\s*"
    rf"(?:(?P<end_month>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
    rf"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    rf"Nov(?:ember)?|Dec(?:ember)?)\s*)?"
    rf"(?:(?P<end_year>(?:19|20)\d{{2}})|(?P<end_current>present|current|now))",
    re.I,
)
_SECTION_HEADER_PATTERNS: dict[str, re.Pattern[str]] = {
    "experience": re.compile(
        r"^(experience|exp|work experience|professional experience|employment|"
        r"work history|career history|internships?)[:\s]*$",
        re.I,
    ),
    "education": re.compile(
        r"^(education|academic background|academics|qualifications|degrees?|"
        r"certifications?)[:\s]*$",
        re.I,
    ),
    "skills": re.compile(
        r"^(skills|technical skills|core skills|toolkit|tools|technologies)[:\s]*$",
        re.I,
    ),
    "projects": re.compile(
        r"^(projects|project experience|portfolio)[:\s]*$",
        re.I,
    ),
}
_PERSON_NAME_TOKEN_RE = re.compile(r"^[^\W\d_][^\W\d_'.-]*$", re.UNICODE)
_NAME_REJECT_RE = re.compile(
    r"\b("
    r"resume|curriculum|vitae|portfolio|linkedin|github|behance|email|phone|"
    r"profile|summary|objective|about|personal|details|information|contact|"
    r"address|street|road|city|country|engineer|developer|designer|manager|"
    r"analyst|architect|consultant|specialist|director|lead|intern|student|"
    r"university|college|school|institute|academy|inc|llc|ltd|corp|corporation|"
    r"technologies|solutions|company"
    r")\b",
    re.I,
)
_EDUCATION_RE = re.compile(
    r"\b(education|university|college|school|degree|bachelor|master|phd|"
    r"b\.sc|m\.sc|gpa|cgpa|coursework|dean'?s list)\b",
    re.I,
)
_ROLE_HINT_RE = re.compile(
    r"\b(engineer|developer|designer|manager|analyst|architect|consultant|"
    r"specialist|director|lead|intern|researcher|marketing|product|software|"
    r"data|frontend|backend|full stack|qa|devops|ux|ui|visualizer|tester|"
    r"artist|administrator|coordinator)\b",
    re.I,
)
_COMPANY_HINT_RE = re.compile(
    r"\b(inc|llc|ltd|limited|corp|corporation|company|technologies|solutions|"
    r"systems|studio|agency|group|pvt|private|labs|software|digital|media|"
    r"consulting|enterprises|industries|global|international)\b",
    re.I,
)
_ROLE_TITLE_RE = re.compile(
    r"\b(?:(?:senior|sr\.?|junior|jr\.?|lead|principal|staff|associate|"
    r"head|chief)\s+)?(?:front[\s-]?end|back[\s-]?end|full[\s-]?stack|"
    r"software|data|devops|qa|test|automation|cloud|platform|product|project|"
    r"marketing|content|graphic|visual|ui|ux)?\s*"
    r"(?:engineer|developer|designer|manager|analyst|architect|consultant|"
    r"specialist|director|lead|intern|researcher|visualizer|artist|tester|"
    r"administrator|coordinator)\b(?:\s*/\s*(?:art\s+director|designer|"
    r"developer|manager|visualizer))?",
    re.I,
)
_EMAIL_LABEL_RE = re.compile(r"^(?:e-?mail|mail|email address)\s*[:\-]?\s*", re.I)
_EMAIL_OBFUSCATION_REPLACEMENTS = (
    (re.compile(r"(?i)\s*(?:\(|\[)?at(?:\)|\])\s*"), "@"),
    (re.compile(r"(?i)\s*(?:\(|\[)?dot(?:\)|\])\s*"), "."),
)
_NAME_GENERIC_TOKEN_RE = re.compile(
    r"\b(profile|summary|objective|curriculum|vitae|contact|details|information|about)\b",
    re.I,
)


def _month_number(token: str | None) -> int | None:
    if not token:
        return None
    return _MONTH_LOOKUP.get(token.strip().lower())


def _month_index(year: int, month: int) -> int:
    return year * 12 + (month - 1)


def _year_month_from_index(index: int) -> tuple[int, int]:
    year, month_zero = divmod(index, 12)
    return year, month_zero + 1


def _canonical_section_header(line: str) -> str | None:
    candidate = re.sub(r"\s+", " ", line.strip())
    if not candidate:
        return None
    for name, pattern in _SECTION_HEADER_PATTERNS.items():
        if pattern.match(candidate):
            return name
    return None


def _split_resume_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        header = _canonical_section_header(line)
        if header:
            current = header
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return sections


def _normalise_name_case(name: str) -> str:
    words = []
    for token in name.split():
        if token.isupper() or token.islower():
            words.append(token[:1].upper() + token[1:].lower())
        else:
            words.append(token)
    return " ".join(words)


def _normalise_email_text(text: str) -> str:
    candidate = text
    for pattern, replacement in _EMAIL_OBFUSCATION_REPLACEMENTS:
        candidate = pattern.sub(replacement, candidate)
    candidate = re.sub(r"(?<=\w)\s*@\s*(?=\w)", "@", candidate)
    candidate = re.sub(r"(?<=\w)\s*\.\s*(?=\w)", ".", candidate)
    return candidate


def _extract_email(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = _EMAIL_LABEL_RE.sub("", raw_line.strip())
        normalised_line = _normalise_email_text(line)
        for match in _EMAIL_RE.finditer(normalised_line):
            candidate = match.group(0).strip(" \t<>[](){}'\".,;:|")
            if candidate:
                return candidate.lower()
    return None


def _email_name_parts(email: str | None) -> list[str]:
    if not email or "@" not in email:
        return []
    local = email.split("@", 1)[0]
    local = re.sub(r"\d+", " ", local)
    local = re.sub(r"[._\-+]+", " ", local)
    tokens = [
        token.lower()
        for token in local.split()
        if len(token) >= 2 and not _NAME_GENERIC_TOKEN_RE.search(token)
    ]
    deduped = list(dict.fromkeys(tokens))
    return deduped[:4]


def _name_candidate_score(candidate: str, line_index: int, email_tokens: set[str]) -> float:
    text = re.sub(r"\s+", " ", candidate.strip(" |,;/"))
    if not text or len(text) > 60:
        return -1.0
    if _canonical_section_header(text):
        return -1.0
    if _NAME_REJECT_RE.search(text):
        return -1.0
    if _EMAIL_RE.search(text) or _LINKEDIN_RE.search(text) or _BEHANCE_RE.search(text):
        return -1.0
    if _PHONE_RE.search(text) or _YEAR_RE.search(text) or any(ch.isdigit() for ch in text):
        return -1.0

    tokens = text.split()
    if not 2 <= len(tokens) <= 4:
        return -1.0
    if not all(_PERSON_NAME_TOKEN_RE.match(token) for token in tokens):
        return -1.0

    score = 24.0
    score += max(0.0, 8.0 - line_index * 1.5)
    if len(tokens) == 2:
        score += 6.0
    elif len(tokens) == 3:
        score += 4.0
    else:
        score += 2.0

    name_tokens = [token.lower().strip(".") for token in tokens]
    overlap = len(set(name_tokens) & email_tokens)
    if overlap >= 2:
        score += 16.0
    elif overlap == 1:
        score += 8.0

    if all(token[:1].isupper() or token.isupper() for token in tokens):
        score += 4.0
    if _NAME_GENERIC_TOKEN_RE.search(text):
        score -= 12.0

    return score


def _is_person_name_candidate(line: str, email_tokens: set[str] | None = None) -> bool:
    return _name_candidate_score(line, 0, email_tokens or set()) >= 24.0


def _extract_candidate_name(text: str, email: str | None = None) -> str | None:
    sections = _split_resume_sections(text)
    header_lines = sections.get("header", [])
    if not header_lines:
        header_lines = [line.strip() for line in text.splitlines() if line.strip()][:8]

    email_parts = _email_name_parts(email)
    email_tokens = set(email_parts)
    best_candidate: str | None = None
    best_score = -1.0

    for line_index, line in enumerate(header_lines[:10]):
        for segment in re.split(r"[|•]+", line):
            candidate = re.sub(r"\s+", " ", segment).strip(" |,;/")
            score = _name_candidate_score(candidate, line_index, email_tokens)
            if score > best_score:
                best_candidate = candidate
                best_score = score

    if best_candidate and best_score >= 24.0:
        return _normalise_name_case(best_candidate)

    if len(email_parts) >= 2:
        fallback = " ".join(token.capitalize() for token in email_parts[:3])
        if _is_person_name_candidate(fallback, email_tokens):
            return fallback
    return None


def _line_looks_education_related(line: str) -> bool:
    return bool(_EDUCATION_RE.search(line))


def _line_looks_like_role(line: str) -> bool:
    if _ROLE_HINT_RE.search(line):
        return True
    return bool(re.search(r"\b(at|@)\b|[-–—|]", line))


def _line_looks_like_company(line: str) -> bool:
    cleaned = _clean_entity_text(_strip_date_ranges(line))
    if not cleaned or len(cleaned) > 80:
        return False
    if _canonical_section_header(cleaned) or _line_looks_education_related(cleaned):
        return False
    if _ROLE_TITLE_RE.search(cleaned):
        return False
    if _COMPANY_HINT_RE.search(cleaned):
        return True
    tokens = re.findall(r"[A-Za-z][A-Za-z&'.-]*", cleaned)
    if not 1 <= len(tokens) <= 6:
        return False
    capitalized = sum(1 for token in tokens if token[:1].isupper())
    return capitalized >= max(1, len(tokens) - 1)


def _parse_date_span(match: re.Match[str]) -> dict[str, Any] | None:
    try:
        start_year = int(match.group("start_year"))
    except (TypeError, ValueError):
        return None

    start_month = _month_number(match.group("start_month")) or 1
    end_current = match.group("end_current")
    if end_current:
        end_year = _CURRENT_YEAR
        end_month = _CURRENT_MONTH
    else:
        try:
            end_year = int(match.group("end_year"))
        except (TypeError, ValueError):
            return None
        end_month = _month_number(match.group("end_month")) or 12

    start_idx = _month_index(start_year, start_month)
    end_idx = _month_index(end_year, end_month)
    if end_idx < start_idx:
        return None

    explicit_months = bool(match.group("start_month")) and bool(match.group("end_month") or end_current)
    confidence = 1.0 if explicit_months else 0.8
    return {
        "start_year": start_year,
        "end_year": end_year,
        "start_idx": start_idx,
        "end_idx": end_idx,
        "is_current": bool(end_current),
        "confidence": confidence,
    }


def _strip_date_ranges(text: str) -> str:
    stripped = _DATE_SPAN_RE.sub("", text)
    stripped = re.sub(r"\(\s*\)", "", stripped)
    return re.sub(r"\s{2,}", " ", stripped).strip(" |-–—,;:/")


def _clean_entity_text(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip(" |-–—,;:/")
    return cleaned or None


def _clean_role_title(text: str | None) -> str | None:
    cleaned = _clean_entity_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r"^[•*\-\s]+", "", cleaned)
    match = _ROLE_TITLE_RE.search(cleaned)
    if match:
        return _clean_entity_text(match.group(0))
    if len(cleaned) > 90 or len(cleaned.split()) > 10:
        return None
    if _ROLE_HINT_RE.search(cleaned):
        return cleaned
    return None


def _clean_company_name(text: str | None) -> str | None:
    cleaned = _clean_entity_text(text)
    if not cleaned:
        return None
    cleaned = re.sub(r"^[•*\-\s]+", "", cleaned)
    if len(cleaned) > 90 or len(cleaned.split()) > 8:
        return None
    if _line_looks_education_related(cleaned) or _canonical_section_header(cleaned):
        return None
    # Keep role titles out of company lists unless there is an explicit company suffix.
    if _ROLE_TITLE_RE.search(cleaned) and not _COMPANY_HINT_RE.search(cleaned):
        return None
    return cleaned


def _extract_role_and_company(source_text: str) -> tuple[str | None, str | None]:
    candidate = _clean_entity_text(_strip_date_ranges(source_text))
    if not candidate:
        return None, None

    patterns = [
        re.compile(r"^(?P<title>.+?)\s+(?:at|@)\s+(?P<company>.+)$", re.I),
        re.compile(r"^(?P<title>.+?)\s+[-–—|]\s+(?P<company>.+)$"),
    ]
    for pattern in patterns:
        match = pattern.match(candidate)
        if match:
            title = _clean_role_title(match.group("title"))
            company = _clean_company_name(match.group("company"))
            if title and company:
                return title, company

    parts = [
        _clean_entity_text(part)
        for part in re.split(r"\s+[|–—]\s+|\s+-\s+", candidate)
    ]
    parts = [part for part in parts if part]
    if len(parts) >= 2:
        title = next((_clean_role_title(part) for part in parts if _clean_role_title(part)), None)
        company = next((_clean_company_name(part) for part in parts if _line_looks_like_company(part)), None)
        if title or company:
            return title, company

    title = _clean_role_title(candidate)
    if title:
        return title, None
    if _line_looks_like_company(candidate):
        return None, _clean_company_name(candidate)
    return None, None


def _extract_experience_entries(text: str) -> list[dict[str, Any]]:
    sections = _split_resume_sections(text)
    lines = sections.get("experience")
    if not lines:
        lines = [line.strip() for line in text.splitlines() if line.strip()]

    entries: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str, str]] = set()

    for idx, line in enumerate(lines):
        if not line or _canonical_section_header(line):
            continue

        combined = line
        match = _DATE_SPAN_RE.search(line)
        if match is None and idx + 1 < len(lines):
            next_line = lines[idx + 1]
            if _DATE_SPAN_RE.search(next_line) and _line_looks_like_role(line):
                combined = f"{line} {next_line}"
                match = _DATE_SPAN_RE.search(next_line)

        if match is None or _line_looks_education_related(combined):
            continue

        parsed = _parse_date_span(match)
        if not parsed:
            continue

        entity_context = [combined]
        if idx > 0:
            entity_context.insert(0, lines[idx - 1])
        if idx > 1:
            entity_context.insert(0, lines[idx - 2])
        if idx + 1 < len(lines):
            entity_context.append(lines[idx + 1])
        title, company = _extract_role_and_company(" | ".join(entity_context))
        dedupe_key = (
            parsed["start_idx"],
            parsed["end_idx"],
            title or "",
            company or "",
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        entries.append({
            "title": title,
            "company": company,
            "start_year": parsed["start_year"],
            "end_year": parsed["end_year"],
            "start_idx": parsed["start_idx"],
            "end_idx": parsed["end_idx"],
            "is_current": parsed["is_current"],
            "confidence": parsed["confidence"],
            "source_text": combined,
        })

    entries.sort(key=lambda item: (item["end_idx"], item["start_idx"]), reverse=True)
    return entries


def _extract_education_summary(text: str) -> str | None:
    sections = _split_resume_sections(text)
    education_lines = sections.get("education", [])
    if education_lines:
        return re.sub(r"\s+", " ", " | ".join(education_lines[:2])).strip()

    for line in text.splitlines():
        if _line_looks_education_related(line):
            return re.sub(r"\s+", " ", line.strip())
    return None


def regex_prepass(text: str) -> dict[str, Any]:
    """
    Extract fields that regex can handle reliably.
    Returns a dict that will be merged into the final result.
    """
    experience_entries = _extract_experience_entries(text)
    extracted_email = _extract_email(text)
    out: dict[str, Any] = {
        "email": extracted_email,
        "phone": None,
        "linkedin": None,
        "behance": None,
        "name": _extract_candidate_name(text, extracted_email),
        "education": _extract_education_summary(text),
        "current_role": None,
        "_date_ranges": [],   # internal – used for experience estimation
        "_years_found": [],   # internal
        "_experience_entries": experience_entries,
        "_experience_month_ranges": [],
        "_experience_confidences": [],
        "_companies_worked": [],
    }

    # phone — take first plausible hit, reject date-range lookalikes
    for m in _PHONE_RE.finditer(text):
        candidate = m.group(0).strip()

        # reject if it looks like a year range e.g. "2022 - 2025"
        if _DATE_RANGE_LOOKALIKE.match(candidate):
            continue

        # reject if it starts with a 4-digit year (19xx / 20xx)
        if re.match(r"^(19|20)\d{2}", candidate.lstrip()):
            continue

        digits = re.sub(r"\D", "", candidate)
        if 7 <= len(digits) <= 15:
            out["phone"] = candidate
            break

    # linkedin
    m = _LINKEDIN_RE.search(text)
    if m:
        out["linkedin"] = m.group(0).rstrip("/")

    # behance
    m = _BEHANCE_RE.search(text)
    if m:
        raw_url = m.group(0).rstrip("/")
        # normalise to full https URL
        if not raw_url.startswith("http"):
            raw_url = "https://" + raw_url
        out["behance"] = raw_url

    # experience-derived date ranges only; this avoids education/project years
    out["_date_ranges"] = [
        (entry["start_year"], entry["end_year"])
        for entry in experience_entries
    ]
    out["_experience_month_ranges"] = [
        (entry["start_idx"], entry["end_idx"])
        for entry in experience_entries
    ]
    out["_experience_confidences"] = [
        entry["confidence"]
        for entry in experience_entries
    ]
    out["_companies_worked"] = list(dict.fromkeys(
        entry["company"]
        for entry in experience_entries
        if entry.get("company")
    ))

    current_entry = next((entry for entry in experience_entries if entry["is_current"]), None)
    if current_entry is None and experience_entries:
        current_entry = max(experience_entries, key=lambda item: item["end_idx"])
    if current_entry:
        out["current_role"] = current_entry.get("title")

    out["_years_found"] = [int(y) for y in _YEAR_RE.findall(text)]

    return out


def _estimate_experience_from_month_ranges(
    month_ranges: list[tuple[int, int]],
    confidences: list[float] | None = None,
) -> tuple[float, float]:
    """
    Merge overlapping month ranges and return (years, confidence).

    Month-level math prevents the parser from shaving off a year when resumes
    use month + year ranges or "Present".
    """
    if not month_ranges:
        return 0.0, 0.0

    merged: list[list[int]] = []
    for start, end in sorted(month_ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    total_months = sum(end - start + 1 for start, end in merged)
    years = round(total_months / 12.0, 1)

    if confidences:
        average_conf = sum(confidences) / len(confidences)
        confidence = min(0.98, round(average_conf + min(0.12, 0.03 * len(month_ranges)), 2))
    else:
        confidence = min(0.9, round(0.45 + 0.08 * len(month_ranges), 2))

    return years, confidence


def _estimate_experience_from_dates(date_ranges: list[tuple[int, int]]) -> tuple[float, float]:
    """
    Backward-compatible year-range estimator.

    Converts year spans to month spans, then delegates to the month-aware
    implementation used by the parser pipeline.
    """
    month_ranges = [
        (_month_index(start, 1), _month_index(end, 12))
        for start, end in date_ranges
        if end >= start
    ]
    return _estimate_experience_from_month_ranges(month_ranges)


# ══════════════════════════════════════════════════════════════════════════
# 3.  LLM PROMPT  (Groq / llama-3.3-70b-versatile – free tier)
# ══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are an expert resume parser and evaluator operating inside a production pipeline.
Return ONLY valid JSON — no markdown, no explanation, no code fences.

=== PRODUCTION CONTEXT RULES ===
- Input may be a TRIMMED resume (only experience/skills/education sections).
  Do NOT require headers or formatting. Extract from raw semantic content.
- Ignore decorative text, repeated lines, OCR noise, and keyword stuffing.
- Unicode names (Arabic, Urdu, accented Latin, CJK) must be preserved exactly.
- Never hallucinate companies, roles, dates, or Behance project details.

=== NAME EXTRACTION (CRITICAL) ===
- Extract the PERSON's full name only — never a company, university, or institution.
- The name is almost always at the very top of the resume.
- If the top line is a university/company name, look at the next line.
- If you cannot find a person's name with confidence, return null.

=== VALIDATION ===
If the text is NOT a resume (logo, random doc, blank page):
  Return: {"is_valid_resume": false, "ranking_score": 0, "notes": "<reason>"}
  and all other fields null/[].

=== OUTPUT SCHEMA (return every key, use null if missing) ===
{
  "is_valid_resume": true,
  "name": string or null,
  "estimated_years_of_experience": number,
  "experience_confidence": float 0-1,
  "skills": [list of TECHNICAL tools/technologies/software ONLY.
             EXCLUDE all soft skills, personality traits, and generic abilities.
             Examples to EXCLUDE: Problem Solving, Team Leadership, Communication,
             Time Management, Creativity, Critical Thinking, Attention to Detail.
             Examples to INCLUDE: Figma, Python, Adobe XD, React, SQL, Blender],
  "top_skills": [EXACTLY max 5 items — never more than 5 — strongest technical skills from skills list],
  "current_role": string or null,
  "seniority_level": "intern" | "junior" | "mid" | "senior" | "lead" | "unknown",
  "role_detected": "frontend" | "backend" | "fullstack" | "data" | "devops" | "qa" | "design" | "marketing" | "general",
  "companies_worked": [list of strings],
  "education": string or null,
  "resume_quality_score": number 0-100,
  "ranking_score": number 0-100,
  "ranking_breakdown": {
    "experience_score": number,
    "skills_score": number,
    "seniority_score": number,
    "quality_score": number
  },
  "notes": string
}

=== ROLE DETECTION ===
  frontend  → React, Vue, Angular, Next.js, UI engineering, HTML/CSS, frontend titles
  backend   → Node.js, Django, FastAPI, Spring, APIs, databases, backend titles
  fullstack → explicit full-stack titles OR strong frontend + backend evidence
  data      → SQL, Python data stack, Spark, Airflow, dbt, BI, data engineering/science
  devops    → AWS/GCP/Azure, Docker, Kubernetes, Terraform, CI/CD, infrastructure
  qa        → QA, test automation, Selenium, Cypress, Playwright, manual testing
  design    → UX, UI, Figma, Illustrator, Photoshop, brand, typography, wireframe
  marketing → SEO, SEM, campaigns, CRM, content strategy, growth, analytics
  general   → everything else

=== EXPERIENCE CONFIDENCE ===
  1.0 = explicit full date ranges (month + year, both endpoints)
  0.8 = year-only date ranges
  0.5 = partial dates or only start years
  0.3 = inferred from role count / seniority titles only
  0.1 = complete guess

=== SENIORITY MAPPING ===
  intern   → student, trainee, intern
  junior   → junior, associate, entry-level, graduate (<2 yrs)
  mid      → engineer/developer/analyst (2–5 yrs, no "senior/lead")
  senior   → senior, staff, principal, specialist (5+ yrs)
  lead     → lead, manager, director, VP, head of, CTO, architect
  unknown  → cannot determine

=== RESUME QUALITY SCORE (0–100) ===
  +20  contact info present
  +20  work experience section with dates
  +20  measurable achievements (numbers, %, metrics)
  +20  education section present
  +20  skills section present and detailed
HARD CAP: quality_score must never exceed 80.
Quality measures PRESENTATION only — a well-formatted but low-skill resume
must NOT outrank a strong-experience poorly-formatted one.   [constraint 5]

=== RANKING — MUST SPREAD ACROSS FULL 0–100 RANGE ===
  Compute experience_score (non-linear):
    0yr→0  1yr→15  2yr→25  3yr→35  5yr→50  8yr→65  10yr→75  15yr→85  20+yr→95

  Compute skills_score:
    0→0  1-3→20  4-6→40  7-10→60  11-15→75  16+→90  (+5 rare/specialist bonus)

  seniority_score: intern→10  junior→30  mid→50  senior→70  lead→90  unknown→30

  quality_score = min(resume_quality_score, 80)

  APPLY ROLE-WEIGHTED FORMULA:
    IF role_detected == "design":
      ranking = portfolio_strength(35%) + skills(30%) + experience(20%) + quality(15%)
      portfolio_strength = proxy from design skill depth (use skills_score)
    IF role_detected == "marketing":
      ranking = impact_score(35%) + skills(30%) + experience(20%) + quality(15%)
      impact_score = proxy from measurable achievements density
    IF role_detected in ["frontend", "backend", "fullstack", "data", "devops", "qa"]:
      ranking = skills(40%) + experience(30%) + seniority(20%) + quality(10%)
    IF role_detected == "general":
      ranking = experience(40%) + skills(30%) + seniority(20%) + quality(10%)

  DIVERSITY RULES — CRITICAL:
  - Use the FULL 0–100 range. Avoid clustering candidates near the same score.
  - Use decimal precision to differentiate similar candidates.
  - If two candidates appear equal, still differentiate on small skill/exp variations.

=== BEHANCE CONSTRAINT ===
  Behance data may be partial (title + tools only, views optional).
  NEVER infer descriptions or quality from missing data.
  NEVER use Behance data in ranking_score.

=== STRICT OUTPUT RULES ===
- Do NOT include email, phone, linkedin, or behance_url in your JSON
- Do NOT hallucinate any field
- All fields must exist (null / [] if unknown)
- Return ONLY the JSON object\
"""

USER_TEMPLATE = """\
=== RESUME TEXT ===
{text}
===================

Now return the JSON.\
"""


def call_groq_llm(
    text: str,
    client: Any,
    model: str = "llama-3.1-8b-instant",
    max_retries: int = 6,
) -> dict:
    """
    Send cleaned resume text to Groq and return parsed JSON.

    Retry strategy for rate-limit errors (HTTP 429):
      Attempt  Base wait   With jitter (≈)
      ──────   ─────────   ───────────────
        1        5 s          5–8 s
        2       10 s         10–15 s
        3       20 s         20–30 s
        4       40 s         40–60 s

    Retry-After header is honoured but CAPPED at 60 s.
    Values > 60 s indicate a daily token quota reset — those cause an
    immediate fallback to rule-based rather than waiting hours.

    Raises:
        RuntimeError    – daily quota exceeded (caller uses rule-based)
        json.JSONDecodeError – model returned non-JSON
    """
    import random

    # Groq free tier: daily quota resets are reported as large Retry-After
    # values (hundreds/thousands of seconds). Anything above this cap means
    # "come back tomorrow" — do NOT retry, fall back immediately.
    _RETRY_AFTER_CAP   = 60    # seconds — above this → daily quota, give up
    _BASE_WAITS        = [5, 10, 20, 40]   # per-attempt base (seconds)

    trimmed = text[:12_000]

    for attempt in range(1, max_retries + 2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": USER_TEMPLATE.format(text=trimmed)},
                ],
                temperature=0.1,                    
                max_tokens = 512)

            raw = response.choices[0].message.content.strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.M)
            raw = re.sub(r"\s*```$",          "", raw, flags=re.M)
            return json.loads(raw)

        except Exception as exc:
            exc_str  = str(exc).lower()
            exc_type = type(exc).__name__

            # ── non-retryable: bad JSON ───────────────────────────────────
            if isinstance(exc, json.JSONDecodeError):
                raise

            # ── non-retryable: auth errors ────────────────────────────────
            if any(s in exc_str for s in ("401", "403", "authentication",
                                          "invalid_api_key")):
                log.error("Groq auth error — check GROQ_API_KEY.")
                raise

            # ── rate-limit (429) ──────────────────────────────────────────
            is_rate_limit = any(s in exc_str for s in (
                "429", "rate_limit", "rate limit", "too many", "quota"
            )) or "RateLimitError" in exc_type

            if is_rate_limit:
                # ── parse Retry-After header ──────────────────────────────
                retry_after: float | None = None
                if hasattr(exc, "response") and exc.response is not None:
                    ra = getattr(exc.response, "headers", {}).get("Retry-After", "")
                    try:
                        retry_after = float(ra)
                    except (ValueError, TypeError):
                        pass

                # ── daily quota check: large Retry-After = come back tomorrow
                if retry_after is not None and retry_after > _RETRY_AFTER_CAP:
                    log.warning(
                        "Groq daily token quota exhausted "
                        "(Retry-After: %.0f s ≈ %.1f min). "
                        "Falling back to rule-based parser for this resume.",
                        retry_after, retry_after / 60,
                    )
                    raise RuntimeError(
                        f"groq_daily_quota_exhausted:retry_after={retry_after:.0f}s"
                    )

                # ── per-minute limit: use capped exponential back-off ─────
                if attempt > max_retries:
                    log.error(
                        "Groq rate limit: all %d retries exhausted. "
                        "Falling back to rule-based parser.", max_retries,
                    )
                    raise

                base_wait = _BASE_WAITS[min(attempt - 1, len(_BASE_WAITS) - 1)]
                # honour Retry-After only up to the cap
                floored   = min(retry_after or 0, _RETRY_AFTER_CAP)
                jitter    = random.uniform(0, base_wait * 0.5)
                wait_secs = max(floored, base_wait) + jitter

                log.warning(
                    "Groq rate limit hit (attempt %d/%d). "
                    "Waiting %.1f s before retry …",
                    attempt, max_retries, wait_secs,
                )
                time.sleep(wait_secs)
                continue

            # ── transient server errors (5xx / timeout) ───────────────────
            is_transient = any(s in exc_str for s in (
                "500", "502", "503", "504", "timeout", "connection"
            )) or "ServiceUnavailable" in exc_type

            if is_transient and attempt <= max_retries:
                base_wait = _BASE_WAITS[min(attempt - 1, len(_BASE_WAITS) - 1)]
                wait_secs = base_wait + random.uniform(0, 2)
                log.warning(
                    "Groq transient error '%s' (attempt %d/%d). "
                    "Waiting %.1f s …",
                    exc_type, attempt, max_retries, wait_secs,
                )
                time.sleep(wait_secs)
                continue

            raise

    raise RuntimeError("call_groq_llm: retry loop exited unexpectedly")


# ══════════════════════════════════════════════════════════════════════════
# 4.  RULE-BASED FALLBACK  (when no LLM is available)
# ══════════════════════════════════════════════════════════════════════════

_SKILL_KEYWORDS = {
    # languages
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "ruby", "php", "kotlin", "swift", "scala", "r",
    # web
    "react", "angular", "vue", "node.js", "nodejs", "django", "flask",
    "fastapi", "spring", "laravel", "next.js", "express",
    # data / ml
    "sql", "mysql", "postgresql", "mongodb", "redis", "elasticsearch",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "spark", "hadoop", "kafka", "airflow", "dbt",
    # cloud / devops
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
    "jenkins", "github actions", "ci/cd", "linux",
    # design / creative
    "figma", "sketch", "adobe xd", "invision", "zeplin", "framer",
    "photoshop", "illustrator", "indesign", "after effects", "premiere",
    "blender", "ux research", "wireframing", "prototyping",
    "user testing", "design systems", "accessibility", "typography",
    "brand identity", "motion design",
    # tools
    "git", "jira", "excel", "tableau", "power bi",
    "postman", "rest api", "graphql",
    #frontend
    "react", "angular", "vue", "svelte", "next.js", "nuxt", "gatsby",
    "typescript", "javascript", "html", "css", "sass", "tailwind",
    "webpack", "vite", "redux", "zustand", "react native", "expo",
    #backend
    "node.js", "express", "fastapi", "django", "flask",
    "spring", "laravel", "rails", "asp.net", "graphql", "rest api",
    "grpc", "websockets", "microservices", "serverless",
    #data_engineering
    "sql", "postgresql", "mysql", "sqlite", "mongodb", "redis",
    "elasticsearch", "cassandra", "dynamodb", "snowflake", "bigquery",
    "spark", "hadoop", "kafka", "airflow", "dbt", "flink", "databricks",
    "hive", "presto", "tableau", "power bi", "looker",
    #ml_ai
    "tensorflow", "pytorch", "keras", "scikit-learn", "xgboost",
    "lightgbm", "hugging face", "transformers", "langchain", "openai api",
    "nlp", "computer vision", "mlflow", "kubeflow", "pandas",
    "numpy", "scipy", "matplotlib", "seaborn", "plotly",
    #cloud_devops
    "aws", "gcp", "azure", "docker", "kubernetes", "terraform",
    "ansible", "jenkins", "github actions", "gitlab ci", "ci/cd",
    "linux", "nginx", "prometheus", "grafana", "datadog",
    "cloudformation", "pulumi", "helm", "argocd",
    #marketing
    "seo", "sem", "ppc", "google ads", "meta ads", "facebook ads",
    "instagram ads", "tiktok ads", "linkedin ads", "youtube ads",
    "media buying", "paid media", "retargeting",
    "google analytics", "ga4", "google tag manager", "meta pixel",
    "hubspot", "salesforce", "klaviyo", "mailchimp", "crm",
    "email marketing", "marketing automation", "content marketing",
    "social media", "influencer marketing", "affiliate marketing",
    "conversion rate optimization", "lead generation",
    "digital marketing", "performance marketing", "growth marketing",
    "roas", "cpa", "cac", "ltv",    

}

_SKILL_ALIASES = {
    "javascript": ("javascript", "js", "ecmascript"),
    "typescript": ("typescript", "ts"),
    "react": ("react", "react.js", "reactjs"),
    "vue": ("vue", "vue.js", "vuejs"),
    "angular": ("angular", "angularjs"),
    "next.js": ("next.js", "nextjs", "next js"),
    "nuxt": ("nuxt", "nuxt.js", "nuxtjs"),
    "node.js": ("node.js", "nodejs", "node js"),
    "express": ("express", "express.js", "expressjs"),
    "tailwind": ("tailwind", "tailwind css", "tailwindcss"),
    "sass": ("sass", "scss"),
    "html": ("html", "html5"),
    "css": ("css", "css3"),
    "redux": ("redux", "redux toolkit", "rtk"),
    "zustand": ("zustand",),
    "vite": ("vite",),
    "webpack": ("webpack",),
    "react native": ("react native", "react-native"),
    "python": ("python", "python3"),
    "java": ("java",),
    "c#": ("c#", "c sharp", "csharp"),
    "c++": ("c++", "cpp"),
    "go": ("go", "golang"),
    "ruby": ("ruby",),
    "php": ("php",),
    "kotlin": ("kotlin",),
    "swift": ("swift",),
    "django": ("django",),
    "flask": ("flask",),
    "fastapi": ("fastapi", "fast api"),
    "spring": ("spring", "spring boot"),
    "laravel": ("laravel",),
    "rails": ("rails", "ruby on rails"),
    "asp.net": ("asp.net", "asp net", ".net"),
    "graphql": ("graphql", "graph ql"),
    "rest api": ("rest api", "restful api", "rest"),
    "grpc": ("grpc", "gRPC"),
    "microservices": ("microservices", "microservice architecture"),
    "serverless": ("serverless", "lambda functions"),
    "postgresql": ("postgresql", "postgres", "psql"),
    "mysql": ("mysql",),
    "sqlite": ("sqlite",),
    "mongodb": ("mongodb", "mongo"),
    "redis": ("redis",),
    "elasticsearch": ("elasticsearch", "elastic search"),
    "sql": ("sql",),
    "aws": ("aws", "amazon web services"),
    "gcp": ("gcp", "google cloud", "google cloud platform"),
    "azure": ("azure", "microsoft azure"),
    "docker": ("docker",),
    "kubernetes": ("kubernetes", "k8s"),
    "terraform": ("terraform",),
    "github actions": ("github actions",),
    "gitlab ci": ("gitlab ci", "gitlab-ci"),
    "ci/cd": ("ci/cd", "cicd", "ci cd"),
    "nginx": ("nginx",),
    "linux": ("linux",),
    "spark": ("spark", "apache spark"),
    "hadoop": ("hadoop",),
    "kafka": ("kafka", "apache kafka"),
    "airflow": ("airflow", "apache airflow"),
    "dbt": ("dbt",),
    "snowflake": ("snowflake",),
    "bigquery": ("bigquery", "big query"),
    "databricks": ("databricks",),
    "pandas": ("pandas",),
    "numpy": ("numpy",),
    "tensorflow": ("tensorflow",),
    "pytorch": ("pytorch", "py torch"),
    "scikit-learn": ("scikit-learn", "sklearn", "scikit learn"),
    "selenium": ("selenium",),
    "cypress": ("cypress",),
    "playwright": ("playwright",),
    "jest": ("jest",),
    "vitest": ("vitest",),
    "testing library": ("testing library", "react testing library"),
    "postman": ("postman",),
    "figma": ("figma",),
    "adobe xd": ("adobe xd", "xd"),
    "photoshop": ("photoshop", "adobe photoshop"),
    "illustrator": ("illustrator", "adobe illustrator"),
    "seo": ("seo", "search engine optimization"),
    "sem": ("sem", "search engine marketing"),
    "google analytics": ("google analytics", "ga4"),
}

_ROLE_SKILL_GROUPS = {
    "frontend": {
        "javascript", "typescript", "react", "vue", "angular", "next.js", "nuxt",
        "svelte", "gatsby", "html", "css", "sass", "tailwind", "webpack", "vite",
        "redux", "zustand", "react native", "testing library",
    },
    "backend": {
        "node.js", "express", "python", "java", "django", "flask", "fastapi",
        "spring", "laravel", "rails", "asp.net", "graphql", "rest api", "grpc",
        "microservices", "serverless", "postgresql", "mysql", "mongodb", "redis",
    },
    "data": {
        "sql", "python", "pandas", "numpy", "spark", "hadoop", "kafka", "airflow",
        "dbt", "snowflake", "bigquery", "databricks", "tensorflow", "pytorch",
        "scikit-learn", "tableau", "power bi", "looker",
    },
    "devops": {
        "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
        "jenkins", "github actions", "gitlab ci", "ci/cd", "linux", "nginx",
        "prometheus", "grafana", "helm", "argocd",
    },
    "qa": {
        "selenium", "cypress", "playwright", "jest", "vitest", "testing library",
        "postman",
    },
    "design": {
        "figma", "sketch", "adobe xd", "photoshop", "illustrator", "indesign",
        "wireframing", "prototyping", "design systems", "ux research",
    },
    "marketing": {
        "seo", "sem", "ppc", "google ads", "meta ads", "google analytics",
        "hubspot", "salesforce", "mailchimp", "crm", "email marketing",
    },
}
_ROLE_SKILL_GROUPS["fullstack"] = (
    _ROLE_SKILL_GROUPS["frontend"] | _ROLE_SKILL_GROUPS["backend"]
)


def _term_pattern(term: str) -> re.Pattern:
    escaped = re.escape(term.lower()).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", re.I)


_SKILL_PATTERNS: list[tuple[str, re.Pattern]] = []
for _canonical, _aliases in _SKILL_ALIASES.items():
    for _alias in _aliases:
        _SKILL_PATTERNS.append((_canonical, _term_pattern(_alias)))
for _keyword in _SKILL_KEYWORDS:
    _SKILL_PATTERNS.append((_keyword, _term_pattern(_keyword)))


def _detect_skills(text: str) -> list[str]:
    found: set[str] = set()
    for canonical, pattern in _SKILL_PATTERNS:
        if pattern.search(text):
            found.add(canonical)
    return sorted(found)


def _rank_skills_for_role(skills: list[str], role: str) -> list[str]:
    role_skills = _ROLE_SKILL_GROUPS.get(role, set())
    return sorted(skills, key=lambda skill: (skill not in role_skills, skill))

# Seniority signal regexes — ORDER MATTERS: more specific first
_SENIORITY_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(lead|manager|director|vp|vice president|head of|cto|architect)\b",
                re.I),                                                                    "lead"),
    (re.compile(r"\b(senior|staff|principal|specialist)\b", re.I),                       "senior"),
    (re.compile(r"\b(intern|trainee)\b", re.I),                                          "intern"),
    (re.compile(r"\b(junior|associate|entry.level|graduate)\b", re.I),                   "junior"),
]


def _detect_seniority(text: str) -> str:
    """Return seniority level string from text signals."""
    for pattern, level in _SENIORITY_MAP:
        if pattern.search(text):
            return level
    # mid is the default if experience hints exist but no strong signal
    return "unknown"


def _experience_score(years: float) -> float:
    """Non-linear mapping of years → 0-100 score (matches LLM prompt table)."""
    breakpoints = [(0, 0), (1, 15), (2, 25), (3, 35), (5, 50),
                   (8, 65), (10, 75), (15, 85), (20, 95)]
    if years <= 0:
        return 0.0
    for i in range(len(breakpoints) - 1):
        x0, y0 = breakpoints[i]
        x1, y1 = breakpoints[i + 1]
        if x0 <= years <= x1:
            t = (years - x0) / (x1 - x0)
            return round(y0 + t * (y1 - y0), 2)
    return 95.0  # 20+ years


def _skills_score(n_skills: int) -> float:
    """Map skill count → 0-100 score."""
    if n_skills == 0:   return 0.0
    if n_skills <= 3:   return 20.0
    if n_skills <= 6:   return 40.0
    if n_skills <= 10:  return 60.0
    if n_skills <= 15:  return 75.0
    return 90.0


_SENIORITY_SCORE_MAP = {
    "intern": 10, "junior": 30, "mid": 50,
    "senior": 70, "lead": 90, "unknown": 30,
}


def _resume_quality_score(text: str, regex_fields: dict, skills: list,
                           date_ranges: list) -> int:
    """
    Heuristic resume quality score (0–100).
    Awards 20 pts each for: contact, work experience w/ dates,
    measurable achievements, education, skills section.
    """
    score = 0
    t = text.lower()

    # contact info
    if regex_fields.get("email") or regex_fields.get("phone"):
        score += 20

    # work experience with dates
    if date_ranges:
        score += 20
    elif re.search(r"\b(experience|work history|employment)\b", t):
        score += 10

    # measurable achievements (numbers / % / metrics)
    if re.search(r"\d+\s*%|\$\s*\d+|\d+x\b|increased|reduced|grew|improved", t):
        score += 20

    # education section
    if re.search(r"\b(education|university|college|degree|bachelor|master|phd|b\.sc|m\.sc)\b", t):
        score += 20

    # skills section
    if skills and len(skills) >= 3:
        score += 20

    return min(100, score)


def _detect_role(text: str) -> str:
    """
    Detect the candidate's domain for role-weighted ranking.
    Returns one of the supported HR filter roles.
    """
    t = text.lower()
    title_signals = {
        "frontend": r"\b(front[\s-]?end|ui engineer|react developer|frontend developer)\b",
        "backend": r"\b(back[\s-]?end|api developer|server-side|backend developer)\b",
        "fullstack": r"\b(full[\s-]?stack|full stack developer|mern|mean stack)\b",
        "data": r"\b(data engineer|data scientist|data analyst|analytics engineer|bi developer)\b",
        "devops": r"\b(devops|site reliability|sre|cloud engineer|platform engineer)\b",
        "qa": r"\b(qa|quality assurance|test automation|automation tester|sdet)\b",
        "design": (
            r"\b(ux|ui|graphic design|visual design|product design|creative director|"
            r"art director|interaction design|brand design)\b"
        ),
        "marketing": (
            r"\b(marketing|seo|sem|ppc|content strategy|growth marketing|"
            r"digital marketing|campaign manager|social media)\b"
        ),
    }
    scores = {role: len(re.findall(pattern, t, re.I)) * 3 for role, pattern in title_signals.items()}
    skills = set(_detect_skills(text))
    for role, role_skills in _ROLE_SKILL_GROUPS.items():
        scores[role] = scores.get(role, 0) + len(skills & role_skills)

    frontend_hits = scores.get("frontend", 0)
    backend_hits = scores.get("backend", 0)
    if scores.get("fullstack", 0) >= 3 or (frontend_hits >= 3 and backend_hits >= 3):
        return "fullstack"

    best_role, best_score = max(scores.items(), key=lambda item: item[1])
    return best_role if best_score > 0 else "general"


def _role_weighted_score(
    role: str,
    exp_sc: float,
    skl_sc: float,
    sen_sc: float,
    qlt_sc: float,
    portfolio_sc: float = 0.0,
    impact_sc: float = 0.0,
) -> float:
    """
    Apply role-specific weights to ranking components.   [constraint 4]

    design    : portfolio(35%) + skills(30%) + experience(20%) + quality(15%)
    marketing : impact(35%)    + skills(30%) + experience(20%) + quality(15%)
    engineering/data/qa/devops : skills(40%) + experience(30%) + seniority(20%) + quality(10%)
    general   : experience(40%) + skills(30%) + seniority(20%) + quality(10%)
    """
    if role == "design":
        return (
            portfolio_sc * 0.35 +
            skl_sc       * 0.30 +
            exp_sc       * 0.20 +
            qlt_sc       * 0.15
        )
    if role == "marketing":
        return (
            impact_sc * 0.35 +
            skl_sc    * 0.30 +
            exp_sc    * 0.20 +
            qlt_sc    * 0.15
        )
    if role in {"frontend", "backend", "fullstack", "data", "devops", "qa"}:
        return (
            skl_sc * 0.40 +
            exp_sc * 0.30 +
            sen_sc * 0.20 +
            qlt_sc * 0.10
        )
    # general
    return (
        exp_sc * 0.40 +
        skl_sc * 0.30 +
        sen_sc * 0.20 +
        qlt_sc * 0.10
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _evidence_score(final: dict[str, Any], regex_fields: dict[str, Any]) -> float:
    """
    Score how much concrete evidence the parser actually found.

    This helps keep sparse resumes from receiving unrealistically high overall
    rankings just because a few heuristics fired.
    """
    score = 0.0
    skills = final.get("skills") or []
    companies = final.get("companies_worked") or []
    years = _safe_float(final.get("estimated_years_of_experience"))
    exp_conf = _safe_float(final.get("experience_confidence"))

    if final.get("name"):
        score += 10
    if regex_fields.get("email"):
        score += 8
    if regex_fields.get("phone"):
        score += 6
    if final.get("current_role"):
        score += 12
    if len(companies) >= 3:
        score += 14
    elif companies:
        score += 10

    if len(skills) >= 12:
        score += 20
    elif len(skills) >= 7:
        score += 16
    elif len(skills) >= 4:
        score += 12
    elif skills:
        score += 6

    if years >= 10:
        score += 14
    elif years >= 5:
        score += 11
    elif years >= 2:
        score += 8
    elif years > 0:
        score += 5

    score += min(12.0, round(exp_conf * 12.0, 2))

    if final.get("education"):
        score += 8
    if final.get("is_valid_resume", True):
        score += 6

    return min(100.0, round(score, 2))


def _calibrate_ranking_score(
    base_score: float,
    final: dict[str, Any],
    regex_fields: dict[str, Any],
) -> float:
    """
    Blend the raw ranking with actual evidence density.

    This produces scores that feel more reasonable in the UI and prevents thin
    resumes from clustering too high.
    """
    if not final.get("is_valid_resume", True):
        return 0.0

    evidence = _evidence_score(final, regex_fields)
    years = _safe_float(final.get("estimated_years_of_experience"))
    exp_conf = _safe_float(final.get("experience_confidence"))
    skills_n = len(final.get("skills") or [])
    companies_n = len(final.get("companies_worked") or [])

    score = base_score * 0.78 + evidence * 0.22

    if exp_conf and exp_conf < 0.45:
        score *= 0.92
    if years < 1 and skills_n < 4:
        score *= 0.84
    elif years < 2 and skills_n < 6:
        score *= 0.90
    if companies_n == 0 and years < 5:
        score *= 0.94
    if not final.get("current_role"):
        score *= 0.97
    if not final.get("name"):
        score *= 0.96

    return round(min(100.0, max(0.0, score)), 1)


def _attach_display_scores(final: dict[str, Any], regex_fields: dict[str, Any]) -> None:
    breakdown = final.get("ranking_breakdown") or {}
    evidence = _evidence_score(final, regex_fields)
    exp_conf = _safe_float(final.get("experience_confidence"))

    final["skills_match_score"] = round(_safe_float(breakdown.get("skills_score")), 1)
    final["evidence_score"] = round(evidence, 1)
    final["consistency_score"] = round(
        min(100.0, max(0.0, exp_conf * 65.0 + evidence * 0.35)),
        1,
    )
    final["overall_score"] = round(_safe_float(final.get("ranking_score")), 1)


def rule_based_parse(text: str, regex_fields: dict) -> dict:
    """
    Full rule-based parser — used when no LLM is available.
    Emits the same schema as the LLM prompt.
    """
    text_lower = text.lower()

    # ── validation ────────────────────────────────────────────────────────
    word_count = len(text.split())
    has_resume_signal = bool(re.search(
        r"\b(experience|education|skills|work|employment|resume|cv|"
        r"university|college|developer|engineer|analyst|designer|manager|"
        r"python|java|react|aws|docker|figma|sql|javascript|typescript|"
        r"b\.sc|m\.sc|bachelor|master|phd|intern|senior|junior|lead)\b",
        text_lower
    ))
    if word_count < 12 or not has_resume_signal:
        return {
            "is_valid_resume": False,
            "name": None, "estimated_years_of_experience": 0,
            "experience_confidence": 0.0, "skills": [], "top_skills": [],
            "current_role": None, "seniority_level": "unknown",
            "role_detected": "general",
            "companies_worked": [], "education": None,
            "resume_quality_score": 0, "ranking_score": 0.0,
            "ranking_breakdown": {"experience_score": 0, "skills_score": 0,
                                  "seniority_score": 0, "quality_score": 0},
            "behance_url": regex_fields.get("behance"),
            "notes": "Text too short or lacks resume signals — marked invalid.",
        }

    experience_entries = regex_fields.get("_experience_entries", [])

    # ── role detection ────────────────────────────────────────────────────
    role = _detect_role(text)                                  # constraint 4

    # ── skills ────────────────────────────────────────────────────────────
    found_skills = _detect_skills(text)
    top_skills   = _rank_skills_for_role(found_skills, role)[:5]

    # ── experience ────────────────────────────────────────────────────────
    years, conf = _estimate_experience_from_month_ranges(
        regex_fields.get("_experience_month_ranges", []),
        regex_fields.get("_experience_confidences"),
    )
    if years == 0 and regex_fields["_years_found"]:
        years_list = sorted(set(regex_fields["_years_found"]))
        if len(years_list) >= 2:
            years = float(years_list[-1] - years_list[0])
            conf  = 0.3

    # ── seniority ─────────────────────────────────────────────────────────
    seniority = _detect_seniority(text)
    if seniority == "unknown" and years >= 2:
        seniority = "mid"

    # ── quality — capped so it never dominates ranking ────────────────────
    # [constraint 5]: quality is evidence of presentation, not capability.
    # Cap its contribution ceiling so a polished-but-empty resume can't
    # outscore a detailed-but-sparse one.
    raw_quality = _resume_quality_score(text, regex_fields, found_skills,
                                        regex_fields["_date_ranges"])
    quality = min(raw_quality, 80)        # hard cap at 80/100

    # ── ranking components ────────────────────────────────────────────────
    exp_sc  = _experience_score(years)
    skl_sc  = _skills_score(len(found_skills))
    sen_sc  = float(_SENIORITY_SCORE_MAP.get(seniority, 30))
    qlt_sc  = float(quality)

    # portfolio_sc / impact_sc: rule-based can only approximate these
    # from available signals (skill count for design, metric density for mkt)
    portfolio_sc = skl_sc  # best proxy: design skill breadth
    metric_hits  = len(re.findall(
        r"\d+\s*%|\$\s*\d+|\d+x\b|roi|roas|ctr|cpc|impressions|conversions",
        text_lower
    ))
    impact_sc = min(90.0, 20.0 + metric_hits * 10)  # marketing impact proxy

    ranking = round(
        _role_weighted_score(role, exp_sc, skl_sc, sen_sc, qlt_sc,
                             portfolio_sc, impact_sc), 1
    )

    current_role = regex_fields.get("current_role")
    companies_worked = regex_fields.get("_companies_worked", [])
    education = regex_fields.get("education")
    name = regex_fields.get("name")
    if current_role is None and experience_entries:
        current_role = experience_entries[0].get("title")

    result = {
        "is_valid_resume": True,
        "name": name,
        "estimated_years_of_experience": round(years, 1),
        "experience_confidence": round(conf, 2),
        "skills": found_skills,
        "top_skills": top_skills,
        "current_role": current_role,
        "seniority_level": seniority,
        "role_detected": role,
        "companies_worked": companies_worked,
        "education": education,
        "resume_quality_score": raw_quality,
        "ranking_score": min(100.0, max(0.0, ranking)),
        "ranking_breakdown": {
            "experience_score": round(exp_sc, 2),
            "skills_score":     round(skl_sc, 2),
            "seniority_score":  round(sen_sc, 2),
            "quality_score":    round(qlt_sc, 2),
        },
        "behance_url": regex_fields.get("behance"),
        "notes": (
            f"Rule-based parse (no LLM). Role={role}. Seniority={seniority}. "
            f"Experience from {'validated experience entries' if experience_entries else 'year spans/inference'}. "
            f"Skills matched via keyword list ({len(found_skills)} found)."
        ),
    }
    result["ranking_score"] = _calibrate_ranking_score(ranking, result, regex_fields)
    _attach_display_scores(result, regex_fields)
    return result



# ══════════════════════════════════════════════════════════════════════════
# 6.  MERGE & FINALISE
# ══════════════════════════════════════════════════════════════════════════

def merge_results(regex_fields: dict, llm_result: dict) -> dict:
    """
    Merge regex (deterministic) fields into LLM/rule-based result.
    Regex always wins for contact fields. LLM fills semantic fields.
    Guarantees every required key exists with correct type.
    """
    final = dict(llm_result)

    # ── contact: regex always overrides ──────────────────────────────────
    final["email"]    = regex_fields.get("email")
    final["phone"]    = regex_fields.get("phone")
    final["linkedin"] = regex_fields.get("linkedin")
    # behance URL stored separately; portfolio data attached later
    final["behance_url"] = regex_fields.get("behance")

    deterministic_years, deterministic_conf = _estimate_experience_from_month_ranges(
        regex_fields.get("_experience_month_ranges", []),
        regex_fields.get("_experience_confidences"),
    )

    # ── experience fallback / correction ──────────────────────────────────
    llm_years = final.get("estimated_years_of_experience")
    try:
        llm_years_value = float(llm_years) if llm_years is not None else 0.0
    except (TypeError, ValueError):
        llm_years_value = 0.0

    if deterministic_years and (
        not llm_years_value or
        (deterministic_conf >= 0.75 and abs(llm_years_value - deterministic_years) >= 1.0)
    ):
        final["estimated_years_of_experience"] = round(deterministic_years, 1)
        final["experience_confidence"] = round(deterministic_conf, 2)

    # ── rename old confidence key if LLM used the old name ───────────────
    if "confidence_score_experience" in final and "experience_confidence" not in final:
        final["experience_confidence"] = final.pop("confidence_score_experience")

    # ── deterministic semantic fallbacks ──────────────────────────────────
    regex_name = regex_fields.get("name")
    if regex_name and not _is_person_name_candidate(str(final.get("name") or "")):
        final["name"] = regex_name

    deterministic_role = regex_fields.get("current_role")
    current_role = final.get("current_role")
    if deterministic_role and (
        not current_role or
        not _clean_role_title(str(current_role)) or
        len(str(current_role).split()) > 10
    ):
        final["current_role"] = regex_fields["current_role"]

    if regex_fields.get("_companies_worked"):
        merged_companies = []
        for company in [*(final.get("companies_worked") or []), *regex_fields["_companies_worked"]]:
            cleaned_company = _clean_company_name(str(company))
            if cleaned_company and cleaned_company not in merged_companies:
                merged_companies.append(cleaned_company)
        if merged_companies:
            final["companies_worked"] = merged_companies

    if not final.get("education") and regex_fields.get("education"):
        final["education"] = regex_fields["education"]

    # ── guarantee all required scalar keys ───────────────────────────────
    _scalar_defaults: dict[str, Any] = {
        "is_valid_resume":               True,
        "name":                          None,
        "estimated_years_of_experience": 0,
        "experience_confidence":         0.0,
        "current_role":                  None,
        "seniority_level":               "unknown",
        "role_detected":                 "general",
        "education":                     None,
        "resume_quality_score":          0,
        "ranking_score":                 0.0,
        "notes":                         "",
    }
    for key, default in _scalar_defaults.items():
        final.setdefault(key, default)

    # ── hard-cap quality score so formatting never dominates  [constraint 5]
    final["resume_quality_score"] = min(
        int(final.get("resume_quality_score") or 0), 80
    )

    # ── guarantee list keys ───────────────────────────────────────────────
    for key in ("skills", "top_skills", "companies_worked"):
        if not isinstance(final.get(key), list):
            final[key] = []

    # derive top_skills from skills if LLM didn't supply them
    if not final["top_skills"] and final["skills"]:
        final["top_skills"] = final["skills"][:5]

    # ── guarantee ranking_breakdown ───────────────────────────────────────
    breakdown = final.get("ranking_breakdown")
    if not isinstance(breakdown, dict):
        # recompute from first principles when LLM omitted it
        yrs     = final["estimated_years_of_experience"]
        n_skl   = len(final["skills"])
        seniority = final.get("seniority_level", "unknown")
        quality   = final.get("resume_quality_score", 0)
        exp_sc  = _experience_score(yrs)
        skl_sc  = _skills_score(n_skl)
        sen_sc  = float(_SENIORITY_SCORE_MAP.get(seniority, 30))
        qlt_sc  = float(quality)
        final["ranking_breakdown"] = {
            "experience_score": round(exp_sc, 2),
            "skills_score":     round(skl_sc, 2),
            "seniority_score":  round(sen_sc, 2),
            "quality_score":    round(qlt_sc, 2),
        }
        # recompute ranking_score consistently when breakdown was missing
        final["ranking_score"] = round(
            exp_sc * 0.4 + skl_sc * 0.3 + sen_sc * 0.2 + qlt_sc * 0.1, 1
        )

    # clamp and calibrate ranking_score
    final["ranking_score"] = min(100.0, max(0.0, _safe_float(final["ranking_score"])))
    final["ranking_score"] = _calibrate_ranking_score(
        final["ranking_score"], final, regex_fields
    )
    _attach_display_scores(final, regex_fields)

    return final


# ══════════════════════════════════════════════════════════════════════════
# 7.  SINGLE-FILE PIPELINE
# ══════════════════════════════════════════════════════════════════════════

def parse_resume(
    pdf_path: str,
    groq_client: Any | None = None,
    fetch_behance: bool = True,
    max_retries: int = 6,
    model: str = "llama-3.1-8b-instant",
) -> dict:
    """Full pipeline for one PDF resume. Returns final structured dict."""
    log.info("Processing: %s", pdf_path)

    # step 1 – extract text
    raw_text = extract_text(pdf_path)

    # step 2 – clean
    clean = _clean_text(raw_text)

    # step 3 – regex pre-pass (extracts Behance URL deterministically)
    regex_fields = regex_prepass(clean)

    # step 4 – LLM or rule-based
    if groq_client:
        try:
            llm_result = call_groq_llm(
                clean,
                groq_client,
                model=model,
                max_retries=max_retries,
            )
        except json.JSONDecodeError as exc:
            log.warning("LLM returned invalid JSON (%s) – using rule-based fallback", exc)
            llm_result = rule_based_parse(clean, regex_fields)
        except Exception as exc:
            log.warning("LLM call failed (%s) – using rule-based fallback", exc)
            llm_result = rule_based_parse(clean, regex_fields)
    else:
        llm_result = rule_based_parse(clean, regex_fields)

    # step 5 – merge
    final = merge_results(regex_fields, llm_result)
    final["source_file"] = Path(pdf_path).name

    return final


# ══════════════════════════════════════════════════════════════════════════
# 8.  BATCH RANKING AGGREGATOR
# ══════════════════════════════════════════════════════════════════════════

def rank_candidates(results: list[dict]) -> list[dict]:
    """Sort parsed resumes by ranking_score descending, add rank field."""
    sorted_results = sorted(
        results,
        key=lambda r: r.get("ranking_score", 0),
        reverse=True,
    )
    for i, r in enumerate(sorted_results, start=1):
        r["rank"] = i
    return sorted_results


def print_summary_table(ranked: list[dict]) -> None:
    """Pretty-print a ranked summary to stdout."""
    header = (
        f"{'Rank':>4}  {'Name':<22} {'Score':>5}  {'Exp':>4}  "
        f"{'Seniority':<8}  {'Quality':>7}  {'Behance':>7}  {'File'}"
    )
    print()
    print("=" * 90)
    print("  CANDIDATE RANKING SUMMARY")
    print("=" * 90)
    print(header)
    print("-" * 90)
    for r in ranked:
        name      = (r.get("name") or "Unknown")[:22]
        score     = r.get("ranking_score") or 0.0
        exp       = r.get("estimated_years_of_experience") or 0.0
        seniority = (r.get("seniority_level") or "unknown")[:8]
        quality   = r.get("resume_quality_score") or 0
        src       = r.get("source_file", "")
        behance   = r.get("behance") or {}
        valid_flag = "" if r.get("is_valid_resume", True) else " ✗"
        # guard: error records may have None for numeric fields
        try:
            print(
                f"{r['rank']:>4}  {name:<22} {float(score):>5.1f}  {float(exp):>4.1f}  "
                f"{seniority:<8}  {int(quality):>7}   {src}{valid_flag}"
            )
        except (TypeError, ValueError):
            print(f"{r['rank']:>4}  {name:<22}  [parse error]  {src}")
    print("=" * 90)
    print()


# ══════════════════════════════════════════════════════════════════════════
# 9.  CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════

def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Resume Parser & Evaluator – outputs JSON + ranking table",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument(
        "--input", "-i",
        required=True,
        help="Path to a single PDF or a directory of PDFs",
    )
    p.add_argument(
        "--output", "-o",
        default="parsed_resumes.json",
        help="Output JSON file (default: parsed_resumes.json)",
    )
    p.add_argument(
        "--api-key",
        default=None,
        help="Groq API key (or set GROQ_API_KEY env var). Free at console.groq.com",
    )
    p.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM; use rule-based parsing only (no API key needed)",
    )
    
    p.add_argument(
        "--model",
        default="llama-3.1-8b-instant",
        help="Groq model to use (default: llama-3.1-8b-instant)",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=8.0,
        help=(
            "Seconds between LLM calls to stay within rate limits (default: 8.0).\n"
            "Groq free tier allows ~30 req/min — 8 s keeps you safely under."
        ),
    )
    p.add_argument(
        "--retries",
        type=int,
        default=6,
        help=(
            "Max LLM retries on rate-limit / transient errors (default: 6).\n"
            "Back-off: 2s, 4s, 8s, 16s (+ jitter). Set 0 to disable retries."
        ),
    )
    return p


def collect_pdfs(input_path: str) -> list[str]:
    p = Path(input_path)
    if p.is_file():
        if p.suffix.lower() != ".pdf":
            sys.exit(f"ERROR: not a PDF file: {p}")
        return [str(p)]
    if p.is_dir():
        pdfs = sorted(p.glob("**/*.pdf"))
        if not pdfs:
            sys.exit(f"ERROR: no PDF files found in: {p}")
        return [str(f) for f in pdfs]
    sys.exit(f"ERROR: path not found: {p}")


def main() -> None:
    args = build_arg_parser().parse_args()

    # ── Groq client setup ─────────────────────────────────────────────────
    groq_client = None
    if not args.no_llm:
        api_key = args.api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            log.warning(
                "No GROQ_API_KEY found. Running in rule-based mode.\n"
                "  Get a free key at https://console.groq.com  then:\n"
                "    export GROQ_API_KEY=gsk_...\n"
                "  or pass --api-key gsk_..."
            )
        elif not HAS_GROQ:
            log.warning("groq package not installed. pip install groq")
        else:
            groq_client = Groq(api_key=api_key)
            log.info("LLM: Groq / %s", args.model)

    # ── collect PDFs ──────────────────────────────────────────────────────
    pdf_files = collect_pdfs(args.input)
    log.info("Found %d PDF(s) to process", len(pdf_files))

    # ── process ───────────────────────────────────────────────────────────
    results: list[dict] = []
    for i, pdf_path in enumerate(pdf_files):
        try:
            result = parse_resume(
                pdf_path, groq_client,
                max_retries=args.retries,
                model=args.model,
            )
            results.append(result)
        except Exception as exc:
            log.error("Failed to parse %s: %s", pdf_path, exc)
            results.append({
                "source_file": Path(pdf_path).name,
                "error": str(exc),
                "ranking_score": 0,
            })

        # rate-limit pause between LLM calls
        if groq_client and i < len(pdf_files) - 1:
            time.sleep(args.delay)

    # ── rank & output ─────────────────────────────────────────────────────
    ranked = rank_candidates(results)
    print_summary_table(ranked)

    out_path = Path(args.output)
    out_path.write_text(json.dumps(ranked, indent=2, ensure_ascii=False))
    log.info("Results saved to: %s", out_path)


if __name__ == "__main__":
    main()
