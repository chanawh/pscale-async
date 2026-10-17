module.exports = {
  root: true,
  env: { 
    browser: true, 
    es2020: true,
    node: true, // Allow Node.js globals like __dirname
  },
  extends: [
    'eslint:recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parserOptions: {
    ecmaVersion: 'latest',
    sourceType: 'module',
    ecmaFeatures: {
      jsx: true,
    },
  },
  globals: {
    React: 'readonly', // Define React as global for JSX
  },
  rules: {
    'no-unused-vars': 'warn',
    'no-console': 'off', // Allow console statements
    'no-undef': 'off', // Disable no-undef for React
  },
  overrides: [
    {
      files: ['*.ts', '*.tsx'],
      parser: '@typescript-eslint/parser',
      plugins: ['@typescript-eslint'],
      rules: {
        '@typescript-eslint/no-unused-vars': 'warn',
        '@typescript-eslint/no-explicit-any': 'warn',
      },
    },
  ],
}
