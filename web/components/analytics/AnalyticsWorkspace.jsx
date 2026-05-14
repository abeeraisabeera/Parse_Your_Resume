import {
  buildExperienceDistribution,
  buildRoleAverages,
  buildRoleDistribution,
  buildScoreDistribution,
  buildSeniorityDistribution,
  buildSummary,
  buildTopSkills,
  formatPercent
} from "../../lib/candidateUtils";
import { StatCard } from "../common/StatCard";

export function AnalyticsWorkspace({ workspace }) {
  const { filteredCandidates } = workspace;
  const summary = buildSummary(filteredCandidates);
  const topSkills = buildTopSkills(filteredCandidates, 10);
  const roleDistribution = buildRoleDistribution(filteredCandidates);
  const roleAverages = buildRoleAverages(filteredCandidates);
  const seniorityDistribution = buildSeniorityDistribution(filteredCandidates);
  const experienceDistribution = buildExperienceDistribution(filteredCandidates);
  const scoreDistribution = buildScoreDistribution(filteredCandidates);

  return (
    <div className="pageGrid">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Analytics</p>
          <h2>Recruiter-oriented intelligence for the active talent pool.</h2>
          <p className="subtle">Analytics respect global filters, including role and managed skill selections.</p>
        </div>
      </section>

      <section className="metricGrid wideMetrics">
        <StatCard label="Total Candidates" value={summary.total_candidates || 0} helper="filtered pool" />
        <StatCard label="Average ATS" value={`${summary.avg_match_score || 0}%`} helper="overall score average" />
        <StatCard label="Parsing Success" value={`${summary.parsing_success_rate || 0}%`} helper="valid parsed resumes" />
        <StatCard label="Shortlisted" value={summary.shortlisted || 0} helper="recruiter or auto selected" />
      </section>

      <section className="analyticsCanvas">
        <article className="panel">
          <div className="panelHeader">
            <h2>Role Distribution</h2>
            <span>{roleDistribution.length} segments</span>
          </div>
          <div className="insightBars">
            {roleDistribution.map((role) => (
              <div className="insightBar" key={role.role}>
                <span>{role.label}</span>
                <div className="barTrack">
                  <div className="barFill" style={{ width: `${(role.count / Math.max(filteredCandidates.length, 1)) * 100}%` }} />
                </div>
                <strong>{role.count}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Role-Wise ATS Averages</h2>
            <span>Quality signal</span>
          </div>
          <div className="insightBars">
            {roleAverages.map((role) => (
              <div className="insightBar" key={role.role}>
                <span>{role.label}</span>
                <div className="barTrack">
                  <div className="barFill" style={{ width: `${role.avgScore}%` }} />
                </div>
                <strong>{formatPercent(role.avgScore)}</strong>
              </div>
            ))}
          </div>
        </article>

        <article className="panel heatmapPanel">
          <div className="panelHeader">
            <h2>Role-Specific Skill Heatmap</h2>
            <span>Top skills</span>
          </div>
          <div className="heatmapGrid">
            {topSkills.length ? topSkills.map((skill) => (
              <div className="heatmapCell" key={skill.skill}>
                <strong>{skill.skill}</strong>
                <span>{skill.count} candidates</span>
              </div>
            )) : <p className="emptyState">No skill heatmap yet.</p>}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Seniority by Role</h2>
            <span>Experience bands</span>
          </div>
          <div className="experienceLegend">
            {seniorityDistribution.map((item) => (
              <div className="legendItem" key={item.level}>
                <strong>{item.count}</strong>
                <span>{item.level}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Experience Distribution</h2>
            <span>Tenure</span>
          </div>
          <div className="experienceLegend">
            {experienceDistribution.map((bucket) => (
              <div className="legendItem" key={bucket.key}>
                <strong>{bucket.count}</strong>
                <span>{bucket.label}</span>
              </div>
            ))}
          </div>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Score Distribution</h2>
            <span>ATS</span>
          </div>
          <div className="experienceLegend">
            {scoreDistribution.map((bucket) => (
              <div className="legendItem" key={bucket.label}>
                <strong>{bucket.count}</strong>
                <span>{bucket.label}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
