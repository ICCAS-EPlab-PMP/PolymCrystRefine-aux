'use strict';

const { app, BrowserWindow, ipcMain, dialog, Menu, net, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const BackendManager = require('./backend-manager');

let mainWindow = null;
const backendManager = new BackendManager();

// A broken stdout/stderr pipe must not crash the app with an
// uncaught-exception dialog. The backend manager pipes the Python log
// stream into console.log; when whatever launched us closes its end of the
// pipe (terminal closed, or the launcher killed mid-write), that write
// throws EPIPE. Swallow exactly that error and rethrow everything else.
for (const stream of [process.stdout, process.stderr]) {
  if (stream && typeof stream.on === 'function') {
    stream.on('error', (err) => {
      if (err && err.code === 'EPIPE') return;
      throw err;
    });
  }
}

// Dedicated port for the PRE / PolymCrystRefine backend. Deliberately OUTSIDE
// PolymCrystIndex's port-scan window (18700–18719): Index scans that range and
// would happily settle on 18710 when its own ports are taken, after which our
// requests hit the wrong app. If the preferred port is busy anyway, the
// BackendManager falls back through PORT_FALLBACKS in order.
const BACKEND_PORT = Number(process.env.PRE_BACKEND_PORT) || 18730;
// Ten consecutive candidate ports in total: the base port plus the nine
// fallbacks below it in the list (18730–18739 by default). Derived from
// BACKEND_PORT so an env override keeps the window contiguous.
const PORT_FALLBACKS = Array.from({ length: 9 }, (_, i) => BACKEND_PORT + 1 + i);
const isDev = process.env.NODE_ENV === 'development' || !!process.env.PRE_DEV_URL;
const DEV_FRONTEND_URL = process.env.PRE_DEV_URL || 'http://localhost:5173';

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1200,
    minHeight: 820,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      preload: path.join(__dirname, 'preload.js')
    },
    backgroundColor: '#F8FAFC',
    show: false,
    title: 'PolymCrystRefine — Aux'
  });

  mainWindow.setTitle('PolymCrystRefine — Aux');

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  if (isDev) {
    // Development: load from Vite dev server
    mainWindow.loadURL(DEV_FRONTEND_URL);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    // Production: load the built index.html
    // In packaged app, frontend/dist is in extraResources (resources/frontend/dist)
    // In unpackaged prod test, it lives at ../frontend/dist relative to electron/
    const indexPath = app.isPackaged
      ? path.join(process.resourcesPath, 'frontend', 'dist', 'index.html')
      : path.join(__dirname, '..', 'frontend', 'dist', 'index.html');
    mainWindow.loadFile(indexPath);
  }
}

// Port the renderer may talk to right now. Only a healthy 'running' backend
// has one: while it is starting (incl. the restart backoff) the previous port
// is a dead socket, and after 'failed' / 'stopped' there is nothing at all.
// Reporting the stale port made the renderer keep requesting a dead socket
// instead of waiting for the auto-restart to come up on a new one.
function liveBackendPort() {
  return backendManager.state === 'running' ? (backendManager.port || null) : null;
}

// IPC handlers
ipcMain.handle('app:get-runtime-info', () => ({
  version: app.getVersion(),
  backendPort: liveBackendPort(),
  backendState: backendManager.state,
  isPackaged: app.isPackaged,
  isDev: isDev,
  platform: process.platform
}));

// Current backend lifecycle status, for a renderer-side indicator and for
// keeping the axios baseURL in sync when the backend restarts on another port.
ipcMain.handle('app:get-backend-status', () => ({
  state: backendManager.state,
  port: liveBackendPort()
}));

function broadcastBackendStatus(state, port) {
  const st = state || backendManager.state;
  // The manager passes null for every non-'running' state; re-derive the port
  // here as well so a stale argument can never advertise a dead socket.
  const payload = { state: st, port: st === 'running' ? (port || liveBackendPort()) : null };
  for (const win of BrowserWindow.getAllWindows()) {
    try { win.webContents.send('backend:status', payload); } catch (_) { /* window closing */ }
  }
}
backendManager.onStatus = broadcastBackendStatus;

ipcMain.handle('app:open-external', (_event, url) => {
  const { shell } = require('electron');
  return shell.openExternal(url);
});

// Check for updates: query the latest GitHub release and compare it with the
// running app version. Only https and only the GitHub API host are ever
// contacted (the release page URL is handed to the browser via open-external).
const UPDATE_REPO = 'ICCAS-EPlab-PMP/PolymCrystRefine-aux';
const UPDATE_API = `https://api.github.com/repos/${UPDATE_REPO}/releases/latest`;
const UPDATE_PAGE = `https://github.com/${UPDATE_REPO}/releases/latest`;

function normalizeVersion(v) {
  return String(v || '').trim().replace(/^v/i, '');
}

