import { Routes, Route, Link } from "react-router-dom";
import { CaseLibrary } from "./pages/CaseLibrary";
import { CaseDetail } from "./pages/CaseDetail";

export function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="app-title">AgentAdvisor</Link>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<CaseLibrary />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
        </Routes>
      </main>
    </div>
  );
}
