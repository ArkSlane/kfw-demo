import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for AI Testing Platform E2E tests
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './',
  
  // Maximum time one test can run
  timeout: 30 * 1000,
  
  // Run tests in files in parallel
  fullyParallel: true,
  
  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,
  
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  
  // Opt out of parallel tests on CI
  workers: process.env.CI ? 1 : undefined,
  
  // Reporter to use
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
    ['junit', { outputFile: 'test-results/junit.xml' }]
  ],
  
  // Shared settings for all the projects below
  use: {
    // Base URL for all tests
    baseURL: 'http://localhost:5173',
    
    // Collect trace when retrying the failed test
    trace: 'on-first-retry',
    
    // Screenshot on failure
    screenshot: 'only-on-failure',
    
    // Video on failure
    video: 'retain-on-failure',
    
    // API context
    extraHTTPHeaders: {
      'Accept': 'application/json',
    },
  },

  // Configure projects for major browsers
  projects: [
    // Auth setup — runs first to create shared auth state
    {
      name: 'setup',
      testMatch: /auth\.setup\.js/,
      use: { ...devices['Desktop Chrome'] },
    },

    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'test-results/.auth/user.json',
      },
      dependencies: ['setup'],
      testDir: './frontend',
    },

    // Firefox and WebKit require separate auth setup due to
    // Keycloak cookie/token handling differences.
    // Uncomment and add per-browser setup projects if needed.
    //
    // {
    //   name: 'firefox',
    //   use: {
    //     ...devices['Desktop Firefox'],
    //     storageState: 'test-results/.auth/user.json',
    //   },
    //   dependencies: ['setup'],
    //   testDir: './frontend',
    // },
    //
    // {
    //   name: 'webkit',
    //   use: {
    //     ...devices['Desktop Safari'],
    //     storageState: 'test-results/.auth/user.json',
    //   },
    //   dependencies: ['setup'],
    //   testDir: './frontend',
    // },

    // Mobile viewports
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },
  ],

  // Run your local dev server before starting the tests
  // Comment out if services are already running
  // webServer: {
  //   command: 'docker-compose up',
  //   url: 'http://localhost:5173',
  //   reuseExistingServer: !process.env.CI,
  //   timeout: 120 * 1000,
  // },
});
