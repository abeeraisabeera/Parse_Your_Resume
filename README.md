# Resume Parser & Evaluator
[![HF Space](https://img.shields.io/badge/HuggingFace-Space-yellow)](https://huggingface.co/spaces/abzyvantae/Parse_Your_Resume_Backend)
[![Vercel](https://img.shields.io/badge/Vercel-Deployed-black)]([https://your-project.vercel.app](https://web-sigma-flame-90.vercel.app/))
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/Tests-170%2B%20cases-brightgreen)]

> A production-grade PDF resume parser that extracts structured candidate data, scores resumes across multiple dimensions, and ranks applicants for recruitment pipelines.

---

## 🚀 Deployment

This system is deployed as a split production architecture.

### Backend (FastAPI Resume Parser)

* Hosted on Hugging Face Spaces (Docker)
* Handles PDF ingestion, OCR extraction, parsing, and scoring
* Exposes REST API endpoints for integration

Live Backend:
[https://huggingface.co/spaces/abzyvantae/Parse_Your_Resume_Backend](https://huggingface.co/spaces/abzyvantae/Parse_Your_Resume_Backend)

---

### Frontend (Candidate Dashboard)

* Hosted on Vercel
* Provides resume upload interface and ranking dashboard
* Consumes backend API for processing and data retrieval

Live Frontend:
[https://web-sigma-flame-90.vercel.app/](https://web-sigma-flame-90.vercel.app/)

---

### System Architecture

Frontend (Vercel)
│
▼
FastAPI Backend (Hugging Face Space)
│
├── OCR Engine (Tesseract / fallback)
├── Parsing Layer (regex + rule engine)
├── LLM Enrichment (Groq API)
│
▼
Neon PostgreSQL Database
│
▼
Ranked Candidate Store + Export Layer

---

### Deployment Notes

* Backend runs in a Docker container on Hugging Face Spaces
* Cold starts may occur after inactivity
* OCR requires Tesseract installed in runtime environment
* Frontend is stateless and depends on backend availability
* Database operations handled via Neon PostgreSQL

---

### Environment Breakdown

| Layer        | Platform            |
| ------------ | ------------------- |
| API Backend  | Hugging Face Spaces |
| Frontend UI  | Vercel              |
| Database     | Neon PostgreSQL     |
| LLM Provider | Groq API            |

---

## Features

| Feature                     | Description                                              |
| --------------------------- | -------------------------------------------------------- |
| Multi-engine PDF extraction | PyMuPDF → pdfplumber → OCR fallback chain                |
| Hybrid parsing              | Rule-based + LLM semantic analysis                       |
| Role-aware scoring          | Different weighting for design, marketing, general roles |
| Behance integration         | Portfolio enrichment for creative candidates             |
| Rate-limit resilient        | Retry logic with exponential backoff                     |
| Unicode-safe                | Supports multilingual resumes                            |
| OCR fallback                | Handles scanned documents                                |

---

## Quick Start

### Installation

```bash
pip install pymupdf requests beautifulsoup4 pytesseract pillow pdf2image groq
```

---

### Basic Usage

```bash
python resume_parser.py --input resume.pdf
python resume_parser.py --input ./resumes/
```

---

### API Service

```bash
uvicorn api_service:app --host 0.0.0.0 --port 8000
```

Endpoints:

* GET /healthz
* POST /parse
* POST /parse-batch
* GET /candidates
* PATCH /candidates/{id}/shortlist
* DELETE /candidates/{id}

---

## Output Schema

Each resume returns structured JSON:

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "skills": ["python", "sql", "docker"],
  "ranking_score": 72.5,
  "experience": 6.0,
  "seniority_level": "senior"
}
```

---

## Architecture Flow

PDF Input
↓
Text Extraction (PyMuPDF → pdfplumber → OCR)
↓
Cleaning & Normalization
↓
Regex Feature Extraction
↓
LLM + Rule-Based Parsing
↓
Scoring Engine
↓
Neon Database Storage
↓
API Response

---

## Scoring System

Experience, skills, seniority, and quality are combined into a weighted ranking score.

* Experience: nonlinear scaling
* Skills: count-based saturation curve
* Seniority: role inference mapping
* Quality: capped contribution to prevent bias

---

## Constraints

* OCR fallback used only when text extraction fails
* Ranking normalization prevents score clustering
* Unicode-safe parsing for international resumes
* Rate limiting handled via retry backoff

---

## Testing

120+ test cases covering:

* parsing accuracy
* OCR fallback
* scoring stability
* edge case handling
* API reliability

---


## License

ALL RIGHTS RESERVED.
Property of Digitalis Global.
Unauthorized reproduction, distribution, or modification is strictly prohibited.

Developer: Abeera Tahir
