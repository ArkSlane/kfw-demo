/**
 * Playwright global setup — authenticate via Keycloak and save session state.
 *
 * All test specs that use the 'authenticated' storage state will skip the
 * login page entirely.
 */
import { test as setup, expect } from '@playwright/test';

const KEYCLOAK_USER = 'admin';
const KEYCLOAK_PASS = 'admin123';
const AUTH_FILE = 'test-results/.auth/user.json';

setup('authenticate via Keycloak', async ({ page }) => {
  // Navigate to the app — keycloak-js will redirect to the Keycloak login page
  await page.goto('/');

  // Wait for the Keycloak login form to appear
  await page.waitForURL(/.*keycloak.*|.*\/auth\/.*|.*\/realms\/.*/, { timeout: 15000 }).catch(() => {
    // If no redirect happened, auth might be disabled — save state as-is
  });

  // Fill Keycloak login form (if present)
  const usernameField = page.locator('#username');
  if (await usernameField.isVisible({ timeout: 5000 }).catch(() => false)) {
    await usernameField.fill(KEYCLOAK_USER);
    await page.locator('#password').fill(KEYCLOAK_PASS);
    await page.locator('#kc-login').click();

    // Wait for redirect back to the app
    await page.waitForURL('**/testplan**', { timeout: 15000 }).catch(async () => {
      // Fallback: wait for any app page (not keycloak)
      await page.waitForURL(url => !url.toString().includes('keycloak'), { timeout: 10000 });
    });
  }

  // Verify we're in the app
  await expect(page.locator('body')).not.toBeEmpty();

  // Save authentication state
  await page.context().storageState({ path: AUTH_FILE });
});
