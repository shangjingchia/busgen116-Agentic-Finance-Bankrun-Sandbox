# PLAN.md — Build Sequence and Decision Rules (4-week version)

This file complements CLAUDE.md. CLAUDE.md says *what* we're building; PLAN.md says *in what order* and *when to stop adding scope*.

## Timeline

You have ~4 weeks until presentation, with significant focused time available. The build is tight but the scope is right-sized for the timeline. Two non-negotiable disciplines:

1. **Build vertical slices.** One agent making one LLM-driven decision in response to one event, with full audit log, by end of day 3. Twelve agents and a full bank run scenario by end of week 1. The dashboard starts in week 2, not week 3.
2. **Resist scope expansion.** Every "wouldn't it be cool if" is recorded in `FUTURE_WORK.md` and not built. The compressed timeline gives you no slack for new features once the build starts.

## Week-by-week build sequence

### Week 1: Engine + agents + first cascade

**Goal: end the week with 12 agents in a working bank run scenario, decisions logged, cascade visibly emerging in the JSON output even without a dashboard yet.**

**Days 1–2: foundation**
- Project structure, dependencies (anthropic, streamlit, plotly, networkx, pydantic, asyncio is stdlib).
- `Agent`, `Bank`, `Event`, `Scenario`, `Persona`, `OutcomeLedger` dataclasses per `architecture.md`.
- `LLMClient` wrapper with retry, structured tool-use output, response caching keyed on input hash.
- One persona ("cautious retiree") fully written: archetype, demographics, prose framing, voice examples, `cost_function` with all relevant categories.
- One full vertical slice: rumor event → agent observation → LLM decision (with cost function in prompt) → structured response → log to JSON.

**Day 3: four personas, prompt rendering**
- Write the other three archetypes: aggressive trader, gig worker, institutional treasurer. Each gets a complete `cost_function` — this is the most important writing work in the project. Spend real time on these. Specific narratives, plausible numbers, qualitative severities.
- Build the persona-to-prompt renderer. Output should read like a coherent character brief, not a parameter dump.
- Manually inspect prompts for all four personas. They should sound like four different people.

**Day 4: event loop and information environment**
- Event queue with `heapq`. Async event handlers via `asyncio`.
- `Feed` abstraction: news_feed, social_feed, direct_observation. Per-agent subscription with optional latency.
- Bank state: deposit ledger, reserves, withdrawal processing capacity.
- 12 agent instances (3 per archetype) with varied portfolios across two banks.

**Day 5: first full scenario run**
- Scenario: rumor about Bank A insolvency at t=0, all 12 agents observe with persona-appropriate latency, each decides independently.
- Run async — all 12 LLM calls fan out via `asyncio.gather` so the whole simulation completes in under a minute.
- Inspect the JSON output: do the four personas produce visibly different decisions? Are the decisions actually responsive to the rumor and the cost function?

**Days 6–7: social signal and cascade**
- Add `SocialSignalEmitted` event: when an agent withdraws, publish their action to the social_feed (visibility configurable).
- Implement re-decision: an agent who decided "hold" can re-decide if they observe a critical mass of others withdrawing. Threshold is part of persona (institutional treasurers have higher thresholds than gig workers).
- Implement the `OutcomeLedger`: every action records realized costs (fees, locked-in losses) deterministically.
- At simulation end, with a `RumorTruth` flag (was the rumor true or false), populate unrealized outcomes (missed upside, avoided loss) and assign outcome tags.
- Run the same scenario at "AI speed" (no artificial latency) and "human speed" (90-second decision delay injected). Compare cascade dynamics in the output JSON.

**End-of-week-1 definition of done:** running `python -m src.core.simulation --scenario rumor_moderate --speed ai` produces a complete JSON with 12 agents, ~30-60 events, full audit trails, and a populated outcome ledger. The same scenario at human speed produces a visibly smaller cascade. Total cost under $5.

### Week 2: Dashboard scaffolding + live view

**Goal: a working Streamlit dashboard where you can configure a scenario, run it, and watch it unfold live with the inspect view available.**

