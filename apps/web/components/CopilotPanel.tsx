"use client";
import { useState, useRef, useEffect } from "react";
import api from "@/lib/api-client";

interface Citation {
  snippet: string;
  activity_id?: string;
  date?: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  no_data?: boolean;
  clarification?: string;
}

interface CopilotPanelProps {
  opportunityId?: string;
  accountId?: string;
  placeholder?: string;
}

export default function CopilotPanel({
  opportunityId,
  accountId,
  placeholder = "问我任何关于此商机的问题…",
}: CopilotPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<"query" | "draft">("query");
  const [draftResult, setDraftResult] = useState<{
    pending_action_id: string;
    subject: string;
    body: string;
    cta: string;
  } | null>(null);
  const [sendEmail, setSendEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, draftResult]);

  const handleQuery = async () => {
    if (!input.trim()) return;
    const q = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: q }]);
    setLoading(true);

    try {
      const res = await api.post("/copilot/query", {
        question: q,
        opportunity_id: opportunityId || null,
        account_id: accountId || null,
      });
      const d = res.data;
      setMessages(prev => [...prev, {
        role: "assistant",
        content: d.answer || "抱歉，暂时无法回答。",
        citations: d.citations,
        no_data: d.no_data,
        clarification: d.clarification_needed,
      }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: "⚠ 请求失败，请稍后重试。" }]);
    } finally {
      setLoading(false);
    }
  };

  const handleDraft = async () => {
    if (!input.trim() || !opportunityId) return;
    const inst = input.trim();
    setInput("");
    setLoading(true);
    setDraftResult(null);
    setSent(false);

    try {
      const res = await api.post("/copilot/draft", {
        opportunity_id: opportunityId,
        instruction: inst,
      });
      setDraftResult(res.data);
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: "⚠ 草稿生成失败，请稍后重试。" }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!draftResult || !sendEmail) return;
    setSending(true);
    try {
      await api.post(`/copilot/draft/${draftResult.pending_action_id}/send`, { to_email: sendEmail });
      setSent(true);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      mode === "query" ? handleQuery() : handleDraft();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50/50">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-full bg-indigo-100 flex items-center justify-center text-xs">✦</div>
          <span className="text-sm font-semibold text-slate-700">Copilot</span>
        </div>
        <div className="flex gap-1 bg-slate-100 rounded-lg p-0.5">
          {(["query", "draft"] as const).map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setDraftResult(null); setSent(false); }}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                mode === m ? "bg-white text-slate-700 shadow-sm" : "text-slate-500 hover:text-slate-700"
              }`}
            >
              {m === "query" ? "问答" : "起草邮件"}
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 min-h-0">
        {messages.length === 0 && !draftResult && (
          <div className="flex flex-col items-center justify-center h-32 text-slate-400 text-sm gap-2">
            <span className="text-2xl">✦</span>
            <span>{mode === "query" ? "问我任何关于此商机的问题" : "输入邮件写作指令，AI 自动生成草稿"}</span>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "assistant" && (
              <div className="w-5 h-5 rounded-full bg-indigo-50 flex items-center justify-center text-xs mr-2 mt-1 shrink-0">✦</div>
            )}
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
              msg.role === "user"
                ? "bg-indigo-600 text-white rounded-tr-sm"
                : "bg-slate-100 text-slate-800 rounded-tl-sm"
            }`}>
              <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>
              {msg.clarification && (
                <p className="mt-2 text-xs text-amber-600 bg-amber-50 rounded p-2">{msg.clarification}</p>
              )}
              {msg.no_data && (
                <p className="mt-2 text-xs text-slate-500">（无相关历史纪要记录）</p>
              )}
              {msg.citations && msg.citations.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.citations.slice(0, 3).map((c, ci) => (
                    <div key={ci} className="text-xs text-slate-500 border-l-2 border-indigo-200 pl-2">
                      {c.date && <span className="text-slate-400">{c.date} · </span>}
                      "{c.snippet}"
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Draft result */}
        {draftResult && !sent && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">邮件草稿</p>
            <div>
              <p className="text-xs text-slate-400 mb-0.5">主题</p>
              <p className="text-sm font-medium text-slate-800">{draftResult.subject}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-0.5">正文</p>
              <pre className="text-sm text-slate-700 whitespace-pre-wrap font-sans leading-relaxed">{draftResult.body}</pre>
            </div>
            {draftResult.cta && (
              <p className="text-xs text-indigo-600 bg-indigo-50 rounded px-2 py-1">▶ {draftResult.cta}</p>
            )}
            <div className="flex gap-2 pt-1">
              <input
                type="email"
                value={sendEmail}
                onChange={e => setSendEmail(e.target.value)}
                placeholder="收件人邮箱"
                className="flex-1 text-xs rounded-lg border border-slate-200 px-3 py-2 focus:outline-none focus:ring-1 focus:ring-indigo-300"
              />
              <button
                onClick={handleSend}
                disabled={sending || !sendEmail}
                className="px-3 py-2 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {sending ? "发送中…" : "确认发送"}
              </button>
            </div>
          </div>
        )}

        {sent && (
          <div className="text-center py-4">
            <p className="text-sm font-medium text-emerald-600">✓ 邮件已发送，活动记录已创建</p>
          </div>
        )}

        {loading && (
          <div className="flex justify-start">
            <div className="w-5 h-5 rounded-full bg-indigo-50 flex items-center justify-center text-xs mr-2">✦</div>
            <div className="bg-slate-100 rounded-2xl rounded-tl-sm px-4 py-2.5">
              <div className="flex gap-1 items-center h-4">
                {[0, 1, 2].map(i => (
                  <div key={i} className={`w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce`}
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-slate-100">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            disabled={loading}
            placeholder={mode === "query" ? placeholder : "例如：写一封跟进邮件，提醒对方 POC 结果…"}
            className="flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 disabled:opacity-50"
          />
          <button
            onClick={mode === "query" ? handleQuery : handleDraft}
            disabled={loading || !input.trim()}
            className="px-4 rounded-xl bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            ↑
          </button>
        </div>
        <p className="text-xs text-slate-400 mt-1.5">Enter 发送 · Shift+Enter 换行</p>
      </div>
    </div>
  );
}
