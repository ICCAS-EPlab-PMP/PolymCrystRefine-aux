<template>
  <div class="home-page">
    <!-- Low-CPU diffraction backdrop that follows the pointer. Particle
         meteors can be toggled off from the settings FAB. -->
    <DiffractionBackground :particles="showParticles" />

    <div class="home-content">
      <!-- Hero: title on the left, vertical workflow on the right. Each
           stage pops its sub-step chips out to the LEFT on hover; every
           node and chip scrolls to its module section below. -->
      <section class="hero-panel" id="sec-hero">
        <div class="hero-copy">
          <div class="hero-kicker">{{ t('home.kicker') }}</div>
          <h2 class="hero-title">
            <span class="hero-title-brand">{{ t('home.title') }}</span>
            <span class="hero-title-sub">{{ t('home.subtitle') }}</span>
          </h2>
          <div class="hero-pill-row">
            <span class="hero-pill" v-for="p in heroPills" :key="p">{{ p }}</span>
          </div>
        </div>

        <div class="hero-flow" id="sec-workflow">
          <div class="hero-flow-head">
            <span class="hero-flow-eyebrow">{{ t('home.workflow.eyebrow') }}</span>
            <span class="hero-flow-title">{{ t('home.workflow.title') }}</span>
          </div>
          <div class="vflow">
            <div
              v-for="(stage, i) in workflowStages"
              :key="stage.id"
              class="vflow-stage"
            >
              <div class="vflow-branch">
                <router-link
                  v-for="(step, si) in stage.steps"
                  :key="stage.id + step.label"
                  class="vflow-chip"
                  :style="{ transitionDelay: `${si * 45}ms` }"
                  :to="step.to"
                >
                  {{ step.label }}
                </router-link>
              </div>
              <span class="vflow-rail" aria-hidden="true"></span>
              <button
                class="vflow-node"
                type="button"
                @click="scrollToSection(stage.anchor)"
              >
                <span class="flow-num">{{ i + 1 }}</span>
                <span class="vflow-labels">
                  <span class="vflow-name">{{ stage.title }}</span>
                  <span class="vflow-lead">{{ stage.lead }}</span>
                </span>
                <svg class="vflow-go" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="9,18 15,12 9,6" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Module groups (功能分栏) — every group shares the SAME 4-column
           grid so all cards on the page are identical in size. -->
      <section
        v-for="group in moduleGroups"
        :key="group.title"
        class="module-group"
        :id="`sec-${group.id}`"
      >
        <div class="group-head">
          <span class="group-eyebrow">{{ group.eyebrow }}</span>
          <h3 class="group-title">{{ group.title }}</h3>
        </div>

        <div class="group-grid">
          <router-link
            v-for="mod in group.modules"
            :key="mod.path"
            :to="mod.path"
            class="feature-card"
          >
            <div class="card-header">
              <span class="card-icon" v-html="mod.icon"></span>
              <h4 class="card-title">{{ mod.title }}</h4>
              <span v-if="mod.preview" class="card-preview-chip">{{ t('home.badges.preview') }}</span>
            </div>
            <p class="card-desc">{{ mod.desc }}</p>
          </router-link>
        </div>
      </section>

      <!-- Local auxiliary functions: CIF hydrogenation, space-group detection
           and structure tools, all fully local (no Fortran backend needed). -->
      <section class="module-group" id="sec-local-aux">
        <div class="group-head">
          <span class="group-eyebrow">{{ t('home.groups.localAux') }}</span>
          <h3 class="group-title">{{ t('home.groups.localAux') }}</h3>
        </div>

        <div class="group-grid">
          <router-link
            v-for="mod in localAuxModules"
            :key="mod.path"
            :to="mod.path"
            class="feature-card"
          >
            <div class="card-header">
              <span class="card-icon" v-html="mod.icon"></span>
              <h4 class="card-title">{{ mod.title }}</h4>
              <span v-if="mod.preview" class="card-preview-chip">{{ t('home.badges.preview') }}</span>
            </div>
            <p class="card-desc">{{ mod.desc }}</p>
          </router-link>
        </div>
      </section>

      <!-- Recent updates (最近更新) — a single bar; empty until filled in. -->
      <section class="home-updates" id="sec-updates">
        <div class="group-head">
          <span class="group-eyebrow">{{ t('home.updates.eyebrow') }}</span>
          <h3 class="group-title">{{ t('home.updates.title') }}</h3>
        </div>

        <div class="updates-bar">
          <template v-if="recentUpdates.length">
            <router-link
              v-for="u in recentUpdates"
              :key="u.key"
              :to="u.path"
              class="update-row"
            >
              <span class="update-badge">{{ u.version }}</span>
              <span class="update-date">{{ u.date }}</span>
              <span class="update-title">{{ u.title }}</span>
              <span class="update-desc">{{ u.desc }}</span>
              <span class="update-cta">{{ t('home.updates.viewLabel') }} →</span>
            </router-link>
          </template>
          <div v-else class="update-empty">
            {{ t('home.updates.empty') }}
          </div>
        </div>
      </section>

      <!-- About · Citation · Acknowledgments · Friendly links -->
      <section class="about-block" id="sec-about">
        <div class="group-head">
          <span class="group-eyebrow">{{ t('home.aboutEyebrow') }}</span>
          <h3 class="group-title">{{ t('home.aboutTitle') }}</h3>
        </div>
        <div class="about-panel">
          <div class="about-panel-grid">
            <p class="about-body">{{ t('home.aboutBody') }}</p>
            <div class="about-facts">
              <span class="about-chip">{{ t('app.name') }}</span>
              <span class="about-chip">{{ versionLabel }}</span>
              <span class="about-chip">Python (FastAPI) + Vue 3 + Electron</span>
            </div>
          </div>
          <div class="about-update">
            <button class="btn-check-update" type="button" :disabled="updateChecking" @click="checkUpdate">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="23 4 23 10 17 10" />
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
              </svg>
              {{ updateChecking ? t('home.aboutSection.checking') : t('home.aboutSection.checkUpdate') }}
            </button>
            <template v-if="updateMsg">
              <span class="update-msg" :class="{ ok: updateOk }">{{ updateMsg }}</span>
              <button
                v-if="updateHasNew"
                class="btn-get-update"
                type="button"
                @click="openExternal(RELEASES_URL)"
              >
                {{ t('home.aboutSection.viewRelease') }} →
              </button>
            </template>
          </div>
        </div>
      </section>

      <!-- Citation + Acknowledgments: two panels side by side on wide screens -->
      <div class="about-duo">
        <section class="about-block" id="sec-citation">
          <div class="group-head">
            <span class="group-eyebrow">{{ t('home.aboutSection.citationEyebrow') }}</span>
            <h3 class="group-title">{{ t('home.aboutSection.citationTitle') }}</h3>
          </div>
          <div class="about-panel">
            <p class="section-lead">{{ t('home.aboutSection.citationLead') }}</p>
            <div class="citation-box">
              <p class="citation-text">
                <span>{{ t('home.aboutSection.citationAuthors') }}</span>
                <span class="citation-doc-title">{{ t('home.aboutSection.citationTitleLine') }}</span>
                <span><em>{{ t('home.aboutSection.citationJournalLine') }}</em></span>
              </p>
              <p class="citation-meta">{{ t('home.aboutSection.citationMeta') }}</p>
              <div class="citation-actions">
                <button class="btn-paper" type="button" @click="openExternal(DOI_URL)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                  {{ t('home.aboutSection.viewPaper') }}
                </button>
                <button class="doi-chip" type="button" @click="openExternal(DOI_URL)">
                  {{ t('home.aboutSection.citationDoi') }}
                </button>
              </div>
            </div>
            <details class="bibtex-box">
              <summary class="bibtex-summary">
                <svg class="bibtex-caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
                <span>{{ t('home.aboutSection.bibtexLabel') }}</span>
                <button class="bibtex-copy" type="button" @click.stop.prevent="copyBibtex">
                  {{ bibtexCopied ? t('home.aboutSection.copied') : t('home.aboutSection.copyBibtex') }}
                </button>
              </summary>
              <pre class="bibtex-pre">{{ BIBTEX_ENTRY }}</pre>
            </details>
          </div>
        </section>

        <section class="about-block" id="sec-acknowledgments">
          <div class="group-head">
            <span class="group-eyebrow">{{ t('home.aboutSection.ackEyebrow') }}</span>
            <h3 class="group-title">{{ t('home.aboutSection.ackTitle') }}</h3>
          </div>
          <div class="about-panel">
            <ul class="ack-list">
              <li v-for="item in ackItems" :key="item.key">
                <span class="ack-text">{{ item.text }}</span>
                <button
                  v-if="item.url"
                  class="ack-link"
                  type="button"
                  :title="item.text"
                  @click="openExternal(item.url)"
                >
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                    <polyline points="15 3 21 3 21 9" />
                    <line x1="10" y1="14" x2="21" y2="3" />
                  </svg>
                </button>
              </li>
            </ul>
          </div>
        </section>
      </div>

      <!-- Friendly links -->
      <section class="about-block" id="sec-links">
        <div class="group-head">
          <span class="group-eyebrow">{{ t('home.aboutSection.linksEyebrow') }}</span>
          <h3 class="group-title">{{ t('home.aboutSection.linksTitle') }}</h3>
        </div>
        <div class="about-panel">
          <p class="section-lead">{{ t('home.aboutSection.linksLead') }}</p>
          <div class="links-grid">
            <article
              v-for="link in friendlyLinks"
              :key="link.key"
              class="link-card"
              :class="{ 'link-card-primary': link.primary }"
            >
              <div class="link-head">
                <span class="link-icon" v-html="link.icon"></span>
                <h4 class="link-name">{{ link.name }}</h4>
              </div>
              <p class="link-desc">{{ link.desc }}</p>
              <button class="btn-visit" type="button" @click="openExternal(link.url)">
                {{ t('home.aboutSection.visit') }}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <line x1="5" y1="12" x2="19" y2="12" />
                  <polyline points="12 5 19 12 12 19" />
                </svg>
              </button>
            </article>
          </div>
        </div>
      </section>
    </div>

    <!-- Floating quick-nav (settings-like) button, bottom-right -->
    <button
      class="fab"
      :class="{ open: navOpen }"
      :title="t('home.quickNav.title')"
      :aria-expanded="navOpen ? 'true' : 'false'"
      aria-label="Quick navigation"
      @click="toggleNav"
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    </button>

    <transition name="fab-pop">
      <div v-if="navOpen" class="fab-panel">
        <div class="fab-panel-title">{{ t('home.quickNav.title') }}</div>
        <label class="fab-toggle">
          <span class="fab-toggle-label">{{ t('home.quickNav.particles') }}</span>
          <input
            type="checkbox"
            class="fab-toggle-input"
            v-model="showParticles"
            aria-label="Particle background"
          />
          <span class="fab-toggle-track" :class="{ on: showParticles }"></span>
        </label>
        <button
          v-for="item in navItems"
          :key="item.id"
          class="fab-item"
          @click="scrollToSection(item.id)"
        >
          <span class="fab-dot"></span>
          <span>{{ item.label }}</span>
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import DiffractionBackground from '@/components/DiffractionBackground.vue'
import { getRuntimeInfo } from '@/services/runtime'

