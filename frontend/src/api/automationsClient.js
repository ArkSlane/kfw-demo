import { createApiClient } from './httpClient';

// jsconfig.json enables checkJs; cast import.meta to any for Vite env access.
const viteEnv = /** @type {any} */ (import.meta).env;
const AUTOMATIONS_URL = viteEnv?.VITE_AUTOMATIONS_URL || 'http://localhost:8006';

const client = createApiClient(AUTOMATIONS_URL);

const automationsAPI = {
  list: async (test_case_id = null, status = null, limit = 50, skip = 0) => {
    try {
      const params = { limit, skip };
      if (test_case_id) params.test_case_id = test_case_id;
      if (status) params.status = status;
      const response = await client.get('/automations', { params });
      return Array.isArray(response.data) ? response.data : response.data.data || [];
    } catch (error) {
      console.error('Automations API error:', error.response?.data || error.message);
      return [];
    }
  },

  get: async (automationId) => {
    try {
      const response = await client.get(`/automations/${automationId}`);
      return response.data;
    } catch (error) {
      console.error('Automations API error:', error.response?.data || error.message);
      return null;
    }
  },

  create: async (data) => {
    try {
      const response = await client.post('/automations', data);
      return response.data;
    } catch (error) {
      console.error('Automations API error:', error.response?.data || error.message);
      throw error;
    }
  },

  update: async (automationId, data) => {
    try {
      const response = await client.put(`/automations/${automationId}`, data);
      return response.data;
    } catch (error) {
      console.error('Automations API error:', error.response?.data || error.message);
      throw error;
    }
  },

  delete: async (automationId) => {
    try {
      await client.delete(`/automations/${automationId}`);
    } catch (error) {
      console.error('Automations API error:', error.response?.data || error.message);
      throw error;
    }
  },

  execute: async (automationId) => {
    try {
      const response = await client.post(`/automations/${automationId}/execute`);
      return response.data;
    } catch (error) {
      console.error('Automations API error:', error.response?.data || error.message);
      throw error;
    }
  },

  normalizeScript: async (automationId) => {
    try {
      const response = await client.post(`/automations/${automationId}/normalize-script`);
      return response.data;
    } catch (error) {
      console.error('Automations API error:', error.response?.data || error.message);
      throw error;
    }
  },

  // Video URLs are plain strings — <video> elements can't send Bearer tokens,
  // so the backend video endpoints must be on the AUTH_PUBLIC_PATHS list.
  getVideoUrl: (automationId) => {
    return `${AUTOMATIONS_URL}/automations/${automationId}/video`;
  },

  getRawVideoUrl: (videoFilename) => {
    return `${AUTOMATIONS_URL}/videos/${videoFilename}`;
  },
};

export default automationsAPI;
