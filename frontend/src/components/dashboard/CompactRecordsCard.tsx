"use client";

interface CompactRecordsCardProps {
  reportCount: number;
  onGoToRecords: () => void;
}

export default function CompactRecordsCard({ reportCount, onGoToRecords }: CompactRecordsCardProps) {
  return (
    <section className="card" style={{ padding: "10px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <p
            style={{
              margin: 0,
              fontSize: 14,
              fontWeight: 700,
              color: "var(--t1)",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            Organized Health Records
          </p>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              minWidth: 22,
              height: 22,
              borderRadius: 999,
              padding: "0 8px",
              fontSize: 12,
              fontWeight: 700,
              color: "var(--t1)",
              background: "#FFF3ED",
              border: "1px solid #FFD5C2",
            }}
            aria-label={`${reportCount} reports`}
          >
            {reportCount}
          </span>
        </div>

        <button
          type="button"
          onClick={onGoToRecords}
          style={{
            border: "none",
            borderRadius: 10,
            padding: "8px 12px",
            fontSize: 12,
            fontWeight: 700,
            color: "#FFFFFF",
            background: "var(--brand-gradient)",
            whiteSpace: "nowrap",
          }}
        >
          View All
        </button>
      </div>
    </section>
  );
}