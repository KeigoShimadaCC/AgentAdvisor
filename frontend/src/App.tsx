import { Routes, Route, Link } from "react-router-dom";
import { CaseLibrary } from "./pages/CaseLibrary";
import { CaseDetail } from "./pages/CaseDetail";
import { NewDecision } from "./screens/NewDecision/NewDecision";
import { ScopeCheckpoint } from "./screens/ScopeCheckpoint/ScopeCheckpoint";
import { SignedRecord } from "./screens/ScopeCheckpoint/SignedRecord";
import { Delivery } from "./screens/Delivery/Delivery";
import { InspectorPage } from "./screens/inspector/InspectorPage";
import { ToastHost } from "./screens/shared/Toast";
import { Calibration } from "./screens/Calibration/Calibration";
import { NoticeBanner } from "./presence/NoticeBanner";

function NotFound() {
  return (
    <div className="not-found">
      <h2>That page does not exist</h2>
      <p>The link may be stale, or the case may have been removed.</p>
      <Link to="/" className="primary-action">Back to your cases</Link>
    </div>
  );
}

export function App() {
  return (
    <ToastHost>
    <div className="app">
      <header className="app-header">
        <h1 className="app-title-heading">
          <Link to="/" className="app-title">AgentAdvisor</Link>
        </h1>
        <nav className="app-nav">
          <Link to="/" className="app-nav-link">Cases</Link>
          <Link to="/new" className="app-nav-link">New decision</Link>
          <Link to="/calibration" className="app-nav-link">Track record</Link>
        </nav>
      </header>
      <NoticeBanner />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<CaseLibrary />} />
          <Route path="/new" element={<NewDecision />} />
          <Route path="/calibration" element={<Calibration />} />
          {/* One case surface (SPEC-048). `/brief` and the six room deep links
              were separate pages; they now resolve here, with rooms opening in
              the context panel, so every previously valid URL still works. */}
          <Route path="/cases/:caseId" element={<CaseDetail />} />
          <Route path="/cases/:caseId/brief" element={<CaseDetail />} />
          <Route path="/cases/:caseId/rooms/:room" element={<CaseDetail />} />
          <Route path="/cases/:caseId/scope" element={<ScopeCheckpoint />} />
          <Route path="/cases/:caseId/scope/signed" element={<SignedRecord />} />
          <Route path="/cases/:caseId/delivery" element={<Delivery />} />
          <Route path="/cases/:caseId/inspector/:artifactId" element={<InspectorPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
    </ToastHost>
  );
}
