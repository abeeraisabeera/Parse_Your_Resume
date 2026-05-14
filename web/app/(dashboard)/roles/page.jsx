"use client";

import { RoleCategories } from "../../../components/roles/RoleCategories";
import { useWorkspaceContext } from "../../../components/workspace/WorkspaceProvider";

export default function RolesPage() {
  const workspace = useWorkspaceContext();
  return <RoleCategories workspace={workspace} />;
}
