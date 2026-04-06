"use client";

import type { CarePlanItem, CarePlanSection } from "@/lib/api";
import { BUCKET_META, itemStatusClass, normalizeStatusTag } from "./dashboard-utils";

interface CarePlanCardProps {
  petName: string;
  buckets: Record<"continue" | "attend" | "add", CarePlanSection[]>;
  cartQtyByItem: Record<string, number>;
  addedIds: Record<string, boolean>;
  onAddToCart: (item: CarePlanItem, sectionTitle: string) => void;
  counts?: { onTrack: number; dueSoon: number; overdue: number };
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
  counts,
}: CarePlanCardProps) {
  const bucketOrder: Array<"continue" | "attend" | "add"> = ["continue", "attend", "add"];

  return (
    <div className="card">
      <div className="sec-lbl" style={{ marginBottom: 0 }}>{petName}&apos;s Care Plan</div>
      <div className="sec-source">Based on lifestage, health & diet analysis</div>
      {counts && (counts.onTrack > 0 || counts.dueSoon > 0 || counts.overdue > 0) && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap", marginBottom: 12 }}>
          {counts.onTrack > 0 && (
            <span style={{ borderRadius: 20, padding: "4px 12px", fontSize: 11, fontWeight: 700, background: "#E8F9EE", color: "#1B7A3D" }}>
              {counts.onTrack} On Track
            </span>
          )}
          {counts.dueSoon > 0 && (
            <span style={{ borderRadius: 20, padding: "4px 12px", fontSize: 11, fontWeight: 700, background: "#FFF3E0", color: "#E65100" }}>
              {counts.dueSoon} Due Soon
            </span>
          )}
          {counts.overdue > 0 && (
            <span style={{ borderRadius: 20, padding: "4px 12px", fontSize: 11, fontWeight: 700, background: "#FFEBEE", color: "#C62828" }}>
              {counts.overdue} Overdue
            </span>
          )}
        </div>
      )}

      {bucketOrder.map((bucketKey, bucketIndex) => {
        const sections = buckets[bucketKey];
        // Always show "Quick Fixes to Add", hide other empty buckets
        if (sections.length === 0 && bucketKey !== "add") return null;

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

            {sections.length === 0 && bucketKey === "add" && (
              <div style={{ fontSize: 12, color: "var(--t2)", padding: "8px 0", lineHeight: 1.5 }}>
                Recommendations for supplements and food will appear here based on {petName}&apos;s care plan.
              </div>
            )}

            {sections.map((section) => (
              <div key={section.title} className="care-sec" style={{ marginBottom: 8 }}>
                <div className="care-hdr">{section.icon ? `${section.icon} ` : ""}{section.title}</div>

                {section.items.map((item) => {
                  const id = itemId(item, section.title);
                  const inCartQty = cartQtyByItem[id] || 0;
                  const isAdded = !!addedIds[id];
                  const canOrder = bucketKey !== "attend" && item.orderable && !!item.reason;
                  const ctaText = (item.cta_label || "Order Now").replace(/\s*[→>-]+\s*$/, "");

                  return (
                    <div key={id} className="care-item">
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="care-name">{item.name ? item.name.replace(/\b\w/g, (c) => c.toUpperCase()) : item.name}</div>
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
                        {item.test_type !== "food" && (
                          <span className={`s-tag ${itemStatusClass(item)}`}>{normalizeStatusTag(item.status_tag)}</span>
                        )}

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
