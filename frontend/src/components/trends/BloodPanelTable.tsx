"use client";

import type { BloodPanelData } from "@/lib/api";
import { bloodPanelRowOrder, formatDisplayDate } from "./trend-utils";

interface BloodPanelTableProps {
  data: BloodPanelData;
}

function isOutOfRange(status: string): boolean {
  return status.toLowerCase() !== "normal";
}

export default function BloodPanelTable({ data }: BloodPanelTableProps) {
  const rows = bloodPanelRowOrder(data.rows);

  return (
    <div className="card">
      <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.6px", textTransform: "uppercase", marginBottom: 5, color: "var(--red)" }}>
        🩸 Blood Panel · {data.date ? formatDisplayDate(data.date) : data.label}
      </div>
      <div style={{ fontSize: 15, fontWeight: 700, color: "var(--t1)", lineHeight: 1.35, marginBottom: 14 }}>{data.headline}</div>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {[
              { label: "Marker", align: "left" },
              { label: "Range", align: "left" },
              { label: "Value", align: "right" },
              { label: "Status", align: "right" },
            ].map((header) => (
              <th
                key={header.label}
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: "var(--t3)",
                  textTransform: "uppercase",
                  letterSpacing: "0.6px",
                  padding: "0 0 8px",
                  textAlign: header.align as "left" | "right",
                }}
              >
                {header.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const outOfRange = isOutOfRange(row.status);
            const accent = outOfRange ? "var(--red)" : "var(--green)";
            return (
              <tr
                key={`${row.marker}-${index}`}
                style={{
                  borderBottom: index < rows.length - 1 ? "1px solid var(--border)" : "none",
                  ...(outOfRange ? { background: "rgba(255, 59, 48, 0.06)" } : {}),
                }}
              >
                <td style={{ padding: "10px 0", fontSize: 14, fontWeight: outOfRange ? 600 : 400, color: "var(--t1)" }}>{row.marker}</td>
                <td style={{ padding: "10px 0", fontSize: 11, color: "var(--t3)" }}>{row.range}</td>
                <td style={{ padding: "10px 0", fontSize: 15, fontWeight: 600, textAlign: "right", color: accent }}>{row.value}</td>
                <td style={{ padding: "10px 0 10px 8px", fontSize: 12, fontWeight: 600, textAlign: "right", color: accent }}>{row.status}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}