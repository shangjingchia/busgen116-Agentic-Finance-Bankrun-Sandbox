# CLAUDE.md — Agentic Bank Run Sandbox: Operating Context

This file is loaded by Claude Code at the start of every session. Read it before starting any task. If a request seems to conflict with anything here, raise it before proceeding.

## Project goal

Build a sandbox where heterogeneous LLM-powered agents — each with their own financial situation, persona, and access to information — manage money on behalf of simulated retail users. Use the sandbox to study how a population of AI delegates behaves during a bank run: who withdraws first, how rumors propagate through their information environment, how reaction speed differs from human-speed runs, and what cascades emerge from machine-coordinated decision-making.

The forward-looking framing is that within 5 years, retail financial management will increasingly be delegated to AI agents acting on consumers' behalf. This sandbox is a first probe into how such systems might behave under stress. It is not a prediction model for real bank runs; it is a controlled environment for studying patterns that emerge specifically when AI agents make financial decisions at machine speed.

## The deliverable: a live presentation, not a paper

The only output of this project is a ~8-minute live presentation in front of class judges (a competition format). There is no paper, no formal writeup, no journal submission. The artifacts that matter are: (1) the running dashboard demonstrated live, (2) optionally 2-4 supporting slides bookending the demo, (3) the speaker's narrative and Q&A handling. Everything we build serves these three things.

Implications for what we work on:
- The dashboard polish, visual clarity, and click-through smoothness matter more than they would for a paper-only project.
- Variance characterization across scenarios still matters, but it lives in dashboard panels we can point at, not in tables in a writeup.
- Empirical anchoring to the bank run literature (SVB, Iyer-Puri, Goldstein-Pauzner) is condensed to a single comparison number or chart that lives in the dashboard or on a closing slide. Not a literature review.
- The headline AI-vs-human delta is *the* number the audience walks away remembering. It must be computed, prominently displayed, and rehearsed into the speaker's narrative.
- Reproducibility, README completeness, and code documentation are nice-to-haves but not deliverables. Skip if time-constrained.

## v1 scope: one experiment, done well

Bank run dynamics under AI agent delegation.

Scenario: a population of agents holds deposits at two banks. A rumor about insolvency at Bank A enters the information environment. Agents observe: (a) the rumor itself, with configurable credibility; (b) the actions of other agents (whose withdrawals are visible through a public ledger or social signal); (c) their own portfolio state. They decide whether to withdraw, partially withdraw, or hold.

We measure: time-to-decision per agent, the fraction of deposits withdrawn over time, the order in which agents act, the correlation of actions across agents with similar personas, and the size and speed of any cascade. We compare AI-speed runs (agents decide in seconds) to artificially slowed runs (decision latency injected) to characterize the speed difference.

The deliverable is an interactive Streamlit dashboard where the presenter can configure a scenario, watch the run unfold visually with real LLM calls happening behind the scenes, and inspect each agent's reasoning.

## v2 vision: scenario-driven sandbox (not for v1, but design for it)

The long-term vision is a textbox where a user types a stress scenario in natural language ("a stablecoin de-pegs by 5% over an hour, news breaks at 9pm Friday"), and the sandbox calibrates the relevant variables, agents, and information environment automatically and shows how the scenario plays out.

This is explicitly out of scope for v1. But the v1 architecture should make this path clean: scenarios are configuration objects, agent personas are data, the information environment is a structured stream. Once these things are true, an LLM-driven scenario translator becomes additive rather than a rewrite. Whenever Claude Code is making an architectural decision, prefer the design that keeps v2 reachable. The "extended version" section at the end of this file describes the v2 surface.

## Core methodological principles (do not violate)

**1. Agents make real LLM calls for decisions.** Not closed-form utility functions, not pre-computed lookup tables. Every consequential agent decision is a structured LLM call where the agent's persona, current state, observations, and goals are inputs and a structured action is the output. This is what makes the project genuinely about *AI agent behavior* rather than about a parameterized economic model.

**2. Decisions are event-driven, not tick-driven.** Agents do not "think" on every simulation tick. They think when an event triggers them: receiving income, observing a rumor, seeing another agent act, hitting a portfolio threshold. This makes LLM costs tractable and reflects how real delegate systems would work.

