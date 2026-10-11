'use strict';

const { spawn, spawnSync } = require('child_process');
const path = require('path');
const http = require('http');
const fs = require('fs');

// How many times the backend is allowed to crash-restart in quick succession
// before we give up and report 'failed' to the UI.
const MAX_RESTART_ATTEMPTS = 5;
// Restart backoff: 2s, 4s, 8s, 16s, capped at 30s.
const RESTART_BACKOFF_BASE_MS = 2000;
const RESTART_BACKOFF_MAX_MS = 30000;
// Candidate window when the caller passes no fallbackPorts: the preferred
// port plus nine consecutive ports above it (18730 → 18730–18739).
const FALLBACK_PORT_COUNT = 9;

class BackendManager {
  constructor() {
    this.process = null;
    this.port = null;            // port the backend actually bound to
    this.state = 'stopped';      // stopped | starting | running | failed
    this.onStatus = null;        // optional (state, port, message) callback
    this.userStopped = false;
    this.restartAttempts = 0;
    this._candidates = [];       // ports to try, in order
    this._restartTimer = null;
    this._startChainRunning = false;
    this._lastIsPackaged = false;
  }

  _setState(state, message) {
    this.state = state;
    if (typeof this.onStatus === 'function') {
      // Only a healthy 'running' backend owns a usable port. During
      // 'starting' / restart backoff this.port still holds the previous (now
      // dead) socket, and 'failed' / 'stopped' have no backend at all —
      // broadcasting that stale number made the renderer keep sending its
      // requests to a port nobody listens on after a crash.
      const reportPort = state === 'running' ? this.port : null;
      try { this.onStatus(state, reportPort, message); } catch (_) { /* listener bug must not kill the manager */ }
    }
  }

  /**
   * Resolve the backend root directory.
   * - Packaged app: <resourcesPath>/backend  (copied via extraResources)
   * - Dev mode:     <projectRoot>/backend     (sibling of electron/)
   */
  _resolveBackendRoot(isPackaged) {
    if (isPackaged) {
      return path.join(process.resourcesPath, 'backend');
    }
    return path.resolve(__dirname, '..', 'backend');
  }

  /**
   * Find a suitable Python interpreter.
   * Priority in packaged mode: bundled runtime > system python
   * Priority in dev mode: venv python > system python/py launcher
   */
  _findPython(backendRoot, isPackaged) {
    // 1. Packaged: check for a bundled Python runtime
    if (isPackaged) {
      const bundledExe = process.platform === 'win32'
        ? path.join(process.resourcesPath, 'runtime', 'python', 'python.exe')
        : path.join(process.resourcesPath, 'runtime', 'python', 'python');
      if (fs.existsSync(bundledExe)) return bundledExe;
    }

    // 2. Dev mode: check for a virtual-env inside backend/
    const venvExe = process.platform === 'win32'
      ? path.join(backendRoot, '.venv', 'Scripts', 'python.exe')
      : path.join(backendRoot, '.venv', 'bin', 'python');
    if (fs.existsSync(venvExe)) return venvExe;

    // 3. Fall back to system python (works on all platforms)
    return process.platform === 'win32' ? 'python' : 'python3';
  }

  /**
   * Start the backend: try each candidate port in order until one binds and
   * passes the identity-checked health probe. After a successful start, an
   * unexpected process exit triggers an automatic restart with backoff.
   */
  async start(port, isPackaged, options = {}) {
    // Preferred port first, then the fallbacks: a caller-supplied list wins,
    // otherwise use FALLBACK_PORT_COUNT consecutive ports above the preferred
    // one (ten candidates in total for the default base port 18730).
    const fallbacks = Array.isArray(options.fallbackPorts) && options.fallbackPorts.length
      ? options.fallbackPorts
      : Array.from({ length: FALLBACK_PORT_COUNT }, (_, i) => port + 1 + i);
    this._candidates = [port, ...fallbacks];
    this._lastIsPackaged = isPackaged;
    this.userStopped = false;
    this.restartAttempts = 0;
    await this._startChain(isPackaged, 20000);
  }

