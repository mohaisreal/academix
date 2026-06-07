import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf-8");
}

describe("users modal visual parity with subjects modal", () => {
  it("uses labeled field blocks and shared header/body/footer treatment", () => {
    const usersPage = readProjectFile("src/pages/management/users.astro");

    expect(usersPage).toContain('<div class="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">');
    expect(usersPage).toContain('<div class="overflow-y-auto flex-1 px-5 py-4">');
    expect(usersPage).toContain('<div class="flex items-center justify-end gap-3 px-5 py-4 border-t border-border shrink-0">');

    expect(usersPage).toContain('label class="text-xs font-medium text-muted-foreground"');
    expect(usersPage).toContain('class="mt-1 w-full bg-input border border-border rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary"');
  });
});

describe("users action buttons visual variants", () => {
  it("keeps edit neutral, delete destructive and toggle state-aware", () => {
    const usersPage = readProjectFile("src/pages/management/users.astro");

    expect(usersPage).toContain('class="edit-btn rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted transition-colors"');
    expect(usersPage).toContain('class="delete-btn rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-red-400 hover:bg-red-500/10 hover:border-red-500/30 transition-colors"');
    expect(usersPage).toContain("toggle-btn");
    expect(usersPage).toContain("text-amber-400");
    expect(usersPage).toContain("text-emerald-400");
  });
});

describe("users destructive actions use visual confirmation modal", () => {
  it("replaces browser confirm() with global confirmAction for delete and toggle", () => {
    const usersPage = readProjectFile("src/pages/management/users.astro");

    expect(usersPage).not.toContain("confirm(");
    expect(usersPage).toContain("(window as any).confirmAction?.({");
    expect(usersPage).toContain("title: active ? 'Desactivar usuario' : 'Activar usuario'");
    expect(usersPage).toContain("title: 'Eliminar usuario'");
    expect(usersPage).toContain("Esta acción no se puede deshacer");
    expect(usersPage).toContain("confirmLabel: active ? 'Desactivar' : 'Activar'");
    expect(usersPage).toContain("confirmLabel: 'Eliminar'");
    expect(usersPage).toContain("variant: 'destructive'");
  });

  it("keeps API side effects inside modal onConfirm callbacks", () => {
    const usersPage = readProjectFile("src/pages/management/users.astro");

    expect(usersPage).toContain("onConfirm: async () => {");
    expect(usersPage).toContain("await apiFetch(`/users/${id}/`, { method: 'PATCH', body: JSON.stringify({ is_active: !active }) });");
    expect(usersPage).toContain("await apiFetch(`/users/${id}/`, { method: 'DELETE' });");
    expect(usersPage).toContain("await loadUsers(currentPage);");
  });
});

describe("users exceptional cases entry point", () => {
  it("exposes a dedicated button and modal for convocation grace", () => {
    const usersPage = readProjectFile("src/pages/management/users.astro");

    expect(usersPage).toContain("Casos excepcionales");
    expect(usersPage).toContain('id="exceptional-backdrop"');
    expect(usersPage).toContain('id="exceptional-save"');
    expect(usersPage).toContain("/enrollment/students/${exceptionalStudent.id}/convocation-graces/");
  });
});
