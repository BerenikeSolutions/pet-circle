-- Migration 013: Add payment fields to orders table for Razorpay integration
--
-- razorpay_order_id: Razorpay order ID created on the backend (order_xxx)
-- razorpay_payment_id: Razorpay payment ID after user completes payment (pay_xxx)
-- payment_status: pending | awaiting_payment | paid | failed | cod
--
-- Safe to re-run: uses ADD COLUMN IF NOT EXISTS

BEGIN;

ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS razorpay_order_id  VARCHAR(100),
    ADD COLUMN IF NOT EXISTS razorpay_payment_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS payment_status      VARCHAR(20) DEFAULT 'pending';

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE tablename = 'orders' AND indexname = 'ix_orders_razorpay_order_id'
  ) THEN
    CREATE INDEX ix_orders_razorpay_order_id ON orders (razorpay_order_id)
    WHERE razorpay_order_id IS NOT NULL;
  END IF;
END $$;

COMMIT;
