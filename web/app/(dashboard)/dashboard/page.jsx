"use client";

import { DashboardOverview } from "../../../components/dashboard/DashboardOverview";
import { useWorkspaceContext } from "../../../components/workspace/WorkspaceProvider";

export default function DashboardPage() {
  const workspace = useWorkspaceContext();
  return <DashboardOverview workspace={workspace} />;
}
