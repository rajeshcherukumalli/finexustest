import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, AppSummary } from "../api/client";

export default function AppsPage() {
  const [apps, setApps] = useState<AppSummary[]>([]);
  const [jobs, setJobs] = useState<Awaited<ReturnType<typeof api.listJobs>>["jobs"]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listApps(), api.listJobs()])
      .then(([appsRes, jobsRes]) => {
        setApps(appsRes.apps);
        setJobs(jobsRes.jobs.slice(0, 10));
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading...</p>;
  if (error) return <p className="error">{error}</p>;

  return (
    <>
      <div className="card">
        <h2>Generated Apps</h2>
        {apps.length === 0 ? (
          <p className="empty">No apps yet. <Link to="/run">Extract a contract</Link>.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>App</th>
                <th>Last run</th>
                <th>Flows</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {apps.map((app) => (
                <tr key={app.slug}>
                  <td><strong>{app.slug}</strong></td>
                  <td>{app.generated_at ? new Date(app.generated_at).toLocaleString() : "—"}</td>
                  <td>{app.flows_count}</td>
                  <td>
                    <Link to={`/apps/${app.slug}/workspace`}>Workspace</Link>
                    {" · "}
                    <Link to={`/apps/${app.slug}`}>Artifacts</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h2>Recent Jobs</h2>
        {jobs.length === 0 ? (
          <p className="empty">No jobs yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>App</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.id}>
                  <td><Link to={`/jobs/${job.id}`}>{job.id}</Link></td>
                  <td>{job.app_slug}</td>
                  <td><span className={`badge badge-${job.status}`}>{job.status}</span></td>
                  <td>{new Date(job.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
