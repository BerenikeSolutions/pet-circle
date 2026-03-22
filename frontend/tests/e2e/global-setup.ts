/**
 * global-setup.ts
 *
 * Runs once before all Playwright tests.
 * 1. Executes backend/scripts/run_onboarding.py to create two test users:
 *    - FULL: Zayn, Labrador, all values filled in
 *    - EMPTY: Skippy, all optional fields skipped
 * 2. Writes tokens to frontend/tests/.tokens so spec files can read them.
 * 3. Validates both tokens are reachable from localhost:8000.
 */

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as http from 'http';

const TOKENS_FILE = path.join(__dirname, '..', '.tokens');
const BACKEND_URL = 'http://localhost:8000';
const BACKEND_DIR = path.join(__dirname, '..', '..', '..', '..', 'backend');

function pingToken(token: string): Promise<boolean> {
  return new Promise((resolve) => {
    const url = `${BACKEND_URL}/dashboard/${token}`;
    http.get(url, (res) => {
      resolve(res.statusCode === 200);
      res.resume();
    }).on('error', () => resolve(false));
  });
}

export default async function globalSetup() {
  console.log('\n🐾 PetCircle E2E — Global Setup');
  console.log('─'.repeat(50));

  let fullToken: string;
  let emptyToken: string;

  // ── Step 1: Use existing .tokens file OR run onboarding script ─────────────
  if (fs.existsSync(TOKENS_FILE)) {
    console.log(`.tokens file found — skipping onboarding script`);
    const content = fs.readFileSync(TOKENS_FILE, 'utf8');
    const tokenMap: Record<string, string> = {};
    for (const line of content.trim().split('\n')) {
      const [k, v] = line.split('=');
      if (k && v) tokenMap[k.trim()] = v.trim();
    }
    fullToken = tokenMap['FULL_TOKEN'];
    emptyToken = tokenMap['EMPTY_TOKEN'];
  } else {
    console.log('Running onboarding simulation script...');
    let scriptOutput: string;
    const PYTHON = path.join(BACKEND_DIR, '..', '.venv', 'Scripts', 'python.exe');
    const pythonExe = fs.existsSync(PYTHON) ? PYTHON : 'python';
    try {
      scriptOutput = execSync(
        `${pythonExe} scripts/run_onboarding.py`,
        {
          cwd: BACKEND_DIR,
          encoding: 'utf8',
          timeout: 120_000,
          stdio: ['pipe', 'pipe', 'pipe'],
          env: { ...process.env, APP_ENV: 'production' },
        }
      );
    } catch (err: any) {
      const stderr = err.stderr || '';
      const stdout = err.stdout || '';
      throw new Error(
        `Onboarding script failed.\nSTDOUT: ${stdout}\nSTDERR: ${stderr}`
      );
    }

    const lines = scriptOutput.trim().split('\n');
    const tokenMap: Record<string, string> = {};
    for (const line of lines) {
      const [key, val] = line.split('=');
      if (key && val) tokenMap[key.trim()] = val.trim();
    }
    fullToken = tokenMap['FULL_TOKEN'];
    emptyToken = tokenMap['EMPTY_TOKEN'];

    if (!fullToken || !emptyToken) {
      throw new Error(
        `Could not parse tokens from script output:\n${scriptOutput}`
      );
    }

    // Write tokens file
    fs.writeFileSync(TOKENS_FILE, `FULL_TOKEN=${fullToken}\nEMPTY_TOKEN=${emptyToken}\n`);
  }

  console.log(`✅ FULL_TOKEN:  ${fullToken.slice(0, 8)}...`);
  console.log(`✅ EMPTY_TOKEN: ${emptyToken.slice(0, 8)}...`);
  console.log(`Tokens saved to ${TOKENS_FILE}`);

  // ── Step 4: Validate backend is reachable ──────────────────────────────────
  console.log('Validating backend connectivity...');
  const fullOk = await pingToken(fullToken);
  const emptyOk = await pingToken(emptyToken);

  if (!fullOk) {
    throw new Error(
      `Backend not reachable or FULL_TOKEN invalid.\n` +
      `Expected 200 from ${BACKEND_URL}/dashboard/${fullToken}\n` +
      `Ensure backend is running: cd backend && uvicorn app.main:app --reload --port 8000`
    );
  }
  if (!emptyOk) {
    throw new Error(
      `Backend not reachable or EMPTY_TOKEN invalid.\n` +
      `Expected 200 from ${BACKEND_URL}/dashboard/${emptyToken}`
    );
  }

  console.log('✅ Both tokens validated against backend.');
  console.log('─'.repeat(50));
}
