"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import {
  IconBell,
  IconChart,
  IconChevron,
  IconFilter,
  IconHome,
  IconKanban,
  IconMenu,
  IconMore,
  IconRoles,
  IconSearch,
  IconSettings,
  IconSkills,
  IconUpload,
  IconUsers
} from "../common/Icons";
import { useTheme } from "../theme/ThemeProvider";
import { useWorkspaceContext } from "../workspace/WorkspaceProvider";

const LOGO_URL = "https://app.digitalisglobal.com/Digitalis_logo_black.png";

const NAV_SECTIONS = [
  {
    label: "HOME",
    items: [{ href: "/dashboard", label: "Dashboard", Icon: IconHome }]
  },
  {
    label: "WORK",
    items: [
      { href: "/candidates", label: "Candidates", Icon: IconUsers },
      { href: "/upload", label: "Upload & Parsing", Icon: IconUpload },
      { href: "/filters", label: "Filters", Icon: IconFilter }
    ]
  },
  {
    label: "HR",
    items: [
      { href: "/pipeline", label: "Pipeline", Icon: IconKanban },
      { href: "/skills", label: "Skills", Icon: IconSkills },
      { href: "/roles", label: "Role Categories", Icon: IconRoles },
      { href: "/analytics", label: "Analytics", Icon: IconChart }
    ]
  },
  {
    label: "SYSTEM",
    items: [{ href: "/settings", label: "Account settings", Icon: IconSettings }]
  }
];

const MOBILE_NAV = [
  { href: "/dashboard", label: "Home", Icon: IconHome },
  { href: "/candidates", label: "Candidates", Icon: IconUsers },
  { href: "/upload", label: "Upload", Icon: IconUpload },
  { href: "/analytics", label: "Analytics", Icon: IconChart },
  { href: "/settings", label: "More", Icon: IconMore }
];

const BREADCRUMB_LABELS = {
  dashboard: "Dashboard",
  candidates: "Candidates",
  upload: "Upload & Parsing",
  analytics: "Analytics",
  skills: "Skills",
  roles: "Role Categories",
  filters: "Filters",
  pipeline: "Pipeline",
  settings: "Settings"
};

function isActive(pathname, href) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function DashboardShell({ children }) {
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
  const { health, filteredCandidates } = useWorkspaceContext();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [compactTopbar, setCompactTopbar] = useState(false);

  const breadcrumb = useMemo(() => {
    const segment = pathname.split("/").filter(Boolean)[0] || "dashboard";
    return BREADCRUMB_LABELS[segment] || "Home";
  }, [pathname]);

  useEffect(() => {
    function onScroll() {
      setCompactTopbar(window.scrollY > 48);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const reviewQueueCount = filteredCandidates.filter(
    (candidate) =>
      !candidate.is_deleted &&
      (candidate.candidate_status === "Needs Review" || candidate.candidate_status === "New")
  ).length;

  return (
    <div className={`appFrame ${collapsed ? "sidebarCollapsed" : ""} ${mobileOpen ? "mobileNavOpen" : ""}`}>
      <header className={`appTopbar ${compactTopbar ? "appTopbar--compact" : ""}`}>
        <div className="topbarLeft">
          <button
            type="button"
            className="iconButton mobileOnly"
            aria-label="Open navigation"
            onClick={() => setMobileOpen(true)}
          >
            <IconMenu />
          </button>
          <Link href="/dashboard" className="brandLockup">
            <Image
              src={LOGO_URL}
              alt="Digitalis Global"
              width={120}
              height={28}
              className={`brandLogo ${theme === "dark" ? "brandLogo--invert" : ""}`}
              unoptimized
            />
            <span className="brandProduct">ResumeRank</span>
          </Link>
        </div>

        <nav className={`topbarBreadcrumb ${compactTopbar ? "topbarBreadcrumb--hidden" : ""}`} aria-label="Breadcrumb">
          <span>Workspace</span>
          <span className="breadcrumbSep" aria-hidden="true">›</span>
          <span>{breadcrumb}</span>
        </nav>

        <div className="topbarRight">
          <label className="topbarSearch" aria-label="Search workspace">
            <IconSearch size={18} />
            <input type="search" placeholder="Search… (⌘K)" readOnly />
            <kbd>⌘K</kbd>
          </label>
          <button type="button" className="iconButton notificationButton" aria-label="Notifications">
            <IconBell />
            {reviewQueueCount > 0 ? <span className="notificationBadge">{reviewQueueCount}</span> : null}
          </button>
          <button type="button" className="userChip" aria-label="User menu">
            <span className="userAvatar" aria-hidden="true">A</span>
            <span className="userMeta">
              <strong>Abeera</strong>
              <small>Team Manager</small>
            </span>
          </button>
        </div>
      </header>

      <div className="appBody">
        <aside className="appSidebar" aria-label="Main navigation">
          <div className="sidebarUserCard">
            <span className="userAvatar userAvatar--lg" aria-hidden="true">A</span>
            <div className="sidebarUserMeta">
              <strong>Abeera</strong>
              <small>Team Manager</small>
              <span className="onlineStatus">
                <span className="onlineDot" aria-hidden="true" />
                Online
              </span>
            </div>
          </div>

          {NAV_SECTIONS.map((section) => (
            <div key={section.label} className="navSection">
              <p className="navSectionLabel">{section.label}</p>
              <nav className="navList">
                {section.items.map((item) => {
                  const active = isActive(pathname, item.href);
                  const Icon = item.Icon;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`navItem ${active ? "active" : ""}`}
                      title={item.label}
                    >
                      <span className="navIcon">
                        <Icon className={active ? "iconActive" : ""} />
                      </span>
                      <span className="navText">{item.label}</span>
                    </Link>
                  );
                })}
              </nav>
            </div>
          ))}

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
              <span>Candidates</span>
              <strong className="statusOk">{filteredCandidates.length}</strong>
            </div>
          </div>

          <button
            type="button"
            className="collapseButton"
            onClick={() => setCollapsed((value) => !value)}
            aria-pressed={collapsed}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <IconChevron className={collapsed ? "collapseIcon--flipped" : ""} />
            <span className="collapseLabel">{collapsed ? "Expand" : "Collapse"}</span>
          </button>
        </aside>

        {mobileOpen ? (
          <button
            type="button"
            className="mobileScrim"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
          />
        ) : null}

        <main className="appMain">
          <div className="pageContent">{children}</div>
        </main>
      </div>

      <nav className="mobileBottomNav" aria-label="Mobile navigation">
        {MOBILE_NAV.map((item) => {
          const active = isActive(pathname, item.href);
          const Icon = item.Icon;
          return (
            <Link key={item.href} href={item.href} className={`mobileNavItem ${active ? "active" : ""}`}>
              <Icon className={active ? "iconActive" : ""} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <button type="button" className="themeFab" onClick={toggleTheme} aria-label="Toggle theme">
        {theme === "dark" ? "Light" : "Dark"}
      </button>
    </div>
  );
}