const { t } = useI18n()

// About-strip version: from the running Electron app (app.getVersion() =
// PRE/package.json) with the frontend/package.json fallback — same policy as
// the header in MainLayout, so the two can never disagree.
const appVersion = ref(__APP_VERSION__)
onMounted(async () => {
  const info = await getRuntimeInfo()
  if (info?.version) appVersion.value = info.version
})
const versionLabel = computed(() => `v${appVersion.value} · ${t('app.versionTag')}`)

const navOpen = ref(false)
// Particle/meteor background effect, toggleable from the settings FAB.
const showParticles = ref(true)

function toggleNav() {
  navOpen.value = !navOpen.value
}

function scrollToSection(id) {
  navOpen.value = false
  if (id === 'sec-hero') {
    window.scrollTo({ top: 0, behavior: 'smooth' })
    return
  }
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const heroPills = computed(() => [
  t('home.pills.integration'),
  t('home.pills.calibration'),
  t('home.pills.simulation'),
  t('home.pills.analysis')
])

// Inline SVG icons kept compact; the surrounding UI/colours are unchanged.
const ICONS = {
  integration: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="9" y1="21" x2="9" y2="9"/></svg>',
  waxs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>',
  xrd: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/></svg>',
  cif: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="8" y1="13" x2="16" y2="13"/><line x1="8" y1="17" x2="13" y2="17"/></svg>',
  analysis: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
  viewer: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
  refine: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
  lmp: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
  cifH: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="6" cy="9" r="2.2"/><circle cx="12" cy="13.5" r="2.2"/><circle cx="18" cy="9" r="2.2"/><circle cx="5" cy="17" r="1.3"/><circle cx="11.5" cy="20" r="1.3"/><circle cx="19" cy="17" r="1.3"/><line x1="7.9" y1="10.1" x2="10.1" y2="12.4"/><line x1="16.1" y1="10.1" x2="13.9" y2="12.4"/><line x1="6.2" y1="11.2" x2="5.4" y2="15.7"/><line x1="12" y1="15.7" x2="11.7" y2="18.7"/><line x1="17.8" y1="11.2" x2="18.6" y2="15.7"/></svg>',
  symmetry: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M12 2v20"/><path d="M12 12l9-5"/><path d="M12 12L3 7"/><path d="M12 12l9 5" stroke-dasharray="2 2"/><path d="M12 12l-9 5" stroke-dasharray="2 2"/></svg>',
  deviation: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 20V4"/><path d="M4 20h16"/><circle cx="8" cy="14" r="1.4"/><circle cx="13" cy="9" r="1.4"/><circle cx="17" cy="5.5" r="1.4"/><path d="M8 14l3.5-3.5"/><path d="M14.4 8.2l1.4-1.4" stroke-dasharray="2 2"/><path d="M13 9l4 5" stroke-dasharray="2 2"/></svg>',
  cp2k: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><ellipse cx="12" cy="12" rx="10" ry="4.5"/><ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(60 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(120 12 12)"/></svg>',
  giwaxs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2v20M2 12h20"/><circle cx="12" cy="12" r="3.2"/><path d="M4.9 4.9l2.2 2.2M19.1 4.9l-2.2 2.2M4.9 19.1l2.2-2.2M19.1 19.1l-2.2-2.2"/></svg>',
  qzSlice: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="8" x2="21" y2="8"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="16" x2="21" y2="16"/></svg>'
}

// Local auxiliary functions (本地辅助功能): the CIF hydrogenator and other
// structure utilities — grouped together, away from the Fortran-coupled modules.
const localAuxModules = computed(() => [
  {
    path: '/app/cif-hydrogen',
    title: t('home.modules.cifH.title'),
    desc: t('home.modules.cifH.desc'),
    icon: ICONS.cifH
  },
  {
    path: '/app/symmetry',
    title: t('home.modules.symmetry.title'),
    desc: t('home.modules.symmetry.desc'),
    icon: ICONS.symmetry
  },
  {
    path: '/app/deviation-report',
    title: t('home.modules.deviation.title'),
    desc: t('home.modules.deviation.desc'),
    icon: ICONS.deviation
  },
  {
    path: '/app/cp2k-input',
    title: t('home.modules.cp2k.title'),
    desc: t('home.modules.cp2k.desc'),
    icon: ICONS.cp2k
  }
])

// Modules grouped into sections. Every section renders through the same
// 4-column grid (see .group-grid), so card size is uniform page-wide.
const moduleGroups = computed(() => [
  {
    id: 'integration2d',
    eyebrow: t('home.groups.integration2d'),
    title: t('home.groups.integration2d'),
    modules: [
      { path: '/app/2d-integration', title: t('home.modules.integration.title'), desc: t('home.modules.integration.desc'), icon: ICONS.integration },
      { path: '/app/integration-merge', title: t('home.modules.waxs.title'), desc: t('home.modules.waxs.desc'), icon: ICONS.waxs },
      { path: '/app/viewer', title: t('home.modules.viewer.title'), desc: t('home.modules.viewer.desc'), icon: ICONS.viewer }
    ]
  },
  {
    id: 'extraction',
    eyebrow: t('home.groups.extraction'),
    title: t('home.groups.extraction'),
    modules: [
      { path: '/app/image-analysis', title: t('home.modules.analysis.title'), desc: t('home.modules.analysis.desc'), icon: ICONS.analysis }
    ]
  },
  {
    id: 'simulation',
    eyebrow: t('home.groups.simulation'),
    title: t('home.groups.simulation'),
    modules: [
      { path: '/app/cif-parser', title: t('home.modules.cif.title'), desc: t('home.modules.cif.desc'), icon: ICONS.cif },
      { path: '/app/xrd-simulator', title: t('home.modules.xrd.title'), desc: t('home.modules.xrd.desc'), icon: ICONS.xrd }
    ]
  },
  {
    id: 'refinement',
    eyebrow: t('home.groups.refinement'),
    title: t('home.groups.refinement'),
    modules: [
      { path: '/app/lmp-extractor', title: t('home.modules.lmpExtractor.title'), desc: t('home.modules.lmpExtractor.desc'), icon: ICONS.lmp },
      { path: '/app/input-generator', title: t('home.modules.inputGen.title'), desc: t('home.modules.inputGen.desc'), icon: ICONS.refine }
    ]
  },
  {
    // 纤维积分处理方向：GIWAXS 合并 → qz 条带积分
    // （轻量前处理路径，预览版；置于末栏）
    id: 'fiberIntegration',
    eyebrow: t('home.groups.fiberIntegration'),
    title: t('home.groups.fiberIntegration'),
    modules: [
      { path: '/app/giwaxs-merge', title: t('home.modules.giwaxs.title'), desc: t('home.modules.giwaxs.desc'), icon: ICONS.giwaxs, preview: true },
      { path: '/app/qz-slice', title: t('home.modules.qzSlice.title'), desc: t('home.modules.qzSlice.desc'), icon: ICONS.qzSlice, preview: true }
    ]
  }
])

// Recent updates (最近更新) — single-bar feed. Entry shape:
//   { key:'v120', path:'/app/home', version:'v1.2.0', date:'2026-10-10',
//     title: t('home.updates.items.v120.title'), desc: t('home.updates.items.v120.desc') }
const recentUpdates = computed(() => [
  {
    key: 'v120',
    path: '/app/home',
    version: 'v1.2.0',
    date: '2026-10-10',
    title: t('home.updates.items.v120.title'),
    desc: t('home.updates.items.v120.desc')
  }
])

// ---- Horizontal workflow rail (three stages, hover-expand steps) ----
// ---- Vertical workflow rail in the hero (three stages; hover pops the
// sub-step chips out to the LEFT, each chip routes to its module page). ----
const FLOW_ICONS = {
  prep: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.6"/><circle cx="15.5" cy="15" r="1.6"/><path d="M3 15l5-4 4 3 3-2 6 5"/></svg>',
  refine: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 3h6M10 3v5.5L4.8 18a2.4 2.4 0 0 0 2.1 3.6h10.2a2.4 2.4 0 0 0 2.1-3.6L14 8.5V3"/><path d="M7.5 15h9"/></svg>',
  post: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2l9 5v10l-9 5-9-5V7z"/><path d="M12 2v20"/><path d="M12 12l9-5"/><path d="M12 12L3 7"/></svg>'
}

const workflowStages = computed(() => [
  {
    id: 'prep',
    anchor: 'sec-integration2d',
    icon: FLOW_ICONS.prep,
    title: t('home.workflow.s1.title'),
    lead: t('home.workflow.s1.lead'),
    steps: [
      { label: t('home.workflow.s1.step1'), to: '/app/2d-integration' },
      { label: t('home.workflow.s1.step2'), to: '/app/integration-merge' },
      { label: t('home.workflow.s1.step3'), to: '/app/image-analysis' }
    ]
  },
  {
    id: 'refine',
    anchor: 'sec-refinement',
    icon: FLOW_ICONS.refine,
    title: t('home.workflow.s2.title'),
    lead: t('home.workflow.s2.lead'),
    steps: [
      { label: t('home.workflow.s2.step1'), to: '/app/image-analysis' },
      { label: t('home.workflow.s2.step2'), to: '/app/lmp-extractor' },
      { label: t('home.workflow.s2.step3'), to: '/app/input-generator' }
    ]
  },
  {
    id: 'post',
    anchor: 'sec-local-aux',
    icon: FLOW_ICONS.post,
    title: t('home.workflow.s3.title'),
    lead: t('home.workflow.s3.lead'),
    steps: [
      { label: t('home.workflow.s3.step1'), to: '/app/cp2k-input' },
      { label: t('home.workflow.s3.step2'), to: '/app/symmetry' },
      { label: t('home.workflow.s3.step3'), to: '/app/xrd-simulator' }
    ]
  }
])

// ---- External links (citation / acknowledgments / friendly links) ----
// Same pattern as LmpExtractorPage.openExternalLink: under Electron,
// target=_blank is suppressed by contextIsolation, so route the URL through
// the preload bridge; in a plain browser just window.open.
const DOI_URL = 'https://doi.org/10.1107/S1600576726008290'
const PYFAI_DOCS_URL = 'https://pyfai.readthedocs.io/en/stable/pyFAI.html'
const RELEASES_URL = 'https://github.com/ICCAS-EPlab-PMP/PolymCrystRefine/releases/latest'

function openExternal(url) {
  if (window.electronAPI?.openExternal) {
    window.electronAPI.openExternal(url)
  } else {
    window.open(url, '_blank', 'noopener,noreferrer')
  }
}

// ---- Check for updates (About panel) ----
// Under Electron the main process queries the GitHub API (https, host
// allow-listed there); in a plain browser we simply open the releases page.
const updateChecking = ref(false)
const updateMsg = ref('')
const updateOk = ref(false)
const updateHasNew = ref(false)

async function checkUpdate() {
  if (!window.electronAPI?.checkUpdate) {
    openExternal(RELEASES_URL)
    return
  }
  updateChecking.value = true
  updateMsg.value = ''
  updateHasNew.value = false
  try {
    const r = await window.electronAPI.checkUpdate()
    if (r.ok && r.hasUpdate) {
      updateMsg.value = t('home.aboutSection.newVersion', { version: r.latest })
      updateOk.value = true
      updateHasNew.value = true
    } else if (r.ok) {
      updateMsg.value = t('home.aboutSection.upToDate', { version: r.current })
      updateOk.value = true
    } else {
      updateMsg.value = t('home.aboutSection.fetchFailed')
      updateOk.value = false
    }
  } catch {
    updateMsg.value = t('home.aboutSection.fetchFailed')
    updateOk.value = false
  } finally {
    updateChecking.value = false
  }
}

// BibTeX entry — language-independent citation data, kept out of i18n on
// purpose: vue-i18n would interpret the braces `{...}` as interpolation.
const BIBTEX_ENTRY = `@article{Ma2026PolymCrystRefine,
  author    = {Ma, Tianyi and Liu, Guoming and Wang, Dujin},
  title     = {{PolymCrystRefine}: a workflow for diffraction analysis of polymer crystals},
  journal   = {Journal of Applied Crystallography},
  volume    = {59},
  number    = {5},
  year      = {2026},
  pages     = {1630--1644},
  publisher = {International Union of Crystallography},
  doi       = {10.1107/s1600576726008290},
  url       = {https://doi.org/10.1107/S1600576726008290}
}`

const bibtexCopied = ref(false)
let bibtexCopiedTimer = null

async function copyBibtex() {
  try {
    await navigator.clipboard.writeText(BIBTEX_ENTRY)
  } catch {
    // Fallback for contexts without the async clipboard API.
    const ta = document.createElement('textarea')
    ta.value = BIBTEX_ENTRY
    ta.setAttribute('readonly', '')
    ta.style.position = 'fixed'
    ta.style.opacity = '0'
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
    } catch {
      /* clipboard unavailable — nothing else we can do */
    }
    document.body.removeChild(ta)
  }
  bibtexCopied.value = true
  clearTimeout(bibtexCopiedTimer)
  bibtexCopiedTimer = setTimeout(() => {
    bibtexCopied.value = false
  }, 2000)
}

const ackItems = computed(() => [
  { key: 'ack1', text: t('home.aboutSection.ack1') },
  { key: 'ack2', text: t('home.aboutSection.ack2') },
  { key: 'ack3', text: t('home.aboutSection.ack3') },
  { key: 'ack4', text: t('home.aboutSection.ack4') },
  { key: 'ack5', text: t('home.aboutSection.ack5') },
  { key: 'ack6', text: t('home.aboutSection.ack6'), url: PYFAI_DOCS_URL }
])

// Compact inline SVG logos for the friendly-link cards.
const LINK_ICONS = {
  polymcrystal: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2l8.66 5v10L12 22l-8.66-5V7z"/><path d="M12 22V12"/><path d="M12 12l8.66-5"/><path d="M12 12L3.34 7"/></svg>',
  iccas: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 21h18"/><path d="M5 21V10"/><path d="M19 21V10"/><path d="M5 10l7-6 7 6"/><path d="M9.5 21v-6h5v6"/></svg>',
  eplab: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M10 2v6L4.6 18a2 2 0 0 0 1.8 3h11.2a2 2 0 0 0 1.8-3L14 8V2"/><path d="M8.5 2h7"/><path d="M7.2 15h9.6"/></svg>',
  pmp: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="6" cy="6" r="2.4"/><circle cx="18" cy="6" r="2.4"/><circle cx="12" cy="18" r="2.4"/><path d="M7.9 7.8l3 7.6"/><path d="M16.1 7.8l-3 7.6"/><path d="M8.4 6h7.2"/></svg>',
  polymcrystalindex: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 9v12"/><path d="M15 9v5"/><path d="M15 14h6"/></svg>',
  xfais: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 20c3 0 3-14 6-14s3 14 6 14 3-9 6-9"/><path d="M3 20h18" stroke-dasharray="3 2"/></svg>'
}

// Friendly-link cards: name + one-liner + a Visit button (per-link i18n).
const friendlyLinks = computed(() => [
  {
    key: 'polymcrystal',
    name: t('home.aboutSection.linkNames.polymcrystal'),
    desc: t('home.aboutSection.linkDescs.polymcrystal'),
    url: 'http://www.polymcrystal.com/',
    icon: LINK_ICONS.polymcrystal,
    primary: true
  },
  {
    key: 'polymcrystalindex',
    name: t('home.aboutSection.linkNames.polymcrystalindex'),
    desc: t('home.aboutSection.linkDescs.polymcrystalindex'),
    url: 'https://github.com/ICCAS-EPlab-PMP/PolymCrystIndex',
    icon: LINK_ICONS.polymcrystalindex
  },
  {
    key: 'xfais',
    name: t('home.aboutSection.linkNames.xfais'),
    desc: t('home.aboutSection.linkDescs.xfais'),
    url: 'https://github.com/ICCAS-EPlab-PMP/XFAIS',
    icon: LINK_ICONS.xfais
  },
  {
    key: 'iccas',
    name: t('home.aboutSection.linkNames.iccas'),
    desc: t('home.aboutSection.linkDescs.iccas'),
    url: 'https://www.iccas.ac.cn/',
    icon: LINK_ICONS.iccas
  },
  {
    key: 'eplab',
    name: t('home.aboutSection.linkNames.eplab'),
    desc: t('home.aboutSection.linkDescs.eplab'),
    url: 'http://eplab.iccas.ac.cn/',
    icon: LINK_ICONS.eplab
  },
  {
    key: 'pmp',
    name: t('home.aboutSection.linkNames.pmp'),
    desc: t('home.aboutSection.linkDescs.pmp'),
    url: 'http://pmp.iccas.ac.cn/',
    icon: LINK_ICONS.pmp
  }
])

// Quick-nav list: top, workflow rail, each module group, local aux, updates,
// then the about / citation / acknowledgments / friendly-links sections.
const navItems = computed(() => {
  const items = [{ id: 'sec-hero', label: t('home.quickNav.backToTop') }]
  items.push({ id: 'sec-workflow', label: t('home.workflow.title') })
  for (const g of moduleGroups.value) {
    items.push({ id: `sec-${g.id}`, label: g.title })
  }
  items.push({ id: 'sec-local-aux', label: t('home.groups.localAux') })
  items.push({ id: 'sec-updates', label: t('home.quickNav.updates') })
  items.push({ id: 'sec-about', label: t('home.quickNav.about') })
  items.push({ id: 'sec-citation', label: t('home.quickNav.citation') })
  items.push({ id: 'sec-acknowledgments', label: t('home.quickNav.acknowledgments') })
  items.push({ id: 'sec-links', label: t('home.quickNav.friendlyLinks') })
  return items
})
</script>

<style scoped>
.home-page {
  position: relative;
}

.home-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 32px;
  padding: 8px 0 0;
  animation: fadeInUp 0.5s ease-out;
}

