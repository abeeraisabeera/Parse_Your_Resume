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
        delete,
        select,
        update,
    )
    from sqlalchemy.engine import Engine
except ImportError:  # pragma: no cover - reported through healthz
    Boolean = Column = DateTime = Float = Integer = JSON = MetaData = String = Table = Text = None
    create_engine = delete = select = update = None
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

role_definitions = Table(
    "role_definitions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("label", String(255), nullable=False),
    Column("short_label", String(120), nullable=True),
    Column("category", String(120), nullable=True),
    Column("description", Text, nullable=True),
    Column("is_custom", Boolean, nullable=False, default=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
) if metadata is not None else None

skill_taxonomy = Table(
    "skill_taxonomy",
    metadata,
    Column("id", String(120), primary_key=True),
    Column("label", String(255), nullable=False),
    Column("category", String(120), nullable=False, default="Uncategorized"),
    Column("aliases", JSON, nullable=False),
    Column("roles", JSON, nullable=False),
    Column("is_custom", Boolean, nullable=False, default=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
) if metadata is not None else None

DEFAULT_ROLE_DEFINITIONS = [
    {"id": "frontend", "label": "Frontend Developer", "short_label": "Frontend", "category": "Engineering"},
    {"id": "backend", "label": "Backend Developer", "short_label": "Backend", "category": "Engineering"},
    {"id": "fullstack", "label": "Fullstack Developer", "short_label": "Fullstack", "category": "Engineering"},
    {"id": "data", "label": "Data Scientist / BI", "short_label": "Data", "category": "Data / AI"},
    {"id": "devops", "label": "DevOps / Cloud", "short_label": "DevOps", "category": "Infrastructure"},
    {"id": "qa", "label": "QA / Testing", "short_label": "QA", "category": "Quality"},
    {"id": "design", "label": "UI/UX Designer", "short_label": "Design", "category": "Creative"},
    {"id": "marketing", "label": "Marketing", "short_label": "Marketing", "category": "Growth"},
    {"id": "hr", "label": "Human Resources", "short_label": "HR", "category": "Operations"},
    {"id": "sales", "label": "Sales", "short_label": "Sales", "category": "Revenue"},
    {"id": "product", "label": "Product Manager", "short_label": "Product", "category": "Product"},
    {"id": "general", "label": "General", "short_label": "General", "category": "General"},
]

DEFAULT_SKILL_TAXONOMY = [
    {"id": "react", "label": "React", "category": "Frontend", "roles": ["frontend", "fullstack"]},
    {"id": "next.js", "label": "Next.js", "category": "Frontend", "roles": ["frontend", "fullstack"]},
    {"id": "typescript", "label": "TypeScript", "category": "Frontend", "roles": ["frontend", "fullstack"]},
    {"id": "javascript", "label": "JavaScript", "category": "Frontend", "roles": ["frontend", "fullstack"]},
    {"id": "python", "label": "Python", "category": "Backend", "roles": ["backend", "data"]},
    {"id": "fastapi", "label": "FastAPI", "category": "Backend", "roles": ["backend"]},
    {"id": "postgresql", "label": "PostgreSQL", "category": "Backend", "roles": ["backend", "data"]},
    {"id": "docker", "label": "Docker", "category": "DevOps", "roles": ["devops", "backend"]},
    {"id": "kubernetes", "label": "Kubernetes", "category": "DevOps", "roles": ["devops"]},
    {"id": "sql", "label": "SQL", "category": "Data / AI", "roles": ["data", "backend"]},
    {"id": "pandas", "label": "Pandas", "category": "Data / AI", "roles": ["data"]},
    {"id": "pytorch", "label": "PyTorch", "category": "Data / AI", "roles": ["data"]},
    {"id": "figma", "label": "Figma", "category": "Design", "roles": ["design"]},
    {"id": "design systems", "label": "Design Systems", "category": "Design", "roles": ["design", "frontend"]},
    {"id": "seo", "label": "SEO", "category": "Marketing", "roles": ["marketing"]},
    {"id": "google analytics", "label": "Google Analytics", "category": "Marketing", "roles": ["marketing"]},
]


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
    _seed_taxonomy()
    _INIT_DONE = True


def _seed_taxonomy() -> None:
    if role_definitions is None or skill_taxonomy is None:
        return
    now = _now()
    with get_engine().begin() as conn:
        existing_roles = {row.id for row in conn.execute(select(role_definitions.c.id)).fetchall()}
        for role in DEFAULT_ROLE_DEFINITIONS:
            if role["id"] in existing_roles:
                continue
            conn.execute(
                role_definitions.insert().values(
                    id=role["id"],
                    label=role["label"],
                    short_label=role.get("short_label"),
                    category=role.get("category"),
                    description=role.get("description"),
                    is_custom=False,
                    created_at=now,
                    updated_at=now,
                )
            )

        existing_skills = {row.id for row in conn.execute(select(skill_taxonomy.c.id)).fetchall()}
        for skill in DEFAULT_SKILL_TAXONOMY:
            if skill["id"] in existing_skills:
                continue
            conn.execute(
                skill_taxonomy.insert().values(
                    id=skill["id"],
                    label=skill["label"],
                    category=skill.get("category") or "Uncategorized",
                    aliases=skill.get("aliases") or [],
                    roles=skill.get("roles") or [],
                    is_custom=False,
                    created_at=now,
                    updated_at=now,
                )
            )


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


def _taxonomy_row(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for key in ("created_at", "updated_at"):
        value = result.get(key)
        if isinstance(value, datetime):
            result[key] = value.isoformat()
    for key in ("aliases", "roles"):
        value = result.get(key)
        if isinstance(value, str):
            result[key] = json.loads(value)
        elif value is None:
            result[key] = []
    return result


def list_roles(include_custom: bool = True) -> list[dict[str, Any]]:
    init_db()
    stmt = select(role_definitions).order_by(role_definitions.c.label.asc())
    with get_engine().connect() as conn:
        rows = [_taxonomy_row(_row_to_dict(row)) for row in conn.execute(stmt).fetchall()]
    if include_custom:
        return rows
    return [row for row in rows if not row.get("is_custom")]


def upsert_role(role: dict[str, Any]) -> dict[str, Any]:
    init_db()
    role_id = str(role.get("id") or "").strip().lower()
    label = str(role.get("label") or "").strip()
    if not role_id or not label:
        raise ValueError("Role id and label are required.")
    now = _now()
    values = {
        "id": role_id,
        "label": label,
        "short_label": role.get("short_label") or role.get("shortLabel") or label,
        "category": role.get("category") or "Custom",
        "description": role.get("description"),
        "is_custom": bool(role.get("is_custom", role.get("isCustom", True))),
        "updated_at": now,
    }
    with get_engine().begin() as conn:
        existing = conn.execute(select(role_definitions).where(role_definitions.c.id == role_id)).first()
        if existing:
            conn.execute(
                update(role_definitions)
                .where(role_definitions.c.id == role_id)
                .values(**values)
            )
        else:
            conn.execute(role_definitions.insert().values(**values, created_at=now))
        updated = conn.execute(select(role_definitions).where(role_definitions.c.id == role_id)).first()
    return _taxonomy_row(_row_to_dict(updated))


def delete_role(role_id: str) -> None:
    init_db()
    with get_engine().begin() as conn:
        existing = conn.execute(select(role_definitions).where(role_definitions.c.id == role_id)).first()
        if not existing:
            raise KeyError(role_id)
        row = _row_to_dict(existing)
        if not row.get("is_custom"):
            raise ValueError("Default roles cannot be deleted.")
        conn.execute(delete(role_definitions).where(role_definitions.c.id == role_id))


def list_skills(search: str = "", role: str = "all") -> list[dict[str, Any]]:
    init_db()
    stmt = select(skill_taxonomy).order_by(skill_taxonomy.c.category.asc(), skill_taxonomy.c.label.asc())
    with get_engine().connect() as conn:
        rows = [_taxonomy_row(_row_to_dict(row)) for row in conn.execute(stmt).fetchall()]
    query = search.strip().lower()
    results: list[dict[str, Any]] = []
    for skill in rows:
        if role != "all" and role not in (skill.get("roles") or []):
            continue
        if query:
            haystack = " ".join(
                str(value)
                for value in [
                    skill.get("id"),
                    skill.get("label"),
                    skill.get("category"),
                    *(skill.get("aliases") or []),
                    *(skill.get("roles") or []),
                ]
                if value
            ).lower()
            if query not in haystack:
                continue
        results.append(skill)
    return results


def upsert_skill(skill: dict[str, Any]) -> dict[str, Any]:
    init_db()
    skill_id = str(skill.get("id") or skill.get("label") or "").strip().lower()
    label = str(skill.get("label") or skill.get("name") or "").strip()
    if not skill_id or not label:
        raise ValueError("Skill id and label are required.")
    aliases = skill.get("aliases") or []
    roles = skill.get("roles") or []
    if not isinstance(aliases, list):
        aliases = [str(item).strip() for item in str(aliases).split(",") if str(item).strip()]
    if not isinstance(roles, list):
        roles = [str(item).strip() for item in str(roles).split(",") if str(item).strip()]
    now = _now()
    values = {
        "id": skill_id,
        "label": label,
        "category": skill.get("category") or "Uncategorized",
        "aliases": aliases,
        "roles": roles,
        "is_custom": bool(skill.get("is_custom", skill.get("isCustom", True))),
        "updated_at": now,
    }
    with get_engine().begin() as conn:
        existing = conn.execute(select(skill_taxonomy).where(skill_taxonomy.c.id == skill_id)).first()
        if existing:
            existing_row = _row_to_dict(existing)
            values["is_custom"] = bool(existing_row.get("is_custom", values["is_custom"]))
            conn.execute(
                update(skill_taxonomy)
                .where(skill_taxonomy.c.id == skill_id)
                .values(**values)
            )
        else:
            conn.execute(skill_taxonomy.insert().values(**values, created_at=now))
        updated = conn.execute(select(skill_taxonomy).where(skill_taxonomy.c.id == skill_id)).first()
    return _taxonomy_row(_row_to_dict(updated))


def delete_skill(skill_id: str) -> None:
    init_db()
    with get_engine().begin() as conn:
        existing = conn.execute(select(skill_taxonomy).where(skill_taxonomy.c.id == skill_id)).first()
        if not existing:
            raise KeyError(skill_id)
        conn.execute(delete(skill_taxonomy).where(skill_taxonomy.c.id == skill_id))
