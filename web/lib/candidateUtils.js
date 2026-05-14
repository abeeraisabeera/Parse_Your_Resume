import { DEFAULT_SKILL_GROUPS, ROLE_DEFINITIONS } from "./constants";

const ROLE_LABELS = new Map(ROLE_DEFINITIONS.map((role) => [role.id, role.label]));

export function candidateStatus(score) {
  const numeric = Number(score || 0);
  if (numeric >= 85) return "Shortlisted";
  if (numeric >= 70) return "In Review";
  if (numeric >= 50) return "Needs Review";
  return "New";
}

export function statusClassName(status) {
  return (status || "New").toLowerCase().replace(/\s+/g, "-");
}

export function getOverallScore(candidate) {
  return Number(candidate?.overall_score ?? candidate?.ranking_score ?? 0);
}

export function getSkillsMatchScore(candidate) {
  return Number(
    candidate?.skills_match_score ??
      candidate?.ranking_breakdown?.skills_score ??
      0
  );
}

export function getConsistencyScore(candidate) {
  return Number(
    candidate?.consistency_score ?? (candidate?.experience_confidence ?? 0) * 100
  );
}

export function getEvidenceScore(candidate) {
  return Number(candidate?.evidence_score ?? candidate?.resume_quality_score ?? 0);
}

export function formatPercent(value) {
  return `${Math.round(Number(value || 0))}%`;
}

export function candidateKey(candidate) {
  return candidate?.id || candidate?.uploaded_file_name || candidate?.source_file;
}

export function getInitials(name) {
  if (!name) return "NA";
  const parts = name.split(/\s+/).filter(Boolean).slice(0, 2);
  return parts.map((part) => part[0]?.toUpperCase() || "").join("") || "NA";
}

export function roleLabel(role) {
  return ROLE_LABELS.get(role || "general") || role || "General";
}

export function normalizeResponse(payload) {
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

export function buildSummary(results) {
  const scores = results.map((item) => getOverallScore(item));
  const experience = results.map((item) =>
    Number(item.estimated_years_of_experience || 0)
  );
  const validCandidates = results.filter((item) => item.is_valid_resume !== false);
  const completed = results.filter((item) => !item.error && item.is_valid_resume !== false).length;

  return {
    total_candidates: results.length,
    valid_candidates: validCandidates.length,
    shortlisted: results.filter((item) => item.is_shortlisted).length,
    high_match: scores.filter((score) => score >= 75).length,
    avg_match_score: scores.length
      ? Number((scores.reduce((sum, value) => sum + value, 0) / scores.length).toFixed(1))
      : 0,
    avg_experience_years: experience.length
      ? Number(
          (experience.reduce((sum, value) => sum + value, 0) / experience.length).toFixed(1)
        )
      : 0,
    parsing_success_rate: results.length
      ? Number(((completed / results.length) * 100).toFixed(1))
      : 0
  };
}

export function buildTopSkills(results, limit = 8) {
  const counts = new Map();
  results.forEach((candidate) => {
    (candidate.top_skills || candidate.skills || []).forEach((skill) => {
      counts.set(skill, (counts.get(skill) || 0) + 1);
    });
  });

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([skill, count]) => ({ skill, count }));
}

