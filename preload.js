'use strict';

const { contextBridge, ipcRenderer, shell } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  getRuntimeInfo: () => ipcRenderer.invoke('app:get-runtime-info'),
  getBackendStatus: () => ipcRenderer.invoke('app:get-backend-status'),
  // cb({state, port}) — fired on every backend lifecycle change (starting /
  // running / failed / stopped), including restarts on a different port.
  onBackendStatus: (cb) => {
    const listener = (_event, payload) => cb(payload);
    ipcRenderer.on('backend:status', listener);
    return () => ipcRenderer.removeListener('backend:status', listener);
  },
  openExternal: (url) => ipcRenderer.invoke('app:open-external', url),
  // payload: { defaultName, filters?, dataUrl?, text?, encoding? }
  saveFile: (payload) => ipcRenderer.invoke('dialog:save-file', payload)
});
