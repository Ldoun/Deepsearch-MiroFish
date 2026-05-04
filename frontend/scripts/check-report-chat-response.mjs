import { normalizeReportAgentResponse } from '../src/utils/reportChat.js'

const cases = [
  {
    name: 'nested backend response object',
    input: { response: { response: 'Nested response text', sources: [], tool_calls: [] } },
    expected: 'Nested response text'
  },
  {
    name: 'plain response string',
    input: { response: 'Plain response text' },
    expected: 'Plain response text'
  },
  {
    name: 'answer fallback',
    input: { answer: 'Answer text' },
    expected: 'Answer text'
  }
]

for (const testCase of cases) {
  const actual = normalizeReportAgentResponse(testCase.input)
  if (actual !== testCase.expected) {
    throw new Error(`${testCase.name}: expected ${JSON.stringify(testCase.expected)}, received ${JSON.stringify(actual)}`)
  }
}

console.log('report chat response normalization check passed')
