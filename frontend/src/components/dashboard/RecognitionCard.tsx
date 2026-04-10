"use client";

import { useState } from "react";
import type { DashboardData } from "@/lib/api";
import { normalizeRecognitionBullets } from "./dashboard-utils";

interface RecognitionCardProps {
  data: DashboardData;
  onGoToRecords: () => void;
  isReturning?: boolean;
}

export default function RecognitionCard({ data, onGoToRecords, isReturning = false }: RecognitionCardProps) {
  const bullets = normalizeRecognitionBullets(data).slice(0, 3);
  const reportCount = data.recognition?.report_count ?? data.documents?.length ?? 0;
  const [expanded, setExpanded] = useState(!isReturning);

  const title = isReturning ? "Organized Health Records" : "What We Found";

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: isReturning && !expanded ? 0 : undefined }}>
        <button
          type="button"
          onClick={isReturning ? () => setExpanded((v) => !v) : undefined}
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            border: "none",
            background: "transparent",
            padding: 0,
            cursor: isReturning ? "pointer" : "default",
            margin: 0,
          }}
        >
          <span className="sec-lbl" style={{ margin: 0 }}>{title}</span>
          {isReturning && (
            <svg
              style={{ width: 14, height: 14, transition: "transform 0.2s", transform: expanded ? "rotate(180deg)" : "rotate(0deg)", color: "var(--t3)" }}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          )}
        </button>
        {isReturning && (
          <button
            type="button"
            onClick={onGoToRecords}
            style={{
              color: "var(--orange)",
              fontSize: 12,
              fontWeight: 600,
              border: "none",
              background: "transparent",
              padding: 0,
              cursor: "pointer",
              whiteSpace: "nowrap",
            }}
          >
            View All Records →
          </button>
        )}
      </div>

      {(!isReturning || expanded) && (
        <>
          <div style={{ fontSize: 13, color: "var(--t2)", marginBottom: 12, marginTop: 6, lineHeight: 1.5 }}>
            {reportCount > 0 ? (
              <>
                We reviewed <strong style={{ color: "var(--t1)" }}>{reportCount} {reportCount === 1 ? "report" : "reports"}</strong> and identified {data.pet.name}&apos;s current care routine.
                {!isReturning && (
                  <>
                    {" "}
                    <button
                      type="button"
                      onClick={onGoToRecords}
                      style={{
                        color: "var(--t3)",
                        textDecoration: "underline",
                        textDecorationStyle: "dashed",
                        textUnderlineOffset: 3,
                        cursor: "pointer",
                        fontSize: 12,
                        fontWeight: 500,
                        border: "none",
                        background: "transparent",
                        padding: 0,
                      }}
                    >
                      View all reports →
                    </button>
                  </>
                )}
              </>
            ) : (
              <>We identified {data.pet.name}&apos;s current care routine.</>
            )}
          </div>

          {bullets.map((bullet, index) => (
            <div
              key={`${bullet.label}-${index}`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "7px 0",
                borderTop: index === 0 ? "1px solid var(--border)" : "none",
              }}
            >
              <span style={{ fontSize: 16, flexShrink: 0, alignSelf: "flex-start", marginTop: 1 }}>{bullet.icon || "•"}</span>
              <span
                style={{
                  fontSize: 13,
                  color: "var(--t1)",
                  fontWeight: 500,
                  lineHeight: 1.4,
                  wordBreak: "break-word",
                }}
              >
                {bullet.label}
              </span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
