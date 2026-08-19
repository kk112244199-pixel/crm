"use client";
import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/api-client";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ContactUpdate {
  full_name: string;
  title?: string;
  role_in_deal?: string;
  influence_level?: number;
  notes?: string;
  is_new?: boolean;
}
interface Task {
  title: string;
  owner?: string;
  due_date?: string;
  priority: string;
  type: string;
}
interface RiskFlag {
  rule: string;
  description: string;
  severity: string;
}
interface OppUpdate {
  pain_points?: string;
  competitor?: string;
  budget_status?: string;
  amount_hint?: number;
  close_date_hint?: string;
  meddic_gaps?: Record<string, string | null>;
}
interface Proposal {
  contact_updates: ContactUpdate[];
  new_contacts: ContactUpdate[];
  opportunity_updates: OppUpdate;
  tasks: Task[];
  risk_flags: RiskFlag[];
  reasoning: string;
  evidence: Array<{ agent: string; snippet: string; field: string }>;
  stage_hint?: string;
  structured_summary?: string;
}
interface ExtractResponse {
  pending_action_id: string;
  proposal: Proposal;
  agents_activated: string[];
  plan_reasoning: string;
  errors: Array<{ agent: string; error: string }>;
}

// ── Severity colors ───────────────────────────────────────────────────────────
const severityColor = { HIGH: "text-red-600 bg-red-50", MEDIUM: "text-amber-600 bg-amber-50", LOW: "text-green-600 bg-green-50" } as const;
const priorityColor = { HIGH: "text-red-600", MEDIUM: "text-amber-500", LOW: "text-slate-500" } as const;

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ExtractPage() {
  const { id: opportunityId } = useParams<{ id: string }>();
  const router = useRouter();

  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ExtractResponse | null>(null);
  const [accepted, setAccepted] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState<"approved" | "rejected" | null>(null);

  const runExtract = async () => {
    if (!text.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await api.post<ExtractResponse>("/activities/extract", {
        opportunity_id: opportunityId,
        canonical_text: text,
      });
      setResult(res.data);
      // Default accept all
      const defaults: Record<string, boolean> = {};
      res.data.proposal.contact_updates.forEach(c => { defaults[`contact_${c.full_name}`] = true; });
      res.data.proposal.new_contacts.forEach(c => { defaults[`new_contact_${c.full_name}`] = true; });
      Object.keys(res.data.proposal.opportunity_updates || {}).forEach(k => { defaults[k] = true; });
      res.data.proposal.tasks.forEach((t, i) => { defaults[`task_${i}`] = true; });
      setAccepted(defaults);
    } finally {
      setLoading(false);
    }
  };

  const toggle = (key: string) => setAccepted(p => ({ ...p, [key]: !p[key] }));

  const handleConfirm = async () => {
    if (!result) return;
    setSubmitting(true);
    const items = Object.entries(accepted).map(([field, a]) => ({ field, accepted: a }));
    try {
      await api.post(`/pending-actions/${result.pending_action_id}/confirm`, { items });
      setDone("approved");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!result) return;
    setSubmitting(true);
    try {
      await api.post(`/pending-actions/${result.pending_action_id}/reject`, { note: "用户拒绝" });
      setDone("rejected");
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          {done === "approved"
            ? <p className="text-2xl font-semibold text-emerald-600">✓ 已写回成功</p>
            : <p className="text-2xl font-semibold text-slate-500">已拒绝，仅保留原始纪要</p>
          }
          <button onClick={() => router.back()} className="mt-6 px-4 py-2 rounded bg-slate-100 hover:bg-slate-200 text-sm">返回</button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      <h1 className="text-2xl font-bold text-slate-800">会议纪要智能写回</h1>

      {/* Input */}
      <div className="space-y-3">
        <label className="block text-sm font-medium text-slate-700">粘贴会议纪要</label>
        <textarea
          value={text}
          onChange={e => setText(e.target.value)}
          rows={10}
          className="w-full rounded-lg border border-slate-200 px-4 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-slate-50"
          placeholder="粘贴会议纪要全文，AI 将自动分析联系人、商机字段、风险和任务…"
        />
        <button
          onClick={runExtract}
          disabled={loading || !text.trim()}
          className="px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
        >
          {loading ? "分析中…" : "AI 智能分析"}
        </button>
      </div>

      {/* Agents activated */}
      {result && (
        <div className="flex flex-wrap gap-2 text-xs">
          {result.agents_activated.map(a => (
            <span key={a} className="px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">
              {a}
            </span>
          ))}
          {result.errors.map((e, i) => (
            <span key={i} className="px-2 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-100">
              ⚠ {e.agent} 降级
            </span>
          ))}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          {/* Reasoning */}
          {result.proposal.reasoning && (
            <Section title="综合分析">
              <p className="text-sm text-slate-600 leading-relaxed">{result.proposal.reasoning}</p>
            </Section>
          )}

          {/* Opportunity updates */}
          {Object.keys(result.proposal.opportunity_updates || {}).length > 0 && (
            <Section title="商机字段更新">
              {Object.entries(result.proposal.opportunity_updates).map(([k, v]) => {
                if (!v || k === "meddic_gaps") return null;
                const key = k;
                return (
                  <DiffRow
                    key={k}
                    field={FIELD_LABELS[k] || k}
                    value={String(v)}
                    accepted={accepted[key] ?? true}
                    onToggle={() => toggle(key)}
                  />
                );
              })}
            </Section>
          )}

          {/* MEDDIC gaps */}
          {result.proposal.opportunity_updates?.meddic_gaps && (
            <Section title="MEDDIC 缺口">
              <div className="space-y-1">
                {Object.entries(result.proposal.opportunity_updates.meddic_gaps).map(([k, v]) => (
                  <div key={k} className="flex gap-2 text-sm">
                    <span className="font-medium w-36 shrink-0 text-slate-600">{MEDDIC_LABELS[k] || k}</span>
                    <span className={v ? "text-amber-600" : "text-slate-400"}>{v || "✓ 已覆盖"}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Contact updates */}
          {result.proposal.contact_updates.length > 0 && (
            <Section title="联系人更新">
              {result.proposal.contact_updates.map((c, i) => (
                <DiffRow
                  key={i}
                  field={c.full_name}
                  value={`${c.title || ""} · ${ROLE_LABELS[c.role_in_deal || ""] || c.role_in_deal || ""} · 影响力 ${c.influence_level ?? "-"}`}
                  badge={c.notes}
                  accepted={accepted[`contact_${c.full_name}`] ?? true}
                  onToggle={() => toggle(`contact_${c.full_name}`)}
                />
              ))}
            </Section>
          )}

          {/* New contacts */}
          {result.proposal.new_contacts.length > 0 && (
            <Section title="新联系人">
              {result.proposal.new_contacts.map((c, i) => (
                <DiffRow
                  key={i}
                  field={c.full_name}
                  value={`${c.title || ""} · ${ROLE_LABELS[c.role_in_deal || ""] || c.role_in_deal || ""}`}
                  isNew
                  accepted={accepted[`new_contact_${c.full_name}`] ?? true}
                  onToggle={() => toggle(`new_contact_${c.full_name}`)}
                />
              ))}
            </Section>
          )}

          {/* Tasks */}
          {result.proposal.tasks.length > 0 && (
            <Section title="待办任务">
              <div className="space-y-2">
                {result.proposal.tasks.map((t, i) => (
                  <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
                    <input
                      type="checkbox"
                      checked={accepted[`task_${i}`] ?? true}
                      onChange={() => toggle(`task_${i}`)}
                      className="mt-0.5"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-800">{t.title}</span>
                        <span className={`text-xs font-medium ${priorityColor[t.priority as keyof typeof priorityColor] || ""}`}>{t.priority}</span>
                      </div>
                      <div className="text-xs text-slate-500 mt-0.5">
                        {t.owner && <span>{t.owner}</span>}
                        {t.due_date && <span className="ml-2">截止 {t.due_date}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Risk flags */}
          {result.proposal.risk_flags.length > 0 && (
            <Section title="风险预警">
              <div className="space-y-2">
                {result.proposal.risk_flags.map((r, i) => (
                  <div key={i} className={`flex items-start gap-3 p-3 rounded-lg border text-sm ${severityColor[r.severity as keyof typeof severityColor] || "bg-slate-50 text-slate-600"}`}>
                    <span className="font-mono font-bold shrink-0">{r.rule}</span>
                    <span>{r.description}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Stage hint */}
          {result.proposal.stage_hint && (
            <div className="text-sm text-slate-500 flex items-center gap-2">
              <span>建议阶段：</span>
              <span className="font-medium text-indigo-600">{result.proposal.stage_hint}</span>
              <span className="text-xs text-slate-400">（仅建议，不自动修改）</span>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={handleConfirm}
              disabled={submitting}
              className="px-6 py-2.5 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50 transition-colors"
            >
              {submitting ? "写入中…" : "确认写回"}
            </button>
            <button
              onClick={handleReject}
              disabled={submitting}
              className="px-6 py-2.5 rounded-lg border border-slate-200 text-slate-600 text-sm hover:bg-slate-50 disabled:opacity-50 transition-colors"
            >
              拒绝
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function DiffRow({
  field, value, accepted, onToggle, isNew, badge,
}: {
  field: string; value: string; accepted: boolean; onToggle: () => void; isNew?: boolean; badge?: string;
}) {
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${accepted ? "bg-white border-emerald-100" : "bg-slate-50 border-slate-100 opacity-50"}`}>
      <input type="checkbox" checked={accepted} onChange={onToggle} className="mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-medium text-slate-800">{field}</span>
          {isNew && <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100">新</span>}
          {badge && <span className="text-xs text-slate-500">{badge}</span>}
        </div>
        <p className="text-xs text-slate-500 mt-0.5 truncate">{value}</p>
      </div>
    </div>
  );
}

// ── Label maps ────────────────────────────────────────────────────────────────
const FIELD_LABELS: Record<string, string> = {
  pain_points: "客户痛点",
  competitor: "竞争对手",
  budget_status: "预算状态",
  amount_hint: "预估金额",
  close_date_hint: "预计成交日",
};
const MEDDIC_LABELS: Record<string, string> = {
  metrics: "可量化指标",
  economic_buyer: "经济买家",
  decision_criteria: "决策标准",
  decision_process: "决策流程",
  identify_pain: "痛点识别",
  champion: "内部拥护者",
};
const ROLE_LABELS: Record<string, string> = {
  ECONOMIC_BUYER: "经济买家",
  TECHNICAL_BUYER: "技术买家",
  CHAMPION: "内部拥护者",
  BLOCKER: "阻碍者",
  INFLUENCER: "影响者",
  UNKNOWN: "未知",
};
