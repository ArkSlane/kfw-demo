import axios from "axios";

// jsconfig.json enables checkJs; cast import.meta to any for Vite env access.
const viteEnv = /** @type {any} */ (import.meta).env;
const GIT_URL = "/svc/8007";

const gitTokensAPI = {
  list: async () => {
    const res = await axios.get(`${GIT_URL}/api-tokens`);
    return Array.isArray(res.data) ? res.data : res.data?.data || [];
  },

  create: async ({ provider, name, token, azure_org = null }) => {
    const res = await axios.post(`${GIT_URL}/api-tokens`, {
      provider,
      name,
      token,
      azure_org,
    });
    return res.data;
  },

  delete: async (id) => {
    await axios.delete(`${GIT_URL}/api-tokens/${id}`);
  },
};

export default gitTokensAPI;
