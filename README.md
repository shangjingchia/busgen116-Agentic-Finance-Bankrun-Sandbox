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

Twelve agents, four personas, two banks. An event-driven simulation engine processes a configurable scenario. Agents make decisions through real LLM calls, accessed via OpenRouter's OpenAI-compatible API so the underlying model is swappable — a cheaper model for routine decisions, a stronger one for high-stakes moments. Each decision produces a structured action plus reasoning, all logged with full audit trails.

Each persona has a `cost_function`: a structured description of what the agent's principal stands to lose or miss from different decisions, framed in qualitative terms (catastrophic, significant, moderate, minor). A cautious retiree reasons knowing that principal loss is catastrophic but missed upside is minor; an aggressive trader has the inverse weighting; a gig worker treats short-term cash flow disruption as catastrophic. This makes agents reason with stakes, not just opine. Outcomes are tracked in a per-agent ledger — fees paid, losses crystallized, upside missed, crises avoided — which renders in the dashboard and grounds the demo's quantitative claims.

The headline finding is about **model identity**. Holding everything else fixed — the same twelve personas, the same rumor about the same *healthy* bank, the same information feed — and changing only *which* underlying model makes the decisions swings the outcome dramatically: under one model about half the depositors run on a bank that is fine, under another every one of them does. A population of delegates that all run on the same model behaves like a monoculture that panics — or holds — in lockstep, which makes the model itself a systemic risk factor.

A second finding is the AI-vs-human speed delta. Every preset runs at both AI speed (no decision latency, the natural mode of the system) and human speed (a calibrated deliberation delay standing in for the time a person needs to notice and decide). AI delegation reaches the halfway point of a run roughly 3× faster; because payouts are rate-limited, the faster request wave also freezes the bank sooner and locks more depositors out. The human-speed baseline is anchored qualitatively to the bank run literature (Iyer-Puri 2012 on network effects; post-SVB analyses; Goldstein-Pauzner foundations) — not to reproduce any specific event, but to keep the human-speed patterns plausible.

The Streamlit dashboard has four pages:

- **Presets:** load a saved run, or configure and launch a new scenario (rumor credibility, persona mix, bank reserves, social-signal visibility, regulator, counter-signal).
- **Inspect:** click any agent to see their persona, portfolio, full decision history, and the verbatim LLM reasoning behind each decision.
- **Findings:** the patterns that held up across runs — model monoculture, speed, and language sensitivity — each with a headline number and an honest caveat.
- **Sandbox:** build a scenario from scratch — describe agents in plain English, set bank health and population mix, write the rumor, add a regulator or counter-signal, then run and save it.

The presentation flow is: load a bank run → click an agent and read what the AI was thinking when it decided to run on the bank → walk the findings.

## Quickstart

Requires Python 3.11+.

```bash
# 1. Install (editable, into a virtualenv)
python -m venv .venv
# Windows:        .\.venv\Scripts\Activate.ps1
# macOS / Linux:  source .venv/bin/activate
pip install -e .

# 2. Launch the dashboard
streamlit run src/dashboard/app.py
```

A browser opens at `http://localhost:8501`. **No API key is needed to explore** — go to **Presets → Load saved run** and the dashboard reads the pre-computed simulations in `runs/`, including every reasoning trail.

To launch *new* live simulations (Sandbox page, or new preset runs), copy `.env.example` to `.env` and add an `OPENROUTER_API_KEY`. Routine agent decisions default to a cheap model and a full run costs roughly $1; see `CLAUDE.md` for the cost model. Run the test suite with `pytest`. Demo-running details are in `DEMO_DAY_RUNBOOK.md`.

## Stack

Python 3.11+, LLM access via OpenRouter (OpenAI-compatible API) so the underlying model is swappable across providers — which is what powers the model-comparison finding; `asyncio` for parallel LLM calls, a custom event-driven loop with `heapq`, and Streamlit + Plotly for the dashboard.

## Status

Built for a course final, culminating in a live competition-format presentation in front of class judges. The deliverable is a live 5–7 minute demo and Q&A; there is no formal writeup.

**Presentation materials** (in this repo): `SLIDES.pptx` (the deck, with speaker notes and a Q&A appendix), `PRESENTATION_SCRIPT_TIGHT.md` (the delivery script), `PRESENTATION_SCRIPT.md` (full script with Q&A prep and backup-slide map), and `DEMO_DAY_RUNBOOK.md` (how to run the demo). See `PLAN.md` for the build sequence and `architecture.md` for technical design.

## What this project does *not* claim

- It does not predict real bank run behavior. The agents are LLM personas, not models of real depositors.
- It does not produce calibrated forecasts of future financial system dynamics. It produces controlled experiments.
- It does not reproduce specific historical events (SVB, Northern Rock, 2008 individual failures). The empirical literature is used as qualitative anchoring for the human-speed baseline, not as a reproduction target.
- The headline findings — the effect of model identity and the AI-vs-human speed delta — are properties of *our simulation*. They characterize what changes when you vary the model or the decision latency in this controlled setup. They are not predictions of how AI bank runs will play out in real markets.

## Scope

V1 is one experiment, deeply instrumented: bank run dynamics under AI delegation. V2, deferred but designed for, is a textbox-driven scenario generator that translates any natural-language stress scenario into a simulation. See the v2 surface section in `CLAUDE.md`.

## License

MIT.
