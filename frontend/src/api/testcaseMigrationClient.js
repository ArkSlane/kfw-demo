import axios from 'axios';

// jsconfig.json enables checkJs; cast import.meta to any for Vite env access.
const viteEnv = /** @type {any} */ (import.meta).env;
const TESTCASE_MIGRATION_URL = viteEnv?.VITE_TESTCASE_MIGRATION_URL || 'http://localhost:8009';

const testcaseMigrationAPI = {
  health: async () => {
    try {
      const res = await axios.get(`${TESTCASE_MIGRATION_URL}/health`);
      return res.data;
    } catch (error) {
      return null;
    }
  },

  analyze: async ({ code, language = null }) => {
    const payload = { code };
    if (language) payload.language = language;
    const res = await axios.post(`${TESTCASE_MIGRATION_URL}/analyze`, payload);
    return res.data;
  },

  generateAutomationDraft: async ({ code = null, testcase, mapping = [] }) => {
    const payload = { testcase };
    if (code) payload.code = code;
    if (Array.isArray(mapping) && mapping.length > 0) payload.mapping = mapping;
    const res = await axios.post(`${TESTCASE_MIGRATION_URL}/generate-automation-draft`, payload);
    return res.data;
  },

  save: async ({ testcase_id, testcase, script, mapping = [], framework = null, notes = null }) => {
    const payload = { testcase_id, testcase, script };
    if (Array.isArray(mapping) && mapping.length > 0) payload.mapping = mapping;
    if (framework) payload.framework = framework;
    if (notes) payload.notes = notes;

    const res = await axios.post(`${TESTCASE_MIGRATION_URL}/save`, payload);
    return res.data;
  },
};

export default testcaseMigrationAPI;
