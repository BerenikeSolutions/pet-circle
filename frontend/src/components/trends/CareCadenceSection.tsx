"use client";

import type { CadenceData } from "@/lib/api";
import DewormingCadence from "@/components/charts/DewormingCadence";
import TickFleaCadence from "@/components/charts/TickFleaCadence";
import VaccinationCadence from "@/components/charts/VaccinationCadence";

interface CareCadenceSectionProps {
  data: CadenceData | null;
}

function footerPill(text: string, bg: string, color: string) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        fontSize: 11,
        fontWeight: 600,
        padding: "5px 11px",
        borderRadius: 20,
        marginTop: 14,
        background: bg,
        color,
      }}
    >
      {text}
    </div>
  );
}

export default function CareCadenceSection({ data }: CareCadenceSectionProps) {
  if (!data) {
    return (
      <div className="card" style={{ fontSize: 13, color: "var(--t2)", lineHeight: 1.5 }}>
        No cadence history is available yet.
      </div>
    );
  }

  return (
    <section>
      {data.vaccines && (
        <div className="card">
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.6px", textTransform: "uppercase", marginBottom: 5, color: "var(--green)" }}>
            💉 Vaccinations · Cadence
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--t1)", lineHeight: 1.35 }}>{data.vaccines.headline}</div>
          <div style={{ marginTop: 12 }}>
            <VaccinationCadence data={data.vaccines} />
          </div>
          {footerPill(data.vaccines.footer.text, data.vaccines.footer.bg, data.vaccines.footer.color)}
        </div>
      )}

      {data.flea_tick && (
        <div className="card">
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.6px", textTransform: "uppercase", marginBottom: 5, color: "var(--amber)" }}>
            🦟 Tick & Flea Prevention · Cadence
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--t1)", lineHeight: 1.35 }}>{data.flea_tick.headline}</div>
          <div style={{ marginTop: 12 }}>
            <TickFleaCadence data={data.flea_tick} />
          </div>
          {footerPill(data.flea_tick.footer.text, data.flea_tick.footer.bg, data.flea_tick.footer.color)}
        </div>
      )}

      {data.deworming && (
        <div className="card">
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "0.6px", textTransform: "uppercase", marginBottom: 5, color: "#9B59B6" }}>
            🐛 Deworming · Cadence
          </div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--t1)", lineHeight: 1.35 }}>{data.deworming.headline}</div>
          <div style={{ marginTop: 12 }}>
            <DewormingCadence data={data.deworming} />
          </div>
          {data.deworming.footer
            ? footerPill(data.deworming.footer.text, data.deworming.footer.bg, data.deworming.footer.color)
            : footerPill("🚨 Administer immediately", "var(--tr)", "#b52020")}
        </div>
      )}
    </section>
  );
}