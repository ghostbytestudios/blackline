import { expect, test, type Page } from "@playwright/test";

/**
 * One end-to-end pass over the whole app against a real backend:
 * create a vault, seed demo data, read the dashboard, split a transaction,
 * and import a CSV into a manual account. Tests run in order and share the
 * vault (workers = 1).
 */

const PASSPHRASE = "e2e-passphrase-123";

/** Land on the dashboard whether the vault is locked, unlocked, or brand new —
 * the backend keeps its unlock state across tests (workers = 1). */
async function ensureUnlocked(page: Page) {
  await page.goto("/");
  const password = page.locator('input[type="password"]');
  const dashboard = page.getByRole("heading", { name: "Dashboard" });
  await expect(password.or(dashboard).first()).toBeVisible({ timeout: 15_000 });
  if (await password.isVisible()) {
    await password.fill(PASSPHRASE);
    await page.locator('button[type="submit"]').click();
  }
  await expect(dashboard).toBeVisible({ timeout: 15_000 });
}

test("cold start: create vault, seed demo, dashboard shows real numbers", async ({
  page,
  request,
}) => {
  await page.goto("/");

  // First-run lock screen -> create the vault.
  await expect(page.getByText("Create a passphrase to secure your vault")).toBeVisible();
  await page.getByPlaceholder(/New passphrase/).fill(PASSPHRASE);
  await page.getByRole("button", { name: "Create Vault" }).click();

  // Unlocked shell renders.
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();

  // Seed the demo household (same origin through the vite proxy).
  const seed = await request.post("/api/demo/seed");
  expect(seed.ok()).toBeTruthy();
  await page.reload();

  // KPIs show non-trivial dollar figures, not $0.00 placeholders.
  await expect(page.getByText("Spent this month")).toBeVisible();
  await expect(page.locator("text=/\\$[1-9][\\d,]*\\.\\d{2}/").first()).toBeVisible();
  await expect(page.getByText("Net worth", { exact: true })).toBeVisible();
});

test("split a transaction from the ledger", async ({ page }) => {
  await ensureUnlocked(page);
  await page.getByRole("link", { name: "Transactions" }).click();
  await expect(page.locator("tbody tr").first()).toBeVisible();

  // Open the split editor on the first splittable row.
  await page.locator('button[title="Split across categories"]').first().click();
  const editor = page.locator("tr").filter({ hasText: /adds up|left to assign/ });
  const amounts = editor.locator('input[inputmode="decimal"]');

  // The editor pre-fills [full, 0.00]; read the total and split it 60/40-ish.
  const total = parseFloat(await amounts.nth(0).inputValue());
  const first = (total - 1).toFixed(2);
  await amounts.nth(0).fill(first);
  await amounts.nth(1).fill("1.00");
  await expect(editor.getByText("✓ adds up")).toBeVisible();
  await editor.getByRole("button", { name: "Split", exact: true }).click();

  // The parent now wears the split chip and the parts render under it.
  await expect(page.locator("tbody").getByText("split", { exact: true }).first()).toBeVisible();
});

test("import a CSV statement into a manual account", async ({ page }) => {
  await ensureUnlocked(page);
  await page.goto("/import");
  await expect(page.getByRole("heading", { name: "Import statements" })).toBeVisible();

  // Create a destination account inline.
  await page.getByRole("button", { name: "New manual account" }).click();
  await page.getByPlaceholder(/Account name/).fill("E2E Old Bank");
  await page.getByRole("button", { name: "Create", exact: true }).click();

  // Upload a small CSV; the preview should auto-map the columns.
  await page.locator('input[type="file"]').setInputFiles({
    name: "statement.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(
      "Date,Description,Amount\n2026-06-01,E2E COFFEE SHOP,-4.50\n2026-06-02,E2E BOOKSTORE,-12.00\n",
    ),
  });
  await expect(page.getByText("Map the columns")).toBeVisible();
  await page.getByRole("button", { name: /Import 2 rows/ }).click();
  await expect(page.getByText(/Imported\s*2\s*transactions/)).toBeVisible();
});
