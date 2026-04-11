"use client";

import { useMemo, useState } from "react";

export type PaymentMethod = "cod" | "upi" | "card";

export interface CheckoutDetails {
  name: string;
  phone: string;
  address: string;
  pincode: string;
  paymentMethod: PaymentMethod;
  upiId?: string;
  cardNumber?: string;
  cardName?: string;
  cardExpiry?: string;
  cardCvv?: string;
}

interface CheckoutViewProps {
  total: number;
  initialName: string;
  initialPhone?: string;
  onBack: () => void;
  onPlaceOrder: (details: CheckoutDetails) => Promise<void>;
}

export default function CheckoutView({
  total,
  initialName,
  initialPhone,
  onBack,
  onPlaceOrder,
}: CheckoutViewProps) {
  const [name, setName] = useState(initialName || "");
  const [phone, setPhone] = useState(initialPhone || "");
  const [address, setAddress] = useState("");
  const [pincode, setPincode] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("cod");
  const [upiId, setUpiId] = useState("");
  const [cardNumber, setCardNumber] = useState("");
  const [cardName, setCardName] = useState("");
  const [cardExpiry, setCardExpiry] = useState("");
  const [cardCvv, setCardCvv] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const canPlaceOrder = useMemo(() => {
    const baseValid = Boolean(name.trim() && address.trim()) && phone.trim().length === 10 && pincode.trim().length === 6;
    if (!baseValid) return false;
    if (paymentMethod === "upi") return upiId.trim().includes("@");
    if (paymentMethod === "card") return cardNumber.replace(/\s/g, "").length === 16 && cardName.trim().length > 0 && cardExpiry.length === 5 && cardCvv.length === 3;
    return true;
  }, [name, phone, address, pincode, paymentMethod, upiId, cardNumber, cardName, cardExpiry, cardCvv]);

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
        upiId: paymentMethod === "upi" ? upiId.trim() : undefined,
        cardNumber: paymentMethod === "card" ? cardNumber.replace(/\s/g, "") : undefined,
        cardName: paymentMethod === "card" ? cardName.trim() : undefined,
        cardExpiry: paymentMethod === "card" ? cardExpiry : undefined,
        cardCvv: paymentMethod === "card" ? cardCvv : undefined,
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

          {paymentMethod === "upi" && (
            <div className="field" style={{ marginTop: 14, marginBottom: 0 }}>
              <label className="f-lbl" htmlFor="checkout-upi">UPI ID</label>
              <input
                id="checkout-upi"
                className="f-input"
                value={upiId}
                onChange={(e) => setUpiId(e.target.value.trim())}
                placeholder="yourname@upi"
                autoComplete="off"
              />
              <p style={{ marginTop: 4, fontSize: 11, color: "var(--t3)" }}>Enter your UPI handle (e.g. name@okicici)</p>
            </div>
          )}

          {paymentMethod === "card" && (
            <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
              <div className="field" style={{ marginBottom: 0 }}>
                <label className="f-lbl" htmlFor="checkout-card-number">Card Number</label>
                <input
                  id="checkout-card-number"
                  className="f-input"
                  inputMode="numeric"
                  value={cardNumber}
                  onChange={(e) => {
                    const digits = e.target.value.replace(/\D/g, "").slice(0, 16);
                    setCardNumber(digits.replace(/(.{4})/g, "$1 ").trim());
                  }}
                  placeholder="0000 0000 0000 0000"
                  autoComplete="cc-number"
                />
              </div>
              <div className="field" style={{ marginBottom: 0 }}>
                <label className="f-lbl" htmlFor="checkout-card-name">Name on Card</label>
                <input
                  id="checkout-card-name"
                  className="f-input"
                  value={cardName}
                  onChange={(e) => setCardName(e.target.value)}
                  placeholder="As printed on card"
                  autoComplete="cc-name"
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="field" style={{ marginBottom: 0 }}>
                  <label className="f-lbl" htmlFor="checkout-card-expiry">Expiry</label>
                  <input
                    id="checkout-card-expiry"
                    className="f-input"
                    inputMode="numeric"
                    value={cardExpiry}
                    onChange={(e) => {
                      const digits = e.target.value.replace(/\D/g, "").slice(0, 4);
                      setCardExpiry(digits.length > 2 ? `${digits.slice(0, 2)}/${digits.slice(2)}` : digits);
                    }}
                    placeholder="MM/YY"
                    autoComplete="cc-exp"
                  />
                </div>
                <div className="field" style={{ marginBottom: 0 }}>
                  <label className="f-lbl" htmlFor="checkout-card-cvv">CVV</label>
                  <input
                    id="checkout-card-cvv"
                    className="f-input"
                    inputMode="numeric"
                    value={cardCvv}
                    onChange={(e) => setCardCvv(e.target.value.replace(/\D/g, "").slice(0, 3))}
                    placeholder="&bull;&bull;&bull;"
                    autoComplete="cc-csc"
                    type="password"
                  />
                </div>
              </div>
            </div>
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
