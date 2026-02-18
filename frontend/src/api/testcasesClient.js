import { createApiClient } from './httpClient';

const API_BASE_URL = 'http://localhost:8002';

const client = createApiClient(API_BASE_URL);

export const testcasesAPI = {
  // List all testcases
  list: async (q = null, limit = 50, skip = 0) => {
    try {
      const params = { limit, skip };
      if (q) params.q = q;
      const response = await client.get('/testcases', { params });
      return Array.isArray(response.data) ? response.data : response.data.data || [];
    } catch (error) {
      // Silently fail - services not running yet
      return [];
    }
  },

  // Get a single testcase
  get: async (testcaseId) => {
    try {
      const response = await client.get(`/testcases/${testcaseId}`);
      return response.data;
    } catch (error) {
      return null;
    }
  },

  // Create a new testcase
  create: async (data) => {
    try {
      const response = await client.post('/testcases', data);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Update a testcase
  update: async (testcaseId, data) => {
    try {
      const response = await client.put(`/testcases/${testcaseId}`, data);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Delete a testcase
  delete: async (testcaseId) => {
    try {
      const response = await client.delete(`/testcases/${testcaseId}`);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Health check
  health: async () => {
    try {
      const response = await client.get('/health');
      return response.data;
    } catch (error) {
      return null;
    }
  },
};
