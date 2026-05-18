"use client";

import Link from "next/link";

import {
  formatPercent,
  getInitials,
  getOverallScore,
  roleLabel,
  statusClassName
} from "../../lib/candidateUtils";
import { ScoreBadge } from "../common/ScoreBadge";

const STAGES = [
  { key: "New", label: "New" },
  { key: "Needs Review", label: "Needs Review" },
  { key: "In Review", label: "In Review" },
  { key: "Shortlisted", label: "Shortlisted" }
];

export function PipelineKanban({ workspace }) {
  const { filteredCandidates } = workspace;

  const columns = STAGES.map((stage) => ({
    ...stage,
    items: filteredCandidates.filter(
      (candidate) => !candidate.is_deleted && (candidate.candidate_status || "New") === stage.key
    )
  }));

  const uncategorized = filteredCandidates.filter(
    (candidate) =>
      !candidate.is_deleted &&
      !STAGES.some((stage) => (candidate.candidate_status || "New") === stage.key)
  );

  if (uncategorized.length) {
    columns.push({ key: "other", label: "Other", items: uncategorized });
  }

  return (
    <div className="pageGrid">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Pipeline</p>
          <h1 className="pageTitle">Hiring Pipeline</h1>
          <p className="subtle">
            Kanban view of candidates by ATS status. Drag-and-drop stages coming soon — use Candidates for full actions.
          </p>
        </div>
        <Link className="button compactButton" href="/candidates">
          Review Queue
        </Link>
      </section>

      <section className="kanbanBoard" aria-label="Candidate pipeline board">
        {columns.map((column) => (
          <article key={column.key} className="kanbanColumn">
            <header className="kanbanColumnHeader">
              <h2>{column.label}</h2>
              <span className="kanbanCount">{column.items.length}</span>
            </header>
            <div className="kanbanCards">
              {column.items.length ? (
                column.items.map((candidate) => (
                  <div key={candidate.id || candidate.uploaded_file_name} className="kanbanCard">
                    <div className="candidateIdentity">
                      <em>{getInitials(candidate.name)}</em>
                      <span>
                        <strong>{candidate.name || "Unknown"}</strong>
                        <small className="candidateMeta">{roleLabel(candidate.role_detected)}</small>
                      </span>
                    </div>
                    <ScoreBadge score={getOverallScore(candidate)} />
                    <div className="docMeta">
                      {(candidate.top_skills || []).slice(0, 3).map((skill) => (
                        <span key={skill}>{skill}</span>
                      ))}
                    </div>
                    <p className="kanbanMeta">
                      {candidate.estimated_years_of_experience || 0} yrs ·{" "}
                      <span className={`statusDot statusDot--${statusClassName(candidate.candidate_status)}`} />
                      {candidate.candidate_status || "New"}
                    </p>
                  </div>
                ))
              ) : (
                <p className="emptyState">No candidates in this stage.</p>
              )}
            </div>
          </article>
        ))}
      </section>
    </div>
  );
}
