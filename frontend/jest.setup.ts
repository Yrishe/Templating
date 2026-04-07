/* eslint-disable @typescript-eslint/no-var-requires */
// jest-fixed-jsdom (configured in jest.config.js) already provides Fetch API
// globals (fetch / Request / Response / Headers / FormData / Blob /
// ReadableStream) needed by MSW v2 — no manual polyfills required.

require('@testing-library/jest-dom')
const { server } = require('./src/mocks/server')

// Start MSW server before all tests
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))

// Reset handlers after each test to avoid state leakage
afterEach(() => server.resetHandlers())

// Stop MSW server after all tests complete
afterAll(() => server.close())
