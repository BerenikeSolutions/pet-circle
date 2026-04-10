"use client";

import type { AskVetCondition } from "@/lib/api";
import BarChart from "@/components/charts/BarChart";
import LineChart from "@/components/charts/LineChart";
import {
  buildBarStatus,
  compressTimelineNodes,
  formatAxisDate,
  formatDisplayDate,
  isPlateletSeries,
  timelineNodeColor,
} from "./trend-utils";

interface AskVetConditionCardProps {
  condition: AskVetCondition;
  onOpenDashboardCondition?: (conditionId: string) => void;
}

function chartTitle(condition: AskVetCondition, isPlatelets: boolean): string {
  if (isPlatelets) return "Blood · Platelet trend";
  return `${condition.chart_data?.points[0]?.marker || "Marker"} · trend`;
}

export default function AskVetConditionCard({
  condition,
  onOpenDashboardCondition,
}: AskVetConditionCardProps) {
  const points = condition.chart_data?.points || [];
  const plateletSeries = isPlateletSeries(points);
  const timeline = compressTimelineNodes(condition.timeline_data || []);
  const maxQuestions = 2;
  const questions = condition.questions.slice(0, maxQuestions);
  const hiddenQuestionsCount = Math.max(0, condition.questions.length - questions.length);

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              borderRadius: 20,
              padding: "4px 11px",
              marginBottom: 12,
              background: condition.label.toLowerCase().includes("tick") ? "#F5EEF8" : "var(--tr)",
            }}
          >
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: plateletSeries ? "#9B59B6" : "var(--red)" }} />
            <span style={{ fontSize: 11, fontWeight: 700, color: plateletSeries ? "#9B59B6" : "var(--red)" }}>
              {condition.condition_tag}
            </span>
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--t1)", lineHeight: 1.35 }}>{condition.headline}</div>
          <div style={{ fontSize: 12, color: "var(--t3)", marginTop: 4 }}>{condition.trend}</div>
        </div>
        {onOpenDashboardCondition && (
          <button
            type="button"
            onClick={() => onOpenDashboardCondition(condition.id)}
            style={{
              border: "1px solid var(--border)",
              background: "var(--warm)",
              color: "var(--t2)",
              borderRadius: 999,
              padding: "7px 10px",
              fontSize: 11,
              fontWeight: 600,
              whiteSpace: "nowrap",
            }}
          >
            View on dashboard →
          </button>
        )}
      </div>

      {questions.length > 0 && (
        <div style={{ marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "var(--t3)", textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: 8 }}>
            Ask your vet
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
            {questions.map((question, index) => {
              const usePurple = plateletSeries || index === questions.length - 1;
              return (
                <div
                  key={`${condition.id}-${index}`}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    padding: "10px 12px",
                    borderRadius: 10,
                    background: usePurple ? "#F5EEF8" : "var(--ta)",
                  }}
                >
                  <span
                    style={{
                      fontSize: 12,
                      fontWeight: 800,
                      color: usePurple ? "#9B59B6" : "var(--orange)",
                      flexShrink: 0,
                      marginTop: 1,
                    }}
                  >
                    Ask:
                  </span>
                  <span style={{ fontSize: 13, color: "var(--t1)", lineHeight: 1.5, fontWeight: 500 }}>{question}</span>
                </div>
              );
            })}
            {hiddenQuestionsCount > 0 && (
              <div style={{ fontSize: 12, color: "var(--t3)", fontWeight: 600, marginTop: 2 }}>
                +{hiddenQuestionsCount} more {hiddenQuestionsCount === 1 ? "question" : "questions"}
              </div>
            )}
          </div>
        </div>
      )}

      {points.length > 0 && (
        <div style={{ marginTop: 18 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "var(--t3)", textTransform: "uppercase", letterSpacing: "0.6px", marginBottom: 4 }}>
            {chartTitle(condition, plateletSeries)}
          </div>
          <div style={{ fontSize: 11, color: "var(--t3)", marginBottom: 10 }}>
            Latest: <span style={{ color: plateletSeries ? "var(--red)" : "var(--amber)", fontWeight: 600 }}>{points[points.length - 1]?.marker}</span>
            {points[points.length - 1]?.date ? ` · ${formatDisplayDate(points[points.length - 1].date)}` : ""}
          </div>

          {plateletSeries ? (
            <LineChart
              points={points.map((point) => ({
                label: formatAxisDate(point.date),
                val: point.value,
                display: point.marker,
                color: point.value >= 200 ? "#34C759" : "#FF3B30",
              }))}
              referenceValue={200}
              referenceLabel="200K normal"
              strokeColor="#FF3B30"
              fillColor="#FF3B30"
            />
          ) : (
            <BarChart
              bars={points.map((point) => ({
                label: formatAxisDate(point.date),
                val: point.value,
                display: point.marker,
                status: buildBarStatus(point),
              }))}
            />
          )}
        </div>
      )}

      {timeline.nodes.length > 0 && (
        <div style={{ marginTop: 18 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: "var(--t3)", textTransform: "uppercase", letterSpacing: "0.6px", marginBottom: 8 }}>
            Episode timeline
          </div>
          <div style={{ position: "relative" }}>
            <div
              style={{
                height: 2,
                background: "var(--border)",
                borderRadius: 2,
                position: "absolute",
                top: 14,
                left: 14,
                right: 14,
                zIndex: 0,
              }}
            />
            <div style={{ display: "flex", justifyContent: "space-between", position: "relative", zIndex: 1, margin: "4px 0" }}>
              {timeline.nodes.map((node, index) => {
                const isUntreated = node.special_type === "untreated";
                const isDue = node.special_type === "due";
                const color = isUntreated ? "#DC2626" : isDue ? "#B45309" : timelineNodeColor(node, index, timeline.nodes.length);
                const nodeBg = isUntreated ? "#DC2626" : isDue ? "#F59E0B" : color;
                return (
                  <div key={`${node.label}-${node.date || index}`} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, width: 56 }}>
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: "50%",
                        background: nodeBg,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 12,
                        border: isUntreated ? "2px solid #DC2626" : "2px solid #fff",
                        boxShadow: isUntreated ? "0 0 0 2px rgba(220,38,38,0.25)" : "0 1px 3px rgba(0,0,0,.12)",
                      }}
                    >
                      {node.icon}
                    </div>
                    <div style={{ fontSize: 9, fontWeight: isUntreated ? 800 : 600, color: isUntreated ? "#DC2626" : "var(--t2)", textAlign: "center" }}>
                      {node.label}
                    </div>
                    {node.finding && (
                      <div style={{ fontSize: 8, fontWeight: 500, color: color, textAlign: "center", lineHeight: 1.2, maxWidth: 56, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {node.finding}
                      </div>
                    )}
                    <div style={{ fontSize: 8, color: "var(--t3)", textAlign: "center", lineHeight: 1.3 }}>
                      {node.date ? formatDisplayDate(node.date) : "Date unavailable"}
                    </div>
                  </div>
                );
              })}
            </div>
            {timeline.showBreak && (
              <div
                style={{
                  position: "absolute",
                  left: "21%",
                  top: 2,
                  fontSize: 12,
                  fontWeight: 700,
                  color: "var(--t3)",
                  background: "var(--warm)",
                  padding: "0 4px",
                }}
              >
                ...
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}