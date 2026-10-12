import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { api, PlanEntry, pollJobUntilDone, Workspace } from "../api/client";
import GenerateButton from "../components/GenerateButton";
import PlaywrightReportModal, { ReportView } from "../components/PlaywrightReportModal";

function truncate(text: string, max = 60) {
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function basename(path: string) {
  return path.split("/").pop() || path;
}

type WorkspaceNavState = { selectPlanId?: string };
type BusyKind = "" | "plan" | "testcase" | "spec" | "run" | "allure";

function downloadArtifact(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
}

type RunResult = { passed: boolean; reportPath?: string };

function PlanSelect({
  id,
  plans,
  value,
  onChange,
  disabled,
}: {
  id: string;
  plans: PlanEntry[];
  value: string;
  onChange: (planId: string) => void;
  disabled?: boolean;
}) {
  return (
    <select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
      <option value="">— select a test plan —</option>
      {plans.map((p) => (
        <option key={p.id} value={p.id}>
          {p.id} — {truncate(p.user_intent)} ({new Date(p.created_at).toLocaleDateString()})
        </option>
      ))}
    </select>
  );
}

export default function AppWorkspacePage() {
  const { slug } = useParams<{ slug: string }>();
  const location = useLocation();
  const [ws, setWs] = useState<Workspace | null>(null);
  const [intent, setIntent] = useState("");
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [planPreview, setPlanPreview] = useState("");
  const [casePreview, setCasePreview] = useState("");
  const [specPreview, setSpecPreview] = useState("");
  const [selectedSpecPath, setSelectedSpecPath] = useState("");
  const [showSpecContent, setShowSpecContent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<BusyKind>("");
  const [statusMessage, setStatusMessage] = useState("");
  const [runResult, setRunResult] = useState<RunResult | null>(null);
  const [useLlmSpec, setUseLlmSpec] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [hasReport, setHasReport] = useState(false);
  const [allureReportExists, setAllureReportExists] = useState(false);
  const [reportView, setReportView] = useState<ReportView>("playwright");

  const jobRunning = busy !== "";

  const loadWorkspace = useCallback(async (): Promise<Workspace | null> => {
    if (!slug) return null;
    const data = await api.getWorkspace(slug);
    setWs(data);
    return data;
  }, [slug]);

  useEffect(() => {
    const nav = location.state as WorkspaceNavState | null;
    loadWorkspace()
      .then((data) => {
        if (!data) return;
        if (nav?.selectPlanId && data.plans.some((p) => p.id === nav.selectPlanId)) {
          setSelectedPlanId(nav.selectPlanId);
        } else if (data.plans.length === 1) {
          setSelectedPlanId(data.plans[0].id);
        }
      })
      .catch((e: Error) => setError(e.message));
  }, [loadWorkspace, location.key]);

  const refreshReportInfo = useCallback(async () => {
    if (!slug) {
      setHasReport(false);
      setAllureReportExists(false);
      return;
    }
    try {
      const [pw, allure] = await Promise.all([
        api.playwrightReportInfo(slug),
        api.allureReportInfo(slug),
      ]);
      setHasReport(pw.exists);
      setAllureReportExists(allure.exists);
    } catch {
      setHasReport(false);
      setAllureReportExists(false);
    }
  }, [slug]);

  useEffect(() => {
    refreshReportInfo();
  }, [refreshReportInfo, runResult?.reportPath]);

  useEffect(() => {
    if (!showReportModal) return;
    refreshReportInfo();
  }, [showReportModal, refreshReportInfo]);

  const selectedPlan: PlanEntry | undefined = ws?.plans.find((p) => p.id === selectedPlanId);
  const testcase = selectedPlan?.testcases[0];
  const specs = selectedPlan?.specs ?? [];
  const specPathsKey = specs.map((s) => s.path).join("|");
  const hasSpec = specs.length > 0;
  const hasAnySpec = (ws?.plans ?? []).some((p) => (p.specs?.length ?? 0) > 0);

  useEffect(() => {
    if (!slug || !selectedPlan) {
      setPlanPreview("");
      return;
    }
    api.readFile(slug, selectedPlan.plan_path)
      .then((f) => setPlanPreview(f.content))
      .catch(() => setPlanPreview("(unable to load plan)"));
  }, [slug, selectedPlan]);

  useEffect(() => {
    if (!slug || !testcase) {
      setCasePreview("");
      return;
    }
    api.readFile(slug, testcase.path)
      .then((f) => setCasePreview(f.content))
      .catch(() => setCasePreview("(unable to load testcase)"));
  }, [slug, testcase]);

  useEffect(() => {
    if (!specs.length) {
      setSelectedSpecPath("");
      setShowSpecContent(false);
      setSpecPreview("");
      return;
    }
    setSelectedSpecPath((prev) =>
      prev && specs.some((s) => s.path === prev) ? prev : specs[0].path,
    );
  }, [selectedPlanId, specPathsKey, specs]);

  async function loadSpecContent(path: string) {
    if (!slug) return;
    setSpecPreview("Loading…");
    try {
      const f = await api.readFile(slug, path);
      setSpecPreview(f.content);
    } catch {
      setSpecPreview("(unable to load spec)");
    }
  }

  function onPlanChange(planId: string) {
    setSelectedPlanId(planId);
    setCasePreview("");
    setSpecPreview("");
    setShowSpecContent(false);
  }

  function selectSpec(path: string) {
    setSelectedSpecPath(path);
    if (showSpecContent) {
      loadSpecContent(path);
    }
  }

  function toggleSpecView() {
    if (!selectedSpecPath) return;
    if (showSpecContent) {
      setShowSpecContent(false);
      return;
    }
    setShowSpecContent(true);
    loadSpecContent(selectedSpecPath);
  }

  async function runJob(kind: BusyKind, start: () => Promise<{ id: string }>, doneLabel: string) {
    setError("");
    setStatusMessage("");
    if (kind === "run") {
      setRunResult(null);
    }
    setBusy(kind);
    try {
      const started = await start();
      setStatusMessage(kind === "run" ? "Running Playwright test…" : "Job running…");
      const job = await pollJobUntilDone(started.id);
      if (job.status === "failed") {
        setError(job.error || "Job failed");
        return null;
      }
      setStatusMessage(doneLabel);
      const data = await loadWorkspace();
      if (job.result?.plan_id && data?.plans.some((p) => p.id === job.result?.plan_id)) {
        setSelectedPlanId(job.result.plan_id);
      }
      if (kind === "spec" && showSpecContent && selectedSpecPath) {
        await loadSpecContent(selectedSpecPath);
      }
      if (kind === "run" && job.result?.passed !== undefined && job.result?.passed !== null) {
        const result: RunResult = {
          passed: job.result.passed,
          reportPath: job.result.report_path ?? undefined,
        };
        setRunResult(result);
        if (slug) {
          refreshReportInfo();
        }
        if (!result.passed) {
          setError(`Test failed (exit code ${job.result.exit_code ?? "unknown"})`);
        }
      }
      return job;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
      return null;
    } finally {
      setBusy("");
    }
  }

  async function handleGeneratePlan() {
    if (!slug || !intent.trim()) return;
    await runJob(
      "plan",
      () => api.generatePlan(slug, intent.trim()),
      "Test plan generated.",
    );
  }

  async function handleGenerateTestcase() {
    if (!slug || !selectedPlanId) return;
    await runJob(
      "testcase",
      () => api.generateTestcase(slug, selectedPlanId),
      "Test case generated.",
    );
  }

  async function handleGenerateSpec() {
    if (!slug || !selectedPlanId) return;
    await runJob(
      "spec",
      () => api.generateSpec(slug, selectedPlanId, useLlmSpec),
      "Playwright spec generated.",
    );
  }

  async function handlePlay() {
    if (!slug || !selectedPlanId || !selectedSpecPath) return;
    await runJob(
      "run",
      () => api.runSpec(slug, selectedPlanId, selectedSpecPath),
      "Test run finished.",
    );
  }

  async function handleRunAllureSuite() {
    if (!slug) return;
    setError("");
    setBusy("allure");
    setStatusMessage("Running full test suite and building Allure report…");
    try {
      const started = await api.runAllureSuite(slug);
      const job = await pollJobUntilDone(started.id);
      if (job.status === "failed") {
        setError(job.error || "Allure job failed");
        return;
      }
      const passed = job.result?.passed;
      setStatusMessage(
        passed === false
          ? "Tests failed — Allure report downloaded"
          : "Allure report downloaded",
      );
      setReportView("allure");
      await refreshReportInfo();
      downloadArtifact(api.downloadUrl(slug, "allure-report"), `${slug}-allure-report.zip`);
      if (passed === false) {
        setError(`Some tests failed (exit code ${job.result?.exit_code ?? "unknown"})`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy("");
    }
  }

  if (!slug) return null;
  if (!ws) return <p>Loading workspace...</p>;

  return (
    <>
      <div className="card">
        <h2>Workspace — {slug}</h2>
        <p className="note">One test plan → one test case → one Playwright spec.</p>
        {ws.contract_exists ? (
          <p>
            Contract: {ws.page_count} pages · {ws.base_url || "unknown URL"}
          </p>
        ) : (
          <p className="error">
            No contract found. <Link to="/run">Extract contract</Link> first.
          </p>
        )}
        <p>
          <Link to={`/apps/${slug}`}>Browse all artifacts</Link>
        </p>
      </div>

      <div className="card">
        <h2>1. Test Plan</h2>
        <label htmlFor="intent">What do you want to test?</label>
        <textarea
          id="intent"
          rows={3}
          value={intent}
          onChange={(e) => setIntent(e.target.value)}
          placeholder="e.g. Verify all nav links open the correct pages"
          disabled={!ws.contract_exists || jobRunning}
        />
        <div style={{ marginTop: "0.75rem" }}>
          <GenerateButton
            loading={busy === "plan"}
            disabled={!ws.contract_exists || !intent.trim() || jobRunning}
            onClick={handleGeneratePlan}
            loadingLabel="Generating test plan…"
          >
            Generate Test Plan
          </GenerateButton>
        </div>

        <div style={{ marginTop: "1rem" }}>
          <label htmlFor="planSelect">Test plans</label>
          <PlanSelect
            id="planSelect"
            plans={ws.plans}
            value={selectedPlanId}
            onChange={onPlanChange}
            disabled={jobRunning}
          />
        </div>
        {planPreview && (
          <div className="content-viewer" style={{ marginTop: "0.75rem", maxHeight: 240 }}>
            <pre>{planPreview}</pre>
          </div>
        )}
      </div>

      <div className="card">
        <h2>2. Test Case</h2>
        <div>
          <label htmlFor="planSelectCase">Test plan</label>
          <PlanSelect
            id="planSelectCase"
            plans={ws.plans}
            value={selectedPlanId}
            onChange={onPlanChange}
            disabled={jobRunning}
          />
        </div>
        {selectedPlanId && (
          <p style={{ marginTop: "0.5rem" }}>
            Status:{" "}
            {testcase
              ? `✓ ${testcase.path}${
                  testcase.case_count && testcase.case_count !== "0"
                    ? ` (${testcase.case_count} case${testcase.case_count === "1" ? "" : "s"} in case.yaml)`
                    : ""
                }`
              : "Not generated yet"}
          </p>
        )}
        <div style={{ marginTop: "0.75rem" }}>
          <GenerateButton
            loading={busy === "testcase"}
            disabled={!selectedPlanId || jobRunning}
            onClick={handleGenerateTestcase}
            loadingLabel="Generating test case…"
          >
            {testcase ? "Regenerate Test Case" : "Generate Test Case"}
          </GenerateButton>
        </div>
        {casePreview && (
          <div className="content-viewer" style={{ marginTop: "0.75rem", maxHeight: 240 }}>
            <pre>{casePreview}</pre>
          </div>
        )}
      </div>

      <div className="card">
        <h2>3. Playwright</h2>
        <div>
          <label htmlFor="planSelectSpec">Test plan</label>
          <PlanSelect
            id="planSelectSpec"
            plans={ws.plans}
            value={selectedPlanId}
            onChange={onPlanChange}
            disabled={jobRunning}
          />
        </div>
        {selectedPlanId && !testcase && (
          <p className="note" style={{ marginTop: "0.75rem" }}>
            Generate a test case in step 2 before creating Playwright code.
          </p>
        )}
        {selectedPlanId && testcase && (
          <div className="playwright-panel" style={{ marginTop: "0.75rem" }}>
            <div className="spec-list">
              <div className="spec-list-header">Generated specs</div>
              {hasSpec ? (
                specs.map((s) => (
                  <button
                    key={s.path}
                    type="button"
                    className={`spec-list-item${selectedSpecPath === s.path ? " active" : ""}`}
                    onClick={() => selectSpec(s.path)}
                    disabled={jobRunning}
                  >
                    <span className="spec-list-name">{basename(s.path)}</span>
                    <span className="spec-list-path">{s.path}</span>
                  </button>
                ))
              ) : (
                <p className="spec-list-empty">No Playwright spec yet — use Regenerate to generate.</p>
              )}
            </div>
            <div className="spec-actions">
              <label className="llm-spec-toggle" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <input
                  type="checkbox"
                  checked={useLlmSpec}
                  onChange={(e) => setUseLlmSpec(e.target.checked)}
                  disabled={jobRunning}
                />
                Use LLM for complex steps
              </label>
              <GenerateButton
                loading={busy === "spec"}
                disabled={!selectedPlanId || !testcase || jobRunning}
                onClick={handleGenerateSpec}
                loadingLabel="Generating…"
              >
                {hasSpec ? "Regenerate" : "Generate"}
              </GenerateButton>
              <button
                type="button"
                className={`btn-play${busy === "run" ? " btn-loading" : ""}`}
                disabled={!hasSpec || !selectedSpecPath || jobRunning}
                onClick={handlePlay}
              >
                {busy === "run" && <span className="spinner" aria-hidden="true" />}
                {busy === "run" ? "Running…" : "Play"}
              </button>
              <button
                type="button"
                className={`btn-view${showSpecContent ? " open" : ""}`}
                disabled={!selectedSpecPath || jobRunning}
                onClick={toggleSpecView}
                aria-expanded={showSpecContent}
              >
                View code
                <span className="btn-chevron" aria-hidden="true">
                  {showSpecContent ? "▴" : "▾"}
                </span>
              </button>
              <div className="spec-report-actions">
                {runResult && (
                  <button
                    type="button"
                    className="btn-report"
                    disabled={jobRunning || (!hasReport && !runResult.reportPath)}
                    title={
                      hasReport || runResult.reportPath
                        ? "Open Playwright HTML report"
                        : "No report yet — run Play again after rebuilding Docker"
                    }
                    onClick={() => setShowReportModal(true)}
                  >
                    Show report
                  </button>
                )}
                <button
                  type="button"
                  className={`btn-report btn-report-allure${busy === "allure" ? " btn-loading" : ""}`}
                  disabled={!hasAnySpec || jobRunning}
                  title="Run all specs headless, build Allure HTML, and download a zip (may take several minutes)"
                  onClick={handleRunAllureSuite}
                >
                  {busy === "allure" && <span className="spinner" aria-hidden="true" />}
                  {busy === "allure" ? "Generating…" : "Generate Allure report"}
                </button>
              </div>
            </div>
          </div>
        )}
        {selectedPlanId && testcase && hasSpec && (
          <div style={{ marginTop: "0.75rem" }}>
            <p className="note" style={{ marginBottom: 0 }}>
              Play opens a visible Chromium window on your desktop. Run these two commands in your
              terminal (from the <code>qa-automation</code> folder):
            </p>
            <pre className="cmd-snippet" style={{ marginTop: "0.5rem" }}>
              {`xhost +local:docker
docker compose -f docker-compose.yml -f docker-compose.headed.yml up -d --build`}
            </pre>
          </div>
        )}
        {runResult && (
          <div className={`run-result-row ${runResult.passed ? "run-result-pass" : "run-result-fail"}`}>
            <span>{runResult.passed ? "Passed" : "Failed"}</span>
            <button
              type="button"
              className="btn-report btn-report-inline"
              disabled={!hasReport && !runResult.reportPath}
              onClick={() => setShowReportModal(true)}
            >
              Show report
            </button>
            {!hasReport && !runResult.reportPath && (
              <span className="run-result-hint">(re-run Play to generate HTML report)</span>
            )}
          </div>
        )}
        {showSpecContent && specPreview && (
          <div className="content-viewer spec-content-panel">
            <div className="spec-content-header">
              <span>{basename(selectedSpecPath)}</span>
            </div>
            <pre>{specPreview}</pre>
          </div>
        )}
      </div>

      {busy && (
        <p className="job-status">
          <span className="spinner" style={{ borderColor: "rgba(37,99,235,0.25)", borderTopColor: "#2563eb" }} />
          {statusMessage || "Working…"}
        </p>
      )}
      {error && <p className="error">{error}</p>}
      {slug && (
        <PlaywrightReportModal
          open={showReportModal}
          onClose={() => setShowReportModal(false)}
          reportUrl={hasReport || runResult?.reportPath ? api.reportUrl(slug) : null}
          allureReportUrl={allureReportExists ? api.allureReportUrl(slug) : null}
          reportView={reportView}
          onReportViewChange={setReportView}
          allureReportExists={allureReportExists}
          passed={runResult?.passed ?? null}
        />
      )}
    </>
  );
}
