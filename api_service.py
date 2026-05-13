from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

import candidate_store
import resume_parser as rp

DEFAULT_MODEL = "llama-3.1-8b-instant"
EXPORT_COLUMNS = ("Rank", "Name", "Email", "Role", "Overall Score", "Shortlisted")

app = FastAPI(
    title="Resume Parser API",
    version="1.0.0",
    description="HTTP wrapper around the resume parser pipeline.",
)


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "*").strip()
    if raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ShortlistUpdate(BaseModel):
    is_shortlisted: bool


def _build_groq_client() -> object | None:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or not rp.HAS_GROQ:
        return None
    return rp.Groq(api_key=api_key)


def _api_mode(client: object | None) -> str:
    return "llm" if client else "rule_based"


def _candidate_status(score: float | int | None) -> str:
    try:
        numeric = float(score or 0)
    except (TypeError, ValueError):
        return "error"
    if numeric >= 85:
        return "Shortlisted"
    if numeric >= 70:
        return "In Review"
    if numeric >= 50:
        return "Needs Review"
    return "New"


def _display_status(result: dict) -> str:
    if result.get("is_deleted"):
        return "Deleted"
    if result.get("is_shortlisted"):
        return "Shortlisted"
    return _candidate_status(result.get("overall_score", result.get("ranking_score")))


def _error_result(filename: str, detail: str, api_mode: str) -> dict:
    return {
        "uploaded_file_name": filename,
        "source_file": filename,
        "error": detail,
        "api_mode": api_mode,
        "candidate_status": "Error",
        "auto_shortlisted": False,
        "is_shortlisted": False,
        "is_deleted": False,
        "is_valid_resume": False,
        "ranking_score": 0.0,
        "estimated_years_of_experience": 0.0,
        "top_skills": [],
        "skills": [],
        "current_role": None,
        "companies_worked": [],
        "notes": detail,
        "skills_match_score": 0.0,
        "consistency_score": 0.0,
        "evidence_score": 0.0,
        "overall_score": 0.0,
    }


async def _write_upload_to_temp(upload: UploadFile) -> tuple[str, str]:
    filename = upload.filename or "resume.pdf"
    suffix = Path(filename).suffix.lower()
    if suffix != ".pdf":
        raise HTTPException(status_code=400, detail=f"{filename}: only PDF uploads are supported.")

    contents = await upload.read()
    if not contents:
        raise HTTPException(status_code=400, detail=f"{filename}: uploaded file is empty.")

    with NamedTemporaryFile(delete=False, suffix=".pdf") as handle:
        handle.write(contents)
        return handle.name, filename


def _parse_temp_resume(
    temp_path: str,
    filename: str,
    client: object | None,
    model: str,
    max_retries: int,
) -> dict:
    result = rp.parse_resume(
        temp_path,
        groq_client=client,
        fetch_behance=False,
        max_retries=max_retries,
        model=model or DEFAULT_MODEL,
    )
    result["uploaded_file_name"] = filename
    result["api_mode"] = _api_mode(client)
    result["auto_shortlisted"] = float(result.get("overall_score") or result.get("ranking_score") or 0) >= candidate_store.SHORTLIST_THRESHOLD
    result["is_shortlisted"] = bool(result.get("is_shortlisted", result["auto_shortlisted"]))
    result["is_deleted"] = False
    result["candidate_status"] = _display_status(result)
    return result


def _build_batch_summary(results: list[dict]) -> dict[str, float | int]:
    scores = [float(result.get("overall_score") or result.get("ranking_score") or 0.0) for result in results]
    experiences = [
        float(result.get("estimated_years_of_experience") or 0.0)
        for result in results
    ]
    valid_count = sum(1 for result in results if result.get("is_valid_resume", True))
    return {
        "total_candidates": len(results),
        "valid_candidates": valid_count,
        "shortlisted": sum(bool(result.get("is_shortlisted")) for result in results),
        "high_match": sum(score >= 75 for score in scores),
        "avg_match_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
        "avg_experience_years": round(sum(experiences) / len(experiences), 1) if experiences else 0.0,
    }


def _storage_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=503, detail=f"Candidate storage unavailable: {exc}")


def _save_result(result: dict, filename: str) -> dict:
    try:
        if result.get("is_valid_resume", True):
            return candidate_store.save_candidate(result, filename)
        return result
    except Exception as exc:  # keep parsing usable even if the DB is being configured
        result["storage_error"] = str(exc)
        return result


def _candidate_query(
    search: str = "",
    role: str = "all",
    shortlist: str = "all",
    min_score: float = 0.0,
    min_experience: float = 0.0,
    include_deleted: bool = False,
    limit: int = 500,
) -> list[dict]:
    try:
        return candidate_store.list_candidates(
            search=search,
            role=role,
            shortlist=shortlist,
            min_score=min_score,
            min_experience=min_experience,
            include_deleted=include_deleted,
            limit=limit,
        )
    except Exception as exc:
        raise _storage_error(exc) from exc


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Resume Parser API is running."}


