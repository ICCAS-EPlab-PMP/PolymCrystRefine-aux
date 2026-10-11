#!/usr/bin/env node
'use strict';

// Prebuild guard: keep the electron-builder output directory reusable so
// every build goes to the SAME release folder instead of bumping
// release-auxN directories whenever the old one cannot be emptied.
//
// Why this exists — two lock sources kept breaking rebuilds:
//   1. A test instance still running from <output>/win-unpacked: Electron
//      holds app.asar open, and a backend python that outlived the window
//      pins resources/backend (its working directory).
//   2. Workspace search indexers / antivirus scanners holding freshly
//      written ~80 MB artifacts (app.asar) open across builds.
//
// What it does:
//   a. kills leftover processes whose executable lives under win-unpacked
//      (our own test instances — nothing else is touched),
//   b. kills leaked backend pythons that hold win-unpacked files open
//      (identified precisely via the Restart Manager, never by name alone),
//   c. removes win-unpacked with retries (scanner locks are transient),
//   d. on persistent locks, NAMES the holding process and exits non-zero so
//      the failure is actionable instead of a cryptic electron-builder stack.

const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
const BUILDER_CFG = path.join(ROOT, 'electron', 'electron-builder.json');
const SCRIPTS = path.join(ROOT, 'electron', 'scripts');

const cfg = JSON.parse(fs.readFileSync(BUILDER_CFG, 'utf8'));
const outDirName = cfg.directories.output;
const outDir = path.resolve(ROOT, outDirName);
const winUnpacked = path.join(outDir, 'win-unpacked');

function log(msg) { console.log(`[prebuild-clean] ${msg}`); }

const isWindows = process.platform === 'win32';

function powershellToArray(script) {
  const out = execFileSync(
    'powershell', ['-NoProfile', '-Command', script],
    { encoding: 'utf8', windowsHide: true },
  ).trim();
  if (!out) return [];
  return out.split(/\r?\n/).filter(Boolean);
}

// ---------------------------------------------------------------- 1. leftovers
// Kill processes whose EXE runs from inside win-unpacked — these are test
// instances of our own app started by double-clicking the unpacked build.
function killUnpackedInstances() {
  if (!isWindows) return;
  let lines = [];
  try {
    lines = powershellToArray(
      `Get-CimInstance Win32_Process -Filter "ExecutablePath IS NOT NULL" | ` +
      `Where-Object { $_.ExecutablePath -like '${winUnpacked.replace(/\\/g, '\\\\')}*' } | ` +
      `ForEach-Object { "$($_.ProcessId)$([char]9)$($_.Name)" }`,
    );
  } catch (err) {
    log(`could not enumerate processes (${err.message}) — continuing`);
    return;
  }
  for (const line of lines) {
    const [pid, name] = line.split('\t');
    log(`killing leftover app process ${name} (PID ${pid}) started from ${outDirName}/win-unpacked`);
    spawnSync('taskkill', ['/pid', pid, '/T', '/F'], { windowsHide: true });
  }
}

// Ask the Windows Restart Manager who holds a file open.
// Returns [{ pid, name, exePath }] (never throws).
function findLockers(target) {
  if (!isWindows) return [];
  try {
    const lines = powershellToArray(
      `& '${path.join(SCRIPTS, 'find-lockers.ps1').replace(/'/g, "''")}' -Target '${target.replace(/'/g, "''")}'`,
    );
    if (!lines.length || lines[0] === 'NONE' || lines[0].startsWith('ERROR')) return [];
    return lines.map((l) => {
      const [pid, name, exePath] = l.split('\t');
      return { pid, name, exe: exePath || '' };
    });
  } catch (_) {
    return [];
  }
}

// A leaked backend python is identifiable BY EVIDENCE, not by name: it must
// hold a handle into win-unpacked. We kill exactly those and nothing else.
function killLeakedBackendPythons() {
  if (!isWindows) return;
  const probes = [
    path.join(winUnpacked, 'resources', 'app.asar'),
    path.join(winUnpacked, 'resources', 'backend', 'main.py'),
  ].filter((p) => fs.existsSync(p));

  for (const probe of probes) {
    for (const holder of findLockers(probe)) {
      const isPython = /^(python|pythonw)\.exe$/i.test(holder.name);
      if (!isPython) continue;
      log(`killing leaked backend python (PID ${holder.pid}) holding ${path.relative(outDir, probe)}`);
      spawnSync('taskkill', ['/pid', holder.pid, '/T', '/F'], { windowsHide: true });
    }
  }
}

// ------------------------------------------------------------------ 2. remove
function removeWinUnpacked() {
  if (!fs.existsSync(winUnpacked)) return true;
  try {
    fs.rmSync(winUnpacked, {
      recursive: true, force: true,
      maxRetries: 5, retryDelay: 500,   // transient scanner/indexer locks
    });
    return !fs.existsSync(winUnpacked);
  } catch (_) {
    return !fs.existsSync(winUnpacked);
  }
}

// -------------------------------------------------------------------- 3. main
if (!fs.existsSync(winUnpacked)) {
  log(`${outDirName}/win-unpacked not present — nothing to clean.`);
  process.exit(0);
}

killUnpackedInstances();
killLeakedBackendPythons();

let removed = false;
for (let attempt = 1; attempt <= 3 && !removed; attempt++) {
  removed = removeWinUnpacked();
  if (!removed) {
    log(`attempt ${attempt}/3: win-unpacked still locked, retrying...`);
    killLeakedBackendPythons();
  }
}

if (removed) {
  log(`${outDirName}/win-unpacked removed — output directory is free.`);
  process.exit(0);
}

// Persistent lock: name the holder(s) so the user knows exactly what to do.
const probe = [
  path.join(winUnpacked, 'resources', 'app.asar'),
].find((p) => fs.existsSync(p)) || winUnpacked;

const holders = findLockers(probe);
console.error('');
console.error('==================================================================');
console.error(`[prebuild-clean] Cannot empty ${outDirName}/win-unpacked.`);
if (holders.length) {
  console.error('The following process(es) hold it open:');
  for (const h of holders) {
    console.error(`  - PID ${h.pid}  ${h.name}  ${h.exe}`);
  }
  console.error('');
  console.error('Close that application (or restart it) and run the build again.');
  console.error('NOTE: if the holder is an editor/IDE or search indexer (it can keep');
  console.error('large freshly-written files like app.asar open), restarting that app');
  console.error('releases the lock; the build output itself does not need renaming.');
} else {
  console.error(`No process admitted to holding it via the Restart Manager (probe: ${probe}).`);
  console.error('This is usually an antivirus scan or a directory watcher — wait a');
  console.error('few seconds and run the build again.');
}
console.error('==================================================================');
process.exit(1);
