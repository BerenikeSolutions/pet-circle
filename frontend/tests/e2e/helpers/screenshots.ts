/**
 * screenshots.ts — Helper to save screenshots into organised folders.
 */

import { Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const SCREENSHOTS_ROOT = path.join(__dirname, '..', '..', 'screenshots');

export async function shot(page: Page, folder: string, name: string) {
  const dir = path.join(SCREENSHOTS_ROOT, folder);
  fs.mkdirSync(dir, { recursive: true });
  const filePath = path.join(dir, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: false });
  console.log(`📸 ${folder}/${name}.png`);
}
