import { test, expect } from "../fixtures/caldera-auth";

test.describe("Compass plugin — page load and accessibility", () => {
  test("should load the Caldera UI and find Compass in the plugin navigation", async ({
    authenticatedPage: page,
  }) => {
    // Navigate to the main Caldera page
    await page.goto("/");

    // Look for compass in the navigation (sidebar or top nav)
    const compassLink = page.locator(
      'a[href*="compass"], a:has-text("compass"), [data-plugin="compass"], nav >> text=compass'
    );
    await expect(compassLink.first()).toBeVisible({ timeout: 15_000 });
  });

  test("should navigate to the Compass plugin page", async ({
    authenticatedPage: page,
  }) => {
    // Navigate directly to the compass plugin page
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");

    // Verify Compass heading is present
    const heading = page.locator("h2:has-text('Compass')");
    await expect(heading).toBeVisible({ timeout: 15_000 });
  });

  test("should display the Generate Layer section", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");

    // Check for the Generate Layer label
    const generateLabel = page.locator("text=Generate Layer").first();
    await expect(generateLabel).toBeVisible({ timeout: 15_000 });
  });

  test("should display the Generate Adversary section", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");

    // Check for the Generate Adversary / Create Operation button area
    const generateAdversary = page.locator(
      "text=Generate Adversary, text=Create Operation"
    );
    await expect(generateAdversary.first()).toBeVisible({ timeout: 15_000 });
  });

  test("should display the adversary selection dropdown", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");

    // The select dropdown for adversaries
    const select = page.locator(
      'select#layer-selection-adversary, select:has(option:has-text("Select an Adversary"))'
    );
    await expect(select.first()).toBeVisible({ timeout: 15_000 });
  });

  test("should have the default 'Select an Adversary (All)' option", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");

    const defaultOption = page.locator(
      'option:has-text("Select an Adversary")'
    );
    await expect(defaultOption.first()).toBeAttached({ timeout: 15_000 });
  });

  test("should embed the ATT&CK Navigator iframe", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");

    const iframe = page.locator(
      'iframe[src*="attack-navigator"], iframe.frame'
    );
    await expect(iframe.first()).toBeVisible({ timeout: 15_000 });
  });

  test("should have the Generate Layer button enabled", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");

    const generateBtn = page.locator(
      'button#generateLayer, button:has-text("Generate Layer")'
    );
    await expect(generateBtn.first()).toBeEnabled({ timeout: 15_000 });
  });
});
