"use client";
import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api-client";
import { HealthBadge } from "@/components/HealthBadge";

interface RiskItem {
  opportunity_id: string;
  opportunity_name: string;
  account_name: string;
  owner_name: string;
  stage: string;
  amount?: number;
  health_score?: number;
  health_status?: string;
  top_rules: string[];
}

interface RiskBoard {
  red: RiskItem[];
  yellow: RiskItem[];
  green: RiskItem[];
  total: number;
}

const STAGE_CN: Record<string, string> = {
  PROSPECTING: "线索",
  QUALIFICATION: "定性",
  NEEDS_ANALYSIS: "需求分析",
  VALUE_PROPOSITION: "价值呈现",
  PROPOSAL: "方案",
  NEGOTIATION: "谈判",
  CLOSED_WON: "赢单",
  CLOSED_LOST: "丢单",
};

function fmt(n?: number | null) {
  if (!n) return "—";
  return n >= 10000 ? `${(n / 10000).toFixed(0)} 万` : `¥${n.toLocaleString()}`;
}

export default function RiskBoardPage() {
  const [data, setData] = useState<RiskBoard | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"red" | "yellow" | "green">("red");
  const router = useRouter();

  useEffect(() => {
    api.get<RiskBoard>("/dashboard/risk-board")
      .then(r => setData(r.data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="flex items-center justify-center min-h-screen text-slate-400">加载中…</div>;
  if (!data) return <div className="text-center py-20 text-slate-400">无法加载风险看板</div>;

  const items = data[tab];
  const tabs = [
    { key: "red" as const,    label: "高风险", count: data.red.length,    color: "text-red-600 border-red-600" },
    { key: "yellow" as const, label: "警示",   count: data.yellow.length, color: "text-amber-600 border-amber-600" },
    { key: "green" as const,  label: "健康",   count: data.green.length,  color: "text-emerald-600 border-emerald-600" },
  ];

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">团队风险看板</h1>
          <p className="text-sm text-slate-500 mt-1">共 {data.total} 个活跃商机</p>
        </div>
        <div className="flex gap-3">
          {[
            { status: "RED" as const,    count: data.red.length,    label: "高风险" },
            { status: "YELLOW" as const, count: data.yellow.length, label: "警示" },
            { status: "GREEN" as const,  count: data.green.length,  label: "健康" },
          ].map(s => (
            <div key={s.status} className="text-center">
              <HealthBadge status={s.status} showScore={false} size="lg" />
              <div className="text-lg font-bold text-slate-800 mt-1">{s.count}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-slate-200 mb-6">
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-5 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              tab === t.key
                ? `${t.color} border-current`
                : "text-slate-500 border-transparent hover:text-slate-700"
            }`}
          >
            {t.label}
            <span className="ml-1.5 text-xs opacity-70">({t.count})</span>
          </button>
        ))}
      </div>

      {/* Table */}
      {items.length === 0 ? (
        <div className="text-center py-16 text-slate-400">当前分类无商机</div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-100 shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-100">
              <tr>
                {["商机名称", "客户", "负责人", "阶段", "金额", "健康度", "主要风险"].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {items.map(item => (
                <tr
                  key={item.opportunity_id}
                  onClick={() => router.push(`/opportunities/${item.opportunity_id}`)}
                  className="hover:bg-slate-50 cursor-pointer transition-colors"
                >
                  <td className="px-4 py-3 font-medium text-slate-800 max-w-[200px] truncate">
                    {item.opportunity_name}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{item.account_name}</td>
                  <td className="px-4 py-3 text-slate-600">{item.owner_name}</td>
                  <td className="px-4 py-3 text-slate-500 text-xs">{STAGE_CN[item.stage] || item.stage}</td>
                  <td className="px-4 py-3 font-medium text-slate-700">{fmt(item.amount)}</td>
                  <td className="px-4 py-3">
                    <HealthBadge score={item.health_score} status={item.health_status} size="sm" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {item.top_rules.slice(0, 3).map(r => (
                        <span key={r} className="text-xs px-1.5 py-0.5 rounded bg-slate-100 font-mono text-slate-500">{r}</span>
                      ))}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
