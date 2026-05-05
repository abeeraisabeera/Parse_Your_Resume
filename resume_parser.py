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
  Skip Behance      : python resume_parser.py --input ./resumes/ --no-behance
  API key           : set env var GROQ_API_KEY=gsk_...
                      OR pass --api-key gsk_...
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
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

if not HAS_FITZ and not HAS_PDFPLUMBER:
    sys.exit("ERROR: install at least one of: pymupdf  pdfplumber")

# ── logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
)
log = logging.getLogger("ResumeParser")

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


def _extract_text_ocr(path: str) -> str:
    """
    OCR fallback for image-based / scanned PDFs.
    Requires: pip install pytesseract pillow pdf2image
    Also needs: apt-get install tesseract-ocr poppler-utils  (Colab / Linux)
    """
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError:
        log.warning("OCR deps missing. Run: pip install pytesseract pillow pdf2image")
        return ""

    try:
        images = convert_from_path(path, dpi=200)
        pages = [pytesseract.image_to_string(img, lang="eng") for img in images]
        return "\n".join(pages)
    except Exception as exc:
        log.warning("OCR failed for %s: %s", path, exc)
        return ""


def extract_text(path: str) -> str:
    """
    Try PyMuPDF → pdfplumber → OCR (for scanned PDFs).
    Raises ValueError only if all three methods yield no text.
    """
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

    if not text.strip():
        log.warning("No text extracted via standard methods — attempting OCR for: %s", path)
        text = _extract_text_ocr(path)

    if not text.strip():
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


def regex_prepass(text: str) -> dict[str, Any]:
    """
    Extract fields that regex can handle reliably.
    Returns a dict that will be merged into the final result.
    """
    out: dict[str, Any] = {
        "email": None,
        "phone": None,
        "linkedin": None,
        "behance": None,
        "_date_ranges": [],   # internal – used for experience estimation
        "_years_found": [],   # internal
    }

    # email
    m = _EMAIL_RE.search(text)
    if m:
        out["email"] = m.group(0).lower()

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

    # date ranges
    ranges = []
    for m in _DATE_RANGE_RE.finditer(text):
        try:
            start_yr = int(m.group(1))
        except (ValueError, TypeError):
            continue
        end_raw = m.group(2)
        if re.match(r"[Pp]resent|[Cc]urrent|[Nn]ow", end_raw):
            end_yr = 2025
        else:
            try:
                end_yr = int(end_raw)
            except (ValueError, TypeError):
                continue   # skip unparseable end year
        if end_yr >= start_yr:
            ranges.append((start_yr, end_yr))
    out["_date_ranges"] = ranges

    out["_years_found"] = [int(y) for y in _YEAR_RE.findall(text)]

    return out


