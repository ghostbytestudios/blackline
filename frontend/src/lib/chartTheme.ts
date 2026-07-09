// Shared Recharts styling for the dark navy theme.

export const AXIS_TICK = { fill: "#94a3b8", fontSize: 12 };
export const AXIS_LINE = { stroke: "#1b2740" };
export const GRID_STROKE = "#1b2740";

export const TOOLTIP_STYLE: React.CSSProperties = {
  backgroundColor: "#111a2e",
  border: "1px solid #1b2740",
  borderRadius: 8,
  color: "#e2e8f0",
};

export const TOOLTIP_ITEM_STYLE: React.CSSProperties = { color: "#e2e8f0" };
export const TOOLTIP_LABEL_STYLE: React.CSSProperties = { color: "#94a3b8" };

export const LEGEND_STYLE: React.CSSProperties = { color: "#94a3b8" };

// Series colors tuned for the navy background (reference: cyan vs yellow).
export const SERIES = {
  primary: "#22d3ee", // cyan — "this month" / main line
  compare: "#eab308", // yellow — "last month" / comparison
  income: "#10b981",
  spending: "#f87171",
  accent: "#3b82f6",
};
