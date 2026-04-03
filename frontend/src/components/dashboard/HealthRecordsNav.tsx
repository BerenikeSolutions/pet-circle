"use client";

interface HealthRecordsNavProps {
  petName: string;
  reportCount: number;
  onGoToRecords: () => void;
}

export default function HealthRecordsNav({ petName, reportCount, onGoToRecords }: HealthRecordsNavProps) {
  return (
    <button className="nav-card" onClick={onGoToRecords} type="button">
      <div>
        <div
          style={{
            fontSize: 11,
            fontWeight: 600,
            color: "var(--t3)",
            textTransform: "uppercase",
            letterSpacing: "0.8px",
            marginBottom: 3,
          }}
        >
          Source Documents
        </div>
        <div style={{ fontSize: 15, fontWeight: 700 }}>See {petName}&apos;s Full Health Records</div>
        <div style={{ fontSize: 12, color: "var(--t3)", marginTop: 3 }}>{reportCount} reports · vet visits · lab results</div>
      </div>
      <div className="nav-arr">→</div>
    </button>
  );
}
