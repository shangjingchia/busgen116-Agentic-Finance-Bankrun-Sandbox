# AI Bank Run Sandbox — Slide Deck Content
## For NotebookLM slide generation

---

# SLIDE 1 — TITLE

**Title:** When AI Agents Run the Bank

**Subtitle:** Studying cascade risk in AI-delegated retail finance

**Speaker note:**
This project asks a forward-looking question: as consumers increasingly hand financial decisions to AI agents, what happens during a stress event? We built a controlled sandbox to find out.

---

# SLIDE 2 — THE NEAR-FUTURE PROBLEM

**Title:** AI is taking over retail financial decisions

**Key points:**
- Robo-advisors already manage over $1.4 trillion in retail assets globally
- Next generation: agentic AI that doesn't just recommend — it acts. Moves money, executes trades, rebalances portfolios, responds to news — autonomously and continuously
- This delegation is already happening: Apple's financial AI assistant, fintech "autopilot" accounts, AI-driven cash management tools
- The question nobody has seriously studied: **what does a population of AI financial agents look like under stress?**

**The core concern:**
Human bank runs are already dangerous. A bank run mediated by AI agents acting simultaneously, on the same signals, without hesitation — could be categorically different.

**Speaker note:**
We're not speculating about the distant future. Agentic AI in finance is a 3-5 year deployment horizon, not science fiction. The SVB collapse showed how quickly digital bank runs move even with human decision-makers. The question is what happens when humans are taken out of the loop entirely.

---

# SLIDE 3 — WHAT WE BUILT

**Title:** A controlled sandbox for AI agent behavior under financial stress

**The setup:**
- 12 LLM-powered agents — each with a distinct persona, financial situation, risk tolerance, and goals
- Two banks: Bank A (under rumor) and Bank B (safe haven)
- A rumor enters the environment with configurable credibility
- Agents observe the rumor, watch each other act, and decide: hold, partially withdraw, or fully withdraw
- We compare **AI speed** (agents decide in seconds) vs **human speed** (90-second deliberation delay)

**Four agent archetypes, three each:**
- Cautious Retirees — CD Saver, Dependent Retiree, Savvy Retiree (deposits: $25k–$50k, locked CDs, catastrophic loss aversion)
- Aggressive Traders — Fintech Engineer, Options Trader, Crypto Trader (smaller deposits, high sophistication, act fast on signals)
- Gig Workers — Freelance Designer, Freelance Developer, Part-Time Worker (tiny deposits $1.8k–$3.2k, entire liquid cushion at stake)
- Institutional Treasurers — Manufacturer, Tech Startup, Hospital System (deposits: $310k–$590k, fiduciary duty, payroll obligations)

**What makes this different from a model:**
Every agent decision is a real LLM call. The agent's persona, portfolio, observations, and cost function go in. A structured action comes out. We read what the AI was actually thinking.

**Speaker note:**
This is not a parameterized economic model where we set utility functions and solve. Each agent is prompting a language model with their specific situation and reading real reasoning. The Inspect view — where you can literally read what the AI was thinking — is the centerpiece of the demo.

---

# SLIDE 4 — THREE MECHANISMS (THE ARGUMENT)

**Title:** The risk isn't speed alone — it's the removal of friction

**The concern with AI delegation isn't that AI is faster in absolute terms. A 12-agent simulation can't be compared to a real bank. The concern is that AI delegation removes three specific friction points that historically slowed bank runs and prevented false alarms.**

**Mechanism 1 — Cost function asymmetry overrides signal quality:**
Each agent reasons with an explicit cost function: "being wrong by staying is catastrophic; being wrong by leaving is merely significant." Under this asymmetry, the model acts on ambiguous signals even at low stated credibility. Our sweep shows withdrawal rates of ~85% regardless of whether the rumor is labeled 25% or 85% credible — the alarming content activates the asymmetry; the credibility label does not override it. AI agents cannot be "detuned" by adding a disclaimer.

**Mechanism 2 — Correlated reasoning without coordination:**
AI agents using similar models apply similar logic to the same signal. They herd without communicating — no group chat needed. In SVB, coordination required VC advisors to actively tell founders to withdraw. In our simulation, 12 agents with different personas and different financial situations converged on the same withdrawal decision on the same rumor — independently, simultaneously. The convergence is driven by shared model reasoning, not communication.

**Mechanism 3 — Peer contagion is amplified at AI speed:**
At AI speed, 45% of all decisions are peer-triggered re-decisions — agents reconsidering after watching others act. At human deliberation speed: 8%. The deliberation window isn't just a delay; it changes cascade mechanics. Human hesitation absorbs the first cascade wave before it reaches later agents. AI speed compresses all waves into the same moment, turning a sequential signal into a simultaneous shock.

