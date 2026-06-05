import tailwindcss from "@tailwindcss/vite";
// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
	vite: {
		plugins: [tailwindcss()],
	},
	server: {
		host: true,
		allowedHosts: ['academix.cv'],
		port: 4321,
	},
});
