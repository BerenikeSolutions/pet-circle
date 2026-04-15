"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { FailedDocument, RecordItem, RecordsV2 } from "@/lib/api";
import { fetchRecords, getDashboardDocumentUrl, retryAllFailedDocuments } from "@/lib/api";
import VetVisitCard from "./VetVisitCard";
import DocumentViewer from "./DocumentViewer";

type RecordsTabId = "vet_visits" | "lab_reports" | "imaging";

const RECORDS_TABS: Array<{ id: RecordsTabId; label: string }> = [
  { id: "vet_visits", label: "Vet Visit" },
  { id: "lab_reports", label: "Lab Report" },
  { id: "imaging", label: "Imaging" },
];

interface RecordsViewProps {
  token: string;
  petName: string;
  onBack: () => void;
}

function formatDate(value: string | null): string {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(date);
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="card" style={{ textAlign: "center", color: "var(--t3)", fontSize: 13 }}>
      {text}
    </div>
  );
}

function RecordCard({
  record,
  onViewDoc,
}: {
  record: RecordItem;
  onViewDoc: (id: string, title: string) => void;
}) {
  const keyFindingLabel = record.key_finding || record.tag;

  return (
    <article className="card" style={{ padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <div
          aria-hidden="true"
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: "var(--to)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 18,
            flexShrink: 0,
          }}
        >
          {record.icon}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontSize: 14,
              fontWeight: 700,
              color: "var(--t1)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
          >
            {record.title}
          </div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              marginTop: 3,
              fontSize: 12,
              color: "var(--t3)",
              minWidth: 0,
            }}
          >
            <span style={{ flexShrink: 0 }}>{formatDate(record.date)}</span>
            {keyFindingLabel && (
              <>
                <span style={{ flexShrink: 0 }}>·</span>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: record.tag_color,
                    background: record.tag_bg,
                    borderRadius: 999,
                    padding: "3px 9px",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    minWidth: 0,
                  }}
                >
                  {keyFindingLabel}
                </span>
              </>
            )}
          </div>
        </div>

        <button
          type="button"
          onClick={() => onViewDoc(record.id, record.title)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 13,
            color: "var(--t2)",
            fontWeight: 600,
            background: "none",
            border: "none",
            padding: 0,
            cursor: "pointer",
            flexShrink: 0,
          }}
          aria-label={`View document for ${record.title}`}
        >
          View →
        </button>
      </div>
    </article>
  );
}

