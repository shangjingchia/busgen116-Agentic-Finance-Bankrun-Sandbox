# architecture.md — Technical Design Notes

This document captures the key technical design decisions and the rationale behind them. Read after CLAUDE.md and PLAN.md.

## The core abstraction: events

The simulation is a sequence of `Event` objects processed by an event queue. Every state change in the system happens via an event. This is what makes the v2 path clean — adding a new scenario type means adding a new event type, not new code paths through the engine.

Event types in v1:

- `RumorPublished(content, source, credibility, timestamp, target_agents)` — a piece of information enters the environment.
- `AgentObserved(agent_id, event_id, observation_latency)` — a specific agent observes a specific event after some latency.
- `AgentDecisionTriggered(agent_id, trigger_reason)` — an agent has cause to make a decision.
- `AgentActed(agent_id, action, reasoning)` — an agent has executed an action.
- `WithdrawalProcessed(agent_id, bank_id, amount)` — a bank has processed a withdrawal.
- `BankReserveUpdated(bank_id, new_reserves)` — bank state changed.
- `SocialSignalEmitted(action_event_id, visibility)` — an agent's action is published to a feed.

The engine is just: process events in timestamp order, fire handlers for each event type, handlers may emit new events.

## The Agent abstraction

An `Agent` is a dataclass with:

- `id`: identifier.
- `persona`: a `Persona` object — see below.
- `portfolio`: dict mapping bank_id and asset_type to amount.
- `subscriptions`: which information feeds this agent observes.
- `decision_history`: list of past decisions, used for context in future prompts.
- `state`: enum {active, has_decided, withdrawn}.

Agents do not have methods that compute decisions. Decisions happen via the `decide` function in `decisions/decision.py`, which takes an Agent and a context and returns a structured action. This separation means we can swap decision strategies (cheap LLM, strategic LLM, deterministic baseline) without changing the agent.

## The Persona abstraction

A `Persona` is what makes heterogeneity genuine. It includes:

- `archetype`: one of {cautious_retiree, aggressive_trader, gig_worker, institutional_treasurer}.
- `demographics`: age, income, dependents.
- `risk_tolerance`: numeric, 0-1, but framed in prose for the LLM ("very averse to losing principal" vs. "comfortable with significant volatility").
- `financial_sophistication`: numeric, 0-1, also framed in prose. Affects vocabulary in the prompt.
- `goals`: list of strings ("preserve capital for retirement", "grow wealth aggressively").
- `trust_profile`: how they react to news and rumors ("skeptical of social media", "follows financial Twitter closely").
- `voice_examples`: 2-3 example phrases this persona would use, given to the LLM as style anchors.
- `cost_function`: a structured description of what costs this persona's principal experiences, by category. See below.

The persona is rendered into a system prompt for every LLM call this agent makes. Two agents with the same archetype but different specific personas will produce different outputs because the rendered prompts are different.

### The cost_function field

The `cost_function` is what makes agents reason with stakes. It is a list of `(cost_category, severity, narrative)` tuples where:

- `cost_category` is one of {principal_loss, withdrawal_fees, locked_in_loss, missed_upside, cash_flow_disruption, reputational_damage, action_inaction_asymmetry}.
- `severity` is one of {catastrophic, significant, moderate, minor, irrelevant}.
- `narrative` is a 1-2 sentence prose description of *why* this cost matters to this principal.

Severity is qualitative on purpose. Quantitative thresholds (e.g., "lose more than 5%") would over-determine the LLM's decision — the model would just compare numbers. Qualitative severities force the LLM to weigh tradeoffs in context, which is what we actually want to study. The narrative grounds the severity in a specific, plausible reason ("your principal is 67 and depends on this money for groceries") so the model has texture to reason with.

