import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const pageSource = readFileSync(join(process.cwd(), "src/pages/management/admissions/[id].astro"), "utf-8");

describe("management admissions detail page", () => {
  it("shows academic data whenever persisted academic fields exist", () => {
    expect(pageSource).toContain("hasAcademicData");
    expect(pageSource).toContain("app.bachillerato_grade != null");
    expect(pageSource).toContain("app.evau_obligatory_grade != null");
    expect(pageSource).toContain("app.admission_score != null");
  });
});
