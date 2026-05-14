"use client";

import { SettingsWorkspace } from "../../../components/settings/SettingsWorkspace";
import { useWorkspaceContext } from "../../../components/workspace/WorkspaceProvider";

export default function SettingsPage() {
  const workspace = useWorkspaceContext();
  return <SettingsWorkspace workspace={workspace} />;
}
