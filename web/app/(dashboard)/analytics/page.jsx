"use client";

import { AnalyticsWorkspace } from "../../../components/analytics/AnalyticsWorkspace";
import { useWorkspaceContext } from "../../../components/workspace/WorkspaceProvider";

export default function AnalyticsPage() {
  const workspace = useWorkspaceContext();
  return <AnalyticsWorkspace workspace={workspace} />;
}