**Days 8–9: Streamlit scaffolding + configure page**
- Three Streamlit pages: configure, live view, inspect.
- Configure page: dropdown of preset scenarios, sliders for rumor credibility, persona mix, bank reserve ratio, social signal visibility. "Run" button triggers the simulation.
- Persist scenario configs in `scenarios/` and run results in `runs/` as JSON.
- Decision: pre-run the simulation when the user clicks "Run", then "play back" the events on the live view at controlled speed. This is more reliable than truly real-time updates and lets you pause/rewind during the demo.

**Days 10–11: live view (the core visual)**
- NetworkX + Plotly force-directed graph: nodes are agents and banks, edges show deposit relationships, edges animate or change color when withdrawals happen.
- Scrolling event timeline panel: each event renders as a card with persona icon, action verb, brief reasoning excerpt.
- Top-bar metrics: agents-who-have-run fraction, Bank A reserve ratio, average time-to-decision, current simulation timestamp.
- Playback controls: play, pause, step forward, step backward, speed slider.
- Pre-rendered playback means the dashboard never has to wait on LLM calls during the demo. The simulation already happened; you're scrubbing through it.

**Days 12–13: inspect view (the reasoning reveal)**
- List of all agents with persona icons. Click any agent.
- Detail view shows: persona description (including cost function), running principal-value plot, full decision timeline, outcome ledger.
- Each decision expandable: show the prompt sent to the LLM, the structured response, the action taken, the realized cost from the ledger.
- This is the demo centerpiece. The audience clicks an agent that just panic-withdrew and sees: their cost function (loss is catastrophic, fees are significant), their reasoning ("the rumor seems credible and I cannot afford to be wrong about my principal's retirement savings"), and their outcome (paid 3% in fees, will be revealed at end of run whether the rumor was true or false).

**Day 14: AI-speed vs. human-speed comparison view + literature anchor reading**
- Side-by-side rendering of two saved runs: same scenario, different speed setting.
- Synchronized playback so you can see the two cascades unfold simultaneously.
- Aggregate metric overlay: cascade size, time-to-50%, total principal-value destroyed across the two runs.
- This is the "wild factor part 2" — the audience watches the AI-speed run finish before the human-speed run is half-done.
- **Reading work (~1-2 hours, can be done in parallel):** since there's no formal writeup, the literature reading shrinks to grabbing a few key numbers for the dashboard's benchmark panel and for the speaker's verbal anchors during the demo. Priorities: (1) the SVB headline numbers — $42 billion withdrawn in one day on March 9, 2023, fastest in modern history, "first Twitter-fueled bank run"; (2) Iyer-Puri (2012) participation-rate context — bank runs typically involve only 3-7% of depositors but that's enough to threaten a bank, with uninsured running at 30+ percentage points higher than insured; (3) the historical timescale — pre-digital runs took 2-10 days, SVB compressed to ~24 hours, our AI-speed simulation will compress further. Three or four numbers. That's it. No literature review needed.

**End-of-week-2 definition of done:** you could open the dashboard, configure a scenario, click run, watch the live view, click into an interesting agent, and read their reasoning. The AI-vs-human comparison view works. A non-developer could drive it. You have 3-4 empirical anchor numbers from the bank run literature ready to use in week 3 — primarily the SVB stats and the Iyer-Puri participation context.

### Week 3: Scenario library + variance characterization + benchmark anchoring + demo construction

**Goal: enough preset scenarios and run data to support real findings, the headline AI-vs-human delta computed and rendered, and the demo flow constructed end-to-end.**

**Days 15–16: scenario presets**
- Build 4-5 distinct preset scenarios:
  - `rumor_credible_true`: high-credibility rumor, bank actually insolvent.
  - `rumor_credible_false`: high-credibility rumor, bank actually fine.
  - `rumor_weak_true`: weak rumor, bank actually insolvent.
  - `rumor_weak_false`: weak rumor, bank actually fine.
  - `slow_burn`: rumor strengthens over time.
- For each preset, run 8-10 simulations *at AI speed* and 8-10 *at human speed*. This is your empirical data. The doubling matters — every preset must have both speed conditions for the headline delta finding to work.
- Output: aggregate findings tables. "In `rumor_weak_false` runs at AI speed, time-to-50% was median 8 seconds; at human speed, median 47 minutes. Delta: ~350x acceleration." That's a finding.

