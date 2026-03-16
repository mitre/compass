import { test, expect } from "../fixtures/caldera-auth";

test.describe("Compass plugin — layer generation", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");
    // Wait for the compass UI to be ready
    const heading = page.locator("h2:has-text('Compass')");
    await expect(heading).toBeVisible({ timeout: 15_000 });
  });

  test("should generate a layer for all adversaries (default selection)", async ({
    authenticatedPage: page,
  }) => {
    // Ensure default "Select an Adversary (All)" is selected
    const select = page.locator(
      'select#layer-selection-adversary, select:has(option:has-text("Select an Adversary"))'
    );
    await expect(select.first()).toBeVisible();
    const selectedValue = await select.first().inputValue();
    expect(selectedValue).toBe("");

    // Click Generate Layer and expect a download
    const downloadPromise = page.waitForEvent("download", { timeout: 30_000 });
    const generateBtn = page.locator(
      'button#generateLayer, button:has-text("Generate Layer")'
    );
    await generateBtn.first().click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe("layer.json");
  });

  test("downloaded layer file should contain valid JSON with ATT&CK layer schema fields", async ({
    authenticatedPage: page,
  }) => {
    const downloadPromise = page.waitForEvent("download", { timeout: 30_000 });
    const generateBtn = page.locator(
      'button#generateLayer, button:has-text("Generate Layer")'
    );
    await generateBtn.first().click();
    const download = await downloadPromise;

    // Read and parse the downloaded file
    const path = await download.path();
    expect(path).toBeTruthy();

    const fs = await import("fs");
    const content = fs.readFileSync(path!, "utf-8");
    const layer = JSON.parse(content);

    // ATT&CK Navigator layer schema fields
    expect(layer).toHaveProperty("name");
    expect(layer).toHaveProperty("versions");
    expect(layer).toHaveProperty("domain");
    expect(layer).toHaveProperty("techniques");
    expect(Array.isArray(layer.techniques)).toBe(true);
  });

  test("should populate the adversary dropdown with available adversaries", async ({
    authenticatedPage: page,
  }) => {
    const select = page.locator(
      'select#layer-selection-adversary, select:has(option:has-text("Select an Adversary"))'
    );
    await expect(select.first()).toBeVisible();

    // Count options — at minimum the default "All" option
    const options = select.first().locator("option");
    const count = await options.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test("should generate a layer for a specific adversary when selected", async ({
    authenticatedPage: page,
  }) => {
    const select = page.locator(
      'select#layer-selection-adversary, select:has(option:has-text("Select an Adversary"))'
    );
    await expect(select.first()).toBeVisible();

    // Get all options
    const options = select.first().locator("option");
    const count = await options.count();

    // Skip if only the default option exists (no adversaries loaded)
    test.skip(count < 2, "No adversaries available to select");

    // Select the first non-default adversary
    const secondOption = options.nth(1);
    const value = await secondOption.getAttribute("value");
    await select.first().selectOption(value!);

    // Generate layer
    const downloadPromise = page.waitForEvent("download", { timeout: 30_000 });
    const generateBtn = page.locator(
      'button#generateLayer, button:has-text("Generate Layer")'
    );
    await generateBtn.first().click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toBe("layer.json");
  });

  test("layer generated for specific adversary should contain technique entries", async ({
    authenticatedPage: page,
  }) => {
    const select = page.locator(
      'select#layer-selection-adversary, select:has(option:has-text("Select an Adversary"))'
    );
    const options = select.first().locator("option");
    const count = await options.count();

    test.skip(count < 2, "No adversaries available to select");

    const secondOption = options.nth(1);
    const value = await secondOption.getAttribute("value");
    await select.first().selectOption(value!);

    const downloadPromise = page.waitForEvent("download", { timeout: 30_000 });
    const generateBtn = page.locator(
      'button#generateLayer, button:has-text("Generate Layer")'
    );
    await generateBtn.first().click();
    const download = await downloadPromise;

    const path = await download.path();
    const fs = await import("fs");
    const content = fs.readFileSync(path!, "utf-8");
    const layer = JSON.parse(content);

    expect(layer.techniques.length).toBeGreaterThan(0);
    // Each technique should have a techniqueID
    for (const tech of layer.techniques) {
      expect(tech).toHaveProperty("techniqueID");
    }
  });
});
