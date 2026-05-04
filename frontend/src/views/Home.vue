<template>
  <div class="home-container">
    <!-- Top Navigation Bar -->
    <nav class="navbar" :style="s.navbar">
      <div class="nav-brand" :style="s.navBrand">DEEPSEARCH MIROFISH</div>
      <div class="nav-links" :style="s.navLinks">
        <a href="https://github.com/nikmcfly/MiroFish-Offline" target="_blank" class="github-link" :style="s.githubLink">
          Visit our Github <span>↗</span>
        </a>
      </div>
    </nav>

    <div class="main-content" :style="s.mainContent">
      <!-- Hero Section -->
      <section class="hero-section" :style="s.heroSection">
        <div class="hero-left" :style="s.heroLeft">
          <div class="tag-row" :style="s.tagRow">
            <span class="orange-tag" :style="s.orangeTag">Web Research Seed Engine</span>
            <span class="version-text" :style="s.versionText">/ v0.1-preview</span>
          </div>

          <h1 class="main-title" :style="s.mainTitle">
            Describe Any Scenario<br>
            <span class="gradient-text" :style="s.gradientText">Ground It With Web Research</span>
          </h1>

          <div class="hero-desc" :style="s.heroDesc">
            <p :style="s.heroDescP">
              <span :style="s.highlightBold">Deepsearch MiroFish</span> turns a scenario prompt into web-search-enriched seed documents, gathering source-grounded incidents, groups, and context before the simulation setup begins.
            </p>
            <p class="slogan-text" :style="s.sloganText">
              Research-enriched seeds first. Local simulation follows<span :style="s.blinkingCursor">_</span>
            </p>
          </div>

          <div class="decoration-square" :style="s.decorationSquare"></div>
        </div>

        <div class="hero-right" :style="s.heroRight">
          <div class="logo-container" :style="s.logoContainer">
            <img src="../assets/logo/MiroFish_logo_left.jpeg" alt="Deepsearch MiroFish Logo" :style="s.heroLogo" />
          </div>
          <button :style="s.scrollDownBtn" type="button" aria-label="Scroll to Start Engine" @click="scrollToBottom">
            <span aria-hidden="true">↓</span>
          </button>
        </div>
      </section>

      <!-- Dashboard: Two-Column Layout -->
      <section class="dashboard-section" :style="s.dashboardSection">
        <!-- Left Column: Status & Steps -->
        <div class="left-panel" :style="s.leftPanel">
          <div class="panel-header" :style="s.panelHeader">
            <span :style="s.statusDot">■</span> System Status
          </div>

          <h2 class="section-title" :style="s.sectionTitle">Ready</h2>
          <p class="section-desc" :style="s.sectionDesc">
            Research seed engine on standby. Enter a scenario prompt to generate enriched seed docs for simulation.
          </p>

          <div class="metrics-row" :style="s.metricsRow">
            <div class="metric-card" :style="s.metricCard">
              <div class="metric-value" :style="s.metricValue">Free</div>
              <div class="metric-label" :style="s.metricLabel">Runs on your hardware</div>
            </div>
            <div class="metric-card" :style="s.metricCard">
              <div class="metric-value" :style="s.metricValue">Private</div>
              <div class="metric-label" :style="s.metricLabel">Local stack, no cloud keys</div>
            </div>
          </div>

          <div class="steps-container" :style="s.stepsContainer">
            <div class="steps-header" :style="s.stepsHeader">
               <span :style="s.diamondIcon">◇</span> Workflow Sequence
            </div>
            <div :style="s.workflowList">
              <div v-for="(step, i) in steps" :key="i" :style="s.workflowItem">
                <span :style="s.stepNum">{{ step.num }}</span>
                <div :style="s.stepInfo">
                  <div :style="s.stepTitle">{{ step.title }}</div>
                  <div :style="s.stepDesc">{{ step.desc }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column: Interactive Console -->
        <div class="right-panel" :style="s.rightPanel">
          <div class="console-box" :style="s.consoleBox">
            <div :style="s.consoleSection">
              <div class="console-header" :style="s.consoleHeader">
                <span>01 / Web Research Seed</span>
                <span>SearXNG + Ollama</span>
              </div>
              <div :style="s.inputWrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  :style="s.codeInput"
                  name="simulation_requirement"
                  aria-label="Simulation Requirement"
                  autocomplete="off"
                  placeholder="// Describe your simulation or prediction goal in natural language…"
                  rows="10"
                  :disabled="loading"
                ></textarea>
                <div :style="s.modelBadge">Seed: web research</div>
              </div>
            </div>

            <div :style="s.btnSection">
	              <button :style="s.startEngineBtn" type="button" @click="startSimulation" :disabled="!canSubmit || loading">
	                <span v-if="!loading">Start Engine</span>
	                <span v-else aria-live="polite">Initializing…</span>
	                <span aria-hidden="true">→</span>
	              </button>
            </div>
          </div>
        </div>
      </section>

      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import { setPendingResearchSeed } from '../store/pendingResearchSeed'

const mono = 'JetBrains Mono, monospace'
const sans = 'Space Grotesk, Noto Sans SC, system-ui, sans-serif'

const s = reactive({
  navbar: { height: '60px', background: '#000', color: '#fff', display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 40px' },
  navBrand: { fontFamily: mono, fontWeight: '800', letterSpacing: '1px', fontSize: '1.2rem' },
  navLinks: { display: 'flex', alignItems: 'center' },
  githubLink: { color: '#fff', textDecoration: 'none', fontFamily: mono, fontSize: '0.9rem', fontWeight: '500', display: 'flex', alignItems: 'center', gap: '8px' },
  mainContent: { maxWidth: '1400px', margin: '0 auto', padding: '60px 40px' },
  heroSection: { display: 'flex', justifyContent: 'space-between', marginBottom: '80px', position: 'relative' },
  heroLeft: { flex: '1', paddingRight: '60px' },
  tagRow: { display: 'flex', alignItems: 'center', gap: '15px', marginBottom: '25px', fontFamily: mono, fontSize: '0.8rem' },
  orangeTag: { background: '#FF4500', color: '#fff', padding: '4px 10px', fontWeight: '700', letterSpacing: '1px', fontSize: '0.75rem' },
  versionText: { color: '#999', fontWeight: '500', letterSpacing: '0.5px' },
  mainTitle: { fontSize: '4.5rem', lineHeight: '1.2', fontWeight: '500', margin: '0 0 40px 0', letterSpacing: '-2px', color: '#000' },
  gradientText: { background: 'linear-gradient(90deg, #000 0%, #444 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', display: 'inline-block' },
  heroDesc: { fontSize: '1.05rem', lineHeight: '1.8', color: '#666', maxWidth: '640px', marginBottom: '50px', fontWeight: '400', textAlign: 'justify' },
  heroDescP: { marginBottom: '1.5rem' },
  highlightBold: { color: '#000', fontWeight: '700' },
  highlightOrange: { color: '#FF4500', fontWeight: '700', fontFamily: mono },
  highlightCode: { background: 'rgba(0,0,0,0.05)', padding: '2px 6px', borderRadius: '2px', fontFamily: mono, fontSize: '0.9em', color: '#000', fontWeight: '600' },
  sloganText: { fontSize: '1.2rem', fontWeight: '520', color: '#000', letterSpacing: '1px', borderLeft: '3px solid #FF4500', paddingLeft: '15px', marginTop: '20px' },
  blinkingCursor: { color: '#FF4500', fontWeight: '700' },
  decorationSquare: { width: '16px', height: '16px', background: '#FF4500' },
  heroRight: { flex: '0.8', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', alignItems: 'flex-end' },
  logoContainer: { width: '100%', display: 'flex', justifyContent: 'flex-end', paddingRight: '40px' },
  heroLogo: { maxWidth: '500px', width: '100%' },
  scrollDownBtn: { width: '40px', height: '40px', border: '1px solid #E5E5E5', background: 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer', color: '#FF4500', fontSize: '1.2rem' },
  dashboardSection: { display: 'flex', gap: '60px', borderTop: '1px solid #E5E5E5', paddingTop: '60px', alignItems: 'flex-start' },
  leftPanel: { flex: '0.8', display: 'flex', flexDirection: 'column' },
  panelHeader: { fontFamily: mono, fontSize: '0.8rem', color: '#999', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' },
  statusDot: { color: '#FF4500', fontSize: '0.8rem' },
  sectionTitle: { fontSize: '2rem', fontWeight: '520', margin: '0 0 15px 0' },
  sectionDesc: { color: '#666', marginBottom: '25px', lineHeight: '1.6' },
  metricsRow: { display: 'flex', gap: '20px', marginBottom: '15px' },
  metricCard: { border: '1px solid #E5E5E5', padding: '20px 30px', minWidth: '150px' },
  metricValue: { fontFamily: mono, fontSize: '1.8rem', fontWeight: '520', marginBottom: '5px' },
  metricLabel: { fontSize: '0.85rem', color: '#999' },
  stepsContainer: { border: '1px solid #E5E5E5', padding: '30px', position: 'relative' },
  stepsHeader: { fontFamily: mono, fontSize: '0.8rem', color: '#999', marginBottom: '25px', display: 'flex', alignItems: 'center', gap: '8px' },
  diamondIcon: { fontSize: '1.2rem', lineHeight: '1' },
  workflowList: { display: 'flex', flexDirection: 'column', gap: '20px' },
  workflowItem: { display: 'flex', alignItems: 'flex-start', gap: '20px' },
  stepNum: { fontFamily: mono, fontWeight: '700', color: '#000', opacity: '0.3' },
  stepInfo: { flex: '1' },
  stepTitle: { fontWeight: '520', fontSize: '1rem', marginBottom: '4px' },
  stepDesc: { fontSize: '0.85rem', color: '#666' },
  rightPanel: { flex: '1.2', display: 'flex', flexDirection: 'column' },
  consoleBox: { border: '1px solid #CCC', padding: '8px' },
  consoleSection: { padding: '20px' },
  consoleHeader: { display: 'flex', justifyContent: 'space-between', marginBottom: '15px', fontFamily: mono, fontSize: '0.75rem', color: '#666' },
  inputWrapper: { position: 'relative', border: '1px solid #DDD', background: '#FAFAFA' },
  codeInput: { width: '100%', border: 'none', background: 'transparent', padding: '20px', fontFamily: mono, fontSize: '0.9rem', lineHeight: '1.6', resize: 'vertical', minHeight: '150px' },
  modelBadge: { position: 'absolute', bottom: '10px', right: '15px', fontFamily: mono, fontSize: '0.7rem', color: '#AAA' },
  btnSection: { padding: '0 20px 20px' },
  startEngineBtn: { width: '100%', background: '#000', color: '#fff', border: 'none', padding: '20px', fontFamily: mono, fontWeight: '700', fontSize: '1.1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', letterSpacing: '1px' },
})

const steps = [
  { num: '01', title: 'Graph Build', desc: 'Generate a web research seed, build knowledge graph with Neo4j + GraphRAG' },
  { num: '02', title: 'Env Setup', desc: 'Generate agent personas, configure simulation parameters via local Ollama LLM' },
  { num: '03', title: 'Simulation', desc: 'Run multi-agent simulation locally with dynamic memory updates and emergent behavior' },
  { num: '04', title: 'Report', desc: 'ReportAgent analyzes the simulation results and generates a detailed prediction report' },
  { num: '05', title: 'Interaction', desc: 'Chat with any agent from the simulated world or discuss findings with ReportAgent' },
]

const router = useRouter()

const formData = ref({ simulationRequirement: '' })
const loading = ref(false)

const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== ''
})

const scrollToBottom = () => { window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }) }

const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  setPendingResearchSeed(formData.value.simulationRequirement)
  router.push({ name: 'Process', params: { projectId: 'new' } })
}
</script>

<!-- Styles loaded from Home.css via import -->
