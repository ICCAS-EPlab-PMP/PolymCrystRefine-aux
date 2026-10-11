/**
 * Runtime detection: local (Electron/desktop) vs cloud
 */

export function isElectron() {
  return typeof window !== 'undefined' && !!window.electronAPI;
}

export function isLocalProfile() {
  if (import.meta.env.VITE_APP_PROFILE === 'local') return true;
  return isElectron();
}

export async function getRuntimeInfo() {
  if (isElectron()) {
    return await window.electronAPI.getRuntimeInfo();
  }
  return {
    // Build-time constant from frontend/package.json (see vite.config.js) —
    // keep it in sync with PRE/package.json so the browser fallback matches
    // the packaged Electron version.
    version: __APP_VERSION__,
    isPackaged: false,
    platform: 'web'
  };
}