**3. Heterogeneity is genuine.** Each agent has a persona that includes demographics, financial sophistication, risk tolerance, goals, information access, and trust profile. Personas are not just different parameter values — they are different narratives the LLM reasons within. Two agents with identical portfolios should produce different decisions because their persona prompts are different.

**4. Findings are about the simulation, not about reality.** The validity claim is "given these agent specifications and this information environment, here is what happens." We are not predicting real bank run behavior. The interest is in characterizing patterns that emerge from AI delegation, not in calibrating to historical events. This must be honest in how we frame results during the live presentation and in any Q&A.

**5. The v2 path is preserved.** All scenario state lives in a `Scenario` config object. All agent state lives in `Agent` objects. The information environment is a structured event stream. If a design choice would close off the textbox-to-simulation path, raise it before committing.

**6. Agents reason with stakes.** Every persona has a `cost_function` rendered into the system prompt that describes, in qualitative terms, what their principal stands to lose or miss from different decisions. A cautious retiree facing a withdrawal decision is reasoning with "losing principal is catastrophic; early withdrawal fees are significant; missing upside is minor." An aggressive trader is reasoning with the inverse weighting. This makes agent decisions consequence-aware without introducing reinforcement learning, and produces noticeably richer reasoning in the inspect view. The cost function is qualitative (catastrophic / significant / moderate / minor), never quantitative thresholds — quantitative thresholds over-determine the outcome and defeat the purpose of using LLMs to weigh judgment calls. Outcomes are tracked in a per-agent ledger: fees paid, losses crystallized, upside missed, crises avoided. At the end of each simulation, every agent has a "principal outcome" — net change in principal wealth plus a qualitative tag (avoided crisis, panicked unnecessarily, ignored real warning, acted appropriately). This data renders in the inspect view as a running "principal value" plot per agent, and it powers any quantitative claim made during the live presentation.

**7. The headline empirical claim is the AI-vs-human delta, anchored to one comparison number.** The single most important finding from this project is *how much faster and larger AI-mediated bank runs are compared to human-mediated runs in the same scenario*. The AI-speed simulation is the natural one (no artificial latency); the human-speed simulation injects decision delays calibrated to observed human decision timescales from the empirical bank run literature. We measure: time-to-first-withdrawal, time-to-50%-withdrawn, final withdrawal fraction, cascade gini, and rumor-credibility threshold for cascade initiation. The headline claim takes the form "in our simulation, AI delegation reduced time-to-50% by a factor of X" — never "AI bank runs in reality will be X times faster," which would overclaim. For the live presentation, the empirical anchor is one comparison: "the SVB run in March 2023 was the fastest in modern history at $42 billion withdrawn in a single day; our simulation compresses comparable cascade dynamics to a fraction of that timescale." That single anchor — paired with the AI-vs-human comparison view in the dashboard — is sufficient grounding for a 60-90 second segment of the presentation. We do not need a literature review, a methodology section, or formal citations. We do need the headline number computed and rehearsed.

## What is explicitly out of scope for v1

If a task seems to require any of these, ask first.

- Bank runs at scale beyond ~12-20 agents.
- Macroeconomic feedback loops (inflation, GDP, monetary policy transmission).
- DeFi, stablecoins, cross-border flows, FX.
- The natural-language scenario generator (v2 feature).
- Validation against real-world bank run data — we are characterizing simulation behavior, not predicting reality.
- Quantitative reproduction of any specific historical event (SVB, Northern Rock, Continental Illinois, 2008 individual bank failures, etc.). We use empirical findings as qualitative anchors for the human-speed baseline, not as reproduction targets. Full event reproduction would require persona system rebuilds (e.g., SVB needed startup-CFO and VC personas rather than retail) and is outside v1 scope.
- Multiple banks beyond two.
- Yield-bearing assets beyond a single illiquid investment option (kept simple to focus on the run mechanic).
- Reinforcement learning, agent training, or any kind of learning across simulation runs. Agents are stateless across runs; their persona is their full configuration.
- Reward signals fed back to the model. The cost function lives in the prompt as context; it does not drive any kind of weight update, fine-tuning, or RLHF. We are *not* training agents to take stakes seriously — we are *prompting* them to reason with stakes in mind.
- Persona drift mid-simulation. A cautious retiree stays a cautious retiree. They do not become more aggressive after a streak of "wrong" cautious decisions. The cost function is static throughout a run.
- Inter-agent reputation systems. Agents do not track each other's track records or weight peer signals based on past accuracy. This is interesting and could be added later but is scope creep for v1.
- A web frontend more elaborate than Streamlit. If Streamlit blocks something we need, raise it.

