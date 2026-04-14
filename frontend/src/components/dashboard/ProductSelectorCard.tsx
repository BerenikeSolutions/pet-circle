"use client";

import { useEffect, useState } from "react";
import BottomSheet from "@/components/ui/BottomSheet";

export interface ResolvedProduct {
  sku_id: string;
  category: "food" | "supplement" | "medicine";
  brand_name: string;
  product_line?: string;
  product_name?: string;
  pack_size: string;
  mrp: number;
  discounted_price: number;
  price_per_unit: number;
  unit_label: string;
  in_stock: boolean;
  vet_diet_flag: boolean;
  is_highlighted: boolean;
  highlight_reason?: string;
  medicine_type?: string;
  notes?: string;
}

interface ProductSelectorCardProps {
  open: boolean;
  onClose: () => void;
  products: ResolvedProduct[];
  signalLevel: string;
  vetDietWarning: boolean;
  packSizeSuggestion: string | null;
  onAddToCart: (skuId: string, quantity: number) => void;
  hideSearchMore?: boolean;
}

export default function ProductSelectorCard({
  open,
  onClose,
  products,
  signalLevel,
  vetDietWarning,
  packSizeSuggestion,
  onAddToCart,
  hideSearchMore,
}: ProductSelectorCardProps) {
  const [selectedSku, setSelectedSku] = useState<string>("");
  const [qty, setQty] = useState(1);

  // Reset selection whenever the product list changes (e.g. popup opens with new products)
  useEffect(() => {
    const first = products.find((p) => p.in_stock) || products[0];
    setSelectedSku(first?.sku_id || "");
    setQty(1);
  }, [products]);

  // Fallback: if useEffect hasn't fired yet, derive the active SKU directly from props
  const activeSku = selectedSku || products.find((p) => p.in_stock)?.sku_id || products[0]?.sku_id || "";

  const handleAdd = () => {
    if (activeSku) onAddToCart(activeSku, qty);
  };

  const displayName = (p: ResolvedProduct) =>
    p.category === "food" ? p.product_line || p.brand_name : p.product_name || p.brand_name;

  // ── No products in catalog ─────────────────────────────────────────────────
  if (products.length === 0) {
    return (
      <BottomSheet open={open} onClose={onClose} title="Select Product">
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            textAlign: "center",
            padding: "24px 16px 40px",
            gap: 12,
          }}
        >
          <div style={{ fontSize: 36 }}>📦</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: "var(--t1)" }}>
            Not available right now
          </div>
          <div style={{ fontSize: 13, color: "var(--t2)", lineHeight: 1.6, maxWidth: 260 }}>
            This item isn&apos;t in our catalog yet. We&apos;ll have it in stock soon — check back shortly!
          </div>
        </div>
      </BottomSheet>
    );
  }

  return (
    <BottomSheet open={open} onClose={onClose} title="Select Product">
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {products.map((p) => {
          const isSelected = p.sku_id === activeSku;
          const hasDiscount = p.mrp > p.discounted_price;

          return (
            <label
              key={p.sku_id}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: 10,
                padding: 12,
                borderRadius: 10,
                border: isSelected ? "2px solid var(--brand-primary)" : "1.5px solid var(--border)",
                background: isSelected ? "#FFF6F1" : "var(--white)",
                cursor: p.in_stock ? "pointer" : "default",
                opacity: p.in_stock ? 1 : 0.5,
                position: "relative",
              }}
            >
              <input
                type="radio"
                name="product-select"
                value={p.sku_id}
                checked={isSelected}
                disabled={!p.in_stock}
                onChange={() => { setSelectedSku(p.sku_id); }}
                style={{ marginTop: 3, accentColor: "var(--brand-primary)" }}
              />

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: "var(--t1)" }}>
                    {displayName(p)}
                  </span>
                  {p.is_highlighted && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        background: "#FFF3E0",
                        color: "#E65100",
                        borderRadius: 20,
                        padding: "2px 8px",
                      }}
                    >
                      {p.highlight_reason || "Most Popular"}
                    </span>
                  )}
                  {!p.in_stock && (
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        background: "#FFEBEE",
                        color: "#C62828",
                        borderRadius: 20,
                        padding: "2px 8px",
                      }}
                    >
                      Out of stock
                    </span>
                  )}
                </div>

                <div style={{ fontSize: 12, color: "var(--t2)", marginTop: 2 }}>
                  {p.brand_name}
                </div>
                <div style={{ fontSize: 11, color: "var(--t3)", marginTop: 1 }}>
                  {p.pack_size}
                </div>

                {p.notes && (
                  <div style={{ fontSize: 11, color: "var(--t3)", marginTop: 2, fontStyle: "italic", lineHeight: 1.4 }}>
                    {p.notes}
                  </div>
                )}

                <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 4 }}>
                  {hasDiscount && (
                    <span style={{ fontSize: 12, color: "var(--t3)", textDecoration: "line-through" }}>
                      Rs {p.mrp.toLocaleString("en-IN")}
                    </span>
                  )}
                  <span style={{ fontSize: 15, fontWeight: 700, color: "var(--brand-primary)" }}>
                    Rs {p.discounted_price.toLocaleString("en-IN")}
                  </span>
                </div>
                <div style={{ fontSize: 11, color: "var(--t3)", marginTop: 1 }}>
                  Rs {p.price_per_unit.toLocaleString("en-IN")}/{p.unit_label.replace("per ", "")}
                </div>
              </div>
            </label>
          );
        })}
      </div>

      {vetDietWarning && (
        <div
          style={{
            marginTop: 12,
            padding: "10px 12px",
            borderRadius: 8,
            background: "#FFF8E1",
            border: "1px solid #FFE082",
            fontSize: 12,
            color: "#F57F17",
            lineHeight: 1.5,
          }}
        >
          This is a therapeutic diet. Please use under veterinary guidance.
        </div>
      )}

      {packSizeSuggestion && (
        <div
          style={{
            marginTop: 10,
            fontSize: 12,
            color: "var(--t2)",
            fontStyle: "italic",
            lineHeight: 1.4,
          }}
        >
          {packSizeSuggestion}
        </div>
      )}

      {/* Quantity selector */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          marginTop: 16,
          padding: "10px 0",
        }}
      >
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--t2)" }}>Qty</span>
        <button
          type="button"
          onClick={() => setQty((q) => Math.max(1, q - 1))}
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            border: "1.5px solid var(--border)",
            background: "var(--white)",
            fontSize: 18,
            fontWeight: 700,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--t1)",
          }}
        >
          -
        </button>
        <strong style={{ fontSize: 16, minWidth: 20, textAlign: "center", color: "var(--t1)" }}>
          {qty}
        </strong>
        <button
          type="button"
          onClick={() => setQty((q) => q + 1)}
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            border: "1.5px solid var(--border)",
            background: "var(--white)",
            fontSize: 18,
            fontWeight: 700,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "var(--t1)",
          }}
        >
          +
        </button>
      </div>

      {/* Bottom action buttons */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: hideSearchMore ? "flex-end" : "space-between",
          gap: 10,
          marginTop: 12,
          marginBottom: 70,
        }}
      >
        {!hideSearchMore && (
          <button
            type="button"
            style={{
              padding: "10px 16px",
              borderRadius: 10,
              border: "1.5px solid var(--border)",
              background: "var(--white)",
              fontSize: 13,
              fontWeight: 600,
              color: "var(--t2)",
              cursor: "pointer",
            }}
          >
            Search more
          </button>
        )}
        <button
          type="button"
          onClick={handleAdd}
          disabled={!activeSku}
          style={{
            padding: "10px 24px",
            borderRadius: 10,
            border: "none",
            background: activeSku ? "var(--brand-primary)" : "var(--border)",
            fontSize: 14,
            fontWeight: 700,
            color: "var(--white)",
            cursor: activeSku ? "pointer" : "default",
          }}
        >
          Add to cart
        </button>
      </div>
    </BottomSheet>
  );
}
