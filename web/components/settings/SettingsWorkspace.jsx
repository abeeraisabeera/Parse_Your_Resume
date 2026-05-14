export function SettingsWorkspace({ workspace }) {
  const { health, useLlm, setUseLlm, model, setModel, maxRetries, setMaxRetries } = workspace;

  return (
    <div className="pageGrid">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Settings</p>
          <h2>Parser and workspace configuration.</h2>
          <p className="subtle">Settings preserve the existing backend integration while exposing operational context.</p>
        </div>
      </section>

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
    </div>
  );
}