**Day 17: benchmark panel + headline delta**
- Add a "literature benchmark" view to the dashboard showing your simulation's metrics next to the empirical anchor numbers from week 2's reading. Use clear labeling: "anchor we tried to match" (typical historical run durations, network effect magnitudes — these are the human-speed baseline calibration targets) vs. "novel finding" (the AI-speed acceleration, which has no historical analog because AI delegation hasn't happened at scale yet).
- Compute the headline delta: across all scenarios, what is the median ratio of (human-speed time-to-50%) / (AI-speed time-to-50%)? What is the cascade-size ratio? What scenarios showed the largest delta?
- These numbers become the demo's punchline. Render the headline number prominently somewhere visible — a stat card on the dashboard, a closing slide, or both.

**Day 18: comparison view + variance dashboard**
- Comparison view in dashboard: pick any two saved runs, see metrics side by side.
- "Variance summary" view: for each preset scenario, show the distribution of outcomes across the multiple runs. Bar charts of mean principal change per persona, distribution of cascade sizes, AI-vs-human delta with confidence intervals.
- This data is what you'll point to during the variance segment of the demo: "across 80 simulation runs, here's what we found — and here's how stable it is."

**Days 19–21: demo construction**

The deliverable is a live ~8-minute presentation with judges. These three days build the presentation itself — slides, speaker notes, demo flow, contingencies.

- **Day 19: write the demo script.** Write down what you'll say, sentence by sentence, for each phase of the demo: opening hook (1 min), motivation (30 sec), live configure (30 sec), live AI-speed run with narration (90 sec), pause and inspect a specific agent reading reasoning aloud (90 sec), AI-vs-human comparison and the headline delta number (90 sec), brief variance/benchmark mention (45 sec), close with v2 vision and stakes (45 sec). Roughly 8 minutes. Pick the *specific* agent and the *specific* moment to pause on — don't leave this to live discovery.
- **Day 20: build supporting slides (2-4 only).** Title + framing slide ("AI agents will manage money in 5 years; what happens when one panics?"). One closing slide with the headline delta number rendered large and a call to forward. Optionally one anchor slide pre-demo with the SVB stat ($42B in one day, fastest in modern history). Optionally one Q&A backup slide listing limitations honestly. Visual style consistent with the dashboard. No walls of text.
- **Day 21: the contingency dashboard layer.** Pre-record a video fallback of the demo flow in case live runs fail in front of judges. Create 1-2 "perfect demo" saved scenarios with seed values that produce the cleanest, most narratively-readable cascades. Identify the *exact* agent (by ID and seed) you'll click into during the inspect-view moment — pick one whose reasoning is concrete and persona-distinctive. Cache its output and verify it loads instantly.

**End-of-week-3 definition of done:** the demo has a written script. The dashboard has a benchmark panel and the headline delta computed and prominently displayed. Slides exist. A pre-recorded fallback video exists. You know exactly which scenario and which agent you'll click into during the live demo.

### Week 4: Polish + rehearsal + presentation prep

**Goal: presentation-ready dashboard, deeply rehearsed demo, tight Q&A handling.**

**Days 22–23: visual polish**
- Consistent color palette. Persona icons. Smooth transitions in the live view.
- Loading states, error states, friendly empty states.
- Inspect view layout: cost function, principal value plot, decision history all visible without scrolling.
- Cost summary printed at end of every run.

**Days 24–25: demo rehearsal**
- Time the full presentation. The flow is: motivate the question (1 min) → show the configure page and pick a scenario (30 sec) → run the AI-speed simulation and watch live view (90 sec) → pause at peak chaos and click an agent (1 min) → read reasoning aloud (1 min) → show AI-vs-human comparison side by side (90 sec) → land the headline delta number ("AI delegation made this run X times faster; the human-speed version of the same scenario barely produced a run at all") → show variance findings and benchmark panel briefly (1 min) → close with v2 vision (30 sec). Roughly 8 minutes.
- The headline delta number is the punchline. Practice landing it. The audience should walk away with one specific quantitative claim.
- Run the demo for 2-3 people unfamiliar with the project. Time them to first "oh I get it" moment. Fix whatever was confusing.
- Cost audit. Document total spend.

**Days 26–28: deep rehearsal + Q&A prep + buffer**
- Run the full demo at least 3 times under realistic conditions: standing up, projector connected, no notes (or only the script printed for emergency reference). Time each run. Variance under 30 seconds across runs means you have the timing internalized; more variance means you need more reps.
- **Q&A preparation.** Write down the 8-10 most likely judge questions and rehearse 60-90 second answers for each. Likely categories: "how does this generalize to real systems?", "what would you do next?", "what are the limitations?", "could AI agents be designed to avoid this?", "is anyone else doing this?" (Rajan & Ruaño 2026 is your honest answer here — name them, articulate the differentiation in 30 seconds), "what would a regulator do with these findings?", "how confident are you in the headline number?". The Q&A is often what separates winners from runners-up — strong technical work with weak Q&A handling loses to medium technical work with sharp Q&A.
- Final dashboard polish based on rehearsal feedback. If something is consistently confusing in rehearsal, fix it now.
- Buffer for things running late. Do not use this for new features.

## Decision rules (read these when stressed)

**If days 1–2 take 3 days:** Accepted. Foundation matters. The LLM client + caching is genuinely tricky to get right.

**If by day 5 the personas don't produce visibly different decisions:** The cost functions are too generic. Rewrite them with more specific narratives ("rent is due in 9 days and you have $400" not "you have liquidity constraints"). The LLM grounds its reasoning in specifics.

**If by end of week 1 the cascade isn't emerging:** Two likely culprits. (1) The social_signal mechanic isn't actually influencing decisions — fix the prompt to make peer actions salient. (2) The thresholds for re-decision are too high — agents observe peers withdrawing but don't update. Tune one at a time and inspect outputs.

**If by day 10 the live view is laggy:** This is why we pre-render. If you're trying to do truly real-time and it's slow, switch to pre-render + playback. The dashboard becomes much smoother and you don't lose anything from the demo.

**If by day 13 the inspect view feels boring:** The reasoning is generic. The fix is in week 1's persona writing — go back and add more specificity to the cost functions. Concrete narratives produce concrete reasoning.

**If by day 18 the variance is too high to draw findings:** Either the rumor credibility levels are too close to the decision threshold (so small persona variations dominate) or you need more runs per scenario. Increase to 15 runs per scenario before declaring no signal.

**If on day 22 you find yourself wanting to add the textbox scenario translator:** No. Note it in `FUTURE_WORK.md`. Polish what exists.

**If LLM costs are higher than projected:** Check caching. If caching works, switch all routine decisions to Haiku. If still high, drop from 12 to 8 agents. The findings stay valid; the demo stays compelling.

**If you're behind by end of week 2:** Cut the AI-vs-human comparison view. Keep one speed setting. The inspect view is non-negotiable; the comparison is optional.

**If you're behind by end of week 3:** Cut to 3 scenario presets instead of 5. Run 5 simulations each instead of 10. The headline delta number gets thinner statistical support but stays defensible as long as the direction is clear and the magnitude is substantial.

## What success looks like at the end of week 4

A working dashboard. A bank run scenario that visibly unfolds with real LLM-driven agent decisions. An inspect view where the audience reads what the AI was thinking. AI-speed vs. human-speed comparison that lands viscerally. A specific quantitative headline: "AI delegation produces an X-fold acceleration of bank run dynamics in our simulation, with the largest effect in moderate-credibility scenarios where human-speed runs typically fail to develop into cascades at all." A benchmark panel anchoring the human-speed baseline to the empirical bank run literature. A rehearsed 8-minute demo that hits its timing within 30 seconds across runs. Sharp 60-90 second Q&A answers prepared for the most likely judge questions. Variance-characterized findings about how different personas behave under stress, displayed in the dashboard.

A *less* successful version: an over-engineered system that doesn't quite ship; a dashboard without the inspect-reasoning moment; a polished demo where the speaker overclaims by framing the headline delta as a prediction about real AI bank runs rather than a characterization of simulation behavior; sharp technical work undermined by a rambling delivery or weak Q&A handling.

The honest version is the impressive version. The framing — "we built a sandbox for studying AI agent behavior under stress, instrumented it carefully, anchored the human-speed baseline to the empirical bank run literature, and measured the AI-delegation acceleration delta" — is more defensible and more interesting than "we predicted what bank runs will look like in five years." For a competition format, judges reward intellectual honesty paired with technical execution. They penalize overclaiming.
