import { test, expect } from '@playwright/test';

import {
  createTestRelease,
  createTestRequirement,
  createTestCase,
  createTestAutomation,
  deleteTestData,
  API_ENDPOINTS,
} from './fixtures/seed-data.js';

function isWebMHeader(buffer) {
  // WebM/Matroska EBML header starts with 0x1A45DFA3
  return (
    buffer?.length >= 4 &&
    buffer[0] === 0x1a &&
    buffer[1] === 0x45 &&
    buffer[2] === 0xdf &&
    buffer[3] === 0xa3
  );
}

async function fetchVideoWithRetry(request, automationId, attempts = 10) {
  let lastStatus = null;
  let lastBody = null;

  for (let i = 0; i < attempts; i += 1) {
    const response = await request.get(
      `${API_ENDPOINTS.automations}/automations/${automationId}/video`
    );

    lastStatus = response.status();

    if (response.ok()) {
      lastBody = await response.body();
      return { response, body: lastBody };
    }

    // 404 can happen briefly if the file isn't visible yet.
    await new Promise((r) => setTimeout(r, 500));
  }

  return { response: { ok: () => false, status: () => lastStatus }, body: lastBody };
}

test.describe('E2E Video Recording', () => {
  test('Create automation → execute → video exists and non-empty', async ({ request }) => {
    test.setTimeout(120_000);

    const ids = {};

    try {
      const release = await createTestRelease(request, { name: `E2E Video Release ${Date.now()}` });
      ids.releaseId = release.id;

      const requirement = await createTestRequirement(request, ids.releaseId);
      ids.requirementId = requirement.id;

      const testCase = await createTestCase(request, ids.requirementId, ids.releaseId);
      ids.testCaseId = testCase.id;

      const automation = await createTestAutomation(request, ids.testCaseId, {
        title: `E2E Video Automation ${Date.now()}`,
      });
      ids.automationId = automation.id;

      // Execute automation (this triggers Playwright MCP video recording).
      const execResponse = await request.post(
        `${API_ENDPOINTS.automations}/automations/${ids.automationId}/execute`
      );
      expect(execResponse.ok()).toBeTruthy();

      const execJson = await execResponse.json();
      expect(execJson).toMatchObject({
        automation_id: ids.automationId,
        video_available: true,
      });

      // Fetch video and validate it's a real, non-empty WebM.
      const { response: videoResponse, body } = await fetchVideoWithRetry(
        request,
        ids.automationId
      );

      expect(videoResponse.ok()).toBeTruthy();
      expect(videoResponse.status()).toBe(200);

      // FastAPI's FileResponse should set content-type.
      const contentType = (await request.get(
        `${API_ENDPOINTS.automations}/automations/${ids.automationId}/video`
      )).headers()['content-type'];

      expect(contentType).toContain('video/webm');

      expect(body.length).toBeGreaterThan(1024);
      expect(isWebMHeader(body)).toBeTruthy();
    } finally {
      await deleteTestData(request, ids);
    }
  });
});
