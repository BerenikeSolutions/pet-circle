"use client";

import { useMemo } from "react";

interface CartViewProps {
  items: CartItem[];
  onBack: () => void;
  onUpdateQuantity: (id: string, quantity: number) => void;
  onRemoveItem: (id: string) => void;
  onProceedToCheckout: () => void;
}

export interface CartItem {
  id: string;
  name: string;
  price: number;
  quantity: number;
  icon?: string;
  section?: string;
}

const DELIVERY_FEE = 49;
const FREE_THRESHOLD = 599;

export default function CartView({
  items,
  onBack,
  onUpdateQuantity,
  onRemoveItem,
  onProceedToCheckout,
}: CartViewProps) {
  const inCartItems = useMemo(() => items.filter((item) => item.quantity > 0), [items]);

  const subtotal = useMemo(() => {
    return inCartItems.reduce((sum, item) => sum + item.price * item.quantity, 0);
  }, [inCartItems]);

  const deliveryFee = subtotal >= FREE_THRESHOLD ? 0 : DELIVERY_FEE;
  const total = subtotal + deliveryFee;
  const amountForFreeDelivery = Math.max(0, FREE_THRESHOLD - subtotal);

  const changeQuantity = (itemId: string, nextQty: number) => {
    if (nextQty <= 0) {
      onRemoveItem(itemId);
      return;
    }
    onUpdateQuantity(itemId, nextQty);
  };

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
            const sku = item.id;
            const section = item.section || "Care";
            return (
              <div className="cart-row" key={item.id}>
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