def _estimate_experience_from_dates(date_ranges: list[tuple[int, int]]) -> tuple[float, float]:
    """
    Merge overlapping date ranges and return (years, confidence).
    confidence approaches 1.0 as more complete ranges are found.
    """
    if not date_ranges:
        return 0.0, 0.0

    merged: list[tuple[int, int]] = []
    for start, end in sorted(date_ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append([start, end])

    total = sum(e - s for s, e in merged)
    confidence = min(0.9, 0.4 + 0.1 * len(date_ranges))  # more ranges → more confident
    return float(total), confidence


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
  "role_detected": "design" | "marketing" | "general",
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
    model: str = "llama-3.3-70b-versatile",
    max_retries: int = 4,
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
                max_tokens=1500,
            )

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
    "figma", "photoshop", "illustrator", "adobe xd", "blender", "sketch",
    "indesign", "after effects", "premiere",
    # tools
    "git", "jira", "excel", "tableau", "power bi",
    "postman", "rest api", "graphql",
}

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
    Returns: "design" | "marketing" | "general"             [constraint 4]
    """
    t = text.lower()
    design_signals = re.compile(
        r"\b(ux|ui|graphic design|visual design|figma|illustrator|photoshop|"
        r"sketch|adobe xd|indesign|blender|motion design|brand design|"
        r"typography|wireframe|prototype|user research|interaction design|"
        r"product design|creative director|art director|animator)\b", re.I
    )
    marketing_signals = re.compile(
        r"\b(marketing|seo|sem|ppc|google ads|facebook ads|content strategy|"
        r"copywriting|email marketing|growth hacking|crm|hubspot|salesforce|"
        r"campaign|brand strategy|social media|influencer|conversion rate|"
        r"digital marketing|market research|lead generation|analytics)\b", re.I
    )
    design_hits    = len(design_signals.findall(t))
    marketing_hits = len(marketing_signals.findall(t))

    if design_hits == 0 and marketing_hits == 0:
        return "general"
    if design_hits >= marketing_hits:
        return "design"
    return "marketing"


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
    # general
    return (
        exp_sc * 0.40 +
        skl_sc * 0.30 +
        sen_sc * 0.20 +
        qlt_sc * 0.10
    )


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

    # ── role detection ────────────────────────────────────────────────────
    role = _detect_role(text)                                  # constraint 4

    # ── skills ────────────────────────────────────────────────────────────
    found_skills = sorted({kw for kw in _SKILL_KEYWORDS if kw in text_lower})
    top_skills   = found_skills[:5]

    # ── experience ────────────────────────────────────────────────────────
    years, conf = _estimate_experience_from_dates(regex_fields["_date_ranges"])
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

    return {
        "is_valid_resume": True,
        "name": None,
        "estimated_years_of_experience": round(years, 1),
        "experience_confidence": round(conf, 2),
        "skills": found_skills,
        "top_skills": top_skills,
        "current_role": None,
        "seniority_level": seniority,
        "role_detected": role,
        "companies_worked": [],
        "education": None,
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
            f"Experience from {'date ranges' if conf >= 0.5 else 'year spans/inference'}. "
            f"Skills matched via keyword list ({len(found_skills)} found)."
        ),
    }


# ══════════════════════════════════════════════════════════════════════════
# 5.  BEHANCE PORTFOLIO SCRAPER
# ══════════════════════════════════════════════════════════════════════════

# Behance renders most content server-side in the initial HTML, so a plain
# requests + BeautifulSoup scrape works without a headless browser.
# We target the public profile page (behance.net/<username>).

_BEHANCE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_BEHANCE_TIMEOUT = 10   # seconds per request
_BEHANCE_MAX_PROJECTS = 12   # cap to keep output manageable


def _safe_int(text: str | None) -> int | None:
    """Parse a human-formatted number like '1.2k' or '34,521' to int."""
    if not text:
        return None
    text = text.strip().replace(",", "")
    try:
        if text.lower().endswith("k"):
            return int(float(text[:-1]) * 1_000)
        if text.lower().endswith("m"):
            return int(float(text[:-1]) * 1_000_000)
        return int(float(text))
    except ValueError:
        return None


def _parse_project_card(card) -> dict:
    """
    Extract project metadata from a single Behance project card element.
    Handles multiple Behance HTML layouts gracefully.
    """
    project: dict[str, Any] = {
        "title": None,
        "url": None,
        "tools_used": [],
        "views": None,
        "appreciations": None,
        "cover_image": None,
    }

    # ── title ──────────────────────────────────────────────────────────────
    for sel in [
        "a.Title",
        "[class*='title']",
        "a[title]",
        "h3",
        "h4",
    ]:
        el = card.select_one(sel)
        if el:
            project["title"] = el.get_text(strip=True) or el.get("title")
            if project["title"]:
                break

    # ── project URL ────────────────────────────────────────────────────────
    link = card.select_one("a[href*='/gallery/']")
    if link:
        href = link.get("href", "")
        project["url"] = href if href.startswith("http") else f"https://www.behance.net{href}"

    # ── stats (views / appreciations) ─────────────────────────────────────
    # Behance uses several class naming conventions over time
    for stat_el in card.select("[class*='stat'], [class*='Stats'], [class*='stats']"):
        label_el = stat_el.select_one("[class*='label'], [class*='Label'], span")
        value_el = stat_el.select_one("[class*='value'], [class*='Value'], strong, b")
        if not (label_el and value_el):
            continue
        label = label_el.get_text(strip=True).lower()
        value = _safe_int(value_el.get_text(strip=True))
        if "view" in label:
            project["views"] = value
        elif "appreciat" in label or "like" in label:
            project["appreciations"] = value

    # fallback: look for aria-label on stat spans
    if project["views"] is None:
        for el in card.select("span[aria-label]"):
            aria = el.get("aria-label", "").lower()
            if "view" in aria:
                project["views"] = _safe_int(el.get_text(strip=True))
            elif "appreciat" in aria or "like" in aria:
                project["appreciations"] = _safe_int(el.get_text(strip=True))

    # ── tools / tags ───────────────────────────────────────────────────────
    tools = []
    for tag_el in card.select(
        "[class*='tool'], [class*='Tool'], [class*='tag'], [class*='Tag']"
    ):
        t = tag_el.get_text(strip=True)
        if t and len(t) < 40:   # skip garbage long strings
            tools.append(t)
    project["tools_used"] = list(dict.fromkeys(tools))  # deduplicate, keep order

    # ── cover image ────────────────────────────────────────────────────────
    img = card.select_one("img[src]")
    if img:
        project["cover_image"] = img.get("src") or img.get("data-src")

    return project


def fetch_behance_portfolio(url: str) -> dict:
    """
    Scrape a Behance profile page and return structured project data.

    Returns a dict with keys:
      username       – extracted from URL
      profile_url    – canonical URL used
      projects       – list of project dicts (up to _BEHANCE_MAX_PROJECTS)
      total_found    – how many project cards were detected on the page
      fetch_status   – "ok" | "error" | "skipped"
      error          – error message if fetch_status == "error"
    """
    result: dict[str, Any] = {
        "username": None,
        "profile_url": url,
        "projects": [],
        "total_found": 0,
        "fetch_status": "ok",
        "error": None,
    }

    # extract username for logging
    m = re.search(r"behance\.net/([^/?#]+)", url)
    result["username"] = m.group(1) if m else url

    if not HAS_SCRAPER:
        result["fetch_status"] = "skipped"
        result["error"] = "requests / beautifulsoup4 not installed"
        return result

    log.info("Fetching Behance portfolio: %s", url)

    try:
        resp = requests.get(url, headers=_BEHANCE_HEADERS, timeout=_BEHANCE_TIMEOUT)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        result["fetch_status"] = "error"
        result["error"] = f"HTTP {exc.response.status_code}"
        log.warning("Behance HTTP error for %s: %s", url, result["error"])
        return result
    except requests.exceptions.RequestException as exc:
        result["fetch_status"] = "error"
        result["error"] = str(exc)
        log.warning("Behance request failed for %s: %s", url, exc)
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── locate project cards ───────────────────────────────────────────────
    # Behance has used several container class patterns historically
    card_selectors = [
        "div.ProjectCoverNeue-root",
        "div[class*='ProjectCover']",
        "div[class*='project-cover']",
        "li[class*='ProjectCover']",
        "div.js-project-cover-image-link",
        # broad fallback: any link wrapping a gallery URL
    ]
    cards = []
    for sel in card_selectors:
        cards = soup.select(sel)
        if cards:
            break

    # last-resort: grab anchor elements pointing to /gallery/ paths
    if not cards:
        gallery_links = soup.select("a[href*='/gallery/']")
        # group by their parent containers
        seen_parents: set[int] = set()
        parent_cards = []
        for link in gallery_links:
            parent = link.parent
            pid = id(parent)
            if pid not in seen_parents:
                seen_parents.add(pid)
                parent_cards.append(parent)
        cards = parent_cards

    result["total_found"] = len(cards)
    log.info("  Found %d project card(s) on Behance page", len(cards))

    projects = []
    for card in cards[:_BEHANCE_MAX_PROJECTS]:
        parsed = _parse_project_card(card)
        # only include cards that have at least a title or URL
        if parsed["title"] or parsed["url"]:
            projects.append(parsed)

    result["projects"] = projects
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

    # ── experience fallback ───────────────────────────────────────────────
    if not final.get("estimated_years_of_experience"):
        yrs, conf = _estimate_experience_from_dates(regex_fields["_date_ranges"])
        if yrs:
            final["estimated_years_of_experience"] = round(yrs, 1)
            final["experience_confidence"]          = round(conf, 2)

    # ── rename old confidence key if LLM used the old name ───────────────
    if "confidence_score_experience" in final and "experience_confidence" not in final:
        final["experience_confidence"] = final.pop("confidence_score_experience")

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

    # clamp ranking_score
    final["ranking_score"] = min(100.0, max(0.0, float(final["ranking_score"])))

    return final


# ══════════════════════════════════════════════════════════════════════════
# 7.  SINGLE-FILE PIPELINE
# ══════════════════════════════════════════════════════════════════════════

def parse_resume(
    pdf_path: str,
    groq_client: Any | None = None,
    fetch_behance: bool = True,
    max_retries: int = 4,
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
            llm_result = call_groq_llm(clean, groq_client, max_retries=max_retries)
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

    # step 6 – Behance portfolio (runs only when URL found in resume)
    behance_url = final.get("behance_url")
    if fetch_behance and behance_url:
        raw_portfolio = fetch_behance_portfolio(behance_url)
        # Reshape into the spec-defined "behance" key
        projects_raw = raw_portfolio.get("projects", [])
        # Keep top 5, reshape to {title, description, tools, views}
        projects_out = []
        for p in projects_raw[:5]:
            projects_out.append({
                "title":       p.get("title"),
                "description": None,          # scraper doesn't fetch project page body
                "tools":       p.get("tools_used", []),
                "views":       p.get("views"),
            })
        final["behance"] = {
            "url":           behance_url,
            "projects":      projects_out,
            "project_count": raw_portfolio.get("total_found", len(projects_out)),
            "fetch_status":  raw_portfolio.get("fetch_status", "ok"),
            "error":         raw_portfolio.get("error"),
        }
    else:
        final["behance"] = {
            "url":           behance_url,
            "projects":      [],
            "project_count": 0,
            "fetch_status":  "skipped" if not fetch_behance else "no_url",
            "error":         None,
        }
        if fetch_behance and not behance_url:
            log.info("  No Behance URL found in resume – skipping portfolio fetch")

    # clean up the interim key
    final.pop("behance_url", None)

    # ── flat top-level behance_url for easy access ────────────────────────
    final["behance_url"] = final["behance"].get("url")

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
        if behance and behance.get("url"):
            n_proj      = behance.get("project_count") or 0
            behance_col = f"{n_proj} proj"
        else:
            behance_col = "—"
        valid_flag = "" if r.get("is_valid_resume", True) else " ✗"
        # guard: error records may have None for numeric fields
        try:
            print(
                f"{r['rank']:>4}  {name:<22} {float(score):>5.1f}  {float(exp):>4.1f}  "
                f"{seniority:<8}  {int(quality):>7}  {behance_col:>7}  {src}{valid_flag}"
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
        "--no-behance",
        action="store_true",
        help="Skip Behance portfolio fetching entirely",
    )
    p.add_argument(
        "--model",
        default="llama-3.3-70b-versatile",
        help="Groq model to use (default: llama-3.3-70b-versatile)",
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
        default=4,
        help=(
            "Max LLM retries on rate-limit / transient errors (default: 4).\n"
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
                fetch_behance=not args.no_behance,
                max_retries=args.retries,
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
