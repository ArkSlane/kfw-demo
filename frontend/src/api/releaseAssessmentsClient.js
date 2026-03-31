import { createApiClient } from './httpClient';
import { SERVICE_URLS } from './config';

const client = createApiClient(SERVICE_URLS.toabrkia);

export const releaseAssessmentsAPI = {
  list: async (params = {}) => {
    const response = await client.get(`/assessments`, { params });
    return response.data;
  },

  delete: async (assessmentId) => {
    const response = await client.delete(`/assessments/${assessmentId}`);
    return response.data;
  },

  getByRelease: async (releaseId) => {
    try {
      const response = await client.get(`/assessments/by-release/${releaseId}`);
      return response.data;
    } catch {
      return null;
    }
  },

  upsertByRelease: async (releaseId, data) => {
    const response = await client.put(`/assessments/by-release/${releaseId}`, data);
    return response.data;
  },

  health: async () => {
    try {
      const r = await client.get('/health');
      return r.data;
    } catch {
      return null;
    }
  },
};
