
================================================================================
                    RESUME PARSER DEVELOPMENT TASK
                    Technical Specification & Test Suite
================================================================================

PROJECT OVERVIEW
----------------
You are building a production-grade Resume Parser & Evaluator that extracts 
structured data from PDF resumes, scores candidates, and ranks them for 
recruitment pipelines. The system combines deterministic regex extraction with 
LLM-powered semantic parsing and includes portfolio scraping capabilities.

CORE COMPONENTS
---------------
1. PDF TEXT EXTRACTION
   • Primary: PyMuPDF (fitz) for standard text extraction
   • Fallback: pdfplumber for multi-column layouts
   • Last resort: OCR (pytesseract + pdf2image) for scanned/image-based PDFs
   • Raises ValueError if all methods fail to extract text

2. TEXT CLEANING PIPELINE
   • Preserves Unicode (Arabic, Urdu, accented Latin, CJK) — Constraint 7
   • Strips control characters and binary artifacts
   • Removes OCR noise: pure punctuation lines, repeated keywords (>3x) — Constraint 6
   • Collapses excessive whitespace while maintaining structure

3. REGEX PRE-PASS (Deterministic Extraction)
   • Email extraction with lowercase normalization
   • Phone number extraction with date-range rejection logic
     - Rejects year ranges like "2022-2025" misidentified as phones
     - Validates digit count (7-15 digits)
   • LinkedIn URL extraction and normalization
   • Behance URL extraction with https normalization
   • Date range parsing: "Jan 2019 – Mar 2022", "2015 – Present"
     - Maps "Present/Current/Now" to 2025
     - Handles uppercase variants (PRESENT, CURRENT)
   • Year extraction for experience inference fallback

4. EXPERIENCE ESTIMATION ENGINE
   • Merges overlapping date ranges
   • Calculates total years from merged ranges
   • Confidence scoring: 0.4 base + 0.1 per additional range, capped at 0.9
   • Fallback: infers from year span gaps when ranges are sparse (confidence 0.3)

5. RULE-BASED PARSER (LLM Fallback)
   Triggered when: no LLM available, LLM fails, daily quota exhausted, or 
   max retries reached.

   Validation Gate:
   • Minimum 12 words AND presence of resume signals
   • Returns invalid flag if text lacks resume characteristics

   Scoring System:
   • Experience Score (non-linear): 0yr→0, 1yr→15, 2yr→25, 3yr→35, 5yr→50,
     8yr→65, 10yr→75, 15yr→85, 20+yr→95
   • Skills Score: 0→0, 1-3→20, 4-6→40, 7-10→60, 11-15→75, 16+→90
   • Seniority Score: intern→10, junior→30, mid→50, senior→70, lead→90, unknown→30
   • Quality Score: CAPPED AT 80/100 (Constraint 5)
     Awards 20pts each for: contact info, work experience w/ dates,
     measurable achievements, education, skills section

   Role Detection (Constraint 4):
   • "design"    → UX/UI, Figma, Illustrator, Photoshop, typography, wireframe
   • "marketing" → SEO, SEM, campaigns, CRM, content strategy, growth, analytics
   • "general"   → everything else

   Role-Weighted Ranking Formulas:
   • design:    portfolio(35%) + skills(30%) + experience(20%) + quality(15%)
   • marketing: impact(35%) + skills(30%) + experience(20%) + quality(15%)
   • general:   experience(40%) + skills(30%) + seniority(20%) + quality(10%)

6. LLM INTEGRATION (Groq Cloud API)
   • Model: llama-3.3-70b-versatile (free tier, no credit card)
   • Temperature: 0.1 (deterministic)
   • Max tokens: 1500
   • Input truncated to 12,000 characters

   Retry Strategy (max_retries=4):
   ┌─────────┬───────────┬─────────────────────────────┐
   │ Attempt │ Base Wait │ Behavior                    │
   ├─────────┼───────────┼─────────────────────────────┤
   │    1    │    5s     │ + jitter (0-50% of base)    │
   │    2    │   10s     │ + jitter                    │
   │    3    │   20s     │ + jitter                    │
   │    4    │   40s     │ + jitter                    │
   └─────────┴───────────┴─────────────────────────────┘
   • Retry-After header honored but CAPPED at 60 seconds
   • Retry-After > 60s → daily quota → immediate RuntimeError (fallback to rule-based)
   • Non-retryable errors: JSON decode errors, auth errors (401/403)
   • Transient errors (5xx/timeout): retried with same backoff

7. BEHANCE PORTFOLIO SCRAPER
   • Requires: requests + BeautifulSoup4
   • Scrapes public behance.net/<username> profiles
   • Extracts: project title, URL, tools used, views, appreciations, cover image
   • Handles multiple HTML layout variants historically used by Behance
   • Reshapes output to spec: {title, description, tools, views}
   • Status: "ok" | "error" | "skipped" | "no_url"
   • NEVER used in ranking_score calculation

8. MERGE & FINALIZE
   • Regex fields override LLM for: email, phone, linkedin, behance_url
   • LLM experience kept; falls back to regex dates if LLM returns 0
   • Renames old confidence key: confidence_score_experience → experience_confidence
   • Recomputes ranking_breakdown if missing from LLM
   • Derives top_skills from skills if missing
   • Clamps ranking_score to [0, 100]
   • Hard-caps resume_quality_score at 80

9. BATCH RANKING AGGREGATOR
   • Sorts by ranking_score descending
   • Assigns rank field (1 = highest)
   • Pretty-prints summary table with error handling for None fields

