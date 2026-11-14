import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { test as base, expect, type Page, type TestInfo } from "@playwright/test";

/*
 * MacroLens end-to-end + visual QA.
 *
 * Why no toHaveScreenshot() pixel baselines: the pipeline rewrites web/public/data/*.json
 * every day (prices, returns, macro prints, "Updated 3h ago"), so any committed baseline
 * would diff on the next data commit and the suite would fail for reasons that are not bugs.
 * Instead we (a) capture full-page screenshots in both themes as report artifacts for human
 * review, and (b) assert layout INVARIANTS that must hold whatever the numbers are: no
 * horizontal overflow, every panel has a non-zero box, one column on phones.
 */

const E2E_DIR = dirname(fileURLToPath(import.meta.url));
const WEB_DIR = join(E2E_DIR, "..");
const DATA_DIR = join(WEB_DIR, "public", "data");
const SHOT_DIR = join(E2E_DIR, "__screenshots__", "actual");

/**
 * Registry-driven: read { id, title } for every panel straight from src/panels/registry.tsx.
 * We parse the source rather than import it, because importing pulls the whole React/ECharts
 * component tree into Node. New panels registered there are picked up automatically.
 */
function registryPanels(): { id: string; title: string }[] {
  const src = readFileSync(join(WEB_DIR, "src", "panels", "registry.tsx"), "utf8");
  const body = src.slice(src.indexOf("export const PANELS"));
  const out = [...body.matchAll(/\{\s*id:\s*"([^"]+)",\s*title:\s*"([^"]+)"/g)].map((m) => ({ id: m[1], title: m[2] }));
  if (!out.length) throw new Error("could not parse PANELS from registry.tsx");
  return out;
}
const PANELS = registryPanels();

/** Panels whose data section is known and must always load (their JSON is committed). */
const CORE_SECTIONS: Record<string, string> = {
  index_snapshot: "markets",
  sectors: "markets",
  fixed_income: "markets",
  commodities: "markets",
  currencies: "markets",
  economic_indicators: "economy",
  yield_curve: "yield_curve",
  economic_calendar: "calendar",
  macro_regime: "regime", // code-computed, committed; needs no LLM key
};

// Network noise we tolerate: favicon and Google Fonts only.
const IGNORED = [/favicon/i, /fonts\.(googleapis|gstatic)\.com/i];

/** Fixture: every test fails if the page logs a console error or throws. */
const test = base.extend<{ errors: string[] }>({
  errors: [async ({ page }, use) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() !== "error") return;
      const where = msg.location()?.url ?? "";
      if (IGNORED.some((re) => re.test(msg.text()) || re.test(where))) return;
      errors.push(`console.error: ${msg.text()} ${where}`);
    });
    page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
    await use(errors);
    expect(errors, "console / page errors").toEqual([]);
  }, { auto: true }],
});

const panel = (page: Page, id: string) => page.locator(`section[aria-labelledby="${id}-title"]`);

/** Load the dashboard and wait until every registered panel has rendered its shell and data. */
async function openDashboard(page: Page) {
  await page.goto("./");
  for (const p of PANELS) await expect(page.locator(`[id="${p.id}-title"]`)).toBeVisible();
  await expect(page.getByText("Loading…")).toHaveCount(0, { timeout: 15_000 });
}

async function layoutInvariants(page: Page) {
  const { scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth, innerWidth: window.innerWidth,
  }));
  expect(scrollWidth, "horizontal page overflow").toBeLessThanOrEqual(innerWidth + 1);
  for (const p of PANELS) {
    const box = await panel(page, p.id).boundingBox();
    expect(box, `${p.id} has a box`).not.toBeNull();
    expect(box!.width, `${p.id} width`).toBeGreaterThan(0);
    expect(box!.height, `${p.id} height`).toBeGreaterThan(0);
  }
}

async function snapshot(page: Page, testInfo: TestInfo, name: string) {
  const png = await page.screenshot({ fullPage: true, animations: "disabled" });
  await testInfo.attach(name, { body: png, contentType: "image/png" });
  mkdirSync(SHOT_DIR, { recursive: true });
  writeFileSync(join(SHOT_DIR, `${name}.png`), png);
}

