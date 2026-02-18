// frontend/src/lib/AuthContext.jsx
import React, { createContext, useState, useContext, useEffect, useRef, useCallback } from 'react';
import Keycloak from 'keycloak-js';
import { keycloakConfig } from './keycloak';
import { setAuthTokenGetter, setupGlobalInterceptor } from '@/api/httpClient';

const AuthContext = createContext();

/**
 * Derive the highest-privilege app role from the Keycloak realm roles array.
 */
function _pickRole(keycloakInstance) {
  const roles = keycloakInstance?.realmAccess?.roles || [];
  if (roles.includes('admin')) return 'admin';
  if (roles.includes('editor')) return 'editor';
  return 'viewer';
}

function _buildUser(keycloakInstance) {
  if (!keycloakInstance?.authenticated) return null;
  const idToken = keycloakInstance.idTokenParsed || {};
  return {
    username: idToken.preferred_username || idToken.sub,
    email: idToken.email || '',
    name: idToken.name || idToken.preferred_username || '',
    firstName: idToken.given_name || '',
    lastName: idToken.family_name || '',
    role: _pickRole(keycloakInstance),
    roles: keycloakInstance.realmAccess?.roles || [],
  };
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoadingAuth, setIsLoadingAuth] = useState(true);
  const [isLoadingPublicSettings, setIsLoadingPublicSettings] = useState(true);
  const [authError, setAuthError] = useState(null);
  const [authEnabled, setAuthEnabled] = useState(false);

  const kcRef = useRef(null);

  // ── Fetch backend /auth/settings to see if auth is turned on ───────────
  useEffect(() => {
    const viteEnv = /** @type {any} */ (import.meta).env;
    const apiBase = viteEnv?.VITE_API_BASE_URL || 'http://localhost:8001';

    fetch(`${apiBase}/auth/settings`)
      .then((r) => r.json())
      .then((settings) => {
        setAuthEnabled(settings.auth_enabled === true);
        setIsLoadingPublicSettings(false);
      })
      .catch(() => {
        // If the backend is unreachable, treat auth as disabled (dev mode)
        setAuthEnabled(false);
        setIsLoadingPublicSettings(false);
      });
  }, []);

  // ── Initialise Keycloak once we know auth is enabled ──────────────────
  useEffect(() => {
    // Wait until settings are loaded
    if (isLoadingPublicSettings) return;

    if (!authEnabled) {
      // Auth disabled — treat user as anonymous admin
      setUser({ username: 'anonymous', role: 'admin', roles: ['admin'], email: '', name: 'Anonymous' });
      setIsAuthenticated(true);
      setIsLoadingAuth(false);
      return;
    }

    const kc = new Keycloak(keycloakConfig);
    kcRef.current = kc;

    // Wire up the token getter BEFORE init so interceptors are ready
    setAuthTokenGetter(() => kc.token || null);
    setupGlobalInterceptor();

    kc.init({
      onLoad: 'login-required',       // redirect to Keycloak login immediately
      checkLoginIframe: false,         // avoid CSP issues in iframes
      pkceMethod: 'S256',             // PKCE for public clients
    })
      .then((authenticated) => {
        if (authenticated) {
          setUser(_buildUser(kc));
          setIsAuthenticated(true);
        } else {
          setAuthError({ type: 'auth_required' });
        }
        setIsLoadingAuth(false);
      })
      .catch((err) => {
        console.error('Keycloak init failed:', err);
        setAuthError({ type: 'auth_required', message: String(err) });
        setIsLoadingAuth(false);
      });

    // Auto-refresh token before expiry
    kc.onTokenExpired = () => {
      kc.updateToken(30).then((refreshed) => {
        if (refreshed) {
          setUser(_buildUser(kc));
        }
      }).catch(() => {
        console.warn('Token refresh failed — logging out');
        kc.logout();
      });
    };

    // Handle auth errors / session changes
    kc.onAuthError = () => {
      setAuthError({ type: 'auth_required' });
    };
  }, [isLoadingPublicSettings, authEnabled]);

  const navigateToLogin = useCallback(() => {
    if (kcRef.current) {
      kcRef.current.login();
    }
  }, []);

  const logout = useCallback(() => {
    if (kcRef.current?.authenticated) {
      kcRef.current.logout({ redirectUri: window.location.origin + '/' });
    } else {
      setUser(null);
      setIsAuthenticated(false);
    }
  }, []);

  return (
    <AuthContext.Provider value={{
      user,
      isAuthenticated,
      isLoadingAuth,
      isLoadingPublicSettings,
      authError,
      authEnabled,
      navigateToLogin,
      logout,
    }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};