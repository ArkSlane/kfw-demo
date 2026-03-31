/**
 * Centralised service URL configuration.
 *
 * All values are read from Vite environment variables (VITE_*).
 * In development, set them in a .env.local file.
 * In production, inject them as build-time env vars (or at docker-compose level).
 *
 * Fallbacks point to localhost for a local dev setup without docker-compose.
 */

// jsconfig.json enables checkJs — cast import.meta to access Vite's env object.
const env = /** @type {any} */ (import.meta).env;

export const SERVICE_URLS = {
  requirements:       env.VITE_REQUIREMENTS_URL       || 'http://localhost:8001',
  testcases:          env.VITE_TESTCASES_URL           || 'http://localhost:8002',
  generator:          env.VITE_GENERATOR_URL           || 'http://localhost:8013',
  releases:           env.VITE_RELEASES_URL            || 'http://localhost:8004',
  executions:         env.VITE_EXECUTIONS_URL          || 'http://localhost:8005',
  automations:        env.VITE_AUTOMATIONS_URL         || 'http://localhost:8006',
  git:                env.VITE_GIT_URL                 || 'http://localhost:8007',
  orchestrator:       env.VITE_ORCHESTRATOR_URL        || 'http://localhost:8011',
  testcaseMigration:  env.VITE_TESTCASE_MIGRATION_URL  || 'http://localhost:8009',
  toabrkia:           env.VITE_TOABRKIA_URL            || 'http://localhost:8008',
};
