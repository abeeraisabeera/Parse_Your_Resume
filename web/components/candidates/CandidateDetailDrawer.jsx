"use client";

import { useState } from "react";

import {
  candidateMissingSkills,
  formatPercent,
  getConsistencyScore,
  getEvidenceScore,
  getInitials,
  getOverallScore,
  getSkillsMatchScore,
  roleConfidence,
  roleLabel
} from "../../lib/candidateUtils";
import { StatusBadge } from "../common/StatusBadge";

function DetailMetric({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export function CandidateDetailDrawer({
  candidate,
  skills,
  open,
  onClose,
  onToggleShortlist,
  onDelete,
  actionLoading
}) {
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  if (!open || !candidate) return null;

  const missingSkills = candidateMissingSkills(candidate, skills);
  const breakdown = candidate.ranking_breakdown || {};

  function downloadCandidateProfile() {
    const blob = new Blob([JSON.stringify(candidate, null, 2)], {
      type: "application/json"
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${candidate.name || candidate.id || "candidate"}-profile.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="drawerOverlay" role="dialog" aria-modal="true" aria-label="Candidate profile">
      <button className="drawerScrim" type="button" onClick={onClose} aria-label="Close candidate profile" />
      <aside className="candidateDrawer">
        <div className="drawerHeader">
          <div className="candidateHero">
            <div className="avatar">{getInitials(candidate.name)}</div>
            <div>
              <p className="eyebrow">{roleLabel(candidate.role_detected)}</p>
              <h2>{candidate.name || "Candidate Profile"}</h2>
              <p className="subtle">{candidate.current_role || "Current role unavailable"}</p>
              <p className="candidateMeta">{candidate.email || "Email not extracted"}</p>
            </div>
          </div>
          <button className="secondaryButton" type="button" onClick={onClose}>Close</button>
        </div>

        <div className="detailActions stickyActions">
          <StatusBadge status={candidate.candidate_status} />
          <button
            className="secondaryButton"
            type="button"
            onClick={() => onToggleShortlist(candidate)}
            disabled={actionLoading === "shortlist" || candidate.is_deleted}
          >
            {candidate.is_shortlisted ? "Unshortlist" : "Shortlist"}
          </button>
          <button className="secondaryButton" type="button" onClick={downloadCandidateProfile}>
            Export Profile
          </button>
          <button
            className="dangerButton"
            type="button"
            onClick={() => setConfirmingDelete(true)}
            disabled={actionLoading === "delete" || candidate.is_deleted}
          >
            Delete
          </button>
        </div>

        {confirmingDelete ? (
          <section className="deleteConfirmPanel" role="alertdialog" aria-label="Confirm candidate deletion">
            <div>
              <h3>Delete this candidate?</h3>
              <p className="subtle">
                This will remove {candidate.name || "this candidate"} from the active list. You can still show deleted resumes from filters.
              </p>
            </div>
            <div className="tableActions">
              <button className="secondaryButton" type="button" onClick={() => setConfirmingDelete(false)}>
                Cancel
              </button>
              <button
                className="dangerButton"
                type="button"
                onClick={() => {
                  setConfirmingDelete(false);
                  onDelete(candidate, { skipConfirm: true });
                }}
                disabled={actionLoading === "delete"}
              >
                Confirm Delete
              </button>
            </div>
          </section>
        ) : null}

        <section className="detailStats">
          <DetailMetric label="ATS Score" value={formatPercent(getOverallScore(candidate))} />
          <DetailMetric label="Skills Match" value={formatPercent(getSkillsMatchScore(candidate))} />
          <DetailMetric label="Consistency" value={formatPercent(getConsistencyScore(candidate))} />
          <DetailMetric label="Evidence" value={formatPercent(getEvidenceScore(candidate))} />
          <DetailMetric label="Experience" value={`${candidate.estimated_years_of_experience || 0} yrs`} />
          <DetailMetric label="Role Confidence" value={formatPercent(roleConfidence(candidate))} />
        </section>

        <section className="profileGrid">
          <article className="detailCardBlock">
            <h3>Resume Preview</h3>
            <div className="docSheet compactDoc">
              <div className="docTitle">{candidate.uploaded_file_name || candidate.source_file || "Resume file"}</div>
              <p className="subtle">{candidate.notes || "No analysis summary generated."}</p>
              <div className="docMeta">
                {(candidate.top_skills || []).slice(0, 5).map((skill) => (
                  <span key={skill}>{skill}</span>
                ))}
              </div>
            </div>
          </article>

          <article className="detailCardBlock">
            <h3>Role Assignment</h3>
            <ul className="bulletList">
              <li>Primary role: <strong>{roleLabel(candidate.role_detected || "general")}</strong></li>
              <li>Secondary roles: <strong>{(candidate.secondary_roles || []).join(", ") || "None assigned"}</strong></li>
              <li>Seniority: <strong>{candidate.seniority_level || "unknown"}</strong></li>
              <li>Confidence: <strong>{formatPercent(roleConfidence(candidate))}</strong></li>
            </ul>
          </article>

          <article className="detailCardBlock">
            <h3>Skills Breakdown</h3>
            <ul className="chips">
              {(candidate.skills || candidate.top_skills || []).length ? (
                (candidate.skills || candidate.top_skills || []).map((skill) => (
                  <li className="chip" key={skill}>{skill}</li>
                ))
              ) : (
                <li className="chip mutedChip">No skills extracted</li>
              )}
            </ul>
          </article>

          <article className="detailCardBlock">
            <h3>Missing Skills / Gaps</h3>
            <ul className="chips">
              {missingSkills.length ? (
                missingSkills.map((skill) => <li className="chip warningChip" key={skill}>{skill}</li>)
              ) : (
                <li className="chip successChip">No mapped role gaps detected</li>
              )}
            </ul>
          </article>

          <article className="detailCardBlock">
            <h3>Experience Timeline</h3>
            <ul className="timelineList">
              {(candidate.companies_worked || []).length ? (
                candidate.companies_worked.map((company) => (
                  <li key={company}>
                    <strong>{company}</strong>
                    <span>{candidate.current_role || "Role extracted from resume"}</span>
                  </li>
                ))
              ) : (
                <li><strong>No company history extracted.</strong><span>Parser returned no company timeline.</span></li>
              )}
            </ul>
          </article>

          <article className="detailCardBlock">
            <h3>Education, Projects, Certifications</h3>
            <ul className="bulletList">
              <li>Education: <strong>{candidate.education || "Not found"}</strong></li>
              <li>Projects: <strong>{(candidate.projects || []).join(", ") || "Not extracted"}</strong></li>
              <li>Certifications: <strong>{(candidate.certifications || []).join(", ") || "Not extracted"}</strong></li>
              <li>LinkedIn: <strong>{candidate.linkedin || "Not found"}</strong></li>
            </ul>
          </article>

          <article className="detailCardBlock wide">
            <h3>ATS Evaluation Metrics</h3>
            <div className="scoreBreakdown">
              {Object.entries(breakdown).map(([key, value]) => (
                <div key={key}>
                  <span>{key.replaceAll("_", " ")}</span>
                  <strong>{formatPercent(value)}</strong>
                  <div className="barTrack">
                    <div className="barFill" style={{ width: `${Math.min(100, Number(value || 0))}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </article>
        </section>
      </aside>
    </div>
  );
}
