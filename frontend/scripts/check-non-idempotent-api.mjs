import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const graphApiPath = resolve(scriptDir, '../src/api/graph.js')
const source = readFileSync(graphApiPath, 'utf8')

const generateOntologyMatch = source.match(/export function generateOntology\(data\) \{([\s\S]*?)\n\}/)

assert.ok(generateOntologyMatch, 'generateOntology API function was not found')
assert.equal(
  generateOntologyMatch[1].includes('requestWithRetry'),
  false,
  'generateOntology must not retry automatically because it creates projects'
)

console.log('Non-idempotent API checks passed')
