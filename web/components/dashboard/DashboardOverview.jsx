"use client";

import Link from "next/link";
import { useState } from "react";

import {
  buildExperienceDistribution,
  buildScoreDistribution,
  buildSummary,
  buildTopSkills,
  formatPercent,
  getOverallScore,
  roleLabel
} from "../../lib/candidateUtils";
import { IconFolder, IconStar, IconTarget, IconTrend } from "../common/Icons";
import { StatCard } from "../common/StatCard";
import { StatusBadge } from "../common/StatusBadge";

const CHART_TABS = ["Score distribution", "Top skills", "Experience"];

function formatDate() {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric"
  }).format(new Date());
}

export function DashboardOverview({ workspace }) {
  const { filteredCandidates, health } = workspace;
  const [chartTab, setChartTab] = useState(CHART_TABS[0]);
  const summary = buildSummary(filteredCandidates);
  const topSkills = buildTopSkills(filteredCandidates, 8);
  const scoreDistribution = buildScoreDistribution(filteredCandidates);
  const experienceDistribution = buildExperienceDistribution(filteredCandidates);
  const totalScoreSegments = scoreDistribution.reduce((sum, item) => sum + item.count, 0);
  const totalExperienceSegments = experienceDistribution.reduce((sum, item) => sum + item.count, 0);
  const topCandidates = filteredCandidates.slice(0, 5);

  return (
    <div className="pageGrid">
      <section className="dg-hero">
        <div>
          <p className="dg-label">Overview</p>
          <h1 className="dg-page-title">Welcome back</h1>
          <p className="subtle">{formatDate()} · {filteredCandidates.length} candidates in workspace</p>
        </div>
        <div className="dg-hero-actions">
          <Link className="secondaryButton" href="/upload">
            Upload resumes
          </Link>
          <Link className="button" href="/candidates">
            Review candidates
          </Link>
        </div>
      </section>

      <section className="dg-kpi-grid" aria-label="Key metrics">
        <StatCard
          label="Total candidates"
          value={summary.total_candidates || 0}
          helper={`${summary.valid_candidates || 0} valid parsed`}
          icon={IconFolder}
        />
        <StatCard
          label="Shortlisted"
          value={summary.shortlisted || 0}
          helper="Auto or manual selection"
          tone="success"
          icon={IconStar}
        />
        <StatCard
          label="High match"
          value={summary.high_match || 0}
          helper="75+ ATS score"
          icon={IconTarget}
        />
        <StatCard
          label="Average ATS score"
          value={`${summary.avg_match_score || 0}%`}
          helper={health?.ok ? "Parser online" : "Parser unavailable"}
          icon={IconTrend}
        />
      </section>

      <article className="dg-card">
        <div className="dg-card-header">
          <div>
            <h2 className="dg-card-title">Talent insights</h2>
            <p className="dg-card-subtitle">Filtered pool analytics</p>
          </div>
          <div className="dg-tabs" role="tablist" aria-label="Chart views">
            {CHART_TABS.map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={chartTab === tab}
                className={`dg-tab ${chartTab === tab ? "is-active" : ""}`}
                onClick={() => setChartTab(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
        </div>

        {chartTab === "Score distribution" ? (
          <div className="histogram" role="img" aria-label="ATS score distribution">
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
        ) : null}

        {chartTab === "Top skills" ? (
          <div className="bars">
            {topSkills.length ? (
              topSkills.map((item) => (
                <div className="barRow" key={item.skill}>
                  <span>{item.skill}</span>
                  <div className="barTrack">
                    <div
                      className="barFill"
                      style={{
                        width: `${(item.count / Math.max(...topSkills.map((s) => s.count), 1)) * 100}%`
                      }}
                    />
                  </div>
                  <strong>{item.count}</strong>
                </div>
              ))
            ) : (
              <p className="hintText">Upload resumes to populate skill trends.</p>
            )}
          </div>
        ) : null}

        {chartTab === "Experience" ? (
          <>
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
                    width: `${totalExperienceSegments ? (bucket.count / totalExperienceSegments) * 100 : 25}%`
                  }}
                  title={`${bucket.label}: ${bucket.count}`}
                />
              ))}
            </div>
          </>
        ) : null}
      </article>

      <article className="dg-card">
        <div className="dg-card-header">
          <div>
            <h2 className="dg-card-title">Top ranked candidates</h2>
            <p className="dg-card-subtitle">Highest ATS scores in current filter</p>
          </div>
          <Link className="dg-btn-ghost" href="/candidates">
            View all
          </Link>
        </div>
        <div className="previewList">
          {topCandidates.length ? (
            topCandidates.map((candidate) => (
              <div className="previewRow" key={candidate.id || candidate.uploaded_file_name}>
                <span>
                  <strong>{candidate.name || "Unknown"}</strong>
                  <small>
                    {roleLabel(candidate.role_detected)} · {candidate.estimated_years_of_experience || 0} yrs
                  </small>
                </span>
                <span className="previewScore">{formatPercent(getOverallScore(candidate))}</span>
                <StatusBadge status={candidate.candidate_status} />
              </div>
            ))
          ) : (
            <p className="emptyState">Upload resumes to see ranked candidates.</p>
          )}
        </div>
      </article>
    </div>
  );
}