Example for cautious_retiree:
```python
cost_function = [
    ("principal_loss", "catastrophic",
     "Your principal is 67 and depends on this money. A 10% drawdown forces them to delay retirement or change lifestyle."),
    ("withdrawal_fees", "significant",
     "The CD has a 3% early withdrawal penalty — three months of grocery money on a $50k deposit."),
    ("locked_in_loss", "significant",
     "Panic-withdrawing on a false rumor crystallizes a tax event and loses interest income for months."),
    ("missed_upside", "minor",
     "You're in capital preservation mode, not growth mode."),
]
```

Example for aggressive_trader:
```python
cost_function = [
    ("missed_upside", "significant",
     "Your principal is 28. Sitting in cash through a recovery is the single biggest mistake at their age."),
    ("locked_in_loss", "moderate",
     "Don't sell at the bottom but don't be paralyzed."),
    ("withdrawal_fees", "minor",
     "A few percent of friction is acceptable if you have conviction."),
    ("principal_loss", "moderate",
     "Catastrophic loss matters but they have decades of compounding and human capital."),
]
```

The renderer composes these into a "Costs you take seriously" section of the system prompt, ordered from most to least severe. The LLM is then asked to weigh the relevant costs explicitly in its reasoning.

## The OutcomeLedger abstraction

Per-agent outcome tracking is its own component because the bookkeeping is non-trivial.

An `OutcomeLedger` for a single agent in a single simulation tracks:

- `principal_starting_value`: total wealth at simulation start.
- `principal_current_value`: updated continuously as actions are taken and prices settle.
- `realized_costs`: list of `(timestamp, cost_category, amount, decision_event_id)` tuples. Populated when an action is taken with a deterministic cost (e.g., paying a 3% early withdrawal fee).
- `unrealized_outcomes`: list of `(timestamp, decision_event_id, "would_have_lost"|"would_have_gained", amount)`. Populated at end of simulation when the rumor's truth is revealed and missed-upside or avoided-loss is computed retrospectively.
- `outcome_tags`: a set of qualitative tags assigned at simulation end: {avoided_crisis, panicked_unnecessarily, ignored_real_warning, acted_appropriately, partial_response}.

The ledger is computed deterministically from the action history and the scenario's revealed truth at simulation end. No LLM calls involved — this is pure bookkeeping. The numbers go straight to the dashboard's per-agent inspect view (running principal value plot, decision-by-decision cost annotations) and to the variance-summary panel that renders aggregate outcomes (mean principal change by persona by scenario type) for the demo.

Important: outcome tracking is *separate from* the cost_function in the prompt. The cost function shapes the agent's reasoning before the action; the ledger records what happened after. Agents do not see their own ledger or any other agent's ledger during the simulation. The ledger is for analysis and presentation, not for feeding back into agent behavior. This is the principle 6 guardrail — costs are reasoned about, never used to update model behavior.

## The decision flow

When an agent's decision is triggered, the flow is:

1. **Build context:** persona, current portfolio, recent observations (rumors, peer actions), prior decisions.
2. **Select model:** Haiku for routine decisions, Sonnet for high-stakes moments (defined as: first decision in a scenario, decision under conflicting information, decision when portfolio change exceeds threshold).
3. **Render prompt:** persona system prompt + structured user message describing the situation and asking for a decision.
4. **Call LLM with tool use** for structured output. The tool schema enforces: `action` (one of {hold, partial_withdraw, full_withdraw, increase_deposit}), `amount` (if applicable), `reasoning` (string), `confidence` (0-1).
5. **Validate response.** If malformed, retry with explicit error feedback.
6. **Cache:** key the response by hash of (persona, portfolio_state, observation_set). Identical inputs return cached responses for replay determinism.
7. **Log:** full audit record to `runs/<run_id>/decisions/<agent_id>/<timestamp>.json`.
8. **Emit `AgentActed` event** with the action and reasoning.

## The information environment

Information flows through `Feed` objects. Each agent subscribes to one or more feeds with optional latency.

