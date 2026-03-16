import { test, expect } from "../fixtures/caldera-auth";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";

/**
 * Helper to create a minimal valid ATT&CK Navigator layer JSON file for upload.
 */
function createSampleLayerFile(): string {
  const layer = {
    name: "E2E Test Layer",
    versions: {
      attack: "14",
      navigator: "4.9.1",
      layer: "4.5",
    },
    domain: "enterprise-attack",
    description: "Test layer for E2E adversary import",
    techniques: [
      {
        techniqueID: "T1059",
        tactic: "execution",
        score: 1,
        color: "#e60d0d",
        comment: "Test technique",
        enabled: true,
      },
      {
        techniqueID: "T1071",
        tactic: "command-and-control",
        score: 1,
        color: "#e60d0d",
        comment: "Test technique",
        enabled: true,
      },
    ],
    gradient: {
      colors: ["#ffffff", "#ff6666"],
      minValue: 0,
      maxValue: 1,
    },
    legendItems: [],
    metadata: [],
    links: [],
    showTacticRowBackground: false,
    tacticRowBackground: "#dddddd",
    selectTechniquesAcrossTactics: true,
    selectSubtechniquesWithParent: false,
  };

  const tmpDir = os.tmpdir();
  const filePath = path.join(tmpDir, "e2e-test-layer.json");
  fs.writeFileSync(filePath, JSON.stringify(layer, null, 2));
  return filePath;
}

test.describe("Compass plugin — adversary import from layer", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto("/#/plugins/compass");
    await page.waitForLoadState("networkidle");
    const heading = page.locator("h2:has-text('Compass')");
    await expect(heading).toBeVisible({ timeout: 15_000 });
  });

  test("should have a file upload input for adversary layer import", async ({
    authenticatedPage: page,
  }) => {
    const fileInput = page.locator(
      'input#generateAdversary[type="file"], input[type="file"]'
    );
    // The input is hidden but present in the DOM
    await expect(fileInput.first()).toBeAttached({ timeout: 10_000 });
  });

  test("should have a Create Operation button for adversary upload", async ({
    authenticatedPage: page,
  }) => {
    const uploadBtn = page.locator(
      'button:has-text("Create Operation"), label:has-text("Create Operation")'
    );
    await expect(uploadBtn.first()).toBeVisible({ timeout: 10_000 });
  });

  test("should upload a layer file and trigger adversary creation", async ({
    authenticatedPage: page,
  }) => {
    const layerFilePath = createSampleLayerFile();

    // Set the file on the hidden file input
    const fileInput = page.locator('input#generateAdversary[type="file"]');
    await fileInput.setInputFiles(layerFilePath);

    // Wait for the API response — either a modal appears or we get a response
    // The modal should appear with "Adversary Created" title
    const modal = page.locator(
      '.modal.is-active, .modal-card-title:has-text("Adversary Created")'
    );
    await expect(modal.first()).toBeVisible({ timeout: 20_000 });

    // Clean up
    fs.unlinkSync(layerFilePath);
  });

  test("should show adversary name in the creation modal", async ({
    authenticatedPage: page,
  }) => {
    const layerFilePath = createSampleLayerFile();

    const fileInput = page.locator('input#generateAdversary[type="file"]');
    await fileInput.setInputFiles(layerFilePath);

    // Wait for modal
    const modalTitle = page.locator(
      '.modal-card-title:has-text("Adversary Created")'
    );
    await expect(modalTitle).toBeVisible({ timeout: 20_000 });

    // The adversary name should be shown (from layer name "E2E Test Layer")
    const nameDisplay = page.locator(".modal-card-head h3").first();
    await expect(nameDisplay).toBeVisible();

    fs.unlinkSync(layerFilePath);
  });

  test("should display unmatched techniques table in creation modal", async ({
    authenticatedPage: page,
  }) => {
    const layerFilePath = createSampleLayerFile();

    const fileInput = page.locator('input#generateAdversary[type="file"]');
    await fileInput.setInputFiles(layerFilePath);

    const modalTitle = page.locator(
      '.modal-card-title:has-text("Adversary Created")'
    );
    await expect(modalTitle).toBeVisible({ timeout: 20_000 });

    // Check for the unmatched techniques table headers
    const tacticHeader = page.locator("th:has-text('Tactic')");
    const techniqueHeader = page.locator("th:has-text('Technique ID')");
    await expect(tacticHeader.first()).toBeVisible();
    await expect(techniqueHeader.first()).toBeVisible();

    fs.unlinkSync(layerFilePath);
  });

  test("should close the adversary creation modal with the Close button", async ({
    authenticatedPage: page,
  }) => {
    const layerFilePath = createSampleLayerFile();

    const fileInput = page.locator('input#generateAdversary[type="file"]');
    await fileInput.setInputFiles(layerFilePath);

    const modal = page.locator(".modal.is-active");
    await expect(modal.first()).toBeVisible({ timeout: 20_000 });

    // Click Close button
    const closeBtn = page.locator(
      '.modal-card-foot button:has-text("Close")'
    );
    await closeBtn.click();

    // Modal should disappear
    await expect(modal).not.toBeVisible({ timeout: 5_000 });

    fs.unlinkSync(layerFilePath);
  });

  test("should close the adversary creation modal by clicking the background overlay", async ({
    authenticatedPage: page,
  }) => {
    const layerFilePath = createSampleLayerFile();

    const fileInput = page.locator('input#generateAdversary[type="file"]');
    await fileInput.setInputFiles(layerFilePath);

    const modal = page.locator(".modal.is-active");
    await expect(modal.first()).toBeVisible({ timeout: 20_000 });

    // Click the modal background overlay
    const overlay = page.locator(".modal-background");
    await overlay.first().click({ force: true });

    await expect(modal).not.toBeVisible({ timeout: 5_000 });

    fs.unlinkSync(layerFilePath);
  });
});
