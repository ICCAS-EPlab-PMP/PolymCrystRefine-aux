/**
 * ROI CSV parsing for the Image Analysis page's "导入 ROI" button.
 *
 * Four layouts are recognised, keyed on the header row:
 *
 *  1. matched_intensity.csv — "导出匹配强度" output:
 *     ID,Match_hkl,New_Psi_Min(deg),New_Psi_Max(deg),New_Q_Min(A-1),
 *     New_Q_Max(A-1),Status,Refined_Flag,Norm_Intensity,Raw_Intensity
 *     The q/ψ columns hold the Miller-derived export box, so the ROI is
 *     restored from those; the hkl / refined / raw-intensity columns come
 *     back alongside.
 *
 *  2. roi_records.csv (full format, 导出 ROI output):
 *     index,qMin,qMax,azimuthMin,azimuthMax,multiplier,label,bgMode,
 *     bgFixedValue,bgSide,bgWidth,matchHkl,refined,matchQMin,matchQMax,
 *     matchAzMin,matchAzMax,exportQMin,exportQMax,exportPsiMin,exportPsiMax
 *     Detected by the presence of the bgMode column. Restores per-peak
 *     background subtraction, the multiplier, the refine (精致化) box and
 *     the Miller-derived export ranges; empty cells fall back to the
 *     caller's defaults.
 *
 *  3. roi_records.csv (legacy six-column layout) —
 *     index,qMin,qMax,azimuthMin,azimuthMax,multiplier
 *
 *  4. Headerless / unknown CSVs keep the historical positional mapping
 *     (index, qMin, qMax, azimuthMin, azimuthMax, multiplier).
 *
 * Header cells are matched after stripping BOM / quotes / whitespace and
 * unit suffixes like "(deg)" / "(A-1)", so "New_Q_Min(A-1)" → "new_q_min".
 */

