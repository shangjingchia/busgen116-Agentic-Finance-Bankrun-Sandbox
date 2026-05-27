# 8-Minute Demo Script
**Agentic Bank Run Sandbox — Competition Presentation**

---

## Format Overview

| Segment | Format | Duration |
|---|---|---|
| Opening hook | Slide 1 | 0:45 |
| Setup | Slide 2 | 0:30 |
| Headline number | Live screen — Findings tab | 1:15 |
| Who moves first | Live screen — scroll down | 1:00 |
| Read the AI's mind | Live screen — scroll down | 1:00 |
| Can regulation fix it? | Live screen — scroll down | 1:00 |
| Credibility labels | Live screen — scroll up | 0:45 |
| Simulation running + close | Slide 3 (embedded video) | 1:30 |
| **Total** | | **~8:00** |

> **One thing to pre-record:** a 60-second clip of the live view during an actual simulation run — agents receiving the rumor, the graph updating, decisions firing. Everything else is live screen. Findings tab is just scrolling — fast, safe, and shows it's a real interactive tool. If a judge asks "can I see X?" you can navigate there. Pre-recording the findings feels like hiding something.
>
> **Backup:** have the Findings tab open and fully loaded in a browser tab before you start. If Streamlit dies mid-demo, you have the slides.

---

## Slide 1 — The Hook

> **Duration:** 0:45
> **Format:** Slide — full screen, minimal text

```
$42,000,000,000
withdrawn in a single day.

March 2023. Silicon Valley Bank.
The fastest bank run in modern history.

The trigger: depositors — all tech startups,
all watching the same Twitter thread —
all decided to move at once.

That was humans.

What happens when the decision isn't theirs?
```

**Speaker notes:**

"In March 2023, SVB collapsed after $42 billion left in a single day — the fastest bank run ever recorded. The trigger wasn't fraud or insolvency. It was that all their depositors were connected, informed, and had every incentive to move fast. That was people. Within five years, millions of retail depositors will delegate these decisions to AI agents. We built a simulation to ask: what does that look like?"

---

## Slide 2 — The Setup

> **Duration:** 0:30, then switch to live screen
> **Format:** Slide

```
THE SETUP

12 AI agents. Each managing a bank deposit
on behalf of a real person.

A rumor enters the environment.
Agents read it. Watch each other. Decide.

Every decision: a live LLM call.
Every agent: a different persona, mandate,
and cost function.

We run it twice.
  ● AI speed     — agents decide in seconds
  ● Human speed  — 90-second deliberation pause
```

**Speaker notes:**

"12 AI agents, each with a different financial situation and persona — a retired teacher, a hospital CFO, a gig worker. A false rumor enters the environment. Every decision is a live call to a large language model. We run the same scenario twice: once at AI speed — agents decide in seconds — and once at human speed, with a 90-second deliberation pause. Same agents. Same bank. Same rumor. Only the speed changes."

**→ Switch to live screen. Open Findings tab, already loaded, scrolled to top.**

---

## Live Screen — Findings Tab

---

### Section 1 — The Headline Number

> **Duration:** 1:15
> **On screen:** Cascade race chart → speed clock widget

**[At the cascade race chart — top of Findings page]**

"Here's the headline. Same false rumor, 45% credibility. At human speed — the blue curve — agents withdraw over three minutes. At AI speed — the red — it's over in seconds. This shaded region is the intervention window: the time a regulator, a circuit breaker, or a verification step would need to act. At AI speed, it's gone before any human process could begin."

*— pause 3 seconds, let the chart land —*

**[Scroll down to the speed clock widget]**

"The number: AI agents reached 50% withdrawn in **4 seconds**. Human speed: **3 minutes and 12 seconds**. That's a 48× compression. Same agents. Same bank. Same rumor."

> ⏱ **~2:45 elapsed**

---

### Section 2 — Who Moves First

> **Duration:** 1:00
> **On screen:** Finding 3 first-mover table → exit queue dot chart

**[Scroll to Finding 3 — first-mover table]**

"A cascade doesn't happen all at once. Someone goes first. In every single cascading scenario we ran — every rumor strength, both speeds — the first agent to withdraw was the institutional treasurer. The hospital CFO. The manufacturer's treasury manager. Not because they panicked. Because their cost function says 'missing liquidity is career-ending.' They have the clearest asymmetry and no hesitation about paying a fee."

**[Scroll down to exit queue dot chart — Finding 3b]**

"Here's what that looks like as a queue. Every dot is one agent. All three institutional agents — red row — cleared the exit before the first retail depositor even acted. In a real bank failure, early queue position means full payment. Late position means partial payment, or nothing. AI delegation doesn't flatten this hierarchy. It locks it in at machine speed."

> ⏱ **~3:45 elapsed**

---

### Section 3 — Read the AI's Mind ⭐ Demo Moment

> **Duration:** 1:00
> **On screen:** Finding 5 — verbatim LLM output side-by-side

**[Scroll to Finding 5]**

"This is what makes this different from any economic model. These are two agents — both institutional treasurers, same archetype, same information environment. They read the same rumor. They watched the same cascade. One held. One withdrew."

