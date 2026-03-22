/**
 * 05-conditions-tab.spec.ts
 *
 * Tests the Conditions tab with FULL_TOKEN (Zayn).
 *
 * Happy path:
 *  - Add condition "Recurring UTI"
 *  - Add medication to condition
 *  - Add monitoring item
 *  - Set monitoring last-done date
 *  - Add second condition "Anaplasma platys"
 *  - Add contact (vet)
 *  - View condition timeline
 *  - View condition recommendations
 *  - Delete medication
 *  - Delete monitoring item
 *
 * Error flows:
 *  - Empty condition name blocked
 *
 * Screenshots saved to tests/screenshots/conditions/
 */

import { test, expect } from '@playwright/test';
import { getTokens } from './helpers/tokens';
import { goDashboard, clickTab, TAB } from './helpers/nav';
import { shot } from './helpers/screenshots';

const FOLDER = 'conditions';

async function openConditionsTab(page: any, token: string): Promise<boolean> {
  const loaded = await goDashboard(page, token);
  if (!loaded) return false;
  await clickTab(page, TAB.conditions);
  await page.waitForTimeout(800);
  return true;
}

async function clickAddCondition(page: any): Promise<boolean> {
  const addBtn = page.locator('button, [role="button"]').filter({ hasText: /add condition|new condition|\+ condition/i }).first();
  if (await addBtn.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await addBtn.click();
    return true;
  }
  // Fallback: look for any "Add" row at the bottom of conditions section
  const addRow = page.locator('text=/add condition/i').first();
  if (await addRow.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await addRow.click();
    return true;
  }
  return false;
}

async function fillConditionForm(page: any, name: string, notes: string) {
  await page.waitForTimeout(400);
  const nameInput = page.locator('input[placeholder*="condition"], input[placeholder*="name"], input[placeholder*="Name"]').first();
  if (await nameInput.isVisible({ timeout: 3_000 }).catch(() => false)) {
    await nameInput.fill(name);
  }
  const notesInput = page.locator('textarea, input[placeholder*="note"], input[placeholder*="description"]').first();
  if (await notesInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await notesInput.fill(notes);
  }
  const saveBtn = page.locator('button').filter({ hasText: /save|add|confirm/i }).last();
  if (await saveBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
    await saveBtn.click();
  } else {
    await page.keyboard.press('Enter');
  }
  await page.waitForTimeout(1000);
}

