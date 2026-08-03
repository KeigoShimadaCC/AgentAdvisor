## Executive recommendation

Choose **option B, buy a SaaS analytics platform now**, and deploy it **this quarter, ideally within 1 to 2 weeks**. Structure the purchase as a **short-term or easily cancellable contract with clear data export/API rights**, then reassess after 60 to 90 days; do **not** start a custom build this quarter unless no viable SaaS option can satisfy must-have requirements after a fast pilot [U1].

## Decision confidence

**Recommendation confidence: moderately high.** The quarter deadline and the current cost/time estimates make the near-term choice fairly one-sided: the custom build is estimated at four months, so it likely misses the quarter even if execution goes well [U1].  
**Evidence confidence: moderate.** The core facts come from the decision prompt, but we do not yet have vendor quotes, security findings, or a quantified value estimate for the core roadmap work displaced by a build [U1].  
**Major uncertainty:** whether your analytics needs will become differentiated enough, or vendor pricing will rise enough, that owning the stack becomes economically superior within 12 to 24 months [Calc1].

## Alternatives considered

1. **Buy SaaS now**. Best rank because it meets the timing requirement, has the lowest near-term cash outlay, and preserves scarce engineering focus for the core product roadmap [U1][2][3].  
2. **Hybrid or staged migration**. Buy SaaS now, but design for portability and revisit an internal build later if requirements harden. This is a good fallback, but it adds planning and engineering overhead immediately without proof that a custom product is strategically necessary [U1][Calc1].  
3. **Build custom now**. Lowest rank because it is the highest-risk path on both delivery and roadmap impact, and it is estimated to take longer than the quarter before accounting for normal scope and integration slippage [U1][1].

## Key reasons

- **Deadline fit dominates**: four months for a build is longer than the quarter; SaaS is available immediately [U1].  
- **Economics favor buying for the next several years**: at $2,000 per month, SaaS reaches the $80,000 build cost only around **month 40**, before counting build maintenance or overrun risk [U1][Calc1].  
- **Roadmap protection matters more in a 10-person startup**: internal tools should reduce product-team cognitive load, not create another non-core product to own and maintain [2][3].  
- **Delivery risk is asymmetric**: internal software efforts frequently overrun, while the buy option mainly concentrates risk in vendor fit and contract terms, which are easier to surface quickly in a pilot [1][U1].

## Scenario analysis

- **Upside scenario, ~25%**: SaaS is deployed in 1 to 2 weeks, covers the core use cases, and total 12-month direct spend stays around **$24,000 to $30,000**. Core roadmap stays intact [U1][Calc1].  
- **Base scenario, ~50%**: deployment happens this month, some configuration gaps remain, and 12-month spend lands around **$30,000 to $40,000**. Recommendation still stands because delivery is on time and much cheaper than building now [Calc1].  
- **Downside scenario, ~20%**: pricing expands through seats/events/services, or fit gaps require workarounds, pushing 12-month direct spend to **$40,000 to $60,000**. Even then, it likely remains cheaper and faster than building this quarter [Calc1].  
- **Tail-risk scenario, ~5%**: vendor fit, security, or lock-in problems force a later migration or custom build; combined 12-month direct spend could approach **$90,000+** before migration labor. This is the main risk to the recommendation, which is why contract flexibility and export rights matter [Calc1].

## Quantitative findings

- **This-quarter direct spend**: build about **$80,000** versus SaaS about **$6,000** [U1].  
- **12-month direct spend at list price**: SaaS about **$24,000** [U1].  
- **Cash break-even horizon**: SaaS equals the $80,000 build cost at roughly **40 months** (`$80,000 / $2,000`) [Calc1].  
- **Monthly SaaS price that would equal build cost**: about **$6,667/month over 12 months**, **$3,333/month over 24 months**, and **$2,222/month over 36 months** [Calc1].  
- **Illustrative expected direct cost over 12 months**: buy-now path about **$35,200** versus build-now path about **$119,000** under reasonable scenario weights. This excludes the economic value of roadmap work delayed by a build, which would widen the gap further [Calc1].

## Strongest counterarguments

- **“We should own the stack to avoid lock-in and get perfect fit.”** True in principle, but unresolved custom needs are not enough reason to miss the quarter and divert engineering now. The better response is to buy with portability guardrails and revisit once real usage clarifies what is genuinely unique.  
- **“Recurring SaaS fees may become expensive.”** Also true, but at the quoted price the vendor does not catch the current build estimate until about month 40, and that is before including build overrun and maintenance risk [U1][Calc1].  
- **“Security or data-governance requirements may rule out SaaS.”** This remains unresolved because no vendor shortlist or diligence results were provided. It should be treated as a gating check in the next actions, not as a reason to default to a custom build today.

## Critical assumptions

- A viable SaaS option can satisfy **most must-have dashboard needs** with configuration rather than deep product engineering.  
- The quoted **$2,000/month** is directionally representative of expected first-year pricing [U1].  
- There is meaningful opportunity cost to pulling engineers off the core product roadmap this quarter.  
- Customer analytics is currently a **supporting capability**, not the startup’s main product differentiator.  
- No non-negotiable compliance, residency, or security constraint automatically disqualifies SaaS.

## What would change the recommendation

- Shortlisted vendors fail a fast pilot on must-have use cases within 1 to 2 weeks.  
- All-in SaaS cost is materially above the quoted level, roughly **>$6.7k/month over a 12-month commitment** or **>$3.3k/month over 24 months**, without offsetting strategic value [Calc1].  
- Contract terms do not provide acceptable **data export, API access, or termination flexibility**.  
- Customer analytics becomes a clear strategic differentiator for the product, making ownership of the stack worth the roadmap cost.  
- The deadline moves out materially and the team has genuine spare engineering capacity.

## Next actions

1. **Shortlist 2 to 3 SaaS vendors this week** against required dashboards, integration needs, security, export/API rights, and contract flexibility.  
2. **Run a fast pilot** with real event data and 3 to 5 must-have dashboards; time-box it to 1 week.  
3. **Negotiate for reversibility**: month-to-month or short initial term, clear data export, no punitive exit terms.  
4. **Set a 60- to 90-day review** with explicit triggers for staying on SaaS, moving to a hybrid path, or planning a custom build.  
5. **Do not allocate core engineers to a full custom build this quarter** unless every credible SaaS option fails the pilot or compliance review.

## Evidence and citations

**Inline citation key**

- **[U1]** User-provided decision facts: 10-person startup; build estimate about $80,000 and four months; SaaS about $2,000/month and immediate deployment.  
- **[Calc1]** Author calculations based on [U1] and explicitly stated scenario assumptions: break-even horizon, threshold monthly prices, and illustrative scenario-weighted expected costs.  
- **[1]** McKinsey & Company, *Delivering large-scale IT projects on time, on budget, and on value* (2012). Used for the directional claim that internal IT/software efforts often overrun and can create material delivery risk.  
  URL: `https://www.mckinsey.com/capabilities/tech-and-ai/our-insights/delivering-large-scale-it-projects-on-time-on-budget-and-on-value`  
- **[2]** DORA, *Capabilities: Platform engineering*. Used for the point that the primary goal of platform work is to reduce developer cognitive load by abstracting complexity.  
  URL: `https://dora.dev/capabilities/platform-engineering/`  
- **[3]** Martin Fowler, *Team Topologies* (bliki, 2023). Used for the related point that platform work is justified when it reduces cognitive load on stream-aligned teams.  
  URL: `https://martinfowler.com/bliki/TeamTopologies.html`