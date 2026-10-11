<template>
  <div class="app-layout">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <div class="logo" :title="t('app.name')">
          <!-- App icon (magnifier on molecule) -->
          <img src="/icon.png" alt="" />
        </div>
        <div class="brand">
          <h1 class="brand-name">
            {{ t('app.name') }}
            <span class="brand-aux-badge">Aux</span>
          </h1>
          <span class="brand-version">{{ versionLabel }}</span>
        </div>
      </div>

      <div class="header-center">
        <span v-if="currentModule" class="module-label">{{ currentModule.label }}</span>
        <div v-if="currentModule" class="module-copy">
          <div class="module-title-row">
            <strong>{{ currentModule.title }}</strong>
            <span v-if="currentModule.preview" class="module-preview-chip">{{ t('home.badges.preview') }}</span>
          </div>
          <span>{{ currentModule.desc }}</span>
        </div>
      </div>

      <div class="header-right">
        <button v-if="route.path !== '/app/home'" class="btn-home" @click="goHome">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          <span>{{ t('common.home') }}</span>
        </button>

        <div class="lang-switch">
          <button
            v-for="loc in availableLocales"
            :key="loc.code"
            :class="['lang-btn', { active: currentLocale === loc.code }]"
            @click="switchLocale(loc.code)"
          >{{ loc.code === 'zh-CN' ? '中文' : 'EN' }}</button>
        </div>
      </div>
    </header>

    <!-- Content -->
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { setLocale, getAvailableLocales } from '@/i18n';
import { getRuntimeInfo } from '@/services/runtime';

const route = useRoute();
const router = useRouter();
const { t, locale } = useI18n();

const currentLocale = computed(() => locale.value);
const availableLocales = getAvailableLocales();

// Header version comes from the RUNNING app (Electron's app.getVersion(),
// i.e. PRE/package.json) so it can never drift from the packaged artifact;
// the plain-browser fallback reads frontend/package.json via the
// __APP_VERSION__ define in vite.config.js. The i18n key only carries the
// edition tag ("辅助功能版"/"Aux"), never a number.
const appVersion = ref(__APP_VERSION__);
onMounted(async () => {
  const info = await getRuntimeInfo();
  if (info?.version) appVersion.value = info.version;
});
const versionLabel = computed(() => `v${appVersion.value} · ${t('app.versionTag')}`);

function switchLocale(code) {
  setLocale(code);
}

function goHome() {
  router.push('/app/home');
}

// Each module surfaces a label pill + a title/description in the header.
const moduleMeta = computed(() => ({
  home:       { label: t('app.module'), title: t('home.title'), desc: t('home.subtitle') },
  integration:{ label: t('app.module'), title: t('integration.title'), desc: t('integration.header') },
  waxs:       { label: t('app.module'), title: t('home.modules.waxs.title'), desc: t('home.modules.waxs.desc') },
  giwaxs:     { label: t('app.module'), title: t('home.modules.giwaxs.title'), desc: t('home.modules.giwaxs.desc'), preview: true },
  cif:        { label: t('app.module'), title: t('home.modules.cif.title'), desc: t('home.modules.cif.desc') },
  xrd:        { label: t('app.module'), title: t('home.modules.xrd.title'), desc: t('home.modules.xrd.desc') },
  analysis:   { label: t('app.module'), title: t('home.modules.analysis.title'), desc: t('home.modules.analysis.desc') },
  viewer:     { label: t('app.module'), title: t('home.modules.viewer.title'), desc: t('home.modules.viewer.desc') },
  inputGen:   { label: t('app.module'), title: t('home.modules.inputGen.title'), desc: t('home.modules.inputGen.desc') },
  lmpExtractor:{ label: t('app.module'), title: t('home.modules.lmpExtractor.title'), desc: t('home.modules.lmpExtractor.desc') },
  cifH:       { label: t('app.module'), title: t('home.modules.cifH.title'), desc: t('home.modules.cifH.desc') },
  symmetry:   { label: t('app.module'), title: t('home.modules.symmetry.title'), desc: t('home.modules.symmetry.desc') },
  deviation:  { label: t('app.module'), title: t('home.modules.deviation.title'), desc: t('home.modules.deviation.desc') },
  cp2k:       { label: t('app.module'), title: t('home.modules.cp2k.title'), desc: t('home.modules.cp2k.desc') },
  qzSlice: { label: t('app.module'), title: t('home.modules.qzSlice.title'), desc: t('home.modules.qzSlice.desc'), preview: true }
}));

