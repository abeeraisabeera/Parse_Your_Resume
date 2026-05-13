# Resume Parser & Evaluator

> A production-grade PDF resume parser that extracts structured candidate data, scores resumes across multiple dimensions, and ranks applicants for recruitment pipelines.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-120%2B%20cases-brightgreen)]()

---

## Features

| Feature | Description |
|---------|-------------|
 **Multi-engine PDF extraction** | PyMuPDF → pdfplumber → OCR fallback chain |
 **Hybrid parsing** | Deterministic regex + LLM semantic analysis |
 **Role-aware scoring** | Design, Marketing, and General weighting formulas |
 **Behance integration** | Automatic portfolio scraping for creative candidates |
 **Rate-limit resilient** | Exponential backoff with daily quota detection |
 **Unicode-safe** | Full support for Arabic, Urdu, accented Latin, CJK |
 **OCR noise resistant** | Handles scanned documents and keyword stuffing |

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/abeeraisabeera/Parse_Your_Resume.git
cd resume-parser

# Install dependencies
pip install pymupdf requests beautifulsoup4

# Optional: LLM support (free tier, no credit card)
pip install groq

# Optional: OCR fallback for scanned PDFs
pip install pytesseract pillow pdf2image
```

### Basic Usage

```bash
# Single resume (rule-based, no API key needed)
python resume_parser.py --input resume.pdf

# Batch process a folder
python resume_parser.py --input ./resumes/ --output results.json

# With LLM enhancement (requires GROQ_API_KEY)
export GROQ_API_KEY="gsk_..."
python resume_parser.py --input ./resumes/
```

### API Service

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start the FastAPI wrapper
uvicorn api_service:app --reload
```

Available endpoints:

- `GET /healthz` for health checks
- `POST /parse` for multipart PDF uploads
- `POST /parse-batch` for batch PDF uploads and ranking

OCR notes:

- The parser now attempts OCR when extracted text is blank or clearly low-quality.
- Install the native Tesseract binary on the API host to enable scanned-PDF support.
- If Tesseract is not installed, `/healthz` will report OCR as unavailable.

### Web App

```bash
cd web
cp .env.example .env.local
npm install
npm run dev
```

The Next.js app supports both single and batch uploads, shows ranked candidates
in a dashboard-style UI, and proxies requests through:

- `/api/parse` for single or batch resume uploads
- `/api/healthz` for backend capability checks

For local development, leave `PARSER_API_URL` pointed at
`http://127.0.0.1:8000/parse`. For Vercel, deploy the `web` directory as the
project root and set `PARSER_API_URL` to your deployed parser API.

### Programmatic Usage

```python
from resume_parser import parse_resume

# Rule-based parsing (no API key required)
result = parse_resume("candidate.pdf", groq_client=None)

print(result["name"])           # "John Doe"
print(result["ranking_score"])  # 78.5
print(result["skills"])         # ["python", "django", "postgresql", ...]
```

---

## Output Schema

Every parsed resume returns a standardized JSON structure:

```json
{
  "is_valid_resume": true,
  "name": "John Doe",
  "email": "john.doe@example.com",
  "phone": "+1-555-123-4567",
  "linkedin": "linkedin.com/in/johndoe",
  "estimated_years_of_experience": 6.0,
  "experience_confidence": 0.7,
  "skills": ["python", "django", "postgresql", "docker", "aws"],
  "top_skills": ["python", "django", "postgresql", "docker", "aws"],
  "current_role": "Senior Software Engineer",
  "seniority_level": "senior",
  "role_detected": "general",
  "companies_worked": ["Acme Corp", "Beta Systems"],
  "education": "B.Sc. Computer Science - MIT, 2015",
  "resume_quality_score": 80,
  "ranking_score": 72.5,
  "ranking_breakdown": {
    "experience_score": 65.0,
    "skills_score": 60.0,
    "seniority_score": 70.0,
    "quality_score": 60.0
  },
  "behance": {
    "url": null,
    "projects": [],
    "project_count": 0,
    "fetch_status": "no_url",
    "error": null
  },
  "behance_url": null,
  "notes": "Rule-based parse (no LLM). Role=general. Seniority=senior.",
  "source_file": "resume.pdf",
  "rank": 1
}
```

---

## Scoring Methodology

### Experience Score (Non-linear)

| Years | Score |
|-------|-------|
| 0 | 0 |
| 1 | 15 |
| 2 | 25 |
| 3 | 35 |
| 5 | 50 |
| 8 | 65 |
| 10 | 75 |
| 15 | 85 |
| 20+ | 95 |

### Skills Score

