import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('messages realtime wiring', () => {
  it('connects websocket and refetches on message.created events', () => {
    const page = readProjectFile('src/pages/messages/index.astro');
    expect(page).toContain('new WebSocket(buildMessagesSocketUrl())');
    expect(page).toContain("payload.type !== 'message.created'");
    expect(page).toContain('loadMessages();');
    expect(page).toContain('refreshUnreadCount();');
    expect(page).toContain("/messaging/unread-count/");
  });

  it('falls back by scheduling reconnects when the socket closes', () => {
    const page = readProjectFile('src/pages/messages/index.astro');
    expect(page).toContain('scheduleReconnect');
    expect(page).toContain('window.WebSocket');
  });

  it('keeps student messages link visible in the dashboard sidebar', () => {
    const layout = readProjectFile('src/layouts/DashboardLayout.astro');
    expect(layout).toContain('href="/messages"');
    expect(layout).toContain('id="nav-student"');
  });
});
