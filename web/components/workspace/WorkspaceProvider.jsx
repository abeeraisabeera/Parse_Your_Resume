"use client";

import { createContext, useContext } from "react";

import { useRecruiterWorkspace } from "../../hooks/useRecruiterWorkspace";

const WorkspaceContext = createContext(null);

export function WorkspaceProvider({ children }) {
  const workspace = useRecruiterWorkspace();
  return (
    <WorkspaceContext.Provider value={workspace}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspaceContext() {
  const value = useContext(WorkspaceContext);
  if (!value) {
    throw new Error("useWorkspaceContext must be used inside WorkspaceProvider.");
  }
  return value;
}