OUTPUT SCHEMA (Every parse returns this structure)
--------------------------------------------------
{
  "is_valid_resume": bool,
  "name": string|null,
  "email": string|null,
  "phone": string|null,
  "linkedin": string|null,
  "estimated_years_of_experience": number,
  "experience_confidence": float (0-1),
  "skills": [string],
  "top_skills": [string] (max 5),
  "current_role": string|null,
  "seniority_level": "intern"|"junior"|"mid"|"senior"|"lead"|"unknown",
  "role_detected": "design"|"marketing"|"general",
  "companies_worked": [string],
  "education": string|null,
  "resume_quality_score": int (0-100, capped at 80 in ranking),
  "ranking_score": float (0-100),
  "ranking_breakdown": {
    "experience_score": float,
    "skills_score": float,
    "seniority_score": float,
    "quality_score": float
  },
  "behance": {
    "url": string|null,
    "projects": [{title, description, tools, views}],
    "project_count": int,
    "fetch_status": "ok"|"error"|"skipped"|"no_url",
    "error": string|null
  },
  "behance_url": string|null,        // flat top-level alias
  "notes": string,
  "source_file": string,
  "rank": int                        // added by rank_candidates()
}

CONSTRAINTS & REQUIREMENTS
--------------------------
Constraint 1 — Trimmed/Headerless Input:
   Parser must work on raw trimmed content without standard section headers.
   Extracts from semantic content alone.

Constraint 3 — Ranking Diversity:
   Scores must use FULL 0-100 range. No clustering near same values.
   Decimal precision used to differentiate similar candidates.
   Senior vs intern scores must differ by >20 points.
   All candidates in a batch must have unique scores.

Constraint 4 — Role Detection:
   Design and marketing roles use specialized weighting formulas.
   Portfolio strength proxies design skill breadth.
   Impact score proxies marketing metric density.

Constraint 5 — Quality Does Not Dominate:
   Quality score hard-capped at 80/100.
   High-experience + low-quality resumes must not be underranked.
   High-quality + low-skill resumes must not be overranked.

Constraint 6 — OCR Noise & Keyword Stuffing:
   Pure punctuation lines removed.
   Repeated words (>3 consecutive identical) collapsed to single occurrence.
   Normal content (≤3 repetitions) must not be mangled.

Constraint 7 — Unicode & International Name Safety:
   Arabic, Urdu, accented Latin, CJK scripts preserved exactly.
   Control characters stripped. Replacement characters stripped.
   Name extraction must handle international names correctly.

TEST SUITE STRUCTURE (22 Test Classes, ~120+ Tests)
-------------------------------------------------
1.  Text Cleaning          — whitespace, control chars, Unicode preservation
2.  Regex Pre-pass           — email, phone (with date rejection), LinkedIn, Behance
3.  Experience Estimation    — range merging, overlapping, empty, confidence
4.  Scoring Helpers          — exp/skills scores, seniority map, safe_int parser
5.  Seniority Detection      — intern/junior/senior/lead/unknown signals
6.  Resume Quality Score     — full resume high score, empty zero, bounded 0-100
7.  Rule-Based Parse         — schema completeness, ranking formula consistency,
                               invalid text flagging, no crashes on minimal input
8.  Merge Results            — regex overrides, fallback experience, key renaming,
                               breakdown recomputation, score clamping
9.  LLM Call (mocked)        — valid JSON, markdown fence stripping, invalid JSON raises
10. Ranking Aggregator       — descending sort, rank field, empty list, error records
11. Full Pipeline (mocked)   — LLM mocked, required keys, Behance structure,
                               messy resume handling, extraction errors
12. Behance Scraper (mocked) — successful fetch, title extraction, absolute URLs,
                               HTTP errors, network errors, empty pages
13. Behance Pipeline Integration — fetch called when URL present, project reshaping,
                                   no URL status, disabled fetch, deterministic ranking
14. Edge Cases & Robustness  — score bounds, different resumes different scores,
                                valid seniority values, confidence bounds
15. Rate-Limit & Retry       — success first attempt, retries on 429, exhausted raises,
                               daily quota immediate fallback, capped waits,
                               growing waits, auth not retried, transient retried,
                               invalid JSON not retried, pipeline fallbacks
16. Unicode Safety            — Arabic, accented Latin, Urdu, control char stripping
17. Noise Handling            — punctuation lines, keyword stuffing, bullets
18. Role Detection            — design, marketing, general, mixed signals
19. Role-Weighted Scoring     — formula correctness, design ignores seniority,
                               rule-based parse uses correct weights
20. Quality Cap Constraint    — capped at 80, high-exp/low-quality not underranked,
                               high-quality/low-skill not overranked
21. Flat behance_url Field    — top-level presence, matches nested, None when absent
22. Ranking Diversity         — intern vs senior spread >20, unique scores,
                               full range spread >15
23. Trimmed Input Handling    — no headers parses, experience without job titles,
                               skills-only valid

CLI USAGE
-----------
  Single file:     python resume_parser.py --input resume.pdf
  Folder batch:    python resume_parser.py --input ./resumes/
  Rule-based only: python resume_parser.py --input ./resumes/ --no-llm
  Skip Behance:    python resume_parser.py --input ./resumes/ --no-behance
  API key:         export GROQ_API_KEY=gsk_...  OR  --api-key gsk_...

DEPENDENCIES
------------
Required (at least one PDF extractor):
  • pymupdf OR pdfplumber
Optional (for full functionality):
  • groq (LLM integration)
  • requests, beautifulsoup4 (Behance scraping)
  • pytesseract, pillow, pdf2image (OCR fallback)

================================================================================
                              END OF DOCUMENT
================================================================================