export function buildExperienceDistribution(results) {
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

export function buildScoreDistribution(results) {
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

export function buildRoleDistribution(results) {
  const counts = new Map();
  results.forEach((candidate) => {
    const role = candidate.role_detected || candidate.primary_role || "general";
    counts.set(role, (counts.get(role) || 0) + 1);
  });

  return [...counts.entries()]
    .map(([role, count]) => ({ role, label: roleLabel(role), count }))
    .sort((a, b) => b.count - a.count);
}

export function buildRoleAverages(results) {
  const groups = new Map();
  results.forEach((candidate) => {
    const role = candidate.role_detected || "general";
    const current = groups.get(role) || { role, label: roleLabel(role), count: 0, totalScore: 0 };
    current.count += 1;
    current.totalScore += getOverallScore(candidate);
    groups.set(role, current);
  });

  return [...groups.values()]
    .map((item) => ({
      ...item,
      avgScore: item.count ? Number((item.totalScore / item.count).toFixed(1)) : 0
    }))
    .sort((a, b) => b.avgScore - a.avgScore);
}

export function buildSeniorityDistribution(results) {
  const counts = new Map();
  results.forEach((candidate) => {
    const level = candidate.seniority_level || "unknown";
    counts.set(level, (counts.get(level) || 0) + 1);
  });
  return [...counts.entries()].map(([level, count]) => ({ level, count }));
}

export function buildCandidateParams(filters, limit) {
  const params = new URLSearchParams();
  if (filters.search?.trim()) params.set("search", filters.search.trim());
  if (filters.roleFilter !== "all") params.set("role", filters.roleFilter);
  if (filters.skillFilter?.trim()) params.set("skills", filters.skillFilter.trim());
  if (filters.shortlistFilter !== "all") params.set("shortlist", filters.shortlistFilter);
  if (Number(filters.minExperience || 0) > 0) params.set("min_experience", filters.minExperience);
  if (Number(filters.minScore || 0) > 0) params.set("min_score", String(filters.minScore));
  if (filters.includeDeleted) params.set("include_deleted", "true");
  if (limit) params.set("limit", String(limit));
  return params;
}

export function filterCandidates(results, filters) {
  const query = (filters.search || "").trim().toLowerCase();
  const requiredSkills = (filters.skillFilter || "")
    .split(/[,;]/)
    .map((skill) => skill.trim().toLowerCase())
    .filter(Boolean);
  const experienceFloor = Number(filters.minExperience || 0);
  const scoreFloor = Number(filters.minScore || 0);

  return results.filter((candidate) => {
    const haystack = [
      candidate.name,
      candidate.email,
      candidate.current_role,
      candidate.role_detected,
      candidate.uploaded_file_name,
      ...(candidate.top_skills || []),
      ...(candidate.skills || [])
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    const matchesSearch = !query || haystack.includes(query);
    const matchesRole =
      filters.roleFilter === "all" ||
      candidate.role_detected === filters.roleFilter ||
      (candidate.secondary_roles || []).includes(filters.roleFilter);
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
      filters.shortlistFilter === "all" ||
      (filters.shortlistFilter === "shortlisted" && candidate.is_shortlisted) ||
      (filters.shortlistFilter === "not_shortlisted" && !candidate.is_shortlisted);
    const matchesExperience =
      Number(candidate.estimated_years_of_experience || 0) >= experienceFloor;
    const matchesScore = getOverallScore(candidate) >= scoreFloor;
    const matchesDeleted = filters.includeDeleted || !candidate.is_deleted;

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
}

export function sortCandidates(results, sortKey) {
  const sorted = [...results];
  sorted.sort((a, b) => {
    if (sortKey === "experience") {
      return Number(b.estimated_years_of_experience || 0) - Number(a.estimated_years_of_experience || 0);
    }
    if (sortKey === "name") {
      return String(a.name || "").localeCompare(String(b.name || ""));
    }
    if (sortKey === "recent") {
      return String(b.created_at || "").localeCompare(String(a.created_at || ""));
    }
    return getOverallScore(b) - getOverallScore(a);
  });
  return sorted.map((candidate, index) => ({ ...candidate, rank: index + 1 }));
}

export function groupCandidatesByRole(results) {
  const grouped = new Map();
  results.forEach((candidate) => {
    const role = candidate.role_detected || "general";
    const list = grouped.get(role) || [];
    list.push(candidate);
    grouped.set(role, list);
  });

  return [...grouped.entries()]
    .map(([role, candidates]) => ({
      role,
      label: roleLabel(role),
      count: candidates.length,
      candidates
    }))
    .sort((a, b) => b.count - a.count);
}

export function skillGroupsFromTaxonomy(skills) {
  if (!skills?.length) return DEFAULT_SKILL_GROUPS;
  const grouped = new Map();
  skills.forEach((skill) => {
    const category = skill.category || "Managed Skills";
    const options = grouped.get(category) || [];
    options.push([skill.id || skill.name || skill.label, skill.label || skill.name || skill.id]);
    grouped.set(category, options);
  });
  return [...grouped.entries()].map(([label, options]) => ({ label, options }));
}

export function roleSkillSet(skills, role) {
  return new Set(
    (skills || [])
      .filter((skill) => (skill.roles || []).includes(role))
      .map((skill) => String(skill.id || skill.name || skill.label).toLowerCase())
  );
}

export function candidateMissingSkills(candidate, skills) {
  const role = candidate?.role_detected || "general";
  const required = roleSkillSet(skills, role);
  if (!required.size) return [];
  const candidateSkills = new Set(
    [...(candidate?.skills || []), ...(candidate?.top_skills || [])].map((skill) =>
      String(skill).toLowerCase()
    )
  );
  return [...required]
    .filter((skill) => !candidateSkills.has(skill))
    .slice(0, 8);
}

export function roleConfidence(candidate) {
  const explicit = Number(candidate?.role_confidence ?? 0);
  if (explicit) return explicit;
  const skills = candidate?.skills?.length || candidate?.top_skills?.length || 0;
  const score = getOverallScore(candidate);
  return Math.min(96, Math.max(35, Math.round(score * 0.55 + skills * 4)));
}
