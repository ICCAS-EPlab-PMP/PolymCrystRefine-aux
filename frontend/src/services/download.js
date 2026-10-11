/**
 * File download helpers that work both in Electron and plain browsers.
 *
 * Why this exists: the classic `URL.createObjectURL(blob)` + `<a download>.click()`
 * pattern throws "An object could not be cloned" under Electron with
 * contextIsolation enabled — Electron intercepts the click and marshals the DOM
 * Event/Blob through IPC, which the structured-clone algorithm rejects. Under
 * Electron we therefore route through the native `dialog:save-file` IPC channel
 * (which only carries a base64 data: URL string) and fall back to the `<a>`
 * download in a regular browser.
 */

import { isElectron } from './runtime';

/**
 * Read a Blob/File as a base64 data: URL.
 * @param {Blob} blob
 * @returns {Promise<string>}
 */
function blobToDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error('FileReader failed'));
    reader.readAsDataURL(blob);
  });
}

/**
 * Derive the file extension (without dot) from a filename, lower-cased.
 * @param {string} filename
 * @returns {string}
 */
function extOf(filename) {
  const i = String(filename || '').lastIndexOf('.');
  return i >= 0 ? filename.slice(i + 1).toLowerCase() : '';
}

/**
 * Save a Blob to disk under the given filename.
 *
 * Under Electron this pops the native "save as" dialog (via the `saveFile` IPC);
 * the Blob is first converted to a base64 data: URL so only a plain string
 * crosses IPC. In a plain browser it falls back to a Blob/Object-URL download.
 *
 * @param {Blob} blob
 * @param {string} filename
 * @returns {Promise<{ok: boolean, filePath?: string, canceled?: boolean}>}
 */
export async function saveBlob(blob, filename) {
  if (isElectron()) {
    const dataUrl = await blobToDataUrl(blob);
    const ext = extOf(filename);
    const filters = ext
      ? [{ name: ext.toUpperCase(), extensions: [ext] }]
      : [{ name: 'All Files', extensions: ['*'] }];
    return window.electronAPI.saveFile({ defaultName: filename, filters, dataUrl });
  }
  // Browser fallback: object URL + <a download>
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return { ok: true };
}

/**
 * Save a plain string to disk under the given filename.
 *
 * @param {string} text
 * @param {string} filename
 * @param {string} [mime] - e.g. 'text/csv'; used by the browser fallback Blob type.
 * @returns {Promise<{ok: boolean, filePath?: string, canceled?: boolean}>}
 */
export async function saveText(text, filename, mime) {
  if (isElectron()) {
    const ext = extOf(filename);
    const filters = ext
      ? [{ name: ext.toUpperCase(), extensions: [ext] }]
      : [{ name: 'All Files', extensions: ['*'] }];
    return window.electronAPI.saveFile({ defaultName: filename, filters, text });
  }
  const blob = new Blob([text == null ? '' : text], { type: mime || 'text/plain' });
  return saveBlob(blob, filename);
}
