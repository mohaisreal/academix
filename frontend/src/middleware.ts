import { defineMiddleware } from 'astro:middleware';

const backendApiBaseUrl = (import.meta.env.BACKEND_API_URL ?? 'http://backend:8000/api').replace(/\/$/, '');

export const onRequest = defineMiddleware(async (context, next) => {
  // Dev runs plain `astro dev` (no adapter): browser hits the backend directly,
  // so the same-origin proxy and /health route are prod-only.
  if (!import.meta.env.PROD) {
    return next();
  }

  if (context.url.pathname === '/health') {
    return new Response('healthy\n', {
      headers: {
        'Content-Type': 'text/plain; charset=utf-8',
      },
    });
  }

  if (!context.url.pathname.startsWith('/api/')) {
    return next();
  }

  const apiPath = context.url.pathname.slice('/api'.length) || '/';
  const target = new URL(backendApiBaseUrl + apiPath + context.url.search);
  const headers = new Headers(context.request.headers);
  headers.set('Host', target.host);
  headers.set('X-Forwarded-Host', context.url.host);
  headers.set('X-Forwarded-Proto', context.url.protocol.replace(':', ''));

  const response = await fetch(target, {
    method: context.request.method,
    headers,
    body: ['GET', 'HEAD'].includes(context.request.method) ? undefined : await context.request.clone().arrayBuffer(),
  });

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers: response.headers,
  });
});