test.describe("dashboard", () => {
  test.beforeEach(async ({ page }) => { await openDashboard(page); });

  test("every registered panel renders a visible, non-empty title", async ({ page }) => {
    for (const p of PANELS) {
      const h2 = page.locator(`[id="${p.id}-title"]`);
      await expect(h2).toBeVisible();
      await expect(h2).toHaveText(p.title, { ignoreCase: true });
    }
    // DOM-side check too: every labelled section has a non-empty heading, one per panel.
    const sections = page.locator("section[aria-labelledby]");
    await expect(sections).toHaveCount(PANELS.length);
    for (const s of await sections.all()) {
      const id = await s.getAttribute("aria-labelledby");
      await expect(s.locator(`h2[id="${id}"]`)).not.toBeEmpty();
    }
  });

  test("no panel shows 'Could not load data' when its JSON exists", async ({ page }) => {
    for (const [id, section] of Object.entries(CORE_SECTIONS)) {
      if (!PANELS.some((p) => p.id === id)) continue;
      expect(existsSync(join(DATA_DIR, `${section}.json`)), `${section}.json committed`).toBe(true);
      await expect(panel(page, id).getByText("Could not load data")).toHaveCount(0);
    }
    // Generic check for any other panel: the error names its section; fail if that file exists.
    for (const msg of await page.getByText(/Could not load data/).allInnerTexts()) {
      const name = /"([\w-]+)" section|([\w-]+)\.json/.exec(msg);
      const section = name?.[1] ?? name?.[2];
      expect(section && !existsSync(join(DATA_DIR, `${section}.json`)), `unexpected load error: ${msg}`).toBe(true);
    }
  });

  test("AI panels: regime always renders; AI text or the 'not generated yet' message", async ({ page }) => {
    // regime.json is computed by code and always committed; insights.json only exists once an
    // LLM key is configured, so both of its states are valid.
    const has = existsSync(join(DATA_DIR, "insights.json"));
    if (PANELS.some((p) => p.id === "macro_regime")) {
      const regime = panel(page, "macro_regime");
      await expect(regime).toContainText("Growth × Inflation momentum");
      await expect(regime).toContainText("Historical tendencies (generalisations, not forecasts)");
      await expect(regime).toContainText(has ? "Why (AI explainer)" : "AI explainer not generated yet");
      await expect(regime.getByText(/Could not load/)).toHaveCount(0);
    }
    if (PANELS.some((p) => p.id === "macro_brief")) {
      const brief = panel(page, "macro_brief");
      await expect(brief.getByText("Could not load data")).toHaveCount(0);
      await expect(brief).toContainText(has ? "Not investment advice" : "AI insights not generated yet");
    }
  });

  test("period radio changes the Sector Performance subtitle", async ({ page }) => {
    const sectors = panel(page, "sectors");
    await expect(sectors).toContainText("Total return · 6M");
    const oneMonth = page.getByRole("radiogroup", { name: "Performance period" }).getByRole("radio", { name: "1M" });
    await oneMonth.click();
    await expect(oneMonth).toHaveAttribute("aria-checked", "true");
    await expect(sectors).toContainText("Total return · 1M");
    await expect(sectors).not.toContainText("Total return · 6M");
  });

  test("ⓘ About opens a dialog with 'What it is'; Escape closes it", async ({ page }) => {
    await panel(page, "sectors").getByRole("button", { name: "About Sector Performance" }).click();
    const dialog = page.getByRole("dialog", { name: "About Sector Performance" });
    await expect(dialog).toBeVisible();
    await expect(dialog).toContainText("What it is");
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });

  test("Economic Indicators row opens the history modal with a chart; Escape closes it", async ({ page }) => {
    const row = panel(page, "economic_indicators").getByRole("button", { name: /: show history$/ }).first();
    const label = (await row.getAttribute("aria-label"))!.replace(/: show history$/, "");
    await row.click();
    const dialog = page.getByRole("dialog", { name: label });
    await expect(dialog).toBeVisible();
    await expect(dialog.locator("canvas").first()).toBeVisible({ timeout: 15_000 });
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  });

  test("theme toggle switches html[data-theme] dark ↔ light", async ({ page }) => {
    const html = page.locator("html");
    const toggle = page.getByRole("button", { name: "Toggle light/dark theme" });
    await expect(html).toHaveAttribute("data-theme", "dark");
    await toggle.click();
    await expect(html).toHaveAttribute("data-theme", "light");
    await toggle.click();
    await expect(html).toHaveAttribute("data-theme", "dark");
  });

  test("Customise View hides a panel and 'Show all' restores it", async ({ page }) => {
    const target = PANELS.find((p) => p.id === "sectors") ?? PANELS[0];
    await page.getByRole("button", { name: "Customise view" }).click();
    const menu = page.getByRole("dialog", { name: "Customise view" });
    const box = menu.getByRole("checkbox", { name: target.title, exact: true });
    await expect(box).toBeChecked();
    await box.uncheck();
    await expect(panel(page, target.id)).toHaveCount(0);
    await menu.getByRole("button", { name: "Show all" }).click();
    await expect(box).toBeChecked();
    await expect(panel(page, target.id)).toBeVisible();
  });

  test("visual: full-page screenshots in dark and light + layout invariants", async ({ page }, testInfo) => {
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await layoutInvariants(page);
    await snapshot(page, testInfo, "dashboard-dark");

    await page.getByRole("button", { name: "Toggle light/dark theme" }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await layoutInvariants(page);
    await snapshot(page, testInfo, "dashboard-light");
  });
});

test.describe("narrow viewport (390×844)", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("no horizontal scroll and panels stack in one column", async ({ page }, testInfo) => {
    await openDashboard(page);
    await layoutInvariants(page);
    const boxes = [];
    for (const p of PANELS) boxes.push({ id: p.id, ...(await panel(page, p.id).boundingBox())! });
    // One column: every panel starts at the same x and spans (nearly) the full width.
    const left = boxes[0].x;
    for (const b of boxes) {
      expect(Math.abs(b.x - left), `${b.id} left edge`).toBeLessThanOrEqual(2);
      expect(b.width, `${b.id} width`).toBeGreaterThan(390 * 0.9);
    }
    // ...and no two panels overlap vertically.
    const sorted = [...boxes].sort((a, b) => a.y - b.y);
    for (let i = 1; i < sorted.length; i++) {
      expect(sorted[i].y, `${sorted[i].id} below ${sorted[i - 1].id}`).toBeGreaterThanOrEqual(sorted[i - 1].y + sorted[i - 1].height - 1);
    }
    await snapshot(page, testInfo, "dashboard-mobile-dark");
  });
});
