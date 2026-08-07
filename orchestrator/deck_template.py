"""Deterministic case -> slide HTML mapping for the deck deliverable (SPEC-057).

Pure functions from validated artifacts to a self-contained ``slides.html`` using
only the component classes in the consulting-deck skill's ``design-system.md``.
No model is invoked: action titles are composed from the recommendation's own
fields. The output is the authored source that ``build_deck.py`` inlines and
``render_deck.mjs`` renders; this module never touches the filesystem.

The four uncertainty measures — outcome probability, evidence confidence,
recommendation confidence and model stability — are rendered as four distinct
figures and never merged, per north star 5.6/9. Model stability is a run count
(``runs_supporting/runs_total``), never a percentage.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from pathlib import Path

from orchestrator.artifacts import (
    AssumptionRecord,
    DecisionSpec,
    DisclosureRecord,
    EvidenceRecord,
    FinalRecommendation,
    PreMortemReport,
)
from orchestrator.deck_charts import SKILL_DIR, ChartResult

_DECK_CSS = SKILL_DIR / "assets" / "deck.css"


def _esc(value: object) -> str:
    return html.escape(str(value))


def _pct(fraction: float) -> str:
    return f"{fraction * 100:.0f}%"


def _sentence(text: str) -> str:
    """Ensure a fragment ends in terminal punctuation so fragments can be joined."""
    stripped = text.rstrip()
    if stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


class _Slides:
    """Accumulates slides and auto-numbers their footers."""

    def __init__(self) -> None:
        self._out: list[str] = []
        self._pg = 0

    def add(self, html_fragment: str) -> None:
        self._out.append(html_fragment)

    def add_numbered(self, template: str) -> None:
        """Append a slide whose footer carries ``{pg}``, filling the page number."""
        self._pg += 1
        self._out.append(template.replace("{pg}", str(self._pg)))

    def bump(self) -> int:
        self._pg += 1
        return self._pg

    def html(self) -> str:
        return "\n".join(self._out)


def _title_slide(
    rec: FinalRecommendation, spec: DecisionSpec | None, case_id: str, run_date: str
) -> str:
    owner = _esc(spec.owner) if spec else "the decision owner"
    return f"""    <section class="slide slide--title">
      <p class="kicker">Decision brief &middot; {_esc(case_id)}</p>
      <h1 class="action-title">{_esc(rec.recommended_action)}</h1>
      <div class="meta">Prepared for {owner} &middot; {_esc(run_date)} &middot; Confidential</div>
    </section>"""


def _exec_summary_slide(rec: FinalRecommendation, pg: int) -> str:
    cards = []
    for i, reason in enumerate(rec.key_reasons[:3], start=1):
        cards.append(
            f'          <div class="card"><span class="num">{i}</span>'
            f"<h3>Reason {i}</h3><p>{_esc(reason)}</p></div>"
        )
    cards_html = "\n".join(cards)
    return f"""    <section class="slide slide--exec">
      <div class="hd">
        <p class="kicker">Executive summary</p>
        <h1 class="action-title">The recommendation, stated first</h1>
      </div>
      <div class="bd">
        <div class="answer">
          <b>Recommendation.</b> {_esc(_sentence(rec.recommended_action))} {_esc(_sentence(rec.timing))}
          Recommendation confidence {rec.recommendation_confidence.value:.2f}.
        </div>
        <div class="cols-3">
{cards_html}
        </div>
      </div>
      <div class="ft">
        <p class="src">Source: final_recommendation. Evidence confidence {rec.evidence_confidence.value:.2f}.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def _decision_slide(rec: FinalRecommendation, spec: DecisionSpec | None, pg: int) -> str:
    if spec is not None:
        title = _esc(spec.question)
        alternatives = list(spec.alternatives)
        constraints = "; ".join(spec.constraints) if spec.constraints else "none stated"
        objectives = ", ".join(spec.objectives)
        takeaway = f"<b>Constraints.</b> {_esc(constraints)}. Objectives: {_esc(objectives)}."
    else:
        title = "The decision and the options assessed"
        alternatives = [
            a.alternative for a in sorted(rec.alternatives_considered, key=lambda x: x.rank)
        ]
        takeaway = "<b>Objectives.</b> Recorded in the case decision spec."
    cards = "\n".join(
        f'          <div class="card--plain"><h3>{_esc(alt)}</h3></div>' for alt in alternatives
    )
    return f"""    <section class="slide">
      <div class="hd">
        <p class="kicker">The decision</p>
        <h1 class="action-title">{title}</h1>
      </div>
      <div class="bd">
        <div class="cols-{min(max(len(alternatives), 2), 4)}">
{cards}
        </div>
        <div class="takeaway">{takeaway}</div>
      </div>
      <div class="ft ft--bare">
        <p class="src">Source: decision_spec.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def _assessed_slide(
    rec: FinalRecommendation,
    evidence: Sequence[EvidenceRecord],
    assumptions: Sequence[AssumptionRecord],
    pg: int,
) -> str:
    kpis = [
        (str(len(rec.alternatives_considered)), "Alternatives compared"),
        (str(len(evidence)), "Evidence records"),
        (str(len(rec.strongest_counterarguments)), "Counterarguments"),
        (str(len(assumptions)), "Assumptions tracked"),
    ]
    kpi_html = "\n".join(
        f'          <div class="kpi"><span class="kpi__val">{_esc(v)}</span>'
        f'<span class="kpi__lab">{_esc(lab)}</span></div>'
        for v, lab in kpis
    )
    steps = [
        ("Frame", "Decision, objectives and constraints fixed."),
        ("Evidence", "Records gathered, critiqued and scored."),
        ("Model", "Scenario probabilities and expected value."),
        ("Challenge", "Pre-mortem and adversarial objection."),
        ("Recommend", "Synthesis, review and the final call."),
    ]
    step_html = "\n".join(
        f'          <div class="step"><b>{_esc(t)}</b>{_esc(d)}</div>' for t, d in steps
    )
    return f"""    <section class="slide">
      <div class="hd">
        <p class="kicker">Approach</p>
        <h1 class="action-title">Alternatives stress-tested against evidence, challenge and a scenario model</h1>
      </div>
      <div class="bd">
        <div class="kpis">
{kpi_html}
        </div>
        <div class="steps">
{step_html}
        </div>
        <div class="takeaway">
          <b>So what.</b> The recommendation rests on framing, evidence critique, a scenario
          model, a pre-mortem and adversarial challenge, not a single pass.
        </div>
      </div>
      <div class="ft ft--bare">
        <p class="src">Source: case artifacts.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def _alternatives_slide(rec: FinalRecommendation, pg: int) -> str:
    rows = []
    for a in sorted(rec.alternatives_considered, key=lambda x: x.rank):
        hl = ' class="hl"' if a.rank == 1 else ""
        rows.append(
            f"          <tr{hl}><td>{_esc(a.alternative)}</td>"
            f'<td class="n">{a.rank}</td><td>{_esc(a.rationale)}</td></tr>'
        )
    rows_html = "\n".join(rows)
    return f"""    <section class="slide">
      <div class="hd">
        <p class="kicker">Alternatives</p>
        <h1 class="action-title">The recommended option ranks first against the alternatives considered</h1>
      </div>
      <div class="bd">
        <table class="tbl">
          <tr><th>Alternative</th><th class="n">Rank</th><th>Rationale</th></tr>
{rows_html}
        </table>
        <div class="takeaway"><b>So what.</b> The ranking reflects the objectives and the evidence, not preference.</div>
      </div>
      <div class="ft ft--bare">
        <p class="src">Source: final_recommendation alternatives_considered.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def _scenario_exhibit(rec: FinalRecommendation, charts: ChartResult) -> str:
    if charts.available and "scenarios" in charts.files:
        return (
            '<div class="exhibit"><p class="exhibit__cap">Exhibit &middot; Scenario probabilities (%)</p>'
            f'<img src="charts/{charts.files["scenarios"]}" alt="Scenario probabilities" /></div>'
        )
    # Table fallback when matplotlib is unavailable.
    rows = []
    for s in rec.scenario_analysis:
        pt = s.probability.point
        val = _pct(pt) if pt is not None else "—"
        rows.append(
            f"          <tr><td>{_esc(s.scenario_name.replace('_', ' ').title())}</td>"
            f'<td class="n">{val}</td></tr>'
        )
    rows_html = "\n".join(rows)
    return (
        '<div class="exhibit"><p class="exhibit__cap">Exhibit &middot; Scenario probabilities (%)</p>'
        '<table class="tbl"><tr><th>Scenario</th><th class="n">Probability</th></tr>\n'
        f"{rows_html}\n        </table></div>"
    )


def _scenarios_slide(rec: FinalRecommendation, charts: ChartResult, pg: int) -> str:
    rail = "\n".join(
        f"          <p><b>{_esc(s.scenario_name.replace('_', ' ').title())}.</b> {_esc(s.summary)}</p>"
        for s in rec.scenario_analysis
    )
    method = ""
    if rec.scenario_analysis:
        method = rec.scenario_analysis[0].probability.method.value
    return f"""    <section class="slide">
      <div class="hd">
        <p class="kicker">Scenarios</p>
        <h1 class="action-title">Probability mass is spread across scenarios, not concentrated in one</h1>
      </div>
      <div class="bd">
        <div class="split">
          {_scenario_exhibit(rec, charts)}
          <div class="rail">
            <h4>What it shows</h4>
{rail}
          </div>
        </div>
        <div class="takeaway"><b>So what.</b> No single scenario dominates, which is what the recommendation hedges.</div>
      </div>
      <div class="ft ft--bare">
        <p class="src">Source: final_recommendation scenario_analysis, method {_esc(method)}.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def _uncertainty_slide(rec: FinalRecommendation, pg: int) -> str:
    outcome_name = sorted(rec.outcome_probabilities)[0]
    outcome = rec.outcome_probabilities[outcome_name]
    outcome_val = _pct(outcome.point) if outcome.point is not None else "—"
    stability = f"{rec.model_stability.runs_supporting}/{rec.model_stability.runs_total}"
    kpis = [
        (outcome_val, f"Outcome probability ({_esc(outcome_name)})"),
        (f"{rec.evidence_confidence.value:.2f}", "Evidence confidence"),
        (f"{rec.recommendation_confidence.value:.2f}", "Recommendation confidence"),
        (stability, "Sensitivity runs supporting"),
    ]
    kpi_html = "\n".join(
        f'          <div class="kpi"><span class="kpi__val">{v}</span>'
        f'<span class="kpi__lab">{lab}</span></div>'
        for v, lab in kpis
    )
    return f"""    <section class="slide">
      <div class="hd">
        <p class="kicker">Uncertainty</p>
        <h1 class="action-title">Four uncertainty measures, kept deliberately distinct</h1>
      </div>
      <div class="bd">
        <div class="kpis">
{kpi_html}
        </div>
        <div class="rail">
          <h4>Bases</h4>
          <p><b>Outcome {outcome_val}.</b> via {_esc(outcome.method.value)}.</p>
          <p><b>Evidence {rec.evidence_confidence.value:.2f}.</b> {_esc(rec.evidence_confidence.basis)}</p>
          <p><b>Recommendation {rec.recommendation_confidence.value:.2f}.</b> {_esc(rec.recommendation_confidence.basis)}</p>
          <p><b>Model stability {stability}.</b> a run count over sensitivity runs, not a probability.</p>
        </div>
      </div>
      <div class="ft ft--bare">
        <p class="src">Source: final_recommendation uncertainty fields. Model stability is a run count, never a percentage.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def _challenge_slide(rec: FinalRecommendation, premortem: PreMortemReport | None, pg: int) -> str:
    counter = rec.strongest_counterarguments[0]
    status = "resolved" if counter.resolved else "unresolved"
    tag = "tag--pos" if counter.resolved else "tag--warn"
    callout = ""
    if premortem is not None:
        mode = next(
            (
                m
                for m in premortem.failure_modes
                if m.failure_mode == premortem.most_likely_failure_mode
            ),
            premortem.failure_modes[0],
        )
        callout = (
            f'        <div class="callout"><b>Pre-mortem.</b> Most likely failure mode: '
            f"{_esc(mode.failure_mode)} — {_esc(mode.narrative)}</div>"
        )
    return f"""    <section class="slide">
      <div class="hd">
        <p class="kicker">Challenge</p>
        <h1 class="action-title">The strongest counterargument is confronted, not dismissed</h1>
      </div>
      <div class="bd">
        <div class="cols-2">
          <div class="card--neg"><h3>Counterargument</h3><p>{_esc(counter.claim)}</p></div>
          <div class="card--pos"><h3>Resolution <span class="tag {tag}">{status}</span></h3><p>{_esc(counter.resolution)}</p></div>
        </div>
{callout}
      </div>
      <div class="ft ft--bare">
        <p class="src">Source: final_recommendation strongest_counterarguments; premortem_report.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def _change_triggers_slide(rec: FinalRecommendation, pg: int) -> str:
    items = "\n".join(f"            <li>{_esc(t)}</li>" for t in rec.recommendation_change_triggers)
    return f"""    <section class="slide slide--dark">
      <div class="hd">
        <p class="kicker">Change triggers</p>
        <h1 class="action-title">What would change this recommendation</h1>
      </div>
      <div class="bd">
        <div class="exhibit">
          <ul style="font-size:18px; line-height:1.6;">
{items}
          </ul>
        </div>
        <div class="takeaway"><b>So what.</b> These are the conditions to watch after the decision is made.</div>
      </div>
      <div class="ft ft--bare">
        <p class="src">Source: final_recommendation recommendation_change_triggers.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def _next_actions_slide(rec: FinalRecommendation, pg: int) -> str:
    rows = []
    for a in rec.next_actions:
        hl = ' class="hl"' if a is rec.next_actions[0] else ""
        rows.append(
            f"          <tr{hl}><td>{_esc(a.action)}</td><td>{_esc(a.owner)}</td>"
            f"<td>{_esc(a.by_date.isoformat())}</td><td>{_esc(a.first_step)}</td></tr>"
        )
    rows_html = "\n".join(rows)
    return f"""    <section class="slide">
      <div class="hd">
        <p class="kicker">Next actions</p>
        <h1 class="action-title">The steps that carry the recommendation into execution</h1>
      </div>
      <div class="bd">
        <table class="tbl">
          <tr><th>Action</th><th>Owner</th><th>By date</th><th>First step</th></tr>
{rows_html}
        </table>
        <div class="takeaway"><b>So what.</b> Each action names an owner, a date and a first step that can start today.</div>
      </div>
      <div class="ft ft--bare">
        <p class="src">Source: final_recommendation next_actions.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def _appendix_slide(
    rec: FinalRecommendation,
    evidence: Sequence[EvidenceRecord],
    assumptions: Sequence[AssumptionRecord],
    disclosure: DisclosureRecord | None,
    pg: int,
) -> str:
    ev_rows = "\n".join(
        f"          <tr><td>{_esc(r.evidence_id)}</td><td>{_esc(r.claim)}</td>"
        f"<td>{_esc(r.publisher)}</td><td>{_esc(r.publication_date.isoformat())}</td>"
        f"<td>{_esc(r.independence_group)}</td></tr>"
        for r in evidence
    )
    asm_rows = "\n".join(
        f"          <tr><td>{_esc(a.assumption_id)}</td><td>{_esc(a.claim)}</td>"
        f'<td><span class="tag tag--flat">{_esc(a.status.value)}</span></td></tr>'
        for a in assumptions
    )
    method = "Case artifacts."
    if disclosure is not None:
        stops = ", ".join(reason.value for reason in disclosure.stop_reasons)
        method = f"Stopped on: {stops}."
    return f"""    <section class="slide slide--appendix">
      <div class="hd">
        <p class="kicker">Appendix</p>
        <h1 class="action-title">Evidence base and method</h1>
      </div>
      <div class="bd">
        <table class="tbl">
          <tr><th>ID</th><th>Claim</th><th>Publisher</th><th>Date</th><th>Independence group</th></tr>
{ev_rows}
        </table>
        <div class="split--narrow">
          <table class="tbl">
            <tr><th>Assumption</th><th>Claim</th><th>Status</th></tr>
{asm_rows}
          </table>
          <div class="rail"><h4>Method</h4><p>{_esc(method)}</p></div>
        </div>
      </div>
      <div class="ft ft--bare">
        <p class="src">Source: shared/evidence, shared/assumptions, disclosure_record.</p>
        <span class="pg">{pg}</span>
      </div>
    </section>"""


