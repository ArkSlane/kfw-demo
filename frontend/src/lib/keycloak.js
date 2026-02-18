/**
 * Keycloak configuration for the TestMaster frontend.
 *
 * Values are read from Vite environment variables at build time.
 * Defaults point to the local docker-compose Keycloak instance.
 */

const viteEnv = /** @type {any} */ (import.meta).env;

export const keycloakConfig = {
  url:      viteEnv?.VITE_KEYCLOAK_URL      || 'http://localhost:8080',
  realm:    viteEnv?.VITE_KEYCLOAK_REALM     || 'testmaster',
  clientId: viteEnv?.VITE_KEYCLOAK_CLIENT_ID || 'testmaster-app',
};
