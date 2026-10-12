import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, FileEntry } from "../api/client";

export default function AppArtifactsPage() {
  const { slug } = useParams<{ slug: string }>();
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState("");
  const [language, setLanguage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!slug) return;
    api
      .listFiles(slug, "", true)
      .then((res) => {
        const flat = res.entries.filter((e) => !e.is_dir);
        flat.sort((a, b) => {
          const aContract = a.path.endsWith("-contract.json") ? 0 : 1;
          const bContract = b.path.endsWith("-contract.json") ? 0 : 1;
          if (aContract !== bContract) return aContract - bContract;
          return a.path.localeCompare(b.path);
        });
        setFiles(flat);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [slug]);

  async function openFile(path: string) {
    if (!slug) return;
    setSelected(path);
    setContent("Loading...");
    try {
      const res = await api.readFile(slug, path);
      setContent(res.content);
      setLanguage(res.language);
    } catch (e) {
      setContent("");
      setError(e instanceof Error ? e.message : "Failed to read file");
    }
  }

  if (!slug) return null;
  if (loading) return <p>Loading...</p>;
  if (error && !files.length) return <p className="error">{error}</p>;

  return (
    <div className="card artifacts-page">
      <h2>Artifacts — {slug}</h2>
      <div className="artifact-layout">
        <div className="file-tree" role="listbox" aria-label="Artifact files">
          {files.map((file) => (
            <button
              key={file.path}
              type="button"
              className={selected === file.path ? "active" : ""}
              onClick={() => openFile(file.path)}
            >
              {file.path}
            </button>
          ))}
        </div>
        <div className="content-viewer">
          {selected ? (
            <>
              <div className="content-viewer-header">
                <span className="content-viewer-path">
                  {selected} ({language})
                </span>
                <a className="btn" href={api.downloadUrl(slug, selected)} download>
                  Download
                </a>
              </div>
              <pre className="content-viewer-body">{content}</pre>
            </>
          ) : (
            <p className="empty">Select a file to preview</p>
          )}
        </div>
      </div>
    </div>
  );
}
