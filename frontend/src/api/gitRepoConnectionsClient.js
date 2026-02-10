import axios from "axios";

// jsconfig.json enables checkJs; cast import.meta to any for Vite env access.
const viteEnv = /** @type {any} */ (import.meta).env;
const GIT_URL = viteEnv?.VITE_GIT_URL || "http://localhost:8007";

const gitRepoConnectionsAPI = {
  list: async () => {
    const res = await axios.get(`${GIT_URL}/repo-connections`);
    return Array.isArray(res.data) ? res.data : res.data?.data || [];
  },

  connect: async ({ repo_url, branch = null, target_dir = null, ssh_key_name = null, api_token_id = null }) => {
    const res = await axios.post(`${GIT_URL}/repo-connections`, {
      repo_url,
      branch,
      target_dir,
      ssh_key_name,
      api_token_id,
    });
    return res.data;
  },

  sync: async (connectionId) => {
    const res = await axios.post(`${GIT_URL}/repo-connections/${connectionId}/sync`);
    return res.data;
  },

  disconnect: async (connectionId) => {
    await axios.delete(`${GIT_URL}/repo-connections/${connectionId}`);
  },
};

export default gitRepoConnectionsAPI;
