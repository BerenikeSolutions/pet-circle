"use client";

import type { DashboardData } from "@/lib/api";
import { normalizeRecognitionBullets } from "./dashboard-utils";

interface RecognitionCardProps {
  data: DashboardData;
  onGoToRecords: () => void;
}

export default function RecognitionCard({ data, onGoToRecords }: RecognitionCardProps) {
  const bullets = normalizeRecognitionBullets(data).slice(0, 3);
  const reportCount = data.recognition?.report_count ?? data.documents?.length ?? 0;

  return (
    <div className="card">
      <div className="sec-lbl">What We Found</div>
      <div style={{ fontSize: 13, color: "var(--t2)", marginBottom: 12, lineHeight: 1.5 }}>
        We reviewed <strong style={{ color: "var(--t1)" }}>{reportCount} reports</strong> and WhatsApp chat and identified {data.pet.name}
        &apos;s current care routine. {" "}
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
          <span style={{ fontSize: 16, flexShrink: 0 }}>{bullet.icon || "•"}</span>
          <span
            style={{
              fontSize: 13,
              color: "var(--t1)",
              fontWeight: 500,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
            title={bullet.label}
          >
            {bullet.label.replace("active conditions", "active health conditions")}
          </span>
        </div>
      ))}
    </div>
  );
}
