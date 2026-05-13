"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const DEFAULT_MODEL = "llama-3.1-8b-instant";
const NAV_ITEMS = [
  { label: "Overview", section: "overview" },
  { label: "Candidates", section: "candidates" },
  { label: "Analytics", section: "analytics" },
  { label: "Details", section: "details" },
  { label: "Filters", section: "filters" },
  { label: "Uploads", section: "uploads" }
];
const ROLE_OPTIONS = [
  ["all", "All roles"],
  ["frontend", "Frontend Developer"],
  ["backend", "Backend Developer"],
  ["fullstack", "Fullstack Developer"],
  ["data", "Data / BI"],
  ["devops", "DevOps / Cloud"],
  ["qa", "QA / Testing"],
  ["design", "Design"],
  ["marketing", "Marketing"],
  ["general", "General"]
];

function candidateStatus(score) {
  const numeric = Number(score || 0);
  if (numeric >= 85) return "Shortlisted";
  if (numeric >= 70) return "In Review";
  if (numeric >= 50) return "Needs Review";
  return "New";
}

function statusClassName(status) {
  return (status || "New").toLowerCase().replace(/\s+/g, "-");
}

function getOverallScore(candidate) {
  return Number(candidate?.overall_score ?? candidate?.ranking_score ?? 0);
}

function getSkillsMatchScore(candidate) {
  return Number(
    candidate?.skills_match_score ??
      candidate?.ranking_breakdown?.skills_score ??
      0
  );
}

function getConsistencyScore(candidate) {
  return Number(
    candidate?.consistency_score ?? (candidate?.experience_confidence ?? 0) * 100
  );
}

function buildSummary(results) {
  const scores = results.map((item) => getOverallScore(item));
  const experience = results.map((item) =>
    Number(item.estimated_years_of_experience || 0)
  );

  return {
    total_candidates: results.length,
    valid_candidates: results.filter((item) => item.is_valid_resume !== false).length,
    shortlisted: results.filter((item) => item.is_shortlisted).length,
    high_match: scores.filter((score) => score >= 75).length,
    avg_match_score: scores.length
      ? Number((scores.reduce((sum, value) => sum + value, 0) / scores.length).toFixed(1))
      : 0,
    avg_experience_years: experience.length
      ? Number(
          (experience.reduce((sum, value) => sum + value, 0) / experience.length).toFixed(1)
        )
      : 0
  };
}

function normalizeResponse(payload) {
  if (Array.isArray(payload?.results)) {
    return payload;
  }

  const result = {
    ...payload,
    candidate_status:
      payload?.candidate_status || candidateStatus(payload?.ranking_score),
    rank: 1
  };

  return {
    mode: "single",
    api_mode: payload?.api_mode || "rule_based",
    results: [result],
    summary: buildSummary([result])
  };
}

function getInitials(name) {
  if (!name) return "NA";
  const parts = name.split(/\s+/).filter(Boolean).slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() || "").join("") || "NA";
}

function buildTopSkills(results) {
  const counts = new Map();
  results.forEach((candidate) => {
    (candidate.top_skills || []).forEach((skill) => {
      counts.set(skill, (counts.get(skill) || 0) + 1);
    });
  });

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([skill, count]) => ({ skill, count }));
}

function buildExperienceDistribution(results) {
  const buckets = [
    { label: "0-2 yrs", key: "0-2", count: 0 },
    { label: "2-5 yrs", key: "2-5", count: 0 },
    { label: "5-8 yrs", key: "5-8", count: 0 },
    { label: "8+ yrs", key: "8+", count: 0 }
  ];

  results.forEach((candidate) => {
    const years = Number(candidate.estimated_years_of_experience || 0);
    if (years < 2) buckets[0].count += 1;
    else if (years < 5) buckets[1].count += 1;
    else if (years < 8) buckets[2].count += 1;
    else buckets[3].count += 1;
  });

  return buckets;
}

