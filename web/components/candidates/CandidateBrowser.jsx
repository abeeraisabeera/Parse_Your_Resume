"use client";

import { useMemo, useState } from "react";

import {
  candidateKey,
  formatPercent,
  getInitials,
  getOverallScore,
  getSkillsMatchScore,
  groupCandidatesByRole,
  roleConfidence,
  roleLabel
} from "../../lib/candidateUtils";
import { exportCandidates } from "../../lib/candidateApi";
import { CandidateFilters } from "../filters/CandidateFilters";
import { StatusBadge } from "../common/StatusBadge";
import { CandidateDetailDrawer } from "./CandidateDetailDrawer";

const PAGE_SIZE = 12;

function CandidateCard({ candidate, active, onSelect, onLearnMore }) {
  return (
    <article className={`candidateCard ${active ? "active" : ""} ${candidate.is_deleted ? "deleted" : ""}`}>
      <button type="button" className="cardSelect" onClick={onSelect}>
        <span className="candidateIdentity">
          <em>{getInitials(candidate.name)}</em>
          <span>
            <strong>{candidate.name || candidateKey(candidate) || "Unknown"}</strong>
            <small className="candidateMeta">{candidate.email || candidate.current_role || "No contact info"}</small>
          </span>
        </span>
      </button>
      <div className="cardMetrics">
        <span>{formatPercent(getOverallScore(candidate))}<small>ATS</small></span>
        <span>{candidate.estimated_years_of_experience || 0}<small>yrs</small></span>
        <span>{formatPercent(roleConfidence(candidate))}<small>role</small></span>
      </div>
      <div className="docMeta">
        {(candidate.top_skills || []).slice(0, 4).map((skill) => <span key={skill}>{skill}</span>)}
      </div>
      <div className="candidateCardFooter">
        <StatusBadge status={candidate.candidate_status} />
        <button className="secondaryButton" type="button" onClick={onLearnMore}>Learn More</button>
      </div>
    </article>
  );
}

