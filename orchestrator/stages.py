"""Stage handlers wiring roles to the SPEC-007 state machine.

Each handler is a method on :class:`StageHandlers` matching the
``handler_name`` in ``_FLOW_PLANS`` (``orchestrator/state_machine.py``).
Handlers contain orchestration only; every substantive judgment stays
inside role invocations.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from orchestrator.artifacts import (
    AnalysisResult,
    AssumptionBatch,
    AuditEvent,
    DecisionSpec,
    DisclosureRecord,
    EvidenceBatch,
    EvidenceRecord,
    FinalApproval,
    FinalRecommendation,
    IndependentReview,
    IndependentVerdict,
    IntakeRecord,
    IssueTree,
    Level,
    ObjectionBatch,
    ObjectionRecord,
    PreliminaryRecommendation,
    PreMortemReport,
    ReviewReport,
    TaskProposalBatch,
    TaskRecord,
    TaskStatus,
    ThesisTrigger,
)
from orchestrator.backend import AgentBackend
from orchestrator.budget import BudgetConfig, BudgetKind, BudgetLedger, StopEvaluator
from orchestrator.case_store import Case
from orchestrator.evidence_critic import critique_case_evidence
from orchestrator.gates import blocking_findings, run_stage_gate
from orchestrator.invoke_role import (
    InvokeTask,
    RoleInvocationFailed,
    invoke,
    invoke_read_only,
)
from orchestrator.issue_tree import compute_coverage
from orchestrator.normalize import normalize_evidence_batch
from orchestrator.planning import apply_planner_acceptance_filter
from orchestrator.render import write_final_recommendation_markdown
from orchestrator.reproduce import reproduce_analysis_result
from orchestrator.roles_config import load_role_config, models_for
from orchestrator.stability import compute_model_stability
from orchestrator.state_machine import CaseState, StepHandler, StepPlan, StepResult, save_case_state
from orchestrator.task_graph import TaskExecutionResult, TaskGraph
from orchestrator.thesis import write_thesis
from orchestrator.tracks import build_position, compare_tracks
from orchestrator.unpack import unpack_assumption_batch, unpack_objection_batch
from orchestrator.verification import build_verification_worksheet, review_is_acceptable

DEFAULT_TIMEOUT_S = 300.0
ANALYST_TIMEOUT_S = 600.0
# The droid CLI (claude-sonnet-5) runs heavy roles (analyst, synthesizer) right
# at the timeout ceiling — a real case saw an analyst task time out at exactly
# 600s and burn a retry. Scale timeouts up on that backend so genuinely slow
# but healthy invocations complete instead of failing spuriously.
_DROID_TIMEOUT_SCALE = 2.0
STALE_AFTER_DAYS = 365
MIN_ISSUE_COVERAGE_TO_STOP = 0.5


def _role_timeout(backend: AgentBackend, role: str) -> float:
    """Per-role invocation timeout, scaled up for the slower droid backend."""
    base = ANALYST_TIMEOUT_S if role == "analyst" else DEFAULT_TIMEOUT_S
    if getattr(backend, "name", "") == "droid":
        return base * _DROID_TIMEOUT_SCALE
    return base


def _unanswered_issue_questions(case: Case) -> list[str]:
    """Issue-tree leaves with no completed task, for the Limitations section.

    ``compute_coverage`` already computes the leaf/completed-task join; this reuses it
    so the limitations statement names real gaps rather than inviting the synthesizer
    to invent plausible ones.
    """
    try:
        tree = case.read_artifact(IssueTree)
    except FileNotFoundError:
        return []
    coverage = compute_coverage(tree, case.list_artifacts(TaskRecord))
    by_id = {node.node_id: node for node in tree.nodes}
    return [by_id[node_id].question for node_id in coverage.uncovered_node_ids if node_id in by_id]


def _audit(case: Case, event_type: str, payload: dict[str, Any]) -> None:
    case.audit(
        AuditEvent(
            ts=datetime.now(UTC),
            actor="orchestrator",
            event_type=event_type,
            payload=payload,
        )
    )


def _build_task_runner(
    case: Case,
    backend: AgentBackend,
    budget_ledger: BudgetLedger,
) -> Any:
    """Build a TaskRunner callable for the task graph dispatch."""

    def runner(task: TaskRecord) -> TaskExecutionResult:
        role = task.role.value
        artifact_type = task.required_output

        # Map required_output to the actual output_artifact_type the role config expects.
        # The planner may produce descriptive strings; we override with canonical types.
        if role == "researcher":
            artifact_type = "evidence_batch"
        elif role == "challenger":
            artifact_type = "objection_batch"
        elif role == "analyst":
            artifact_type = "analysis_result"
        elif role == "auditor":
            artifact_type = "audit_finding"

        # Dispatching a researcher task additionally consumes research_tasks.
        # The task graph already consumed agent_invocations, so the invoke()
        # call below must not double-count (consume_agent_invocations=False).
        if role == "researcher":
            budget_ledger.try_consume(BudgetKind.RESEARCH_TASKS.value)

        timeout = _role_timeout(backend, role)
        invoke_task = InvokeTask(
            task_id=task.task_id,
            assignment=(
                f"Question: {task.question}\n"
                f"Why it matters: {task.why_it_matters}\n"
                f"Completion criteria: {task.completion_criteria}\n"
            ),
            output_artifact_type=artifact_type,
            timeout_s=timeout,
        )

        try:
            if role == "auditor":
                artifact = invoke_read_only(
                    case,
                    role,
                    invoke_task,
                    backend=backend,
                    budget_ledger=budget_ledger,
                    consume_agent_invocations=False,
                )
            else:
                artifact = invoke(
                    case,
                    role,
                    invoke_task,
                    backend=backend,
                    budget_ledger=budget_ledger,
                    consume_agent_invocations=False,
                )
        except RoleInvocationFailed as exc:
            return TaskExecutionResult(
                artifacts=(),
                audit_payload={"error": str(exc), "role": role},
            )

        # Post-processing for researcher: normalize evidence batch
        if isinstance(artifact, EvidenceBatch):
            if not artifact.no_evidence_found and artifact.records:
                normalized = normalize_evidence_batch(
                    artifact,
                    stale_after_days=STALE_AFTER_DAYS,
                )
                # Rebuild batch with only accepted records
                accepted_batch = EvidenceBatch(
                    task_id=artifact.task_id,
                    question=artifact.question,
                    records=list(normalized.accepted),
                    no_evidence_found=False,
                    search_notes=artifact.search_notes,
                )
                return TaskExecutionResult(
                    artifacts=(accepted_batch,),
                    audit_payload={
                        "accepted": len(normalized.accepted),
                        "quarantined": len(normalized.quarantined),
                        "contradictions": len(normalized.contradiction_links),
                        "stale": len(normalized.stale_evidence_ids),
                    },
                )
            return TaskExecutionResult(
                artifacts=(artifact,),
                audit_payload={"no_evidence_found": True},
            )

        # Post-processing for analyst: reproducibility gate
        if isinstance(artifact, AnalysisResult):
            try:
                result = reproduce_analysis_result(
                    case_root=case.root,
                    analysis_result=artifact,
                )
                if result.status.value != "pass":
                    _audit(
                        case,
                        "reproducibility_gate_failed",
                        {
                            "task_id": artifact.task_id,
                            "status": result.status.value,
                            "diff_count": len(result.diff),
                        },
                    )
            except Exception as exc:  # noqa: BLE001
                _audit(
                    case,
                    "reproducibility_gate_error",
                    {"task_id": artifact.task_id, "error": str(exc)},
                )

        return TaskExecutionResult(
            artifacts=(artifact,),
            audit_payload={"role": role, "artifact_type": type(artifact).__name__},
        )

    return runner


class StageHandlers:
    """Stage handlers for the end-to-end pipeline.

    Parameters
    ----------
    backend:
        Agent backend for role invocations (CursorCLIBackend for live, StubBackend for tests).
    budget_config:
        Budget configuration for the case.
    raw_prompt:
        The user's raw decision prompt (for the intake stage).
    model_tier_map:
        Mapping from model names to tiers for budget accounting.
    """

    def __init__(
        self,
        *,
        backend: AgentBackend,
        budget_config: BudgetConfig,
        raw_prompt: str,
        model_tier_map: dict[str, str] | None = None,
        dual_track: bool = True,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._backend = backend
        self._budget_config = budget_config
        self._raw_prompt = raw_prompt
        self._model_tier_map = model_tier_map or {}
        self._dual_track = dual_track
        self._budget_ledger: BudgetLedger | None = None
        self._task_graph: TaskGraph | None = None
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))

    @property
    def budget_ledger(self) -> BudgetLedger:
        if self._budget_ledger is None:
            raise RuntimeError("Budget ledger not initialized; call run() first.")
        return self._budget_ledger

    @property
    def task_graph(self) -> TaskGraph:
        if self._task_graph is None:
            raise RuntimeError("Task graph not initialized; call run() first.")
        return self._task_graph

    def _elapsed_s(self, state: CaseState) -> float:
        """Total elapsed wall-clock seconds including the current run segment."""
        elapsed = state.elapsed_s
        if state.started_at_run is not None:
            elapsed += (self._clock() - state.started_at_run).total_seconds()
        return elapsed

    def _wall_clock_exceeded(self, state: CaseState) -> bool:
        return self._elapsed_s(state) >= self._budget_config.max_wall_clock_s

    def handlers(self) -> dict[str, StepHandler]:
        return {
            "intake": self.handle_intake,
            "framing": self.handle_framing,
            "structuring": self.handle_structuring,
            "provisional_thesis": self.handle_provisional_thesis,
            "planning": self.handle_planning,
            "investigation": self.handle_investigation,
            "evidence_critique": self.handle_evidence_critique,
            "assumption_ledger": self.handle_assumption_ledger,
            "preliminary_recommendation": self.handle_preliminary_recommendation,
            "pre_mortem": self.handle_pre_mortem,
            "challenge": self.handle_challenge,
            "repair": self.handle_repair,
            "stop_decision": self.handle_stop_decision,
            "synthesis": self.handle_synthesis,
            "review": self.handle_review,
        }

    def _gate(self, case: Case, stage: str) -> None:
        """Run the deterministic process gate for a stage boundary.

        Gates never fail the case on their own. A blocking finding is recorded and fed
        to the stop evaluator, which is what keeps the case from concluding on a broken
        chain while still leaving the run inspectable.
        """
        run_stage_gate(case, stage, task_graph=self._task_graph)

    # --- Stage handlers ---

    def handle_intake(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-intake",
            assignment=(
                f"Extract a schema-valid intake artifact from this raw user prompt.\n"
                f"Raw user prompt:\n{self._raw_prompt}"
            ),
            output_artifact_type="intake_record",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case, "intake", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Intake failed: {exc}")
        assert isinstance(artifact, IntakeRecord)
        case.write_artifact(artifact)
        _audit(case, "stage_completed", {"stage": "intake"})
        return StepResult.ok()

    def handle_framing(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id=f"T-framing-r{state.framing_revisions}",
            assignment=(
                "Produce a schema-valid decision specification from the provided intake input.\n"
                f"Case ID: {case.root.name}\nOwner: user"
            ),
            output_artifact_type="decision_spec",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case,
                "director",
                task,
                backend=self._backend,
                variant="framing",
                budget_ledger=self.budget_ledger,
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Framing failed: {exc}")
        assert isinstance(artifact, DecisionSpec)
        case.write_artifact(artifact)
        if artifact.objective_weights:
            _audit(
                case,
                "objective_weights_recorded",
                {
                    "source": "framing_proposal",
                    "objective_count": len(artifact.objective_weights),
                },
            )
        _audit(case, "stage_completed", {"stage": "framing"})
        return StepResult.ok()

    def handle_structuring(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-structuring",
            assignment=(
                "Decompose this decision into a MECE issue tree of sub-questions.\n"
                "The root node Q-1 restates the decision. Children are the drivers and "
                "sub-questions that must be answered before anyone can recommend an action.\n"
                "Every node needs resolution_criteria stating what would count as answering "
                "it and what answer would change the recommendation.\n"
                "You are structuring the question, not answering it."
            ),
            output_artifact_type="issue_tree",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case, "structurer", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Structuring failed: {exc}")
        assert isinstance(artifact, IssueTree)
        case.write_artifact(artifact)
        _audit(
            case,
            "stage_completed",
            {
                "stage": "structuring",
                "node_count": len(artifact.nodes),
                "leaf_count": len(artifact.leaf_node_ids()),
            },
        )
        return StepResult.ok()

    def handle_provisional_thesis(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-provisional-thesis",
            assignment=(
                "Form a provisional thesis based on the decision specification and issue tree.\n"
                "State your preferred alternative, the rationale, and at least 3 uncertainties "
                "that could most plausibly reverse it.\n"
                "This is NOT the final answer; it is a provisional thesis to guide research."
            ),
            output_artifact_type="preliminary_recommendation",
            mode="provisional_thesis",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case, "director", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Provisional thesis failed: {exc}")
        assert isinstance(artifact, PreliminaryRecommendation)
        write_thesis(case, artifact, trigger=ThesisTrigger.PROVISIONAL)
        _audit(case, "stage_completed", {"stage": "provisional_thesis"})
        return StepResult.ok()

    def handle_planning(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-planning",
            assignment=(
                "Decompose the decision into investigation tasks.\n"
                "Emit a TaskProposalBatch with up to 10 proposals.\n"
                "Each proposal must include: role, question, why_it_matters, materiality, "
                "probability_of_changing_conclusion, estimated_cost, completion_criteria, "
                "inputs, required_output, priority fields.\n"
                "Propose nothing if open tasks already cover material gaps."
            ),
            output_artifact_type="task_proposal_batch",
            mode="initial",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case, "planner", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Planning failed: {exc}")
        assert isinstance(artifact, TaskProposalBatch)

        # Run acceptance filter
        result = apply_planner_acceptance_filter(case, artifact)
        accepted_batch = result.accepted_batch

        # Convert accepted proposals to TaskRecords and add to task graph
        task_records: list[TaskRecord] = []
        edges: dict[str, list[str]] = {}
        for proposal in accepted_batch.proposals:
            task_id = case.next_id("T-")
            record = TaskRecord(
                task_id=task_id,
                role=proposal.task.role,
                issue_node_id=proposal.task.issue_node_id,
                question=proposal.task.question,
                why_it_matters=proposal.task.why_it_matters,
                expected_information_gain=proposal.task.expected_information_gain,
                materiality=proposal.task.materiality,
                probability_of_changing_conclusion=proposal.task.probability_of_changing_conclusion,
                estimated_cost=proposal.task.estimated_cost,
                inputs=list(proposal.task.inputs),
                required_output=proposal.task.required_output,
                completion_criteria=proposal.task.completion_criteria,
                status=TaskStatus.PLANNED,
                priority=proposal.task.priority,
                priority_score=proposal.task.priority_score,
                priority_rationale=proposal.task.priority_rationale,
            )
            task_records.append(record)
            deps = [
                task_records[idx].task_id
                for idx in proposal.depends_on_indices
                if idx < len(task_records)
            ]
            if deps:
                edges[task_id] = deps

        if task_records:
            self.task_graph.add_tasks(task_records, edges=edges or None)

        _audit(
            case,
            "stage_completed",
            {
                "stage": "planning",
                "proposals_total": len(artifact.proposals),
                "accepted": len(task_records),
                "rejected": len(result.rejections),
                "issue_coverage": self._issue_coverage_share(case),
            },
        )
        return StepResult.ok()

    def _issue_coverage_share(self, case: Case) -> float | None:
        trees = case.list_artifacts(IssueTree)
        if not trees:
            return None
        return compute_coverage(trees[0], case.list_artifacts(TaskRecord)).covered_share

    def handle_investigation(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        runner = _build_task_runner(case, self._backend, self.budget_ledger)

        all_started: list[str] = []
        all_completed: list[str] = []
        all_failed: list[str] = []

        # Dispatch waves until no more ready tasks
        while True:
            # Wall-clock check before each dispatch wave.
            if self._wall_clock_exceeded(state):
                _audit(
                    case,
                    "wall_clock_exceeded",
                    {"elapsed_s": self._elapsed_s(state)},
                )
                break
            summary = self.task_graph.dispatch(
                runner,
                max_concurrent=self._budget_config.max_concurrent_workers,
            )
            all_started.extend(summary.started)
            all_completed.extend(summary.completed)
            all_failed.extend(summary.failed)

            # Check if more tasks became ready
            ready = self.task_graph.ready()
            if not ready:
                break
            if summary.budget_refused:
                break

        self._gate(case, "investigation")
        _audit(
            case,
            "stage_completed",
            {
                "stage": "investigation",
                "tasks_started": len(all_started),
                "tasks_completed": len(all_completed),
                "tasks_failed": len(all_failed),
            },
        )
        return StepResult.ok()

    def handle_evidence_critique(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        """Score the evidence corpus deterministically. No agent runs here.

        Everything in the critique is computable from fields the researcher already had
        to fill in, so an agent would only add an opportunity to talk a weak corpus up.
        """
        critique = critique_case_evidence(case, as_of=datetime.now(UTC).date())
        self._gate(case, "evidence_critique")
        _audit(
            case,
            "stage_completed",
            {
                "stage": "evidence_critique",
                "evidence_count": critique.evidence_count,
                "corpus_authority_mean": critique.corpus_authority_mean,
                "primary_source_share": critique.primary_source_share,
                "max_cluster_share": critique.max_cluster_share,
                "independent_group_count": critique.independent_group_count,
                "gap_count": len(critique.gaps),
            },
        )
        return StepResult.ok()

    def handle_assumption_ledger(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-assumption-ledger",
            assignment=(
                "Extract the load-bearing assumptions the case is currently resting on.\n"
                "An assumption is a proposition that must be true for the reasoning to hold "
                "but which no evidence in inputs/ establishes.\n"
                "Rate materiality honestly; most assumptions are not high.\n"
                "Every assumption needs a testable claim and a probability estimate."
            ),
            output_artifact_type="assumption_batch",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case,
                "assumption_analyst",
                task,
                backend=self._backend,
                budget_ledger=self.budget_ledger,
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Assumption extraction failed: {exc}")
        assert isinstance(artifact, AssumptionBatch)

        records = unpack_assumption_batch(case, artifact, task_id="T-assumption-ledger")
        self._gate(case, "assumption_ledger")
        _audit(
            case,
            "stage_completed",
            {
                "stage": "assumption_ledger",
                "assumption_count": len(records),
                "high_materiality": sum(
                    1 for record in records if record.materiality is Level.HIGH
                ),
                "no_assumptions_found": artifact.no_assumptions_found,
            },
        )
        return StepResult.ok()

    def _run_track_b(self, case: Case, primary: PreliminaryRecommendation) -> None:
        """Second independent Director on a different model family.

        Failure here is non-fatal: a missing diversity signal degrades the case, it does
        not invalidate it.
        """
        task = InvokeTask(
            task_id="T-preliminary-rec-track-b",
            assignment=(
                "Form an independent view of what the evidence supports.\n"
                "You have not been shown any other conclusion and must not try to infer one.\n"
                "Reason from the evidence upward. Every rationale item must cite E-/A- IDs.\n"
                "If the evidence cannot distinguish the alternatives, say so."
            ),
            output_artifact_type="preliminary_recommendation",
            mode="preliminary_recommendation",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case,
                "director",
                task,
                backend=self._backend,
                variant="b",
                budget_ledger=self.budget_ledger,
            )
        except RoleInvocationFailed as exc:
            _audit(case, "dual_track_skipped", {"reason": str(exc)})
            return
        if not isinstance(artifact, PreliminaryRecommendation):
            return

        backend_name = self._backend.name
        try:
            positions = [
                build_position(
                    track_id="track-a",
                    model=models_for(load_role_config("director"), backend_name).default_model,
                    recommendation=primary,
                ),
                build_position(
                    track_id="track-b",
                    model=models_for(load_role_config("director", "b"), backend_name).default_model,
                    recommendation=artifact,
                ),
            ]
            divergence = compare_tracks(stage="preliminary_recommendation", positions=positions)
        except ValueError as exc:
            _audit(case, "dual_track_skipped", {"reason": str(exc)})
            return

        case.write_artifact(divergence)
        _audit(
            case,
            "dual_track_compared",
            {
                "agreement": divergence.agreement,
                "positions": [
                    {
                        "track_id": position.track_id,
                        "model_family": position.model_family,
                        "preferred_alternative": position.preferred_alternative,
                    }
                    for position in divergence.positions
                ],
            },
        )

    def handle_preliminary_recommendation(
        self, case: Case, state: CaseState, plan: StepPlan
    ) -> StepResult:
        task = InvokeTask(
            task_id="T-preliminary-rec",
            assignment=(
                "Produce a preliminary recommendation based on all available evidence, "
                "assumptions, and analysis results.\n"
                "Every material claim must cite E-* or A-* IDs.\n"
                "Recommendation confidence and evidence confidence must be separate, and "
                "the evidence critique in inputs/ bounds how high evidence confidence can be.\n"
                "Outcome probabilities must be built base-rate-first."
            ),
            output_artifact_type="preliminary_recommendation",
            mode="preliminary_recommendation",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case, "director", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Preliminary recommendation failed: {exc}")
        assert isinstance(artifact, PreliminaryRecommendation)
        write_thesis(case, artifact, trigger=ThesisTrigger.PRELIMINARY)

        if self._dual_track:
            self._run_track_b(case, artifact)

        self._gate(case, "preliminary_recommendation")
        _audit(case, "stage_completed", {"stage": "preliminary_recommendation"})
        return StepResult.ok()

    def handle_pre_mortem(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-pre-mortem",
            assignment=(
                "Assume the recommendation was followed and it failed badly. Write the "
                "explanation of why.\n"
                "Each failure mode must be specific to this decision, name its mechanism, "
                "and give at least one concrete leading indicator with a rough time.\n"
                "Rank by severity then probability. Do not soften."
            ),
            output_artifact_type="premortem_report",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case, "premortem", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            # A missing pre-mortem weakens the case but should not destroy the run.
            _audit(case, "pre_mortem_skipped", {"reason": str(exc)})
            return StepResult.ok()
        assert isinstance(artifact, PreMortemReport)
        case.write_artifact(artifact)
        _audit(
            case,
            "stage_completed",
            {
                "stage": "pre_mortem",
                "failure_mode_count": len(artifact.failure_modes),
                "most_likely_failure_mode": artifact.most_likely_failure_mode,
            },
        )
        return StepResult.ok()

    def handle_challenge(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        mode = "final_pass" if state.repair_cycle > 0 else "standard"
        task = InvokeTask(
            task_id=f"T-challenge-{state.repair_cycle}",
            assignment=(
                "Review the preliminary recommendation adversarially.\n"
                "Use the Section 6.3 checklist: hidden assumptions, contrary evidence, "
                "omitted alternatives, bias tests, tail risks, load-bearing assumptions.\n"
                "Emit up to 5 objections (standard) or 2 (final_pass), each with "
                "target_section, reversal_evidence, and materiality.\n"
                "Manufactured disagreement is prohibited."
            ),
            output_artifact_type="objection_batch",
            mode=mode,
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case, "challenger", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Challenge failed: {exc}")
        assert isinstance(artifact, ObjectionBatch)

        # Unpack objections into individual records
        unpack_objection_batch(case, artifact, task_id=f"T-challenge-{state.repair_cycle}")

        self._gate(case, "challenge")
        _audit(
            case,
            "stage_completed",
            {
                "stage": "challenge",
                "mode": mode,
                "objection_count": len(artifact.objections),
            },
        )
        return StepResult.ok()

    def handle_repair(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        # 1. Planner in repair mode
        task = InvokeTask(
            task_id=f"T-repair-{state.repair_cycle}",
            assignment=(
                "Commission targeted repair work to resolve the open objections.\n"
                "Each proposal must reference the objection IDs it resolves.\n"
                "Emit up to 4 proposals. Only propose work that addresses material objections."
            ),
            output_artifact_type="task_proposal_batch",
            mode="repair",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case, "planner", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Repair planning failed: {exc}")
        assert isinstance(artifact, TaskProposalBatch)

        result = apply_planner_acceptance_filter(case, artifact)
        accepted_batch = result.accepted_batch

        task_records: list[TaskRecord] = []
        edges: dict[str, list[str]] = {}
        for proposal in accepted_batch.proposals:
            task_id = case.next_id("T-")
            record = TaskRecord(
                task_id=task_id,
                role=proposal.task.role,
                issue_node_id=proposal.task.issue_node_id,
                question=proposal.task.question,
                why_it_matters=proposal.task.why_it_matters,
                expected_information_gain=proposal.task.expected_information_gain,
                materiality=proposal.task.materiality,
                probability_of_changing_conclusion=proposal.task.probability_of_changing_conclusion,
                estimated_cost=proposal.task.estimated_cost,
                inputs=list(proposal.task.inputs),
                required_output=proposal.task.required_output,
                completion_criteria=proposal.task.completion_criteria,
                status=TaskStatus.PLANNED,
                priority=proposal.task.priority,
                priority_score=proposal.task.priority_score,
                priority_rationale=proposal.task.priority_rationale,
            )
            task_records.append(record)
            deps = [
                task_records[idx].task_id
                for idx in proposal.depends_on_indices
                if idx < len(task_records)
            ]
            if deps:
                edges[task_id] = deps

        if task_records:
            self.task_graph.add_tasks(task_records, edges=edges or None)

            # Dispatch repair tasks
            runner = _build_task_runner(case, self._backend, self.budget_ledger)
            self.task_graph.dispatch(
                runner, max_concurrent=self._budget_config.max_concurrent_workers
            )
            critique_case_evidence(case, as_of=datetime.now(UTC).date())

        # 2. Director updates preliminary recommendation
        rec_task = InvokeTask(
            task_id=f"T-repair-rec-{state.repair_cycle}",
            assignment=(
                "Update the preliminary recommendation based on the new evidence "
                "from the repair cycle.\n"
                "Address the objections that were raised.\n"
                "Every material claim must cite E-* or A-* IDs."
            ),
            output_artifact_type="preliminary_recommendation",
            mode="preliminary_recommendation",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            rec_artifact = invoke(
                case, "director", rec_task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Repair recommendation update failed: {exc}")
        assert isinstance(rec_artifact, PreliminaryRecommendation)
        open_objection_ids = [
            record.objection_id
            for record in case.list_artifacts(ObjectionRecord)
            if record.resolution_status.value != "open"
        ]
        revision = write_thesis(
            case,
            rec_artifact,
            trigger=ThesisTrigger.REPAIR,
            objection_ids=open_objection_ids,
        )

        self._gate(case, "repair")
        _audit(
            case,
            "stage_completed",
            {
                "stage": "repair",
                "cycle": state.repair_cycle,
                "repair_tasks": len(task_records),
                "thesis_changed": revision.changed,
            },
        )
        return StepResult.ok()

    def handle_stop_decision(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        from orchestrator.state_machine import StepOutcome

        # Gather inputs for the stop evaluator
        objections = case.list_artifacts(ObjectionRecord)
        open_objections = [obj for obj in objections if obj.resolution_status.value == "open"]
        has_unresolved_material = any(obj.materiality is Level.HIGH for obj in open_objections)

        # A blocking gate finding is an open critical gap by definition: the evidence or
        # citation chain is broken, so the case must not be allowed to quietly conclude.
        gate_blocks = blocking_findings(case)
        coverage_share = self._issue_coverage_share(case)
        coverage_short = coverage_share is not None and coverage_share < MIN_ISSUE_COVERAGE_TO_STOP
        critical_gaps = has_unresolved_material or bool(gate_blocks) or coverage_short

        # Check for analysis results and compute stability
        analysis_results = case.list_artifacts(AnalysisResult)
        recommendation_stable = True
        try:
            prelim = case.read_artifact(PreliminaryRecommendation)
            if analysis_results:
                # Use the first analysis result for stability
                stability = compute_model_stability(
                    analysis_results[0],
                    candidate_alternative=prelim.preferred_alternative,
                )
                recommendation_stable = (
                    stability.share_of_sensitivity_runs_supporting_recommendation >= 0.5
                )
        except FileNotFoundError:
            pass

        # Budget remaining
        counters = state.budget_counters
        remaining = {
            "agent_invocations": max(
                0, self._budget_config.max_agent_invocations - counters.get("agent_invocations", 0)
            ),
            "high_tier_calls": max(
                0, self._budget_config.max_high_tier_calls - counters.get("high_tier_calls", 0)
            ),
            "research_tasks": max(
                0, self._budget_config.max_research_tasks - counters.get("research_tasks", 0)
            ),
        }

        # Deadline from the decision spec (if available).
        deadline_dt: datetime | None = None
        try:
            spec = case.read_artifact(DecisionSpec)
            if spec.deadline is not None:
                deadline_dt = datetime.combine(spec.deadline, datetime.min.time(), tzinfo=UTC)
        except FileNotFoundError:
            pass

        depth_limit_reached = self._wall_clock_exceeded(state)

        evaluator = StopEvaluator(clock=self._clock)
        from orchestrator.budget import StopEvaluatorInputs

        inputs = StopEvaluatorInputs(
            open_critical_evidence_gaps=critical_gaps,
            unresolved_material_objections=has_unresolved_material,
            recommendation_stable=recommendation_stable,
            expected_value_of_more_research_low=not critical_gaps,
            remaining_budget=remaining,
            deadline=deadline_dt,
            depth_limit_reached=depth_limit_reached,
        )
        decision = evaluator.evaluate(inputs)

        if decision.disclosure is not None:
            case.write_artifact(decision.disclosure)

        _audit(
            case,
            "stop_decision_evaluated",
            {
                "action": decision.action,
                "reasons": [r.value for r in decision.reasons],
                "repair_cycle": state.repair_cycle,
                "gate_blocking_checks": sorted({finding.check_id for finding in gate_blocks}),
                "issue_coverage": coverage_share,
            },
        )

        if decision.action == "stop":
            return StepResult.ok()
        return StepResult(StepOutcome.NEEDS_REPAIR)

    def handle_synthesis(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        retry_note = ""
        if state.synthesis_retries > 0:
            retry_note = (
                "\nThis is a re-synthesis. The previous final recommendation FAILED review. "
                "Read review_report.yaml in inputs/ and fix every defect it lists. Where a "
                "claim's citation does not support it, either cite evidence that does or "
                "remove the claim; do not restate it with softer wording."
            )
        # Final-gate send-back: the user requested a revision with a note.
        # This is independent of synthesis_retries (a review-triggered retry and a
        # user-triggered revision are different events with different budgets).
        if state.final_revisions > 0:
            try:
                final_approval = case.read_artifact(FinalApproval)
                user_note = final_approval.note
            except FileNotFoundError:
                user_note = ""
            if user_note:
                retry_note += (
                    "\nThe user rejected the final recommendation and requested a revision. "
                    f"Their note: {user_note}\n"
                    "Address the user's concerns alongside any review feedback."
                )
        task = InvokeTask(
            task_id=f"T-synthesis-{state.synthesis_retries}-fr-{state.final_revisions}",
            assignment=(
                "Integrate all artifacts into a FinalRecommendation.\n"
                "Cover all Section 16 blocks: executive recommendation, confidence explanation, "
                "alternatives ranking, key reasons, scenarios, quantitative findings, "
                "counterarguments, critical assumptions, change-triggers, next actions.\n"
                "Every material claim must cite E-/A- IDs.\n"
                "Pre-mortem leading indicators belong in recommendation_change_triggers.\n"
                "Averaging agent opinions is forbidden.\n"
                "Unresolved disagreement, including between reasoning tracks, must be "
                "reported as unresolved rather than split."
                f"{retry_note}"
            ),
            output_artifact_type="final_recommendation",
            timeout_s=_role_timeout(self._backend, "analyst"),
        )
        try:
            artifact = invoke(
                case, "synthesizer", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Synthesis failed: {exc}")
        assert isinstance(artifact, FinalRecommendation)
        case.write_artifact(artifact)
        self._gate(case, "synthesis")
        _audit(
            case,
            "stage_completed",
            {"stage": "synthesis", "attempt": state.synthesis_retries + 1},
        )
        return StepResult.ok()

    def _run_independent_review(self, case: Case, state: CaseState) -> IndependentReview | None:
        """Invoke the independent reviewer; a failure degrades rather than blocks.

        The reviewer sees the conclusion and the raw evidence but never the reasoning
        trail (see ``_independent_review_packet``).  If the invocation fails, the case
        proceeds without a second opinion rather than dying at the last gate — the
        absence is audited, and the reviewer's own gate check records nothing, so the
        omission is visible instead of silently passing as a concur.
        """
        task = InvokeTask(
            task_id=f"T-independent-review-{state.synthesis_retries}",
            assignment=(
                "You are the independent second opinion on this recommendation.\n"
                "You have the decision spec, the final recommendation, the evidence "
                "ledger, the assumption ledger and the evidence critique. You do NOT "
                "have the thesis history, objections, dual-track comparison or "
                "pre-mortem; that exclusion is deliberate.\n"
                "Answer one question: reading this evidence, would you reach this "
                "conclusion?\n"
                "Output an IndependentReview. Dissent only if you would reach a "
                "different conclusion, and name it."
            ),
            output_artifact_type="independent_review",
            timeout_s=_role_timeout(self._backend, "reviewer"),
        )
        try:
            artifact = invoke(
                case,
                "reviewer",
                task,
                backend=self._backend,
                variant="b",
                budget_ledger=self.budget_ledger,
            )
        except RoleInvocationFailed as exc:
            _audit(case, "independent_review_skipped", {"reason": str(exc)})
            return None
        assert isinstance(artifact, IndependentReview)
        case.write_artifact(artifact)
        _audit(
            case,
            "independent_review_recorded",
            {
                "verdict": artifact.verdict.value,
                "unsupported_claim_count": len(artifact.unsupported_claims),
            },
        )
        return artifact

    def handle_review(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        from orchestrator.state_machine import StepOutcome

        try:
            worksheet = build_verification_worksheet(case)
        except FileNotFoundError as exc:
            return StepResult.error(f"Review setup failed: {exc}")

        task = InvokeTask(
            task_id=f"T-review-{state.synthesis_retries}-fr-{state.final_revisions}",
            assignment=(
                "Verify the FinalRecommendation against the verification worksheet.\n"
                "Return one citation verdict for EVERY item_id in the worksheet; a review "
                "that skips items is not a review.\n"
                "Judge whether the quoted excerpts support each claim as written, including "
                "its magnitude and time frame.\n"
                "Treat any deterministic finding with severity 'block' as an automatic fail.\n"
                "Output a ReviewReport (pass, or fail with itemized defects)."
            ),
            output_artifact_type="review_report",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(
                case, "reviewer", task, backend=self._backend, budget_ledger=self.budget_ledger
            )
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Review failed: {exc}")
        assert isinstance(artifact, ReviewReport)
        case.write_artifact(artifact)

        accepted = review_is_acceptable(artifact, worksheet)
        # Persist the review verdict as an engine fact so ``done`` never silently
        # means "review failed" and a crash before review is distinguishable (None).
        state.review_accepted = accepted
        save_case_state(case, state)
        _audit(
            case,
            "review_evaluated",
            {
                "outcome": artifact.outcome.value,
                "accepted": accepted,
                "worksheet_items": len(worksheet.items),
                "verdicts_returned": len(artifact.citation_verdicts),
                "unsupported_verdicts": [
                    verdict.item_id
                    for verdict in artifact.citation_verdicts
                    if not verdict.supported
                ],
                "deterministic_blocks": [
                    finding.check_id
                    for finding in worksheet.deterministic_findings
                    if finding.severity.value == "block"
                ],
                "synthesis_retries": state.synthesis_retries,
            },
        )

        # SPEC-039 — independent review. Runs only once the conformance reviewer has
        # passed: there is no point asking a second opinion about a package whose
        # citations do not resolve, and it would burn a high-tier invocation per retry.
        independent: IndependentReview | None = None
        if accepted:
            independent = self._run_independent_review(case, state)
            if independent is not None and independent.verdict is IndependentVerdict.DISSENT:
                accepted = False
                state.review_accepted = False
                save_case_state(case, state)

        # Render unconditionally: if the retry budget is exhausted the state machine
        # advances to approval anyway, and an unrendered case would have no output.
        try:
            recommendation = case.read_artifact(FinalRecommendation)
            evidence = case.list_artifacts(EvidenceRecord)
            disclosure: DisclosureRecord | None = None
            try:
                disclosure = case.read_artifact(DisclosureRecord)
            except FileNotFoundError:
                pass
            premortem: PreMortemReport | None = None
            try:
                premortem = case.read_artifact(PreMortemReport)
            except FileNotFoundError:
                pass
            objective_weights: dict[str, float] | None = None
            try:
                objective_weights = case.read_artifact(DecisionSpec).objective_weights
            except FileNotFoundError:
                pass

            write_final_recommendation_markdown(
                case.root,
                recommendation,
                evidence,
                disclosure_record=disclosure,
                user_supplied_inputs=[self._raw_prompt],
                premortem_report=premortem,
                objective_weights=objective_weights,
                independent_review=independent,
                unanswered_questions=_unanswered_issue_questions(case),
            )
        except FileNotFoundError as exc:
            return StepResult.error(f"Render failed: {exc}")
        except ValueError as exc:
            # A failed review typically leaves a FinalRecommendation that cites
            # unsupported or dangling evidence IDs; rendering validates citations
            # and raises ValueError.  That must not crash the worker — the review
            # verdict below routes to resynthesis (or, once the retry budget is
            # spent, to the approval gate with review_accepted=False recorded).
            # Skip the unrenderable draft and let the state machine proceed so the
            # case stays inspectable instead of crashing on every resume.
            _audit(
                case,
                "render_skipped",
                {"stage": "review", "accepted": accepted, "reason": str(exc)},
            )

        _audit(case, "stage_completed", {"stage": "review", "accepted": accepted})
        if not accepted:
            return StepResult(StepOutcome.NEEDS_RESYNTHESIS)
        return StepResult.ok()