function buildScoreDistribution(results) {
  const buckets = [
    { label: "0-20", count: 0 },
    { label: "20-40", count: 0 },
    { label: "40-60", count: 0 },
    { label: "60-80", count: 0 },
    { label: "80-100", count: 0 }
  ];

  results.forEach((candidate) => {
    const score = getOverallScore(candidate);
    if (score < 20) buckets[0].count += 1;
    else if (score < 40) buckets[1].count += 1;
    else if (score < 60) buckets[2].count += 1;
    else if (score < 80) buckets[3].count += 1;
    else buckets[4].count += 1;
  });

  return buckets;
}

function formatPercent(value) {
  return `${Math.round(Number(value || 0))}%`;
}

function candidateKey(candidate) {
  return candidate?.id || candidate?.uploaded_file_name || candidate?.source_file;
}

function buildCandidateParams({
  search,
  roleFilter,
  skillFilter,
  shortlistFilter,
  minExperience,
  minScore,
  includeDeleted,
  limit
}) {
  const params = new URLSearchParams();
  if (search.trim()) params.set("search", search.trim());
  if (roleFilter !== "all") params.set("role", roleFilter);
  if (skillFilter.trim()) params.set("skills", skillFilter.trim());
  if (shortlistFilter !== "all") params.set("shortlist", shortlistFilter);
  if (Number(minExperience || 0) > 0) params.set("min_experience", minExperience);
  if (Number(minScore || 0) > 0) params.set("min_score", String(minScore));
  if (includeDeleted) params.set("include_deleted", "true");
  if (limit) params.set("limit", String(limit));
  return params;
}

