import { useEffect } from "react";

export type ReportView = "playwright" | "allure";

type Props = {
  open: boolean;
  onClose: () => void;
  reportUrl: string | null;
  allureReportUrl: string | null;
  reportView: ReportView;
  onReportViewChange: (view: ReportView) => void;
  allureReportExists: boolean;
  passed?: boolean | null;
};

export default function PlaywrightReportModal({
  open,
  onClose,
  reportUrl,
  allureReportUrl,
  reportView,
  onReportViewChange,
  allureReportExists,
  passed,
}: Props) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const canToggle = Boolean(reportUrl) && Boolean(allureReportExists && allureReportUrl);
  const activeUrl =
    reportView === "allure" && allureReportUrl ? allureReportUrl : reportUrl;
  const title =
    reportView === "allure" && allureReportUrl ? "Allure report" : "Playwright report";

  return (
    <div
      className="report-modal-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="report-modal-panel" role="dialog" aria-modal="true" aria-label={title}>
        <div className="report-modal-header">
          <div className="report-modal-title">
            <span>{title}</span>
            {passed !== undefined && passed !== null && (
              <span className={`report-modal-badge ${passed ? "pass" : "fail"}`}>
                {passed ? "Passed" : "Failed"}
              </span>
            )}
          </div>
          <div className="report-modal-actions">
            {canToggle && (
              <div className="report-view-toggle" role="group" aria-label="Report view">
                <button
                  type="button"
                  className={`btn-report-toggle ${reportView === "playwright" ? "active" : ""}`}
                  onClick={() => onReportViewChange("playwright")}
                >
                  Playwright
                </button>
                <button
                  type="button"
                  className={`btn-report-toggle ${reportView === "allure" ? "active" : ""}`}
                  onClick={() => onReportViewChange("allure")}
                >
                  Allure
                </button>
              </div>
            )}
            <button type="button" className="report-modal-close" onClick={onClose} aria-label="Close">
              ×
            </button>
          </div>
        </div>
        <div className="report-modal-body">
          {activeUrl ? (
            <iframe className="report-modal-iframe" src={activeUrl} title={title} />
          ) : (
            <p className="report-modal-empty">No report available — run Play again.</p>
          )}
        </div>
      </div>
    </div>
  );
}
