import Link from "next/link";

import {
  buildExperienceDistribution,
  buildRoleAverages,
  buildRoleDistribution,
  buildScoreDistribution,
  buildSummary,
  buildTopSkills,
  formatPercent,
  getOverallScore,
  roleLabel
} from "../../lib/candidateUtils";
import { StatCard } from "../common/StatCard";
import { StatusBadge } from "../common/StatusBadge";

export function DashboardOverview({ workspace }) {
  const { filteredCandidates, health } = workspace;
  const summary = buildSummary(filteredCandidates);
  const topSkills = buildTopSkills(filteredCandidates, 6);
  const roleDistribution = buildRoleDistribution(filteredCandidates);
  const roleAverages = buildRoleAverages(filteredCandidates);
  const experienceDistribution = buildExperienceDistribution(filteredCandidates);
  const scoreDistribution = buildScoreDistribution(filteredCandidates);
  const totalExperienceSegments = experienceDistribution.reduce((sum, item) => sum + item.count, 0);
  const totalScoreSegments = scoreDistribution.reduce((sum, item) => sum + item.count, 0);
  const topCandidates = filteredCandidates.slice(0, 5);

  return (
    <div className="pageGrid">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h2>Hiring pipeline overview without operational clutter.</h2>
          <p className="subtle">Use this page for executive signal, then jump into Candidates or Analytics for deeper work.</p>
        </div>
        <Link className="button compactButton" href="/candidates">Review Candidates</Link>
      </section>

      <section className="metricGrid wideMetrics">
        <StatCard label="Total Candidates" value={summary.total_candidates || 0} helper={`${summary.valid_candidates || 0} valid resumes`} />
        <StatCard label="Shortlisted" value={summary.shortlisted || 0} helper="auto or recruiter selected" tone="success" />
        <StatCard label="High Match" value={summary.high_match || 0} helper="75+ ATS score" />
        <StatCard label="Average ATS Score" value={`${summary.avg_match_score || 0}%`} helper={`${summary.avg_experience_years || 0} yrs avg experience`} />
        <StatCard label="Parsing Success" value={`${summary.parsing_success_rate || 0}%`} helper={health?.ok ? "parser API online" : "parser status unavailable"} />
        <StatCard label="Role Categories" value={roleDistribution.length} helper="detected active segments" />
      </section>

      <section className="analyticsGrid dashboardAnalytics">
        <article className="panel soft">
          <div className="panelHeader">
            <h2>Match Score Distribution</h2>
            <span>ATS spread</span>
          </div>
          <div className="histogram">
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
                  <div className="barFill" style={{ width: `${(item.count / Math.max(...topSkills.map((skill) => skill.count), 1)) * 100}%` }} />
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

      <section className="twoColumnGrid">
        <article className="panel">
          <div className="panelHeader">
            <h2>Role Distribution</h2>
            <Link className="textButton" href="/analytics">View analytics</Link>
          </div>
          <div className="roleAnalyticsList">
            {roleDistribution.length ? roleDistribution.map((role) => (
              <div className="roleAnalyticsRow" key={role.role}>
                <span>{role.label}</span>
                <strong>{role.count}</strong>
              </div>
            )) : <p className="emptyState">No role data yet.</p>}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Role-Wise ATS Averages</h2>
            <span>{roleAverages.length} roles</span>
          </div>
          <div className="roleAnalyticsList">
            {roleAverages.length ? roleAverages.map((role) => (
              <div className="roleAnalyticsRow" key={role.role}>
                <span>{role.label}</span>
                <strong>{formatPercent(role.avgScore)}</strong>
              </div>
            )) : <p className="emptyState">No ATS averages yet.</p>}
          </div>
        </article>
      </section>

      <section className="panel">
        <div className="panelHeader">
          <div>
            <h2>Top Ranked Candidates Preview</h2>
            <p className="subtle">Detailed review is kept on the Candidates page.</p>
          </div>
          <Link className="secondaryButton" href="/candidates">Open Candidates</Link>
        </div>
        <div className="previewList">
          {topCandidates.length ? topCandidates.map((candidate) => (
            <div className="previewRow" key={candidate.id || candidate.uploaded_file_name}>
              <span>
                <strong>{candidate.name || "Unknown"}</strong>
                <small>{roleLabel(candidate.role_detected)} - {candidate.estimated_years_of_experience || 0} yrs</small>
              </span>
              <span>{formatPercent(getOverallScore(candidate))}</span>
              <StatusBadge status={candidate.candidate_status} />
            </div>
          )) : <p className="emptyState">Upload resumes to populate top candidates.</p>}
        </div>
      </section>
    </div>
  );
}
