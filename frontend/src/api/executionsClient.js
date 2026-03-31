import { createApiClient } from './httpClient';

const API_BASE_URL = 'http://localhost:8005';

const client = createApiClient(API_BASE_URL);

export const executionsAPI = {
  list: async (params = {}) => {
    try {
      const response = await client.get('/executions', { params });
      return Array.isArray(response.data) ? response.data : response.data.data || [];
    } catch (error) {
      return [];
    }
  },
  get: async (id) => {
    try {
      const response = await client.get(`/executions/${id}`);
      return response.data;
    } catch (error) { return null; }
  },
  create: async (data) => {
    const response = await client.post('/executions', data);
    return response.data;
  },
  update: async (id, data) => {
    const response = await client.put(`/executions/${id}`, data);
    return response.data;
  },
  health: async () => {
    try { const r = await client.get('/health'); return r.data; } catch { return null; }
  },
};