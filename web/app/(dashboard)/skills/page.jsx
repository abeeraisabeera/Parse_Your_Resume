"use client";

import { SkillsManagement } from "../../../components/skills/SkillsManagement";
import { useWorkspaceContext } from "../../../components/workspace/WorkspaceProvider";

export default function SkillsPage() {
  const workspace = useWorkspaceContext();
  return <SkillsManagement workspace={workspace} />;
}
