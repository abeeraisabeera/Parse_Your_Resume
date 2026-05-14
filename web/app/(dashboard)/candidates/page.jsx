"use client";

import { CandidateBrowser } from "../../../components/candidates/CandidateBrowser";
import { useWorkspaceContext } from "../../../components/workspace/WorkspaceProvider";

export default function CandidatesPage() {
  const workspace = useWorkspaceContext();
  return <CandidateBrowser workspace={workspace} />;
}
