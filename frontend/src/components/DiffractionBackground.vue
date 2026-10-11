<template>
  <!-- Low-CPU, pointer-events: none backdrop. A very light blue→white gradient
       with fast, thin, horizontal light-purple meteors that deflect at an angle
       when the pointer passes near them. No rings / no diagonal lines. -->
  <canvas ref="canvas" class="diffraction-backdrop" aria-hidden="true"></canvas>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

const props = defineProps({
  // Toggle the meteor particles. Controlled by the settings FAB.
  particles: { type: Boolean, default: true }
})

const canvas = ref(null)

let ctx = null
let dpr = 1
let w = 0
let h = 0
let raf = null
let running = false

// Pointer position (meteors deflect away from it).
let tx = 0
let ty = 0

// Meteor particle system.
let particlesList = []
const PARTICLE_COUNT = 120
const MOUSE_RADIUS = 150
const PUSH = 3.0      // radial nudge of position
const DEFLECT = 5.0   // vertical velocity kick → diagonal "fly out" on disturbance
const VY_LIMIT = 6.0  // keeps the deflected angle bounded

const TAU = Math.PI * 2

function setupSize() {
  const el = canvas.value
  if (!el) return
  ctx = ctx || el.getContext('2d')
  if (!ctx) return
  dpr = Math.min(window.devicePixelRatio || 1, 1.5)
  w = window.innerWidth
  h = window.innerHeight
  el.width = Math.round(w * dpr)
  el.height = Math.round(h * dpr)
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  tx = tx || w / 2
  ty = ty || h / 2
}

function initParticles() {
  particlesList = []
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    // All meteors fly left → right (vx is always positive).
    particlesList.push({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: Math.random() * 6 + 6, // 6..12 px/frame
      vy: 0,
      // Thin light-purple meteors with a short tail.
      size: Math.random() * 0.9 + 0.8,
      alpha: Math.random() * 0.35 + 0.6,
      tail: Math.random() * 3 + 2
    })
  }
}

// Fast, thin horizontal meteors: a bright little head plus a short fading tail.
function drawParticles() {
  if (!props.particles) return
  ctx.lineCap = 'round'
  for (const p of particlesList) {
    ctx.lineWidth = Math.max(0.6, p.size * 0.6)
    ctx.strokeStyle = `rgba(167,139,250,${(p.alpha * 0.55).toFixed(3)})`
    ctx.beginPath()
    ctx.moveTo(p.x - p.vx * p.tail, p.y - p.vy * p.tail)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.size * 0.7, 0, TAU)
    ctx.fillStyle = `rgba(196,181,253,${p.alpha.toFixed(3)})`
    ctx.fill()
  }
}

function updateParticles() {
  if (!props.particles) return
  for (const p of particlesList) {
    p.x += p.vx
    p.y += p.vy
    // Pointer disturbance: nudge away from the cursor and kick a diagonal. The
    // deflected angle is KEPT (no easing back) while the meteor is alive.
    const dx = p.x - tx
    const dy = p.y - ty
    const dist = Math.hypot(dx, dy)
    if (dist < MOUSE_RADIUS && dist > 0.001) {
      const f = (MOUSE_RADIUS - dist) / MOUSE_RADIUS
      const ux = dx / dist
      const uy = dy / dist
      p.x += ux * f * PUSH
      p.y += uy * f * PUSH
      p.vy += uy * f * DEFLECT
    }
    // Keep the angled flight but clamp it so it doesn't run away mid-crossing.
    if (p.vy > VY_LIMIT) p.vy = VY_LIMIT
    else if (p.vy < -VY_LIMIT) p.vy = -VY_LIMIT
    // Terminate when it exits any edge (i.e. reaches the right), then spawn a
    // fresh HORIZONTAL meteor from the LEFT. This bounds any deflection to a
    // single left→right pass, so disturbed particles never scatter everywhere.
    if (p.x > w + 40 || p.x < -40 || p.y < -40 || p.y > h + 40) {
      p.x = -40
      p.y = Math.random() * h
      p.vx = Math.random() * 6 + 6
      p.vy = 0
    }
  }
}

// A single faint glow at the pointer (not rings) for a soft follow effect.
function drawGlow() {
  const r = 150
  const g = ctx.createRadialGradient(tx, ty, 0, tx, ty, r)
  g.addColorStop(0, 'rgba(124,58,237,0.055)')
  g.addColorStop(1, 'rgba(124,58,237,0)')
  ctx.fillStyle = g
  ctx.fillRect(tx - r, ty - r, r * 2, r * 2)
}

function draw() {
  // Transparent canvas — the page body supplies the shared light-blue→white
  // gradient backdrop, so the homepage and every module page look identical.
  ctx.clearRect(0, 0, w, h)
  drawGlow()
  drawParticles()
}

function frame() {
  updateParticles()
  draw()
  // Keep animating while particles are on; otherwise stop (idle → ~0 CPU).
  if (props.particles) {
    raf = requestAnimationFrame(frame)
  } else {
    running = false
    raf = null
  }
}

function start() {
  if (!running) {
    running = true
    raf = requestAnimationFrame(frame)
  }
}

function onMove(e) {
  tx = e.clientX
  ty = e.clientY
}

function onResize() {
  setupSize()
  initParticles()
  draw()
}

// When particles are toggled ON from the settings FAB, resume the loop.
watch(() => props.particles, (val) => {
  if (val) start()
})

onMounted(() => {
  setupSize()
  initParticles()
  draw()

  window.addEventListener('resize', onResize, { passive: true })
  window.addEventListener('mousemove', onMove, { passive: true })
  start()
})

onBeforeUnmount(() => {
  if (raf) cancelAnimationFrame(raf)
  raf = null
  window.removeEventListener('resize', onResize)
  window.removeEventListener('mousemove', onMove)
})
</script>

<style scoped>
.diffraction-backdrop {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  z-index: 0;
  pointer-events: none;
}
</style>