**Speaker note:**
Mechanism 1 is the most important for Q&A. The data shows both AI and human speed cascade at all credibility levels — so the old framing of "lower threshold" doesn't hold. The real finding is that alarming content dominates stated credibility for both LLMs and deliberating humans. The difference is mechanism 3: cascade intensity and peer contagion structure.

---

# SLIDE 5 — EMPIRICAL ANCHORING

**Title:** Why even a small fraction of AI-delegated deposits is dangerous

**The Iyer-Puri finding (2012):**
Rajkamal Iyer and Manju Puri studied the 2001 Indian bank run and found that typically only **3–7% of depositors** need to withdraw to threaten a bank's liquidity. Uninsured depositors ran at rates 30+ percentage points higher than insured ones. Distance to a branch and social network density were the strongest predictors of early withdrawal — constraints that AI agents do not face.

**Why this matters for AI delegation:**
If AI agents manage even a modest fraction of retail deposits — say 10–15% by 2030 — and cascade at lower credibility thresholds than human depositors, the aggregate effect scales to a dangerous level. No individual agent needs to behave irrationally. The systemic risk emerges from the combination of low thresholds, correlated reasoning, and fast execution.

**SVB as a preview (March 2023):**
SVB was the fastest bank run in modern history: $42 billion withdrawn in a single day. The key wasn't speed alone — it was that SVB's depositors were clustered (tech startups advised by the same VCs), monitored the same Twitter feeds, and were almost entirely above the $250k FDIC limit. AI delegation recreates these conditions for any bank: concentrated, correlated, informed, and above insurance thresholds.

**The bridge:**
Our simulation doesn't predict real bank run dynamics. But it shows that AI agents cascade on weaker signals, in correlated ways, without the deliberation buffer that human hesitation provides. Iyer-Puri tells us the threshold for systemic risk is low — 3–7%. The question is whether AI delegation brings more depositors above that threshold, faster, on weaker signals.

**Speaker note:**
This is the most important slide for grounding the argument. The simulation finding alone could be dismissed as a toy model. The Iyer-Puri finding gives it teeth: we don't need most depositors to run. We need very few. And AI agents — acting fast, on weak signals, in correlated ways — make "very few" easier to reach.

---

# SLIDE 6 — THE DASHBOARD (DEMO PREVIEW)

**Title:** What the simulation produces

**Three views designed for live demonstration:**

**Configure:**
Pick a scenario — from "moderate credibility rumor, bank solvent" to "high credibility rumor, bank genuinely insolvent." Set the rumor credibility, social signal visibility. Switch between AI Speed and Human Speed. Press Run.

**Live View:**
Watch the simulation unfold. See each agent observe the rumor, deliberate, and act. The event timeline shows exactly who moved when and why — "Crypto Trader observed rumor at T+2s → withdrew 100% at T+4s." Bank A's reserve ratio drops with each withdrawal.

**Inspect:**
Click any agent. Read their full LLM reasoning. A cautious retiree: "This CD has 8 months left and a 3% penalty. The rumor is from a regional outlet, not a regulator. I've worked 40 years for this money and I am not moving it on one unverified report." An options trader: "I watched SVB collapse in real time. When credible signals appear, you move first and ask questions later. I'm moving everything now."

**Compare:**
Same scenario, same agents, same rumor — run at AI speed and human speed side by side. The headline: which speed cascaded, which held, and by how much.

**Speaker note:**
The Inspect view is the demo centerpiece. Judges should be able to read two or three agents' reasoning and immediately identify which persona produced which. If they can do that, the heterogeneity is real and the project has demonstrated its core claim.

---

# SLIDE 7 — KEY FINDINGS

**Title:** What the simulation found

**Finding 1 — Credibility labels have no effect (sweep across 7 levels):**
We varied the stated rumor credibility from 25% to 85% while keeping content constant. Withdrawal rate stayed flat at ~85% at both AI and human speed across all seven levels. The alarming content — not the credibility percentage — is what drives the cascade. This has a direct regulatory implication: labeling unverified information with credibility scores or "UNCONFIRMED" warnings will not dampen AI-mediated runs, because LLMs parse content semantics, not tags.

**Finding 2 — False alarms at full rate (high and moderate credibility, solvent bank):**
In every high- and moderate-credibility scenario where the bank was solvent: 12/12 agents withdrew at AI speed, 12/12 at human speed. Every agent was tagged *panicked_unnecessarily*. Neither speed — AI or human — distinguished real crisis from false alarm when the content was alarming. The withdrawal decision was driven by cost function asymmetry, not ground truth.

