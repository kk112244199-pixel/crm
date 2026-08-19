import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MontoCRM",
  description: "AI-native B2B CRM",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <div className="min-h-screen flex flex-col">
          <header className="bg-brand-600 text-white px-6 py-3 flex items-center gap-4 shadow">
            <span className="font-bold text-lg tracking-tight">MontoCRM</span>
            <nav className="flex gap-4 text-sm ml-6">
              <a href="/" className="hover:text-brand-100">首页</a>
              <a href="/accounts" className="hover:text-brand-100">客户</a>
              <a href="/opportunities" className="hover:text-brand-100">商机</a>
              <a href="/settings/llm" className="hover:text-brand-100">LLM 设置</a>
            </nav>
          </header>
          <main className="flex-1 p-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
