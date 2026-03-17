'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import type { DashboardData } from '@/lib/api';
import { MOCK_CART_ITEMS, PAYMENT_METHODS, NET_BANKS } from '@/lib/dashboard-utils';

interface CartViewProps {
  data: DashboardData;
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

export default function CartView({ data, pinnedItemId, onBack }: CartViewProps) {
  const petName = data.pet.name || 'Your Pet';

  const [screen, setScreen] = useState<Screen>('cart');
  const [cart, setCart] = useState<Record<string, boolean>>(() =>
    MOCK_CART_ITEMS.reduce((a, i) => ({ ...a, [i.id]: i.inCart }), {} as Record<string, boolean>)
  );
  const [qtys, setQtys] = useState<Record<string, number>>(() =>
    MOCK_CART_ITEMS.reduce((a, i) => ({ ...a, [i.id]: 1 }), {} as Record<string, number>)
  );
  const [coupon, setCoupon] = useState('');
  const [couponApplied, setCouponApplied] = useState(false);
  const [payMethod, setPayMethod] = useState('upi');
  const [upiId, setUpiId] = useState('');

  // Card state
  const [cardNum, setCardNum] = useState('');
  const [cardName, setCardName] = useState('');
  const [cardExp, setCardExp] = useState('');
  const [cardCvv, setCardCvv] = useState('');

  // Net banking
  const [netBank, setNetBank] = useState('');

  // Address state
  const [addresses, setAddresses] = useState<AddressData[]>([
    { id: 'a1', name: data.owner.full_name || 'Pet Parent', line: 'Mumbai 400001', tag: 'Home', selected: true },
  ]);
  const [addressSheet, setAddressSheet] = useState<AddressSheetState | null>(null);
  const [addrForm, setAddrForm] = useState({ name: '', line: '', tag: 'Home' });

  const selectedAddr = addresses.find(a => a.selected) || addresses[0];

  // Auto-add pinned item to cart on mount
  useEffect(() => {
    if (pinnedItemId) {
      setCart(prev => ({ ...prev, [pinnedItemId]: true }));
    }
  }, [pinnedItemId]);

  // Sort helper: pinned item always first
  const sortWithPin = useCallback((items: typeof MOCK_CART_ITEMS) => {
    if (!pinnedItemId) return items;
    return [...items].sort((a, b) => {
      if (a.id === pinnedItemId) return -1;
      if (b.id === pinnedItemId) return 1;
      return 0;
    });
  }, [pinnedItemId]);

  // Derived cart values
  const { inCart, subtotal, discount, delivery, total } = useMemo(() => {
    const inCart = MOCK_CART_ITEMS.filter(i => cart[i.id]);
    const subtotal = inCart.reduce((s, i) => s + i.price * qtys[i.id], 0);
    const discount = couponApplied ? Math.round(subtotal * 0.1) : 0;
    const delivery = subtotal > 999 ? 0 : 49;
    return { inCart, subtotal, discount, delivery, total: subtotal - discount + delivery };
  }, [cart, qtys, couponApplied]);

  const toggleCart = useCallback((id: string) => setCart(p => ({ ...p, [id]: !p[id] })), []);
  const setQty = useCallback((id: string, v: number) => setQtys(p => ({ ...p, [id]: Math.max(1, v) })), []);

  const urgentItems = useMemo(() => sortWithPin(MOCK_CART_ITEMS.filter(i => i.inCart || i.id === pinnedItemId)), [sortWithPin, pinnedItemId]);
  const recItems = useMemo(() => sortWithPin(MOCK_CART_ITEMS.filter(i => !i.inCart && i.id !== pinnedItemId)), [sortWithPin, pinnedItemId]);

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

  const orderId = `PC-${Math.floor(Math.random() * 90000 + 10000)}`;

  // ─── SUCCESS SCREEN ──────────────────────────────────────────
  if (screen === 'success') {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6" style={{ background: 'var(--bg-app)' }}>
        <div className="max-w-[430px] w-full text-center animate-fadeIn">
          <span className="text-6xl mb-4 block">🎉</span>
          <h1 className="font-display text-2xl font-bold text-gray-900 mb-2">Order Confirmed!</h1>
          <p className="text-sm text-gray-500 mb-6">Order ID: {orderId}</p>

          {/* Itemized receipt */}
          <div className="bg-white rounded-2xl shadow-sm p-4 mb-4 text-left" style={{ border: '1.5px solid rgba(52,199,89,0.2)' }}>
            {inCart.map(i => (
              <div key={i.id} className="flex justify-between items-center py-1.5" style={{ borderBottom: '1px solid #F5F2EE' }}>
                <span className="text-[13px]">{i.icon} {i.name}</span>
                <span className="text-[13px] font-bold" style={{ color: '#D44800' }}>
                  ₹{(i.price * qtys[i.id]).toLocaleString('en-IN')}
                </span>
              </div>
            ))}
            <div className="flex justify-between pt-2 mt-0.5">
              <span className="font-bold text-sm">Total paid</span>
              <span className="font-extrabold text-[15px]" style={{ color: '#D44800' }}>
                ₹{total.toLocaleString('en-IN')}
              </span>
            </div>
          </div>

          {/* Green delivery note */}
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
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-4 bg-white border-b border-gray-100">
            <button onClick={() => setScreen('cart')} className="text-gray-600 text-lg">←</button>
            <h2 className="font-display font-bold text-lg">Payment</h2>
          </div>

          <div className="p-4 space-y-3 pb-32">
            {/* Order Summary Pill */}
            <div className="bg-white rounded-xl px-4 py-3 flex justify-between items-center" style={{ border: '1px solid #E8E4DF' }}>
              <span className="text-[13px] text-gray-600">{inCart.length} items for {petName}</span>
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

                  {/* UPI input */}
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

                  {/* Card input */}
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

                  {/* Net banking chips */}
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
                    <span>Discount (10%)</span>
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
                onClick={() => setScreen('success')}
                className="w-full py-3.5 rounded-2xl text-white font-bold text-[15px]"
                style={{ background: '#D44800' }}
              >
                Pay ₹{total.toLocaleString('en-IN')} →
              </button>
            </div>
          </div>
        </div>

        {/* Address Bottom Sheet (inline) */}
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
  return (
    <div className="min-h-screen" style={{ background: 'var(--bg-app)' }}>
      <div className="max-w-[430px] mx-auto">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-4 bg-white border-b border-gray-100">
          <button onClick={onBack} className="text-gray-600 text-lg">←</button>
          <h2 className="font-display font-bold text-lg">{petName}&apos;s Care Orders</h2>
          <div
            className="ml-auto rounded-full px-2.5 py-0.5 text-xs font-bold text-white"
            style={{ background: '#FF3B30' }}
          >
            {inCart.length} items
          </div>
        </div>

        <div className="p-4 space-y-2 pb-40">
          {/* Pinned item banner */}
          {pinnedItemId && (() => {
            const pinned = MOCK_CART_ITEMS.find(i => i.id === pinnedItemId);
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

          {/* Urgent section */}
          <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mt-1 mb-0.5 pl-0.5">
            🚨 Urgent for {petName}
          </p>
          {urgentItems.map(item => (
            <CartItemRow
              key={item.id} item={item}
              inCart={!!cart[item.id]} qty={qtys[item.id]}
              onToggle={() => toggleCart(item.id)}
              onQtyChange={v => setQty(item.id, v)}
            />
          ))}

          {/* Recommended section */}
          <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wider mt-2 mb-0.5 pl-0.5">
            ✨ Recommended for {petName}
          </p>
          {recItems.map(item => (
            <CartItemRow
              key={item.id} item={item}
              inCart={!!cart[item.id]} qty={qtys[item.id]}
              onToggle={() => toggleCart(item.id)}
              onQtyChange={v => setQty(item.id, v)}
            />
          ))}
        </div>

        {/* Sticky Footer */}
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-100 shadow-lg" style={{ zIndex: 100 }}>
          <div className="max-w-[430px] mx-auto px-4 py-2.5 pb-5">
            {/* Coupon row */}
            <div className="flex gap-2 mb-2">
              <input
                value={coupon} onChange={e => setCoupon(e.target.value)}
                placeholder="Coupon code"
                className="flex-1 px-3 py-1.5 rounded-xl text-xs focus:outline-none"
                style={{ border: '1px solid #E0E0E0' }}
              />
              <button
                onClick={() => { if (coupon.toUpperCase() === 'PETCARE10') setCouponApplied(true); }}
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
                {inCart.length} items · {delivery === 0
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
              disabled={inCart.length === 0}
              className="w-full py-3.5 rounded-2xl text-white font-bold text-[15px] disabled:opacity-50"
              style={{ background: inCart.length ? '#D44800' : '#D1D1D6' }}
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
  item: typeof MOCK_CART_ITEMS[number];
  inCart: boolean;
  qty: number;
  onToggle: () => void;
  onQtyChange: (v: number) => void;
}

function CartItemRow({ item, inCart, qty, onToggle, onQtyChange }: CartItemRowProps) {
  return (
    <div
      className="bg-white rounded-xl transition-all"
      style={{
        border: `1.5px solid ${inCart ? item.tagColor + '55' : '#EBEBEB'}`,
        opacity: inCart ? 1 : 0.6,
      }}
    >
      <div className="flex items-center gap-2.5 px-3 py-2.5">
        {/* Colored icon box */}
        <div
          className="w-[38px] h-[38px] rounded-[10px] flex items-center justify-center text-[19px] shrink-0"
          style={{ background: item.tagColor + '15' }}
        >
          {item.icon}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <span className="font-bold text-[13px] text-gray-900">{item.name}</span>
            <span
              className="text-[9px] font-extrabold px-1.5 py-0.5 rounded shrink-0"
              style={{ background: item.tagColor + '18', color: item.tagColor, letterSpacing: '0.3px' }}
            >
              {item.tag}
            </span>
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

      {/* Qty row + per-item total */}
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