**Finding 3 — Cascade anatomy: institutional AI leads, peer contagion follows:**
In all six cascading scenarios, the Institutional Treasurer acted first — highest stakes, clearest asymmetry, access to the more capable model (Sonnet vs Haiku for retail). At AI speed, 45% of all subsequent decisions were peer-triggered re-decisions; at human speed, only 8%. The cascade isn't just faster — it's structurally different. AI speed turns a sequential wave into simultaneous contagion.

**Finding 4 — The reversal: AI is better calibrated on genuinely weak signals:**
With weak, vague content: AI held 0/12 (correct). Human deliberation panicked 2/12. During the 90-second window, social signals from early movers accumulated and pushed marginal agents to withdraw unnecessarily. The deliberation buffer cuts both ways — it stabilizes moderate false alarms, but amplifies weak-signal panic through social contagion.

**What this means:**
AI delegation doesn't uniformly increase cascade risk — it changes *where* the risk lives. False alarms on alarming-but-uncertain signals become near-certain. Cascade contagion is structurally more intense. And the institutional AI advantage means retail depositors are systematically last in line, even if they also delegate to AI.

**Speaker note:**
Finding 4 (the reversal) is the best Q&A hook — it's counter-intuitive and shows the simulation produces non-obvious behavior. Finding 3 (institutional advantage) is the strongest policy point. If judges push on the 12-agent scale: Finding 1 is the answer — the behavioral pattern (credibility labels don't work) is about model behavior, not scale.

---

# SLIDE 8 — HONEST SCOPE AND IMPLICATIONS

**Title:** What this shows and what it doesn't

**What the simulation shows:**
- AI agents cascade on weaker signals than human deliberation speed
- Correlated reasoning produces herding behavior without explicit coordination
- Removing the deliberation buffer removes a stabilizer, not just a delay
- The behavioral patterns are robust across scenario types

**What it does not show:**
- Real bank run dynamics at scale — 12 agents is a proof-of-concept, not a model
- Calibrated predictions about real depositor behavior
- That AI bank runs in reality will be X times faster or larger than human runs
- Any specific bank or depositor population

**Why study this now:**
AI delegation in retail finance is a 3-5 year deployment horizon. The regulatory and risk management frameworks for this don't yet exist. This project is a first probe into the behavioral patterns that emerge specifically when AI agents make financial decisions under stress — before it happens at scale, not after.

**The open question:**
Do AI financial agents need a deliberation floor? A minimum latency before acting on financial stress signals? The simulation suggests that human hesitation was doing stabilizing work that we don't fully appreciate until it's gone.

**Speaker note:**
End on the open question, not a conclusion. The strongest position for Q&A is: "we've identified a pattern worth taking seriously, not a prediction." Judges who push on the 12-agent limitation get the Iyer-Puri response: systemic risk doesn't require most depositors, just 3-7%.

---

# APPENDIX — Q&A PREPARATION

**Q: How can you compare 12 agents to a real bank run?**
A: We don't. The finding is about behavioral patterns — specifically, at what signal strength AI agents cascade versus human deliberation. The Iyer-Puri finding does the scaling: if those patterns generalize, the threshold for systemic risk is 3-7% of depositors, not a majority.

**Q: Aren't the agents just following their prompts?**
A: Yes — that's the point. The agents are doing exactly what an AI delegate would do: reasoning within their persona and cost function about what's in their principal's interest. The finding is that a population of well-intentioned, individually rational AI agents can produce collectively dangerous behavior. No agent needs to malfunction.

**Q: Couldn't you just add a delay to AI agents to fix this?**
A: Possibly — and that's one policy implication. But delay alone doesn't address correlated reasoning or lower trigger thresholds. AI agents with a 90-second delay still apply similar logic to the same signal. The deliberation buffer helps, but it's not a complete solution.

**Q: Why not use a real economic model instead of LLMs?**
A: A parameterized model would bake in the answer — we'd be specifying how agents respond to signals. LLMs let us observe emergent reasoning from persona-conditioned agents. The interesting finding is not that AI agents "can" cascade — it's reading the reasoning they produce when they do, and seeing the patterns in that reasoning.

**Q: Is social_signal_visibility = 1.0 realistic?**
A: For AI agents, yes — they monitor all feeds continuously. For human-speed runs, we use 0.55, reflecting that human depositors see a filtered, delayed subset of social signals. The differential is itself part of the argument: AI agents don't just act faster, they also see more of the signal environment simultaneously.
