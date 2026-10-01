import { defineConfig, devices } from '@playwright/test';

// Live evaluation: real FastAPI backend + real Vite proxy, nothing mocked (unlike playwright.config.ts).
// Start a throwaway stack first: backend on :8010 (in-memory SQLite) and `VITE_BACKEND_URL=http://127.0.0.1:8010 vite --port 3010`.
const PORT = Number(process.env.LIVE_PORT ?? 3010);

export default defineConfig({
  testDir: './live',
  testMatch: '**/*.live.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: { baseURL: `http://localhost:${PORT}`, viewport: { width: 1280, height: 800 }, trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } }],
});
