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

  it("includes departments admin link in dashboard sidebar", () => {
    const layout = readProjectFile("src/layouts/DashboardLayout.astro");
    expect(layout).toContain('href="/departments"');
  });

  it("keeps departments link inside academic admin cluster", () => {
    const layout = readProjectFile("src/layouts/DashboardLayout.astro");
    const subjectIndex = layout.indexOf('href="/subject"');
    const departmentsIndex = layout.indexOf('href="/departments"');
    const periodsIndex = layout.indexOf('href="/periods"');
    expect(subjectIndex).toBeGreaterThan(-1);
    expect(departmentsIndex).toBeGreaterThan(subjectIndex);
    expect(periodsIndex).toBeGreaterThan(departmentsIndex);
  });
});

describe("system page scope cleanup", () => {
  it("keeps system page focused on settings only", () => {
    const systemPage = readProjectFile("src/pages/system/index.astro");
    expect(systemPage).not.toContain("id=\"new-user-btn\"");
    expect(systemPage).not.toContain("id=\"users-table\"");
    expect(systemPage).not.toContain("/users/");
  });

  it("removes waitlist grace days controls from the management system page", () => {
    const managementSystemPage = readProjectFile("src/pages/management/system.astro");
    expect(managementSystemPage).not.toContain("admission-waitlist-grace-days");
    expect(managementSystemPage).not.toContain("admission_waitlist_grace_days");
  });
});

describe("departments page scaffold", () => {
  it("contains base loading and content sections", () => {
    const departmentsPage = readProjectFile("src/pages/departments/index.astro");
    expect(departmentsPage).toContain('currentPath="/departments"');
    expect(departmentsPage).toContain('id="page-loading"');
    expect(departmentsPage).toContain('id="page-content"');
    expect(departmentsPage).toContain('id="departments-table-body"');
    expect(departmentsPage).toContain('id="departments-empty"');
    expect(departmentsPage).toContain('id="page-error"');
  });

  it("contains base table skeleton and creation trigger", () => {
    const departmentsPage = readProjectFile("src/pages/departments/index.astro");
    expect(departmentsPage).toContain('id="new-department-btn"');
    expect(departmentsPage).toContain('id="departments-table-body"');
    expect(departmentsPage).toContain('No se encontraron departamentos');
  });
});

describe("departments page CRUD wiring", () => {
  it("adds pagination and modal form structure", () => {
    const departmentsPage = readProjectFile("src/pages/departments/index.astro");
    expect(departmentsPage).toContain('id="departments-pagination"');
    expect(departmentsPage).toContain('id="department-form"');
    expect(departmentsPage).toContain('id="department-teacher"');
    expect(departmentsPage).toContain('id="department-active"');
  });

  it("wires departments and teachers API contracts", () => {
    const departmentsPage = readProjectFile("src/pages/departments/index.astro");
    expect(departmentsPage).toContain("buildPaginatedEndpoint('/academic/departments/'");
    expect(departmentsPage).toContain("apiFetch('/users/teachers/')");
    expect(departmentsPage).toContain("/academic/departments/${id}/");
  });

  it("contains actionable CRUD error handling", () => {
    const departmentsPage = readProjectFile("src/pages/departments/index.astro");
    expect(departmentsPage).toContain('id="crud-error"');
    expect(departmentsPage).toContain('No se pudo guardar el departamento');
    expect(departmentsPage).toContain('No se pudo eliminar el departamento');
  });
});

describe("subject page department integration wiring", () => {
  it("loads departments catalog together with subjects context", () => {
    const subjectPage = readProjectFile("src/pages/subject/index.astro");
    expect(subjectPage).toContain("let departmentsList = []");
    expect(subjectPage).toContain("apiFetch('/academic/departments/')");
  });

  it("contains department selector with null option", () => {
    const subjectPage = readProjectFile("src/pages/subject/index.astro");
    expect(subjectPage).toContain('id="subject-department"');
    expect(subjectPage).toContain('Sin departamento');
    expect(subjectPage).toContain("departmentSel.value = subject.department ? String(subject.department) : ''");
  });

  it("sends department id or null on subject save", () => {
    const subjectPage = readProjectFile("src/pages/subject/index.astro");
    expect(subjectPage).toContain("const departmentRaw = (document.getElementById('subject-department') as HTMLSelectElement).value;");
    expect(subjectPage).toContain("department: departmentRaw ? Number(departmentRaw) : null");
    expect(subjectPage).toContain("const departmentName = s.department_name || '-';");
  });
});
