import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';

// Frontend layering (low to high): types < config/lib < api < state < hooks < components < pages.
// A file may import only from layers at or below its own; pages never import api directly.
const layers = ['types', 'config', 'lib', 'api', 'state', 'hooks', 'components', 'pages'];
const layerRules = layers.map((layer, i) => {
  const higher = layers.slice(i + 1).map((l) => `@/${l}`);
  const patterns = higher.flatMap((l) => [l, `${l}/*`]);
  if (layer === 'pages' || layer === 'components') {
    patterns.push('@/api', '@/api/*');
  }
  return {
    files: [`src/${layer}/**/*.{ts,tsx}`],
    rules: {
      'no-restricted-imports': [
        'error',
        { patterns: patterns.map((group) => ({ group: [group], message: `Layer violation: ${layer} must not import ${group}` })) },
      ],
    },
  };
});

export default tseslint.config(
  { ignores: ['dist', 'coverage', 'node_modules'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
    plugins: { 'react-hooks': reactHooks },
    rules: { ...reactHooks.configs.recommended.rules, 'max-lines': ['error', { max: 300, skipBlankLines: true, skipComments: true }] },
  },
  ...layerRules,
);