/* ---- Hero panel (frosted glass; copy left, vertical workflow right) ---- */
.hero-panel {
  position: relative;
  overflow: hidden;
  padding: 30px 32px 34px;
  border-radius: 24px;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.98) 0%, rgba(237, 233, 254, 0.9) 100%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 20px 45px rgba(124, 58, 237, 0.10);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
  gap: 30px;
  align-items: center;
}

.hero-panel::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  z-index: 0;
  pointer-events: none;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.85) 0%,
    rgba(255, 255, 255, 0.15) 45%,
    rgba(124, 58, 237, 0.05) 100%
  );
}

.hero-copy {
  position: relative;
  z-index: 1;
}

.hero-kicker {
  margin-bottom: 14px;
  font-size: 0.82rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--primary);
}

.hero-title {
  margin: 0 0 16px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  /* generous line-height so the gradient-clipped title never gets cut off */
  line-height: 1.16;
}

.hero-title-brand {
  display: inline-block;
  font-size: clamp(2.2rem, 4.5vw, 3.8rem);
  font-weight: 800;
  letter-spacing: -0.04em;
  line-height: 1.2;
  /* extra bottom space so descenders (e.g. the "y" in PolymCrystRefine) render
     fully and are not obscured by the subtitle below */
  padding-bottom: 0.12em;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-title-sub {
  font-size: clamp(1rem, 1.8vw, 1.35rem);
  font-weight: 500;
  letter-spacing: 0.01em;
  color: var(--text-secondary);
}

.hero-pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 12px;
}

