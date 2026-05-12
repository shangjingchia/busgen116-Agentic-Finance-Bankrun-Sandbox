# Demo Script — AI Bank Run Sandbox
**Live Presentation · ~8 minutes**

---

## OPENING [0:00 – 0:45]

*[Screen: dashboard sidebar, no run loaded yet]*

> "What happens to your savings when the person in charge of them is not a person?
>
> Within the next five years, AI agents will increasingly manage retail financial accounts
> on behalf of consumers — making decisions at machine speed.
> We built a simulation to study what that looks like under stress.
> Specifically: what happens during a bank run when every depositor has an AI delegate acting for them?
>
> This is a live dashboard. Every decision you see was made by a real large language model call.
> Let me walk you through it."

---

## CONFIGURE VIEW [0:45 – 2:00]

*[Click: Configure in sidebar]*

> "The Configure page is where a presenter — or a researcher — sets up a scenario.
> There are five presets."

*[Hover over the preset list]*

> "Each preset defines a rumor about Bank A, its credibility, whether the bank is actually in trouble,
> and the population of twelve agents managing deposits.
> The key variable is speed: every scenario runs twice —
> once at AI speed, where agents decide in seconds,
> and once at human speed, where we inject a ninety-second deliberation delay per decision.
> Same agents, same rumor, same bank. Only the speed changes.
>
> For this recording, I'm going to load a pre-saved run so I don't have to wait for live LLM calls —
> but this button right here is all it takes to start a real run."

*[Click: Load Saved Run → select `rumor_high_false_ai`]*

> "Strong rumor. Bank is actually fine. AI speed. Twelve agents. Let's see what happened."

---

## LIVE VIEW [2:00 – 4:15]

*[Click: Live View in sidebar]*

> "The live view has two panels.
> On the left, a force-directed graph showing every agent and their connection to Bank A.
> On the right, a scrolling event log."

*[Drag scrubber to T=0]*

> "At T-zero, the rumor enters the information environment. Watch what happens."

*[Slowly drag scrubber forward to ~T=15–20s]*

> "The first mover is Marcus Chen — the Institutional Treasurer managing a corporate account
> worth six hundred and ninety thousand dollars.
> He sees the rumor, runs his cost function —
> what does he stand to lose if he waits and the bank is actually in trouble
> versus what does he lose if he withdraws and the bank turns out to be fine —
> and he acts. Full withdrawal. Within seconds.
>
> That event is now visible on the public ledger. Every other agent can see it."

*[Continue scrubbing to T=40–60s]*

> "Watch the cascade. The retired teacher sees Marcus withdrew. The gig worker sees it.
> The hospital CFO sees it. Each of them re-evaluates.
> The original rumor was the trigger —
> but what's actually driving these decisions now is that someone else moved first.
>
> By the time the simulation ends, eleven out of twelve agents withdrew.
> The bank suspended payouts.
> And — remember — the bank was perfectly fine.
> There was no crisis. This entire run was a false alarm."

*[Pause on final state]*

> "At human speed, this cascade still happened — but it took much longer,
> and the social signal spread more slowly because humans check their banking apps periodically
> rather than monitoring a live data feed continuously.
> At AI speed, the copycat wave arrived before some agents had even processed the original rumor.
> Two separate shocks compressed into a single simultaneous panic."

---

## INSPECT VIEW [4:15 – 5:45]

*[Click: Inspect in sidebar]*

> "This is the part that surprises audiences.
> Click any agent and you can read exactly what the AI was thinking."

*[Click on Marcus Chen / Institutional Treasurer]*

> "Marcus Chen. Corporate treasurer. Managing payroll deposits for a mid-sized manufacturer.
> His cost function is explicit in the prompt:
> missing a payroll cycle is a career-ending event.
> An early withdrawal fee is a line item.
> The asymmetry is stark.
>
> Read his reasoning."

*[Scroll through the reasoning text for a few seconds]*

> "The model walks through the asymmetry. It names the fee. It names the risk of a freeze.
> It decides."

*[Click on a retail agent — e.g. Sofia Rivera the retired teacher]*

> "Now look at Sofia Rivera — a retired teacher living on a fixed income.
> Different voice entirely.
> She's scared. She's not reasoning about payroll;
> she's reasoning about whether her savings are safe.
> The cost function here is 'losing principal is catastrophic.'
> She withdraws too. For completely different reasons that produce exactly the same action.
>
> The personas are doing real work.
> The judges should be able to skim several agents' reasoning logs
> and tell which persona produced which without seeing the names."

