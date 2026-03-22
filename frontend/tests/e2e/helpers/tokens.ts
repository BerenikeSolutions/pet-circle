/**
 * tokens.ts — Read test tokens written by global-setup.ts
 */

import * as fs from 'fs';
import * as path from 'path';

const TOKENS_FILE = path.join(__dirname, '..', '..', '.tokens');

export function getTokens(): { fullToken: string; emptyToken: string } {
  if (!fs.existsSync(TOKENS_FILE)) {
    throw new Error(
      `.tokens file not found at ${TOKENS_FILE}.\n` +
      'Run the Playwright suite (which triggers global-setup) first.'
    );
  }
  const content = fs.readFileSync(TOKENS_FILE, 'utf8');
  const map: Record<string, string> = {};
  for (const line of content.trim().split('\n')) {
    const [k, v] = line.split('=');
    if (k && v) map[k.trim()] = v.trim();
  }
  const fullToken = map['FULL_TOKEN'];
  const emptyToken = map['EMPTY_TOKEN'];
  if (!fullToken || !emptyToken) {
    throw new Error(`Invalid .tokens file content:\n${content}`);
  }
  return { fullToken, emptyToken };
}
