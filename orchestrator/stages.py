"""Stage handlers wiring roles to the SPEC-007 state machine.

Each handler is a method on :class:`StageHandlers` matching the
``handler_name`` in ``_FLOW_PLANS`` (``orchestrator/state_machine.py``).
Handlers contain orchestration only; every substantive judgment stays
inside role invocations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from orchestrator.artifacts import (
    AnalysisResult,
    AuditEvent,
    DecisionSpec,
    DisclosureRecord,
    EvidenceBatch,
    EvidenceRecord,
    FinalRecommendation,
    IntakeRecord,
    Level,
    ObjectionBatch,
    ObjectionRecord,
    PreliminaryRecommendation,
    ReviewReport,
    TaskProposalBatch,
    TaskRecord,
    TaskStatus,
)
from orchestrator.backend import AgentBackend
from orchestrator.budget import BudgetConfig, BudgetLedger, StopEvaluator
from orchestrator.case_store import Case
from orchestrator.invoke_role import (
    InvokeTask,
    RoleInvocationFailed,
    invoke,
    invoke_read_only,
)
from orchestrator.normalize import normalize_evidence_batch
from orchestrator.planning import apply_planner_acceptance_filter
from orchestrator.render import write_final_recommendation_markdown
from orchestrator.reproduce import reproduce_analysis_result
from orchestrator.stability import compute_model_stability
from orchestrator.state_machine import CaseState, StepHandler, StepPlan, StepResult
from orchestrator.task_graph import TaskExecutionResult, TaskGraph
from orchestrator.unpack import unpack_objection_batch

DEFAULT_TIMEOUT_S = 300.0
ANALYST_TIMEOUT_S = 600.0
STALE_AFTER_DAYS = 365


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
        # The researcher produces evidence_batch, the challenger produces objection_batch.
        if role == "researcher":
            artifact_type = "evidence_batch"
        elif role == "challenger":
            artifact_type = "objection_batch"

        timeout = ANALYST_TIMEOUT_S if role == "analyst" else DEFAULT_TIMEOUT_S
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

        config_role = role
        if role == "researcher":
            config_role = "researcher"
        elif role == "analyst":
            config_role = "analyst"

        try:
            if role == "auditor":
                artifact = invoke_read_only(case, config_role, invoke_task, backend=backend)
            else:
                artifact = invoke(case, config_role, invoke_task, backend=backend)
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
    ) -> None:
        self._backend = backend
        self._budget_config = budget_config
        self._raw_prompt = raw_prompt
        self._model_tier_map = model_tier_map or {}
        self._budget_ledger: BudgetLedger | None = None
        self._task_graph: TaskGraph | None = None

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

    def handlers(self) -> dict[str, StepHandler]:
        return {
            "intake": self.handle_intake,
            "framing": self.handle_framing,
            "provisional_thesis": self.handle_provisional_thesis,
            "planning": self.handle_planning,
            "investigation": self.handle_investigation,
            "preliminary_recommendation": self.handle_preliminary_recommendation,
            "challenge": self.handle_challenge,
            "repair": self.handle_repair,
            "stop_decision": self.handle_stop_decision,
            "synthesis": self.handle_synthesis,
            "review": self.handle_review,
        }

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
            artifact = invoke(case, "intake", task, backend=self._backend)
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Intake failed: {exc}")
        assert isinstance(artifact, IntakeRecord)
        case.write_artifact(artifact)
        _audit(case, "stage_completed", {"stage": "intake"})
        return StepResult.ok()

    def handle_framing(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-framing",
            assignment=(
                "Produce a schema-valid decision specification from the provided intake input.\n"
                f"Case ID: {case.root.name}\nOwner: user"
            ),
            output_artifact_type="decision_spec",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(case, "director", task, backend=self._backend, variant="framing")
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Framing failed: {exc}")
        assert isinstance(artifact, DecisionSpec)
        case.write_artifact(artifact)
        _audit(case, "stage_completed", {"stage": "framing"})
        return StepResult.ok()

    def handle_provisional_thesis(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-provisional-thesis",
            assignment=(
                "Form a provisional thesis based on the decision specification.\n"
                "State your preferred alternative, the rationale, and at least 3 uncertainties "
                "that could most plausibly reverse it.\n"
                "This is NOT the final answer; it is a provisional thesis to guide research."
            ),
            output_artifact_type="preliminary_recommendation",
            mode="provisional_thesis",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(case, "director", task, backend=self._backend)
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Provisional thesis failed: {exc}")
        assert isinstance(artifact, PreliminaryRecommendation)
        case.write_artifact(artifact)
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
            artifact = invoke(case, "planner", task, backend=self._backend)
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
            },
        )
        return StepResult.ok()

    def handle_investigation(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        runner = _build_task_runner(case, self._backend, self.budget_ledger)

        all_started: list[str] = []
        all_completed: list[str] = []
        all_failed: list[str] = []

        # Dispatch waves until no more ready tasks
        while True:
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

    def handle_preliminary_recommendation(
        self, case: Case, state: CaseState, plan: StepPlan
    ) -> StepResult:
        task = InvokeTask(
            task_id="T-preliminary-rec",
            assignment=(
                "Produce a preliminary recommendation based on all available evidence, "
                "assumptions, and analysis results.\n"
                "Every material claim must cite E-* or A-* IDs.\n"
                "Recommendation confidence and evidence confidence must be separate.\n"
                "Outcome probabilities must be built base-rate-first."
            ),
            output_artifact_type="preliminary_recommendation",
            mode="preliminary_recommendation",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(case, "director", task, backend=self._backend)
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Preliminary recommendation failed: {exc}")
        assert isinstance(artifact, PreliminaryRecommendation)
        case.write_artifact(artifact)
        _audit(case, "stage_completed", {"stage": "preliminary_recommendation"})
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
            artifact = invoke(case, "challenger", task, backend=self._backend)
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Challenge failed: {exc}")
        assert isinstance(artifact, ObjectionBatch)

        # Unpack objections into individual records
        unpack_objection_batch(case, artifact)

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
            artifact = invoke(case, "planner", task, backend=self._backend)
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
            rec_artifact = invoke(case, "director", rec_task, backend=self._backend)
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Repair recommendation update failed: {exc}")
        assert isinstance(rec_artifact, PreliminaryRecommendation)
        case.write_artifact(rec_artifact)

        _audit(
            case,
            "stage_completed",
            {
                "stage": "repair",
                "cycle": state.repair_cycle,
                "repair_tasks": len(task_records),
            },
        )
        return StepResult.ok()

    def handle_stop_decision(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        from orchestrator.state_machine import StepOutcome

        # Gather inputs for the stop evaluator
        objections = case.list_artifacts(ObjectionRecord)
        open_objections = [obj for obj in objections if obj.resolution_status.value == "open"]
        has_unresolved_material = any(obj.materiality is Level.HIGH for obj in open_objections)

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
        }

        evaluator = StopEvaluator(clock=datetime.now)
        from orchestrator.budget import StopEvaluatorInputs

        inputs = StopEvaluatorInputs(
            open_critical_evidence_gaps=has_unresolved_material,
            unresolved_material_objections=has_unresolved_material,
            recommendation_stable=recommendation_stable,
            expected_value_of_more_research_low=not has_unresolved_material,
            remaining_budget=remaining,
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
            },
        )

        if decision.action == "stop":
            return StepResult.ok()
        return StepResult(StepOutcome.NEEDS_REPAIR)

    def handle_synthesis(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-synthesis",
            assignment=(
                "Integrate all artifacts into a FinalRecommendation.\n"
                "Cover all Section 16 blocks: executive recommendation, confidence explanation, "
                "alternatives ranking, key reasons, scenarios, quantitative findings, "
                "counterarguments, critical assumptions, change-triggers, next actions.\n"
                "Every material claim must cite E-/A- IDs.\n"
                "Averaging agent opinions is forbidden.\n"
                "Unresolved disagreement must be reported as such."
            ),
            output_artifact_type="final_recommendation",
            timeout_s=ANALYST_TIMEOUT_S,
        )
        try:
            artifact = invoke(case, "synthesizer", task, backend=self._backend)
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Synthesis failed: {exc}")
        assert isinstance(artifact, FinalRecommendation)
        case.write_artifact(artifact)
        _audit(case, "stage_completed", {"stage": "synthesis"})
        return StepResult.ok()

    def handle_review(self, case: Case, state: CaseState, plan: StepPlan) -> StepResult:
        task = InvokeTask(
            task_id="T-review",
            assignment=(
                "Review the FinalRecommendation for calibration and citation quality.\n"
                "Check: false precision, confidence mismatch, citation validity, "
                "independence overstatement.\n"
                "Output a ReviewReport (pass or fail with itemized defects)."
            ),
            output_artifact_type="review_report",
            timeout_s=DEFAULT_TIMEOUT_S,
        )
        try:
            artifact = invoke(case, "reviewer", task, backend=self._backend)
        except RoleInvocationFailed as exc:
            return StepResult.error(f"Review failed: {exc}")
        assert isinstance(artifact, ReviewReport)
        case.write_artifact(artifact)

        # Render the final recommendation
        try:
            recommendation = case.read_artifact(FinalRecommendation)
            evidence = case.list_artifacts(EvidenceRecord)
            disclosure: DisclosureRecord | None = None
            try:
                disclosure = case.read_artifact(DisclosureRecord)
            except FileNotFoundError:
                pass

            write_final_recommendation_markdown(
                case.root,
                recommendation,
                evidence,
                disclosure_record=disclosure,
                user_supplied_inputs=[self._raw_prompt],
            )
        except FileNotFoundError as exc:
            return StepResult.error(f"Render failed: {exc}")

        _audit(case, "stage_completed", {"stage": "review"})
        return StepResult.ok()
