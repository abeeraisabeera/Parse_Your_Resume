import { DEFAULT_SKILLS, ROLE_DEFINITIONS } from "./constants";

async function readJson(response, fallbackMessage) {
  const payload = await response.json().catch(() => ({ error: fallbackMessage }));
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || fallbackMessage);
  }
  return payload;
}

export async function loadSkills() {
  try {
    const response = await fetch("/api/skills", { cache: "no-store" });
    const payload = await readJson(response, "Unable to load managed skills.");
    return payload.skills?.length ? payload.skills : DEFAULT_SKILLS;
  } catch {
    return DEFAULT_SKILLS;
  }
}

export async function saveSkill(skill) {
  const response = await fetch("/api/skills", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(skill)
  });
  const payload = await readJson(response, "Unable to save skill.");
  return payload.skill;
}

export async function removeSkill(skillId) {
  const response = await fetch(`/api/skills/${encodeURIComponent(skillId)}`, {
    method: "DELETE"
  });
  return readJson(response, "Unable to delete skill.");
}

export async function loadRoles() {
  try {
    const response = await fetch("/api/roles", { cache: "no-store" });
    const payload = await readJson(response, "Unable to load roles.");
    return payload.roles?.length ? payload.roles : ROLE_DEFINITIONS.filter((role) => role.id !== "all");
  } catch {
    return ROLE_DEFINITIONS.filter((role) => role.id !== "all");
  }
}

export async function saveRole(role) {
  const response = await fetch("/api/roles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(role)
  });
  const payload = await readJson(response, "Unable to save role.");
  return payload.role;
}

export async function removeRole(roleId) {
  const response = await fetch(`/api/roles/${encodeURIComponent(roleId)}`, {
    method: "DELETE"
  });
  return readJson(response, "Unable to delete role.");
}
