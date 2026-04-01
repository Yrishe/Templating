import '@testing-library/jest-dom'
import { server } from './src/mocks/server'

// Start MSW server before all tests
beforeAll(() => server.listen({ onUnhandledRequest: 'warn' }))

// Reset handlers after each test to avoid state leakage
afterEach(() => server.resetHandlers())

// Stop MSW server after all tests complete
afterAll(() => server.close())
