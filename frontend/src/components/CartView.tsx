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
  onAddBySku: (skuId: string, name: string, price: number, mrp: number, icon: string, section: string, quantity?: number, medicine_type?: string, sub?: string) => void;
}

export interface CartItem {
  id: string;
  name: string;
  sub?: string;
  price: number;
  mrp?: number;
  quantity: number;
  icon?: string;
  section?: string;
  note?: string;
  medicine_type?: string;
}

interface SearchResult {
  sku_id: string;
  category: "food" | "supplement" | "medicine";
  brand_name: string;
  product_name: string;
  name: string;
  pack_size: string;
  mrp: number;
  discounted_price: number;
  in_stock: boolean;
  medicine_type?: string;
  notes?: string;
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

  // Group search results by product identity (brand + product_name) — one row per distinct product
  const groupedResults = useMemo(() => {
    const groups: Record<string, SearchResult[]> = {};
    for (const r of searchResults) {
      const key = `${r.brand_name}||${r.product_name}`;
      if (!groups[key]) groups[key] = [];
      groups[key].push(r);
    }
    return Object.entries(groups).map(([key, skus]) => {
      const [brand, productName] = key.split("||");
      return { brand, productName, skus };
    });
  }, [searchResults]);

  // Open the variant picker for the chosen product group
  const handleSearchGroupAdd = useCallback((skus: SearchResult[]) => {
    const products: ResolvedProduct[] = skus.map((r) => ({
      sku_id: r.sku_id,
      category: r.category,
      brand_name: r.brand_name,
      // food uses product_line for display; supplement/medicine use product_name
      product_line: r.category === "food" ? r.product_name : undefined,
      product_name: r.category !== "food" ? r.product_name : undefined,
      pack_size: r.pack_size,
      mrp: r.mrp,
      discounted_price: r.discounted_price,
      price_per_unit: 0,
      unit_label: "",
      in_stock: r.in_stock,
      vet_diet_flag: false,
      is_highlighted: false,
      medicine_type: r.medicine_type,
      notes: r.notes,
    }));
    setSelectorProducts(products);
    setSelectorOpen(true);
  }, []);

  // Add selected SKU+qty from popup to cart, then return to cart page
  const handleSelectorAdd = useCallback(async (skuId: string, quantity: number) => {
    const product = selectorProducts.find((p) => p.sku_id === skuId);

    // Optimistic update — close popup and add to cart immediately using local product data
    const icon = product?.category === "food" ? "🥣" : "💊";
    const name = product?.category === "food"
      ? (product.product_line || product.brand_name || skuId)
      : (product?.product_name || product?.brand_name || skuId);
    const price = product?.discounted_price ?? 0;
    const mrp = product?.mrp ?? price;
    // For supplements/medicines: sub = "Brand · pack_size"; for food sub = pack_size
    const sub = product?.category === "food"
      ? product?.pack_size
      : (product?.brand_name && product?.pack_size
          ? `${product.brand_name} · ${product.pack_size}`
          : product?.pack_size);
    onAddBySku(skuId, name, price, mrp, icon, "Search", quantity, product?.medicine_type, sub);
    setSelectorOpen(false);
    setSearchQuery("");
    setSearchResults([]);

    // Sync with backend in background (best-effort)
    try {
      await fetch(`${API_BASE}/dashboard/${token}/cart/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sku_id: skuId, quantity }),
      });
    } catch (e) {
      console.error("Failed to sync cart with backend:", e);
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
                fontSize: 16,
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

          {/* Show one row per product — clicking Add opens the variant popup */}
          {groupedResults.length > 0 && (
            <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              {groupedResults.map(({ brand, productName, skus }) => {
                const firstSku = skus[0];
                const allOutOfStock = skus.every((s) => !s.in_stock);
                const alreadyInCart = skus.some((s) => cartSkuIds.has(s.sku_id));
                const minPrice = Math.min(...skus.map((s) => s.discounted_price));
                const maxMrp = Math.max(...skus.map((s) => s.mrp));
                const hasDiscount = maxMrp > minPrice;
                return (
                  <div
                    key={`${brand}||${productName}`}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "10px 0",
                      borderBottom: "1px solid var(--border)",
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 700, color: "var(--t1)" }}>{productName || brand}</div>
                      <div style={{ fontSize: 11, color: "var(--t3)" }}>
                        {brand}
                        {(() => {
                          const available = skus.filter(s => s.in_stock).length;
                          const optionText = skus.length === 1
                            ? firstSku.pack_size
                            : available === 1 ? `1 option` : `${available} options`;
                          return ` · ${optionText}`;
                        })()}
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
                  {item.sub && (
                    <div style={{ fontSize: 11, color: "var(--t3)", marginTop: 1 }}>
                      {item.sub}
                    </div>
                  )}
                  {item.note && (
                    <div style={{ fontSize: 11, color: "#E65100", marginTop: 2, fontStyle: "italic", lineHeight: 1.4 }}>
                      ⚠ {item.note}
                    </div>
                  )}
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
