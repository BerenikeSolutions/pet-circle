"use client";

interface CarePlanTrackerProps {
  petName: string;
  onTrack: number;
  dueSoon: number;
  overdue: number;
}

export default function CarePlanTracker({
  petName,
  onTrack,
  dueSoon,
  overdue,
}: CarePlanTrackerProps) {
  const totalCount = onTrack + dueSoon + overdue;
  if (totalCount === 0) return null;

  return (
    <section
      className="card"
      style={{
        padding: "12px 14px",
        border: "1px solid #FFD5C2",
        background: "linear-gradient(180deg, #FFF6F1 0%, #FFFFFF 100%)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <h3 className="sec-lbl" style={{ margin: 0, fontWeight: 700 }}>
          {petName}&apos;s Care Plan
        </h3>

        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {onTrack > 0 && (
            <span
              style={{
                borderRadius: 20,
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: 700,
                background: "#E8F9EE",
                color: "#1B7A3D",
              }}
            >
              {onTrack} On Track
            </span>
          )}

          {dueSoon > 0 && (
            <span
              style={{
                borderRadius: 20,
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: 700,
                background: "#FFF3E0",
                color: "#E65100",
              }}
            >
              {dueSoon} Due Soon
            </span>
          )}

          {overdue > 0 && (
            <span
              style={{
                borderRadius: 20,
                padding: "4px 10px",
                fontSize: 11,
                fontWeight: 700,
                background: "#FFEBEE",
                color: "#C62828",
              }}
            >
              {overdue} Overdue
            </span>
          )}
        </div>
      </div>
    </section>
  );
}