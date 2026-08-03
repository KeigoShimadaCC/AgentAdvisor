import { Routes, Route, Link } from "react-router-dom";
import { CaseLibrary } from "./pages/CaseLibrary";
import { CaseDetail } from "./pages/CaseDetail";
import { NewDecision } from "./screens/NewDecision/NewDecision";
import { ScopeCheckpoint } from "./screens/ScopeCheckpoint/ScopeCheckpoint";
import { SignedRecord } from "./screens/ScopeCheckpoint/SignedRecord";
import { SourcesRoom } from "./screens/rooms/Sources/SourcesRoom";
import { AssumptionsRoom } from "./screens/rooms/Assumptions/AssumptionsRoom";
import { OptionsRoom } from "./screens/rooms/Options/OptionsRoom";
import { ChallengesRoom } from "./screens/rooms/Challenges/ChallengesRoom";
import { PlanRoom } from "./screens/rooms/Plan/PlanRoom";
import { MethodRoom } from "./screens/rooms/Method/MethodRoom";
import { InspectorPage } from "./screens/inspector/InspectorPage";

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
    <div className="app">
      <header className="app-header">
        <h1 className="app-title-heading">
          <Link to="/" className="app-title">AgentAdvisor</Link>
        </h1>
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
          <Route path="/cases/:caseId/rooms/sources" element={<SourcesRoom />} />
          <Route path="/cases/:caseId/rooms/assumptions" element={<AssumptionsRoom />} />
          <Route path="/cases/:caseId/rooms/options" element={<OptionsRoom />} />
          <Route path="/cases/:caseId/rooms/challenges" element={<ChallengesRoom />} />
          <Route path="/cases/:caseId/rooms/plan" element={<PlanRoom />} />
          <Route path="/cases/:caseId/rooms/method" element={<MethodRoom />} />
          <Route path="/cases/:caseId/inspector/:artifactId" element={<InspectorPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </div>
  );
}
