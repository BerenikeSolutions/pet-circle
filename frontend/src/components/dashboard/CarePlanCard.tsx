"use client";

import type { CarePlanItem, CarePlanSection } from "@/lib/api";
import { BUCKET_META, itemStatusClass } from "./dashboard-utils";

interface CarePlanCardProps {
  petName: string;
  buckets: Record<"continue" | "attend" | "add", CarePlanSection[]>;
  cartQtyByItem: Record<string, number>;
  addedIds: Record<string, boolean>;
  onAddToCart: (item: CarePlanItem, sectionTitle: string) => void;
}

function itemId(item: CarePlanItem, sectionTitle: string): string {
  return `${sectionTitle}:${item.test_type}:${item.name}`.toLowerCase();
}

export default function CarePlanCard({
  petName,
  buckets,
  cartQtyByItem,
  addedIds,
  onAddToCart,
}: CarePlanCardProps) {
  const bucketOrder: Array<"continue" | "attend" | "add"> = ["continue", "attend", "add"];

  return (
    <div className="card">
      <div className="sec-lbl">{petName}&apos;s Care Plan</div>
      <div className="sec-source">Based on lifestage, health & diet analysis</div>

      {bucketOrder.map((bucketKey, bucketIndex) => {
        const sections = buckets[bucketKey];
        if (sections.length === 0) return null;

        const meta = BUCKET_META[bucketKey];

        return (
          <div key={bucketKey} style={{ marginBottom: bucketIndex < bucketOrder.length - 1 ? 16 : 0 }}>
            <div
              style={{
                background: meta.bg,
                border: `1px solid ${meta.border}`,
                borderRadius: 8,
                padding: "6px 12px",
                marginBottom: 8,
                fontSize: 12,
                fontWeight: 700,
                color: meta.color,
              }}
            >
              {meta.label}
            </div>

            {sections.map((section) => (
              <div key={section.title} className="care-sec" style={{ marginBottom: 8 }}>
                <div className="care-hdr">{section.icon} {section.title}</div>

                {section.items.map((item) => {
                  const id = itemId(item, section.title);
                  const inCartQty = cartQtyByItem[id] || 0;
                  const isAdded = !!addedIds[id];
                  const canOrder = bucketKey !== "attend" && item.orderable && !!item.reason;
                  const ctaText = (item.cta_label || "Order Now").replace(/\s*[→>-]+\s*$/, "");

                  return (
                    <div key={id} className="care-item">
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="care-name">{item.name}</div>
                        <div className="care-meta">
                          {item.freq} · Next: {item.next_due || "--"}
                        </div>
                        {item.reason && (
                          <div style={{ fontSize: 11, color: "var(--t2)", lineHeight: 1.4, marginTop: 3, fontStyle: "italic" }}>
                            {item.reason}
                          </div>
                        )}
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 5, flexShrink: 0 }}>
                        <span className={`s-tag ${itemStatusClass(item)}`}>{item.status_tag}</span>

                        {canOrder && (
                          <button
                            className="order-btn"
                            type="button"
                            onClick={() => onAddToCart(item, section.title)}
                            style={
                              isAdded
                                ? { background: "#34C759", transform: "scale(1.04)", transition: "all .2s" }
                                : { transition: "all .2s" }
                            }
                          >
                            {isAdded
                              ? `✓ Added${inCartQty > 1 ? ` (${inCartQty})` : ""}`
                              : inCartQty > 0
                                ? `Order Again (${inCartQty} in cart)`
                                : `${ctaText} →`}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
