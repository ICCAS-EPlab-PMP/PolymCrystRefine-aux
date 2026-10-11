import { defineAsyncComponent } from 'vue';

const MainLayout = () => import('@/layouts/MainLayout.vue');

const userRoutes = [
  {
    path: '/app',
    component: MainLayout,
    children: [
      {
        path: '',
        redirect: 'home'
      },
      {
        path: 'home',
        name: 'Home',
        component: () => import('@/views/Home.vue'),
        meta: { moduleKey: 'home', title: 'Home' }
      },
      {
        path: '2d-integration',
        name: 'Integration2D',
        component: () => import('@/views/IntegrationPage.vue'),
        meta: { moduleKey: 'integration', title: '2D Intensity Integration' }
      },
      {
        path: 'integration-merge',
        name: 'IntegrationMerge',
        component: () => import('@/views/IntegrationMergePage.vue'),
        meta: { moduleKey: 'waxs', title: '2D Integration Processing' }
      },
      {
        path: 'giwaxs-merge',
        name: 'GiwaxsMerge',
        component: () => import('@/views/GiwaxsMergePage.vue'),
        meta: { moduleKey: 'giwaxs', title: 'GIWAXS Fiber Integration Merge' }
      },
      {
        path: 'cif-parser',
        name: 'CifParser',
        component: () => import('@/views/CifParserPage.vue'),
        meta: { moduleKey: 'cif', title: 'CIF Parser' }
      },
      {
        path: 'xrd-simulator',
        name: 'XrdSimulator',
        component: () => import('@/views/XrdSimulatorPage.vue'),
        meta: { moduleKey: 'xrd', title: 'XRD Gaussian Simulator' }
      },
      {
        path: 'image-analysis',
        name: 'ImageAnalysis',
        component: () => import('@/views/ImageAnalysisPage.vue'),
        meta: { moduleKey: 'analysis', title: 'Image Analysis' }
      },
      {
        path: 'viewer',
        name: 'Viewer',
        component: () => import('@/views/ViewerPage.vue'),
        meta: { moduleKey: 'viewer', title: 'Data Viewer' }
      },
      {
        path: 'input-generator',
        name: 'InputGenerator',
        component: () => import('@/views/InputGeneratorPage.vue'),
        meta: { moduleKey: 'inputGen', title: 'Refine Input Generator' }
      },
      {
        path: 'lmp-extractor',
        name: 'LmpExtractor',
        component: () => import('@/views/LmpExtractorPage.vue'),
        meta: { moduleKey: 'lmpExtractor', title: 'OPLSAA Force Field Extractor' }
      },
      {
        path: 'cif-hydrogen',
        name: 'CifHydrogen',
        component: () => import('@/views/CifHydrogenPage.vue'),
        meta: { moduleKey: 'cifH', title: 'CIF Hydrogenation' }
      },
      {
        path: 'symmetry',
        name: 'Symmetry',
        component: () => import('@/views/SymmetryPage.vue'),
        meta: { moduleKey: 'symmetry', title: 'Space Group Detection' }
      },
      {
        path: 'deviation-report',
        name: 'DeviationReport',
        component: () => import('@/views/DeviationReportPage.vue'),
        meta: { moduleKey: 'deviation', title: 'Structure Deviation Report' }
      },
      {
        path: 'cp2k-input',
        name: 'Cp2kInput',
        component: () => import('@/views/Cp2kInputPage.vue'),
        meta: { moduleKey: 'cp2k', title: 'CP2K FIBER_DIFFRACTION Generator' }
      },
      {
        path: 'qz-slice',
        name: 'QzSlice',
        component: () => import('@/views/QzSlicePage.vue'),
        meta: { moduleKey: 'qzSlice', title: 'Qz Band Integration' }
      }
    ]
  }
];

export default userRoutes;