| Skill Count | Score |
|-------------|-------|
| 0 | 0 |
| 1–3 | 20 |
| 4–6 | 40 |
| 7–10 | 60 |
| 11–15 | 75 |
| 16+ | 90 |

### Seniority Score

| Level | Score |
|-------|-------|
| Intern | 10 |
| Junior | 30 |
| Mid | 50 |
| Senior | 70 |
| Lead | 90 |
| Unknown | 30 |

### Role-Weighted Ranking Formula

| Role | Weights |
|------|---------|
| **General** | Experience(40%) + Skills(30%) + Seniority(20%) + Quality(10%) |
| **Design** | Portfolio(35%) + Skills(30%) + Experience(20%) + Quality(15%) |
| **Marketing** | Impact(35%) + Skills(30%) + Experience(20%) + Quality(15%) |

> **Quality Score is hard-capped at 80/100** so presentation quality never dominates actual capability.

---

## Architecture

```
PDF Input
    │
    ▼
┌─────────────────┐
│  Text Extraction │  ← PyMuPDF → pdfplumber → OCR
│   (3-tier fallback)│
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Text Cleaning   │  ← Unicode-safe, OCR noise removal
└─────────────────┘
    │
    ▼
┌─────────────────┐
│  Regex Pre-pass  │  ← Email, phone, LinkedIn, Behance, dates
└─────────────────┘
    │
    ├──────────────┬──────────────┐
    ▼              ▼              ▼
┌────────┐   ┌────────────┐   ┌─────────────┐
│  LLM    │   │ Rule-Based │   │  Behance    │
│ (Groq)  │   │  Fallback  │   │  Scraper    │
└────────┘   └────────────┘   └─────────────┘
    │              │              │
    └──────────────┴──────────────┘
                   │
                   ▼
          ┌──────────────┐
          │ Merge & Rank │  ← Schema guarantee, score clamping
          └──────────────┘
                   │
                   ▼
              JSON Output
```

---

## Testing

The project includes a comprehensive test suite with **120+ test cases** covering edge cases, error handling, and constraint validation.

```bash
# Run all tests
python test_resume_parser.py

# Verbose output
python test_resume_parser.py -v
```

### Test Coverage Areas

- **Text Cleaning** — Unicode preservation, control character stripping, noise removal
- **Regex Accuracy** — Phone/date disambiguation, URL normalization
- **Experience Estimation** — Range merging, overlapping intervals, confidence scoring
- **Scoring Formulas** — Non-linear interpolation, boundary conditions
- **Seniority Detection** — Title-based classification
- **Role Detection** — Design vs. marketing vs. general signal detection
- **Rate-Limit Handling** — Exponential backoff, daily quota detection, retry exhaustion
- **Behance Scraping** — HTML parsing, error handling, empty pages
- **Edge Cases** — Empty input, minimal resumes, invalid documents
- **Constraint Validation** — Quality caps, ranking diversity, Unicode safety

---

## Constraints & Design Decisions

| Constraint | Rationale |
|------------|-----------|
| **Trimmed input support** | Resumes may come from ATS systems that strip headers |
| **Ranking diversity** | Scores must span full 0–100 range; no clustering |
| **Role detection** | Design/marketing candidates need portfolio/impact weighting |
| **Quality cap (80)** | Prevents polished but empty resumes from outranking strong candidates |
| **OCR noise suppression** | Handles scanned documents and keyword-stuffed resumes |
| **Unicode safety** | Supports international candidates (Arabic, Urdu, CJK, accented Latin) |

---

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | API key for LLM enhancement | No (falls back to rule-based) |

### CLI Arguments

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | *required* | Path to PDF file or directory |
| `--output, -o` | `parsed_resumes.json` | Output JSON file |
| `--api-key` | `None` | Groq API key (or use env var) |
| `--no-llm` | `False` | Skip LLM; use rule-based only |
| `--no-behance` | `False` | Skip Behance portfolio fetching |
| `--model` | `llama-3.3-70b-versatile` | Groq model name |
| `--delay` | `8.0` | Seconds between LLM calls (rate limiting) |
| `--retries` | `4` | Max retries on rate-limit errors |

---

## Dependencies

### Required (at least one PDF extractor)
- `pymupdf` **or** `pdfplumber`

### Optional
- `groq` — LLM integration
- `requests`, `beautifulsoup4` — Behance scraping
- `pytesseract`, `pillow`, `pdf2image` — OCR fallback

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass: `python test_resume_parser.py`
2. New features include corresponding test cases
3. Code follows existing style and documentation patterns

---

## Acknowledgments

- LLM parsing powered by [Groq](https://groq.com) (free tier)
- PDF extraction via [PyMuPDF](https://pymupdf.readthedocs.io/) and [pdfplumber](https://github.com/jsvine/pdfplumber)
