import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Wallet,
  ArrowLeftRight,
  PieChart,
  LineChart,
  Repeat,
  TrendingUp,
  Lightbulb,
  Settings,
  ShieldCheck,
  Lock,
} from "lucide-react";
import { useLock } from "../hooks/useApi";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/accounts", label: "Accounts", icon: Wallet },
  { to: "/transactions", label: "Transactions", icon: ArrowLeftRight },
  { to: "/spending", label: "Spending", icon: PieChart },
  { to: "/investments", label: "Investments", icon: LineChart },
  { to: "/recurring", label: "Recurring", icon: Repeat },
  { to: "/net-worth", label: "Net Worth", icon: TrendingUp },
  { to: "/insights", label: "Insights", icon: Lightbulb },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const lock = useLock();
  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col bg-ink-900 text-slate-300">
      <div className="flex items-center gap-2 px-5 py-5 text-white">
        <ShieldCheck className="h-6 w-6 text-accent-soft" />
        <span className="text-lg font-bold tracking-tight">VaultCFO</span>
      </div>

      <div className="px-5 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Menu
      </div>
      <nav className="flex-1 space-y-1 px-3">
        {nav.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? "bg-ink-700 text-white"
                  : "text-slate-400 hover:bg-ink-800 hover:text-slate-200"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon className={`h-5 w-5 ${isActive ? "text-accent-soft" : ""}`} />
                {label}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="p-3">
        <button
          onClick={() => lock.mutate()}
          className="flex w-full items-center justify-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-400 hover:bg-ink-800 hover:text-white"
        >
          <Lock className="h-5 w-5" />
          Lock Vault
        </button>
      </div>
      <div className="border-t border-ink-700 px-3 py-3 text-center text-xs text-slate-500">
        Powered by GhostByte Studios
      </div>
    </aside>
  );
}