.hero-pill {
  display: inline-flex;
  align-items: center;
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(241, 245, 249, 0.8);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

/* ---- Vertical workflow rail (hero right column) ----
   Tree layout: [branch chips] | rail | node. The rail is one continuous
   dashed line; hovering a stage pops its chips out to the LEFT with a
   staggered slide-in; chips route to module pages, nodes scroll to the
   modules grid. */
.hero-flow {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.hero-flow-head {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-left: 24px;
}

.hero-flow-eyebrow {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--primary);
}

.hero-flow-title {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-primary);
}

.vflow {
  display: flex;
  flex-direction: column;
  /* branch column | rail column | node column (fixed widths so the rail
     line below can sit at a constant x-offset) */
}

.vflow-stage {
  display: grid;
  grid-template-columns: 148px 22px minmax(0, 1fr);
  align-items: center;
}

/* The rail: one continuous dashed vertical line through all stages. */
.vflow::before {
  content: '';
  position: absolute;
  left: 158px;
  top: 14px;
  bottom: 14px;
  width: 0;
  border-left: 2px dashed rgba(167, 139, 250, 0.55);
  pointer-events: none;
}

.vflow {
  position: relative;
}

.vflow-rail {
  position: relative;
  z-index: 1;
  height: 100%;
  min-height: 46px;
}

