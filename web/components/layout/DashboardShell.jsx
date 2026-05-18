"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useWorkspaceContext } from "../workspace/WorkspaceProvider";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", hint: "Overview" },
  { href: "/candidates", label: "Candidates", hint: "Talent pool" },
  { href: "/upload", label: "Upload & Parsing", hint: "Intake" },
  { href: "/analytics", label: "Analytics", hint: "Insights" },
  { href: "/skills", label: "Skills Management", hint: "Skills" },
  { href: "/roles", label: "Role Categories", hint: "Segments" },
  { href: "/filters", label: "Filters", hint: "Presets" },
  { href: "/settings", label: "Settings", hint: "System" }
];

export function DashboardShell({ children }) {
  const pathname = usePathname();
  const { health, filteredCandidates, activeFilterChips } = useWorkspaceContext();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <main className={`dashboardShell ${collapsed ? "sidebarCollapsed" : ""}`}>
      <aside className="appSidebar" aria-label="Main navigation">
        <div className="brand brandWide">
          <div className="brandMark">R</div>
          <div>
            <strong>ResumeRank</strong>
            <p>Recruiter OS</p>
          </div>
        </div>

        <button
          className="collapseButton"
          type="button"
          onClick={() => setCollapsed((value) => !value)}
          aria-pressed={collapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <span className="collapseIcon" aria-hidden="true">{collapsed ? ">" : "<"}</span>
          <span className="collapseLabel">{collapsed ? "Expand" : "Collapse"}</span>
        </button>

        <nav className="navList">
          {NAV_ITEMS.map((item, index) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`navItem ${active ? "active" : ""}`}
              >
                <span className="navIcon">{index + 1}</span>
                <span className="navText">
                  <strong>{item.label}</strong>
                  <small>{item.hint}</small>
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="sidebarCard systemCard">
          <h3>System Status</h3>
          <div className="statusRow">
            <span>Parser API</span>
            <strong className={health?.ok ? "statusOk" : "statusWarn"}>
              {health?.ok ? "Online" : "Offline"}
            </strong>
          </div>
          <div className="statusRow">
            <span>OCR</span>
            <strong className={health?.ocr_available ? "statusOk" : "statusWarn"}>
              {health?.ocr_available ? "Ready" : "Unavailable"}
            </strong>
          </div>
          <div className="statusRow">
            <span>Batch</span>
            <strong className="statusOk">
              {health?.supports_batch_processing ? "Enabled" : "Checking"}
            </strong>
          </div>
          <div className="statusRow">
            <span>Storage</span>
            <strong className={health?.candidate_storage?.available ? "statusOk" : "statusWarn"}>
              {health?.candidate_storage?.backend || "Checking"}
            </strong>
          </div>
          {health?.ocr_available === false && health?.ocr_detail ? (
            <p className="miniNote">{health.ocr_detail}</p>
          ) : null}
        </div>
      </aside>

      <section className="contentShell">
        <header className="globalTopbar">
          <div>
            <p className="eyebrow">AI-Powered Resume Screening</p>
            <h1>Enterprise ATS Workspace</h1>
            <p className="subtle">
              {filteredCandidates.length} candidate(s) visible
              {activeFilterChips.length ? ` across ${activeFilterChips.length} active filter(s)` : ""}
            </p>
          </div>
          <div className="topbarActions">
            <Link className="secondaryButton" href="/upload">Upload Resumes</Link>
            <Link className="button compactButton" href="/candidates">Browse Candidates</Link>
          </div>
        </header>

        {children}
      </section>
    </main>
  );
}
