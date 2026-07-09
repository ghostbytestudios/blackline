import { Navigate, Route, Routes } from "react-router-dom";
import { useStatus } from "./hooks/useApi";
import Sidebar from "./components/Sidebar";
import LockScreen from "./components/LockScreen";
import Tutorial from "./components/Tutorial";
import Dashboard from "./pages/Dashboard";
import Accounts from "./pages/Accounts";
import Transactions from "./pages/Transactions";
import Import from "./pages/Import";
import Spending from "./pages/Spending";
import Merchants from "./pages/Merchants";
import Goals from "./pages/Goals";
import Investments from "./pages/Investments";
import Recurring from "./pages/Recurring";
import NetWorth from "./pages/NetWorth";
import Insights from "./pages/Insights";
import Settings from "./pages/Settings";

export default function App() {
  const { data: status, isLoading, isError } = useStatus();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-900 text-slate-400">
        Connecting to local vault…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-900 px-6 text-center text-slate-300">
        <div>
          <p className="font-semibold text-white">Cannot reach the backend.</p>
          <p className="mt-2 text-sm">
            Start it with{" "}
            <code className="rounded bg-ink-700 px-1.5 py-0.5">uvicorn app.main:app</code> on
            127.0.0.1:8000.
          </p>
        </div>
      </div>
    );
  }

  if (!status?.unlocked) return <LockScreen />;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto bg-ink-900 px-8 py-7">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/transactions" element={<Transactions />} />
          <Route path="/import" element={<Import />} />
          <Route path="/spending" element={<Spending />} />
          <Route path="/merchants" element={<Merchants />} />
          <Route path="/goals" element={<Goals />} />
          <Route path="/investments" element={<Investments />} />
          <Route path="/recurring" element={<Recurring />} />
          <Route path="/net-worth" element={<NetWorth />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <Tutorial />
    </div>
  );
}
