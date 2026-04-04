"use client";

import { useMemo, useState } from "react";
import type { NudgeItem } from "@/lib/api";

interface NudgeCardProps {
  nudge: NudgeItem;
  onDismiss: (nudgeId: string) => void;
  onAddToCart: (nudge: NudgeItem) => void;
  isAdded: boolean;
}

const LONG_MESSAGE_LIMIT = 100;

function getPriorityBadgeClass(priority: string): string {
  const normalized = priority.toLowerCase();
  if (normalized === "urgent") return "s-tag s-tag-r";
  if (normalized === "high") return "s-tag s-tag-y";
  return "s-tag";
}

function getPriorityLabel(priority: string): string {
  const normalized = priority.toLowerCase();
  if (normalized === "urgent") return "Urgent";
  if (normalized === "high") return "High";
  if (normalized === "medium") return "Medium";
  return priority;
}

export default function NudgeCard({ nudge, onDismiss, onAddToCart, isAdded }: NudgeCardProps) {
  const [showAllMessage, setShowAllMessage] = useState(false);
  const [confirmDismiss, setConfirmDismiss] = useState(false);

  const isLongMessage = nudge.message.length > LONG_MESSAGE_LIMIT;
  const messageText = useMemo(() => {
    if (showAllMessage || !isLongMessage) return nudge.message;
    return `${nudge.message.slice(0, LONG_MESSAGE_LIMIT)}...`;
  }, [isLongMessage, nudge.message, showAllMessage]);

  return (
    <article className="card" style={{ padding: 14, marginBottom: 10 }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <div
          aria-hidden="true"
          style={{
            width: 38,
            height: 38,
            borderRadius: 10,
            background: "var(--to)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 18,
            flexShrink: 0,
          }}
        >
          {nudge.icon || "⚡"}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, color: "var(--t1)", lineHeight: 1.3 }}>{nudge.title}</h3>
            <span className={getPriorityBadgeClass(nudge.priority)}>{getPriorityLabel(nudge.priority)}</span>
          </div>

          <p style={{ marginTop: 6, fontSize: 12, lineHeight: 1.5, color: "var(--t2)" }}>{messageText}</p>

          {isLongMessage && (
            <button
              type="button"
              onClick={() => setShowAllMessage((prev) => !prev)}
              style={{
                marginTop: 2,
                padding: 0,
                border: "none",
                background: "transparent",
                color: "var(--orange)",
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              {showAllMessage ? "Show less" : "Show more"}
            </button>
          )}

          <div style={{ marginTop: 10, display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            {!nudge.mandatory && !confirmDismiss && (
              <button
                type="button"
                onClick={() => setConfirmDismiss(true)}
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: 10,
                  background: "var(--white)",
                  color: "var(--t2)",
                  fontWeight: 600,
                  fontSize: 12,
                  padding: "6px 10px",
                  cursor: "pointer",
                }}
              >
                Dismiss
              </button>
            )}

            {confirmDismiss && (
              <div style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
                <span style={{ fontSize: 12, color: "var(--t3)" }}>Dismiss this?</span>
                <button
                  type="button"
                  onClick={() => onDismiss(nudge.id)}
                  style={{
                    border: "none",
                    borderRadius: 8,
                    background: "var(--red)",
                    color: "#fff",
                    fontWeight: 700,
                    fontSize: 12,
                    padding: "5px 10px",
                    cursor: "pointer",
                  }}
                >
                  Dismiss
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmDismiss(false)}
                  style={{
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    background: "var(--white)",
                    color: "var(--t2)",
                    fontWeight: 600,
                    fontSize: 12,
                    padding: "5px 10px",
                    cursor: "pointer",
                  }}
                >
                  Cancel
                </button>
              </div>
            )}

            {nudge.orderable && (
              <button
                type="button"
                onClick={() => onAddToCart(nudge)}
                disabled={isAdded}
                style={{
                  border: "none",
                  borderRadius: 10,
                  background: isAdded ? "var(--green)" : "var(--orange)",
                  color: "#fff",
                  fontWeight: 700,
                  fontSize: 12,
                  padding: "7px 12px",
                  cursor: isAdded ? "default" : "pointer",
                  opacity: isAdded ? 0.9 : 1,
                }}
              >
                {isAdded ? "Added" : "Order Now"}
              </button>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