/* Dot on the rail at each stage. */
.vflow-rail::before {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #fff;
  border: 3px solid var(--primary);
  box-shadow: 0 0 0 4px rgba(124, 58, 237, 0.12);
}

/* Branch chips: hidden (translated right, transparent) until the stage is
   hovered/focused; each chip slides out with its own stagger delay. */
.vflow-branch {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 5px;
  padding-right: 10px;
}

.vflow-chip {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(196, 181, 253, 0.9);
  background: rgba(245, 243, 255, 0.95);
  color: var(--primary-dark);
  font-size: 0.72rem;
  font-weight: 600;
  white-space: nowrap;
  text-decoration: none;
  opacity: 0;
  transform: translateX(16px);
  pointer-events: none;
  transition: opacity 0.22s ease, transform 0.26s cubic-bezier(0.2, 0.9, 0.3, 1.2), background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.vflow-stage:hover .vflow-chip,
.vflow-stage:focus-within .vflow-chip {
  opacity: 1;
  transform: translateX(0);
  pointer-events: auto;
}

.vflow-chip:hover {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

/* Node: the clickable stage card on the right of the rail. */
.vflow-node {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 5px 0;
  padding: 9px 12px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.85);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.98) 0%, rgba(237, 233, 254, 0.92) 100%);
  box-shadow: 0 6px 18px rgba(124, 58, 237, 0.08);
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.vflow-node:hover {
  transform: translateX(3px);
  border-color: var(--primary);
  box-shadow: 0 10px 26px rgba(124, 58, 237, 0.16);
}

