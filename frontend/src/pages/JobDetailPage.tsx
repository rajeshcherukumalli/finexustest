import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, JobResponse } from "../api/client";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = (location.state as { redirectTo?: string } | null)?.redirectTo;
  const [job, setJob] = useState<JobResponse | null>(null);
  const [logs, setLogs] = useState("");
  const [error, setError] = useState("");
  const offsetRef = useRef(0);

  useEffect(() => {
    if (!id) return;

    let active = true;

    async function poll() {
      try {
        const [jobRes, logRes] = await Promise.all([
          api.getJob(id!),
          api.getLogs(id!, offsetRef.current),
        ]);
        if (!active) return;
        setJob(jobRes);
        if (logRes.content) {
          setLogs((prev) => prev + logRes.content);
          offsetRef.current = logRes.offset;
        }
        if (jobRes.status === "queued" || jobRes.status === "running") {
          setTimeout(poll, 2000);
        } else if (redirectTo && jobRes.status === "completed") {
          const navState: Record<string, string> = {};
          if (jobRes.result?.plan_id) {
            navState.selectPlanId = jobRes.result.plan_id;
          }
          setTimeout(() => navigate(redirectTo, { state: navState }), 1500);
        }
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Failed to load job");
      }
    }

    poll();
    return () => {
      active = false;
    };
  }, [id, navigate, redirectTo]);

  if (error) return <p className="error">{error}</p>;
  if (!job) return <p>Loading job...</p>;

  return (
    <>
      <div className="card">
        <h2>
          Job {job.id} ({job.job_type}){" "}
          <span className={`badge badge-${job.status}`}>{job.status}</span>
        </h2>
        <p>App: <strong>{job.app_slug}</strong></p>
        {job.result && (
          <p>
            Steps: {job.result.steps_run.join(", ")}
            {job.result.plan_id && <> · Plan: {job.result.plan_id}</>}
            {job.result.flow_id && <> · Flow: {job.result.flow_id}</>}
            {job.result.flows?.length > 0 && <> · Flows: {job.result.flows.join(", ")}</>}
          </p>
        )}
        {job.error && <p className="error">{job.error}</p>}
        {job.status === "completed" && (
          <p>
            <Link to={`/apps/${job.app_slug}/workspace`}>Open workspace →</Link>
            {" · "}
            <Link to={`/apps/${job.app_slug}`}>Browse artifacts</Link>
          </p>
        )}
      </div>

      <div className="card">
        <h2>Logs</h2>
        <div className="log-panel">{logs || "Waiting for logs..."}</div>
      </div>
    </>
  );
}
