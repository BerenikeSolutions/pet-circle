"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CarePlanItem, DashboardData } from "@/lib/api";
import ProfileBanner from "./ProfileBanner";
import RecognitionCard from "./RecognitionCard";
import LifeStageCard from "./LifeStageCard";
import HealthConditionsCard from "./HealthConditionsCard";
import DietAnalysisCard from "./DietAnalysisCard";
import CarePlanCard from "./CarePlanCard";
import HealthRecordsNav from "./HealthRecordsNav";
import CartFloater from "./CartFloater";
import { buildCarePlanBuckets } from "./dashboard-utils";

interface DashboardViewProps {
  data: DashboardData;
  onGoToReminders: () => void;
  onGoToTrends: () => void;
  onGoToRecords: () => void;
  onGoToCart: () => void;
}

function cartItemId(item: CarePlanItem, sectionTitle: string): string {
  return `${sectionTitle}:${item.test_type}:${item.name}`.toLowerCase();
}

export default function DashboardView({
  data,
  onGoToReminders,
  onGoToTrends,
  onGoToRecords,
  onGoToCart,
}: DashboardViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [floaterUnlocked, setFloaterUnlocked] = useState(false);
  const [addedIds, setAddedIds] = useState<Record<string, boolean>>({});
  const [cartQtyByItem, setCartQtyByItem] = useState<Record<string, number>>({});
  const [cartPriceByItem, setCartPriceByItem] = useState<Record<string, number>>({});
  const timerIdsRef = useRef<number[]>([]);

  const buckets = useMemo(() => buildCarePlanBuckets(data), [data]);

  useEffect(() => {
    if (floaterUnlocked) return;
    const btn = containerRef.current?.querySelector(".order-btn");
    if (!btn) return;

    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setFloaterUnlocked(true);
          obs.disconnect();
        }
      },
      { threshold: 0.1 }
    );

    obs.observe(btn);
    return () => obs.disconnect();
  }, [floaterUnlocked]);

  useEffect(() => {
    return () => {
      timerIdsRef.current.forEach((id) => window.clearTimeout(id));
      timerIdsRef.current = [];
    };
  }, []);

  const handleAddToCart = (item: CarePlanItem, sectionTitle: string) => {
    const id = cartItemId(item, sectionTitle);
    setCartQtyByItem((prev) => ({ ...prev, [id]: (prev[id] || 0) + 1 }));

    const price = Number((item as CarePlanItem & { price?: number }).price || 0);
    setCartPriceByItem((prev) => ({ ...prev, [id]: Number.isFinite(price) ? price : 0 }));

    setAddedIds((prev) => ({ ...prev, [id]: true }));
    const timeoutId = window.setTimeout(() => {
      setAddedIds((prev) => ({ ...prev, [id]: false }));
    }, 1800);
    timerIdsRef.current.push(timeoutId);
  };

  const cartCount = Object.values(cartQtyByItem).reduce((sum, qty) => sum + qty, 0);
  const cartTotal = Object.entries(cartQtyByItem).reduce((sum, [id, qty]) => {
    return sum + qty * (cartPriceByItem[id] || 0);
  }, 0);

  return (
    <div ref={containerRef}>
      <ProfileBanner data={data} onGoToReminders={onGoToReminders} />
      <RecognitionCard data={data} onGoToRecords={onGoToRecords} />
      <LifeStageCard data={data} />
      <HealthConditionsCard data={data} onGoToTrends={onGoToTrends} />
      <DietAnalysisCard data={data} />
      <CarePlanCard
        petName={data.pet.name}
        buckets={buckets}
        cartQtyByItem={cartQtyByItem}
        addedIds={addedIds}
        onAddToCart={handleAddToCart}
      />
      <HealthRecordsNav
        petName={data.pet.name}
        reportCount={data.recognition?.report_count ?? data.documents?.length ?? 0}
        onGoToRecords={onGoToRecords}
      />
      <CartFloater unlocked={floaterUnlocked} cartCount={cartCount} totalPrice={cartTotal} onGoToCart={onGoToCart} />
    </div>
  );
}
