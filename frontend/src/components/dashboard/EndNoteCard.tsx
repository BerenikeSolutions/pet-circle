"use client";

interface EndNoteCardProps {
  petName: string;
  onUploadClick: () => void;
}

export default function EndNoteCard({ petName, onUploadClick }: EndNoteCardProps) {
  return (
    <div
      className="card"
      style={{
        borderLeft: "8px solid var(--brand-primary, #D44800)",
        paddingLeft: 16,
      }}
    >
      <div style={{ marginBottom: 12 }}>
        <div
          style={{
            fontSize: 18,
            fontWeight: 700,
            color: "var(--t1, #000)",
            marginBottom: 8,
          }}
        >
          Great Start! {petName}&apos;s Care is in good hands.
        </div>
        <div
          style={{
            fontSize: 14,
            color: "var(--t2, #666)",
            lineHeight: 1.5,
            marginBottom: 10,
          }}
        >
          From here, we make sure nothing slips through.<br />
          Every due date, every reminder, right on WhatsApp.
        </div>
        <div
          style={{
            fontSize: 14,
            color: "var(--orange, #FF6B35)",
            fontStyle: "italic",
            marginBottom: 10,
          }}
        >
          The more you add, the smarter the plan gets.
        </div>
        <div
          style={{
            fontSize: 14,
            color: "var(--t2, #666)",
            lineHeight: 1.5,
            marginBottom: 14,
          }}
        >
          Drop in a past record, lab report, or prescription — on WhatsApp chat or upload here.
        </div>
      </div>
      <button
        type="button"
        onClick={onUploadClick}
        style={{
          width: "100%",
          padding: "12px 16px",
          borderRadius: 10,
          border: "none",
          background: "var(--brand-primary, #D44800)",
          color: "white",
          fontSize: 14,
          fontWeight: 700,
          cursor: "pointer",
        }}
      >
        + Add documents →
      </button>
    </div>
  );
}
