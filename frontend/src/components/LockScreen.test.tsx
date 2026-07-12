import "@testing-library/jest-dom/vitest";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import LockScreen from "./LockScreen";

const mockUnlock = vi.fn();
const mockReset = vi.fn();
let status: { initialized: boolean; unlocked: boolean } = { initialized: true, unlocked: false };

vi.mock("../hooks/useApi", () => ({
  useStatus: () => ({ data: status }),
  useUnlock: () => ({ mutate: mockUnlock, isPending: false, error: null }),
  useResetVault: () => ({ mutate: mockReset, isPending: false, error: null }),
}));

beforeEach(() => {
  mockUnlock.mockClear();
  mockReset.mockClear();
  status = { initialized: true, unlocked: false };
});

describe("LockScreen", () => {
  it("keeps Unlock disabled until the passphrase is 8+ characters", async () => {
    render(<LockScreen />);
    const button = screen.getByRole("button", { name: "Unlock" });
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByPlaceholderText("Passphrase"), "short");
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByPlaceholderText("Passphrase"), "-enough");
    expect(button).toBeEnabled();
  });

  it("submits the passphrase", async () => {
    render(<LockScreen />);
    await userEvent.type(screen.getByPlaceholderText("Passphrase"), "correct horse battery");
    await userEvent.click(screen.getByRole("button", { name: "Unlock" }));
    expect(mockUnlock).toHaveBeenCalledWith("correct horse battery");
  });

  it("shows first-run copy for an uninitialized vault", () => {
    status = { initialized: false, unlocked: false };
    render(<LockScreen />);
    expect(screen.getByText(/Create a passphrase/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Vault" })).toBeInTheDocument();
    // No reset entry point before a vault exists.
    expect(screen.queryByText(/Forgot your passphrase/)).not.toBeInTheDocument();
  });

  it("arms vault destruction only after the exact confirmation phrase", async () => {
    render(<LockScreen />);
    await userEvent.click(screen.getByText("Forgot your passphrase?"));
    const destroy = screen.getByRole("button", { name: /Destroy vault/ });
    expect(destroy).toBeDisabled();
    const confirm = screen.getByPlaceholderText("DELETE MY DATA");
    await userEvent.type(confirm, "delete my data"); // wrong case
    expect(destroy).toBeDisabled();
    await userEvent.clear(confirm);
    await userEvent.type(confirm, "DELETE MY DATA");
    expect(destroy).toBeEnabled();
    await userEvent.click(destroy);
    expect(mockReset).toHaveBeenCalledWith("DELETE MY DATA");
  });
});
