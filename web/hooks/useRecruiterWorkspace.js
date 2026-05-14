"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  deleteCandidate,
  loadCandidates,
  loadHealth,
  parseResumes,
  updateShortlist
} from "../lib/candidateApi";
import {
  candidateKey,
  filterCandidates,
  sortCandidates
} from "../lib/candidateUtils";
import { DEFAULT_MODEL } from "../lib/constants";
import { loadRoles, loadSkills } from "../lib/taxonomyApi";
import { useCandidateFilters } from "./useCandidateFilters";

export function useRecruiterWorkspace() {
  const filterState = useCandidateFilters();
  const [files, setFiles] = useState([]);
  const [uploadQueue, setUploadQueue] = useState([]);
  const [useLlm, setUseLlm] = useState(true);
  const [model, setModel] = useState(DEFAULT_MODEL);
  const [maxRetries, setMaxRetries] = useState(6);
  const [dashboard, setDashboard] = useState({ mode: "stored", results: [], summary: {} });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState(null);
  const [selectedCandidateKey, setSelectedCandidateKey] = useState(null);
  const [actionLoading, setActionLoading] = useState("");
  const [viewMode, setViewMode] = useState("list");
  const [sortKey, setSortKey] = useState("score");
  const [page, setPage] = useState(1);
  const [skills, setSkills] = useState([]);
  const [roles, setRoles] = useState([]);

  const refreshCandidates = useCallback(
    async (preferredKey = null) => {
      const normalized = await loadCandidates({
        includeDeleted: filterState.filters.includeDeleted
      });
      setDashboard(normalized);
      const firstKey =
        preferredKey ||
        candidateKey(normalized.results?.[0]) ||
        null;
      setSelectedCandidateKey(firstKey);
      return normalized;
    },
    [filterState.filters.includeDeleted]
  );

  useEffect(() => {
    let cancelled = false;

    loadHealth()
      .then((payload) => {
        if (!cancelled) setHealth(payload);
      })
      .catch((healthError) => {
        if (!cancelled) setHealth({ ok: false, error: healthError.message });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    refreshCandidates()
      .catch((loadError) => {
        if (!cancelled) {
          setDashboard({ mode: "stored", results: [], summary: {} });
          setError(loadError.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [refreshCandidates]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([loadSkills(), loadRoles()])
      .then(([loadedSkills, loadedRoles]) => {
        if (cancelled) return;
        setSkills(loadedSkills);
        setRoles(loadedRoles);
      })
      .catch(() => {
        if (!cancelled) {
          setSkills([]);
          setRoles([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filteredCandidates = useMemo(() => {
    const results = dashboard?.results || [];
    const filtered = filterCandidates(results, filterState.filters).filter((candidate) => {
      const education = filterState.filters.education.trim().toLowerCase();
      const location = filterState.filters.location.trim().toLowerCase();
      const status = filterState.filters.status;
      const seniority = filterState.filters.seniority;
      const confidence = Number(filterState.filters.parsingConfidence || 0);
      const confidenceValue = Number(candidate.experience_confidence || 0) * 100;
      const educationMatch =
        !education || String(candidate.education || "").toLowerCase().includes(education);
      const locationMatch =
        !location || String(candidate.location || "").toLowerCase().includes(location);
      const statusMatch =
        status === "all" || String(candidate.candidate_status || "").toLowerCase() === status;
      const seniorityMatch =
        seniority === "all" || candidate.seniority_level === seniority;
      const confidenceMatch = confidenceValue >= confidence;
      return educationMatch && locationMatch && statusMatch && seniorityMatch && confidenceMatch;
    });
    return sortCandidates(filtered, sortKey);
  }, [dashboard, filterState.filters, sortKey]);

  const selectedCandidate = useMemo(() => {
    if (!filteredCandidates.length) return null;
    return (
      filteredCandidates.find((candidate) => candidateKey(candidate) === selectedCandidateKey) ||
      filteredCandidates[0]
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

  function selectFiles(nextFiles) {
    const selected = Array.from(nextFiles || []);
    setFiles(selected);
    setUploadQueue(
      selected.map((file) => ({
        id: `${file.name}-${file.size}-${file.lastModified}`,
        name: file.name,
        size: file.size,
        status: "waiting",
        message: "Ready to parse"
      }))
    );
  }

  async function submitUpload(event) {
    event?.preventDefault?.();
    if (!files.length) {
      setError("Select at least one PDF resume before submitting.");
      return;
    }

    setLoading(true);
    setError("");
    setUploadQueue((queue) => queue.map((item) => ({ ...item, status: "uploading", message: "Uploading" })));

    try {
      setUploadQueue((queue) => queue.map((item) => ({ ...item, status: "parsing", message: "Parsing resume" })));
      const normalized = await parseResumes({ files, useLlm, model, maxRetries });
      const preferredKey = candidateKey(normalized.results[0]);
      await refreshCandidates(preferredKey);
      const storageIssue = normalized.results.find((candidate) => candidate.storage_error);
      setUploadQueue((queue) =>
        queue.map((item, index) => {
          const parsed = normalized.results[index];
          return {
            ...item,
            status: parsed?.error ? "failed" : "completed",
            message: parsed?.error || parsed?.candidate_status || "Completed"
          };
        })
      );
      if (storageIssue) {
        setError(`Parsed successfully, but storage failed: ${storageIssue.storage_error}`);
      }
      setFiles([]);
    } catch (submitError) {
      setUploadQueue((queue) =>
        queue.map((item) => ({ ...item, status: "failed", message: submitError.message }))
      );
      setError(submitError.message);
    } finally {
      setLoading(false);
    }
  }

  async function toggleShortlist(candidate = selectedCandidate) {
    if (!candidate?.id) return;
    setActionLoading("shortlist");
    setError("");
    try {
      const payload = await updateShortlist(candidate.id, !candidate.is_shortlisted);
      setDashboard((current) => ({
        ...current,
        results: (current?.results || []).map((item) =>
          item.id === payload.id ? payload : item
        )
      }));
      setSelectedCandidateKey(payload.id);
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setActionLoading("");
    }
  }

  async function removeCandidate(candidate = selectedCandidate) {
    if (!candidate?.id) return;
    const confirmed = window.confirm("Delete this outdated resume from the active list?");
    if (!confirmed) return;
    setActionLoading("delete");
    setError("");
    try {
      await deleteCandidate(candidate.id);
      await refreshCandidates();
    } catch (actionError) {
      setError(actionError.message);
    } finally {
      setActionLoading("");
    }
  }

  function refreshTaxonomy(nextSkills, nextRoles = roles) {
    setSkills(nextSkills);
    setRoles(nextRoles);
  }

  return {
    ...filterState,
    files,
    uploadQueue,
    useLlm,
    model,
    maxRetries,
    dashboard,
    error,
    loading,
    health,
    selectedCandidate,
    selectedCandidateKey,
    actionLoading,
    viewMode,
    sortKey,
    page,
    skills,
    roles,
    filteredCandidates,
    setFiles: selectFiles,
    setUseLlm,
    setModel,
    setMaxRetries,
    setError,
    setSelectedCandidateKey,
    setViewMode,
    setSortKey,
    setPage,
    setSkills,
    setRoles,
    refreshCandidates,
    refreshTaxonomy,
    submitUpload,
    toggleShortlist,
    removeCandidate
  };
}