.flow-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 800;
}

.vflow-labels {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.vflow-name {
  font-size: 0.86rem;
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vflow-lead {
  font-size: 0.68rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vflow-go {
  margin-left: auto;
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  color: var(--primary);
  opacity: 0;
  transform: translateX(-4px);
  transition: opacity 0.2s ease, transform 0.2s ease;
}

.vflow-node:hover .vflow-go {
  opacity: 0.85;
  transform: translateX(0);
}

/* ---- Check-update row (About panel) ---- */
.about-update {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px dashed var(--border);
}

.btn-check-update {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  border-radius: 999px;
  border: 1px solid var(--primary);
  background: rgba(245, 243, 255, 0.9);
  color: var(--primary);
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.btn-check-update svg {
  width: 14px;
  height: 14px;
}

.btn-check-update:hover:not(:disabled) {
  background: var(--primary);
  color: #fff;
  transform: translateY(-1px);
}

.btn-check-update:disabled {
  opacity: 0.6;
  cursor: wait;
}

.update-msg {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.update-msg.ok {
  color: var(--color-success, #10B981);
  font-weight: 600;
}

.btn-get-update {
  padding: 6px 12px;
  border-radius: 999px;
  border: none;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.btn-get-update:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(124, 58, 237, 0.25);
}

/* ---- Module groups ---- */
.module-group {
  display: flex;
  flex-direction: column;
  gap: 16px;
  scroll-margin-top: 96px;
}

.group-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  padding: 0 2px;
}

.group-eyebrow {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: var(--primary-bg);
  color: var(--primary);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.group-title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--text-primary);
}

/* ---- Module groups: every section shares the SAME 4-column grid so all
   cards are identical in size across the whole page (a group with fewer
   modules simply leaves trailing slots empty). ---- */
.group-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

/* ---- Feature card (frosted glass) ---- */
.feature-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  /* Fixed height keeps every card equal in size. */
  height: 186px;
  padding: 18px;
  border-radius: var(--radius-lg, 14px);
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.98) 0%, rgba(237, 233, 254, 0.9) 100%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 10px 30px rgba(124, 58, 237, 0.08);
  color: var(--text-primary);
  text-decoration: none;
  overflow: hidden;
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
}

/* Frosted sheen overlay — makes the glass readable even on a pure-white
   backdrop (blur alone is invisible over white). */
.feature-card::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  z-index: 0;
  pointer-events: none;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.85) 0%,
    rgba(255, 255, 255, 0.15) 45%,
    rgba(124, 58, 237, 0.06) 100%
  );
}

.feature-card > * {
  position: relative;
  z-index: 1;
}

