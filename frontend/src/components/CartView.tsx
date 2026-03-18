'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import type { DashboardData, CartItemData, CartRecommendation, PlaceOrderResponse } from '@/lib/api';
import {
  getCart, toggleCartItem, updateCartQuantity, addToCart,
  getCartRecommendations, applyCoupon, placeOrder,
} from '@/lib/api';
import { PAYMENT_METHODS, NET_BANKS } from '@/lib/dashboard-utils';

interface CartViewProps {
  data: DashboardData;
  token: string;
  pinnedItemId?: string;
  onBack: () => void;
}

interface AddressData {
  id: string;
  name: string;
  line: string;
  tag: string;
  selected: boolean;
}

interface AddressSheetState {
  mode: 'edit' | 'add';
  id?: string;
}

type Screen = 'cart' | 'payment' | 'success';

export default function CartView({ data, token, pinnedItemId, onBack }: CartViewProps) {
  const petName = data.pet.name || 'Your Pet';

  const [screen, setScreen] = useState<Screen>('cart');
  const [items, setItems] = useState<CartItemData[]>([]);
  const [recommendations, setRecommendations] = useState<CartRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [recsLoading, setRecsLoading] = useState(true);
  const [coupon, setCoupon] = useState('');
  const [couponApplied, setCouponApplied] = useState(false);
  const [discountPercent, setDiscountPercent] = useState(0);
  const [payMethod, setPayMethod] = useState('upi');
  const [upiId, setUpiId] = useState('');
  const [cardNum, setCardNum] = useState('');
  const [cardName, setCardName] = useState('');
  const [cardExp, setCardExp] = useState('');
  const [cardCvv, setCardCvv] = useState('');
  const [netBank, setNetBank] = useState('');
  const [orderResult, setOrderResult] = useState<PlaceOrderResponse | null>(null);
  const [placing, setPlacing] = useState(false);

  // Address state
  const [addresses, setAddresses] = useState<AddressData[]>([
    { id: 'a1', name: data.owner.full_name || 'Pet Parent', line: 'Mumbai 400001', tag: 'Home', selected: true },
  ]);
  const [addressSheet, setAddressSheet] = useState<AddressSheetState | null>(null);
  const [addrForm, setAddrForm] = useState({ name: '', line: '', tag: 'Home' });

  const selectedAddr = addresses.find(a => a.selected) || addresses[0];

  // Load cart items from API
  const loadCart = useCallback(async () => {
    try {
      setLoading(true);
      const cartData = await getCart(token);
      setItems(cartData.items);
    } catch (e) {
      console.error('Failed to load cart:', e);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // Load recommendations from API
  const loadRecommendations = useCallback(async () => {
    try {
      setRecsLoading(true);
      const recs = await getCartRecommendations(token);
      setRecommendations(recs);
    } catch (e) {
      console.error('Failed to load recommendations:', e);
    } finally {
      setRecsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadCart();
    loadRecommendations();
  }, [loadCart, loadRecommendations]);

  // Auto-add pinned item to cart on mount
  useEffect(() => {
    if (pinnedItemId && !loading) {
      const existing = items.find(i => i.product_id === pinnedItemId);
      if (!existing || !existing.in_cart) {
        handleToggle(pinnedItemId);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pinnedItemId, loading]);

  const handleToggle = useCallback(async (productId: string) => {
    try {
      const updated = await toggleCartItem(token, productId);
      setItems(prev => {
        const exists = prev.find(i => i.product_id === productId);
        if (exists) {
          return prev.map(i => i.product_id === productId ? updated : i);
        }
        return [...prev, updated];
      });
      // Remove from recommendations if added
      if (updated.in_cart) {
        setRecommendations(prev => prev.filter(r => r.product_id !== productId));
      }
    } catch (e) {
      console.error('Toggle failed:', e);
    }
  }, [token]);

  const handleAddRecommendation = useCallback(async (rec: CartRecommendation) => {
    try {
      const added = await addToCart(token, {
        product_id: rec.product_id,
        name: rec.name,
        price: rec.price,
        icon: rec.icon,
        sub: rec.sub,
        tag: rec.tag || undefined,
        tag_color: rec.tag_color || undefined,
      });
      setItems(prev => [...prev, added]);
      setRecommendations(prev => prev.filter(r => r.product_id !== rec.product_id));
    } catch (e) {
      console.error('Add to cart failed:', e);
    }
  }, [token]);

  const handleQtyChange = useCallback(async (productId: string, newQty: number) => {
    const qty = Math.max(1, newQty);
    // Optimistic update
    setItems(prev => prev.map(i => i.product_id === productId ? { ...i, quantity: qty } : i));
    try {
      await updateCartQuantity(token, productId, qty);
    } catch (e) {
      console.error('Quantity update failed:', e);
      loadCart(); // Revert on failure
    }
  }, [token, loadCart]);

  const handleApplyCoupon = useCallback(async () => {
    if (!coupon) return;
    try {
      const result = await applyCoupon(token, coupon);
      if (result.valid) {
        setCouponApplied(true);
        setDiscountPercent(result.discount_percent);
      }
    } catch (e) {
      console.error('Coupon failed:', e);
    }
  }, [token, coupon]);

  const handlePlaceOrder = useCallback(async () => {
    setPlacing(true);
    try {
      const result = await placeOrder(token, {
        payment_method: payMethod === 'net' ? 'netbanking' : payMethod,
        address: selectedAddr ? { name: selectedAddr.name, line: selectedAddr.line, tag: selectedAddr.tag } : undefined,
        coupon: couponApplied ? coupon : undefined,
      });
      setOrderResult(result);
      setScreen('success');
    } catch (e) {
      console.error('Order failed:', e);
      alert('Failed to place order. Please try again.');
    } finally {
      setPlacing(false);
    }
  }, [token, payMethod, selectedAddr, couponApplied, coupon]);

  // Derived values
  const inCartItems = useMemo(() => items.filter(i => i.in_cart), [items]);
  const notInCartItems = useMemo(() => items.filter(i => !i.in_cart), [items]);
  const subtotal = useMemo(() => inCartItems.reduce((s, i) => s + i.price * i.quantity, 0), [inCartItems]);
  const discount = useMemo(() => couponApplied ? Math.round(subtotal * discountPercent / 100) : 0, [subtotal, couponApplied, discountPercent]);
  const delivery = subtotal > 999 ? 0 : 49;
  const total = subtotal - discount + delivery;

  // Sort pinned item first
  const sortWithPin = useCallback((arr: CartItemData[]) => {
    if (!pinnedItemId) return arr;
    return [...arr].sort((a, b) => {
      if (a.product_id === pinnedItemId) return -1;
      if (b.product_id === pinnedItemId) return 1;
      return 0;
    });
  }, [pinnedItemId]);

  const openEditAddress = () => {
    setAddrForm({ name: selectedAddr.name, line: selectedAddr.line, tag: selectedAddr.tag });
    setAddressSheet({ mode: 'edit', id: selectedAddr.id });
  };
  const openAddAddress = () => {
    setAddrForm({ name: '', line: '', tag: 'Home' });
    setAddressSheet({ mode: 'add' });
  };
  const saveAddress = () => {
    if (!addrForm.name || !addrForm.line) return;
    if (addressSheet?.mode === 'edit' && addressSheet.id) {
      setAddresses(prev => prev.map(a => a.id === addressSheet.id ? { ...a, ...addrForm } : a));
    } else {
      const newId = 'a' + (addresses.length + 1);
      setAddresses(prev => [...prev.map(a => ({ ...a, selected: false })), { id: newId, ...addrForm, selected: true }]);
    }
    setAddressSheet(null);
  };

  // ─── LOADING ──────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg-app)' }}>
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-t-transparent" style={{ borderColor: '#FFD5C2', borderTopColor: '#D44800' }} />
          <p className="text-gray-500 text-sm">Loading cart...</p>
        </div>
      </div>
    );
  }

  // ─── SUCCESS SCREEN ──────────────────────────────────────────
  if (screen === 'success' && orderResult) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6" style={{ background: 'var(--bg-app)' }}>
        <div className="max-w-[430px] w-full text-center animate-fadeIn">
          <span className="text-6xl mb-4 block">🎉</span>
          <h1 className="font-display text-2xl font-bold text-gray-900 mb-2">Order Confirmed!</h1>
          <p className="text-sm text-gray-500 mb-6">Order ID: {orderResult.order_id}</p>

          <div className="bg-white rounded-2xl shadow-sm p-4 mb-4 text-left" style={{ border: '1.5px solid rgba(52,199,89,0.2)' }}>
            {orderResult.items.map(i => (
              <div key={i.product_id} className="flex justify-between items-center py-1.5" style={{ borderBottom: '1px solid #F5F2EE' }}>
                <span className="text-[13px]">{i.icon} {i.name}</span>
                <span className="text-[13px] font-bold" style={{ color: '#D44800' }}>
                  ₹{i.total.toLocaleString('en-IN')}
                </span>
              </div>
            ))}
            <div className="flex justify-between pt-2 mt-0.5">
              <span className="font-bold text-sm">Total paid</span>
              <span className="font-extrabold text-[15px]" style={{ color: '#D44800' }}>
                ₹{orderResult.total.toLocaleString('en-IN')}
              </span>
            </div>
          </div>

          <div className="rounded-xl px-3.5 py-2.5 mb-5 text-left text-xs" style={{ background: '#F0FFF4', color: '#1A6B2A' }}>
            ✅ Payment received · Estimated delivery 1–2 business days<br />
            🏠 Home vet visit & grooming scheduled for confirmed slots
          </div>

          <button
            onClick={onBack}
            className="w-full py-3.5 rounded-2xl text-white font-semibold text-sm"
            style={{ background: 'var(--brand-gradient)' }}
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  // ─── PAYMENT SCREEN ──────────────────────────────────────────
  if (screen === 'payment') {
    return (
      <div className="min-h-screen" style={{ background: 'var(--bg-app)' }}>
        <div className="max-w-[430px] mx-auto">
          <div className="flex items-center gap-3 px-4 py-4 bg-white border-b border-gray-100">
            <button onClick={() => setScreen('cart')} className="text-gray-600 text-lg">←</button>
            <h2 className="font-display font-bold text-lg">Payment</h2>
          </div>

          <div className="p-4 space-y-3 pb-32">
            <div className="bg-white rounded-xl px-4 py-3 flex justify-between items-center" style={{ border: '1px solid #E8E4DF' }}>
              <span className="text-[13px] text-gray-600">{inCartItems.length} items for {petName}</span>
              <span className="font-extrabold text-base" style={{ color: '#D44800' }}>₹{total.toLocaleString('en-IN')}</span>
            </div>

            {/* Deliver To */}
            <div className="bg-white rounded-xl p-3.5" style={{ border: '1px solid #E8E4DF' }}>
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2">Deliver to</p>
              {addresses.map(addr => (
                <div
                  key={addr.id}
                  onClick={() => setAddresses(prev => prev.map(a => ({ ...a, selected: a.id === addr.id })))}
                  className="flex items-center gap-2.5 py-2 cursor-pointer"
                  style={{ borderBottom: '1px solid #F5F2EE' }}
                >
                  <div
                    className="w-[18px] h-[18px] rounded-full flex items-center justify-center shrink-0"
                    style={{ border: `2px solid ${addr.selected ? '#D44800' : '#C7C7CC'}`, background: addr.selected ? '#D44800' : 'white' }}
                  >
                    {addr.selected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                  </div>
                  <span className="text-lg">📍</span>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-[13px]">{addr.name}</p>
                    <p className="text-xs text-gray-500">{addr.line} · {addr.tag}</p>
                  </div>
                  {addr.selected && (
                    <button
                      onClick={e => { e.stopPropagation(); openEditAddress(); }}
                      className="text-xs font-bold px-1.5 py-0.5"
                      style={{ color: '#D44800', background: 'none', border: 'none' }}
                    >
                      Edit
                    </button>
                  )}
                </div>
              ))}
              <button
                onClick={openAddAddress}
                className="mt-2 flex items-center gap-2 w-full rounded-xl py-2.5 px-3 text-[13px] font-semibold"
                style={{ border: '1.5px dashed rgba(212,72,0,0.4)', color: '#D44800', background: 'none' }}
              >
                <span className="text-base">＋</span> Add new address
              </button>
            </div>

            {/* Payment Methods */}
            <div className="bg-white rounded-xl p-3.5" style={{ border: '1px solid #E8E4DF' }}>
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2.5">Payment method</p>
              {PAYMENT_METHODS.map(pm => (
                <div key={pm.id}>
                  <div
                    onClick={() => setPayMethod(pm.id)}
                    className="flex items-center gap-3 py-2.5 cursor-pointer"
                    style={{ borderBottom: (payMethod === pm.id && ['upi', 'card', 'net'].includes(pm.id)) ? 'none' : '1px solid #F5F2EE' }}
                  >
                    <div
                      className="w-[18px] h-[18px] rounded-full flex items-center justify-center shrink-0"
                      style={{ border: `2px solid ${payMethod === pm.id ? '#D44800' : '#C7C7CC'}`, background: payMethod === pm.id ? '#D44800' : 'white' }}
                    >
                      {payMethod === pm.id && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                    </div>
                    <span className="text-xl">{pm.icon}</span>
                    <div className="flex-1">
                      <p className="font-semibold text-[13px]">{pm.label}</p>
                      <p className="text-[11px] text-gray-500">{pm.sub}</p>
                    </div>
                  </div>

                  {payMethod === 'upi' && pm.id === 'upi' && (
                    <div className="py-2.5 pb-3.5" style={{ borderBottom: '1px solid #F5F2EE' }}>
                      <input
                        value={upiId} onChange={e => setUpiId(e.target.value)}
                        placeholder="Enter UPI ID (e.g. name@upi)"
                        className="w-full px-3.5 py-2.5 rounded-xl text-[13px] focus:outline-none"
                        style={{ border: '1.5px solid #E8E4DF' }}
                      />
                    </div>
                  )}

                  {payMethod === 'card' && pm.id === 'card' && (
                    <div className="py-2.5 pb-3.5 space-y-2" style={{ borderBottom: '1px solid #F5F2EE' }}>
                      <input
                        value={cardNum}
                        onChange={e => setCardNum(e.target.value.replace(/\D/g, '').slice(0, 16).replace(/(.{4})/g, '$1 ').trim())}
                        placeholder="Card number" maxLength={19}
                        className="w-full px-3.5 py-2.5 rounded-xl text-[13px] focus:outline-none"
                        style={{ border: '1.5px solid #E8E4DF' }}
                      />
                      <input
                        value={cardName} onChange={e => setCardName(e.target.value)}
                        placeholder="Name on card"
                        className="w-full px-3.5 py-2.5 rounded-xl text-[13px] focus:outline-none"
                        style={{ border: '1.5px solid #E8E4DF' }}
                      />
                      <div className="flex gap-2">
                        <input
                          value={cardExp}
                          onChange={e => {
                            let v = e.target.value.replace(/\D/g, '');
                            if (v.length >= 2) v = v.slice(0, 2) + '/' + v.slice(2, 4);
                            setCardExp(v);
                          }}
                          placeholder="MM/YY" maxLength={5}
                          className="flex-1 px-3.5 py-2.5 rounded-xl text-[13px] focus:outline-none"
                          style={{ border: '1.5px solid #E8E4DF' }}
                        />
                        <input
                          value={cardCvv}
                          onChange={e => setCardCvv(e.target.value.replace(/\D/g, '').slice(0, 4))}
                          placeholder="CVV" maxLength={4} type="password"
                          className="flex-1 px-3.5 py-2.5 rounded-xl text-[13px] focus:outline-none"
                          style={{ border: '1.5px solid #E8E4DF' }}
                        />
                      </div>
                    </div>
                  )}

                  {payMethod === 'net' && pm.id === 'net' && (
                    <div className="py-2.5 pb-3.5" style={{ borderBottom: '1px solid #F5F2EE' }}>
                      <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2">Select your bank</p>
                      <div className="flex flex-wrap gap-1.5">
                        {NET_BANKS.map(bank => (
                          <button
                            key={bank} onClick={() => setNetBank(bank)}
                            className="px-3 py-1.5 rounded-full text-xs font-medium"
                            style={{
                              border: `1.5px solid ${netBank === bank ? '#D44800' : '#E8E4DF'}`,
                              background: netBank === bank ? '#FFF3EE' : 'white',
                              color: netBank === bank ? '#D44800' : '#555',
                              fontWeight: netBank === bank ? 700 : 500,
                            }}
                          >
                            {bank}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Bill Summary */}
            <div className="bg-white rounded-xl p-3.5" style={{ border: '1px solid #E8E4DF' }}>
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-2.5">Bill summary</p>
              <div className="space-y-1 text-[13px]">
                <div className="flex justify-between py-1" style={{ borderBottom: '1px solid #F5F2EE' }}>
                  <span className="text-gray-600">Subtotal</span>
                  <span className="font-semibold">₹{subtotal.toLocaleString('en-IN')}</span>
                </div>
                {couponApplied && (
                  <div className="flex justify-between py-1 text-green-600" style={{ borderBottom: '1px solid #F5F2EE' }}>
                    <span>Discount ({discountPercent}%)</span>
                    <span className="font-semibold">-₹{discount.toLocaleString('en-IN')}</span>
                  </div>
                )}
                <div className="flex justify-between py-1" style={{ borderBottom: '1px solid #F5F2EE' }}>
                  <span className="text-gray-600">Delivery</span>
                  <span className={`font-semibold ${delivery === 0 ? 'text-green-600' : ''}`}>{delivery === 0 ? 'FREE' : `₹${delivery}`}</span>
                </div>
                <div className="flex justify-between pt-2.5 mt-0.5">
                  <span className="font-bold text-sm">Total</span>
                  <span className="font-extrabold text-base" style={{ color: '#D44800' }}>₹{total.toLocaleString('en-IN')}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Sticky Pay Button */}
          <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 p-4 shadow-lg" style={{ zIndex: 100 }}>
            <div className="max-w-[430px] mx-auto">
              <button
                onClick={handlePlaceOrder}
                disabled={placing}
                className="w-full py-3.5 rounded-2xl text-white font-bold text-[15px] disabled:opacity-50"
                style={{ background: '#D44800' }}
              >
                {placing ? 'Processing...' : `Pay ₹${total.toLocaleString('en-IN')} →`}
              </button>
            </div>
          </div>
        </div>

        {/* Address Bottom Sheet */}
        {addressSheet && (
          <div
            className="fixed inset-0 flex items-end justify-center"
            style={{ background: 'rgba(0,0,0,0.45)', zIndex: 300 }}
            onClick={() => setAddressSheet(null)}
          >
            <div
              onClick={e => e.stopPropagation()}
              className="bg-white w-full max-w-[430px] p-6"
              style={{ borderRadius: '20px 20px 0 0' }}
            >
              <div className="w-10 h-1 bg-gray-300 rounded-full mx-auto mb-5" />
              <h3 className="font-bold text-base mb-1">
                {addressSheet.mode === 'edit' ? 'Edit address' : 'Add new address'}
              </h3>
              <p className="text-xs text-gray-500 mb-5">Delivery details for {petName}&apos;s order</p>

              <div className="space-y-2.5">
                <div>
                  <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Full name</p>
                  <input
                    value={addrForm.name} onChange={e => setAddrForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="e.g. Priya Sharma"
                    className="w-full px-3.5 py-2.5 rounded-xl text-[13px] focus:outline-none"
                    style={{ border: '1.5px solid #E8E4DF' }}
                  />
                </div>
                <div>
                  <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Address & pincode</p>
                  <input
                    value={addrForm.line} onChange={e => setAddrForm(f => ({ ...f, line: e.target.value }))}
                    placeholder="e.g. Mumbai 400001"
                    className="w-full px-3.5 py-2.5 rounded-xl text-[13px] focus:outline-none"
                    style={{ border: '1.5px solid #E8E4DF' }}
                  />
                </div>
                <div>
                  <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Tag</p>
                  <div className="flex gap-2">
                    {['Home', 'Work', 'Other'].map(tag => (
                      <button
                        key={tag} onClick={() => setAddrForm(f => ({ ...f, tag }))}
                        className="flex-1 py-2 rounded-full text-[13px] font-semibold border-none"
                        style={{
                          background: addrForm.tag === tag ? '#D44800' : '#F2EDE8',
                          color: addrForm.tag === tag ? 'white' : '#555',
                        }}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <button
                onClick={saveAddress}
                className="w-full mt-5 py-3 rounded-xl text-white text-sm font-bold border-none"
                style={{ background: addrForm.name && addrForm.line ? '#D44800' : '#D1D1D6', cursor: addrForm.name && addrForm.line ? 'pointer' : 'default' }}
              >
                Save Address
              </button>
              <button
                onClick={() => setAddressSheet(null)}
                className="w-full py-2.5 text-[13px] text-gray-500 mt-1 bg-transparent border-none"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ─── CART SCREEN ─────────────────────────────────────────────
  const sortedInCart = sortWithPin(inCartItems);
  const hasItems = items.length > 0 || recommendations.length > 0;

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-app)' }}>
      <div className="max-w-[430px] mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-4 bg-white border-b border-gray-100">
          <button onClick={onBack} className="text-gray-600 text-lg">←</button>
          <h2 className="font-display font-bold text-lg">{petName}&apos;s Care Orders</h2>
          {inCartItems.length > 0 && (
            <div
              className="ml-auto rounded-full px-2.5 py-0.5 text-xs font-bold text-white"
              style={{ background: '#FF3B30' }}
            >
              {inCartItems.length} items
            </div>
          )}
        </div>

        <div className="p-4 space-y-2 pb-40">
          {/* Pinned item banner */}
          {pinnedItemId && (() => {
            const pinned = items.find(i => i.product_id === pinnedItemId);
            return pinned ? (
              <div
                className="flex items-center gap-2.5 rounded-xl px-3.5 py-2.5 mb-0.5"
                style={{ background: '#FFF6ED', border: '1.5px solid rgba(255,149,0,0.33)' }}
              >
                <span className="text-base">{pinned.icon}</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-bold" style={{ color: '#B86000' }}>Added from your dashboard</p>
                  <p className="text-[11px]" style={{ color: '#8E5A00' }}>{pinned.name} is at the top of your order</p>
                </div>
              </div>
            ) : null;
          })()}

          {/* Empty state */}
          {!hasItems && !recsLoading && (
            <div className="text-center py-12">
              <span className="text-4xl block mb-3">🛒</span>
              <p className="text-gray-500 text-sm">No items in your cart yet.</p>
              <p className="text-gray-400 text-xs mt-1">Recommendations will appear as we analyze {petName}&apos;s needs.</p>
            </div>
          )}

          {/* In-cart items */}
          {sortedInCart.length > 0 && (
            <>
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mt-1 mb-0.5 pl-0.5">
                🛒 In Cart
              </p>
              {sortedInCart.map(item => (
                <CartItemRow
                  key={item.product_id} item={item}
                  inCart={true} qty={item.quantity}
                  onToggle={() => handleToggle(item.product_id)}
                  onQtyChange={v => handleQtyChange(item.product_id, v)}
                />
              ))}
            </>
          )}

          {/* Items removed from cart */}
          {notInCartItems.length > 0 && (
            <>
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mt-2 mb-0.5 pl-0.5">
                Previously Added
              </p>
              {notInCartItems.map(item => (
                <CartItemRow
                  key={item.product_id} item={item}
                  inCart={false} qty={item.quantity}
                  onToggle={() => handleToggle(item.product_id)}
                  onQtyChange={v => handleQtyChange(item.product_id, v)}
                />
              ))}
            </>
          )}

          {/* Recommendations section */}
          {recommendations.length > 0 && (
            <>
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mt-3 mb-0.5 pl-0.5">
                ✨ Recommended for {petName}
              </p>
              {recommendations.map(rec => (
                <RecommendationRow key={rec.product_id} rec={rec} onAdd={() => handleAddRecommendation(rec)} />
              ))}
            </>
          )}

          {recsLoading && (
            <div className="text-center py-4">
              <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: '#FFD5C2', borderTopColor: '#D44800' }} />
              <p className="text-gray-400 text-xs mt-2">Finding recommendations...</p>
            </div>
          )}
        </div>

        {/* Sticky Footer */}
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 shadow-lg" style={{ zIndex: 100 }}>
          <div className="max-w-[430px] mx-auto px-4 py-2.5 pb-5">
            <div className="flex gap-2 mb-2">
              <input
                value={coupon} onChange={e => setCoupon(e.target.value)}
                placeholder="Coupon code"
                className="flex-1 px-3 py-1.5 rounded-xl text-xs focus:outline-none"
                style={{ border: '1px solid #E0E0E0' }}
              />
              <button
                onClick={handleApplyCoupon}
                className="px-3.5 py-1.5 rounded-xl text-xs font-bold border-none whitespace-nowrap"
                style={{
                  background: couponApplied ? '#34C759' : '#F2EDE8',
                  color: couponApplied ? 'white' : '#555',
                }}
              >
                {couponApplied ? '✓ Applied' : 'Apply'}
              </button>
            </div>

            <div className="flex justify-between items-center mb-2">
              <div className="text-xs text-gray-600">
                {inCartItems.length} items · {delivery === 0
                  ? <span className="text-green-600 font-semibold">Free delivery</span>
                  : `₹${delivery} delivery`}
                {couponApplied && <span className="text-green-600 font-semibold"> · −₹{discount} off</span>}
              </div>
              <div className="text-[17px] font-extrabold" style={{ color: '#D44800' }}>
                ₹{total.toLocaleString('en-IN')}
              </div>
            </div>

            <button
              onClick={() => setScreen('payment')}
              disabled={inCartItems.length === 0}
              className="w-full py-3.5 rounded-2xl text-white font-bold text-[15px] disabled:opacity-50"
              style={{ background: inCartItems.length ? '#D44800' : '#D1D1D6' }}
            >
              Proceed to Payment →
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Cart Item Row Component ───────────────────────────────────

interface CartItemRowProps {
  item: CartItemData;
  inCart: boolean;
  qty: number;
  onToggle: () => void;
  onQtyChange: (v: number) => void;
}

function CartItemRow({ item, inCart, qty, onToggle, onQtyChange }: CartItemRowProps) {
  const tagColor = item.tag_color || '#FF9500';
  return (
    <div
      className="bg-white rounded-xl transition-all"
      style={{
        border: `1.5px solid ${inCart ? tagColor + '55' : '#EBEBEB'}`,
        opacity: inCart ? 1 : 0.6,
      }}
    >
      <div className="flex items-center gap-2.5 px-3 py-2.5">
        <div
          className="w-[38px] h-[38px] rounded-[10px] flex items-center justify-center text-[19px] shrink-0"
          style={{ background: tagColor + '15' }}
        >
          {item.icon || '📦'}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="font-bold text-[13px] text-gray-900">{item.name}</span>
            {item.tag && (
              <span
                className="text-[9px] font-extrabold px-1.5 py-0.5 rounded shrink-0"
                style={{ background: tagColor + '18', color: tagColor, letterSpacing: '0.3px' }}
              >
                {item.tag}
              </span>
            )}
          </div>
          <p className="text-[11px] text-gray-400 truncate">{item.sub}</p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-sm font-extrabold" style={{ color: '#D44800' }}>₹{item.price}</span>
          <button
            onClick={onToggle}
            className="w-[26px] h-[26px] rounded-full border-none flex items-center justify-center text-[13px] font-bold shrink-0"
            style={{
              background: inCart ? '#D44800' : '#F2EDE8',
              color: inCart ? 'white' : '#777',
            }}
          >
            {inCart ? '✓' : '＋'}
          </button>
        </div>
      </div>

      {inCart && (
        <div className="flex items-center justify-end gap-1.5 px-3 py-1.5" style={{ borderTop: '1px solid #F5F2EE' }}>
          <button
            onClick={() => onQtyChange(qty - 1)}
            className="w-6 h-6 rounded-[7px] flex items-center justify-center text-[13px] text-gray-700"
            style={{ border: '1px solid #E0E0E0', background: 'white' }}
          >
            −
          </button>
          <span className="font-bold text-[13px] min-w-[14px] text-center">{qty}</span>
          <button
            onClick={() => onQtyChange(qty + 1)}
            className="w-6 h-6 rounded-[7px] flex items-center justify-center text-[13px] text-gray-700"
            style={{ border: '1px solid #E0E0E0', background: 'white' }}
          >
            +
          </button>
          <span className="text-xs font-bold ml-1" style={{ color: '#D44800' }}>
            ₹{(item.price * qty).toLocaleString('en-IN')}
          </span>
        </div>
      )}
    </div>
  );
}

// ─── Recommendation Row Component ──────────────────────────────

interface RecommendationRowProps {
  rec: CartRecommendation;
  onAdd: () => void;
}

function RecommendationRow({ rec, onAdd }: RecommendationRowProps) {
  const tagColor = rec.tag_color || '#007AFF';
  return (
    <div className="bg-white rounded-xl" style={{ border: '1.5px solid #EBEBEB' }}>
      <div className="flex items-center gap-2.5 px-3 py-2.5">
        <div
          className="w-[38px] h-[38px] rounded-[10px] flex items-center justify-center text-[19px] shrink-0"
          style={{ background: tagColor + '15' }}
        >
          {rec.icon}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="font-bold text-[13px] text-gray-900">{rec.name}</span>
            {rec.tag && (
              <span
                className="text-[9px] font-extrabold px-1.5 py-0.5 rounded shrink-0"
                style={{ background: tagColor + '18', color: tagColor, letterSpacing: '0.3px' }}
              >
                {rec.tag}
              </span>
            )}
          </div>
          <p className="text-[11px] text-gray-400 truncate">{rec.sub}</p>
          <p className="text-[10px] mt-0.5" style={{ color: '#D44800' }}>{rec.reason}</p>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {rec.price > 0 && <span className="text-sm font-extrabold" style={{ color: '#D44800' }}>₹{rec.price}</span>}
          <button
            onClick={onAdd}
            className="w-[26px] h-[26px] rounded-full border-none flex items-center justify-center text-[13px] font-bold shrink-0"
            style={{ background: '#F2EDE8', color: '#777' }}
          >
            ＋
          </button>
        </div>
      </div>
    </div>
  );
}
