import axios from 'axios';

// Default backend port for PRE / PolymCrystRefine. Outside PolymCrystIndex's
// port-scan window (18700–18719). The Electron main process may move the
// backend to a fallback port (18731+) after a collision — the actual port is
// pulled from runtime info / backend status events below, so this constant is
// only used until that resolves (and in plain-browser dev mode).
const PRE_BACKEND_PORT = 18730;

const inElectronFile = window.location.protocol === 'file:';
let backendPort = PRE_BACKEND_PORT;
// True while the Electron main process reports the backend as not running
// (starting / restart backoff / failed / stopped). Requests made in that
// window carry a "restarting, retry shortly" hint instead of a dead-end error.
let backendDown = false;

function buildBaseURL() {
  return inElectronFile ? `http://127.0.0.1:${backendPort}/api` : '/api';
}

function applyBackendPort(port) {
  if (!port || port === backendPort) return;
  backendPort = port;
  request.defaults.baseURL = buildBaseURL();
}

/** Drop a locked port after the backend went away: the locked socket is dead
    by definition, so fall back to the default port and wait for the next
    'running' event to hand us the port the restarted backend bound to. */
function releaseBackendPort() {
  if (backendPort === PRE_BACKEND_PORT) return;
  backendPort = PRE_BACKEND_PORT;
  request.defaults.baseURL = buildBaseURL();
}

const request = axios.create({
  baseURL: buildBaseURL(),
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json'
  }
});

/**
 * Keep the axios baseURL in sync with the backend lifecycle the main process
 * reports. Only a 'running' backend owns a usable port: while it is starting
 * or restarting (the event fires with port = null), the previously locked
 * port is a dead socket — drop it and flag the API as down so failures read
 * as "restarting" rather than as a dead end. Without this, a backend restart
 * on a fallback port left every request pointing at the old port, surfacing
 * as bare "Network Error" in every page.
 */
function syncBackendStatus(status) {
  const state = status?.state;
  if (state === 'running') {
    backendDown = false;
    applyBackendPort(status.port);
    return;
  }
  backendDown = true;
  releaseBackendPort();
}

if (inElectronFile && window.electronAPI) {
  window.electronAPI.getRuntimeInfo?.()
    .then((info) => {
      if (!info) return;
      if (info.backendState) syncBackendStatus({ state: info.backendState, port: info.backendPort });
      else applyBackendPort(info.backendPort);
    })
    .catch(() => {});
  window.electronAPI.onBackendStatus?.(syncBackendStatus);
}

// Request interceptor
request.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
);

// Response interceptor
request.interceptors.response.use(
  (response) => response,
  (error) => {
    if (!error.response) {
      // No HTTP response at all — the backend process is not reachable
      // (not started, crashed, or wrong port). Replace axios's opaque
      // "Network Error" with an actionable message; pages render err.message.
      // While the manager is already restarting it, say so instead of telling
      // the user to restart the whole application.
      error.message = backendDown
        ? `无法连接后端服务 (http://127.0.0.1:${backendPort}) — 后端未就绪，正在自动重启，请稍后重试。` +
          ` / Cannot reach the backend at http://127.0.0.1:${backendPort}. ` +
          `The backend is not ready — an automatic restart is in progress, please retry in a moment.`
        : `无法连接后端服务 (http://127.0.0.1:${backendPort}) — 后端未启动或已退出，` +
          `请重启应用 / Cannot reach the backend at http://127.0.0.1:${backendPort}. ` +
          `The backend service is not running — please restart the application.`;
    }
    const msg = error.response?.data?.detail || error.message || 'Request failed';
    console.error('[API Error]', msg);
    return Promise.reject(error);
  }
);

export default request;
