# Agentic Bank Run Sandbox

A controlled simulation environment for studying how a population of LLM-powered AI agents — each acting as a financial delegate for a simulated retail user — behaves under stress.

## What this is

A growing share of consumer financial decisions will likely be delegated to AI agents within the next five years. These agents will read news, observe portfolios, and act on their principal's behalf at machine speed. This raises questions that are hard to study with current tools: how do AI delegates behave when a rumor spreads through their information environment? How fast does a bank run cascade when withdrawal decisions don't have to wait for humans to wake up, read the news, and decide to act?

This project is a sandbox for asking those questions concretely. We instantiate a small population of heterogeneous AI agents, each with a distinct persona (cautious retiree, aggressive young trader, gig worker, institutional treasurer), each with their own portfolio across two banks. We inject controlled events — most notably rumors of bank insolvency — and observe what happens. Every agent decision is a real LLM call. Every reasoning trail is auditable.

The v1 deliverable is a focused study of bank run dynamics. The vision is a general-purpose stress-testing sandbox where any scenario can be described in natural language and simulated.

## Why this is interesting

Two reasons.

**The substantive question.** The Silicon Valley Bank failure in March 2023 was reportedly accelerated by Twitter — a partial preview of what happens when information cascades faster than institutional response. AI delegation accelerates this further: if an agent observes a rumor and acts in milliseconds, and other agents observe its action and act in milliseconds, the cascade dynamics change qualitatively. Are bank runs faster? Larger? Triggered by smaller signals? These are testable questions in a controlled environment.

**The methodological angle.** Most agent-based macroeconomic simulations use closed-form utility functions and are vulnerable to the "garbage in, garbage out" critique — you can produce any qualitative result by tuning parameters. We sidestep this by making every agent decision a genuine LLM call with persona-driven heterogeneity. The validity claim is not "this predicts real bank runs" but "this characterizes how a population of LLM delegates behaves in a controlled environment." The interesting findings live at the system level: cascade speed, correlation across personas, sensitivity to information environment design.

## How it works

Twelve agents, four personas, two banks. An event-driven simulation engine processes a configurable scenario. Agents make decisions through LLM calls — Claude Haiku for routine decisions, Claude Sonnet for high-stakes moments. Each decision produces a structured action plus reasoning, all logged with full audit trails.

Each persona has a `cost_function`: a structured description of what the agent's principal stands to lose or miss from different decisions, framed in qualitative terms (catastrophic, significant, moderate, minor). A cautious retiree reasons knowing that principal loss is catastrophic but missed upside is minor; an aggressive trader has the inverse weighting; a gig worker treats short-term cash flow disruption as catastrophic. This makes agents reason with stakes, not just opine. Outcomes are tracked in a per-agent ledger — fees paid, losses crystallized, upside missed, crises avoided — which renders in the dashboard and grounds the demo's quantitative claims.

The empirical headline is the AI-vs-human delta. Every preset scenario runs at both AI speed (no decision latency, the natural mode of the system) and human speed (decision delays calibrated to observed human decision timescales from the bank run literature). We measure how much faster, larger, and more easily triggered AI-mediated runs are than human-mediated runs in the same scenario. The human-speed baseline is anchored to established empirical findings (Iyer-Puri 2012 on network effects in Indian bank runs; post-SVB analyses for institutional run dynamics; Goldstein-Pauzner theoretical foundations) — not to reproduce any specific historical event but to ensure the human-speed simulation produces patterns consistent with what's been observed. The delta between the AI-speed and human-speed runs is the headline finding.

The Streamlit dashboard has three views:

- **Configure:** pick a scenario preset, adjust parameters (rumor credibility, persona mix, bank reserves, social signal visibility), press run.
- **Live:** watch the simulation unfold as a force-directed agent-bank graph with a scrolling event timeline and aggregate metrics.
- **Inspect:** click any agent, see their persona, portfolio, full decision history, and the LLM's reasoning behind each decision.

The presentation flow is: configure a bank run → watch it happen → pause → click an interesting agent → read what the AI was thinking when it decided to start running on the bank.

## Stack

Python 3.11+, Anthropic Python SDK (Claude Haiku for most calls, Claude Sonnet for strategic moments), `asyncio` for parallel LLM calls, custom event-driven loop with `heapq`, Streamlit + Plotly for the dashboard, NetworkX for the agent-bank graph.

## Status

Project in active development for a course final, four-week build culminating in a live competition-format presentation in front of class judges. The only deliverable is the live ~8-minute demo and Q&A. There is no formal writeup. See `PLAN.md` for the build sequence and `architecture.md` for technical design.

## What this project does *not* claim

- It does not predict real bank run behavior. The agents are LLM personas, not models of real depositors.
- It does not produce calibrated forecasts of future financial system dynamics. It produces controlled experiments.
- It does not reproduce specific historical events (SVB, Northern Rock, 2008 individual failures). The empirical literature is used as qualitative anchoring for the human-speed baseline, not as a reproduction target.
- The headline AI-vs-human delta is a property of *our simulation* — it characterizes what changes when the same scenario runs with and without artificial decision latency. It is not a prediction of how AI bank runs will play out in real markets.

## Scope

V1 is one experiment, deeply instrumented: bank run dynamics under AI delegation. V2, deferred but designed for, is a textbox-driven scenario generator that translates any natural-language stress scenario into a simulation. See the v2 surface section in `CLAUDE.md`.

## License

MIT.
