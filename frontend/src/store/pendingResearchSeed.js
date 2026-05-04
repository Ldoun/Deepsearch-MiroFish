/**
 * Temporarily store the prompt used to generate a web research seed.
 * Used to immediately navigate after clicking Start Engine on home page.
 */
import { reactive } from 'vue'

const state = reactive({
  simulationRequirement: '',
  additionalContext: '',
  isPending: false
})

export function setPendingResearchSeed(requirement, additionalContext = '') {
  state.simulationRequirement = requirement
  state.additionalContext = additionalContext
  state.isPending = true
}

export function getPendingResearchSeed() {
  return {
    simulationRequirement: state.simulationRequirement,
    additionalContext: state.additionalContext,
    isPending: state.isPending
  }
}

export function clearPendingResearchSeed() {
  state.simulationRequirement = ''
  state.additionalContext = ''
  state.isPending = false
}

export default state
