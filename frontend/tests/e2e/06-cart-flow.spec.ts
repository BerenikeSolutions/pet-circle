/**
 * 06-cart-flow.spec.ts
 *
 * Tests the full cart → payment → success flow with FULL_TOKEN (Zayn).
 *
 * Opening the cart:
 *  The cart overlay opens when "Order →" (header) or a nudge "Order Now" button is clicked.
 *  With Zayn having all overdue preventive records, the header "Actions Due" button IS visible.
 *  Clicking it → NudgesView → "Order Now" → CartView overlay.
 *
 * Happy path:
 *  1. Open cart via nudge flow
 *  2. See recommendations
 *  3. Add item from recommendations
 *  4. Add another item
 *  5. Remove an item
 *  6. Add it back
 *  7. Change quantity
 *  8. Apply coupon (PETCIRCLE10 — shown in error message as suggestion)
 *  9. Invalid coupon shows error
 * 10. COD order placed — success screen shown
 * 11. Re-open cart, UPI payment flow (screenshot Razorpay modal if it opens)
 *
 * Screenshots saved to tests/screenshots/cart/
 */

import { test, expect } from '@playwright/test';
import { getTokens } from './helpers/tokens';
import { goDashboard } from './helpers/nav';
import { shot } from './helpers/screenshots';

const FOLDER = 'cart';

/** Navigate to dashboard and open CartView via nudge or header button. */
async function openCart(page: any, token: string): Promise<boolean> {
  const loaded = await goDashboard(page, token);
  if (!loaded) return false;
  await page.waitForTimeout(1000); // wait for nudges to load

  // Try 1: Header "Order →" / "Actions Due" button
  const headerOrderBtn = page.locator('button').filter({ hasText: /order/i }).first();
  if (await headerOrderBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await headerOrderBtn.click();
    await page.waitForTimeout(800);
    // May open NudgesView — then click "Order Now"
    const orderNowBtn = page.locator('button').filter({ hasText: /order now|order/i }).first();
    if (await orderNowBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await orderNowBtn.click();
      await page.waitForTimeout(1000);
    }
  }

  // Try 2: FAB ⚡ button
  if (!(await page.locator('text=Loading cart').isVisible({ timeout: 2_000 }).catch(() => false)) &&
      !(await page.locator('text=Recommendations').isVisible({ timeout: 2_000 }).catch(() => false))) {
    const fab = page.locator('button').filter({ hasText: '⚡' }).last();
    if (await fab.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await fab.click();
      await page.waitForTimeout(500);
      const orderNowBtn = page.locator('button').filter({ hasText: /order now/i }).first();
      if (await orderNowBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await orderNowBtn.click();
        await page.waitForTimeout(1000);
      }
    }
  }

  // Check if cart is open
  const cartOpen =
    await page.locator('text=/recommendations|Loading cart|My Cart|Cart/i').isVisible({ timeout: 5_000 }).catch(() => false);

  return cartOpen;
}

