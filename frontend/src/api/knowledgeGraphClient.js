import { createApiClient } from './httpClient';

// jsconfig.json enables checkJs; cast import.meta to any for Vite env access.
const viteEnv = /** @type {any} */ (import.meta).env;
const GENERATOR_URL = viteEnv?.VITE_GENERATOR_URL || 'http://localhost:8003';

const client = createApiClient(GENERATOR_URL);

const knowledgeGraphAPI = {
  /**
   * List all knowledge graphs.
   * @returns {Promise<Array>}
   */
  list: async () => {
    const res = await client.get('/knowledge-graphs');
    return res.data;
  },

  /**
   * Get a single knowledge graph by ID.
   * @param {string} id
   * @returns {Promise<Object>}
   */
  get: async (id) => {
    const res = await client.get(`/knowledge-graphs/${id}`);
    return res.data;
  },

  /**
   * Create a new knowledge graph.
   * @param {Object} data
   * @returns {Promise<Object>}
   */
  create: async (data) => {
    const res = await client.post('/knowledge-graphs', data);
    return res.data;
  },

  /**
   * Update an existing knowledge graph.
   * @param {string} id
   * @param {Object} data
   * @returns {Promise<Object>}
   */
  update: async (id, data) => {
    const res = await client.put(`/knowledge-graphs/${id}`, data);
    return res.data;
  },

  /**
   * Delete a knowledge graph.
   * @param {string} id
   * @returns {Promise<Object>}
   */
  delete: async (id) => {
    const res = await client.delete(`/knowledge-graphs/${id}`);
    return res.data;
  },
};

export default knowledgeGraphAPI;