  /**
   * Probe a port: 'ours' if a polymcrystrefine-pre backend answers /health,
   * 'foreign' if anything else answers, null if nothing listens.
   */
  _probePort(port, timeoutMs = 1500) {
    return new Promise((resolve) => {
      const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          let parsed = null;
          try { parsed = JSON.parse(body); } catch (_) { /* not JSON */ }
          resolve(parsed && parsed.app === 'polymcrystrefine-pre' ? 'ours' : 'foreign');
        });
      });
      req.on('error', () => resolve(null));
      req.setTimeout(timeoutMs, () => { req.destroy(); resolve(null); });
    });
  }

  async _startChain(isPackaged, healthTimeoutMs) {
    if (this._startChainRunning) return;
    this._startChainRunning = true;
    try {
      const backendRoot = this._resolveBackendRoot(isPackaged);
      const pythonCmd = this._findPython(backendRoot, isPackaged);
      let lastError = null;

      this._setState('starting');

      for (const candidate of this._candidates) {
        // Skip ports already serving something — ours (a leaked instance from
        // a previous run, possibly an older build) or another application.
        // Starting uvicorn on them would just fail to bind.
        const probe = await this._probePort(candidate);
        if (probe === 'ours') {
          lastError = new Error(`Port ${candidate} is held by a leftover PolymCrystRefine backend from a previous run.`);
          console.warn(`[BackendManager] ${lastError.message}`);
          continue;
        }
        if (probe === 'foreign') {
          lastError = new Error(`Port ${candidate} is already in use by another application.`);
          console.warn(`[BackendManager] ${lastError.message}`);
          continue;
        }

        try {
          await this._spawnAndWait(candidate, pythonCmd, backendRoot, healthTimeoutMs);
          this.restartAttempts = 0;
          console.log(`[BackendManager] Backend running on port ${this.port}`);
          return;
        } catch (err) {
          lastError = err;
          console.warn(`[BackendManager] Failed to start on port ${candidate}: ${err.message}`);
          this._killCurrent();
        }
      }

      this._setState('failed', lastError ? lastError.message : 'no usable port');
      throw lastError || new Error('Backend failed to start');
    } finally {
      this._startChainRunning = false;
    }
  }

  _killCurrent() {
    const proc = this.process;
    this.process = null;
    if (!proc) return;
    // In-process API only (no external command): uvicorn is our direct child
    // with no shell in between. On Windows Node maps kill() to
    // TerminateProcess, which force-closes the process and its handles.
    try { proc.kill('SIGKILL'); } catch (_) { /* already gone */ }
  }

  async _spawnAndWait(port, pythonCmd, backendRoot, healthTimeoutMs) {
    this.port = port;

    const args = [
      '-m', 'uvicorn', 'main:app',
      '--host', '127.0.0.1',
      '--port', String(port),
      '--log-level', 'info'
    ];

    console.log(`[BackendManager] Starting: ${pythonCmd} ${args.join(' ')}`);
    console.log(`[BackendManager] CWD: ${backendRoot}`);

    this.process = spawn(pythonCmd, args, {
      cwd: backendRoot,
      env: { ...process.env, PRE_PORT: String(port) },
      stdio: ['pipe', 'pipe', 'pipe'],
      // On Windows, hide the console window for the child process
      windowsHide: true
    });

    const proc = this.process;
    proc.stdout.on('data', (data) => {
      console.log(`[Backend] ${data.toString().trim()}`);
    });

    proc.stderr.on('data', (data) => {
      console.error(`[Backend] ${data.toString().trim()}`);
    });

    proc.on('error', (err) => {
      console.error(`[BackendManager] Failed to spawn process: ${err.message}`);
    });

    proc.on('exit', (code) => {
      console.log(`[BackendManager] Process exited with code ${code}`);
      // Unexpected exit while this child is still the active backend →
      // auto-restart with backoff (a manual stop() cancels via userStopped).
      if (this.process === proc) {
        this.process = null;
        this._scheduleRestart();
      }
    });

    await this._waitForHealth(port, healthTimeoutMs);
    this._setState('running');
  }

  /**
   * Restart after an unexpected exit. Backs off exponentially and gives up
   * after MAX_RESTART_ATTEMPTS quick crashes; stop() cancels pending restarts.
   */
  _scheduleRestart() {
    if (this.userStopped || this._restartTimer) return;
    this.restartAttempts += 1;
    if (this.restartAttempts > MAX_RESTART_ATTEMPTS) {
      this._setState('failed', `Backend exited and auto-restart gave up after ${MAX_RESTART_ATTEMPTS} attempts.`);
      return;
    }
    const delay = Math.min(
      RESTART_BACKOFF_BASE_MS * Math.pow(2, this.restartAttempts - 1),
      RESTART_BACKOFF_MAX_MS
    );
    console.log(`[BackendManager] Unexpected exit — restarting in ${delay}ms (attempt ${this.restartAttempts}/${MAX_RESTART_ATTEMPTS})`);
    this._setState('starting', `restarting (attempt ${this.restartAttempts}/${MAX_RESTART_ATTEMPTS})`);
    this._restartTimer = setTimeout(() => {
      this._restartTimer = null;
      if (this.userStopped) return;
      // _startChain marks the manager 'failed' on total failure; errors are
      // contained there, so no unhandled rejection escapes this timer.
      this._startChain(this._lastIsPackaged, 20000).catch(() => { /* state already 'failed' */ });
    }, delay);
  }

  stop() {
    this.userStopped = true;              // cancel any pending auto-restart
    if (this._restartTimer) {
      clearTimeout(this._restartTimer);
      this._restartTimer = null;
    }
    this._setState('stopped');
    const proc = this.process;
    this.process = null;                  // idempotent: safe from every quit hook
    if (!proc) return;
    const pid = proc.pid;
    if (process.platform === 'win32') {
      // Synchronous on purpose: with the old fire-and-forget taskkill, the
      // Electron process could exit before the kill landed, leaving the
      // python backend alive with its working directory inside the packaged
      // resources/ — which pins the unpacked build output and breaks the
      // next packaging run ("app.asar is being used by another process").
      spawnSync('taskkill', ['/pid', String(pid), '/T', '/F'], {
        windowsHide: true,
      });
      try { proc.kill(); } catch (_) { /* already gone */ }
    } else {
      try { proc.kill('SIGTERM'); } catch (_) { /* already gone */ }
    }
  }

  _waitForHealth(port, timeoutMs) {
    // The probe must confirm it is talking to OUR backend, not any other app
    // answering on the same port. PolymCrystIndex also serves /health on its
    // own port; if it (or anything else) is squatting on `port`, our uvicorn
    // can't bind and the old code falsely accepted the foreign /health 200,
    // after which every /api/integration POST came back 405.
    const EXPECTED_APP = 'polymcrystrefine-pre';
    const start = Date.now();
    return new Promise((resolve, reject) => {
      const check = () => {
        const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
          let body = '';
          res.on('data', (chunk) => { body += chunk; });
          res.on('end', () => {
            if (res.statusCode !== 200) {
              retry();
              return;
            }
            let parsed = null;
            try { parsed = JSON.parse(body); } catch (_) { /* not our backend */ }
            if (parsed && parsed.app === EXPECTED_APP) {
              resolve();
              return;
            }
            // 200 but it's a different application — our port is taken.
            const got = (parsed && parsed.app) || 'unknown';
            reject(new Error(
              `Port ${port} is already in use by another application ` +
              `(health reported app="${got}", expected "${EXPECTED_APP}"). ` +
              `Close it (e.g. PolymCrystIndex) or set a different port with ` +
              `PRE_BACKEND_PORT / PRE_PORT.`
            ));
          });
        });
        req.on('error', retry);
        req.setTimeout(2000, () => {
          req.destroy();
          retry();
        });
      };

      const retry = () => {
        if (Date.now() - start > timeoutMs) {
          reject(new Error(`Backend health check timed out after ${timeoutMs}ms`));
          return;
        }
        setTimeout(check, 1000);
      };

      check();
    });
  }
}

module.exports = BackendManager;
