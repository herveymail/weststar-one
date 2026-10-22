// Bundles the API (and @ws/shared) into plain JavaScript in dist/. npm packages stay external.
import { build } from 'esbuild';
import { rmSync } from 'node:fs';
rmSync('dist', { recursive: true, force: true });
await build({
  entryPoints: ['src/server.ts', 'src/jobs/worker.ts', 'src/scripts/seed-admin.ts', 'src/scripts/migrate-cli.ts', 'src/importer/cli.ts'],
  outdir: 'dist', outbase: 'src', bundle: true, platform: 'node', format: 'esm', target: 'node22', sourcemap: true,
  plugins: [{
    name: 'externals',
    setup(b) { b.onResolve({ filter: /^[^./]/ }, (a) => (a.kind === 'entry-point' || a.path.startsWith('@ws/') ? undefined : { path: a.path, external: true })); },
  }],
  banner: { js: "import { createRequire as __cr } from 'node:module'; const require = __cr(import.meta.url);" },
  logLevel: 'info',
});
