"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { RecordItem, RecordResult, RecordsV2 } from "@/lib/api";
import { fetchRecords, getDashboardDocumentUrl } from "@/lib/api";
import VetVisitCard from "./VetVisitCard";
import DocumentViewer from "./DocumentViewer";

type RecordsTabId = "vet_visits" | "lab_reports" | "imaging" | "whatsapp";

const RECORDS_TABS: Array<{ id: RecordsTabId; label: string }> = [
  { id: "vet_visits", label: "Vet Visit" },
  { id: "lab_reports", label: "Lab Report" },
  { id: "imaging", label: "Imaging" },
  { id: "whatsapp", label: "WhatsApp Chat" },
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

function ResultFlagBadge({ flag }: { flag: string | null }) {
  if (!flag) return null;
  const lower = flag.toLowerCase();
  const color = lower === "high" ? "#DC2626" : lower === "low" ? "#B45309" : "#374151";
  const bg = lower === "high" ? "#FEE2E2" : lower === "low" ? "#FFF3E0" : "#F3F4F6";
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        color,
        background: bg,
        borderRadius: 999,
        padding: "2px 7px",
        marginLeft: 6,
        whiteSpace: "nowrap",
      }}
    >
      {flag.toUpperCase()}
    </span>
  );
}

function RecordExpandedContent({
  record,
  onViewDoc,
}: {
  record: RecordItem;
  onViewDoc: (id: string, title: string) => void;
}) {
  const keyFinding = record.key_finding || record.tag;
  const hasResults = record.results && record.results.length > 0;

  return (
    <div style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
      {/* FINDING */}
      <div
        style={{
          borderRadius: 10,
          background: "#F0F9FF",
          border: "1px solid #BAE6FD",
          padding: "10px 12px",
          marginBottom: 12,
        }}
      >
        <div style={{ fontSize: 11, fontWeight: 700, color: "#0369A1", marginBottom: 3 }}>
          FINDING
        </div>
        <div
          style={{
            fontSize: 13,
            fontWeight: 600,
            color: record.tag_color || "var(--t1)",
            lineHeight: 1.35,
          }}
        >
          {keyFinding}
        </div>
      </div>

      {/* TEST RESULTS */}
      {hasResults && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--t3)", marginBottom: 8 }}>
            TEST RESULTS
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(record.results as RecordResult[]).map((r, i) => {
              const valueStr = r.unit ? `${r.value} ${r.unit}` : r.value;
              return (
                <div
                  key={`${record.id}-result-${i}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    fontSize: 13,
                    color: "var(--t1)",
                  }}
                >
                  <span style={{ flex: 1, color: "var(--t2)" }}>{r.parameter}</span>
                  <span style={{ fontWeight: 600, flexShrink: 0 }}>
                    {valueStr}
                    <ResultFlagBadge flag={r.flag} />
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* NOTES */}
      {record.notes && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: "var(--t3)", marginBottom: 6 }}>
            NOTES
          </div>
          <div style={{ fontSize: 12, color: "var(--t2)", lineHeight: 1.4 }}>{record.notes}</div>
        </div>
      )}

      {/* View document link */}
      <button
        type="button"
        onClick={() => onViewDoc(record.id, record.title)}
        style={{
          fontSize: 12,
          color: "var(--t3)",
          fontWeight: 600,
          background: "none",
          border: "1px solid var(--border)",
          borderRadius: 8,
          padding: "6px 12px",
          cursor: "pointer",
          display: "inline-block",
        }}
        aria-label={`View document for ${record.title}`}
      >
        View document ↗
      </button>
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
  const [open, setOpen] = useState(false);
  const keyFindingLabel = record.key_finding || record.tag;
  const buttonId = `record-toggle-${record.id}`;
  const panelId = `record-panel-${record.id}`;

  return (
    <article className="card" style={{ padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
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
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: "var(--t1)", flex: 1, minWidth: 0 }}>
              {record.title}
            </div>
            <button
              id={buttonId}
              type="button"
              onClick={() => setOpen((prev) => !prev)}
              aria-label={open ? `Collapse ${record.title}` : `View ${record.title}`}
              aria-expanded={open}
              aria-controls={panelId}
              style={{
                fontSize: 12,
                color: "var(--orange)",
                fontWeight: 700,
                background: "none",
                border: "none",
                padding: 0,
                cursor: "pointer",
                flexShrink: 0,
              }}
            >
              {open ? "Close ✕" : "View →"}
            </button>
          </div>
          <div style={{ fontSize: 12, color: "var(--t3)", marginTop: 3 }}>
            {formatDate(record.date)}
            {keyFindingLabel && (
              <span style={{ color: record.tag_color, fontWeight: 600, marginLeft: 6 }}>
                · {keyFindingLabel}
              </span>
            )}
          </div>
        </div>
      </div>

      {open && (
        <div id={panelId} role="region" aria-labelledby={buttonId}>
          <RecordExpandedContent record={record} onViewDoc={onViewDoc} />
        </div>
      )}
    </article>
  );
}

export default function RecordsView({ token, petName, onBack }: RecordsViewProps) {
  const [activeTab, setActiveTab] = useState<RecordsTabId>("vet_visits");
  const [data, setData] = useState<RecordsV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [viewerDoc, setViewerDoc] = useState<{ id: string; title: string } | null>(null);
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

  useEffect(() => {
    load();
  }, [load]);

  const filteredRecords = useMemo(() => {
    if (!data?.records || activeTab === "vet_visits") return [];

    const getDisplayTab = (recordType: string): RecordsTabId | null => {
      if (recordType === "lab_reports" || recordType === "imaging" || recordType === "whatsapp") return recordType;
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
    if (activeTab === "whatsapp") {
      const n = filteredRecords.length;
      return `${n} ${n === 1 ? "message" : "messages"}`;
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
      const emptyText = activeTab === "whatsapp"
        ? "No WhatsApp documents shared yet."
        : "No records in this section yet.";
      return <EmptyState text={emptyText} />;
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

        <button className="floater fl-home" onClick={onBack} type="button" aria-label="Go to dashboard" title="Go to dashboard">
          🏠
        </button>
      </div>
    </div>
  );
}