ipcMain.handle('app:check-update', () => new Promise((resolve) => {
  let parsed;
  try { parsed = new URL(UPDATE_API); } catch { resolve({ ok: false, error: 'badurl' }); return; }
  if (parsed.protocol !== 'https:' || parsed.hostname !== 'api.github.com') {
    resolve({ ok: false, error: 'badurl' });
    return;
  }
  const req = net.request({
    method: 'GET',
    url: UPDATE_API,
    useSessionCookies: false,
  });
  req.setHeader('User-Agent', 'PolymCrystRefine-Desktop');
  req.setHeader('Accept', 'application/vnd.github+json');
  const timer = setTimeout(() => { req.destroy(); resolve({ ok: false, error: 'timeout' }); }, 10000);
  req.on('response', (res) => {
    let body = '';
    res.on('data', (chunk) => { body += chunk; });
    res.on('end', () => {
      clearTimeout(timer);
      if (res.statusCode !== 200) { resolve({ ok: false, error: `http-${res.statusCode}` }); return; }
      try {
        const tag = JSON.parse(body).tag_name || '';
        const latest = normalizeVersion(tag);
        const current = normalizeVersion(app.getVersion());
        resolve({
          ok: true,
          current,
          latest,
          hasUpdate: !!latest && latest !== current,
          releaseUrl: UPDATE_PAGE,
        });
      } catch { resolve({ ok: false, error: 'parse' }); }
    });
  });
  req.on('error', () => { clearTimeout(timer); resolve({ ok: false, error: 'network' }); });
  req.end();
}));

ipcMain.handle('app:get-update-page', () => UPDATE_PAGE);

// Native save-file dialog. The renderer sends a payload describing the file
// (a data: URL for images, or raw text for CSV/JSON/SVG); the main process
// pops the OS "save as" dialog so the user picks the destination, then writes
// the bytes. This replaces the silent <a download>/Blob download which never
// showed a save dialog and silently no-op'd under contextIsolation.
//
// payload: { defaultName, filters?, dataUrl?, text?, encoding? }
//   - dataUrl: full data: URL. base64 (`data:...;base64,xx`) is decoded as
//     binary; charset-encoded SVG (`data:image/svg+xml;charset=utf-8,<..>`)
//     is URI-decoded to text. Used for Plotly PNG/SVG exports.
//   - text: plain string content (CSV / JSON / SVG markup).
ipcMain.handle('dialog:save-file', async (_event, payload) => {
  const { defaultName, filters, dataUrl, text, encoding } = payload || {};
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath: defaultName,
    filters: filters && filters.length ? filters : [{ name: 'All Files', extensions: ['*'] }]
  });
  if (result.canceled || !result.filePath) return { ok: false, canceled: true };

  let buffer;
  if (dataUrl != null) {
    buffer = dataUrlToBuffer(String(dataUrl));
  } else {
    buffer = Buffer.from(text == null ? '' : String(text), encoding || 'utf-8');
  }
  fs.writeFileSync(result.filePath, buffer);
  return { ok: true, filePath: result.filePath };
});

// Decode a data: URL into a Buffer. Handles both base64 payloads (PNG/JPEG) and
// URL-encoded text payloads (Plotly's SVG export).
function dataUrlToBuffer(dataUrl) {
  const comma = dataUrl.indexOf(',');
  if (comma < 0) return Buffer.from(dataUrl, 'utf-8');
  const header = dataUrl.slice(0, comma);
  const body = dataUrl.slice(comma + 1);
  if (/;base64$/i.test(header)) {
    return Buffer.from(body, 'base64');
  }
  // text/svg: URI-encoded
  return Buffer.from(decodeURIComponent(body), 'utf-8');
}

// App lifecycle
app.whenReady().then(async () => {
  // The default File/Edit/View/Window/Help menu bar is dead weight for this
  // app — remove it in production builds. Keep it during development so the
  // DevTools accelerators (Ctrl+Shift+I etc.) still work while debugging.
  if (app.isPackaged) {
    Menu.setApplicationMenu(null);
  }
  try {
    await backendManager.start(BACKEND_PORT, app.isPackaged, { fallbackPorts: PORT_FALLBACKS });
    console.log(`[PolymCrystRefine] Backend started on port ${backendManager.port}`);
  } catch (err) {
    // Surface the failure instead of failing silently. The BackendManager has
    // already tried every fallback port; show the window anyway so the user
    // sees the connection error in the console panel rather than nothing.
    // If the backend later comes back (auto-restart), the renderer is notified
    // via 'backend:status' and requests start working again.
    console.error('[PolymCrystRefine] Backend failed to start:', err);
    dialog.showErrorBox(
      '后端启动失败 / Backend failed to start',
      `${err.message || err}\n\n` +
      `已尝试端口 ${BACKEND_PORT} 及备用端口 (${PORT_FALLBACKS.join(', ')})，均不可用。\n` +
      `常见原因：残留的本程序后端进程或其他程序（例如 PolymCrystIndex）占用端口。\n` +
      `请在任务管理器结束多余的 python.exe / PolymCrystRefine 进程后重启本应用。\n\n` +
      `Tried port ${BACKEND_PORT} and fallbacks (${PORT_FALLBACKS.join(', ')}) — all unavailable.\n` +
      `Common cause: leftover python.exe / PolymCrystRefine processes or another app (e.g. PolymCrystIndex) holding the ports.\n` +
      `Close them in Task Manager and restart this application.`
    );
  }
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    backendManager.stop();
    app.quit();
  }
});

app.on('before-quit', () => {
  backendManager.stop();
});

// Final guard: covers quit paths that skip before-quit (e.g. autoQuitApp
// after update, or app.quit() from a crash flow). stop() is idempotent.
app.on('will-quit', () => {
  backendManager.stop();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
