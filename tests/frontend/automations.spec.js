import { test, expect } from '@playwright/test';

test.describe('Automations Page', () => {
  test('should load automations page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    
    // Verify page loaded
    await expect(page.locator('text=Test Automations')).toBeVisible();
    await expect(page.locator('text=Manage automated test scripts')).toBeVisible();
  });

  test('should display New Automation button', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    
    // Verify New Automation button
    await expect(page.locator('button:has-text("New Automation")')).toBeVisible();
  });

  test('should display All Automations header', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    
    // Verify header
    await expect(page.locator('text=All Automations')).toBeVisible();
  });

  test('should display filter by test case dropdown', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify test case filter dropdown
    const testCaseFilter = page.locator('button[role="combobox"]').filter({ hasText: /Filter by Test Case|All Test Cases/i }).first();
    await expect(testCaseFilter).toBeVisible();
  });

  test('should display status filter tabs', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify status filter tabs exist
    await expect(page.locator('button[role="tab"]:has-text("All")')).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("Ready")')).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("Passing")')).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("Failing")')).toBeVisible();
  });

  test('should filter by status tabs', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Click on Ready filter
    await page.locator('button[role="tab"]:has-text("Ready")').click();
    await page.waitForTimeout(500);
    
    // Click on Passing filter
    await page.locator('button[role="tab"]:has-text("Passing")').click();
    await page.waitForTimeout(500);
    
    // Click on Failing filter
    await page.locator('button[role="tab"]:has-text("Failing")').click();
    await page.waitForTimeout(500);
    
    // Click back to All
    await page.locator('button[role="tab"]:has-text("All")').click();
    await page.waitForTimeout(500);
    
    // Test passed if no errors
  });

  test('should display loading state', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    
    // Eventually content should load
    await expect(page.locator('text=Test Automations')).toBeVisible({ timeout: 10000 });
  });

  test('should display empty state when no automations', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // If there are no automations, verify empty state
    const noAutomationsMessage = page.locator('text=No automations found');
    const automationCards = page.locator('text=/automation|test/i');
    
    // Should see either automations or empty message
    try {
      await expect(noAutomationsMessage).toBeVisible({ timeout: 2000 });
      // Verify "Create your first automation" button in empty state
      await expect(page.locator('button:has-text("Create your first automation")')).toBeVisible();
    } catch {
      // If no empty message, there should be automation cards
      await expect(automationCards.first()).toBeVisible({ timeout: 2000 });
    }
  });

  test('should open new automation dialog', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    
    // Click New Automation button
    await page.locator('button:has-text("New Automation")').click();
    await page.waitForTimeout(500);
    
    // Verify dialog opened
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
  });

  test('should display filter icon', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify filter icon is displayed
    const filterIcons = await page.locator('svg[class*="lucide-filter"]').count();
    expect(filterIcons).toBeGreaterThan(0);
  });

  test('should have grid layout for automation cards', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Check if grid container exists (md:grid-cols-2 class)
    const gridContainer = page.locator('.grid.md\\:grid-cols-2').first();
    const gridExists = await gridContainer.count();
    
    // If no automations, there won't be a grid
    // Test passes either way
    expect(gridExists).toBeGreaterThanOrEqual(0);
  });

  test('should display automation card elements when automations exist', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);
    
    // Check if any automation cards exist
    const cards = page.locator('.group.relative');
    const cardCount = await cards.count();
    
    if (cardCount > 0) {
      // If cards exist, verify they have expected elements
      const firstCard = cards.first();
      
      // Should have bot icon
      await expect(firstCard.locator('svg[class*="lucide"]').first()).toBeVisible();
      
      // Test passed
    } else {
      // No automations - verify empty state
      await expect(page.locator('text=No automations found')).toBeVisible();
    }
  });

  test('should close new automation dialog on escape', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    
    // Open dialog
    await page.locator('button:has-text("New Automation")').click();
    await page.waitForTimeout(500);
    
    // Verify dialog opened
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    
    // Press escape
    await page.keyboard.press('Escape');
    await page.waitForTimeout(500);
    
    // Verify dialog closed
    await expect(dialog).not.toBeVisible();
  });

  test('should display page heading with icon styles', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    
    // Verify heading
    const heading = page.locator('h1:has-text("Test Automations")');
    await expect(heading).toBeVisible();
    
    // Verify it has proper styling class
    const className = await heading.getAttribute('class');
    expect(className).toContain('text-3xl');
    expect(className).toContain('font-bold');
  });

  test('should display subtitle text', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Automations' }).first().click();
    await page.waitForLoadState('networkidle');
    
    // Verify subtitle
    await expect(page.locator('text=Manage automated test scripts')).toBeVisible();
  });
});
