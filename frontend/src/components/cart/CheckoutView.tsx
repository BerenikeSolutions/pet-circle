"use client";

import { useMemo, useState } from "react";

export type PaymentMethod = "cod" | "upi" | "card";

export interface CheckoutDetails {
  name: string;
  phone: string;
  address: string;
  pincode: string;
  paymentMethod: PaymentMethod;
}

interface CheckoutViewProps {
  total: number;
  initialName: string;
  initialPhone?: string;
  initialPincode?: string;
  initialAddress?: string;
  initialPaymentMethod?: PaymentMethod;
  onBack: () => void;
  onPlaceOrder: (details: CheckoutDetails) => Promise<void>;
}

export default function CheckoutView({
  total,
  initialName,
  initialPhone,
  initialPincode,
  initialAddress,
  initialPaymentMethod,
  onBack,
  onPlaceOrder,
}: CheckoutViewProps) {
  const [name, setName] = useState(initialName || "");
  const [phone, setPhone] = useState(initialPhone || "");
  const [address, setAddress] = useState(initialAddress || "");
  const [pincode, setPincode] = useState(initialPincode || "");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>(initialPaymentMethod || "cod");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const canPlaceOrder = useMemo(
    () =>
      Boolean(name.trim() && address.trim()) &&
      phone.trim().length === 10 &&
      pincode.trim().length === 6,
    [name, phone, address, pincode]
  );

  const submit = async () => {
    if (!canPlaceOrder || submitting) return;
    setSubmitting(true);
    setSubmitError("");
    try {
      await onPlaceOrder({
        name: name.trim(),
        phone: phone.trim(),
        address: address.trim(),
        pincode: pincode.trim(),
        paymentMethod,
      });
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Failed to place order.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-app)" }}>
      <div className="app">
        <div className="vh">
          <button className="back-btn" onClick={onBack} type="button" aria-label="Back to cart">
            &#8592;
          </button>
          <div className="vh-title">Checkout</div>
        </div>

        <div className="card">
          <div className="field">
            <label className="f-lbl" htmlFor="checkout-name">Name</label>
            <input
              id="checkout-name"
              className="f-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Full name"
            />
          </div>
          <div className="field">
            <label className="f-lbl" htmlFor="checkout-phone">Phone</label>
            <input
              id="checkout-phone"
              type="tel"
              inputMode="numeric"
              className="f-input"
              value={phone}
              onChange={(e) => setPhone(e.target.value.replace(/\D/g, "").slice(0, 10))}
              placeholder="10-digit number"
            />
          </div>
          <div className="field">
            <label className="f-lbl" htmlFor="checkout-address">Address</label>
            <textarea
              id="checkout-address"
              className="f-input"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="House, street, locality"
              rows={3}
            />
          </div>
          <div className="field" style={{ marginBottom: 0 }}>
            <label className="f-lbl" htmlFor="checkout-pincode">Pincode</label>
            <input
              id="checkout-pincode"
              type="tel"
              inputMode="numeric"
              className="f-input"
              value={pincode}
              onChange={(e) => setPincode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              placeholder="6-digit pincode"
            />
          </div>
        </div>

        <div className="card">
          <div className="sec-lbl">Payment</div>
          <div style={{ display: "grid", gap: 10 }}>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="radio"
                name="paymentMethod"
                checked={paymentMethod === "cod"}
                onChange={() => setPaymentMethod("cod")}
              />
              Cash on Delivery
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="radio"
                name="paymentMethod"
                checked={paymentMethod === "upi"}
                onChange={() => setPaymentMethod("upi")}
              />
              UPI
            </label>
            <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="radio"
                name="paymentMethod"
                checked={paymentMethod === "card"}
                onChange={() => setPaymentMethod("card")}
              />
              Debit / Credit Card
            </label>
          </div>

          {(paymentMethod === "upi" || paymentMethod === "card") && (
            <p style={{ marginTop: 12, fontSize: 12, color: "var(--t3)" }}>
              {paymentMethod === "upi"
                ? "You will enter your UPI ID in the payment screen."
                : "You will enter your card details in the payment screen."}
            </p>
          )}
        </div>

        <div className="card" style={{ marginBottom: 80 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
            <span style={{ color: "var(--t2)" }}>Total</span>
            <strong style={{ color: "var(--orange)" }}>Rs {total.toLocaleString("en-IN")}</strong>
          </div>
          {submitError && (
            <p style={{ marginTop: 10, fontSize: 12, color: "var(--red)" }}>{submitError}</p>
          )}
          <button className="btn btn-or" type="button" disabled={!canPlaceOrder || submitting} onClick={submit}>
            {submitting ? "Placing Order..." : "Place Order"}
          </button>
        </div>
      </div>
    </div>
  );
}
