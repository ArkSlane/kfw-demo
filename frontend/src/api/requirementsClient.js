import { createApiClient } from './httpClient';
import { SERVICE_URLS } from './config';

const client = createApiClient(SERVICE_URLS.requirements);

export const requirementsAPI = {
  // List all requirements
  list: async (q = null, limit = 50, skip = 0, review_status = null) => {
    const params = { limit, skip };
    if (q) params.q = q;
    if (review_status) params.review_status = review_status;
    const response = await client.get('/requirements', { params });
    return Array.isArray(response.data) ? response.data : response.data.data || [];
  },

  // Get a single requirement
  get: async (requirementId) => {
    const response = await client.get(`/requirements/${requirementId}`);
    return response.data;
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

  // Approve a pending requirement
  approve: async (requirementId, reviewedBy) => {
    const response = await client.post(`/requirements/${requirementId}/approve`, null, { params: { reviewed_by: reviewedBy } });
    return response.data;
  },

  // Reject a pending requirement
  reject: async (requirementId, reviewedBy) => {
    const response = await client.post(`/requirements/${requirementId}/reject`, null, { params: { reviewed_by: reviewedBy } });
    return response.data;
  },
};
