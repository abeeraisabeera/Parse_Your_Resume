"use client";

import { UploadParsingWorkspace } from "../../../components/uploads/UploadParsingWorkspace";
import { useWorkspaceContext } from "../../../components/workspace/WorkspaceProvider";

export default function UploadPage() {
  const workspace = useWorkspaceContext();
  return <UploadParsingWorkspace workspace={workspace} />;
}