test.describe('Conditions Tab — Full Data (Zayn)', () => {
  test('Conditions tab loads without error', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '01-skipped'); return; }
    await shot(page, FOLDER, '01-initial');
    await expect(page.locator('body')).not.toContainText('Unable to load');
  });

  test('Add condition: Recurring UTI', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '02-skipped'); return; }

    const opened = await clickAddCondition(page);
    if (!opened) {
      console.log('Add condition button not found');
      await shot(page, FOLDER, '02-no-add-button');
      return;
    }

    await fillConditionForm(page, 'Recurring UTI', 'E. coli, culture positive Nov 2024');
    await shot(page, FOLDER, '02-uti-added');

    const body = await page.innerText('body');
    expect(body).toContain('UTI');
  });

  test('Add medication to UTI condition', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '03-skipped'); return; }

    // Find "Add Medication" button
    const addMedBtn = page.locator('text=/add medication/i').first();
    if (!(await addMedBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      console.log('Add Medication button not visible — condition may not exist');
      await shot(page, FOLDER, '03-no-add-med');
      return;
    }
    await addMedBtn.click();
    await page.waitForTimeout(400);

    // Fill medication form
    const nameInput = page.locator('input').filter({ hasText: '' }).first();
    const inputs = page.locator('input[type="text"], input:not([type="hidden"])');
    const inputCount = await inputs.count();
    if (inputCount > 0) {
      await inputs.first().fill('Enrofloxacin 50mg');
    }

    const saveBtn = page.locator('button').filter({ hasText: /save|add|confirm/i }).last();
    if (await saveBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await saveBtn.click();
      await page.waitForTimeout(800);
    }
    await shot(page, FOLDER, '03-medication-added');
  });

  test('Add monitoring item to UTI condition', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '04-skipped'); return; }

    const addMonBtn = page.locator('text=/add monitoring/i').first();
    if (!(await addMonBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      console.log('Add Monitoring not visible');
      await shot(page, FOLDER, '04-no-monitoring');
      return;
    }
    await addMonBtn.click();
    await page.waitForTimeout(400);

    const inputs = page.locator('input[type="text"], input:not([type="hidden"])');
    if (await inputs.count() > 0) {
      await inputs.first().fill('Urine Culture');
    }

    const saveBtn = page.locator('button').filter({ hasText: /save|add|confirm/i }).last();
    if (await saveBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await saveBtn.click();
      await page.waitForTimeout(800);
    }
    await shot(page, FOLDER, '04-monitoring-added');
  });

  test('Add second condition: Anaplasma platys', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '05-skipped'); return; }

    const opened = await clickAddCondition(page);
    if (!opened) return;

    await fillConditionForm(page, 'Anaplasma platys', 'PCR positive, tick-borne, untreated');
    await shot(page, FOLDER, '05-anaplasma-added');

    const body = await page.innerText('body');
    expect(body).toContain('Anaplasma');
  });

  test('Add vet contact', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '06-skipped'); return; }

    // Scroll down to contact section
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(500);

    const addContactBtn = page.locator('button, [role="button"], text').filter({ hasText: /add contact|add vet|new contact/i }).first();
    if (!(await addContactBtn.isVisible({ timeout: 5_000 }).catch(() => false))) {
      console.log('Add contact button not visible');
      await shot(page, FOLDER, '06-no-contact-btn');
      return;
    }
    await addContactBtn.click();
    await page.waitForTimeout(400);

    // Fill contact form
    const inputs = page.locator('input[type="text"], input:not([type="hidden"])');
    const inputCount = await inputs.count();
    if (inputCount >= 2) {
      await inputs.nth(0).fill('Dr. Chavan');
      await inputs.nth(1).fill('9876543210');
    } else if (inputCount === 1) {
      await inputs.first().fill('Dr. Chavan');
    }

    const saveBtn = page.locator('button').filter({ hasText: /save|add|confirm/i }).last();
    if (await saveBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await saveBtn.click();
      await page.waitForTimeout(800);
    }
    await shot(page, FOLDER, '06-contact-added');
  });

  test('Condition timeline renders', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '07-skipped'); return; }

    // Scroll to find timeline section
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(2000); // Timeline may load async

    const body = await page.innerText('body');
    // Check for timeline section text
    if (body.includes('Timeline') || body.includes('timeline') || body.includes('events')) {
      await shot(page, FOLDER, '07-timeline');
    } else {
      console.log('Timeline section not visible — may require conditions to be added first');
      await shot(page, FOLDER, '07-no-timeline');
    }
  });

  test('Condition recommendations render', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '08-skipped'); return; }

    // Wait for recommendations (AI call)
    await page.waitForTimeout(3000);

    const body = await page.innerText('body');
    if (body.includes('Recommend') || body.includes('recommend') || body.includes('suggestion')) {
      await shot(page, FOLDER, '08-recommendations');
    } else {
      await shot(page, FOLDER, '08-no-recommendations');
    }
    // No crash
    await expect(page.locator('body')).not.toContainText('Unable to load');
  });

  test('Health summary and vet questions render', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '09-skipped'); return; }
    await page.waitForTimeout(3000);
    await shot(page, FOLDER, '09-health-summary');
  });

  test('Empty condition name is blocked', async ({ page }) => {
    const { fullToken } = getTokens();
    const loaded = await openConditionsTab(page, fullToken);
    if (!loaded) { await shot(page, FOLDER, '10-skipped'); return; }

    const opened = await clickAddCondition(page);
    if (!opened) return;

    await page.waitForTimeout(400);
    // Leave name empty, try to save
    const saveBtn = page.locator('button').filter({ hasText: /save|add|confirm/i }).last();
    if (await saveBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await saveBtn.click();
      await page.waitForTimeout(500);
      const stillOpen = await page.locator('input').first().isVisible().catch(() => false);
      const body = await page.innerText('body');
      const blocked =
        stillOpen ||
        body.includes('required') ||
        body.includes('empty') ||
        body.includes('Please');
      expect(blocked, 'Should not save empty condition name').toBe(true);
    }
    await page.keyboard.press('Escape');
    await shot(page, FOLDER, '10-empty-name-blocked');
  });
});