## Tech stack

- **Language:** Python 3.11+
- **LLM API:** Anthropic Python SDK. Default to `claude-haiku-4-5-20251001` for routine agent decisions. Use `claude-sonnet-4-6` for strategic moments (initial portfolio assessment, run-or-stay decision under high stress) where reasoning quality matters more than cost. Both models accessed via the Messages API.
- **Simulation engine:** A custom event-driven loop, not SimPy. SimPy is overkill for ~12 agents and adds learning curve. Build a simple event queue with `heapq` and async event handlers.
- **State management:** Plain Python dataclasses for `Agent`, `Bank`, `Event`, `Scenario`. JSON serializable for inspection and replay.
- **Visualization:** Streamlit + Plotly for charts, NetworkX + Plotly for the agent-bank graph if we add it. Avoid heavy frontend stacks.
- **Storage:** JSON files for simulation runs. SQLite if we need to query across runs. No databases for v1.
- **Async:** `asyncio` for parallel LLM calls when multiple agents trigger decisions simultaneously. This matters because LLM call latency is the binding constraint on simulation wall-clock time.

Default to simple. If a fancier tool is genuinely needed, ask before installing.

## Cost discipline

LLM calls dominate cost. Keep them tractable:

- 12 agents × ~50 decision events per simulation × $0.001 average per Haiku call = ~$0.60 per run.
- ~10 strategic-moment Sonnet calls per run × $0.015 = ~$0.15 per run.
- Total: under $1 per simulation run. Budget for hundreds of runs.
- Cache aggressively: identical (persona, state, observation) tuples produce identical decisions, so cache and reuse.
- Log every LLM call with model, tokens, cost. Print cost summary at end of each run.

If a single run starts costing more than $5, stop and audit before continuing.

## File structure

```
agent-bankrun/
├── CLAUDE.md                  (this file)
├── PLAN.md                    (build sequence and decision rules)
├── README.md                  (project overview)
├── architecture.md            (technical design notes)
├── pyproject.toml             (dependencies)
├── .env.example               (API keys template)
├── src/
│   ├── core/
│   │   ├── agent.py           (Agent dataclass + decision interface)
│   │   ├── bank.py            (Bank with deposit ledger and reserves)
│   │   ├── event.py           (Event types, event queue)
│   │   ├── scenario.py        (Scenario config object — v2-ready)
│   │   └── simulation.py      (event loop, orchestration)
│   ├── personas/
│   │   ├── archetypes.py      (4 archetype definitions)
│   │   ├── instances.py       (12 specific agent instances built from archetypes)
│   │   └── prompts.py         (persona-to-prompt rendering)
│   ├── decisions/
│   │   ├── llm_client.py      (Anthropic SDK wrapper, retry, caching)
│   │   ├── decision.py        (structured input → structured output)
│   │   └── strategies.py      (cheap-model vs strategic-model routing)
│   ├── information/
│   │   ├── feed.py            (information environment)
│   │   ├── rumor.py           (rumor injection mechanism)
│   │   └── observation.py     (what each agent sees)
│   ├── analysis/
│   │   ├── metrics.py         (time-to-decision, cascade size, correlation)
│   │   └── replay.py          (load saved run, step through events)
│   └── dashboard/
│       ├── app.py             (Streamlit entry point)
│       ├── live_view.py       (network graph + agent state during run)
│       ├── scenario_panel.py  (configure scenario, trigger events)
│       └── reasoning_view.py  (per-agent decision inspector)
├── scenarios/                 (saved scenario JSON files)
├── runs/                      (saved simulation runs as JSON)
└── tests/
```

## Conventions

