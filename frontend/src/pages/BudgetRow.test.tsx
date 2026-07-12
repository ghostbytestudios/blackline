import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BudgetRow } from "./Spending";
import type { BudgetStatus } from "../lib/types";

const mockSetBudget = vi.fn();
vi.mock("../hooks/useApi", () => ({
  useSetBudget: () => ({ mutate: mockSetBudget, isPending: false }),
  useDeleteBudget: () => ({ mutate: vi.fn(), isPending: false }),
  useBudgetHistory: () => ({ data: [] }),
  useBudgets: () => ({ data: [] }),
  useInsights: () => ({ data: undefined }),
  useProfile: () => ({ data: undefined }),
  useSetProfile: () => ({ mutate: vi.fn(), isPending: false }),
  useSuggestBudgets: () => ({ mutate: vi.fn(), isPending: false }),
}));

const budget: BudgetStatus = {
  category: "groceries",
  limit_minor: 50_000,
  spent_minor: 20_000,
  rollover: false,
  carryover_minor: 0,
  effective_limit_minor: 50_000,
};

beforeEach(() => mockSetBudget.mockClear());

describe("BudgetRow", () => {
  it("commits an edited limit in minor units on blur", async () => {
    render(<BudgetRow budget={budget} />);
    const input = screen.getByDisplayValue("500");
    await userEvent.clear(input);
    await userEvent.type(input, "625.5");
    await userEvent.tab(); // blur commits
    expect(mockSetBudget).toHaveBeenCalledWith({
      category: "groceries",
      limit_minor: 62_550,
      rollover: false,
    });
  });

  it("reverts invalid input without saving", async () => {
    render(<BudgetRow budget={budget} />);
    const input = screen.getByDisplayValue("500");
    await userEvent.clear(input);
    await userEvent.type(input, "not-money");
    await userEvent.tab();
    expect(mockSetBudget).not.toHaveBeenCalled();
    expect(screen.getByDisplayValue("500")).toBeInTheDocument();
  });

  it("does not save when the value is unchanged", async () => {
    render(<BudgetRow budget={budget} />);
    const input = screen.getByDisplayValue("500");
    await userEvent.click(input);
    await userEvent.tab();
    expect(mockSetBudget).not.toHaveBeenCalled();
  });
});
