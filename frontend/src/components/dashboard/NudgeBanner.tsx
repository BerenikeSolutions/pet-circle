"use client";

interface NudgeBannerProps {
  petName: string;
  nudgeCount: number;
  onGoToNudges: () => void;
}

export default function NudgeBanner({ petName, nudgeCount, onGoToNudges }: NudgeBannerProps) {
  if (nudgeCount <= 0) return null;

  const itemLabel = nudgeCount === 1 ? "action item" : "action items";

  return (
    <section
      className="card"
      role="button"
      tabIndex={0}
      aria-label={`View all health actions for ${petName}`}
      onClick={onGoToNudges}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onGoToNudges();
        }
      }}
      style={{
        padding: "12px 14px",
        border: "1px solid #FFD5C2",
        background: "linear-gradient(180deg, #FFF6F1 0%, #FFFFFF 100%)",
        cursor: "pointer",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div>
          <p style={{ margin: 0, fontSize: 14, fontWeight: 700, color: "var(--t1)" }}>
            You have {nudgeCount} {itemLabel} for {petName}
          </p>
        </div>

        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            onGoToNudges();
          }}
          aria-label={`View all health actions for ${petName}`}
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