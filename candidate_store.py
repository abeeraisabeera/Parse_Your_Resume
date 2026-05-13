from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

try:
    from sqlalchemy import (
        Boolean,
        Column,
        DateTime,
        Float,
        Integer,
        JSON,
        MetaData,
        String,
        Table,
        Text,
        create_engine,
        select,
        update,
    )
    from sqlalchemy.engine import Engine
except ImportError:  # pragma: no cover - reported through healthz
    Boolean = Column = DateTime = Float = Integer = JSON = MetaData = String = Table = Text = None
    create_engine = select = update = None
    Engine = Any


SHORTLIST_THRESHOLD = float(os.environ.get("SHORTLIST_THRESHOLD", "85"))
_ENGINE: Engine | None = None
_INIT_DONE = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _database_url() -> str:
    raw = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("RESUME_DATABASE_URL")
        or "sqlite:///./resume_rank.db"
    )
    if raw.startswith("postgres://"):
        return raw.replace("postgres://", "postgresql+psycopg://", 1)
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+psycopg://", 1)
    return raw


def database_status() -> dict[str, Any]:
    url = _database_url()
    configured = bool(
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("RESUME_DATABASE_URL")
    )
    return {
        "available": create_engine is not None,
        "configured": configured,
        "backend": "postgres" if url.startswith("postgresql") else "sqlite",
        "detail": None if create_engine else "Install sqlalchemy and psycopg to enable persistence.",
    }


metadata = MetaData() if MetaData else None

candidates = Table(
    "candidates",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(255), nullable=True),
    Column("email", String(255), nullable=True),
    Column("current_role", String(255), nullable=True),
    Column("role_detected", String(64), nullable=False, default="general"),
    Column("seniority_level", String(64), nullable=True),
    Column("ranking_score", Float, nullable=False, default=0.0),
    Column("overall_score", Float, nullable=False, default=0.0),
    Column("skills_match_score", Float, nullable=False, default=0.0),
    Column("consistency_score", Float, nullable=False, default=0.0),
    Column("estimated_years_of_experience", Float, nullable=False, default=0.0),
    Column("candidate_status", String(64), nullable=False, default="New"),
    Column("auto_shortlisted", Boolean, nullable=False, default=False),
    Column("is_shortlisted", Boolean, nullable=False, default=False),
    Column("is_deleted", Boolean, nullable=False, default=False),
    Column("resume_filename", String(512), nullable=True),
    Column("api_mode", String(64), nullable=True),
    Column("parsed_payload", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("deleted_at", DateTime(timezone=True), nullable=True),
) if metadata is not None else None


def get_engine() -> Engine:
    global _ENGINE
    if create_engine is None:
        raise RuntimeError("SQLAlchemy is not installed. Run pip install -r requirements.txt.")
    if _ENGINE is None:
        connect_args = {}
        url = _database_url()
        if url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _ENGINE = create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
    return _ENGINE


def init_db() -> None:
    global _INIT_DONE
    if _INIT_DONE:
        return
    if metadata is None:
        raise RuntimeError("SQLAlchemy is not installed. Run pip install -r requirements.txt.")
    metadata.create_all(get_engine())
    _INIT_DONE = True