Feeds in v1:
- `news_feed`: rumors and announcements.
- `social_feed`: actions of other agents (when configured to be visible).
- `direct_observation`: things the agent always sees (their own portfolio, their bank's stated reserve ratio).

When an event is published to a feed, each subscribed agent receives an `AgentObserved` event scheduled at `current_time + latency`. Latency is per-agent and can model: "this agent checks news every 30 seconds" vs. "this agent has alerts that fire instantly."

For v2, scenario translation will produce additional feeds (regulatory_feed, market_data_feed, etc.) — the architecture supports this without changes.

## The bank abstraction

A `Bank` has:
- `id`, `name`.
- `deposits`: dict from agent_id to amount.
- `reserves`: amount of liquid reserves.
- `reserve_ratio_target`: the ratio the bank tries to maintain.
- `withdrawal_processing_capacity`: how many withdrawals per unit time.
- `state`: enum {healthy, distressed, suspended}.

When withdrawals exceed reserves, the bank transitions to distressed. When the queue exceeds processing capacity, withdrawals are delayed (potentially triggering more panic). When reserves hit zero, the bank suspends withdrawals — this is what a real bank run looks like.

## Cost optimization patterns

- **Cache identical decisions.** A persona + portfolio state + observation set tuple should produce the same decision. Cache aggressively.
- **Batch parallel decisions.** When 5 agents simultaneously trigger decisions, fire all 5 LLM calls via `asyncio.gather` rather than sequentially.
- **Use Haiku for everything possible.** Haiku is ~10x cheaper than Sonnet and for "should I withdraw given my persona and this rumor" decisions, it's plenty capable.
- **Use Sonnet for strategic moments.** First-decision-in-scenario, conflicting-information, large-portfolio-change moments. ~10 Sonnet calls per simulation total.
- **Trim prompts.** Persona prompts can balloon. Aim for under 500 tokens per system prompt.

## Replay determinism

Simulation runs are not deterministic because LLM calls aren't. But for debugging and analysis, we want to be able to *replay* a saved run and see the same events.

The replay mechanism: each LLM call's response is cached by the hash of its inputs. When replaying a saved run, the cache is pre-populated with the original responses. Re-running the simulation produces identical events.

This means: every agent decision can be inspected, every cascade can be re-watched, and the dashboard's "live view" can be a controlled playback of a previously-completed run rather than a true real-time simulation. For demos this is actually preferable — no risk of API failures during the presentation.

## v2 hooks (do not build, but preserve)

The architecture must support these v2 additions without rewrite:

1. **Scenario translator.** A function `translate_scenario(natural_language: str) -> Scenario` that uses an LLM to produce a Scenario config object. The Scenario object is already the only input to the simulation engine in v1, so adding this is purely additive.

2. **Additional event types.** Adding `MarketPriceMoved`, `RegulatoryAnnouncement`, `PaymentSystemOutage` events should require: (a) defining the event dataclass, (b) writing a handler, (c) adding a feed subscription. No engine changes.

3. **Larger agent populations.** Scaling from 12 to 50 agents should be a config change. Bottlenecks: LLM cost (linear) and async fan-out (manageable). Test with 20 agents in v1 to confirm the architecture scales.

4. **Multi-bank scenarios.** The Bank abstraction is generic. Adding a third or fourth bank is config.

5. **Cross-scenario learning (NOT v2; v3 idea).** Agents learning from past simulation runs would require persistent state across runs. Deliberately excluded from v1 and v2 design — agents are stateless across runs. If we want this later, we introduce a persistent persona memory abstraction at that point.

## What is NOT in this architecture

- No reinforcement learning. Agents do not optimize objectives across simulation runs.
- No adversarial agents. Agents do not try to manipulate each other (in v1).
- No economic equilibrium computation. We do not solve for prices, market clearing, or any kind of fixed point.
- No external data integration. Banks are configured, not modeled on real banks.
- No regulatory compliance modeling. Banks just have reserves; they don't have capital requirements, deposit insurance modeling, or stress test simulation.

These are all interesting and could be added later. They are not v1.
