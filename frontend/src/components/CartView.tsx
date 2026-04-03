"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CartItemData, DashboardData, PlaceOrderResponse } from "@/lib/api";
import { getCart, placeOrder, toggleCartItem, updateCartQuantity } from "@/lib/api";
import CheckoutView from "./cart/CheckoutView";
import type { CheckoutDetails } from "./cart/CheckoutView";
import ConfirmView from "./cart/ConfirmView";

interface CartViewProps {
  data: DashboardData;
  token: string;
  pinnedItemId?: string;
  onBack: () => void;
}

type CartScreen = "cart" | "checkout" | "confirm";

const DELIVERY_FEE = 49;
const FREE_THRESHOLD = 599;

export default function CartView({ data, token, pinnedItemId, onBack }: CartViewProps) {
  const [screen, setScreen] = useState<CartScreen>("cart");
  const [items, setItems] = useState<CartItemData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [orderResult, setOrderResult] = useState<PlaceOrderResponse | null>(null);
  const pinHandledRef = useRef(false);

  const loadCart = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getCart(token);
      setItems(response.items);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load cart.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  const ensurePinnedItem = useCallback(async () => {
    if (!pinnedItemId || pinHandledRef.current || loading) return;
    pinHandledRef.current = true;
    const alreadyPresent = items.some((item) => item.product_id === pinnedItemId && item.in_cart);
    if (alreadyPresent) return;
    try {
      const updatedItem = await toggleCartItem(token, pinnedItemId);
      setItems((prev) => {
        const idx = prev.findIndex((entry) => entry.product_id === updatedItem.product_id);
        if (idx === -1) return [...prev, updatedItem];
        const next = [...prev];
        next[idx] = updatedItem;
        return next;
      });
    } catch {
      // Keep flow non-blocking if pin add fails.
    }
  }, [items, loading, pinnedItemId, token]);

  useEffect(() => {
    loadCart();
  }, [loadCart]);

  useEffect(() => {
    ensurePinnedItem();
  }, [ensurePinnedItem]);

  const inCartItems = useMemo(() => items.filter((item) => item.in_cart), [items]);

  const subtotal = useMemo(() => {
    return inCartItems.reduce((sum, item) => sum + item.price * item.quantity, 0);
  }, [inCartItems]);

  const deliveryFee = subtotal >= FREE_THRESHOLD ? 0 : DELIVERY_FEE;
  const total = subtotal + deliveryFee;
  const amountForFreeDelivery = Math.max(0, FREE_THRESHOLD - subtotal);

  const changeQuantity = async (productId: string, nextQty: number) => {
    const quantity = Math.max(1, nextQty);
    setItems((prev) => prev.map((item) => (item.product_id === productId ? { ...item, quantity } : item)));
    try {
      const updated = await updateCartQuantity(token, productId, quantity);
      setItems((prev) => prev.map((item) => (item.product_id === productId ? updated : item)));
    } catch {
      loadCart();
    }
  };

  const handlePlaceOrder = async (details: CheckoutDetails) => {
    const addressLine = `${details.address}, ${details.pincode}`;
    const result = await placeOrder(token, {
      payment_method: details.paymentMethod,
      address: {
        name: details.name,
        line: addressLine,
        tag: "Home",
      },
    });
    setOrderResult(result);
    setScreen("confirm");
  };

  if (loading) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
        <div className="app">
          <div className="card" style={{ textAlign: "center", color: "var(--t3)" }}>Loading cart...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
        <div className="app">
          <div className="card" style={{ textAlign: "center" }}>
            <p style={{ color: "var(--red)", marginBottom: 10 }}>{error}</p>
            <button type="button" className="btn btn-or" onClick={loadCart}>Retry</button>
          </div>
        </div>
      </div>
    );
  }

  if (screen === "checkout") {
    return (
      <CheckoutView
        total={total}
        initialName={data.owner.full_name || ""}
        onBack={() => setScreen("cart")}
        onPlaceOrder={handlePlaceOrder}
      />
    );
  }

  if (screen === "confirm") {
    const confirmedItems = orderResult?.items?.map((item) => ({
      id: item.product_id,
      product_id: item.product_id,
      icon: item.icon,
      name: item.name,
      sub: null,
      price: item.price,
      tag: null,
      tag_color: null,
      in_cart: true,
      quantity: item.quantity,
    })) || inCartItems;

    return (
      <ConfirmView
        items={confirmedItems}
        totalPaid={orderResult?.total ?? total}
        onBackToDashboard={onBack}
      />
    );
  }

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="app">
        <div className="vh">
          <button className="back-btn" onClick={onBack} type="button" aria-label="Back to dashboard">
            Back
          </button>
          <div className="vh-title">Your Cart</div>
        </div>

        <div className="card" style={{ marginBottom: 12 }}>
          {inCartItems.length === 0 && (
            <div style={{ textAlign: "center", color: "var(--t3)" }}>No items in cart yet.</div>
          )}

          {inCartItems.map((item) => {
            const sku = item.product_id;
            const section = item.tag || item.sub || "Care";
            return (
              <div className="cart-row" key={item.product_id}>
                <div className="cart-icon" style={{ background: "var(--to)" }}>{item.icon || "PKG"}</div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: "var(--t1)" }}>{item.name}</div>
                  <div style={{ fontSize: 11, color: "var(--t3)" }}>SKU: {sku}</div>
                  <div style={{ fontSize: 11, color: "var(--t3)" }}>Section: {section}</div>
                  <div style={{ marginTop: 4, fontSize: 13, fontWeight: 700, color: "var(--orange)" }}>
                    Rs {item.price.toLocaleString("en-IN")}
                  </div>
                </div>
                <div className="qty">
                  <button className="qty-btn" type="button" onClick={() => changeQuantity(item.product_id, item.quantity - 1)}>
                    -
                  </button>
                  <strong style={{ minWidth: 14, textAlign: "center" }}>{item.quantity}</strong>
                  <button className="qty-btn" type="button" onClick={() => changeQuantity(item.product_id, item.quantity + 1)}>
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
            onClick={() => setScreen("checkout")}
          >
            Proceed to Checkout
          </button>
        </div>
      </div>
    </div>
  );
}