/* Top accent bar reveals on hover — keeps the surface colour unchanged. */
.feature-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--primary), var(--primary-light));
  opacity: 0;
  z-index: 2;
  transition: opacity 0.25s ease;
}

.feature-card:hover {
  transform: translateY(-4px);
  border-color: var(--primary);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 18px 40px rgba(124, 58, 237, 0.16);
}

.feature-card:hover::before {
  opacity: 1;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 11px;
  background: var(--primary-bg);
  color: var(--primary);
  transition: transform 0.22s ease;
}

.feature-card:hover .card-icon {
  transform: scale(1.06);
}

.card-icon :deep(svg) {
  width: 21px;
  height: 21px;
}

.card-title {
  margin: 0;
  font-size: 0.94rem;
  font-weight: 700;
  line-height: 1.3;
  color: var(--text-primary);
}

/* Preview badge (preview badge) for modules still under active validation. */
.card-preview-chip {
  flex-shrink: 0;
  padding: 2px 6px;
  border-radius: 999px;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: #92400e;
  background: rgba(245, 158, 11, 0.14);
  border: 1px solid rgba(245, 158, 11, 0.45);
  white-space: nowrap;
}

.card-desc {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.55;
  color: var(--text-secondary);
  /* Clamp to a fixed number of lines so cards stay equal in height. */
  display: -webkit-box;
  -webkit-line-clamp: 4;
  line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ---- Recent updates (single bar) ---- */
.home-updates {
  display: flex;
  flex-direction: column;
  gap: 16px;
  scroll-margin-top: 96px;
}

.updates-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 22px 24px;
  border-radius: 24px;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.98) 0%, rgba(237, 233, 254, 0.9) 100%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow: 0 10px 30px rgba(124, 58, 237, 0.08);
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
}

.update-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.7);
  border: 1px solid rgba(226, 232, 240, 0.7);
  color: var(--text-primary);
  text-decoration: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
}

.update-row:hover {
  border-color: var(--primary);
  background: rgba(248, 250, 252, 0.95);
  box-shadow: 0 8px 20px rgba(124, 58, 237, 0.12);
}

.update-badge {
  flex-shrink: 0;
  padding: 3px 9px;
  border-radius: 999px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  color: #fff;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.update-date {
  flex-shrink: 0;
  font-size: 0.72rem;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.update-title {
  flex-shrink: 0;
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-primary);
}

.update-desc {
  min-width: 0;
  font-size: 0.8rem;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.update-cta {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--primary);
}

.update-empty {
  padding: 26px 8px;
  text-align: center;
  font-size: 0.9rem;
  color: var(--text-muted);
  border: 1px dashed var(--border);
  border-radius: 14px;
}

/* ---- About · Citation · Acknowledgments · Friendly links ---- */
.about-block {
  display: flex;
  flex-direction: column;
  gap: 16px;
  scroll-margin-top: 96px;
}

/* Citation + Acknowledgments sit side by side on wide screens. */
.about-duo {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: 32px;
  align-items: stretch;
}

.about-duo .about-panel {
  flex: 1;
}

/* Frosted-glass panel shared by all four about-area sections. */
.about-panel {
  position: relative;
  padding: 24px 26px;
  border-radius: 24px;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.98) 0%, rgba(237, 233, 254, 0.9) 100%);
  border: 1px solid rgba(255, 255, 255, 0.8);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.9),
    0 20px 45px rgba(124, 58, 237, 0.10);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
}

.about-panel::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  z-index: 0;
  pointer-events: none;
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.85) 0%,
    rgba(255, 255, 255, 0.15) 45%,
    rgba(124, 58, 237, 0.05) 100%
  );
}

.about-panel > * {
  position: relative;
  z-index: 1;
}

/* About intro: body text left, app facts stacked right. */
.about-panel-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 300px);
  gap: 24px;
  align-items: center;
}

.about-body {
  margin: 0;
  font-size: 0.92rem;
  color: var(--text-secondary);
  line-height: 1.7;
}

.about-facts {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.about-chip {
  padding: 7px 12px;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.8);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 0.78rem;
  font-weight: 500;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.section-lead {
  margin: 0 0 14px;
  font-size: 0.85rem;
  color: var(--text-muted);
  line-height: 1.6;
}

/* ---- Citation ---- */
.citation-box {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 20px;
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.75);
  border: 1px solid var(--border);
}

.citation-text {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--text-secondary);
}

.citation-doc-title {
  font-weight: 600;
  color: var(--text-primary);
}

.citation-meta {
  margin: 0;
  font-size: 0.78rem;
  line-height: 1.6;
  color: var(--text-muted);
}

.citation-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.btn-paper {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 16px;
  border: none;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
  color: #fff;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.btn-paper:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px rgba(124, 58, 237, 0.28);
}

.btn-paper svg {
  width: 15px;
  height: 15px;
}

.doi-chip {
  padding: 9px 14px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: rgba(248, 250, 252, 0.85);
  color: var(--primary);
  font-size: 0.78rem;
  font-weight: 600;
  font-family: var(--font-mono);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.doi-chip:hover {
  border-color: var(--primary);
  background: var(--primary-bg);
}

/* BibTeX collapsible */
.bibtex-box {
  margin-top: 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.6);
  overflow: hidden;
}

.bibtex-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  cursor: pointer;
  list-style: none;
  user-select: none;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--text-secondary);
}

.bibtex-summary::-webkit-details-marker {
  display: none;
}

.bibtex-caret {
  flex-shrink: 0;
  width: 15px;
  height: 15px;
  color: var(--primary);
  transition: transform 0.18s ease;
}

.bibtex-box[open] .bibtex-caret {
  transform: rotate(180deg);
}

.bibtex-summary span {
  flex: 1;
}

.bibtex-copy {
  flex-shrink: 0;
  padding: 6px 12px;
  border-radius: 9px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.9);
  color: var(--primary);
  font-size: 0.74rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.bibtex-copy:hover {
  border-color: var(--primary);
  background: var(--primary-bg);
}

