# E2E Tests

End-to-end tests for the AI Testing Platform using Playwright.

## Structure

```
tests/
├── frontend/              # Frontend E2E tests
│   ├── test-cases.spec.js
│   ├── requirements.spec.js
│   ├── executions.spec.js
│   └── fixtures/
│       └── seed-data.js
├── playwright.config.js   # Playwright configuration
├── package.json
└── README.md
```

## Prerequisites

1. **Services Running**: Ensure all Docker services are running:
   ```bash
   docker-compose up -d
   ```

2. **Database Seeded**: Run the seed script to populate test data:
   ```bash
   python seed_database.py
   ```

## Installation

Install Playwright and dependencies:

```bash
cd tests
npm install
npx playwright install
```

## Running Tests

### All Tests
```bash
npm test
```

### Frontend Tests Only
```bash
npm run test:frontend
```

### With UI Mode (Interactive)
```bash
npm run test:ui
```

### Headed Mode (See Browser)
```bash
npm run test:headed
```

### Debug Mode
```bash
npm run test:debug
```

### Specific Test File
```bash
npx playwright test frontend/test-cases.spec.js
```

### Video Recording E2E Test
```bash
npx playwright test frontend/video-recording.spec.js --project=chromium --workers=1
```

### Specific Browser
```bash
npx playwright test --project=chromium
npx playwright test --project=firefox
npx playwright test --project=webkit
```

## Test Reports

After running tests, view the HTML report:

```bash
npm run test:report
```

Reports are saved in `playwright-report/` directory.

## Writing Tests

### Test Structure

```javascript
import { test, expect } from '@playwright/test';

test.describe('Feature Name', () => {
  test('should do something', async ({ page }) => {
    await page.goto('/');
    
    // Your test code here
    await expect(page.locator('h1')).toContainText('Expected Text');
  });
});
```

### Using Fixtures

Import test data from fixtures:

```javascript
import { createTestCase, deleteTestData } from './fixtures/seed-data.js';

test.beforeAll(async ({ request }) => {
  const testcase = await createTestCase(request);
  // Use testcase in tests
});
```

### API Testing

Use the `request` fixture for API calls:

```javascript
test('should create via API', async ({ request }) => {
  const response = await request.post('http://localhost:8002/testcases', {
    data: { title: 'New Test Case' }
  });
  expect(response.ok()).toBeTruthy();
});
```

## Best Practices

1. **Isolation**: Each test should be independent
2. **Cleanup**: Use `beforeAll`/`afterAll` for setup/teardown
3. **Waits**: Use `waitForSelector` or `waitForLoadState` instead of hard timeouts
4. **Selectors**: Prefer text/role selectors over CSS classes
5. **Assertions**: Use Playwright's auto-waiting assertions (`expect(locator).toBeVisible()`)

## Debugging

### Playwright Inspector
```bash
npm run test:debug
```

### Generate Tests with Codegen
```bash
npm run codegen
```

This opens a browser where you can interact with the app, and Playwright will generate test code.

### Screenshots and Videos

Failed tests automatically capture:
- Screenshots: `test-results/*/test-failed-*.png`
- Videos: `test-results/*/video.webm`
- Traces: View with `npx playwright show-trace test-results/.../trace.zip`

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Install dependencies
  run: |
    cd tests
    npm ci
    npx playwright install --with-deps

- name: Run tests
  run: |
    cd tests
    npm test

- name: Upload test results
  if: always()
  uses: actions/upload-artifact@v3
  with:
    name: playwright-report
    path: tests/playwright-report/
```

## Common Issues

### Tests Timeout
- Increase timeout in `playwright.config.js`
- Check if services are running: `docker-compose ps`
- Verify frontend is accessible: `curl http://localhost:5173`

### Flaky Tests
- Add proper waits: `await page.waitForLoadState('networkidle')`
- Use auto-retrying assertions
- Avoid hard-coded timeouts

### Element Not Found
- Use `await page.locator('selector').waitFor()` before interaction
- Check if element is in viewport
- Verify selector is correct using `page.locator('selector').highlight()`

## Resources

- [Playwright Documentation](https://playwright.dev)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [API Reference](https://playwright.dev/docs/api/class-playwright)
