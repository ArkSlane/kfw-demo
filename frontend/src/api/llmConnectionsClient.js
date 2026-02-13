import axios from "axios";

// jsconfig.json enables checkJs; cast import.meta to any for Vite env access.
const viteEnv = /** @type {any} */ (import.meta).env;
const GIT_URL = "/svc/8007";

const llmConnectionsAPI = {
  list: async () => {
    const res = await axios.get(`${GIT_URL}/llm-connections`);
    return Array.isArray(res.data) ? res.data : res.data?.data || [];
  },

  create: async ({ provider, name, base_url, api_key, default_model = null }) => {
    const res = await axios.post(`${GIT_URL}/llm-connections`, {
      provider,
      name,
      base_url,
      api_key,
      default_model,
    });
    return res.data;
  },

  delete: async (id) => {
    await axios.delete(`${GIT_URL}/llm-connections/${id}`);
  },
};

export default llmConnectionsAPI;
