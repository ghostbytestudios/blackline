import { describe, expect, it } from "vitest";
import { buildMapping, rolesFromSuggestion, type Role } from "./Import";

describe("rolesFromSuggestion", () => {
  it("places suggested roles at their column indexes", () => {
    const roles = rolesFromSuggestion(
      { date: 0, amount: 2, description: 1, date_format: "%Y-%m-%d" },
      3,
    );
    expect(roles).toEqual(["date", "description", "amount"]);
  });

  it("ignores suggestions that point past the header width", () => {
    const roles = rolesFromSuggestion({ date: 0, amount: 9 }, 2);
    expect(roles).toEqual(["date", "ignore"]);
  });

  it("returns all-ignore when there is no suggestion", () => {
    expect(rolesFromSuggestion(null, 2)).toEqual(["ignore", "ignore"]);
  });
});

describe("buildMapping", () => {
  it("round-trips roles into a mapping with format and flip", () => {
    const roles: Role[] = ["date", "payee", "amount", "memo"];
    expect(buildMapping(roles, "%m/%d/%Y", true)).toEqual({
      date: 0,
      amount: 2,
      debit: null,
      credit: null,
      payee: 1,
      description: null,
      memo: 3,
      date_format: "%m/%d/%Y",
      flip_amounts: true,
    });
  });

  it("accepts debit/credit columns instead of a signed amount", () => {
    const m = buildMapping(["date", "debit", "credit"], null, false);
    expect(m).not.toBeNull();
    expect([m!.debit, m!.credit, m!.amount]).toEqual([1, 2, null]);
  });

  it("requires a date column", () => {
    expect(buildMapping(["ignore", "amount"], null, false)).toBeNull();
  });

  it("requires some amount column", () => {
    expect(buildMapping(["date", "payee"], null, false)).toBeNull();
  });
});
