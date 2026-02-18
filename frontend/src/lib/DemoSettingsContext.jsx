import React, { createContext, useContext, useState, useCallback } from 'react';

const STORAGE_KEY = 'aitp.settings.demoBannerEnabled';

function loadSetting() {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    // Default: enabled (true) when no setting stored
    return v === null ? true : v === 'true';
  } catch {
    return true;
  }
}

const DemoSettingsContext = createContext();

export function DemoSettingsProvider({ children }) {
  const [demoBannerEnabled, setDemoBannerEnabledState] = useState(loadSetting);

  const setDemoBannerEnabled = useCallback((enabled) => {
    setDemoBannerEnabledState(enabled);
    try { localStorage.setItem(STORAGE_KEY, String(enabled)); } catch {}
  }, []);

  return (
    <DemoSettingsContext.Provider value={{ demoBannerEnabled, setDemoBannerEnabled }}>
      {children}
    </DemoSettingsContext.Provider>
  );
}

export function useDemoSettings() {
  const ctx = useContext(DemoSettingsContext);
  if (!ctx) throw new Error('useDemoSettings must be used within DemoSettingsProvider');
  return ctx;
}
