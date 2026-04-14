"use client";

import type { CarePlanItem, CarePlanSection } from "@/lib/api";
import { BUCKET_META, itemStatusClass, normalizeStatusTag } from "./dashboard-utils";

interface CarePlanCardProps {
  petName: string;
  buckets: Record<"continue" | "attend" | "add", CarePlanSection[]>;
  cartQtyByItem: Record<string, number>;
  addedIds: Record<string, boolean>;
  onAddToCart: (item: CarePlanItem, sectionTitle: string) => void;
  onEditReminders?: () => void;
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
  onEditReminders,
  counts,
}: CarePlanCardProps) {
  const bucketOrder: Array<"continue" | "attend" | "add"> = ["continue", "attend", "add"];

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
        <div className="sec-lbl" style={{ marginBottom: 0 }}>{petName}&apos;s Care Plan</div>
        {onEditReminders && (
          <button
            type="button"
            onClick={onEditReminders}
            style={{
              border: "1px solid #ffd9c2",
              background: "#fff4ec",
              color: "#c54c0b",
              borderRadius: 999,
              padding: "5px 12px",
              fontSize: 12,
              fontWeight: 700,
              cursor: "pointer",
              flexShrink: 0,
            }}
            aria-label="Edit care reminders"
          >
            Edit
          </button>
        )}
      </div>
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
                  // Food and supplement items don't display their reason text in the
                  // continue bucket (hidden by the condition below), so requiring a
                  // reason before showing the Order button would block newly-added
                  // items (e.g. "omega") that haven't had a GPT reason generated yet.
                  const isFoodOrSupplement = item.test_type === "food" || item.test_type === "supplement";
                  const canOrder = bucketKey !== "attend" && (item.orderable || isFoodOrSupplement);
                  const ctaText = (item.cta_label || "Order Now").replace(/\s*[→>-]+\s*$/, "");

                  // Format supplement names: capitalize first letter and append
                  // "Supplement" suffix so "omega" renders as "Omega Supplement".
                  // Guard against double-suffixing if the label already ends with it.
                  const displayName = item.test_type === "supplement"
                    ? (() => {
                        const capitalized = item.name.charAt(0).toUpperCase() + item.name.slice(1);
                        return /supplement$/i.test(capitalized.trim())
                          ? capitalized
                          : `${capitalized} Supplement`;
                      })()
                    : item.name;

                  return (
                    <div key={id} className="care-item">
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div className="care-name">{displayName}</div>
                        <div className="care-meta">
                          {item.test_type === "food" || item.test_type === "supplement"
                            ? item.freq
                            : `${item.freq} · ${normalizeStatusTag(item.status_tag) === "Urgent" && item.next_due ? `Overdue since ${item.next_due}` : `Next: ${item.next_due || "--"}`}`}
                        </div>
                        {item.reason && !(bucketKey === "continue" && (item.test_type === "food" || item.test_type === "supplement")) && (
                          <div style={{ fontSize: 11, color: "var(--t2)", lineHeight: 1.4, marginTop: 3, fontStyle: "italic" }}>
                            {item.reason}
                          </div>
                        )}
                      </div>

                      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 5, flexShrink: 0 }}>
                        {bucketKey === "add"
                          ? <span className="s-tag s-tag-rec">Recommended</span>
                          : item.test_type !== "food" && item.test_type !== "supplement"
                            ? <span className={`s-tag ${itemStatusClass(item)}`}>{normalizeStatusTag(item.status_tag)}</span>
                            : null
                        }

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

                        {!canOrder && item.signal_level === "L1" && item.info_prompt && item.test_type !== "food" && item.test_type !== "supplement" && (
                          <div style={{ fontSize: 11, color: "var(--t3)", fontStyle: "italic", textAlign: "right", maxWidth: 160, lineHeight: 1.4 }}>
                            {item.info_prompt}
                          </div>
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
