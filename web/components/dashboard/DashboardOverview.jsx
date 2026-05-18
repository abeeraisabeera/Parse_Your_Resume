"use client";

import Link from "next/link";
import { useState } from "react";

import {
  buildExperienceDistribution,
  buildRoleDistribution,
  buildScoreDistribution,
  buildSummary,
  buildTopSkills,
  getOverallScore,
  roleLabel
} from "../../lib/candidateUtils";
import { IconChart, IconClock, IconFolder, IconTimer } from "../common/Icons";
import { ScoreBadge } from "../common/ScoreBadge";
import { StatusBadge } from "../common/StatusBadge";

const SUB_TABS = ["Projects", "My tasks", "Inbox", "Attendance", "Leave", "Remote"];

function formatToday() {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric"
  }).format(new Date());
}

export function DashboardOverview({ workspace }) {
  const { filteredCandidates, health } = workspace;
  const [activeTab, setActiveTab] = useState("Projects");
  const summary = buildSummary(filteredCandidates);
  const topSkills = buildTopSkills(filteredCandidates, 6);
  const roleDistribution = buildRoleDistribution(filteredCandidates);
  const scoreDistribution = buildScoreDistribution(filteredCandidates);
  const experienceDistribution = buildExperienceDistribution(filteredCandidates);
  const totalScoreSegments = scoreDistribution.reduce((sum, item) => sum + item.count, 0);
  const totalExperienceSegments = experienceDistribution.reduce((sum, item) => sum + item.count, 0);
  const topCandidates = filteredCandidates.slice(0, 5);
  const projectCount = Math.max(roleDistribution.length, 1);

  return (
    <div className="pageGrid">
      <section className="heroCard">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h1 className="pageTitle">Hiring Pipeline</h1>
          <p className="subtle">
            Welcome back, Abeera 👋 · {formatToday()} · Remote (YTD): 0 approved days
          </p>
        </div>
        <div className="heroActions">
          <Link className="pillButton" href="/candidates">View projects</Link>
          <Link className="pillButton pillButton--primary" href="/upload">+ New project</Link>
          <button type="button" className="pillButton">Start timer</button>
          <button type="button" className="pillButton">New client</button>
          <button type="button" className="pillButton">Invite member</button>
        </div>
      </section>

      <nav className="subNavTabs" aria-label="Dashboard sections">
        <ul className="subNavList">
          {SUB_TABS.map((tab) => (
            <li key={tab}>
              <button
                type="button"
                className={activeTab === tab ? "active" : ""}
                onClick={() => setActiveTab(tab)}
              >
                {tab}
              </button>
            </li>
          ))}
        </ul>
        <span className="subtle">{projectCount} project{projectCount === 1 ? "" : "s"}</span>
      </nav>

      <section className="todayCard">
        <header>
          <div>
            <h2 className="sectionTitle">Today</h2>
            <p className="subtle">{formatToday()}</p>
          </div>
          <p className="subtle">You have not checked in yet today</p>
        </header>
        <div className="heroActions">
          <button type="button" className="pillButton pillButton--primary">Check in</button>
          <button type="button" className="pillButton">Check out</button>
          <button type="button" className="pillButton pillButton--muted">Start break</button>
          <button type="button" className="pillButton pillButton--muted">End break</button>
        </div>
        <Link className="textButton" href="/candidates">
          Full attendance &amp; history →
        </Link>
      </section>

      <section className="kpiRow" aria-label="Key metrics">
        <article className="kpiCard">
          <span className="kpiIcon" aria-hidden="true"><IconFolder /></span>
          <span className="kpiLabel">Active projects</span>
          <strong>{projectCount}</strong>
          <small>In your workspace scope</small>
        </article>
        <article className="kpiCard">
          <span className="kpiIcon" aria-hidden="true"><IconChart /></span>
          <span className="kpiLabel">Team utilization</span>
          <strong>—</strong>
          <small>Placeholder metric</small>
        </article>
        <article className="kpiCard">
          <span className="kpiIcon" aria-hidden="true"><IconClock /></span>
          <span className="kpiLabel">Overdue tasks</span>
          <strong>0</strong>
          <small>Assigned to you</small>
        </article>
        <article className="kpiCard">
          <span className="kpiIcon" aria-hidden="true"><IconTimer /></span>
          <span className="kpiLabel">Hours logged</span>
          <strong>0s</strong>
          <small>Log time from a project page</small>
        </article>
      </section>

      <section className="metricGrid wideMetrics">
        <article className="kpiCard">
          <span className="kpiLabel">Total candidates</span>
          <strong>{summary.total_candidates || 0}</strong>
          <small>{summary.valid_candidates || 0} valid resumes</small>
        </article>
        <article className="kpiCard">
          <span className="kpiLabel">Shortlisted</span>
          <strong>{summary.shortlisted || 0}</strong>
          <small>Auto or recruiter selected</small>
        </article>
        <article className="kpiCard">
          <span className="kpiLabel">High match</span>
          <strong>{summary.high_match || 0}</strong>
          <small>75+ ATS score</small>
        </article>
        <article className="kpiCard">
          <span className="kpiLabel">Average ATS</span>
          <strong>{summary.avg_match_score || 0}%</strong>
          <small>{summary.avg_experience_years || 0} yrs avg experience</small>
        </article>
        <article className="kpiCard">
          <span className="kpiLabel">Parsing success</span>
          <strong>{summary.parsing_success_rate || 0}%</strong>
          <small>{health?.ok ? "Parser API online" : "Parser status unavailable"}</small>
        </article>
      </section>

      <section className="analyticsGrid dashboardAnalytics">
        <article className="panel soft">
          <div className="panelHeader">
            <h2>Match Score Distribution</h2>
            <span>ATS spread</span>
          </div>
          <div className="histogram" role="img" aria-label="ATS score distribution histogram">
            {scoreDistribution.map((bucket) => (
              <div className="histogramColumn" key={bucket.label}>
                <div
                  className="histogramBar"
                  style={{
                    height: `${totalScoreSegments ? Math.max(18, (bucket.count / totalScoreSegments) * 150) : 18}px`
                  }}
                />
                <span>{bucket.label}</span>
                <strong>{bucket.count}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="panel soft">
          <div className="panelHeader">
            <h2>Top Skills</h2>
            <span>Frequency</span>
          </div>
          <div className="bars">
            {topSkills.length ? topSkills.map((item) => (
              <div className="barRow" key={item.skill}>
                <span>{item.skill}</span>
                <div className="barTrack">
                  <div
                    className="barFill"
                    style={{ width: `${(item.count / Math.max(...topSkills.map((skill) => skill.count), 1)) * 100}%` }}
                  />
                </div>
                <strong>{item.count}</strong>
              </div>
            )) : <p className="hintText">Upload resumes to populate skill trends.</p>}
          </div>
        </article>

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
                style={{ width: `${totalExperienceSegments ? (bucket.count / totalExperienceSegments) * 100 : 25}%` }}
                title={`${bucket.label}: ${bucket.count}`}
              />
            ))}
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panelHeader">
          <div>
            <h2>Top Ranked Candidates</h2>
            <p className="subtle">Quick preview — open Candidates for full review.</p>
          </div>
          <Link className="secondaryButton" href="/candidates">Open Candidates</Link>
        </div>
        <div className="previewList">
          {topCandidates.length ? topCandidates.map((candidate) => (
            <div className="previewRow" key={candidate.id || candidate.uploaded_file_name}>
              <span>
                <strong>{candidate.name || "Unknown"}</strong>
                <small>{roleLabel(candidate.role_detected)} · {candidate.estimated_years_of_experience || 0} yrs</small>
              </span>
              <ScoreBadge score={getOverallScore(candidate)} />
              <StatusBadge status={candidate.candidate_status} />
            </div>
          )) : <p className="emptyState">Upload resumes to populate top candidates.</p>}
        </div>
      </section>
    </div>
  );
}