// Normalize a header cell for name-based matching.
function normHeader(s) {
  return String(s)
    .replace(/^\uFEFF/, '')
    .trim()
    .replace(/["']/g, '')
    .replace(/\(.*?\)/g, '')
    .replace(/\s+/g, '')
    .toLowerCase()
}

function toNum(v, fallback = 0) {
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : fallback
}

// Split one CSV row, honouring double-quoted fields (a literal quote inside a
// field is escaped as ""). The export quotes labels/hkl that contain commas,
// so a naive split(',') would shift every later column.
function splitCsvLine(line) {
  const out = []
  let cur = ''
  let inQ = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (inQ) {
      if (ch === '"') {
        if (line[i + 1] === '"') { cur += '"'; i++ }
        else inQ = false
      } else {
        cur += ch
      }
    } else if (ch === '"') {
      inQ = true
    } else if (ch === ',') {
      out.push(cur)
      cur = ''
    } else {
      cur += ch
    }
  }
  out.push(cur)
  return out
}

// Multiplier cell → 0/1/2/4. Presence-checked so a legitimate 0 survives
// (`toNum(v, 1) || 1` used to coerce 0 → 1 and silently drop the value);
// empty/missing cells keep the default 1.
function toMultiplier(v, fallback = 1) {
  if (v == null || String(v).trim() === '') return fallback
  const n = parseFloat(v)
  return Number.isFinite(n) ? Math.round(n) : fallback
}

// Optional numeric cell → number, or undefined when empty/absent (so the
// caller's defaults survive an object spread).
function toOptNum(v) {
  if (v == null || String(v).trim() === '') return undefined
  const n = parseFloat(v)
  return Number.isFinite(n) ? n : undefined
}

/**
 * Parse ROI CSV text into ROI records.
 *
 * @param {string} text raw CSV content
 * @param {object|null} bgDefaults per-peak background fields copied into every
 *   record ({ bgMode, bgFixedValue, bgSide, bgWidth }); pass null to omit them.
 * @returns {{ rois: object[], format: string, count: number }}
 */
export function parseRoiCsv(text, bgDefaults = null) {
  const lines = String(text).trim().split(/\r?\n/).filter(l => l.trim().length)
  if (lines.length < 1) return { rois: [], format: 'empty', count: 0 }
  const headers = splitCsvLine(lines[0]).map(normHeader)
  // A headerless CSV whose first line is pure numbers would lose that row if
  // it were consumed as the header — treat it as data instead.
  const headerIsData = headers.every(h => h === '' || Number.isFinite(parseFloat(h)))
  const dataLines = headerIsData ? lines : lines.slice(1)
  const col = (cols, name) => {
    const idx = headers.indexOf(name)
    return idx >= 0 ? cols[idx] : undefined
  }
  const baseRoi = () => ({
    multiplier: 1,
    intensity: null,
    pixelCount: null,
    label: '',
    matchHkl: null,
    matchQMin: null, matchQMax: null, matchAzMin: null, matchAzMax: null,
    exportQMin: null, exportQMax: null, exportPsiMin: null, exportPsiMax: null,
    refined: false,
    ...(bgDefaults || {}),
  })

  const rois = []
  let format = 'legacy'
  for (let i = 0; i < dataLines.length; i++) {
    const cols = splitCsvLine(dataLines[i])
    if (cols.length < 4) continue
    let roi
    if (headers.includes('new_q_min') && headers.includes('new_q_max')) {
      // matched_intensity.csv
      const hkl = (col(cols, 'match_hkl') || '').trim()
      const good = hkl && hkl.toUpperCase() !== 'N/A'
      roi = {
        ...baseRoi(),
        qMin: toNum(col(cols, 'new_q_min')),
        qMax: toNum(col(cols, 'new_q_max')),
        azimuthMin: toNum(col(cols, 'new_psi_min')),
        azimuthMax: toNum(col(cols, 'new_psi_max')),
        label: good ? hkl : '',
        matchHkl: good ? hkl : null,
        refined: (col(cols, 'refined_flag') || '').trim() === 'Refined',
        intensity: col(cols, 'raw_intensity') != null ? toNum(col(cols, 'raw_intensity')) : null,
        exportQMin: toNum(col(cols, 'new_q_min')),
        exportQMax: toNum(col(cols, 'new_q_max')),
        exportPsiMin: toNum(col(cols, 'new_psi_min')),
        exportPsiMax: toNum(col(cols, 'new_psi_max')),
      }
      format = 'matched_intensity'
    } else if (headers.includes('bgmode')) {
      // Full roi_records.csv: geometry + multiplier + per-peak background +
      // refine/match results (导出 ROI current output).
      roi = {
        ...baseRoi(),
        qMin: toNum(col(cols, 'qmin')),
        qMax: toNum(col(cols, 'qmax')),
        azimuthMin: toNum(col(cols, 'azimuthmin')),
        azimuthMax: toNum(col(cols, 'azimuthmax')),
        multiplier: toMultiplier(col(cols, 'multiplier')),
        label: (col(cols, 'label') || '').trim(),
        matchHkl: (col(cols, 'matchhkl') || '').trim() || null,
        refined: (col(cols, 'refined') || '').trim() === 'Refined',
      }
      const opt = (name) => toOptNum(col(cols, name))
      const box = [
        opt('matchqmin'), opt('matchqmax'), opt('matchazmin'), opt('matchazmax'),
      ]
      if (box.every(v => v !== undefined)) {
        [roi.matchQMin, roi.matchQMax, roi.matchAzMin, roi.matchAzMax] = box
      }
      const exp = [opt('exportqmin'), opt('exportqmax'), opt('exportpsimin'), opt('exportpsimax')]
      if (exp.some(v => v !== undefined)) {
        roi.exportQMin = exp[0] ?? null
        roi.exportQMax = exp[1] ?? null
        roi.exportPsiMin = exp[2] ?? null
        roi.exportPsiMax = exp[3] ?? null
      }
      // Per-peak background: only overwrite the defaults for cells actually
      // present, so an old file's missing columns keep the panel defaults.
      const bgMode = (col(cols, 'bgmode') || '').trim()
      if (bgMode) {
        roi.bgMode = bgMode
        if (bgMode === 'fixed') {
          const v = toOptNum(col(cols, 'bgfixedvalue'))
          roi.bgFixedValue = v !== undefined ? v : 0
        } else if (bgMode === 'neighbor') {
          roi.bgSide = (col(cols, 'bgside') || '').trim() || 'both'
          const w = toOptNum(col(cols, 'bgwidth'))
          roi.bgWidth = w !== undefined ? Math.max(0, Math.round(w)) : 10
        }
      }
      format = 'roi_records_full'
    } else if (headers.includes('qmin') && headers.includes('qmax')) {
      // roi_records.csv (legacy six-column layout)
      roi = {
        ...baseRoi(),
        qMin: toNum(col(cols, 'qmin')),
        qMax: toNum(col(cols, 'qmax')),
        azimuthMin: toNum(col(cols, 'azimuthmin')),
        azimuthMax: toNum(col(cols, 'azimuthmax')),
        multiplier: toMultiplier(col(cols, 'multiplier')),
      }
      format = 'roi_records'
    } else {
      // Headerless / unknown: historical positional mapping.
      roi = {
        ...baseRoi(),
        qMin: toNum(cols[1] ?? cols[0]),
        qMax: toNum(cols[2] ?? cols[1]),
        azimuthMin: toNum(cols[3] ?? cols[2]),
        azimuthMax: toNum(cols[4] ?? cols[3]),
        multiplier: toMultiplier(cols[5]),
      }
      format = 'legacy'
    }
    rois.push(roi)
  }
  return { rois, format, count: rois.length }
}