def _score(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _status_for_candidate(score: float, is_shortlisted: bool, is_deleted: bool = False) -> str:
    if is_deleted:
        return "Deleted"
    if is_shortlisted:
        return "Shortlisted"
    if score >= 70:
        return "In Review"
    if score >= 50:
        return "Needs Review"
    return "New"


def _normalise_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    payload = dict(candidate)
    payload.setdefault("skills", [])
    payload.setdefault("top_skills", [])
    payload.setdefault("companies_worked", [])
    return payload


def save_candidate(candidate: dict[str, Any], filename: str | None = None) -> dict[str, Any]:
    init_db()
    payload = _normalise_payload(candidate)
    score = _score(payload.get("overall_score", payload.get("ranking_score")))
    ranking_score = _score(payload.get("ranking_score", score))
    auto_shortlisted = score >= SHORTLIST_THRESHOLD
    is_shortlisted = bool(payload.get("is_shortlisted", auto_shortlisted))
    now = _now()
    candidate_id = str(uuid.uuid4())
    status = _status_for_candidate(score, is_shortlisted)

    payload.update(
        {
            "id": candidate_id,
            "candidate_status": status,
            "auto_shortlisted": auto_shortlisted,
            "is_shortlisted": is_shortlisted,
            "is_deleted": False,
        }
    )

    row = {
        "id": candidate_id,
        "name": payload.get("name"),
        "email": payload.get("email"),
        "current_role": payload.get("current_role"),
        "role_detected": payload.get("role_detected") or "general",
        "seniority_level": payload.get("seniority_level"),
        "ranking_score": ranking_score,
        "overall_score": score,
        "skills_match_score": _score(payload.get("skills_match_score")),
        "consistency_score": _score(payload.get("consistency_score")),
        "estimated_years_of_experience": _score(payload.get("estimated_years_of_experience")),
        "candidate_status": status,
        "auto_shortlisted": auto_shortlisted,
        "is_shortlisted": is_shortlisted,
        "is_deleted": False,
        "resume_filename": filename or payload.get("uploaded_file_name") or payload.get("source_file"),
        "api_mode": payload.get("api_mode"),
        "parsed_payload": payload,
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
    }

    with get_engine().begin() as conn:
        conn.execute(candidates.insert().values(**row))
    return row_to_candidate(row)


def _row_to_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


def row_to_candidate(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("parsed_payload") or {}
    if isinstance(payload, str):
        payload = json.loads(payload)
    result = dict(payload)
    for key in (
        "id",
        "name",
        "email",
        "current_role",
        "role_detected",
        "seniority_level",
        "ranking_score",
        "overall_score",
        "skills_match_score",
        "consistency_score",
        "estimated_years_of_experience",
        "candidate_status",
        "auto_shortlisted",
        "is_shortlisted",
        "is_deleted",
        "resume_filename",
        "api_mode",
        "created_at",
        "updated_at",
        "deleted_at",
    ):
        value = row.get(key)
        if isinstance(value, datetime):
            value = value.isoformat()
        result[key] = value
    result["uploaded_file_name"] = result.get("uploaded_file_name") or row.get("resume_filename")
    return result


def _matches_query(candidate: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        str(value)
        for value in [
            candidate.get("name"),
            candidate.get("email"),
            candidate.get("current_role"),
            candidate.get("role_detected"),
            candidate.get("resume_filename"),
            *(candidate.get("skills") or []),
            *(candidate.get("top_skills") or []),
        ]
        if value
    ).lower()
    return query.lower() in haystack


def _normalise_filter_terms(value: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        raw_terms = re.split(r"[,;]", value)
    else:
        raw_terms = []
        for item in value:
            raw_terms.extend(re.split(r"[,;]", str(item)))
    return [term.strip().lower() for term in raw_terms if term.strip()]


def _matches_skills(candidate: dict[str, Any], skills_filter: str | list[str] | None) -> bool:
    required = _normalise_filter_terms(skills_filter)
    if not required:
        return True
    candidate_skills = {
        str(skill).lower()
        for skill in [
            *(candidate.get("skills") or []),
            *(candidate.get("top_skills") or []),
        ]
        if skill
    }
    return all(
        any(required_skill in skill or skill in required_skill for skill in candidate_skills)
        for required_skill in required
    )


def list_candidates(
    search: str = "",
    role: str = "all",
    skills: str | list[str] | None = None,
    shortlist: str = "all",
    min_score: float = 0.0,
    min_experience: float = 0.0,
    include_deleted: bool = False,
    limit: int = 500,
) -> list[dict[str, Any]]:
    init_db()
    stmt = select(candidates).order_by(candidates.c.overall_score.desc(), candidates.c.created_at.desc())
    with get_engine().connect() as conn:
        rows = [_row_to_dict(row) for row in conn.execute(stmt).fetchall()]

    results: list[dict[str, Any]] = []
    for row in rows:
        candidate = row_to_candidate(row)
        if not include_deleted and candidate.get("is_deleted"):
            continue
        if role != "all" and candidate.get("role_detected") != role:
            continue
        if not _matches_skills(candidate, skills):
            continue
        if shortlist == "shortlisted" and not candidate.get("is_shortlisted"):
            continue
        if shortlist == "not_shortlisted" and candidate.get("is_shortlisted"):
            continue
        if _score(candidate.get("overall_score", candidate.get("ranking_score"))) < min_score:
            continue
        if _score(candidate.get("estimated_years_of_experience")) < min_experience:
            continue
        if not _matches_query(candidate, search):
            continue
        results.append(candidate)
        if len(results) >= limit:
            break

    for index, candidate in enumerate(results, start=1):
        candidate["rank"] = index
    return results


def set_shortlist(candidate_id: str, is_shortlisted: bool) -> dict[str, Any]:
    init_db()
    now = _now()
    with get_engine().begin() as conn:
        existing = conn.execute(select(candidates).where(candidates.c.id == candidate_id)).first()
        if not existing:
            raise KeyError(candidate_id)
        row = _row_to_dict(existing)
        score = _score(row.get("overall_score", row.get("ranking_score")))
        status = _status_for_candidate(score, is_shortlisted, bool(row.get("is_deleted")))
        payload = row.get("parsed_payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        payload.update({"is_shortlisted": is_shortlisted, "candidate_status": status})
        conn.execute(
            update(candidates)
            .where(candidates.c.id == candidate_id)
            .values(
                is_shortlisted=is_shortlisted,
                candidate_status=status,
                parsed_payload=payload,
                updated_at=now,
            )
        )
        updated = conn.execute(select(candidates).where(candidates.c.id == candidate_id)).first()
    return row_to_candidate(_row_to_dict(updated))


def soft_delete_candidate(candidate_id: str) -> dict[str, Any]:
    init_db()
    now = _now()
    with get_engine().begin() as conn:
        existing = conn.execute(select(candidates).where(candidates.c.id == candidate_id)).first()
        if not existing:
            raise KeyError(candidate_id)
        row = _row_to_dict(existing)
        payload = row.get("parsed_payload") or {}
        if isinstance(payload, str):
            payload = json.loads(payload)
        payload.update({"is_deleted": True, "candidate_status": "Deleted"})
        conn.execute(
            update(candidates)
            .where(candidates.c.id == candidate_id)
            .values(
                is_deleted=True,
                candidate_status="Deleted",
                parsed_payload=payload,
                updated_at=now,
                deleted_at=now,
            )
        )
        updated = conn.execute(select(candidates).where(candidates.c.id == candidate_id)).first()
    return row_to_candidate(_row_to_dict(updated))
