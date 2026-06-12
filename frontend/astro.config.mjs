import tailwindcss from "@tailwindcss/vite";
// @ts-check
import node from '@astrojs/node';
import { defineConfig } from 'astro/config';

// `astro.config.mjs` is a plain object (Astro's `defineConfig` is `(c) => c`, not a
// Vite-style `(env) => c` factory), so the dev/build/preview branch is resolved from
// `process.argv` at module-eval time: `astro <command>` puts the command at argv[2].
const isDev = process.argv[2] === 'dev';

// https://astro.build/config
export default defineConfig({
	// SSR + Node adapter only for build/preview; `astro dev` stays a plain dev server.
	...(!isDev
		? {
				output: 'server',
				adapter: node({
					mode: 'standalone',
				}),
			}
		: {}),
	vite: {
		plugins: [tailwindcss()],
	},
	server: {
		host: true,
		allowedHosts: ['academix.cv', 'localhost', '127.0.0.1', '::1'],
		port: 4321,
	},
});
