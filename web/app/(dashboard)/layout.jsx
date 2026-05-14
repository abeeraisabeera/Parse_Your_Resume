import { Suspense } from "react";

import { DashboardShell } from "../../components/layout/DashboardShell";
import { WorkspaceProvider } from "../../components/workspace/WorkspaceProvider";

export default function DashboardLayout({ children }) {
  return (
    <Suspense fallback={<main className="loadingShell">Loading recruiter workspace...</main>}>
      <WorkspaceProvider>
        <DashboardShell>{children}</DashboardShell>
      </WorkspaceProvider>
    </Suspense>
  );
}