export default function HomePage() {
  const [files, setFiles] = useState([]);
  const [useLlm, setUseLlm] = useState(true);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [maxRetries, setMaxRetries] = useState(6);
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [skillFilter, setSkillFilter] = useState("");
  const [shortlistFilter, setShortlistFilter] = useState("all");
  const [minExperience, setMinExperience] = useState("0");
  const [minScore, setMinScore] = useState(0);
  const [includeDeleted, setIncludeDeleted] = useState(false);
  const [selectedCandidateKey, setSelectedCandidateKey] = useState(null);
  const [activeNav, setActiveNav] = useState("overview");
  const [actionLoading, setActionLoading] = useState("");
  const sectionRefs = useRef({});

  const loadCandidates = useCallback(
    async (preferredKey = null) => {
      const params = new URLSearchParams();
      if (includeDeleted) params.set("include_deleted", "true");
      params.set("limit", "1000");

      const response = await fetch(`/api/candidates?${params.toString()}`, {
        cache: "no-store"
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || payload.error || "Unable to load stored candidates.");
      }
      const normalized = normalizeResponse(payload);
      setDashboard(normalized);
      const firstKey =
        preferredKey ||
        candidateKey(normalized.results[0]) ||
        null;
      setSelectedCandidateKey(firstKey);
      return normalized;
    },
    [includeDeleted]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      try {
        const response = await fetch("/api/healthz", { cache: "no-store" });
        const payload = await response.json();
        if (!cancelled) {
          setHealth(payload);
        }
      } catch (healthError) {
        if (!cancelled) {
          setHealth({ ok: false, error: healthError.message });
        }
      }
    }

    loadHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    loadCandidates()
      .catch((loadError) => {
        if (!cancelled) {
          setDashboard({ mode: "stored", results: [], summary: buildSummary([]) });
          setError(loadError.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [loadCandidates]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!files.length) {
      setError("Select at least one PDF resume before submitting.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const formData = new FormData();
      files.forEach((file) => formData.append("files", file));
      formData.append("use_llm", String(useLlm));
      formData.append("model", model);
      formData.append("max_retries", String(maxRetries));

      const response = await fetch("/api/parse", {
        method: "POST",
        body: formData
      });
      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.error || "Parsing failed.");
      }

      const normalized = normalizeResponse(payload);
      const preferredKey = candidateKey(normalized.results[0]);
      await loadCandidates(preferredKey);
      const storageIssue = normalized.results.find((candidate) => candidate.storage_error);
      if (storageIssue) {
        setError(`Parsed successfully, but storage failed: ${storageIssue.storage_error}`);
      }
      setActiveNav("candidates");
    } catch (submitError) {
      setError(submitError.message);
    } finally {
      setLoading(false);
    }
  }

  const filteredCandidates = useMemo(() => {
    const results = dashboard?.results || [];
    const query = search.trim().toLowerCase();
    const requiredSkills = skillFilter
      .split(/[,;]/)
      .map((skill) => skill.trim().toLowerCase())
      .filter(Boolean);
    const experienceFloor = Number(minExperience || 0);
    const scoreFloor = Number(minScore || 0);

    return results.filter((candidate) => {
      const haystack = [
        candidate.name,
        candidate.email,
        candidate.current_role,
        candidate.uploaded_file_name,
        ...(candidate.top_skills || []),
        ...(candidate.skills || [])
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      const matchesSearch = !query || haystack.includes(query);
      const matchesRole =
        roleFilter === "all" || candidate.role_detected === roleFilter;
      const candidateSkills = [
        ...(candidate.top_skills || []),
        ...(candidate.skills || [])
      ].map((skill) => String(skill).toLowerCase());
      const matchesSkill =
        !requiredSkills.length ||
        requiredSkills.every((requiredSkill) =>
          candidateSkills.some(
            (skill) => skill.includes(requiredSkill) || requiredSkill.includes(skill)
          )
        );
      const matchesShortlist =
        shortlistFilter === "all" ||
        (shortlistFilter === "shortlisted" && candidate.is_shortlisted) ||
        (shortlistFilter === "not_shortlisted" && !candidate.is_shortlisted);
      const matchesExperience =
        Number(candidate.estimated_years_of_experience || 0) >= experienceFloor;
      const matchesScore = getOverallScore(candidate) >= scoreFloor;
      const matchesDeleted = includeDeleted || !candidate.is_deleted;

      return (
        matchesSearch &&
        matchesRole &&
        matchesSkill &&
        matchesShortlist &&
        matchesExperience &&
        matchesScore &&
        matchesDeleted
      );
    });
  }, [
    dashboard,
    search,
    roleFilter,
    skillFilter,
    shortlistFilter,
    minExperience,
    minScore,
    includeDeleted
  ]);

  const selectedCandidate = useMemo(() => {
    if (!filteredCandidates.length) return null;
    return (
      filteredCandidates.find((candidate) => {
        const key = candidateKey(candidate);
        return key === selectedCandidateKey;
      }) || filteredCandidates[0]
    );
  }, [filteredCandidates, selectedCandidateKey]);

  useEffect(() => {
    if (selectedCandidate) {
      const selectedKey = candidateKey(selectedCandidate);
      if (selectedKey !== selectedCandidateKey) {
        setSelectedCandidateKey(selectedKey);
      }
    }
  }, [selectedCandidate, selectedCandidateKey]);

  const summary = useMemo(
    () => buildSummary(filteredCandidates),
    [filteredCandidates]
  );
  const topSkills = useMemo(
    () => buildTopSkills(filteredCandidates),
    [filteredCandidates]
  );
  const experienceDistribution = useMemo(
    () => buildExperienceDistribution(filteredCandidates),
    [filteredCandidates]
  );
  const scoreDistribution = useMemo(
    () => buildScoreDistribution(filteredCandidates),
    [filteredCandidates]
  );
  const totalExperienceSegments = experienceDistribution.reduce(
    (sum, item) => sum + item.count,
    0
  );
  const totalScoreSegments = scoreDistribution.reduce((sum, item) => sum + item.count, 0);

  function scrollToSection(section) {
    setActiveNav(section);
    const node = sectionRefs.current[section];
    if (node) {
      node.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  async function handleToggleShortlist() {
    if (!selectedCandidate?.id) return;
    setActionLoading("shortlist");
    setError("");
    try {
      const response = await fetch(`/api/candidates/${selectedCandidate.id}/shortlist`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_shortlisted: !selectedCandidate.is_shortlisted })
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || payload.error || "Unable to update shortlist.");
      }
      setDashboard((current) => ({
        ...current,
        results: (current?.results || []).map((candidate) =>
          candidate.id === payload.id ? payload : candidate
        )
      }));
      setSelectedCandidateKey(payload.id);
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setActionLoading("");
    }
  }

  async function handleDeleteCandidate() {
    if (!selectedCandidate?.id) return;
    const confirmed = window.confirm("Delete this outdated resume from the active list?");
    if (!confirmed) return;
    setActionLoading("delete");
    setError("");
    try {
      const response = await fetch(`/api/candidates/${selectedCandidate.id}`, {
        method: "DELETE"
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || payload.error || "Unable to delete candidate.");
      }
      await loadCandidates();
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setActionLoading("");
    }
  }

  function handleExportCandidates() {
    const params = buildCandidateParams({
      search,
      roleFilter,
      skillFilter,
      shortlistFilter,
      minExperience,
      minScore,
      includeDeleted,
      limit: Math.max(filteredCandidates.length, 1)
    });
    window.location.href = `/api/candidates/export?${params.toString()}`;
  }

  return (
    <main className="workspace">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">R</div>
          <div>
            <strong>ResumeRank</strong>
            <p>HR workspace</p>
          </div>
        </div>

        <nav className="navList">
          {NAV_ITEMS.map((item, index) => (
            <button
              key={item.section}
              className={`navItem ${activeNav === item.section ? "active" : ""}`}
              type="button"
              onClick={() => scrollToSection(item.section)}
            >
              <span className="navIcon">{index + 1}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebarCard">
          <h3>System Status</h3>
          <div className="statusRow">
            <span>Parser API</span>
            <strong className={health?.ok ? "statusOk" : "statusWarn"}>
              {health?.ok ? "Online" : "Offline"}
            </strong>
          </div>
          <div className="statusRow">
            <span>OCR</span>
            <strong
              className={health?.ocr_available ? "statusOk" : "statusWarn"}
            >
              {health?.ocr_available ? "Ready" : "Unavailable"}
            </strong>
          </div>
          <div className="statusRow">
            <span>Batch Parsing</span>
            <strong className="statusOk">
              {health?.supports_batch_processing ? "Enabled" : "Checking"}
            </strong>
          </div>
          <div className="statusRow">
            <span>Storage</span>
            <strong
              className={health?.candidate_storage?.available ? "statusOk" : "statusWarn"}
            >
              {health?.candidate_storage?.backend || "Checking"}
            </strong>
          </div>
          {health?.ocr_available === false && health?.ocr_detail ? (
            <p className="miniNote">{health.ocr_detail}</p>
          ) : null}
        </div>
      </aside>

      <section className="mainPane">
        <header
          className="topBar"
          ref={(node) => {
            sectionRefs.current.overview = node;
          }}
        >
          <div>
            <p className="eyebrow">AI-Powered Resume Screening</p>
            <h1>Dashboard Overview</h1>
            <p className="subtle">Stored candidate pipeline for parsing, ranking, shortlisting, and export.</p>
          </div>
          <label className="searchBox">
            <span>Search</span>
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by name, skill, role, or file"
            />
          </label>
        </header>

        <section className="metricGrid">
          <article className="metricCard">
            <span>Total Candidates</span>
            <strong>{summary.total_candidates || 0}</strong>
            <small>{summary.valid_candidates || 0} valid</small>
          </article>
          <article className="metricCard">
            <span>Shortlisted</span>
            <strong>{summary.shortlisted || 0}</strong>
            <small>auto or HR selected</small>
          </article>
          <article className="metricCard">
            <span>High Match</span>
            <strong>{summary.high_match || 0}</strong>
            <small>75+ overall</small>
          </article>
          <article className="metricCard">
            <span>Avg Score</span>
            <strong>{summary.avg_match_score || 0}%</strong>
            <small>{summary.avg_experience_years || 0} yrs avg exp</small>
          </article>
        </section>

        <section
          className="analyticsGrid"
          ref={(node) => {
            sectionRefs.current.analytics = node;
          }}
        >
          <article className="panel soft">
            <div className="panelHeader">
              <h2>Candidates by Experience</h2>
              <span>{filteredCandidates.length}</span>
            </div>
            <div className="experienceLegend">
              {experienceDistribution.map((bucket) => (
                <div className="legendItem" key={bucket.key}>
                  <strong>{bucket.count}</strong>
                  <span>{bucket.label}</span>
                </div>
              ))}
            </div>
            <div className="stackBar">
              {experienceDistribution.map((bucket) => (
                <div
                  key={bucket.key}
                  className="stackSegment"
                  style={{
                    width: `${
                      totalExperienceSegments
                        ? (bucket.count / totalExperienceSegments) * 100
                        : 25
                    }%`
                  }}
                  title={`${bucket.label}: ${bucket.count}`}
                />
              ))}
            </div>
          </article>

          <article className="panel soft">
            <div className="panelHeader">
              <h2>Top Skills</h2>
              <span>Frequency</span>
            </div>
            <div className="bars">
              {topSkills.length ? (
                topSkills.map((item) => (
                  <div className="barRow" key={item.skill}>
                    <span>{item.skill}</span>
                    <div className="barTrack">
                      <div
                        className="barFill"
                        style={{
                          width: `${
                            (item.count /
                              Math.max(...topSkills.map((skill) => skill.count), 1)) *
                            100
                          }%`
                        }}
                      />
                    </div>
                    <strong>{item.count}</strong>
                  </div>
                ))
              ) : (
                <p className="hintText">Run a parse to populate top skills.</p>
              )}
            </div>
          </article>

          <article className="panel soft">
            <div className="panelHeader">
              <h2>Match Score Distribution</h2>
              <span>Spread</span>
            </div>
            <div className="histogram">
              {scoreDistribution.map((bucket) => (
                <div className="histogramColumn" key={bucket.label}>
                  <div
                    className="histogramBar"
                    style={{
                      height: `${
                        totalScoreSegments
                          ? Math.max(18, (bucket.count / totalScoreSegments) * 140)
                          : 18
                      }px`
                    }}
                  />
                  <span>{bucket.label}</span>
                </div>
              ))}
            </div>
          </article>
        </section>

        <section
          className="panel"
          ref={(node) => {
            sectionRefs.current.candidates = node;
          }}
        >
          <div className="panelHeader">
            <div>
              <h2>Top Ranked Candidates</h2>
            </div>
            <div className="tableActions">
              <span className="tableCount">
                {filteredCandidates.length} visible
              </span>
              <button
                className="secondaryButton"
                type="button"
                onClick={handleExportCandidates}
                disabled={!filteredCandidates.length}
              >
                Export Excel
              </button>
            </div>
          </div>

          {error ? <div className="message error">{error}</div> : null}

          {filteredCandidates.length ? (
            <div className="candidateTable">
              <div className="candidateTableHead">
                <span>Rank</span>
                <span>Candidate</span>
                <span>Experience</span>
                <span>Skills Match</span>
                <span>Match Score</span>
                <span>Status</span>
              </div>

              {filteredCandidates.map((candidate) => {
                const key = candidateKey(candidate);
                const isActive = key === candidateKey(selectedCandidate);
                return (
                  <button
                    key={key}
                    type="button"
                    className={`candidateRow ${isActive ? "active" : ""} ${
                      candidate.is_deleted ? "deleted" : ""
                    }`}
                    onClick={() => setSelectedCandidateKey(key)}
                  >
                    <span>#{candidate.rank || "-"}</span>
                    <span className="candidateIdentity">
                      <em>{getInitials(candidate.name)}</em>
                      <span>
                        <strong>{candidate.name || key || "Unknown"}</strong>
                        <small className="candidateMeta">
                          {candidate.email || candidate.current_role || "No contact info"}
                        </small>
                      </span>
                    </span>
                    <span>{candidate.estimated_years_of_experience || 0} yrs</span>
                    <span>{formatPercent(getSkillsMatchScore(candidate))}</span>
                    <span>{formatPercent(getOverallScore(candidate))}</span>
                    <span>
                      <mark
                        className={`statusBadge ${statusClassName(
                          candidate.candidate_status
                        )}`}
                      >
                        {candidate.candidate_status || "New"}
                      </mark>
                    </span>
                  </button>
                );
              })}
            </div>
          ) : (
            <p className="emptyState">
              Upload resumes to populate the candidate table.
            </p>
          )}
        </section>

        <section
          className="detailGrid"
          ref={(node) => {
            sectionRefs.current.details = node;
          }}
        >
          <article className="panel detailCard">
            <div className="resumePreview">
              <div className="docSheet">
                <div className="docTitle">
                  {selectedCandidate?.uploaded_file_name || "No resume selected"}
                </div>
                <div className="docMeta">
                  {(selectedCandidate?.top_skills || []).slice(0, 4).map((skill) => (
                    <span key={skill}>{skill}</span>
                  ))}
                </div>
              </div>
            </div>
          </article>

          <article className="panel candidateDetail">
            <div className="panelHeader">
              <div className="candidateHero">
                <div className="avatar">{getInitials(selectedCandidate?.name)}</div>
                <div>
                  <h2>{selectedCandidate?.name || "Candidate Detail"}</h2>
                  <p className="subtle">
                    {selectedCandidate?.current_role || "Current role unavailable"}
                  </p>
                  <p className="candidateMeta detailMeta">
                    {selectedCandidate?.email || "Email not extracted"}
                  </p>
                </div>
              </div>
              {selectedCandidate ? (
                <div className="detailActions">
                  <mark
                    className={`statusBadge ${statusClassName(
                      selectedCandidate.candidate_status
                    )}`}
                  >
                    {selectedCandidate.candidate_status || "New"}
                  </mark>
                  <button
                    className="secondaryButton"
                    type="button"
                    onClick={handleToggleShortlist}
                    disabled={actionLoading === "shortlist" || selectedCandidate.is_deleted}
                  >
                    {selectedCandidate.is_shortlisted ? "Unshortlist" : "Shortlist"}
                  </button>
                  <button
                    className="dangerButton"
                    type="button"
                    onClick={handleDeleteCandidate}
                    disabled={actionLoading === "delete" || selectedCandidate.is_deleted}
                  >
                    Delete
                  </button>
                </div>
              ) : null}
            </div>

            {selectedCandidate ? (
              <>
                <div className="detailStats">
                  <div>
                    <span>Experience</span>
                    <strong>
                      {selectedCandidate.estimated_years_of_experience || 0} yrs
                    </strong>
                  </div>
                  <div>
                    <span>Skills Match</span>
                    <strong>{formatPercent(getSkillsMatchScore(selectedCandidate))}</strong>
                  </div>
                  <div>
                    <span>Consistency</span>
                    <strong>{formatPercent(getConsistencyScore(selectedCandidate))}</strong>
                  </div>
                  <div>
                    <span>Overall Score</span>
                    <strong>{formatPercent(getOverallScore(selectedCandidate))}</strong>
                  </div>
                </div>

                <div className="detailColumns">
                  <div>
                    <h3 className="sectionTitle">Top Skills Detected</h3>
                    <ul className="chips">
                      {(selectedCandidate.top_skills || selectedCandidate.skills || []).map(
                        (skill) => (
                          <li className="chip" key={skill}>
                            {skill}
                          </li>
                        )
                      )}
                    </ul>

                    <h3 className="sectionTitle">Companies</h3>
                    <ul className="bulletList">
                      {(selectedCandidate.companies_worked || []).length ? (
                        selectedCandidate.companies_worked.map((company) => (
                          <li key={company}>{company}</li>
                        ))
                      ) : (
                        <li>No company history extracted.</li>
                      )}
                    </ul>
                  </div>

                  <div>
                    <h3 className="sectionTitle">Analysis</h3>
                    <ul className="bulletList">
                      <li>{selectedCandidate.notes || "No analysis notes generated."}</li>
                      <li>
                        Role: <strong>{selectedCandidate.role_detected || "general"}</strong>
                      </li>
                      <li>
                        Seniority: <strong>{selectedCandidate.seniority_level || "unknown"}</strong>
                      </li>
                      <li>
                        Education: <strong>{selectedCandidate.education || "Not found"}</strong>
                      </li>
                    </ul>
                  </div>
                </div>
              </>
            ) : (
              <p className="emptyState">
                Parse at least one resume to inspect candidate details.
              </p>
            )}
          </article>
        </section>
      </section>

      <aside className="rightRail">
        <section
          className="panel"
          ref={(node) => {
            sectionRefs.current.filters = node;
          }}
        >
          <div className="panelHeader">
            <h2>Filters</h2>
            <button
              className="textButton"
              type="button"
              onClick={() => {
                setRoleFilter("all");
                setSkillFilter("");
                setShortlistFilter("all");
                setMinExperience("0");
                setMinScore(0);
                setIncludeDeleted(false);
                setSearch("");
              }}
            >
              Clear all
            </button>
          </div>

          <div className="controlGroup">
            <label className="label">
              Job Role
              <select
                className="input"
                value={roleFilter}
                onChange={(event) => setRoleFilter(event.target.value)}
              >
                {ROLE_OPTIONS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>

            <label className="label">
              Skills
              <input
                className="input"
                type="text"
                value={skillFilter}
                onChange={(event) => setSkillFilter(event.target.value)}
                placeholder="React, Python, SQL"
              />
            </label>

            <label className="label">
              Shortlist State
              <select
                className="input"
                value={shortlistFilter}
                onChange={(event) => setShortlistFilter(event.target.value)}
              >
                <option value="all">All candidates</option>
                <option value="shortlisted">Shortlisted only</option>
                <option value="not_shortlisted">Not shortlisted</option>
              </select>
            </label>

            <label className="label">
              Minimum Experience
              <select
                className="input"
                value={minExperience}
                onChange={(event) => setMinExperience(event.target.value)}
              >
                <option value="0">Any</option>
                <option value="2">2+ years</option>
                <option value="5">5+ years</option>
                <option value="8">8+ years</option>
              </select>
            </label>

            <label className="label">
              Match Score
              <input
                className="input"
                type="range"
                min="0"
                max="100"
                value={minScore}
                onChange={(event) => setMinScore(event.target.value)}
              />
            </label>
            <div className="sliderValue">{minScore}% and above</div>
            <label className="checkboxRow">
              <input
                type="checkbox"
                checked={includeDeleted}
                onChange={(event) => setIncludeDeleted(event.target.checked)}
              />
              <span>Show deleted resumes</span>
            </label>
          </div>
        </section>

        <section
          className="panel"
          ref={(node) => {
            sectionRefs.current.uploads = node;
          }}
        >
          <div className="panelHeader">
            <h2>Quick Actions</h2>
            <span>{files.length} file(s) selected</span>
          </div>

          <form className="form" onSubmit={handleSubmit}>
            <label className="uploadZone">
              <input
                className="hiddenInput"
                type="file"
                accept="application/pdf,.pdf"
                multiple
                onChange={(event) =>
                  setFiles(Array.from(event.target.files || []))
                }
              />
              <strong>Upload resumes</strong>
              <span>PDF only, single or batch</span>
            </label>

            <div className="fileList">
              {files.length ? (
                files.map((file) => <span key={file.name}>{file.name}</span>)
              ) : (
                <span>No files selected yet.</span>
              )}
            </div>

            <label className="checkboxRow">
              <input
                type="checkbox"
                checked={useLlm}
                onChange={(event) => setUseLlm(event.target.checked)}
              />
              <span>Use LLM enhancement when available</span>
            </label>

            <label className="label">
              Model
              <input
                className="input"
                type="text"
                value={model}
                onChange={(event) => setModel(event.target.value)}
              />
            </label>

            <label className="label">
              Max retries
              <input
                className="input"
                type="number"
                min="0"
                max="10"
                value={maxRetries}
                onChange={(event) => setMaxRetries(event.target.value)}
              />
            </label>

            <button className="button" type="submit" disabled={loading}>
              {loading
                ? files.length > 1
                  ? "Ranking candidates..."
                  : "Parsing resume..."
                : files.length > 1
                ? "Process Batch"
                : "Parse Resume"}
            </button>
          </form>
        </section>
      </aside>
    </main>
  );
}
