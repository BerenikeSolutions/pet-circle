"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface CartViewProps {
  items: CartItem[];
  token: string;
  onBack: () => void;
  onUpdateQuantity: (id: string, quantity: number) => void;
  onRemoveItem: (id: string) => void;
  onProceedToCheckout: () => void;
  onAddBySku: (skuId: string, name: string, price: number, mrp: number, icon: string, section: string) => void;
}

export interface CartItem {
  id: string;
  name: string;
  price: number;
  mrp?: number;
  quantity: number;
  icon?: string;
  section?: string;
}

interface SearchResult {
  sku_id: string;
  category: "food" | "supplement";
  brand_name: string;
  name: string;
  pack_size: string;
  mrp: number;
  discounted_price: number;
  in_stock: boolean;
}

const DELIVERY_FEE = 49;
const FREE_THRESHOLD = 599;

export default function CartView({
  items,
  token,
  onBack,
  onUpdateQuantity,
  onRemoveItem,
  onProceedToCheckout,
  onAddBySku,
}: CartViewProps) {
  const inCartItems = useMemo(() => items.filter((item) => item.quantity > 0), [items]);

  const subtotal = useMemo(() => {
    return inCartItems.reduce((sum, item) => sum + item.price * item.quantity, 0);
  }, [inCartItems]);

  const deliveryFee = subtotal >= FREE_THRESHOLD ? 0 : DELIVERY_FEE;
  const total = subtotal + deliveryFee;
  const amountForFreeDelivery = Math.max(0, FREE_THRESHOLD - subtotal);

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [addingSkus, setAddingSkus] = useState<Record<string, boolean>>({});
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const runSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/dashboard/${token}/products/search?q=${encodeURIComponent(q)}`
      );
      if (!res.ok) throw new Error("search failed");
      const data = await res.json();
      setSearchResults(data.results || []);
    } catch {
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      void runSearch(searchQuery);
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [searchQuery, runSearch]);

  const handleSearchAdd = useCallback(async (result: SearchResult) => {
    if (!result.in_stock) return;
    setAddingSkus((prev) => ({ ...prev, [result.sku_id]: true }));
    try {
      const res = await fetch(`${API_BASE}/dashboard/${token}/cart/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku_id: result.sku_id, quantity: 1 }),
      });
      if (!res.ok) throw new Error("add failed");
      const data = await res.json();
      const icon = result.category === "food" ? "🥣" : "💊";
      onAddBySku(result.sku_id, data.name, data.price, result.mrp, icon, "Search");
    } catch (e) {
      console.error("Failed to add search result to cart:", e);
    } finally {
      setAddingSkus((prev) => ({ ...prev, [result.sku_id]: false }));
    }
  }, [token, onAddBySku]);

  const changeQuantity = (itemId: string, nextQty: number) => {
    if (nextQty <= 0) {
      onRemoveItem(itemId);
      return;
    }
    onUpdateQuantity(itemId, nextQty);
  };

  const cartSkuIds = useMemo(() => new Set(inCartItems.map((i) => i.id)), [inCartItems]);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="app">
        <div className="vh">
          <button className="back-btn" onClick={onBack} type="button" aria-label="Back to dashboard">
            Back
          </button>
          <div className="vh-title">Your Cart</div>
        </div>

        {/* Search bar */}
        <div className="card" style={{ marginBottom: 12 }}>
          <div style={{ position: "relative" }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search food or supplements..."
              style={{
                width: "100%",
                padding: "10px 36px 10px 12px",
                borderRadius: 10,
                border: "1.5px solid var(--border)",
                fontSize: 14,
                color: "var(--t1)",
                background: "var(--white)",
                boxSizing: "border-box",
                outline: "none",
              }}
            />
            {searchLoading && (
              <div
                style={{
                  position: "absolute",
                  right: 10,
                  top: "50%",
                  transform: "translateY(-50%)",
                  width: 16,
                  height: 16,
                  borderRadius: "50%",
                  border: "2px solid var(--border)",
                  borderTopColor: "var(--brand-primary)",
                  animation: "spin 0.6s linear infinite",
                }}
              />
            )}
          </div>

          {searchQuery.length >= 2 && !searchLoading && searchResults.length === 0 && (
            <div style={{ marginTop: 10, fontSize: 13, color: "var(--t3)", textAlign: "center" }}>
              No products found
            </div>
          )}

          {searchResults.length > 0 && (
            <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              {searchResults.map((r) => {
                const alreadyInCart = cartSkuIds.has(r.sku_id);
                const hasDiscount = r.mrp > r.discounted_price;
                return (
                  <div
                    key={r.sku_id}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "10px 0",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    <div style={{ fontSize: 20 }}>{r.category === "food" ? "🥣" : "💊"}</div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "var(--t1)" }}>{r.name}</div>
                      <div style={{ fontSize: 11, color: "var(--t3)" }}>{r.pack_size}</div>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 5, marginTop: 2 }}>
                        {hasDiscount && (
                          <span style={{ fontSize: 11, color: "var(--t3)", textDecoration: "line-through" }}>
                            Rs {r.mrp.toLocaleString("en-IN")}
                          </span>
                        )}
                        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--brand-primary)" }}>
                          Rs {r.discounted_price.toLocaleString("en-IN")}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled={!r.in_stock || alreadyInCart || addingSkus[r.sku_id]}
                      onClick={() => handleSearchAdd(r)}
                      style={{
                        padding: "7px 14px",
                        borderRadius: 8,
                        border: "none",
                        background: alreadyInCart ? "var(--border)" : r.in_stock ? "var(--brand-primary)" : "var(--border)",
                        color: "var(--white)",
                        fontSize: 12,
                        fontWeight: 700,
                        cursor: r.in_stock && !alreadyInCart ? "pointer" : "default",
                        flexShrink: 0,
                      }}
                    >
                      {alreadyInCart ? "In Cart" : !r.in_stock ? "Out of Stock" : addingSkus[r.sku_id] ? "..." : "Add"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Cart items */}
        <div className="card" style={{ marginBottom: 12 }}>
          {inCartItems.length === 0 && (
            <div style={{ textAlign: "center", color: "var(--t3)" }}>No items in cart yet.</div>
          )}

          {inCartItems.map((item) => {
            const sku = item.id;
            const section = item.section || "Care";
            const hasDiscount = item.mrp !== undefined && item.mrp > item.price;
            return (
              <div className="cart-row" key={item.id}>
                <div className="cart-icon" style={{ background: "var(--to)" }}>{item.icon || "PKG"}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--t1)" }}>{item.name}</div>
                  <div style={{ fontSize: 11, color: "var(--t3)" }}>SKU: {sku}</div>
                  <div style={{ fontSize: 11, color: "var(--t3)" }}>Section: {section}</div>
                  <div style={{ display: "flex", alignItems: "baseline", gap: 6, marginTop: 4 }}>
                    {hasDiscount && (
                      <span style={{ fontSize: 11, color: "var(--t3)", textDecoration: "line-through" }}>
                        Rs {item.mrp!.toLocaleString("en-IN")}
                      </span>
                    )}
                    <span style={{ fontSize: 13, fontWeight: 700, color: "var(--orange)" }}>
                      Rs {item.price.toLocaleString("en-IN")}
                    </span>
                  </div>
                </div>
                <div className="qty">
                  <button className="qty-btn" type="button" onClick={() => changeQuantity(item.id, item.quantity - 1)}>
                    -
                  </button>
                  <strong style={{ minWidth: 14, textAlign: "center" }}>{item.quantity}</strong>
                  <button className="qty-btn" type="button" onClick={() => changeQuantity(item.id, item.quantity + 1)}>
                    +
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="card">
          <div style={{ display: "grid", gap: 8, fontSize: 13 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--t2)" }}>Subtotal</span>
              <strong>Rs {subtotal.toLocaleString("en-IN")}</strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--t2)" }}>Delivery</span>
              <strong style={{ color: deliveryFee === 0 ? "var(--green)" : "var(--t1)" }}>
                {deliveryFee === 0 ? "Free" : `Rs ${DELIVERY_FEE}`}
              </strong>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 15 }}>
              <span>Total</span>
              <strong style={{ color: "var(--orange)" }}>Rs {total.toLocaleString("en-IN")}</strong>
            </div>
          </div>

          {inCartItems.length > 0 && subtotal < FREE_THRESHOLD && (
            <div style={{ marginTop: 10, fontSize: 12, color: "var(--amber)" }}>
              Add Rs {amountForFreeDelivery.toLocaleString("en-IN")} more to unlock free delivery.
            </div>
          )}

          {inCartItems.length > 0 && subtotal >= FREE_THRESHOLD && (
            <div style={{ marginTop: 10, fontSize: 12, color: "var(--green)", fontWeight: 600 }}>
              Free delivery unlocked.
            </div>
          )}

          <button
            className="btn btn-or"
            type="button"
            disabled={inCartItems.length === 0}
            onClick={onProceedToCheckout}
          >
            Proceed to Checkout
          </button>
        </div>
      </div>
    </div>
  );
}
