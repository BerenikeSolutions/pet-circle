"use client";

import type { CartItemData } from "@/lib/api";

interface ConfirmViewProps {
  items: CartItemData[];
  totalPaid: number;
  onBackToDashboard: () => void;
}

export default function ConfirmView({ items, totalPaid, onBackToDashboard }: ConfirmViewProps) {
  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="app" style={{ paddingTop: 32, paddingBottom: 32 }}>
        <div className="card" style={{ textAlign: "center" }}>
          <div
            style={{
              width: 80,
              height: 80,
              borderRadius: "50%",
              background: "var(--green)",
              margin: "0 auto 12px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
            aria-hidden="true"
          >
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 6L9 17L4 12" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <h2 className="vh-title" style={{ marginBottom: 4 }}>Order Placed!</h2>
          <p style={{ color: "var(--t3)", fontSize: 13 }}>Estimated delivery: 2-4 business days</p>
        </div>

        <div className="card">
          <div className="sec-lbl">Order Summary</div>
          {items.length === 0 && <div style={{ color: "var(--t3)", fontSize: 13 }}>No items found.</div>}
          {items.map((item) => (
            <div
              key={item.product_id}
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 12,
                padding: "8px 0",
                borderBottom: "1px solid var(--border)",
                fontSize: 13,
              }}
            >
              <span>
                {item.name} x {item.quantity}
              </span>
              <strong>Rs {(item.price * item.quantity).toLocaleString("en-IN")}</strong>
            </div>
          ))}
          <div style={{ display: "flex", justifyContent: "space-between", paddingTop: 10, fontSize: 14 }}>
            <span>Total paid</span>
            <strong style={{ color: "var(--orange)" }}>Rs {totalPaid.toLocaleString("en-IN")}</strong>
          </div>
        </div>

        <div style={{ marginTop: 8 }}>
          <button className="btn btn-or" type="button" onClick={onBackToDashboard}>
            Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