.bibtex-pre {
  margin: 0;
  padding: 14px 16px;
  border-top: 1px solid var(--border);
  font-family: var(--font-mono);
  font-size: 0.74rem;
  line-height: 1.6;
  color: var(--text-secondary);
  overflow-x: auto;
  white-space: pre;
}

/* ---- Acknowledgments ---- */
.ack-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ack-list li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.75);
  border: 1px solid rgba(226, 232, 240, 0.7);
  font-size: 0.86rem;
  line-height: 1.55;
  color: var(--text-secondary);
}

.ack-list li::before {
  content: '✓';
  flex-shrink: 0;
  font-weight: 700;
  color: var(--primary);
  opacity: 0.8;
}

.ack-text {
  flex: 1;
  min-width: 0;
}

.ack-link {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.9);
  color: var(--primary);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.ack-link:hover {
  border-color: var(--primary);
  background: var(--primary-bg);
}

.ack-link svg {
  width: 13px;
  height: 13px;
}

/* ---- Friendly links ---- */
.links-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 14px;
}

.link-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 18px;
  border-radius: 16px;
  background: rgba(248, 250, 252, 0.75);
  border: 1px solid rgba(226, 232, 240, 0.8);
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
}

.link-card:hover {
  transform: translateY(-3px);
  border-color: var(--primary);
  box-shadow: 0 14px 30px rgba(124, 58, 237, 0.14);
}

.link-card-primary {
  background: linear-gradient(150deg, rgba(255, 255, 255, 0.95) 0%, rgba(238, 241, 254, 0.95) 100%);
  border-color: rgba(124, 58, 237, 0.35);
}

.link-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.link-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  flex-shrink: 0;
  border-radius: 11px;
  background: var(--primary-bg);
  color: var(--primary);
}

.link-icon :deep(svg) {
  width: 19px;
  height: 19px;
}

.link-name {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.35;
  color: var(--text-primary);
}

.link-desc {
  margin: 0;
  flex: 1;
  font-size: 0.78rem;
  line-height: 1.55;
  color: var(--text-muted);
}

.btn-visit {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  align-self: flex-start;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.9);
  color: var(--primary);
  font-size: 0.76rem;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.btn-visit:hover {
  border-color: var(--primary);
  background: var(--primary-bg);
}

.btn-visit svg {
  width: 13px;
  height: 13px;
}

/* ---- Floating quick-nav (settings-like) FAB ---- */
.fab {
  position: fixed;
  right: 28px;
  bottom: 28px;
  z-index: 400;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 58px;
  height: 58px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.7);
  box-shadow: 0 12px 30px rgba(124, 58, 237, 0.22);
  color: var(--primary);
  cursor: pointer;
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  transition: transform 0.22s ease, box-shadow 0.22s ease, color 0.22s ease, background 0.22s ease;
}

.fab svg {
  width: 24px;
  height: 24px;
}

.fab:hover {
  transform: translateY(-2px);
  box-shadow: 0 16px 36px rgba(124, 58, 237, 0.3);
  color: var(--primary-dark);
}

.fab.open {
  color: #fff;
  background: linear-gradient(135deg, var(--primary) 0%, var(--primary-light) 100%);
}

.fab.open svg {
  transform: rotate(90deg);
}

.fab-panel {
  position: fixed;
  right: 28px;
  bottom: 96px;
  z-index: 400;
  width: 240px;
  padding: 12px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(226, 232, 240, 0.9);
  box-shadow: 0 24px 60px rgba(124, 58, 237, 0.2);
  backdrop-filter: blur(18px) saturate(160%);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.fab-panel-title {
  padding: 6px 12px 10px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border);
  margin-bottom: 4px;
}

.fab-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.86rem;
  font-weight: 500;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.fab-item:hover {
  background: var(--primary-bg);
  color: var(--primary);
}

.fab-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--primary);
  opacity: 0.7;
}

/* Particle-background toggle inside the settings panel */
.fab-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 9px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s ease;
}

.fab-toggle:hover {
  background: var(--primary-bg);
}

.fab-toggle-label {
  font-size: 0.86rem;
  font-weight: 500;
  color: var(--text-primary);
}

.fab-toggle-input {
  position: absolute;
  opacity: 0;
  pointer-events: none;
}

.fab-toggle-track {
  position: relative;
  flex-shrink: 0;
  width: 38px;
  height: 22px;
  border-radius: 999px;
  background: var(--border);
  transition: background 0.18s ease;
}

.fab-toggle-track::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 3px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  transition: transform 0.18s ease;
}

.fab-toggle-track.on {
  background: var(--primary);
}

.fab-toggle-track.on::after {
  transform: translateX(16px);
}

/* FAB panel enter/leave */
.fab-pop-enter-active,
.fab-pop-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.fab-pop-enter-from,
.fab-pop-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (max-width: 1280px) {
  /* Narrower windows: 4 → 3 shared columns (cards stay uniform page-wide). */
  .group-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1024px) {
  /* Hero stacks: title on top, vertical workflow below. */
  .hero-panel {
    grid-template-columns: 1fr;
  }
  .hero-flow {
    max-width: 460px;
  }
  .group-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  /* Citation + Acknowledgments stack; links keep 3 columns. */
  .about-duo {
    grid-template-columns: 1fr;
    gap: 32px;
  }
  .about-panel-grid {
    grid-template-columns: 1fr;
  }
  .about-facts {
    flex-direction: row;
    flex-wrap: wrap;
  }
  .links-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 768px) {
  .hero-panel,
  .about-panel {
    padding: 22px;
  }
  .home-content {
    gap: 22px;
  }
  .about-duo {
    gap: 22px;
  }
  .group-grid {
    grid-template-columns: 1fr;
  }
  .feature-card {
    height: auto;
    min-height: 160px;
  }
  .links-grid {
    grid-template-columns: 1fr;
  }
  .update-row {
    flex-wrap: wrap;
  }
  /* Touch has no hover — keep the workflow branch chips permanently visible. */
  .vflow-chip {
    opacity: 1;
    transform: translateX(0);
    pointer-events: auto;
  }
  .fab {
    right: 18px;
    bottom: 18px;
  }
  .fab-panel {
    right: 18px;
    bottom: 86px;
  }
}
</style>