export default function RecordsView({ token, petName, onBack }: RecordsViewProps) {
  const [activeTab, setActiveTab] = useState<RecordsTabId>("vet_visits");
  const [data, setData] = useState<RecordsV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [viewerDoc, setViewerDoc] = useState<{ id: string; title: string } | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [retryMsg, setRetryMsg] = useState<string | null>(null);
  const activePanelId = `records-panel-${activeTab}`;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await fetchRecords(token);
      setData(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load records.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  const handleRetryAll = useCallback(async () => {
    setRetrying(true);
    setRetryMsg(null);
    try {
      const result = await retryAllFailedDocuments(token);
      const succeeded = result.results.filter((r) => r.status === "success").length;
      const failed = result.results.filter((r) => r.status === "failed" || r.status === "skipped").length;
      setRetryMsg(
        succeeded > 0
          ? `${succeeded} document${succeeded > 1 ? "s" : ""} processed successfully.${failed > 0 ? ` ${failed} still failed.` : ""}`
          : `Processing failed. Please re-upload the documents on WhatsApp.`
      );
      await load();
    } catch {
      setRetryMsg("Retry failed. Please try again.");
    } finally {
      setRetrying(false);
    }
  }, [token, load]);

  useEffect(() => {
    load();
  }, [load]);

  const filteredRecords = useMemo(() => {
    if (!data?.records || activeTab === "vet_visits") return [];

    const getDisplayTab = (recordType: string): RecordsTabId | null => {
      // "whatsapp" typed records are re-mapped to lab_reports since they are
      // uploaded medical documents classified by channel rather than content.
      if (recordType === "whatsapp") return "lab_reports";
      if (recordType === "lab_reports" || recordType === "imaging") return recordType;
      return null;
    };

    return data.records.filter((record) => getDisplayTab(record.type) === activeTab);
  }, [activeTab, data]);

  const countLine = useMemo(() => {
    if (!data) return null;
    if (activeTab === "vet_visits") {
      const n = data.vet_visits?.length ?? 0;
      return `${n} ${n === 1 ? "visit" : "visits"}`;
    }
    const n = filteredRecords.length;
    return `${n} ${n === 1 ? "document" : "documents"}`;
  }, [activeTab, data, filteredRecords]);

  const handleView = useCallback((id: string, title: string) => {
    setViewerDoc({ id, title });
  }, []);

  const handleCloseViewer = useCallback(() => {
    setViewerDoc(null);
  }, []);

  const renderContent = () => {
    if (loading) {
      return (
        <div className="card" style={{ textAlign: "center", color: "var(--t3)" }}>
          Loading records...
        </div>
      );
    }

    if (error) {
      return (
        <div className="card" style={{ textAlign: "center", color: "var(--red)" }}>
          <div>{error}</div>
          <button
            type="button"
            onClick={load}
            style={{
              marginTop: 12,
              border: "1px solid var(--border)",
              borderRadius: 10,
              padding: "8px 12px",
              background: "var(--white)",
              color: "var(--t1)",
              fontWeight: 600,
            }}
          >
            Retry
          </button>
        </div>
      );
    }

    if (activeTab === "vet_visits") {
      const visits = data?.vet_visits || [];
      if (visits.length === 0) {
        return <EmptyState text="No vet visits available yet." />;
      }
      return (
        <div>
          {visits.map((visit, index) => (
            <VetVisitCard
              key={visit.id}
              visit={visit}
              defaultOpen={index === 0}
              onView={handleView}
            />
          ))}
        </div>
      );
    }

    if (filteredRecords.length === 0) {
      return <EmptyState text="No records in this section yet." />;
    }

    return (
      <div>
        {filteredRecords.map((record) => (
          <RecordCard key={record.id} record={record} onViewDoc={handleView} />
        ))}
      </div>
    );
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      {viewerDoc && (
        <DocumentViewer
          url={getDashboardDocumentUrl(token, viewerDoc.id)}
          title={viewerDoc.title}
          onClose={handleCloseViewer}
        />
      )}

      <div className="app">
        <div className="vh">
          <button className="back-btn" onClick={onBack} type="button" aria-label="Back to dashboard" title="Back to dashboard">
            ←
          </button>
          <span className="vh-title">{petName}&apos;s Health Records</span>
        </div>

        <div className="nscroll" aria-label="Record categories" style={{ margin: "-4px 0 14px" }}>
          <div className="npills" role="tablist" aria-label="Record categories" style={{ minWidth: "max-content" }}>
            {RECORDS_TABS.map((tab) => {
              const active = tab.id === activeTab;
              return (
                <button
                  key={tab.id}
                  id={`records-tab-${tab.id}`}
                  type="button"
                  className={`npill${active ? " active" : ""}`}
                  role="tab"
                  aria-selected={active}
                  aria-controls={`records-panel-${tab.id}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>

        {!loading && !error && countLine && (
          <div style={{ fontSize: 13, color: "var(--t3)", marginBottom: 10, paddingLeft: 2 }}>
            {countLine}
          </div>
        )}

        <div id={activePanelId} role="tabpanel" aria-labelledby={`records-tab-${activeTab}`}>
          {renderContent()}
        </div>

        {!loading && (data?.failed_documents?.length ?? 0) > 0 && (() => {
          const failedOnly = data!.failed_documents.filter((d) => d.status !== "rejected");
          const rejectedOnly = data!.failed_documents.filter((d) => d.status === "rejected");
          return (
            <div style={{ marginTop: 20 }}>
              {rejectedOnly.length > 0 && (
                <>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "var(--t3)", letterSpacing: "0.5px", textTransform: "uppercase", marginBottom: 8 }}>
                    Not accepted ({rejectedOnly.length})
                  </div>
                  {rejectedOnly.map((doc: FailedDocument) => (
                    <div
                      key={doc.id}
                      className="card"
                      style={{ padding: "10px 14px", display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}
                    >
                      <span style={{ fontSize: 18, flexShrink: 0 }}>🚫</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--t1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {doc.title}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--t3)", marginTop: 2 }}>
                          {doc.rejection_reason ?? "Document was not accepted"}
                        </div>
                      </div>
                    </div>
                  ))}
                </>
              )}
              {failedOnly.length > 0 && (
                <>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "var(--t3)", letterSpacing: "0.5px", textTransform: "uppercase", marginBottom: 8, marginTop: rejectedOnly.length > 0 ? 16 : 0 }}>
                    Failed to process ({failedOnly.length})
                  </div>
                  {failedOnly.map((doc: FailedDocument) => (
                    <div
                      key={doc.id}
                      className="card"
                      style={{ padding: "10px 14px", display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}
                    >
                      <span style={{ fontSize: 18, flexShrink: 0 }}>⚠️</span>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--t1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {doc.title}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--t3)", marginTop: 2 }}>Couldn&apos;t be processed</div>
                      </div>
                    </div>
                  ))}
                  {retryMsg && (
                    <div style={{ fontSize: 13, color: "var(--t2)", padding: "8px 0", textAlign: "center" }}>{retryMsg}</div>
                  )}
                  <button
                    type="button"
                    onClick={handleRetryAll}
                    disabled={retrying}
                    style={{
                      width: "100%",
                      marginTop: 4,
                      padding: "10px",
                      borderRadius: 10,
                      border: "1px solid var(--border)",
                      background: retrying ? "var(--bg-app)" : "var(--white)",
                      color: retrying ? "var(--t3)" : "var(--brand)",
                      fontWeight: 700,
                      fontSize: 14,
                      cursor: retrying ? "default" : "pointer",
                    }}
                  >
                    {retrying ? "Retrying…" : "Retry processing"}
                  </button>
                </>
              )}
            </div>
          );
        })()}

        <button className="floater fl-home" onClick={onBack} type="button" aria-label="Go to dashboard" title="Go to dashboard">
          🏠
        </button>
      </div>
    </div>
  );
}
