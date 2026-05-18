"use client";

import { PipelineKanban } from "../../../components/pipeline/PipelineKanban";
import { useWorkspaceContext } from "../../../components/workspace/WorkspaceProvider";

export default function PipelinePage() {
  const workspace = useWorkspaceContext();
  return <PipelineKanban workspace={workspace} />;
}
