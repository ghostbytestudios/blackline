import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ShieldCheck,
  Link2,
  LayoutDashboard,
  Target,
  ArrowLeftRight,
  PieChart,
  LineChart,
  Lightbulb,
  HelpCircle,
  X,
  ChevronLeft,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";

const STORAGE_KEY = "blackline.tutorial.v1";

type Step = {
  icon: LucideIcon;
  title: string;
  body: string;
  route?: string;
  action?: string;
};

const STEPS: Step[] = [
  {
    icon: ShieldCheck,
    title: "Welcome to Blackline",
    body: "Your private, local-first finance dashboard. Everything lives encrypted on this machine — the app only reaches the internet when you choose to sync. Here's a 1-minute tour.",
  },
  {
    icon: Link2,
    title: "Connect your accounts",
    body: "In Settings, link your banks through SimpleFIN (read-only — we never see your bank password). Paste a setup token, hit Connect & Sync, and your accounts flow in.",
    route: "/settings",
    action: "Open Settings",
  },
  {
    icon: LayoutDashboard,
    title: "Your dashboard",
    body: "The Dashboard is your snapshot: net worth, monthly spend vs. income, savings rate, recent activity, and total assets vs. liabilities.",
    route: "/",
    action: "Go to Dashboard",
  },
  {
    icon: Target,
    title: "Accounts & savings goals",
    body: "On Accounts, label each account (checking, savings, investment…) for a clearer picture, and set a savings goal on any account to track your progress with a bar.",
    route: "/accounts",
    action: "Open Accounts",
  },
  {
    icon: ArrowLeftRight,
    title: "Transactions that learn",
    body: "Transactions are auto-categorized. Fix one category and Blackline remembers — it creates a rule and applies it to every similar charge automatically.",
    route: "/transactions",
    action: "Open Transactions",
  },
  {
    icon: PieChart,
    title: "Spending & budgets",
    body: "See where your money goes, then set monthly budgets (edit them inline anytime). Added your income in Settings? Hit ‘Suggest from income’ for a 50/30/20 starting point.",
    route: "/spending",
    action: "Open Spending",
  },
  {
    icon: LineChart,
    title: "Investments & recurring",
    body: "Investments shows your holdings and allocation. Recurring auto-detects your subscriptions so you can catch anything you no longer use.",
    route: "/investments",
    action: "Open Investments",
  },
  {
    icon: Lightbulb,
    title: "Insights & staying secure",
    body: "Insights flags spending spikes, budget overruns, and 50/30/20 guidance. When you step away, lock the vault from the sidebar — you'll need your passphrase to get back in.",
    route: "/insights",
    action: "Open Insights",
  },
];

export default function Tutorial() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
  }, []);

  const markSeen = () => localStorage.setItem(STORAGE_KEY, "1");
  const close = () => {
    markSeen();
    setOpen(false);
  };
  const start = () => {
    setStep(0);
    setOpen(true);
  };

  const launchButton = (
    <button
      onClick={start}
      title="Tutorial"
      className="fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-accent text-white shadow-lg hover:bg-blue-700"
    >
      <HelpCircle className="h-6 w-6" />
    </button>
  );

  if (!open) return launchButton;

  const s = STEPS[step];
  const Icon = s.icon;
  const isLast = step === STEPS.length - 1;

  return (
    <>
      {launchButton}
      <div
        className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 px-4"
        onClick={close}
      >
        <div
          className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-start justify-between">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-accent">
              <Icon className="h-6 w-6" />
            </div>
            <button onClick={close} className="text-slate-400 hover:text-slate-600">
              <X className="h-5 w-5" />
            </button>
          </div>

          <h2 className="mt-4 text-xl font-bold text-slate-900">{s.title}</h2>
          <p className="mt-2 text-sm leading-relaxed text-slate-600">{s.body}</p>

          {s.route && s.action && (
            <button
              onClick={() => {
                navigate(s.route!);
                markSeen();
                setOpen(false);
              }}
              className="mt-4 text-sm font-medium text-accent hover:underline"
            >
              {s.action} →
            </button>
          )}

          <div className="mt-6 flex items-center justify-between">
            <div className="flex gap-1.5">
              {STEPS.map((_, i) => (
                <span
                  key={i}
                  className={`h-1.5 rounded-full transition-all ${
                    i === step ? "w-5 bg-accent" : "w-1.5 bg-slate-200"
                  }`}
                />
              ))}
            </div>
            <div className="flex items-center gap-2">
              {step > 0 && (
                <button
                  onClick={() => setStep((v) => v - 1)}
                  className="flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Back
                </button>
              )}
              {isLast ? (
                <button
                  onClick={close}
                  className="rounded-lg bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Done
                </button>
              ) : (
                <button
                  onClick={() => setStep((v) => v + 1)}
                  className="flex items-center gap-1 rounded-lg bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:bg-blue-700"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>

          {step === 0 && (
            <button
              onClick={close}
              className="mt-3 w-full text-center text-xs text-slate-400 hover:text-slate-600"
            >
              Skip tour
            </button>
          )}
        </div>
      </div>
    </>
  );
}
