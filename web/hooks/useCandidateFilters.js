"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

const STORAGE_KEY = "resumeRank.filters";

const DEFAULT_FILTERS = {
  search: "",
  roleFilter: "all",
  skillFilter: "",
  shortlistFilter: "all",
  minExperience: "0",
  minScore: 0,
  includeDeleted: false,
  education: "",
  parsingConfidence: "0",
  location: "",
  seniority: "all",
  status: "all"
};

function readStoredFilters() {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function filtersFromSearch(searchParams) {
  return {
    search: searchParams.get("search") || "",
    roleFilter: searchParams.get("role") || "all",
    skillFilter: searchParams.get("skills") || "",
    shortlistFilter: searchParams.get("shortlist") || "all",
    minExperience: searchParams.get("min_experience") || "0",
    minScore: Number(searchParams.get("min_score") || 0),
    includeDeleted: searchParams.get("include_deleted") === "true",
    education: searchParams.get("education") || "",
    parsingConfidence: searchParams.get("parsing_confidence") || "0",
    location: searchParams.get("location") || "",
    seniority: searchParams.get("seniority") || "all",
    status: searchParams.get("status") || "all"
  };
}

function hasSearchFilters(searchParams) {
  return [
    "search",
    "role",
    "skills",
    "shortlist",
    "min_experience",
    "min_score",
    "include_deleted",
    "education",
    "parsing_confidence",
    "location",
    "seniority",
    "status"
  ].some((key) => searchParams.has(key));
}

function toSearchParams(filters) {
  const params = new URLSearchParams();
  if (filters.search.trim()) params.set("search", filters.search.trim());
  if (filters.roleFilter !== "all") params.set("role", filters.roleFilter);
  if (filters.skillFilter.trim()) params.set("skills", filters.skillFilter.trim());
  if (filters.shortlistFilter !== "all") params.set("shortlist", filters.shortlistFilter);
  if (Number(filters.minExperience || 0) > 0) params.set("min_experience", filters.minExperience);
  if (Number(filters.minScore || 0) > 0) params.set("min_score", String(filters.minScore));
  if (filters.includeDeleted) params.set("include_deleted", "true");
  if (filters.education.trim()) params.set("education", filters.education.trim());
  if (Number(filters.parsingConfidence || 0) > 0) params.set("parsing_confidence", filters.parsingConfidence);
  if (filters.location.trim()) params.set("location", filters.location.trim());
  if (filters.seniority !== "all") params.set("seniority", filters.seniority);
  if (filters.status !== "all") params.set("status", filters.status);
  return params;
}

export function useCandidateFilters() {
  const searchParams = useSearchParams();
  const pathname = usePathname();
  const router = useRouter();
  const hydratedFromUrl = useRef(false);
  const [filters, setFilters] = useState(() => ({
    ...DEFAULT_FILTERS,
    ...readStoredFilters()
  }));

  useEffect(() => {
    if (!hydratedFromUrl.current && hasSearchFilters(searchParams)) {
      hydratedFromUrl.current = true;
      setFilters((current) => ({
        ...current,
        ...filtersFromSearch(searchParams)
      }));
    }
  }, [searchParams]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(filters));
  }, [filters]);

  useEffect(() => {
    const params = toSearchParams(filters);
    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }, [filters, pathname, router]);

  const setFilter = useCallback((key, value) => {
    setFilters((current) => ({ ...current, [key]: value }));
  }, []);

  const clearFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  const activeFilterChips = useMemo(() => {
    const chips = [];
    if (filters.search) chips.push({ key: "search", label: `Search: ${filters.search}` });
    if (filters.roleFilter !== "all") chips.push({ key: "roleFilter", label: `Role: ${filters.roleFilter}` });
    filters.skillFilter
      .split(/[,;]/)
      .map((skill) => skill.trim())
      .filter(Boolean)
      .forEach((skill) => {
        chips.push({ key: `skillFilter:${skill}`, label: `Skill: ${skill}` });
      });
    if (filters.shortlistFilter !== "all") chips.push({ key: "shortlistFilter", label: `Shortlist: ${filters.shortlistFilter}` });
    if (Number(filters.minExperience) > 0) chips.push({ key: "minExperience", label: `${filters.minExperience}+ yrs` });
    if (Number(filters.minScore) > 0) chips.push({ key: "minScore", label: `${filters.minScore}%+ ATS` });
    if (filters.includeDeleted) chips.push({ key: "includeDeleted", label: "Includes deleted" });
    if (filters.education) chips.push({ key: "education", label: `Education: ${filters.education}` });
    if (Number(filters.parsingConfidence) > 0) chips.push({ key: "parsingConfidence", label: `${filters.parsingConfidence}%+ confidence` });
    if (filters.location) chips.push({ key: "location", label: `Location: ${filters.location}` });
    if (filters.seniority !== "all") chips.push({ key: "seniority", label: `Seniority: ${filters.seniority}` });
    if (filters.status !== "all") chips.push({ key: "status", label: `Status: ${filters.status}` });
    return chips;
  }, [filters]);

  function removeFilter(key) {
    if (key.startsWith("skillFilter:")) {
      const skillToRemove = key.replace("skillFilter:", "").toLowerCase();
      setFilters((current) => ({
        ...current,
        skillFilter: current.skillFilter
          .split(/[,;]/)
          .map((skill) => skill.trim())
          .filter((skill) => skill && skill.toLowerCase() !== skillToRemove)
          .join(", ")
      }));
      return;
    }

    setFilters((current) => ({
      ...current,
      [key]: DEFAULT_FILTERS[key]
    }));
  }

  return {
    filters,
    setFilter,
    setFilters,
    clearFilters,
    activeFilterChips,
    removeFilter
  };
}
