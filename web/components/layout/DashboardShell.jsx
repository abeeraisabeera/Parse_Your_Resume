"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  IconBell,
  IconChart,
  IconChevronLeft,
  IconDashboard,
  IconFilter,
  IconMenu,
  IconMoon,
  IconRoles,
  IconSearch,
  IconSettings,
  IconSkills,
  IconSun,
  IconUpload,
  IconUsers
} from "../common/Icons";
import { useTheme } from "../theme/ThemeProvider";
import { useWorkspaceContext } from "../workspace/WorkspaceProvider";

const LOGO_URL = "https://app.digitalisglobal.com/Digitalis_logo_black.png";

const NAV = [
  { href: "/dashboard", label: "Dashboard", Icon: IconDashboard },
  { href: "/candidates", label: "Candidates", Icon: IconUsers },
  { href: "/upload", label: "Upload & Parsing", Icon: IconUpload },
  { href: "/analytics", label: "Analytics", Icon: IconChart },
  { href: "/skills", label: "Skills", Icon: IconSkills },
  { href: "/roles", label: "Role Categories", Icon: IconRoles },
  { href: "/filters", label: "Filters", Icon: IconFilter },
  { href: "/settings", label: "Settings", Icon: IconSettings }
];

const PAGE_NAMES = {
  dashboard: "Dashboard",
  candidates: "Candidates",
  upload: "Upload & Parsing",
  analytics: "Analytics",
  skills: "Skills",
  roles: "Role Categories",
  filters: "Filters",
  settings: "Settings"
};

function isActive(pathname, href) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function DashboardShell({ children }) {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const { health } = useWorkspaceContext();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const pageName = useMemo(() => {
    const key = pathname.split("/").filter(Boolean)[0] || "dashboard";
    return PAGE_NAMES[key] || "Dashboard";
  }, [pathname]);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  useEffect(() => {
    function onResize() {
      if (window.innerWidth < 1280 && window.innerWidth >= 768) {
        setCollapsed(true);
      }
    }
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  const frameClass = [
    "dg-app",
    collapsed ? "is-collapsed" : "",
    mobileOpen ? "is-mobile-open" : ""
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={frameClass}>
      <aside className="dg-sidebar" aria-label="Sidebar navigation">
        <div className="dg-logo-area">
          <Link href="/dashboard" className="dg-logo-link" title="Digitalis Global">
            <Image src={LOGO_URL} alt="Digitalis Global" width={140} height={36} className="dg-logo" unoptimized priority />
          </Link>
        </div>

        <nav className="dg-nav">
          <p className="dg-section-label">Recruiting</p>
          <ul className="dg-nav-list">
            {NAV.map((item) => {
              const active = isActive(pathname, item.href);
              const Icon = item.Icon;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={`dg-nav-item ${active ? "is-active" : ""}`}
                    title={item.label}
                  >
                    <Icon size={20} />
                    <span className="dg-nav-label">{item.label}</span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="dg-status-card">
          <h3>Parser status</h3>
          <div className="statusRow">
            <span>API</span>
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
        </div>

        <div className="dg-collapse-wrap">
          <button
            type="button"
            className="dg-collapse-btn"
            onClick={() => setCollapsed((v) => !v)}
            aria-pressed={collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <IconChevronLeft size={18} />
            <span className="dg-collapse-text">{collapsed ? "Expand" : "Collapse"}</span>
          </button>
        </div>
      </aside>

      {mobileOpen ? (
        <button type="button" className="dg-scrim" aria-label="Close menu" onClick={() => setMobileOpen(false)} />
      ) : null}

      <div className="dg-main-wrap">
        <header className="dg-topbar">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              type="button"
              className="dg-icon-btn dg-hamburger"
              aria-label="Open menu"
              onClick={() => setMobileOpen(true)}
            >
              <IconMenu size={18} />
            </button>
            <nav className="dg-breadcrumb" aria-label="Breadcrumb">
              <span>Workspace</span>
              <span aria-hidden="true">›</span>
              <strong>{pageName}</strong>
            </nav>
          </div>

          <div className="dg-topbar-right">
            <label className="dg-search">
              <IconSearch size={18} />
              <input type="search" placeholder="Search..." aria-label="Search" />
            </label>
            <button
              type="button"
              className="dg-icon-btn"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {theme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
            </button>
            <div className="dg-notify-wrap">
              <button type="button" className="dg-icon-btn" aria-label="Notifications">
                <IconBell size={18} />
              </button>
              <span className="dg-notify-dot" aria-hidden="true" />
            </div>
            <span className="dg-avatar" aria-hidden="true">
              RR
            </span>
          </div>
        </header>

        <main className="dg-content">{children}</main>
      </div>
    </div>
  );
}
