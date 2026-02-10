import axios from 'axios';

const API_BASE_URL = 'http://localhost:8001';

const client = axios.create({
  baseURL: API_BASE_URL,
});

export const requirementsAPI = {
  // List all requirements
  list: async (q = null, limit = 50, skip = 0) => {
    try {
      const params = { limit, skip };
      if (q) params.q = q;
      const response = await client.get('/requirements', { params });
      return Array.isArray(response.data) ? response.data : response.data.data || [];
    } catch (error) {
      // Silently fail - services not running yet
      return [];
    }
  },

  // Get a single requirement
  get: async (requirementId) => {
    try {
      const response = await client.get(`/requirements/${requirementId}`);
      return response.data;
    } catch (error) {
      return null;
    }
  },

  // Create a new requirement
  create: async (data) => {
    try {
      const response = await client.post('/requirements', data);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Update a requirement
  update: async (requirementId, data) => {
    try {
      const response = await client.put(`/requirements/${requirementId}`, data);
      return response.data;
    } catch (error) {
      throw error;
    }
  },

  // Delete a requirement
  delete: async (requirementId) => {
    try {
      const response = await client.delete(`/requirements/${requirementId}`);
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