@app.get("/healthz")
def healthz() -> dict[str, object]:
    ocr_status = rp.get_ocr_status()
    db_status = candidate_store.database_status()
    return {
        "ok": True,
        "llm_enabled": bool(os.environ.get("GROQ_API_KEY")) and rp.HAS_GROQ,
        "pdf_extractors_available": rp.HAS_FITZ or rp.HAS_PDFPLUMBER,
        "ocr_available": ocr_status["available"],
        "ocr_detail": ocr_status["detail"],
        "ocr_binary_path": ocr_status["binary_path"],
        "supports_batch_processing": True,
        "candidate_storage": db_status,
        "shortlist_threshold": candidate_store.SHORTLIST_THRESHOLD,
    }


@app.get("/candidates")
def list_stored_candidates(
    search: str = Query("", max_length=200),
    role: str = Query("all", max_length=64),
    shortlist: str = Query("all", pattern="^(all|shortlisted|not_shortlisted)$"),
    min_score: float = Query(0.0, ge=0, le=100),
    min_experience: float = Query(0.0, ge=0),
    include_deleted: bool = Query(False),
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    results = _candidate_query(
        search=search,
        role=role,
        shortlist=shortlist,
        min_score=min_score,
        min_experience=min_experience,
        include_deleted=include_deleted,
        limit=limit,
    )
    return {
        "mode": "stored",
        "summary": _build_batch_summary(results),
        "results": results,
    }


@app.patch("/candidates/{candidate_id}/shortlist")
def update_candidate_shortlist(candidate_id: str, payload: ShortlistUpdate) -> dict:
    try:
        candidate = candidate_store.set_shortlist(candidate_id, payload.is_shortlisted)
        return candidate
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Candidate not found.") from exc
    except Exception as exc:
        raise _storage_error(exc) from exc


@app.delete("/candidates/{candidate_id}")
def delete_candidate(candidate_id: str) -> dict:
    try:
        candidate = candidate_store.soft_delete_candidate(candidate_id)
        return {"ok": True, "candidate": candidate}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Candidate not found.") from exc
    except Exception as exc:
        raise _storage_error(exc) from exc


@app.get("/candidates/export.xlsx")
def export_candidates_xlsx(
    search: str = Query("", max_length=200),
    role: str = Query("all", max_length=64),
    shortlist: str = Query("all", pattern="^(all|shortlisted|not_shortlisted)$"),
    min_score: float = Query(0.0, ge=0, le=100),
    min_experience: float = Query(0.0, ge=0),
    include_deleted: bool = Query(False),
    limit: int = Query(100, ge=1, le=2000),
) -> StreamingResponse:
    try:
        from openpyxl import Workbook
    except ImportError as exc:  # pragma: no cover - dependency boundary
        raise HTTPException(status_code=503, detail="Install openpyxl to enable Excel export.") from exc

    results = _candidate_query(
        search=search,
        role=role,
        shortlist=shortlist,
        min_score=min_score,
        min_experience=min_experience,
        include_deleted=include_deleted,
        limit=limit,
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Top Candidates"
    sheet.append(EXPORT_COLUMNS)
    for candidate in results:
        score = float(candidate.get("overall_score") or candidate.get("ranking_score") or 0)
        sheet.append(
            [
                candidate.get("rank"),
                candidate.get("name") or "Unknown",
                candidate.get("email") or "",
                candidate.get("role_detected") or candidate.get("current_role") or "general",
                round(score, 1),
                "Yes" if candidate.get("is_shortlisted") else "No",
            ]
        )

    for column in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        sheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 42)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="top-ranked-candidates.xlsx"'}
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@app.post("/parse")
async def parse_uploaded_resume(
    file: UploadFile = File(...),
    use_llm: bool = Form(True),
    model: str = Form(DEFAULT_MODEL),
    max_retries: int = Form(6),
) -> dict:
    client = _build_groq_client() if use_llm else None
    temp_path: str | None = None
    try:
        temp_path, filename = await _write_upload_to_temp(file)
        result = _parse_temp_resume(temp_path, filename, client, model, max_retries)
        return _save_result(result, filename)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive API boundary
        raise HTTPException(status_code=500, detail=f"Failed to parse resume: {exc}") from exc
    finally:
        await file.close()
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink()


@app.post("/parse-batch")
async def parse_resume_batch(
    files: list[UploadFile] = File(...),
    use_llm: bool = Form(True),
    model: str = Form(DEFAULT_MODEL),
    max_retries: int = Form(6),
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF file is required.")

    client = _build_groq_client() if use_llm else None
    results: list[dict] = []
    for upload in files:
        temp_path: str | None = None
        filename = upload.filename or "resume.pdf"
        try:
            temp_path, filename = await _write_upload_to_temp(upload)
            parsed = _parse_temp_resume(temp_path, filename, client, model, max_retries)
            results.append(_save_result(parsed, filename))
        except HTTPException as exc:
            results.append(_error_result(filename, str(exc.detail), _api_mode(client)))
        except ValueError as exc:
            results.append(_error_result(filename, str(exc), _api_mode(client)))
        except RuntimeError as exc:
            results.append(_error_result(filename, str(exc), _api_mode(client)))
        except Exception as exc:  # pragma: no cover - defensive API boundary
            results.append(_error_result(filename, f"Failed to parse resume: {exc}", _api_mode(client)))
        finally:
            await upload.close()
            if temp_path and Path(temp_path).exists():
                Path(temp_path).unlink()

    ranked = rp.rank_candidates(results)
    return {
        "mode": "batch",
        "api_mode": _api_mode(client),
        "summary": _build_batch_summary(ranked),
        "results": ranked,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_service:app", host="127.0.0.1", port=8000, reload=True)
