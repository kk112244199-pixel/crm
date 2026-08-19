export default function Home() {
  return (
    <div className="max-w-2xl mx-auto mt-16 text-center space-y-6">
      <h1 className="text-4xl font-bold text-gray-900">MontoCRM</h1>
      <p className="text-gray-500 text-lg">AI-native B2B CRM — 智能销售助手</p>
      <div className="grid grid-cols-2 gap-4 mt-8 text-left">
        <a href="/accounts" className="block border rounded-xl p-5 hover:shadow-md transition">
          <div className="text-2xl mb-2">🏢</div>
          <div className="font-semibold">客户管理</div>
          <div className="text-sm text-gray-500 mt-1">Account / Contact CRUD</div>
        </a>
        <a href="/opportunities" className="block border rounded-xl p-5 hover:shadow-md transition">
          <div className="text-2xl mb-2">💼</div>
          <div className="font-semibold">商机管理</div>
          <div className="text-sm text-gray-500 mt-1">Opportunity + 健康度</div>
        </a>
        <a href="/settings/llm" className="block border rounded-xl p-5 hover:shadow-md transition">
          <div className="text-2xl mb-2">⚙️</div>
          <div className="font-semibold">LLM 配置</div>
          <div className="text-sm text-gray-500 mt-1">Admin 模型切换</div>
        </a>
        <a href="http://localhost:8000/docs" target="_blank" className="block border rounded-xl p-5 hover:shadow-md transition">
          <div className="text-2xl mb-2">📄</div>
          <div className="font-semibold">API 文档</div>
          <div className="text-sm text-gray-500 mt-1">FastAPI Swagger UI</div>
        </a>
      </div>
    </div>
  );
}