*— pause 10 seconds, let the audience read the cards —*

"The one on the left saw 63% withdrawal and concluded it was panic without evidence. The one on the right saw the same number and concluded it was a signal too strong to ignore. Neither is wrong. They're reasoning from different priors. And we did not write this — this came back from the model. This is what genuine heterogeneity looks like inside an AI agent."

> ⏱ **~4:45 elapsed**

---

### Section 4 — Can Regulation Fix It?

> **Duration:** 1:00
> **On screen:** Finding 6 — 2×2 judgment matrix

**[Scroll to Finding 6]**

"We added a Central Bank agent watching the cascade in real time. Two variants: one makes a live LLM call and reads the bank's reserve ratio before acting. The other fires a fixed deposit guarantee the moment a threshold is crossed — no reasoning, no context. We tested both against a false alarm and a real crisis."

*— point to the matrix —*

"AI-powered CB: 2 out of 2. Correctly held fire on a healthy bank. Correctly intervened on an insolvent one. Rule-based CB: 1 out of 2 — got lucky on the real crisis because it fires the same response regardless. The catch: both CBs only work because they also run at machine speed. A human-reviewed regulatory process — committee deliberation, legal sign-off — operates on hours to days. By then the cascade is over."

> ⏱ **~5:45 elapsed**

---

### Section 5 — Credibility Labels Don't Work

> **Duration:** 0:45
> **On screen:** Finding 2 — flat credibility line chart

**[Scroll up to Finding 2]**

"One more thing for anyone thinking about misinformation policy. We ran the same alarming rumor 14 times, changing only one variable: we told agents how credible the rumor was. 25% — barely credible. 85% — highly credible. That's the red line. Nearly flat. The credibility label is being ignored — because LLMs read the words in a message, not the tag above it. A rumor containing 'liquidity crisis' and 'may not meet withdrawal requests' activates the cost function at 25% credibility just as hard as at 85%. Labeling strategies that work on humans need to be re-engineered for AI delegates."

> ⏱ **~6:30 elapsed**

---

## Slide 3 — The Simulation Running + Close

> **Duration:** 1:30
> **Format:** Slide with embedded 60-second pre-recorded video (top half) + bullet points (bottom half)

```
[EMBEDDED VIDEO — 60 seconds]
Live view: agents receiving the rumor,
decisions firing, graph edges updating in real time.
```

```
WHAT THIS MEANS

  ● AI delegation compresses cascade timescales
    from hours to seconds

  ● Correlated AI populations (same model, same product)
    are the highest-risk configuration

  ● Two regulatory tools commonly discussed —
    credibility labels and visibility limits —
    both need to be re-engineered at the AI layer

  ● This is a sandbox. Every parameter is configurable.
```

**Speaker notes (over video):**

"This is what it looks like running. Each event is a live LLM call. The agents are actually reasoning. You can read every decision in the inspect view afterward."

**Speaker notes (after video, on bullets):**

"Three takeaways. First: AI delegation compresses bank run timescales from hours to seconds — and this is not hypothetical, it's what we measure. Second: the riskiest configuration isn't smarter agents — it's *correlated* agents. A bank where all depositors use the same AI product is functionally a homogeneous crowd. Our results show those cascade every time. Third: two regulatory ideas commonly floated — credibility labels and withdrawal visibility limits — both fail at the AI layer and need to be rethought. The sandbox is open. Every parameter is configurable."

> ⏱ **~8:00 elapsed**

---

## Cut Guide — If Running Long

| Over by | Cut this | How |
|---|---|---|
| 30 sec | Finding 2 (credibility) | One sentence: *"Labels don't work — we have the chart"* — don't scroll there |
| 60 sec | Finding 2 entirely | Jump straight from CB matrix to Slide 3 |
| 90 sec | Also shorten exit queue | Show dot chart, say *"institutional agents own the front of the line, every time"* — skip the rest |

> **Never cut:** SVB hook · speed clock number · Finding 5 verbatim output.
> Those three are the demo. Everything else is context.

---

## Never-Cut Moments — Memorize These Lines

| Moment | Line |
|---|---|
| Speed clock | *"4 seconds versus 3 minutes and 12 seconds. 48 times faster. Same agents. Same bank. Same rumor."* |
| Exit queue | *"AI delegation doesn't flatten this hierarchy. It locks it in at machine speed."* |
| Finding 5 | *"We did not write this. This came back from the model."* |
| CB matrix | *"Both CBs only work because they also run at machine speed. A human-reviewed process operates on hours to days. By then the cascade is over."* |
| Close | *"The riskiest configuration isn't smarter agents — it's correlated ones."* |

---

## Pre-Demo Checklist

- [ ] Streamlit running at `localhost:8501`
- [ ] Findings tab open and fully loaded in browser (scroll to top)
- [ ] 60-second simulation video embedded in Slide 3
- [ ] Slide deck in presentation mode, Slide 1 showing
- [ ] Know which browser tab to Alt-Tab to for live screen
- [ ] Run the 8-minute cut once aloud, alone, the night before
