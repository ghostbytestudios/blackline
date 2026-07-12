import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SplitRow } from "./Transactions";
import type { Transaction } from "../lib/types";

const mockSplit = vi.fn();
vi.mock("../hooks/useApi", () => ({
  useSplitTransaction: () => ({ mutate: mockSplit, isPending: false }),
  useUnsplitTransaction: () => ({ mutate: vi.fn(), isPending: false }),
  useAccounts: () => ({ data: [] }),
  useAnnotateTransaction: () => ({ mutate: vi.fn(), isPending: false }),
  useSetCategory: () => ({ mutate: vi.fn(), isPending: false }),
  useTransactions: () => ({ data: [], isLoading: false }),
}));

const txn: Transaction = {
  id: 7,
  account_id: 1,
  posted_at: "2026-07-01T00:00:00Z",
  amount_minor: -10_000, // a $100 charge
  description: "COSTCO",
  payee: "Costco",
  pending: false,
  category: "shopping",
  category_source: "auto",
  note: null,
  tags: [],
  transfer_peer_id: null,
  parent_id: null,
  is_split_parent: false,
};

function renderRow() {
  return render(
    <table>
      <tbody>
        <SplitRow txn={txn} children={[]} onDone={vi.fn()} />
      </tbody>
    </table>,
  );
}

beforeEach(() => mockSplit.mockClear());

describe("SplitRow", () => {
  it("starts with the full amount assigned but a zero part, so saving is blocked", () => {
    renderRow();
    expect(screen.getByText("✓ adds up")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Split" })).toBeDisabled();
  });

  it("shows the live remainder while amounts don't add up", async () => {
    renderRow();
    const first = screen.getByDisplayValue("100.00");
    await userEvent.clear(first);
    await userEvent.type(first, "60.00");
    expect(screen.getByText(/left to assign/)).toHaveTextContent("$40.00 left to assign");
    expect(screen.getByRole("button", { name: "Split" })).toBeDisabled();
  });

  it("saves sign-corrected minor units when the parts add up exactly", async () => {
    renderRow();
    const first = screen.getByDisplayValue("100.00");
    const second = screen.getByDisplayValue("0.00");
    await userEvent.clear(first);
    await userEvent.type(first, "75.00");
    await userEvent.clear(second);
    await userEvent.type(second, "25.00");
    const save = screen.getByRole("button", { name: "Split" });
    expect(save).toBeEnabled();
    await userEvent.click(save);
    expect(mockSplit).toHaveBeenCalledWith(
      {
        id: 7,
        parts: [
          { category: "shopping", amount_minor: -7_500 },
          { category: "uncategorized", amount_minor: -2_500 },
        ],
      },
      expect.anything(),
    );
  });

  it("over-assignment is flagged, not saved", async () => {
    renderRow();
    const second = screen.getByDisplayValue("0.00");
    await userEvent.clear(second);
    await userEvent.type(second, "5.00"); // 100 + 5 = 105 > 100
    expect(screen.getByText(/left to assign/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Split" })).toBeDisabled();
    expect(mockSplit).not.toHaveBeenCalled();
  });
});
