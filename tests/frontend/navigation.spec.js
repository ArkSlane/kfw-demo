import { test, expect } from '@playwright/test';

test.describe('Side Navigation', () => {
  test('should display all navigation items', async ({ page }) => {
    await page.goto('/');
    
    // Verify all main navigation items are visible
    await expect(page.getByRole('link', { name: 'Test Plan' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'AI Insights' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Releases' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Requirements' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Test Cases' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Automations' }).first()).toBeVisible();
    await expect(page.getByRole('link', { name: 'Executions' })).toBeVisible();
  });

  test('should display Administration link in footer', async ({ page }) => {
    await page.goto('/');
    
    // Verify Admin link is visible
    await expect(page.getByRole('link', { name: 'Admin' })).toBeVisible();
  });

  test('should display TestMaster branding', async ({ page }) => {
    await page.goto('/');
    
    // Verify branding elements
    await expect(page.getByRole('heading', { name: 'TestMaster' }).first()).toBeVisible();
    await expect(page.locator('text=QA Management')).toBeVisible();
  });

  test('should navigate to Test Plan page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Test Plan' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify URL changed
    expect(page.url()).toContain('/testplan');
  });

  test('should navigate to AI Insights page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'AI Insights' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify URL changed
    expect(page.url()).toContain('/aiinsights');
  });

  test('should navigate to Releases page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Releases' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify URL changed
    expect(page.url()).toContain('/releases');
    
    // Verify page content loaded
    await expect(page.locator('text=All Releases')).toBeVisible({ timeout: 5000 });
  });

  test('should navigate to Requirements page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Requirements' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify URL changed
    expect(page.url()).toContain('/requirements');
    
    // Verify page content loaded
    await expect(page.locator('text=All Requirements')).toBeVisible({ timeout: 5000 });
  });

  test('should navigate to Test Cases page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Test Cases' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify URL changed
    expect(page.url()).toContain('/testcases');
    
    // Verify page content loaded
    await expect(page.locator('text=All Test Cases')).toBeVisible({ timeout: 5000 });
  });

  test('should navigate to Automations page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    
    // Verify URL changed
    expect(page.url()).toContain('/automations');
  });

  test('should navigate to Executions page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify URL changed
    expect(page.url()).toContain('/executions');
    
    // Verify page content loaded
    await expect(page.locator('text=All Executions')).toBeVisible({ timeout: 5000 });
  });

  test('should navigate to Administration page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Admin' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify URL changed
    expect(page.url()).toContain('/admin');
  });

  test('should highlight active navigation item', async ({ page }) => {
    await page.goto('/');
    
    // Navigate to Requirements
    await page.getByRole('link', { name: 'Requirements' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify Requirements link has active styling
    const requirementsLink = page.getByRole('link', { name: 'Requirements' });
    const classes = await requirementsLink.getAttribute('class');
    expect(classes).toContain('bg-blue-50');
    expect(classes).toContain('text-blue-700');
  });

  test('should highlight active Administration link', async ({ page }) => {
    await page.goto('/');
    
    // Navigate to Admin
    await page.getByRole('link', { name: 'Admin' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify Admin link has active styling
    const adminLink = page.getByRole('link', { name: 'Admin' });
    const classes = await adminLink.getAttribute('class');
    expect(classes).toContain('bg-blue-50');
    expect(classes).toContain('text-blue-700');
  });

  test('should navigate between multiple pages', async ({ page }) => {
    await page.goto('/');
    
    // Navigate to Releases
    await page.getByRole('link', { name: 'Releases' }).click();
    await page.waitForLoadState('networkidle');
    expect(page.url()).toContain('/releases');
    
    // Navigate to Requirements
    await page.getByRole('link', { name: 'Requirements' }).click();
    await page.waitForLoadState('networkidle');
    expect(page.url()).toContain('/requirements');
    
    // Navigate to Test Cases
    await page.getByRole('link', { name: 'Test Cases' }).click();
    await page.waitForLoadState('networkidle');
    expect(page.url()).toContain('/testcases');
    
    // Navigate back to Releases
    await page.getByRole('link', { name: 'Releases' }).click();
    await page.waitForLoadState('networkidle');
    expect(page.url()).toContain('/releases');
  });

  test('should display navigation icons', async ({ page }) => {
    await page.goto('/');
    
    // Verify icons are present by checking SVG elements within navigation links
    const navLinks = await page.getByRole('link', { name: /Test Plan|AI Insights|Releases|Requirements|Test Cases|Automations|Executions/ }).all();
    expect(navLinks.length).toBeGreaterThan(0);
    
    // Check that navigation items have icons (SVG elements)
    for (const link of navLinks) {
      const svg = await link.locator('svg').count();
      expect(svg).toBeGreaterThan(0);
    }
  });

  test('should maintain sidebar state during navigation', async ({ page }) => {
    await page.goto('/');
    
    // Verify sidebar is visible initially
    await expect(page.locator('text=TestMaster').first()).toBeVisible();
    
    // Navigate to different pages
    await page.click('text=Requirements');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=TestMaster').first()).toBeVisible();
    
    await page.click('text=Test Cases');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('text=TestMaster').first()).toBeVisible();
  });

  test('should display Navigation group label', async ({ page }) => {
    await page.goto('/');
    
    // Verify the "Navigation" group label is visible
    await expect(page.locator('text=Navigation').first()).toBeVisible();
  });
});
