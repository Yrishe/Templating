const nextJest = require('next/jest.js')

const createJestConfig = nextJest({ dir: './' })

/** @type {import('jest').Config} */
const config = {
  coverageProvider: 'v8',
  testEnvironment: 'jest-fixed-jsdom',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: {
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  testMatch: [
    '**/__tests__/**/*.[jt]s?(x)',
    '**/?(*.)+(spec|test).[jt]s?(x)',
  ],
  testPathIgnorePatterns: [
    '/node_modules/',
    '/e2e/',
    '/__tests__/test-utils\\.tsx$',
    '\\.d\\.ts$',
  ],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/mocks/**',
    '!src/app/**/{layout,page}.tsx',
  ],
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80,
    },
  },
}

// next/jest's default transformIgnorePatterns ignore everything in node_modules
// except a small allowlist (next, geist). MSW v2 ships ESM-only deps that need
// transforming, so we override the resolved config AFTER next/jest applies its
// defaults.
const asyncConfig = createJestConfig(config)

module.exports = async () => {
  const resolved = await asyncConfig()
  resolved.transformIgnorePatterns = [
    '/node_modules/(?!(msw|@mswjs|until-async|@bundled-es-modules|headers-polyfill|outvariant|strict-event-emitter|@open-draft|graphql)/)',
    '^.+\\.module\\.(css|sass|scss)$',
  ]
  return resolved
}
