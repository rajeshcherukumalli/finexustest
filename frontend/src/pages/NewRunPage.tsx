import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, pollJobUntilDone } from "../api/client";

export default function NewRunPage() {
  const navigate = useNavigate();
  const [appSlug, setAppSlug] = useState("dfsqa");
  const [url, setUrl] = useState("https://dfsqa.beehyv.com");
  const [contractFilename, setContractFilename] = useState("");
  const [maxPages, setMaxPages] = useState(20);
  const [headed, setHeaded] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    setStatusMessage("Starting extraction…");
    const slug = appSlug.trim();
    try {
      const started = await api.extractContract({
        app_slug: slug,
        url: url.trim(),
        contract_filename: contractFilename.trim() || null,
        max_pages: maxPages,
        headed,
      });
      setStatusMessage("Crawling site and building contract…");
      const job = await pollJobUntilDone(started.id);
      if (job.status === "failed") {
        setError(job.error || "Extraction failed");
        return;
      }
      navigate(`/apps/${slug}/workspace`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start extraction");
    } finally {
      setSubmitting(false);
      setStatusMessage("");
    }
  }

  return (
    <div className="card">
      <h2>Extract Contract</h2>
      <p className="note">
        Crawl the target site and build a UI action contract. After extraction, use the App
        Workspace to describe what you want to test and generate plans, test cases, and Playwright
        specs step by step.
      </p>

      <form className="form-grid" onSubmit={onSubmit}>
        <div>
          <label htmlFor="appSlug">App slug</label>
          <input
            id="appSlug"
            type="text"
            value={appSlug}
            onChange={(e) => setAppSlug(e.target.value)}
            required
            disabled={submitting}
          />
        </div>

        <div>
          <label htmlFor="url">Target URL</label>
          <input
            id="url"
            type="url"
            placeholder="https://dfsqa.beehyv.com"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            required
            disabled={submitting}
          />
        </div>

        <div>
          <label htmlFor="contract">Contract filename (optional)</label>
          <input
            id="contract"
            type="text"
            placeholder="{app-slug}-contract.json"
            value={contractFilename}
            onChange={(e) => setContractFilename(e.target.value)}
            disabled={submitting}
          />
        </div>

        <div>
          <label htmlFor="maxPages">Max pages</label>
          <input
            id="maxPages"
            type="number"
            min={1}
            max={100}
            value={maxPages}
            onChange={(e) => setMaxPages(Number(e.target.value))}
            disabled={submitting}
          />
        </div>

        <div className="checkbox-group">
          <label htmlFor="headedScrape">
            <input
              id="headedScrape"
              type="checkbox"
              checked={headed}
              onChange={(e) => setHeaded(e.target.checked)}
              disabled={submitting}
            />
            Show browser while scraping (headed)
          </label>
        </div>

        {headed && (
          <p className="note" style={{ marginTop: 0 }}>
            Opens a visible Chromium window on your desktop. From the <code>qa-automation</code>{" "}
            folder run <code>xhost +local:docker</code> then{" "}
            <code>docker compose -f docker-compose.yml -f docker-compose.headed.yml up -d --build</code>
            .
          </p>
        )}

        {error && <p className="error">{error}</p>}
        {submitting && statusMessage && (
          <p className="job-status">
            <span className="spinner" style={{ borderColor: "rgba(37,99,235,0.25)", borderTopColor: "#2563eb" }} />
            {statusMessage}
          </p>
        )}

        <div>
          <button type="submit" className={submitting ? "btn-loading" : undefined} disabled={submitting}>
            {submitting && <span className="spinner" aria-hidden="true" />}
            {submitting ? "Extracting contract…" : "Extract Contract"}
          </button>
        </div>
      </form>
    </div>
  );
}
