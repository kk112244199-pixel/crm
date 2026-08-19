"use client";

interface HealthBadgeProps {
  score?: number | null;
  status?: string | null;
  showScore?: boolean;
  size?: "sm" | "md" | "lg";
}

const STATUS_CONFIG = {
  GREEN:  { dot: "bg-emerald-500", bg: "bg-emerald-50",  text: "text-emerald-700", border: "border-emerald-200", label: "健康" },
  YELLOW: { dot: "bg-amber-400",   bg: "bg-amber-50",    text: "text-amber-700",   border: "border-amber-200",   label: "警示" },
  RED:    { dot: "bg-red-500",     bg: "bg-red-50",       text: "text-red-700",     border: "border-red-200",     label: "风险" },
};

export function HealthBadge({ score, status, showScore = true, size = "md" }: HealthBadgeProps) {
  const s = (status as keyof typeof STATUS_CONFIG) || "GREEN";
  const cfg = STATUS_CONFIG[s] || STATUS_CONFIG.GREEN;
  const sizeClass = size === "sm" ? "text-xs px-2 py-0.5 gap-1" : size === "lg" ? "text-sm px-3 py-1.5 gap-2" : "text-xs px-2.5 py-1 gap-1.5";
  const dotSize = size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2";

  return (
    <span className={`inline-flex items-center rounded-full border font-medium ${cfg.bg} ${cfg.text} ${cfg.border} ${sizeClass}`}>
      <span className={`rounded-full shrink-0 ${cfg.dot} ${dotSize}`} />
      {cfg.label}
      {showScore && score != null && (
        <span className="ml-1 opacity-70">{score}</span>
      )}
    </span>
  );
}

interface RuleCardProps {
  ruleId: string;
  title: string;
  description: string;
  severity: string;
  deduction: number;
}

const SEVERITY_COLOR = {
  HIGH:   "border-l-red-500   bg-red-50",
  MEDIUM: "border-l-amber-400 bg-amber-50",
  LOW:    "border-l-slate-300 bg-slate-50",
};

export function RuleCard({ ruleId, title, description, severity, deduction }: RuleCardProps) {
  const color = SEVERITY_COLOR[severity as keyof typeof SEVERITY_COLOR] || SEVERITY_COLOR.LOW;
  return (
    <div className={`border-l-4 rounded-r-lg px-4 py-3 ${color}`}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-bold text-slate-500">{ruleId}</span>
          <span className="text-sm font-semibold text-slate-800">{title}</span>
        </div>
        <span className="text-xs font-bold text-red-600">-{deduction}</span>
      </div>
      <p className="text-xs text-slate-600">{description}</p>
    </div>
  );
}