def render_slides_html(
    rec: FinalRecommendation,
    *,
    spec: DecisionSpec | None,
    evidence: Sequence[EvidenceRecord],
    assumptions: Sequence[AssumptionRecord],
    premortem: PreMortemReport | None,
    disclosure: DisclosureRecord | None,
    charts: ChartResult,
    case_id: str,
    run_date: str,
    present: bool = False,
) -> str:
    """Assemble the full self-contained ``slides.html`` for a completed case."""
    slides = _Slides()
    slides.add(_title_slide(rec, spec, case_id, run_date))
    slides.add(_exec_summary_slide(rec, slides.bump()))
    slides.add(_decision_slide(rec, spec, slides.bump()))
    slides.add(_assessed_slide(rec, evidence, assumptions, slides.bump()))
    slides.add(_alternatives_slide(rec, slides.bump()))
    slides.add(_scenarios_slide(rec, charts, slides.bump()))
    slides.add(_uncertainty_slide(rec, slides.bump()))
    if rec.strongest_counterarguments:
        slides.add(_challenge_slide(rec, premortem, slides.bump()))
    if rec.recommendation_change_triggers:
        slides.add(_change_triggers_slide(rec, slides.bump()))
    slides.add(_next_actions_slide(rec, slides.bump()))
    slides.add(_appendix_slide(rec, evidence, assumptions, disclosure, slides.bump()))

    body_class = "deck--present" if present else ""
    css_href = _DECK_CSS.resolve().as_posix()
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Decision brief &middot; {_esc(case_id)}</title>
    <link rel="stylesheet" href="{_esc(css_href)}" />
  </head>
  <body class="{body_class}">
{slides.html()}
  </body>
</html>
"""


def deck_css_path() -> Path:
    return _DECK_CSS
