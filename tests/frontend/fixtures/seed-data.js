/**
 * Test data fixtures for E2E tests
 */

export const testRelease = {
  name: "Test Release",
  version: "1.0.0-test",
  description: "Release for E2E testing",
  status: "planning",
  release_date: new Date().toISOString().split('T')[0],
};

export const testRequirement = {
  title: "E2E Test Requirement",
  description: "A requirement created for end-to-end testing",
  source: "manual",
  category: "functionality",
  priority: "medium",
  acceptance_criteria: "Test can be executed successfully",
};

export const testCase = {
  title: "E2E Test Case",
  description: "Verify user can login successfully",
  priority: "high",
  test_type: "manual",
  status: "ready",
  preconditions: "User account exists",
  steps: [
    {
      step_number: 1,
      action: "Navigate to login page",
      expected_result: "Login form is displayed"
    },
    {
      step_number: 2,
      action: "Enter valid credentials",
      expected_result: "Credentials are accepted"
    },
    {
      step_number: 3,
      action: "Click login button",
      expected_result: "User is redirected to dashboard"
    }
  ]
};

export const testExecution = {
  execution_type: "manual",
  result: "passed",
  executed_by: "E2E Test User",
  notes: "Test executed successfully via automation",
  duration_seconds: 120,
};

/**
 * API endpoints for services
 */
export const API_ENDPOINTS = {
  requirements: 'http://localhost:8001',
  testcases: 'http://localhost:8002',
  releases: 'http://localhost:8004',
  executions: 'http://localhost:8005',
  automations: 'http://localhost:8006',
};

/**
 * Helper to create test data via API
 */
export async function createTestRelease(request, customData = {}) {
  const response = await request.post(`${API_ENDPOINTS.releases}/releases`, {
    data: {
      ...testRelease,
      ...customData,
    },
  });
  return response.json();
}

export async function createTestRequirement(request, releaseId) {
  const response = await request.post(`${API_ENDPOINTS.requirements}/requirements`, {
    data: {
      ...testRequirement,
      release_id: releaseId,
    },
  });
  return response.json();
}

export async function createTestCase(request, requirementId, releaseId) {
  const response = await request.post(`${API_ENDPOINTS.testcases}/testcases`, {
    data: {
      requirement_id: requirementId,
      title: testCase.title,
      gherkin: testCase.description,
      status: testCase.status,
      metadata: {
        requirement_ids: [requirementId],
        release_ids: [releaseId],
        priority: testCase.priority,
        test_type: testCase.test_type,
        preconditions: testCase.preconditions,
        steps: testCase.steps,
        description: testCase.description,
      },
    },
  });
  return response.json();
}

export async function deleteTestData(request, ids) {
  // Clean up in reverse order of creation
  if (ids.automationId) {
    await request.delete(`${API_ENDPOINTS.automations}/automations/${ids.automationId}`);
  }
  if (ids.testCaseId) {
    await request.delete(`${API_ENDPOINTS.testcases}/testcases/${ids.testCaseId}`);
  }
  if (ids.requirementId) {
    await request.delete(`${API_ENDPOINTS.requirements}/requirements/${ids.requirementId}`);
  }
  if (ids.releaseId) {
    await request.delete(`${API_ENDPOINTS.releases}/releases/${ids.releaseId}`);
  }
}

export async function createTestAutomation(request, testCaseId, customData = {}) {
  const response = await request.post(`${API_ENDPOINTS.automations}/automations`, {
    data: {
      test_case_id: testCaseId,
      title: 'E2E Video Automation',
      framework: 'playwright',
      // Script is executed inside the playwright-mcp container; use docker-compose service name.
      script: [
        "await page.goto('http://frontend:5173/');",
        // Ensure the page renders for long enough to produce a meaningful recording.
        'await page.waitForTimeout(2000);',
      ].join('\n'),
      status: 'not_started',
      ...customData,
    },
  });

  return response.json();
}
