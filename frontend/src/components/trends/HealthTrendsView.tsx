"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { HealthTrendsV2, VetSummary } from "@/lib/api";
import { fetchHealthTrends } from "@/lib/api";
import AskVetSection from "./AskVetSection";
import CareCadenceSection from "./CareCadenceSection";
import SignalsSection from "./SignalsSection";
import { getSpeciesEmoji } from "./trend-utils";

type TabId = "askvet" | "signals" | "cadence";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "askvet", label: "Ask Your Vet" },
  { id: "signals", label: "Signals" },
  { id: "cadence", label: "Care Cadence" },
];

interface HealthTrendsViewProps {
  token: string;
  petName: string;
  species?: string | null;
  vetSummary?: VetSummary | null;
  onBack: () => void;
  onOpenDashboardCondition?: (conditionId: string) => void;
}

export default function HealthTrendsView({
  token,
  petName,
  species,
  vetSummary,
  onBack,
  onOpenDashboardCondition,
}: HealthTrendsViewProps) {
  const [activeTab, setActiveTab] = useState<TabId>("askvet");
  const [data, setData] = useState<HealthTrendsV2 | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const sectionRefs = useRef<Record<TabId, HTMLDivElement | null>>({
    askvet: null,
    signals: null,
    cadence: null,
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await fetchHealthTrends(token);
      setData(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load health trends.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const observers: IntersectionObserver[] = [];
    TABS.forEach(({ id }) => {
      const element = sectionRefs.current[id];
      if (!element) return;
      const observer = new IntersectionObserver(
        ([entry]) => {
          if (entry.isIntersecting) {
            setActiveTab(id);
          }
        },
        { rootMargin: "-40% 0px -55% 0px", threshold: 0 }
      );
      observer.observe(element);
      observers.push(observer);
    });
    return () => observers.forEach((observer) => observer.disconnect());
  }, [data]);

  const scrollTo = (id: TabId) => {
    setActiveTab(id);
    sectionRefs.current[id]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const titleEmoji = getSpeciesEmoji(species);
  const vetName = vetSummary?.name || "your vet";

  const renderBody = () => {
    if (loading) {
      return (
        <div className="card" style={{ textAlign: "center", color: "var(--t3)" }}>
          Loading health trends...
        </div>
      );
    }

    if (error) {
      return (
        <div className="card" style={{ textAlign: "center", color: "var(--red)" }}>
          <div>{error}</div>
          <button
            type="button"
            onClick={load}
            style={{
              marginTop: 12,
              border: "1px solid var(--border)",
              borderRadius: 10,
              padding: "8px 12px",
              background: "var(--white)",
              color: "var(--t1)",
              fontWeight: 600,
            }}
          >
            Retry
          </button>
        </div>
      );
    }

    return (
      <div className="tr-content">
        <div
          id="health-trends-askvet"
          ref={(element) => {
            sectionRefs.current.askvet = element;
          }}
          className="tr-section"
        >
          <div className="sec-lbl" style={{ paddingTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
            Ask Your Vet
            <span style={{ flex: 1, height: 1, background: "var(--border)", display: "block" }} />
          </div>
          <AskVetSection
            data={data?.ask_vet || null}
            vetName={vetName}
            onOpenDashboardCondition={onOpenDashboardCondition}
          />
        </div>

        <div
          id="health-trends-signals"
          ref={(element) => {
            sectionRefs.current.signals = element;
          }}
          className="tr-section"
        >
          <div className="sec-lbl" style={{ paddingTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
            Health Signals
            <span style={{ flex: 1, height: 1, background: "var(--border)", display: "block" }} />
          </div>
          <SignalsSection data={data?.signals || null} />
        </div>

        <div
          id="health-trends-cadence"
          ref={(element) => {
            sectionRefs.current.cadence = element;
          }}
          className="tr-section"
        >
          <div className="sec-lbl" style={{ paddingTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
            Health Care Cadence
            <span style={{ flex: 1, height: 1, background: "var(--border)", display: "block" }} />
          </div>
          <CareCadenceSection data={data?.cadence || null} />
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="app">
        <div className="tr-header" style={{ background: "var(--bg)" }}>
          <div className="tr-top">
            <button className="back-btn" onClick={onBack} type="button" aria-label="Back to dashboard" title="Back to dashboard">
              ←
            </button>
            <span style={{ fontSize: 15, fontWeight: 700 }}>{petName}&apos;s Health Trends {titleEmoji}</span>
            <div style={{ width: 36 }} />
          </div>
          <div className="nscroll" aria-label="Health Trends sections">
            <div className="npills" style={{ minWidth: "max-content" }}>
              {TABS.map((tab) => {
                const active = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    id={`health-trends-tab-${tab.id}`}
                    type="button"
                    className={`npill${active ? " active" : ""}`}
                    onClick={() => scrollTo(tab.id)}
                    style={{
                      background: active ? "var(--orange)" : "#fff",
                      color: active ? "#fff" : "var(--t2)",
                      borderColor: active ? "var(--orange)" : "var(--border)",
                    }}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {renderBody()}

        <button className="floater fl-home" onClick={onBack} type="button" aria-label="Go to dashboard" title="Go to dashboard">
          🏠
        </button>
      </div>
    </div>
  );
}