"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ProductSelectorCard, { type ResolvedProduct } from "./dashboard/ProductSelectorCard";

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
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ProductSelectorCard state
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectorProducts, setSelectorProducts] = useState<ResolvedProduct[]>([]);

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

  // Group search results by brand_name — show one row per brand
  const groupedResults = useMemo(() => {
    const groups: Record<string, SearchResult[]> = {};
    for (const r of searchResults) {
      if (!groups[r.brand_name]) groups[r.brand_name] = [];
      groups[r.brand_name].push(r);
    }
    return Object.entries(groups).map(([brand, skus]) => ({ brand, skus }));
  }, [searchResults]);

  // Open ProductSelectorCard with the brand's SKUs
  const handleSearchGroupAdd = useCallback((skus: SearchResult[]) => {
    const products: ResolvedProduct[] = skus.map((r) => ({
      sku_id: r.sku_id,
      category: r.category,
      brand_name: r.brand_name,
      product_line: r.name,
      pack_size: r.pack_size,
      mrp: r.mrp,
      discounted_price: r.discounted_price,
      price_per_unit: 0,
      unit_label: "",
      in_stock: r.in_stock,
      vet_diet_flag: false,
      is_highlighted: false,
    }));
    setSelectorProducts(products);
    setSelectorOpen(true);
  }, []);

  // Add selected SKU+qty from popup to cart, then return to cart page
  const handleSelectorAdd = useCallback(async (skuId: string, quantity: number) => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/${token}/cart/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku_id: skuId, quantity }),
      });
      if (!res.ok) throw new Error("add failed");
      const data = await res.json();
      const product = selectorProducts.find((p) => p.sku_id === skuId);
      const icon = product?.category === "food" ? "🥣" : "💊";
      onAddBySku(skuId, data.name, data.price, product?.mrp ?? data.price, icon, "Search");
      setSelectorOpen(false);
      setSearchQuery("");
      setSearchResults([]);
    } catch (e) {
      console.error("Failed to add to cart:", e);
    }
  }, [token, selectorProducts, onAddBySku]);

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
        <div
          style={{
            padding: '14px 16px',
            borderBottom: '1px solid var(--border, #e0e0e0)',
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            background: 'var(--white, #fff)',
          }}
        >
          <button
            onClick={onBack}
            style={{
              width: 34,
              height: 34,
              borderRadius: '50%',
              border: '1.5px solid var(--border, #e0e0e0)',
              background: 'var(--white, #fff)',
              fontSize: 16,
              cursor: 'pointer',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--t1, #111)',
              lineHeight: 1,
            }}
            type="button"
            aria-label="Back"
          >
            &larr;
          </button>
          <div
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: 'var(--t1, #000)',
              letterSpacing: '-0.01em',
              lineHeight: 1.1,
            }}
          >
            Your Cart
          </div>
        </div>

        {/* Search bar */}
        <div className="card" style={{ marginTop: 12, marginBottom: 12 }}>
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

          {searchQuery.length >= 2 && !searchLoading && groupedResults.length === 0 && (
            <div style={{ marginTop: 10, fontSize: 13, color: "var(--t3)", textAlign: "center" }}>
              No products found
            </div>
          )}

          {/* Show one row per brand — clicking Add opens the variant popup */}
          {groupedResults.length > 0 && (
            <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              {groupedResults.map(({ brand, skus }) => {
                const firstSku = skus[0];
                const allOutOfStock = skus.every((s) => !s.in_stock);
                const alreadyInCart = skus.some((s) => cartSkuIds.has(s.sku_id));
                const minPrice = Math.min(...skus.map((s) => s.discounted_price));
                const maxMrp = Math.max(...skus.map((s) => s.mrp));
                const hasDiscount = maxMrp > minPrice;
                return (
                  <div
                    key={brand}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "10px 0",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "var(--t1)" }}>{brand}</div>
                      <div style={{ fontSize: 11, color: "var(--t3)" }}>
                        {skus.length === 1 ? firstSku.pack_size : `${skus.length} options available`}
                      </div>
                      <div style={{ display: "flex", alignItems: "baseline", gap: 5, marginTop: 2 }}>
                        {hasDiscount && (
                          <span style={{ fontSize: 11, color: "var(--t3)", textDecoration: "line-through" }}>
                            Rs {maxMrp.toLocaleString("en-IN")}
                          </span>
                        )}
                        <span style={{ fontSize: 13, fontWeight: 700, color: "var(--brand-primary)" }}>
                          from Rs {minPrice.toLocaleString("en-IN")}
                        </span>
                      </div>
                    </div>
                    <button
                      type="button"
                      disabled={allOutOfStock || alreadyInCart}
                      onClick={() => handleSearchGroupAdd(skus)}
                      style={{
                        padding: "7px 14px",
                        borderRadius: 8,
                        border: "none",
                        background: alreadyInCart ? "var(--border)" : allOutOfStock ? "var(--border)" : "var(--brand-primary)",
                        color: "var(--white)",
                        fontSize: 12,
                        fontWeight: 700,
                        cursor: allOutOfStock || alreadyInCart ? "default" : "pointer",
                        flexShrink: 0,
                      }}
                    >
                      {alreadyInCart ? "In Cart" : allOutOfStock ? "Out of Stock" : "Add"}
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
            const section = item.section || "Care";
            const hasDiscount = item.mrp !== undefined && item.mrp > item.price;
            return (
              <div className="cart-row" key={item.id}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--t1)" }}>{item.name}</div>
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
                  {item.quantity > 0 && (
                    <div style={{ fontSize: 11, color: "var(--t3)", marginTop: 3 }}>
                      Qty: {item.quantity}
                    </div>
                  )}
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

      {/* Product variant popup — same pattern as dashboard */}
      <ProductSelectorCard
        open={selectorOpen}
        onClose={() => setSelectorOpen(false)}
        products={selectorProducts}
        signalLevel=""
        vetDietWarning={false}
        packSizeSuggestion={null}
        onAddToCart={handleSelectorAdd}
        hideSearchMore
      />
    </div>
  );
}
