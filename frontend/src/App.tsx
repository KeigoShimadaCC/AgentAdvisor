import { Routes, Route, Link } from "react-router-dom";
import { CaseLibrary } from "./pages/CaseLibrary";
import { CaseDetail } from "./pages/CaseDetail";
import { NewDecision } from "./screens/NewDecision/NewDecision";
import { ScopeCheckpoint } from "./screens/ScopeCheckpoint/ScopeCheckpoint";
import { SignedRecord } from "./screens/ScopeCheckpoint/SignedRecord";

export function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="app-title">AgentAdvisor</Link>
        <nav className="app-nav">
          <Link to="/" className="app-nav-link">Cases</Link>
          <Link to="/new" className="app-nav-link">New decision</Link>
        </nav>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<CaseLibrary />} />
          <Route path="/new" element={<NewDecision />} />
          <Route path="/cases/:caseId" element={<CaseDetail />} />
          <Route path="/cases/:caseId/scope" element={<ScopeCheckpoint />} />
          <Route path="/cases/:caseId/scope/signed" element={<SignedRecord />} />
        </Routes>
      </main>
    </div>
  );
}
