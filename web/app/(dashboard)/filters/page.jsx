"use client";

import { FiltersWorkspace } from "../../../components/filters/FiltersWorkspace";
import { useWorkspaceContext } from "../../../components/workspace/WorkspaceProvider";

export default function FiltersPage() {
  const workspace = useWorkspaceContext();
  return <FiltersWorkspace workspace={workspace} />;
}
