import request from './request';

// ---- Health ----
export const getHealth = () => request.get('/health');

// ---- Integration Merge (formerly WAXS Pipeline) ----
export const waxsUploadFiles = (formData) =>
  request.post('/waxs/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const waxsRunBackground = (params) =>
  request.post('/waxs/background', params);

export const waxsRunMerge = (params) =>
  request.post('/waxs/merge', params);

export const waxsMergeExport = (params) =>
  request.post('/waxs/merge/export', params, { responseType: 'blob' });

export const waxsStepsExport = (params) =>
  request.post('/waxs/steps/export', params, { responseType: 'blob' });

export const waxsParsePoni = (fileId) =>
  request.post(`/waxs/parse-poni`, { fileId });

export const waxsExportPoni = (params) =>
  request.post(`/waxs/export-poni`, params, { responseType: 'blob' });

// ---- GIWAXS Fiber-Integration Merge ----
export const giwaxsUploadFiles = (formData) =>
  request.post('/giwaxs-merge/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const giwaxsParsePoni = (fileId) =>
  request.post(`/giwaxs-merge/parse-poni`, { fileId });

export const giwaxsRunMerge = (params) =>
  request.post('/giwaxs-merge/run', params);

export const giwaxsRenderPng = (params) =>
  request.post('/giwaxs-merge/render-png', params, { responseType: 'blob' });

export const giwaxsExportZip = (params) =>
  request.post('/giwaxs-merge/export', params, { responseType: 'blob' });

// ---- XRD Simulator ----
export const xrdUploadPeaks = (formData) =>
  request.post('/xrd/upload-peaks', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const xrdUploadCif = (formData) =>
  request.post('/xrd/upload-cif', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const xrdRunSimulation = (params) =>
  request.post('/xrd/simulate', params);

export const xrdRunDualSimulation = (params) =>
  request.post('/xrd/simulate-dual', params);

export const xrdGeneratePeaks = (params) =>
  request.post('/xrd/generate-peaks', params);

export const xrdUploadFile = (formData) =>
  request.post('/xrd/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const xrdParsePoni = (fileId) =>
  request.post(`/xrd/parse-poni`, { fileId });

export const xrdParseProcessingInfo = (fileId) =>
  request.post(`/xrd/parse-processing-info`, { fileId });

export const xrdDownloadResult = (taskId) =>
  request.get(`/xrd/task/${taskId}/download`, { responseType: 'blob' });

// Full-resolution simulation image as raw float32 bytes (behind a decimated
// detector preview). Response is an ArrayBuffer of rows*cols float32 values.
export const xrdDownloadRawF32 = (taskId) =>
  request.get(`/xrd/task/${taskId}/f32`, { responseType: 'arraybuffer' });

export const xrdLoadExperiment = (fileId, mode) =>
  request.post(`/xrd/load-experiment`, { fileId, mode });

// ---- CIF Hydrogenation ----
export const cifhUpload = (formData) =>
  request.post('/cifh/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const cifhAddHydrogens = (params) =>
  request.post('/cifh/add-hydrogens', params);

export const cifhExport = (params) =>
  request.post('/cifh/export', params);

export const cifhDownload = (taskId) =>
  request.get(`/cifh/task/${taskId}/download`, { responseType: 'blob' });

// ---- Space Group Detection (cell preserved) ----
export const symmetryUpload = (formData) =>
  request.post('/symmetry/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const symmetryAnalyze = (params) =>
  request.post('/symmetry/analyze', params);

export const symmetryScan = (params) =>
  request.post('/symmetry/scan', params);

export const symmetrySymmetrize = (params) =>
  request.post('/symmetry/symmetrize', params);

export const symmetryDownload = (taskId) =>
  request.get(`/symmetry/task/${taskId}/download`, { responseType: 'blob' });

// ---- Image Analysis ----
export const analysisUploadImage = (formData) =>
  request.post('/analysis/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const analysisUploadMiller = (formData) =>
  request.post('/analysis/upload-miller', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const analysisGetImage = (fileId) =>
  request.get(`/analysis/image/${fileId}`);

export const analysisParseInfo = (formData) =>
  request.post('/analysis/parse-info', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const analysisCalculateIntensity = (params) =>
  request.post('/analysis/intensity', params);

export const analysisUploadPoni = (formData) =>
  request.post('/analysis/poni-upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const analysisDetectorRoiWindow = (params) =>
  request.post('/analysis/detector-roi-window', params);

export const analysisDetectorClick = (params) =>
  request.post('/analysis/detector-click', params);

export const analysisDetectorIntegrate = (params) =>
  request.post('/analysis/detector-integrate', params);

export const analysisDetectorWedge = (params) =>
  request.post('/analysis/detector-wedge', params);

export const analysisEstimateBackground = (params) =>
  request.post('/analysis/background-estimate', params);

export const analysisExportRoi = (params) =>
  request.post('/analysis/export-roi', params);

export const analysisMatchMiller = (params) =>
  request.post('/analysis/match-miller', params);

// ---- Viewer ----
export const viewerUploadFiles = (formData) =>
  request.post('/viewer/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const viewerGetImageData = (fileId, maxDim = null) =>
  request.get(`/viewer/image/${fileId}`, { params: maxDim ? { max_dim: maxDim } : undefined });

export const viewerGetFileList = () =>
  request.get('/viewer/file-list');

export const viewerDeleteFile = (fileId) =>
  request.delete(`/viewer/file/${fileId}`);

export const viewerDeleteAllFiles = () =>
  request.delete('/viewer/files');

export const viewerExportPng = (params) =>
  request.post('/viewer/export', params, { responseType: 'blob' });

export const viewerExportBatchZip = (params) =>
  request.post('/viewer/export-batch', params, { responseType: 'blob' });

// ---- 2D Integration ----
export const integrationUpload = (formData) =>
  request.post('/integration/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const integrationParsePoni = (fileId) =>
  request.post('/integration/parse-poni', { fileId });

export const integrationParseInfo = (formData) =>
  request.post('/integration/parse-info', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const integrationAutoThreshold = (params) =>
  request.post('/integration/auto-threshold', params);

export const integrationGetImage = (fileId, maxSide = 500) =>
  request.get(`/integration/image/${fileId}`, { params: { maxSide } });

export const integrationRun = (params) =>
  request.post('/integration/run', params);

export const integrationExportZip = (params) =>
  request.post('/integration/export', params, { responseType: 'blob' });

export const integrationExportBatchZip = (params) =>
  request.post('/integration/export-batch', params, { responseType: 'blob' });

export const integrationExportPoni = (params) =>
  request.post('/integration/export-poni', params, { responseType: 'blob' });

// ---- Input Generator ----
export const inputGenGenerate = (params) =>
  request.post('/input-generator/generate', params, { responseType: 'text' });

// ---- CP2K FIBER_DIFFRACTION Generator ----
export const cp2kGenerate = (params) =>
  request.post('/cp2k/generate', params, { responseType: 'text' });

// ---- OPLSAA (LAMMPS data) Force Field Extractor ----
export const lmpParseStructure = (formData) =>
  request.post('/lmp-extractor/parse-structure', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const lmpParseLmp = (formData) =>
  request.post('/lmp-extractor/parse-lmp', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const lmpValidate = (params) =>
  request.post('/lmp-extractor/validate', params);

export const lmpExtract = (params) =>
  request.post('/lmp-extractor/extract', params, { responseType: 'text' });

// ---- Structure Deviation Report (DFT-relaxed vs reference) ----
// Upload one structure file (.cif or CP2K .pdb); call once per slot.
export const deviationUpload = (formData) =>
  request.post('/deviation/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

// Pair the two structures' atoms and return all per-atom deviations.
export const deviationCompare = (params) =>
  request.post('/deviation/compare', params);

// Render the comparison as a Markdown / CSV report file.
export const deviationReport = (params) =>
  request.post('/deviation/report', params);

// Download a generated report.
export const deviationDownload = (taskId) =>
  request.get(`/deviation/task/${taskId}/download`, { responseType: 'blob' });


// ---- Qz Band Slice (GIWAXS merge map -> per-band I(q) curves) ----
export const qzSliceUpload = (formData) =>
  request.post('/qz-slice/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } });

export const qzSliceAttach = (params) =>
  request.post('/qz-slice/attach', params);

export const qzSliceRun = (params) =>
  request.post('/qz-slice/run', params);

export const qzSliceExportCsv = (params) =>
  request.post('/qz-slice/export-csv', params, { responseType: 'blob' });

// Whitespace-column TXT variant (qip first column) for the lab 1-D pipelines.
export const qzSliceExportTxt = (params) =>
  request.post('/qz-slice/export-txt', params, { responseType: 'blob' });

