import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import gitRepoConnectionsAPI from '@/api/gitRepoConnectionsClient';

const STORAGE_KEY = 'aitp.selectedAppRepoId';

const AppRepoContext = createContext();

export function AppRepoProvider({ children }) {
  const [repoConnections, setRepoConnections] = useState([]);
  const [selectedAppRepoId, setSelectedAppRepoIdState] = useState(
    () => localStorage.getItem(STORAGE_KEY) || null
  );
  const [loading, setLoading] = useState(true);

  const fetchConnections = useCallback(async () => {
    try {
      const list = await gitRepoConnectionsAPI.list();
      setRepoConnections(list);
      // If stored selection is no longer valid, clear it
      const storedId = localStorage.getItem(STORAGE_KEY);
      if (storedId && !list.find((c) => c.id === storedId)) {
        setSelectedAppRepoIdState(null);
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch (e) {
      console.error('Failed to load repo connections', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  const setSelectedAppRepoId = useCallback((id) => {
    setSelectedAppRepoIdState(id);
    if (id) {
      localStorage.setItem(STORAGE_KEY, id);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const appRepos = repoConnections.filter((c) => c.repo_type === 'application_repository');

  const selectedAppRepo = appRepos.find((c) => c.id === selectedAppRepoId) || null;

  // Find test repo linked to the selected app repo (link can be in either direction)
  const linkedTestRepo = selectedAppRepo
    ? repoConnections.find(
        (c) =>
          c.repo_type === 'test_repository' &&
          (c.linked_repo_id === selectedAppRepo.id || selectedAppRepo.linked_repo_id === c.id)
      )
    : null;

  return (
    <AppRepoContext.Provider
      value={{
        repoConnections,
        appRepos,
        selectedAppRepoId,
        selectedAppRepo,
        linkedTestRepo,
        setSelectedAppRepoId,
        refreshConnections: fetchConnections,
        loading,
      }}
    >
      {children}
    </AppRepoContext.Provider>
  );
}

export function useAppRepo() {
  const ctx = useContext(AppRepoContext);
  if (!ctx) throw new Error('useAppRepo must be used within AppRepoProvider');
  return ctx;
}
