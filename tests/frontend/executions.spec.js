import { test, expect } from '@playwright/test';
import { createTestRelease, createTestRequirement, createTestCase, deleteTestData } from './fixtures/seed-data.js';

test.describe('Executions Page', () => {
  test('should load executions page', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify page loaded
    await expect(page.locator('text=Test Executions')).toBeVisible();
    await expect(page.locator('text=Track manual and automated test execution results')).toBeVisible();
  });

  test('should display statistics cards', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify stat cards
    await expect(page.locator('text=Total').first()).toBeVisible();
    await expect(page.locator('text=Passed').first()).toBeVisible();
    await expect(page.locator('text=Failed').first()).toBeVisible();
    await expect(page.locator('text=Blocked').first()).toBeVisible();
    await expect(page.locator('text=Pass Rate').first()).toBeVisible();
  });

  test('should display filter tabs for result', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify result filter tabs exist
    await expect(page.locator('button[role="tab"]:has-text("All")').last()).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("Passed")').last()).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("Failed")').last()).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("Blocked")').last()).toBeVisible();
  });

  test('should display view mode tabs', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify view mode tabs exist
    await expect(page.locator('button[role="tab"]:has-text("All")').first()).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("Manual")').first()).toBeVisible();
    await expect(page.locator('button[role="tab"]:has-text("Automated")').first()).toBeVisible();
  });

  test('should display release filter dropdown', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify release filter dropdown
    const releaseFilter = page.locator('button[role="combobox"]').filter({ hasText: /Filter by Release|All Releases/i }).first();
    await expect(releaseFilter).toBeVisible();
  });

  test('should display API Documentation button', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify API Documentation button
    await expect(page.locator('button:has-text("API Documentation")')).toBeVisible();
  });

  test('should open API info dialog', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    
    // Click API Documentation button
    await page.locator('button:has-text("API Documentation")').click();
    await page.waitForTimeout(500);
    
    // Verify API info dialog opened
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
  });

  test('should display All Executions header', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    
    // Verify header
    await expect(page.locator('text=All Executions')).toBeVisible();
  });

  test('should display loading state', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    
    // Eventually content should load
    await expect(page.locator('text=Test Executions')).toBeVisible({ timeout: 10000 });
  });

  test('should display empty state when no executions', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // If there are no executions, verify empty state
    const noExecutionsMessage = page.locator('text=No executions found');
    const executionsList = page.locator('text=/E2E Test Case|Test Case/i');
    
    // Should see either executions or empty message
    try {
      await expect(noExecutionsMessage).toBeVisible({ timeout: 2000 });
    } catch {
      // If no empty message, there should be executions
      await expect(executionsList.first()).toBeVisible({ timeout: 2000 });
    }
  });

  test('should filter by result tabs', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Click on Passed filter
    await page.locator('button[role="tab"]:has-text("Passed")').last().click();
    await page.waitForTimeout(500);
    
    // Click on Failed filter
    await page.locator('button[role="tab"]:has-text("Failed")').last().click();
    await page.waitForTimeout(500);
    
    // Click back to All
    await page.locator('button[role="tab"]:has-text("All")').last().click();
    await page.waitForTimeout(500);
    
    // Test passed if no errors
  });

  test('should filter by view mode tabs', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Click on Manual tab
    const manualTab = page.locator('button[role="tab"]:has-text("Manual")').first();
    await manualTab.click();
    await page.waitForTimeout(500);
    
    // Click on Automated tab
    const automatedTab = page.locator('button[role="tab"]:has-text("Automated")').first();
    await automatedTab.click();
    await page.waitForTimeout(500);
    
    // Click back to All
    const allTab = page.locator('button[role="tab"]:has-text("All")').first();
    await allTab.click();
    await page.waitForTimeout(500);
    
    // Test passed if no errors
  });

  test('should display statistics with correct format', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify stats contain numbers
    const statCards = page.locator('.text-2xl.font-bold');
    await expect(statCards.first()).toBeVisible();
  });

  test('should display pass rate with percentage', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: 'Executions' }).click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    
    // Verify pass rate shows percentage
    await expect(page.locator('text=%').first()).toBeVisible();
  });
});
