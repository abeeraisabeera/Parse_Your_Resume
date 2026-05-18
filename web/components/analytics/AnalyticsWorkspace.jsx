"use client";

import { useState } from "react";

import {
  buildExperienceDistribution,
  buildRoleAverages,
  buildRoleDistribution,
  buildScoreDistribution,
  buildSeniorityDistribution,
  buildSummary,
  buildTopSkills,
  formatPercent,
  getOverallScore
} from "../../lib/candidateUtils";
import { StatCard } from "../common/StatCard";

const DATE_PRESETS = ["7d", "30d", "90d", "Year", "Custom"];

export function AnalyticsWorkspace({ workspace }) {
  const { filteredCandidates } = workspace;
  const [dateRange, setDateRange] = useState("30d");
  const summary = buildSummary(filteredCandidates);
  const topSkills = buildTopSkills(filteredCandidates, 10);
  const roleDistribution = buildRoleDistribution(filteredCandidates);
  const roleAverages = buildRoleAverages(filteredCandidates);
  const seniorityDistribution = buildSeniorityDistribution(filteredCandidates);
  const experienceDistribution = buildExperienceDistribution(filteredCandidates);
  const scoreDistribution = buildScoreDistribution(filteredCandidates);
  const maxRoleCount = Math.max(...roleDistribution.map((role) => role.count), 1);
  const maxSkillCount = Math.max(...topSkills.map((skill) => skill.count), 1);
  const funnel = [
    { label: "Parsed", count: summary.valid_candidates || 0 },
    { label: "High Match", count: summary.high_match || 0 },
    { label: "Shortlisted", count: summary.shortlisted || 0 }
  ];
  const topCandidateScores = [...filteredCandidates]
    .sort((a, b) => getOverallScore(b) - getOverallScore(a))
    .slice(0, 8);

  return (
    <div className="pageGrid">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Insights</p>
          <h1 className="pageTitle">Analytics</h1>
          <p className="subtle">Analytics respect global filters, including role and managed skill selections.</p>
          <div className="dateRange" role="group" aria-label="Date range">
            {DATE_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                className={dateRange === preset ? "active" : ""}
                onClick={() => setDateRange(preset)}
              >
                {preset}
              </button>
            ))}
          </div>
        </div>
      </section>

      <section className="metricGrid wideMetrics">
        <StatCard label="Total Candidates" value={summary.total_candidates || 0} helper="filtered pool" />
        <StatCard label="Average ATS" value={`${summary.avg_match_score || 0}%`} helper="overall score average" />
        <StatCard label="Parsing Success" value={`${summary.parsing_success_rate || 0}%`} helper="valid parsed resumes" />
        <StatCard label="Shortlisted" value={summary.shortlisted || 0} helper="recruiter or auto selected" />
      </section>

      <section className="analyticsCanvas upgradedAnalytics">
        <article className="panel insightPanel wideInsight">
          <div className="panelHeader">
            <h2>Hiring Funnel</h2>
            <span>Filtered pipeline</span>
          </div>
          <div className="funnelChart">
            {funnel.map((stage, index) => (
              <div className="funnelStage" key={stage.label}>
                <strong>{stage.count}</strong>
                <span>{stage.label}</span>
                <div className="barTrack">
                  <div
                    className="barFill"
                    style={{
                      width: `${summary.valid_candidates ? Math.max(8, (stage.count / summary.valid_candidates) * 100) : 0}%`
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </article>

        <article className="panel insightPanel">
          <div className="panelHeader">
            <h2>Role Mix vs ATS Average</h2>
            <span>{roleDistribution.length} segments</span>
          </div>
          <div className="comparisonList">
            {roleDistribution.map((role) => {
              const average = roleAverages.find((item) => item.role === role.role)?.avgScore || 0;
              return (
              <div className="comparisonRow" key={role.role}>
                <span>{role.label}</span>
                <div className="dualBars">
                  <div className="barTrack" title={`${role.count} candidates`}>
                    <div className="barFill" style={{ width: `${(role.count / maxRoleCount) * 100}%` }} />
                  </div>
                  <div className="barTrack scoreTrack" title={`${average}% average ATS`}>
                    <div className="barFill" style={{ width: `${average}%` }} />
                  </div>
                </div>
                <strong>{role.count} / {formatPercent(average)}</strong>
              </div>
            );
            })}
          </div>
        </article>

        <article className="panel insightPanel">
          <div className="panelHeader">
            <h2>ATS Score Distribution</h2>
            <span>Quality bands</span>
          </div>
          <div className="distributionChart">
            {scoreDistribution.map((bucket) => (
              <div className="distributionColumn" key={bucket.label}>
                <div
                  className="distributionBar"
                  style={{
                    height: `${Math.max(16, (bucket.count / Math.max(filteredCandidates.length, 1)) * 180)}px`
                  }}
                />
                <strong>{bucket.count}</strong>
                <span>{bucket.label}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel insightPanel heatmapPanel">
          <div className="panelHeader">
            <h2>Skill Demand Heatmap</h2>
            <span>Top extracted skills</span>
          </div>
          <div className="heatmapGrid">
            {topSkills.length ? topSkills.map((skill) => (
              <div
                className="heatmapCell"
                key={skill.skill}
                style={{ opacity: 0.58 + (skill.count / maxSkillCount) * 0.42 }}
              >
                <strong>{skill.skill}</strong>
                <span>{skill.count} candidate(s)</span>
              </div>
            )) : <p className="emptyState">No skill heatmap yet.</p>}
          </div>
        </article>

        <article className="panel insightPanel">
          <div className="panelHeader">
            <h2>Seniority & Experience</h2>
            <span>Talent shape</span>
          </div>
          <div className="splitLegend">
            {[...seniorityDistribution, ...experienceDistribution].map((bucket) => (
              <div className="legendItem" key={bucket.key}>
                <strong>{bucket.count || 0}</strong>
                <span>{bucket.label || bucket.level}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel insightPanel">
          <div className="panelHeader">
            <h2>Top Candidate Score Trend</h2>
            <span>Ranked comparison</span>
          </div>
          <div className="sparkList">
            {topCandidateScores.length ? topCandidateScores.map((candidate, index) => (
              <div className="sparkRow" key={candidate.id || candidate.uploaded_file_name || index}>
                <span>#{index + 1} {candidate.name || "Unknown"}</span>
                <div className="barTrack">
                  <div className="barFill" style={{ width: `${getOverallScore(candidate)}%` }} />
                </div>
                <strong>{formatPercent(getOverallScore(candidate))}</strong>
              </div>
            )) : <p className="emptyState">No ranked candidates yet.</p>}
          </div>
        </article>
      </section>
    </div>
  );
}
