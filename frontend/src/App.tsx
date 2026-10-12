import { Link, Route, Routes } from "react-router-dom";
import AppsPage from "./pages/AppsPage";
import NewRunPage from "./pages/NewRunPage";
import JobDetailPage from "./pages/JobDetailPage";
import AppArtifactsPage from "./pages/AppArtifactsPage";
import AppWorkspacePage from "./pages/AppWorkspacePage";

export default function App() {
  return (
    <div className="layout">
      <header>
        <h1>QA Automation</h1>
        <nav>
          <Link to="/">Apps</Link>
          <Link to="/run">Extract Contract</Link>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<AppsPage />} />
        <Route path="/run" element={<NewRunPage />} />
        <Route path="/jobs/:id" element={<JobDetailPage />} />
        <Route path="/apps/:slug/workspace" element={<AppWorkspacePage />} />
        <Route path="/apps/:slug" element={<AppArtifactsPage />} />
      </Routes>
    </div>
  );
}