---

## FINDINGS VIEW [5:45 – 7:45]

*[Click: Findings in sidebar]*

> "The Findings page compiles what we learned across all twenty-four simulation runs —
> ten preset scenarios and fourteen credibility sweep runs."

*[Scroll to Finding 1 bar chart]*

> "Finding one: agents withdrew even when the bank was perfectly safe.
> In the two alarming scenarios where the bank was solvent,
> every single agent across both speeds withdrew unnecessarily. The red bars. All the way up."

*[Scroll to Finding 2 line chart]*

> "Finding two — and this one has direct policy implications.
> We ran the same alarming rumor fourteen times,
> changing only the stated credibility label:
> from twenty-five percent — 'barely credible' —
> up to eighty-five percent — 'highly credible.'
> The withdrawal rate barely moved. Both lines are almost flat.
>
> Telling an LLM that a rumor is unverified doesn't help,
> because the model is reading the alarming language in the content — not the tag above it."

*[Scroll to Finding 3 — first mover table and peer-trigger bar]*

> "Finding three: the cascade has a structure.
> The Institutional Treasurer went first in every single cascading scenario. Always.
> Because they have the most to lose and the least hesitation about the fee.
> Then the copycat wave.
>
> At AI speed, forty-five percent of all decisions were made because an agent
> watched someone else withdraw — not because of the original rumor.
> At human speed: eight percent.
> AI delegation doesn't just make the run faster. It amplifies peer contagion."

*[Scroll to Finding 4 outcome chart, pause on the three metric boxes]*

> "And finding four: were they right?
> Across all ten preset scenarios,
> forty-nine agents were tagged 'panicked unnecessarily.'
> Twenty-three 'acted appropriately.'
> Twenty-three 'ignored a real warning' —
> they stayed in a bank that was actually collapsing.
>
> There is no tuning that fixes both failure modes simultaneously.
> More reactive catches real crises but amplifies every false alarm.
> Less reactive reduces panic but misses the real signal.
> The only interventions that work on both are structural."

*[Scroll to SVB / Iyer-Puri anchors]*

> "One empirical anchor.
> SVB in March 2023 — forty-two billion dollars withdrawn in a single day,
> the fastest bank run in modern history.
> SVB's depositor base was essentially a population of AI-like actors:
> connected, informed, large uninsured balances, same VCs on every board
> watching the same Twitter feeds.
> AI delegation extends that profile to any retail bank.
> Our simulation compresses comparable cascade dynamics to a matter of seconds."

---

## CLOSE [7:45 – 8:00]

*[Hold on Findings page]*

> "This is not a prediction model.
> It's a controlled environment for studying the patterns that emerge
> when AI agents make financial decisions at machine speed.
>
> What we found is systematic: correlated reasoning without coordination,
> institutional agents structurally ahead of retail,
> and miscalibration to alarming content that no label can fix.
>
> The question isn't whether this will happen.
> The question is whether we study it before it does."

---

## Q&A POCKET ANSWERS

| Question | Answer |
|---|---|
| "Why only 12 agents?" | Tractability — every decision is a real LLM call. 12 agents × ~50 events × $0.001 per Haiku call ≈ $0.60 per run. The patterns emerge at 12; scale is a follow-on question. |
| "Aren't the agents just following their prompts?" | Yes — and that's the point. The prompt *is* the agent's persona and cost function. The finding isn't that any single agent is surprising; it's that the population-level behavior is systematic. |
| "Could you just make the agents more rational?" | You'd have to define 'rational' under uncertainty without knowing if the bank is truly failing. The asymmetric cost function is correct reasoning given the information available. The problem is speed and coordination, not logic. |
| "Is this generalizable beyond bank runs?" | The architecture generalizes to any stress scenario — money market freezes, stablecoin de-pegs, regulatory shocks. Bank runs are v1 because they have the clearest empirical baseline. |
| "What would actually fix this?" | Structural interventions: mandatory wait times before large AI-initiated withdrawals, circuit breakers that pause activity at withdrawal thresholds, ground-truth verification requirements. These need to be enforced at the data-feed API layer, not the human layer. |

---

## TIMING GUIDE

| Section | Duration | Cumulative |
|---|---|---|
| Opening | 0:45 | 0:45 |
| Configure | 1:15 | 2:00 |
| Live View | 2:15 | 4:15 |
| Inspect | 1:30 | 5:45 |
| Findings | 2:00 | 7:45 |
| Close | 0:15 | 8:00 |

*~45 seconds of slack built in for screen transitions.*
