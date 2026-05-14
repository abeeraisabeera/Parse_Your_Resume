"use client";

import { useEffect, useState } from "react";

import { ROLE_OPTIONS, SENIORITY_OPTIONS } from "../../lib/constants";
import { skillGroupsFromTaxonomy } from "../../lib/candidateUtils";

const FILTER_PANEL_STORAGE_KEY = "resumeRank.filtersPanelOpen";

export function FilterChips({ chips, onRemove, onClear }) {
  if (!chips.length) {
    return <p className="hintText">No active filters. Use the controls to narrow the talent pool.</p>;
  }

  return (
    <div className="filterChips">
      {chips.map((chip) => (
        <button key={chip.key} className="filterChip" type="button" onClick={() => onRemove(chip.key)}>
          {chip.label}
          <span aria-hidden="true">x</span>
        </button>
      ))}
      <button className="textButton" type="button" onClick={onClear}>Clear all</button>
    </div>
  );
}

export function CandidateFilters({
  filters,
  setFilter,
  clearFilters,
  activeFilterChips,
  removeFilter,
  skills = [],
  roles = [],
  compact = false
}) {
  const skillGroups = skillGroupsFromTaxonomy(skills);
  const roleOptions = roles.length
    ? [["all", "All roles"], ...roles.map((role) => [role.id, role.label])]
    : ROLE_OPTIONS;
  const selectedSkills = filters.skillFilter
    .split(/[,;]/)
    .map((skill) => skill.trim())
    .filter(Boolean);
  const [expanded, setExpanded] = useState(true);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(FILTER_PANEL_STORAGE_KEY);
      if (stored !== null) setExpanded(stored === "true");
    } catch {
      setExpanded(true);
    }
  }, []);

  function toggleExpanded() {
    setExpanded((current) => {
      const next = !current;
      try {
        window.localStorage.setItem(FILTER_PANEL_STORAGE_KEY, String(next));
      } catch {
        // Ignore storage failures; the visible toggle still works for the session.
      }
      return next;
    });
  }

  return (
    <section className={`panel filterPanel ${compact ? "compact" : ""} ${expanded ? "" : "collapsed"}`}>
      <div className="panelHeader">
        <div>
          <h2>Global Filters</h2>
          <p className="subtle">Filters persist across candidate, dashboard, analytics, and export views.</p>
        </div>
        <div className="tableActions">
          <button
            className="secondaryButton"
            type="button"
            onClick={toggleExpanded}
            aria-expanded={expanded}
          >
            {expanded ? "Collapse" : "Expand"}
          </button>
          <button className="textButton" type="button" onClick={clearFilters}>Reset</button>
        </div>
      </div>

      <FilterChips chips={activeFilterChips} onRemove={removeFilter} onClear={clearFilters} />

      <div className="filterGrid" hidden={!expanded}>
        <label className="label">
          Search
          <input
            className="input"
            type="search"
            value={filters.search}
            onChange={(event) => setFilter("search", event.target.value)}
            placeholder="Name, role, skill, email, file"
          />
        </label>

        <label className="label">
          Role / Category
          <select
            className="input"
            value={filters.roleFilter}
            onChange={(event) => setFilter("roleFilter", event.target.value)}
          >
            {roleOptions.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>

        <label className="label">
          Skills
          <select
            className="input"
            multiple
            value={selectedSkills}
            onChange={(event) =>
              setFilter(
                "skillFilter",
                Array.from(event.target.selectedOptions)
                  .map((option) => option.value)
                  .filter(Boolean)
                  .join(", ")
              )
            }
          >
            {skillGroups.map((group) => (
              <optgroup key={group.label} label={group.label}>
                {group.options.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </optgroup>
            ))}
          </select>
          <span className="sliderValue">
            {selectedSkills.length ? `${selectedSkills.length} skill(s) selected` : "No skill filter selected"}
          </span>
        </label>

        <label className="label">
          Experience
          <select
            className="input"
            value={filters.minExperience}
            onChange={(event) => setFilter("minExperience", event.target.value)}
          >
            <option value="0">Any</option>
            <option value="2">2+ years</option>
            <option value="5">5+ years</option>
            <option value="8">8+ years</option>
            <option value="12">12+ years</option>
          </select>
        </label>

        <label className="label">
          ATS Score
          <input
            className="input"
            type="range"
            min="0"
            max="100"
            value={filters.minScore}
            onChange={(event) => setFilter("minScore", event.target.value)}
          />
          <span className="sliderValue">{filters.minScore}% and above</span>
        </label>

        <label className="label">
          Seniority
          <select
            className="input"
            value={filters.seniority}
            onChange={(event) => setFilter("seniority", event.target.value)}
          >
            <option value="all">Any seniority</option>
            {SENIORITY_OPTIONS.map((level) => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
        </label>

        <label className="label">
          Status
          <select
            className="input"
            value={filters.status}
            onChange={(event) => setFilter("status", event.target.value)}
          >
            <option value="all">Any status</option>
            <option value="shortlisted">Shortlisted</option>
            <option value="in review">In Review</option>
            <option value="needs review">Needs Review</option>
            <option value="new">New</option>
            <option value="deleted">Deleted</option>
          </select>
        </label>

        <label className="label">
          Shortlist State
          <select
            className="input"
            value={filters.shortlistFilter}
            onChange={(event) => setFilter("shortlistFilter", event.target.value)}
          >
            <option value="all">All candidates</option>
            <option value="shortlisted">Shortlisted only</option>
            <option value="not_shortlisted">Not shortlisted</option>
          </select>
        </label>

        <label className="label">
          Education
          <input
            className="input"
            value={filters.education}
            onChange={(event) => setFilter("education", event.target.value)}
            placeholder="Degree, school, certification"
          />
        </label>

        <label className="label">
          Location
          <input
            className="input"
            value={filters.location}
            onChange={(event) => setFilter("location", event.target.value)}
            placeholder="City, country, remote"
          />
        </label>

        <label className="label">
          Parsing Confidence
          <input
            className="input"
            type="range"
            min="0"
            max="100"
            value={filters.parsingConfidence}
            onChange={(event) => setFilter("parsingConfidence", event.target.value)}
          />
          <span className="sliderValue">{filters.parsingConfidence}% and above</span>
        </label>

        <label className="checkboxRow">
          <input
            type="checkbox"
            checked={filters.includeDeleted}
            onChange={(event) => setFilter("includeDeleted", event.target.checked)}
          />
          <span>Show deleted resumes</span>
        </label>
      </div>
    </section>
  );
}
