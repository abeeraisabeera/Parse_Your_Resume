"use client";

export function UploadParsingWorkspace({ workspace }) {
  const {
    files,
    uploadQueue,
    setFiles,
    useLlm,
    setUseLlm,
    model,
    setModel,
    maxRetries,
    setMaxRetries,
    loading,
    submitUpload,
    error
  } = workspace;

  function handleDrop(event) {
    event.preventDefault();
    setFiles(Array.from(event.dataTransfer.files || []).filter((file) => file.type === "application/pdf" || file.name.endsWith(".pdf")));
  }

  return (
    <div className="pageGrid">
      <section className="pageHero">
        <div>
          <p className="eyebrow">Upload & Parsing</p>
          <h2>Dedicated resume intake workflow.</h2>
          <p className="subtle">Batch PDF uploads still use the existing `/api/parse` proxy and FastAPI parsing pipeline.</p>
        </div>
      </section>

      {error ? <div className="message error">{error}</div> : null}

      <section className="uploadWorkflow">
        <article className="panel">
          <div className="panelHeader">
            <div>
              <h2>Resume Upload</h2>
              <p className="subtle">PDF only, single or batch.</p>
            </div>
            <span className="tableCount">{files.length} file(s) selected</span>
          </div>

          <form className="form" onSubmit={submitUpload}>
            <label
              className={`uploadZone largeUpload ${loading ? "isLoading" : ""}`}
              onDragOver={(event) => event.preventDefault()}
              onDrop={handleDrop}
            >
              <input
                className="hiddenInput"
                type="file"
                accept="application/pdf,.pdf"
                multiple
                onChange={(event) => setFiles(Array.from(event.target.files || []))}
              />
              <strong>Drag and drop resumes here</strong>
              <span>or click to select PDF files from your device</span>
            </label>

            <div className="formGrid">
              <label className="checkboxRow">
                <input
                  type="checkbox"
                  checked={useLlm}
                  onChange={(event) => setUseLlm(event.target.checked)}
                />
                <span>Use LLM enhancement when available</span>
              </label>

              <label className="label">
                Model
                <input
                  className="input"
                  type="text"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                />
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

            <button className="button" type="submit" disabled={loading}>
              {loading
                ? files.length > 1
                  ? "Ranking candidates..."
                  : "Parsing resume..."
                : files.length > 1
                ? "Process Batch"
                : "Parse Resume"}
            </button>
          </form>
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Upload Queue</h2>
            <span>{uploadQueue.length} item(s)</span>
          </div>
          <div className="queueList">
            {uploadQueue.length ? uploadQueue.map((item) => (
              <div className={`queueItem ${item.status}`} key={item.id}>
                <span>
                  <strong>{item.name}</strong>
                  <small>{item.message}</small>
                </span>
                <mark>{item.status}</mark>
              </div>
            )) : (
              <p className="emptyState">No files waiting. Add resumes to start parsing.</p>
            )}
          </div>
          {uploadQueue.some((item) => item.status === "failed") ? (
            <button className="secondaryButton retryButton" type="button" onClick={submitUpload} disabled={loading}>
              Retry Failed Batch
            </button>
          ) : null}
        </article>

        <article className="panel">
          <div className="panelHeader">
            <h2>Parsing States</h2>
            <span>Operational clarity</span>
          </div>
          <div className="stateGrid">
            {["waiting", "uploading", "parsing", "completed", "failed"].map((state) => (
              <div className={`statePill ${state}`} key={state}>
                <strong>{state}</strong>
                <span>{state === "failed" ? "retry after correcting the upload" : "visible in queue"}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </div>
  );
}
