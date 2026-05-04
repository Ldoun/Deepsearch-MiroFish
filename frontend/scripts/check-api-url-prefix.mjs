import assert from 'node:assert/strict'
import { normalizeApiBaseURL } from '../src/api/baseUrl.js'

const endpoint = '/api/graph/ontology/generate'
const cases = [
  ['/api', ''],
  ['/api/', ''],
  ['http://localhost:5001/api', 'http://localhost:5001'],
  ['http://localhost:5001/api/', 'http://localhost:5001'],
  ['http://localhost:5001', 'http://localhost:5001'],
  ['', '']
]

for (const [input, expected] of cases) {
  const normalized = normalizeApiBaseURL(input)
  assert.equal(normalized, expected, `Unexpected normalized base for ${input}`)
  assert.equal(
    `${normalized}${endpoint}`.includes('/api/api/'),
    false,
    `API URL double-prefixes /api for ${input}`
  )
}

console.log('API URL prefix checks passed')
