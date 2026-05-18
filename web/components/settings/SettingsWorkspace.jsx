"use client";

import { useState } from "react";

const TABS = [
  { id: "general", label: "General" },
  { id: "parsing", label: "Parsing" },
  { id: "notifications", label: "Notifications" },
  { id: "integrations", label: "Integrations" },
  { id: "api", label: "API" }
];

export function SettingsWorkspace({ workspace }) {
  const { health, useLlm, setUseLlm, model, setModel, maxRetries, setMaxRetries } = workspace;
  const [activeTab, setActiveTab] = useState("parsing");

  return (
    <div className="pageGrid">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Settings</p>
          <h1 className="pageTitle">Account settings</h1>
          <p className="subtle">Parser and workspace configuration for ResumeRank.</p>
        </div>
      </section>

      <div className="settingsLayout">
        <nav className="settingsNav" aria-label="Settings sections">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={activeTab === tab.id ? "active" : ""}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div>
          {activeTab === "parsing" || activeTab === "general" ? (
            <section className="twoColumnGrid alignStart">
              <article className="panel">
                <div className="panelHeader">
                  <h2>Parsing Defaults</h2>
                  <span>Upload workflow</span>
                </div>
                <div className="form">
                  <label className="checkboxRow">
                    <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
                    <span>Use LLM enhancement when available</span>
                  </label>
                  <label className="label">
                    Default model
                    <input className="input" value={model} onChange={(event) => setModel(event.target.value)} />
                  </label>
                  <label className="label">
                    Max retries
                    <input
                      className="input"
                      type="number"
                      min="0"
                      max="10"
                      value={maxRetries}
                      onChange={(event) => setMaxRetries(event.target.value)}
                    />
                  </label>
                </div>
              </article>

              <article className="panel">
                <div className="panelHeader">
                  <h2>Backend Status</h2>
                  <span>{health?.ok ? "Online" : "Unavailable"}</span>
                </div>
                <div className="statusMatrix">
                  <div><span>Parser API</span><strong>{health?.ok ? "Online" : "Offline"}</strong></div>
                  <div><span>LLM Enabled</span><strong>{health?.llm_enabled ? "Yes" : "No"}</strong></div>
                  <div><span>OCR</span><strong>{health?.ocr_available ? "Ready" : "Unavailable"}</strong></div>
                  <div><span>Batch</span><strong>{health?.supports_batch_processing ? "Enabled" : "Checking"}</strong></div>
                  <div><span>Storage</span><strong>{health?.candidate_storage?.backend || "Unknown"}</strong></div>
                  <div><span>Shortlist Threshold</span><strong>{health?.shortlist_threshold || 85}%</strong></div>
                </div>
              </article>
            </section>
          ) : (
            <article className="panel">
              <p className="subtle">This section is reserved for future {activeTab} configuration.</p>
            </article>
          )}

          <div className="settingsStickyBar">
            <button type="button" className="secondaryButton">Discard</button>
            <button type="button" className="button">Save Changes</button>
          </div>
        </div>
      </div>
    </div>
  );
}
