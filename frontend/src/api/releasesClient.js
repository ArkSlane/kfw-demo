import { createApiClient } from './httpClient';

const API_BASE_URL = 'http://localhost:8004';

const client = createApiClient(API_BASE_URL);

export const releasesAPI = {
  // List all releases
  list: async (q = null, limit = 50, skip = 0) => {
    try {
      const params = { limit, skip };
      if (q) params.q = q;
      const response = await client.get('/releases', { params });
      return Array.isArray(response.data) ? response.data : response.data.data || [];
    } catch (error) {
      // Silently fail - services not running yet
      return [];
    }
  },

  // Get a single release
  get: async (releaseId) => {
    try {
      const response = await client.get(`/releases/${releaseId}`);
      return response.data;
    } catch (error) {
      return null;
    }
  },

  // Create a new release
  create: async (data) => {
    try {
      const response = await client.post('/releases', data);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Update a release
  update: async (releaseId, data) => {
    try {
      const response = await client.put(`/releases/${releaseId}`, data);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Delete a release
  delete: async (releaseId) => {
    try {
      const response = await client.delete(`/releases/${releaseId}`);
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