function CandidateTable({ candidates, selectedCandidate, onSelect, onLearnMore }) {
  return (
    <div className="candidateTable">
      <div className="candidateTableHead candidateTableHeadWide">
        <span>Rank</span>
        <span>Candidate</span>
        <span>Role</span>
        <span>Experience</span>
        <span>Skills Match</span>
        <span>ATS Score</span>
        <span>Status</span>
        <span>Action</span>
      </div>

      {candidates.map((candidate) => {
        const key = candidateKey(candidate);
        const isActive = key === candidateKey(selectedCandidate);
        return (
          <div
            key={key}
            className={`candidateRow candidateRowWide ${isActive ? "active" : ""} ${
              candidate.is_deleted ? "deleted" : ""
            }`}
          >
            <button className="rowButton rankButton" type="button" onClick={() => onSelect(key)}>
              #{candidate.rank || "-"}
            </button>
            <button className="rowButton candidateIdentity" type="button" onClick={() => onSelect(key)}>
              <em>{getInitials(candidate.name)}</em>
              <span>
                <strong>{candidate.name || key || "Unknown"}</strong>
                <small className="candidateMeta">{candidate.email || candidate.current_role || "No contact info"}</small>
              </span>
            </button>
            <span>{roleLabel(candidate.role_detected)}</span>
            <span>{candidate.estimated_years_of_experience || 0} yrs</span>
            <span>{formatPercent(getSkillsMatchScore(candidate))}</span>
            <span>{formatPercent(getOverallScore(candidate))}</span>
            <span><StatusBadge status={candidate.candidate_status} /></span>
            <span>
              <button className="secondaryButton" type="button" onClick={() => onLearnMore(candidate)}>
                Learn More
              </button>
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function CandidateBrowser({ workspace }) {
  const {
    filteredCandidates,
    selectedCandidate,
    selectedCandidateKey,
    setSelectedCandidateKey,
    filters,
    setFilter,
    clearFilters,
    activeFilterChips,
    removeFilter,
    viewMode,
    setViewMode,
    sortKey,
    setSortKey,
    page,
    setPage,
    skills,
    roles,
    toggleShortlist,
    removeCandidate,
    actionLoading,
    error
  } = workspace;
  const [drawerCandidate, setDrawerCandidate] = useState(null);

  const roleGroups = useMemo(() => groupCandidatesByRole(filteredCandidates), [filteredCandidates]);
  const pageCount = Math.max(1, Math.ceil(filteredCandidates.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount);
  const visibleCandidates = filteredCandidates.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE);

  function changeRole(role) {
    setFilter("roleFilter", role);
    setPage(1);
  }

  function openCandidate(candidate) {
    setSelectedCandidateKey(candidateKey(candidate));
    setDrawerCandidate(candidate);
  }

  return (
    <div className="pageGrid candidatePage">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Candidate Workspace</p>
          <h2>Browse candidates by role, score, and skill fit.</h2>
          <p className="subtle">Use role groups and persistent filters to move through large resume pools quickly.</p>
        </div>
        <div className="tableActions">
          <button
            className={`secondaryButton ${viewMode === "list" ? "activeControl" : ""}`}
            type="button"
            onClick={() => setViewMode("list")}
          >
            List
          </button>
          <button
            className={`secondaryButton ${viewMode === "grid" ? "activeControl" : ""}`}
            type="button"
            onClick={() => setViewMode("grid")}
          >
            Grid
          </button>
          <button
            className="secondaryButton"
            type="button"
            disabled={!filteredCandidates.length}
            onClick={() => exportCandidates(filters, filteredCandidates.length)}
          >
            Export Excel
          </button>
        </div>
      </section>

      {error ? <div className="message error">{error}</div> : null}

      <div className="candidateLayout">
        <aside className="roleRail panel">
          <div className="panelHeader">
            <h2>Roles</h2>
            <span>{filteredCandidates.length}</span>
          </div>
          <button
            className={`roleTab ${filters.roleFilter === "all" ? "active" : ""}`}
            type="button"
            onClick={() => changeRole("all")}
          >
            <span>All Candidates</span>
            <strong>{filteredCandidates.length}</strong>
          </button>
          {roleGroups.map((group) => (
            <button
              key={group.role}
              className={`roleTab ${filters.roleFilter === group.role ? "active" : ""}`}
              type="button"
              onClick={() => changeRole(group.role)}
            >
              <span>{group.label}</span>
              <strong>{group.count}</strong>
            </button>
          ))}
        </aside>

        <section className="candidateMain">
          <CandidateFilters
            compact
            filters={filters}
            setFilter={setFilter}
            clearFilters={clearFilters}
            activeFilterChips={activeFilterChips}
            removeFilter={removeFilter}
            skills={skills}
            roles={roles}
          />

          <div className="panel">
            <div className="panelHeader">
              <div>
                <h2>Candidate Results</h2>
                <p className="subtle">{filteredCandidates.length} matching candidates</p>
              </div>
              <label className="label inlineLabel">
                Sort
                <select className="input" value={sortKey} onChange={(event) => setSortKey(event.target.value)}>
                  <option value="score">ATS score</option>
                  <option value="experience">Experience</option>
                  <option value="recent">Recently parsed</option>
                  <option value="name">Name</option>
                </select>
              </label>
            </div>

            {visibleCandidates.length ? (
              viewMode === "grid" ? (
                <div className="candidateCardGrid">
                  {visibleCandidates.map((candidate) => (
                    <CandidateCard
                      key={candidateKey(candidate)}
                      candidate={candidate}
                      active={candidateKey(candidate) === selectedCandidateKey}
                      onSelect={() => setSelectedCandidateKey(candidateKey(candidate))}
                      onLearnMore={() => openCandidate(candidate)}
                    />
                  ))}
                </div>
              ) : (
                <CandidateTable
                  candidates={visibleCandidates}
                  selectedCandidate={selectedCandidate}
                  onSelect={setSelectedCandidateKey}
                  onLearnMore={openCandidate}
                />
              )
            ) : (
              <p className="emptyState">No candidates match the current filters.</p>
            )}

            <div className="paginationBar">
              <button
                className="secondaryButton"
                type="button"
                disabled={currentPage <= 1}
                onClick={() => setPage(currentPage - 1)}
              >
                Previous
              </button>
              <span>Page {currentPage} of {pageCount}</span>
              <button
                className="secondaryButton"
                type="button"
                disabled={currentPage >= pageCount}
                onClick={() => setPage(currentPage + 1)}
              >
                Next
              </button>
            </div>
          </div>
        </section>
      </div>

      <CandidateDetailDrawer
        candidate={drawerCandidate || selectedCandidate}
        skills={skills}
        open={Boolean(drawerCandidate)}
        onClose={() => setDrawerCandidate(null)}
        onToggleShortlist={toggleShortlist}
        onDelete={removeCandidate}
        actionLoading={actionLoading}
      />
    </div>
  );
}