- **Build vertical slices.** Get one agent making one LLM-driven decision in response to one event before scaling to 12 agents and a full run.
- **Every LLM call is structured.** Use Anthropic's tool-use feature or strict JSON mode. Free-form text only when explicitly displaying reasoning.
- **Every agent decision is logged with full context.** Persona snapshot, observation set, prompt, response, action taken, timestamp. This is the audit trail and the data for the dashboard.
- **Determinism where possible.** Set seeds for any randomness in the scenario (rumor timing, persona assignment). LLM calls are inherently non-deterministic; accept this and run experiments multiple times to characterize variance.
- **Async LLM calls.** When multiple agents need to decide simultaneously, fan out via `asyncio.gather`. This is the difference between a 30-second simulation and a 5-minute one.

## The headline interaction

The Streamlit dashboard has three main views:

**Configure view:** the presenter chooses a scenario (preset bank run scenarios with different parameters: rumor credibility, propagation speed, agent population mix, bank reserve ratio). They press "Run."

**Live view:** as the simulation runs, a left panel shows a force-directed graph of agents and their bank holdings. Edges glow when withdrawals happen. A right panel shows a scrolling timeline of events: "Agent 3 (cautious retiree) observed rumor → withdrew 80% from Bank A." A top bar shows aggregate metrics: Bank A reserve ratio, fraction of agents who have run, average time-to-decision.

**Inspect view:** click any agent. See their persona, their current portfolio, every decision they've made, and the LLM reasoning behind each decision. This is the wild factor — the audience can literally read what the AI was thinking when it decided to run on the bank.

## Tone for agent reasoning output

Each agent's persona dictates voice. A "cautious retiree" reasons in different language than an "aggressive young trader." This isn't decoration — it's evidence the personas are doing real work. Judges should be able to skim several agents' reasoning logs during the inspect-view portion of the demo and tell which persona produced which without seeing labels.

## When in doubt

- Ask before expanding scope to v2 features.
- Ask before introducing new dependencies.
- Ask before changing the core methodological principles above.
- Default to the simplest implementation that works.
- If something is taking longer than expected, surface it rather than going deep alone.

## Validation expectations

Before any simulation run is considered "complete":
- All agent decisions have full audit logs (persona, observation, prompt, response).
- The simulation completes without unhandled exceptions.
- Cost summary is logged.
- Run metadata (scenario config, seed, timestamp, total LLM calls) is saved alongside the run.
- A replay of the run produces identical events given the same LLM responses (replay determinism, not simulation determinism).

---

## v2 surface (extended vision — design for this, do not build it)

The long-term goal is a sandbox that supports any stress scenario expressible in natural language. The v1 bank run experiment is a template for what v2 generalizes.

**The textbox interaction:** a user types something like "a major bank announces it cannot meet a regulatory capital requirement, news breaks at 4pm on a Friday before a long weekend." The system:

1. **Translates the scenario** via an LLM call into a structured `Scenario` object: which event types occur, when, what information enters the environment, what initial conditions hold.
2. **Calibrates agent personas** by adjusting the population mix to fit the scenario context (more institutional agents for an institutional crisis; more retail agents for a consumer panic).
3. **Renders the resulting parameters in the dashboard** so the user can review and edit before pressing run.
4. **Runs the simulation** using the same engine that runs v1 bank runs.
5. **Generates an analysis report** at the end summarizing what happened.

**Additional scenario types to support in v2:**
- Liquidity crises beyond bank runs (money market freezes, payment system outages).
- New product launches (a new payment rail, a new yield-bearing instrument) and how AI agents adopt or avoid them.
- Information warfare (coordinated false information injected into the agent feed).
- Regulatory shocks (new compliance constraints introduced mid-simulation).
- Cross-bank contagion (multiple banks in distress).

**What the v1 architecture must preserve to make v2 cheap:**
- Scenario is a config object, not hardcoded logic.
- Agent population is generated from a persona pool with adjustable mix.
- Information environment is a generic event stream — any event type can be added.
- Bank logic is generic — adding more banks or more product types is configuration, not code.
- Decision prompts are templated by persona and event type — adding new event types means adding new templates, not new code paths.

If v1 is built well, v2 is roughly: add a scenario translator (one LLM call), add 3-5 new event types, add the textbox to the dashboard. Maybe two weeks of work after v1 is solid.
