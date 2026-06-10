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

  it('uses a unified inbox and simplified compose payload', () => {
    const page = readProjectFile('src/pages/messages/index.astro');
    expect(page).toContain("/messaging/threads/");
    expect(page).not.toContain('tab-inbox');
    expect(page).not.toContain('tab-sent');
    expect(page).not.toContain('compose-subject');
    expect(page).not.toContain('subject:');
  });

  it('keeps student messages link visible in the dashboard sidebar', () => {
    const layout = readProjectFile('src/layouts/DashboardLayout.astro');
    expect(layout).toContain('href="/messages"');
    expect(layout).toContain('id="nav-student"');
    expect(layout).toContain('/messaging/unread-count/');
  });
});
