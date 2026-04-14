"use client";

import { useEffect, useState } from "react";
import type { VetVisit } from "@/lib/api";

interface VetVisitCardProps {
  visit: VetVisit;
  defaultOpen: boolean;
  onView: (id: string, title: string) => void;
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

export default function VetVisitCard({ visit, defaultOpen, onView }: VetVisitCardProps) {
  const [open, setOpen] = useState(defaultOpen);
  const buttonId = `visit-toggle-${visit.id}`;
  const panelId = `visit-panel-${visit.id}`;
  const keyFindingLabel = visit.key_finding || visit.tag;

  useEffect(() => {
    setOpen(defaultOpen);
  }, [defaultOpen, visit.id]);

  return (
    <article className="card" style={{ padding: 14 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
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
          🩺
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--t1)" }}>{visit.title}</div>
              <div style={{ fontSize: 12, color: "var(--t3)", marginTop: 2 }}>{formatDate(visit.date)}</div>
            </div>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: visit.tag_color,
                background: visit.tag_bg,
                borderRadius: 999,
                padding: "4px 10px",
                whiteSpace: "nowrap",
                maxWidth: 160,
                overflow: "hidden",
                textOverflow: "ellipsis",
                flexShrink: 0,
              }}
            >
              {keyFindingLabel}
            </span>
            <button
              id={buttonId}
              type="button"
              onClick={() => setOpen((prev) => !prev)}
              aria-label={open ? "Collapse vet visit" : "Expand vet visit"}
              aria-expanded={open}
              aria-controls={panelId}
              style={{
                width: 24,
                height: 24,
                border: "none",
                borderRadius: 999,
                background: "transparent",
                color: "var(--t2)",
                cursor: "pointer",
                padding: 0,
                fontSize: 16,
                lineHeight: "24px",
                transform: open ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform 0.2s ease",
              }}
            >
              ▾
            </button>
          </div>

          <div style={{ marginTop: 8 }}>
            <button
              type="button"
              onClick={() => onView(visit.id, visit.title)}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: 12,
                color: "var(--orange)",
                fontWeight: 700,
                background: "none",
                border: "none",
                padding: 0,
                cursor: "pointer",
              }}
              aria-label={`View prescription for ${visit.title}`}
            >
              View →
            </button>
          </div>

          {open && (
            <div
              id={panelId}
              role="region"
              aria-labelledby={buttonId}
              style={{ marginTop: 12, borderTop: "1px solid var(--border)", paddingTop: 12 }}
            >
              <div
                style={{
                  borderRadius: 10,
                  background: "#FFF3EE",
                  border: "1px solid #FFD5C2",
                  padding: "10px 12px",
                  marginBottom: 12,
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 700, color: "#B45309", marginBottom: 3 }}>
                  RX / PRESCRIPTION
                </div>
                <div style={{ fontSize: 13, color: "var(--t1)", lineHeight: 1.35 }}>{visit.rx || "Not available"}</div>
              </div>

              {visit.medications.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--t3)", marginBottom: 8 }}>
                    MEDICATIONS
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {visit.medications.map((medication, index) => {
                      const subtitle = [medication.dose, medication.duration].filter(Boolean).join(" · ");
                      return (
                        <div key={`${visit.id}-med-${index}`}>
                          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--t1)" }}>{medication.name}</div>
                          {subtitle && (
                            <div style={{ fontSize: 12, color: "var(--t3)", marginTop: 2 }}>{subtitle}</div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {visit.tests.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--t3)", marginBottom: 8 }}>
                    TESTS PRESCRIBED
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {visit.tests.map((test, index) => (
                      <div key={`${visit.id}-test-${index}`}>
                        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--t1)" }}>{test.name}</div>
                        {test.frequency && (
                          <div style={{ fontSize: 12, color: "var(--t3)", marginTop: 2 }}>{test.frequency}</div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {visit.medications.length === 0 && visit.tests.length === 0 && (
                <div
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 10,
                    padding: "8px 10px",
                    fontSize: 12,
                    color: "var(--t3)",
                    marginBottom: 12,
                  }}
                >
                  No medications or tests prescribed at this visit.
                </div>
              )}

              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: "var(--t3)", marginBottom: 6 }}>NOTES</div>
                <div style={{ fontSize: 12, color: "var(--t2)", lineHeight: 1.4, whiteSpace: "pre-line" }}>
                  {visit.notes ? visit.notes.split(" | ").join("\n") : "No additional notes recorded."}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}
