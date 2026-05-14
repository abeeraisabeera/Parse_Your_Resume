import { buildCandidateParams, normalizeResponse } from "./candidateUtils";

async function readJson(response, fallbackMessage) {
  const payload = await response.json().catch(() => ({ error: fallbackMessage }));
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || fallbackMessage);
  }
  return payload;
}

export async function loadHealth() {
  const response = await fetch("/api/healthz", { cache: "no-store" });
  return readJson(response, "Unable to load parser health.");
}

export async function loadCandidates({ includeDeleted = false } = {}) {
  const params = new URLSearchParams();
  if (includeDeleted) params.set("include_deleted", "true");
  params.set("limit", "1000");
  const response = await fetch(`/api/candidates?${params.toString()}`, {
    cache: "no-store"
  });
  return normalizeResponse(
    await readJson(response, "Unable to load stored candidates.")
  );
}

export async function parseResumes({ files, useLlm, model, maxRetries }) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("use_llm", String(useLlm));
  formData.append("model", model);
  formData.append("max_retries", String(maxRetries));

  const response = await fetch("/api/parse", {
    method: "POST",
    body: formData
  });
  return normalizeResponse(await readJson(response, "Parsing failed."));
}

export async function updateShortlist(candidateId, isShortlisted) {
  const response = await fetch(`/api/candidates/${candidateId}/shortlist`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ is_shortlisted: isShortlisted })
  });
  return readJson(response, "Unable to update shortlist.");
}

export async function deleteCandidate(candidateId) {
  const response = await fetch(`/api/candidates/${candidateId}`, {
    method: "DELETE"
  });
  return readJson(response, "Unable to delete candidate.");
}

export function exportCandidates(filters, visibleCount) {
  const params = buildCandidateParams(filters, Math.max(visibleCount, 1));
  window.location.href = `/api/candidates/export?${params.toString()}`;
}
