import axios from 'axios';

// jsconfig.json enables checkJs; cast import.meta to any for Vite env access.
const viteEnv = /** @type {any} */ (import.meta).env;
const GENERATOR_URL = '/svc/8003';

const generatorAPI = {
  generateAutomation: async (testCaseData) => {
    try {
      // Prefer execution-based generation that actually runs the steps via MCP + Ollama
      const response = await axios.post(`${GENERATOR_URL}/generate-automation-from-execution`, {
        test_case_id: testCaseData.id,
      });
      return response.data; // { automation_id, title, framework, script_outline, notes, actions_taken }
    } catch (error) {
      console.error('Generator API error:', error.response?.data || error.message);
      throw error;
    }
  },

  generateAutomationDraft: async (testCaseData) => {
    try {
      const response = await axios.post(`${GENERATOR_URL}/generate-automation-draft-from-execution`, {
        test_case_id: testCaseData.id,
      });
      return response.data; // { title, framework, script_outline, notes, actions_taken, exec_success, ... }
    } catch (error) {
      console.error('Generator API error:', error.response?.data || error.message);
      throw error;
    }
  },

  automationChat: async ({ test_case_id, message, history = [], context = {}, execute = false }) => {
    try {
      const response = await axios.post(`${GENERATOR_URL}/automation-chat`, {
        test_case_id,
        message,
        history,
        context,
        execute,
      });
      return response.data; // { reply, suggested_script, exec_success, video_path }
    } catch (error) {
      console.error('Generator API error:', error.response?.data || error.message);
      throw error;
    }
  },

  generateTestcases: async (requirementId, amount = 1, mode = 'append') => {
    try {
      const response = await axios.post(`${GENERATOR_URL}/generate`, {
        requirement_id: requirementId,
        amount,
        mode,
      });
      return response.data; // { generated: [...] }
    } catch (error) {
      console.error('Generator API error:', error.response?.data || error.message);
      throw error;
    }
  },

  generateStructuredTestcase: async (requirementId) => {
    try {
      const response = await axios.post(`${GENERATOR_URL}/generate-structured-testcase`, {
        requirement_id: requirementId,
      });
      return response.data; // { testcase: { title, description, priority, steps }, generator, model, attempts }
    } catch (error) {
      console.error('Generator API error:', error.response?.data || error.message);
      throw error;
    }
  },

  generateTestSuite: async (requirementId, positiveAmount = 3, negativeAmount = 2) => {
    try {
      const response = await axios.post(`${GENERATOR_URL}/generate-test-suite`, {
        requirement_id: requirementId,
        positive_amount: positiveAmount,
        negative_amount: negativeAmount,
      });
      return response.data; // { positive_tests: [...], negative_tests: [...], generator, model, attempts }
    } catch (error) {
      console.error('Generator API error:', error.response?.data || error.message);
      throw error;
    }
  },
  
  executeScript: async (payload) => {
    const response = await axios.post(`${GENERATOR_URL}/execute-script`, payload);
    return response.data;
  },
};

export default generatorAPI;
