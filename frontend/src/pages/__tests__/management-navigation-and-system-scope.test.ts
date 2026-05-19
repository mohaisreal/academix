import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), "utf-8");
}

describe("management users navigation wiring", () => {
  it("points dashboard quick users action to /management/users", () => {
    const indexPage = readProjectFile("src/pages/index.astro");
    expect(indexPage).toContain('href="/management/users" id="quick-users-card"');
  });

  it("includes users admin link in dashboard sidebar", () => {
    const layout = readProjectFile("src/layouts/DashboardLayout.astro");
    expect(layout).toContain('id="nav-users" href="/management/users"');
  });
});

describe("system page scope cleanup", () => {
  it("keeps system page focused on settings only", () => {
    const systemPage = readProjectFile("src/pages/system/index.astro");
    expect(systemPage).not.toContain("id=\"new-user-btn\"");
    expect(systemPage).not.toContain("id=\"users-table\"");
    expect(systemPage).not.toContain("/users/");
  });
});
