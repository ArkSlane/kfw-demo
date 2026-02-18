/**
 * Centralized axios helpers with Keycloak Bearer-token interceptor.
 *
 * Usage:
 *   import { createApiClient } from '@/api/httpClient';
 *   const client = createApiClient('http://localhost:8001');
 *   // All requests now carry Authorization: Bearer <token>
 *
 * For API files that use bare `axios.get/post`, call
 * `setupGlobalInterceptor()` once at app init — it patches the
 * default axios instance so every call picks up the token.
 */
import axios from 'axios';

// ── Token provider ──────────────────────────────────────────────────────────
let _getToken = () => null;

/**
 * Register a function that returns the current access-token string
 * (or null when no user is logged in). Called by AuthContext on init.
 */
export function setAuthTokenGetter(fn) {
  _getToken = fn;
}

/** Attach Bearer header to every outgoing request. */
function _addInterceptor(instance) {
  instance.interceptors.request.use(
    (config) => {
      const token = _getToken();
      if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error),
  );
  return instance;
}

// ── Public API ──────────────────────────────────────────────────────────────

/** Create a new axios instance with auth interceptor already wired. */
export function createApiClient(baseURL) {
  const client = axios.create({ baseURL });
  return _addInterceptor(client);
}

let _globalSetup = false;

/**
 * Patch the *default* axios instance so `axios.get(...)` etc. carry the
 * Bearer token automatically. Safe to call multiple times (idempotent).
 */
export function setupGlobalInterceptor() {
  if (_globalSetup) return;
  _addInterceptor(axios);
  _globalSetup = true;
}
