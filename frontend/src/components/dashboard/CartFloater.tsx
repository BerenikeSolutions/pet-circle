"use client";

interface CartFloaterProps {
  unlocked: boolean;
  cartCount: number;
  totalPrice: number;
  onGoToCart: () => void;
}

export default function CartFloater({ unlocked, cartCount, totalPrice, onGoToCart }: CartFloaterProps) {
  return (
    <button className={`floater fl-cart ${!unlocked ? "hidden" : ""}`} onClick={onGoToCart} type="button">
      🛒 {cartCount > 0 ? `${cartCount} item${cartCount > 1 ? "s" : ""} · ₹${totalPrice.toLocaleString()}` : "Cart"}
    </button>
  );
}
