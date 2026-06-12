import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const pageSource = readFileSync(join(process.cwd(), "src/pages/management/identity-verifications.astro"), "utf-8");

describe("identity verification document access page", () => {
  it("uses the authenticated download proxy instead of raw media urls", () => {
    expect(pageSource).toContain("doc.download_url");
    expect(pageSource).toContain("res.blob()");
    expect(pageSource).toContain("URL.createObjectURL");
    expect(pageSource).not.toContain("resolveMediaUrl(doc.file)");
  });
});