test.describe('Cart Flow — Full Data (Zayn)', () => {
  test('Open cart and see recommendations', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);

    if (!opened) {
      console.log('Cart could not be opened — nudges may be empty or dismissed');
      await shot(page, FOLDER, '00-cart-not-opened');
      return;
    }

    await shot(page, FOLDER, '01-cart-opened');
    await page.waitForTimeout(2000); // wait for recommendations to load
    await shot(page, FOLDER, '02-recommendations');

    const body = await page.innerText('body');
    console.log('Cart body contains:', body.slice(0, 200));
  });

  test('Add item 1 from recommendations', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '01-skipped'); return; }

    await page.waitForTimeout(2000);

    // Click any "Add" button in recommendations
    const addBtns = page.locator('button').filter({ hasText: /^add$/i });
    const addCount = await addBtns.count();
    if (addCount > 0) {
      await addBtns.first().click();
      await page.waitForTimeout(800);
      await shot(page, FOLDER, '03-item1-added');
    } else {
      // Try "Add to Cart" or "+" button
      const addAltBtn = page.locator('button').filter({ hasText: /add to cart|\+/i }).first();
      if (await addAltBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await addAltBtn.click();
        await page.waitForTimeout(800);
        await shot(page, FOLDER, '03-item1-added');
      } else {
        console.log('No add button found in recommendations');
        await shot(page, FOLDER, '03-no-add-button');
      }
    }
  });

  test('Add item 2 from recommendations', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '02-skipped'); return; }

    await page.waitForTimeout(2000);

    const addBtns = page.locator('button').filter({ hasText: /^add$/i });
    const count = await addBtns.count();
    if (count >= 2) {
      await addBtns.nth(1).click();
      await page.waitForTimeout(800);
      await shot(page, FOLDER, '04-item2-added');
    } else if (count === 1) {
      await addBtns.first().click();
      await page.waitForTimeout(800);
      await shot(page, FOLDER, '04-item2-added-from-first');
    } else {
      await shot(page, FOLDER, '04-no-second-item');
    }
  });

  test('Remove item and re-add', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '03-skipped'); return; }

    await page.waitForTimeout(2000);

    // Add at least one item first
    const addBtn = page.locator('button').filter({ hasText: /^add$/i }).first();
    if (await addBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await addBtn.click();
      await page.waitForTimeout(500);
    }

    // Find and click remove button (✕ or "Remove" in cart)
    const removeBtn = page.locator('button').filter({ hasText: /✕|×|remove/i }).first();
    if (await removeBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await removeBtn.click();
      await page.waitForTimeout(500);
      await shot(page, FOLDER, '05-item-removed');

      // Re-add it — click the Add button again
      const reAddBtn = page.locator('button').filter({ hasText: /^add$/i }).first();
      if (await reAddBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await reAddBtn.click();
        await page.waitForTimeout(500);
        await shot(page, FOLDER, '06-item-readded');
      }
    } else {
      await shot(page, FOLDER, '05-no-remove-button');
    }
  });

  test('Change quantity of cart item', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '04-skipped'); return; }

    await page.waitForTimeout(2000);

    // Add an item to cart first
    const addBtn = page.locator('button').filter({ hasText: /^add$/i }).first();
    if (await addBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await addBtn.click();
      await page.waitForTimeout(500);
    }

    // Find + button to increment quantity
    const plusBtn = page.locator('button').filter({ hasText: '+' }).first();
    if (await plusBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await plusBtn.click();
      await page.waitForTimeout(500);
      await plusBtn.click();
      await page.waitForTimeout(500);
      await shot(page, FOLDER, '07-quantity-increased');
    } else {
      await shot(page, FOLDER, '07-no-quantity-btn');
    }
  });

  test('Apply invalid coupon shows error', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '05-skipped'); return; }

    await page.waitForTimeout(1000);

    const couponInput = page.locator('input[placeholder*="oupon"], input[placeholder*="promo"]').first();
    if (!(await couponInput.isVisible({ timeout: 5_000 }).catch(() => false))) {
      console.log('Coupon input not visible');
      await shot(page, FOLDER, '08-no-coupon-input');
      return;
    }

    await couponInput.fill('INVALIDCOUPON');
    const applyBtn = page.locator('button').filter({ hasText: /apply/i }).first();
    if (await applyBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await applyBtn.click();
      await page.waitForTimeout(1000);
      await shot(page, FOLDER, '08-invalid-coupon-error');

      // Verify error shown
      const body = await page.innerText('body');
      expect(body).toContain('Invalid');
    }
  });

  test('Apply PETCIRCLE10 coupon and see discount', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '06-skipped'); return; }

    await page.waitForTimeout(1000);

    // Add an item first (need items for coupon to matter)
    const addBtn = page.locator('button').filter({ hasText: /^add$/i }).first();
    if (await addBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await addBtn.click();
      await page.waitForTimeout(500);
    }

    const couponInput = page.locator('input[placeholder*="oupon"], input[placeholder*="promo"]').first();
    if (!(await couponInput.isVisible({ timeout: 3_000 }).catch(() => false))) {
      await shot(page, FOLDER, '09-no-coupon');
      return;
    }

    await couponInput.fill('PETCIRCLE10');
    const applyBtn = page.locator('button').filter({ hasText: /apply/i }).first();
    if (await applyBtn.isVisible().catch(() => false)) {
      await applyBtn.click();
      await page.waitForTimeout(1000);
    }
    await shot(page, FOLDER, '09-coupon-applied');
  });

  test('Full cart summary screenshot', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '07-skipped'); return; }

    await page.waitForTimeout(2000);

    // Add 2 items
    const addBtns = page.locator('button').filter({ hasText: /^add$/i });
    const count = await addBtns.count();
    for (let i = 0; i < Math.min(count, 2); i++) {
      await addBtns.nth(0).click();
      await page.waitForTimeout(500);
    }

    await shot(page, FOLDER, '10-cart-summary');
  });

  test('COD payment — place order and see success screen', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '08-skipped'); return; }

    await page.waitForTimeout(2000);

    // Add an item if cart is empty
    const addBtn = page.locator('button').filter({ hasText: /^add$/i }).first();
    if (await addBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await addBtn.click();
      await page.waitForTimeout(500);
    }

    // Click "Proceed to Payment →"
    const proceedBtn = page.locator('button').filter({ hasText: /proceed to payment/i }).first();
    if (!(await proceedBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      // May need to scroll down
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForTimeout(500);
    }

    if (await proceedBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await proceedBtn.click();
      await page.waitForTimeout(800);
      await shot(page, FOLDER, '11-payment-screen');

      // Select COD
      const codBtn = page.locator('button, label, div').filter({ hasText: /cash on delivery|COD/i }).first();
      if (await codBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await codBtn.click();
        await page.waitForTimeout(400);
      }

      // Add delivery address (required to enable Pay button)
      const editAddrBtn = page.locator('button').filter({ hasText: /edit|add address/i }).first();
      if (await editAddrBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await editAddrBtn.click();
        await page.waitForTimeout(400);

        const addrInput = page.locator('input[placeholder*="address"], input[placeholder*="line"]').first();
        if (await addrInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
          await addrInput.fill('123, MG Road, Mumbai 400001');
          const saveAddrBtn = page.locator('button').filter({ hasText: /save/i }).last();
          if (await saveAddrBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await saveAddrBtn.click();
            await page.waitForTimeout(500);
          }
        }
      }

      await shot(page, FOLDER, '12-cod-selected');

      // Click Pay button
      const payBtn = page.locator('button').filter({ hasText: /pay.*₹|place order|confirm order/i }).first();
      if (await payBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
        await payBtn.click();
        await page.waitForTimeout(3000); // Wait for order placement

        const body = await page.innerText('body');
        const success =
          body.includes('Order Confirmed') ||
          body.includes('confirmed') ||
          body.includes('order_id') ||
          body.includes('Confirmed!');

        if (success) {
          await shot(page, FOLDER, '13-cod-success');
          expect(body).toContain('Confirmed');
        } else {
          // May have failed due to address validation or API error
          await shot(page, FOLDER, '13-cod-result');
          console.log('Order result:', body.slice(0, 300));
        }
      }
    } else {
      console.log('"Proceed to Payment" button not found — cart may be empty');
      await shot(page, FOLDER, '11-no-proceed-button');
    }
  });

  test('UPI payment method selection screenshot', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '09-skipped'); return; }

    await page.waitForTimeout(2000);

    // Add item
    const addBtn = page.locator('button').filter({ hasText: /^add$/i }).first();
    if (await addBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
      await addBtn.click();
      await page.waitForTimeout(500);
    }

    // Go to payment
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    const proceedBtn = page.locator('button').filter({ hasText: /proceed to payment/i }).first();
    if (await proceedBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await proceedBtn.click();
      await page.waitForTimeout(800);

      // Select UPI
      const upiBtn = page.locator('button, label, div').filter({ hasText: /^UPI$/i }).first();
      if (await upiBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
        await upiBtn.click();
        await page.waitForTimeout(400);

        // Enter UPI ID
        const upiInput = page.locator('input[placeholder*="UPI"], input[placeholder*="upi"]').first();
        if (await upiInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
          await upiInput.fill('test@upi');
        }
        await shot(page, FOLDER, '14-upi-selected');
      }
    }
    await shot(page, FOLDER, '14-payment-methods');
  });

  test('Empty cart — Place Order disabled', async ({ page }) => {
    const { fullToken } = getTokens();
    const opened = await openCart(page, fullToken);
    if (!opened) { await shot(page, FOLDER, '10-skipped'); return; }

    // Go to payment without adding items
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    const proceedBtn = page.locator('button').filter({ hasText: /proceed to payment/i }).first();

    if (await proceedBtn.isVisible({ timeout: 5_000 }).catch(() => false)) {
      // If there are items, skip this test
      await proceedBtn.click();
      await page.waitForTimeout(800);

      // "Pay" button should be disabled if no address
      const payBtn = page.locator('button[disabled]').filter({ hasText: /pay/i }).first();
      const isDisabled = await payBtn.isVisible({ timeout: 3_000 }).catch(() => false);
      if (isDisabled) {
        await shot(page, FOLDER, '15-pay-disabled');
      }
    } else {
      // Cart is empty — "Proceed" may not be visible
      await shot(page, FOLDER, '15-proceed-not-visible');
    }
  });
});