const currentModule = computed(() => {
  const key = route.meta?.moduleKey;
  return key ? moduleMeta.value[key] || null : null;
});

// Ctrl+K command palette shortcut (placeholder)
function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    console.log('[Command Palette] Ctrl+K triggered - command palette placeholder');
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  /* Sub-pages keep a hint of the homepage's violet backdrop (static, no
     particles — the animated canvas only ever renders on Home). */
  background:
    radial-gradient(1100px 420px at 18% -8%, rgba(237, 233, 254, 0.9) 0%, rgba(237, 233, 254, 0) 62%),
    radial-gradient(900px 380px at 92% 4%, rgba(245, 243, 255, 0.85) 0%, rgba(245, 243, 255, 0) 58%),
    var(--bg-primary);
  background-attachment: fixed;
}

/* ---- Header ---- */
.header {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 32px;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 24px;
}

.header-left {
  gap: 16px;
  min-width: 0;
}

.header-center {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 28px;
}

.module-label {
  padding: 6px 12px;
  border-radius: var(--radius-full);
  background: var(--primary-bg);
  color: var(--primary);
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  flex-shrink: 0;
}

.module-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  line-height: 1.4;
}

.module-copy strong {
  font-size: 0.95rem;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Title row holds the module title + the optional preview badge. */
.module-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.module-preview-chip {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #92400e;
  background: rgba(245, 158, 11, 0.14);
  border: 1px solid rgba(245, 158, 11, 0.45);
  white-space: nowrap;
  overflow: visible;
  text-overflow: clip;
}

.module-copy span {
  font-size: 0.75rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ---- Logo + Brand ---- */
.logo {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-surface-elevated);
  padding: 3px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  flex-shrink: 0;
}

.logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
}

.brand {
  display: flex;
  flex-direction: column;
  line-height: 1.1;
}

.brand-name {
  font-size: 1.4rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  /* Slightly taller so the gradient-clipped glyphs (incl. descenders) are not
     cut off by the version line below. */
  line-height: 1.25;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  display: flex;
  align-items: center;
  gap: 8px;
}

.brand-aux-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: linear-gradient(135deg, #F59E0B 0%, #F97316 100%);
  color: #fff;
  font-size: 0.62rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  -webkit-text-fill-color: #fff;
  line-height: 1.4;
  vertical-align: middle;
}

.brand-version {
  font-size: 0.7rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
  margin-top: 2px;
}

/* ---- Header right controls ---- */
.btn-home {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 18px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-home:hover {
  background: var(--bg-surface-alt);
  border-color: var(--border-hover);
  color: var(--text-primary);
}

.btn-home svg {
  width: 17px;
  height: 17px;
}

.lang-switch {
  display: flex;
  gap: 2px;
  background: var(--bg-surface-alt);
  border-radius: var(--radius-md);
  padding: 2px;
}

.lang-btn {
  padding: 7px 14px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all var(--transition-fast);
}

.lang-btn:hover {
  color: var(--text-primary);
}

.lang-btn.active {
  background: var(--bg-surface);
  color: var(--primary);
  box-shadow: var(--shadow-sm);
}

/* ---- Main Content ---- */
.main-content {
  flex: 1;
  width: 100%;
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 40px;
  display: flex;
  flex-direction: column;
  gap: 32px;
  position: relative;
  isolation: isolate;
}

/* Single-tone background — depth comes from layered surfaces, not orbs/grid */


/* ---- Responsive ---- */
@media (max-width: 900px) {
  .header {
    padding: 0 16px;
  }
  .header-center {
    display: none;
  }
  .main-content {
    padding: 24px;
    gap: 24px;
  }
  .btn-home span {
    display: none;
  }
}
</style>
