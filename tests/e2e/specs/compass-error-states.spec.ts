import { test, expect } from "../fixtures/caldera-auth";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";

test.describe("Compass plugin — error states and edge cases", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");
    const heading = page.locator("h2:has-text('Compass')");
    await expect(heading).toBeVisible({ timeout: 15_000 });
  });

  test("should handle layer generation API failure gracefully", async ({
    authenticatedPage: page,
  }) => {
    // Intercept the layer generation API and force a 500 error
    await page.route("**/plugin/compass/layer", (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: "Internal Server Error" }),
      })
    );

    const generateBtn = page.locator(
      'button#generateLayer, button:has-text("Generate Layer")'
    );
    await generateBtn.first().click();

    // The page should remain functional (no crash)
    const heading = page.locator("h2:has-text('Compass')");
    await expect(heading).toBeVisible({ timeout: 5_000 });

    // No download should have occurred
    let downloadTriggered = false;
    page.on("download", () => {
      downloadTriggered = true;
    });
    await page.waitForTimeout(2_000);
    expect(downloadTriggered).toBe(false);
  });

  test("should handle adversary upload API failure gracefully", async ({
    authenticatedPage: page,
  }) => {
    // Intercept the adversary upload API and force a 500 error
    await page.route("**/plugin/compass/adversary", (route) =>
      route.fulfill({
        status: 500,
        contentType: "application/json",
        body: JSON.stringify({ error: "Internal Server Error" }),
      })
    );

    // Create a minimal layer file to upload
    const tmpDir = os.tmpdir();
    const filePath = path.join(tmpDir, "e2e-error-test-layer.json");
    fs.writeFileSync(
      filePath,
      JSON.stringify({
        name: "Error Test",
        techniques: [{ techniqueID: "T1059", tactic: "execution" }],
      })
    );

    const fileInput = page.locator('input#generateAdversary[type="file"]');
    await fileInput.setInputFiles(filePath);

    // The page should remain functional (no unhandled crash)
    await page.waitForTimeout(3_000);
    const heading = page.locator("h2:has-text('Compass')");
    await expect(heading).toBeVisible();

    // No modal should appear
    const modal = page.locator(".modal.is-active");
    await expect(modal).not.toBeVisible();

    fs.unlinkSync(filePath);
  });

  test("should handle uploading an invalid (non-JSON) file gracefully", async ({
    authenticatedPage: page,
  }) => {
    // Create a non-JSON file
    const tmpDir = os.tmpdir();
    const filePath = path.join(tmpDir, "e2e-invalid-file.txt");
    fs.writeFileSync(filePath, "This is not valid JSON layer data");

    const fileInput = page.locator('input#generateAdversary[type="file"]');
    await fileInput.setInputFiles(filePath);

    // Page should remain stable
    await page.waitForTimeout(3_000);
    const heading = page.locator("h2:has-text('Compass')");
    await expect(heading).toBeVisible();

    fs.unlinkSync(filePath);
  });

  test("should handle network timeout for layer generation gracefully", async ({
    authenticatedPage: page,
  }) => {
    // Simulate a network timeout by aborting the request
    await page.route("**/plugin/compass/layer", (route) => route.abort());

    const generateBtn = page.locator(
      'button#generateLayer, button:has-text("Generate Layer")'
    );
    await generateBtn.first().click();

    // The page should still be functional
    await page.waitForTimeout(2_000);
    const heading = page.locator("h2:has-text('Compass')");
    await expect(heading).toBeVisible();
  });

  test("should not show the creation modal before any upload is performed", async ({
    authenticatedPage: page,
  }) => {
    // Verify no modal is visible initially
    const modal = page.locator(".modal.is-active");
    await expect(modal).not.toBeVisible();
  });

  test("should preserve UI state after a failed layer generation", async ({
    authenticatedPage: page,
  }) => {
    // Block the API
    await page.route("**/plugin/compass/layer", (route) =>
      route.fulfill({ status: 500, body: "error" })
    );

    const select = page.locator(
      'select#layer-selection-adversary, select:has(option:has-text("Select an Adversary"))'
    );
    const generateBtn = page.locator(
      'button#generateLayer, button:has-text("Generate Layer")'
    );

    await generateBtn.first().click();
    await page.waitForTimeout(2_000);

    // Dropdown should still be visible and functional
    await expect(select.first()).toBeVisible();
    await expect(generateBtn.first()).toBeEnabled();

    // The iframe should still be present
    const iframe = page.locator(
      'iframe[src*="attack-navigator"], iframe.frame'
    );
    await expect(iframe.first()).toBeVisible();
  });
});
