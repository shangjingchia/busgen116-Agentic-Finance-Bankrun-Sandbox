# Presentation Script (TIGHT) — AI Bank Run Sandbox
**Target ~6:35 · hard ceiling 7:00** · live demo + recording + slides

> This is the trimmed talk track. The full `PRESENTATION_SCRIPT.md` stays as the master and Q&A reference.
> **One rule:** every claim is *"in our simulation, these agents did X"* — never *"AI bank runs in reality will be X."*

**Setup before you walk up:** dashboard running (`streamlit run src/dashboard/app.py`), browser at `localhost:8501` on the Presets page, slides open on a second screen, Sandbox recording queued. First demo move is live — pre-load nothing.

---

## Timing map (target ~6:15)

| Time | Segment | Surface |
|------|---------|---------|
| 0:00–0:35 | Hook + premise | Slides 1–2 |
| 0:35–1:00 | What this is | Slide 3 |
| 1:00–2:50 | **LIVE DEMO** — run, read a mind | Slide 4 → Dashboard: Presets → Inspect |
| 2:50–4:20 | Three findings | Dashboard: Findings |
| 4:20–5:05 | SVB anchor + two numbers | Slides 5–6 |
| 5:05–5:30 | Why it matters | Slide 7 |
| 5:30–6:35 | Sandbox + close (incl. the "infrastructure" vision) | Slide 8 + recording |

**Cut levers if long:** drop Finding 3 (Language) and the second inspected agent (~50–70s). Never cut the Model finding or the SVB anchor. Keep the recording (it's your required demo if the live one fails).

---

## 0:00 — Hook *(Slide 1)*

> "In five years, most of us won't move our own money in a crisis. An AI agent will — checking our accounts, reading the news, deciding whether to pull our savings, in seconds, while we're asleep.
>
> So we built a sandbox to ask one question: **when a bank rumor hits and the depositors are AI agents instead of people — what happens?**"

## 0:20 — Premise *(Slide 2)*

> "A human bank run is slow because *noticing* is slow. You have to see the news, sit with it, second-guess, maybe call someone — and most people aren't watching at 3am. Even SVB, which ran entirely online, took most of a day. That hesitation is part of what stops a rumor from becoming a collapse.
>
> AI delegates remove it. They watch every feed, act in seconds, and tend to reason alike. We wanted to see what that does to a run."

## 0:35 — What this is *(Slide 3)*

> "This is **not** a forecast. It's twelve AI agents, each making **real LLM calls** to decide what to do with someone's money. Each has a persona — a cautious retiree, a trader, a gig worker, an institutional treasurer. They hold deposits at two banks. A rumor hits Bank A. Each sees the rumor, sees what others do, and decides: **hold, partially withdraw, or run.** Everything I show you is the actual reasoning the models produced."

---

## 1:00 — LIVE DEMO

### Load a run *(Presets page)*

> "I'll load a run we did earlier so we're not waiting on API calls — but every decision here was made live."

- **[CLICK]** Presets → Load saved run → **"Strong rumor · Bank healthy · AI speed."**

> "Note the setup: a strong, alarming rumor about Bank A — **but the bank is fine.** It's solvent. No one's money is actually at risk. **[CLICK Load and view →]**"

### The summary *(Inspect page)*

> "Look at the top strip: this is what twelve agents did with a *false* alarm. All twelve tried to exit — on a healthy bank."

### Read a mind *(spend time here)*

- **[CLICK]** the first mover, or an **Institutional Treasurer.**

> "This is real model output, not a script. It weighs the withdrawal fee against the risk to principal, decides the fee is worth it, and runs — on a bank that was fine."

- **[CLICK]** a **Cautious Retiree.**

> "Same rumor, different persona — and listen to the voice. It reasons like a frightened retiree, not a trader. You can tell the personas apart without the labels. That's the heterogeneity doing real work.
>
> This is the part I'd never seen before: you can read what the AI was thinking when it decided to run."

---

## 2:50 — THREE FINDINGS *(Findings page)*

> "We ran dozens of these. Three patterns held up. Top to bottom."

### Finding 1 — Same personas, different brains *(the headline)*

> "This one surprised us. We froze everything — same personas, same rumor, same healthy bank — and changed one thing: **which model** decides. Withdrawing here is the wrong call; the bank is fine.
>
> With Claude, about **half** run. With GPT, **every one** runs. The model alone takes it from a scare to a full collapse — and these bars are replicated four to five runs each, so the ranking is stable.
>
> The punchline: if everyone's money is run by the same model, you don't have a diversified crowd — you have a monoculture that panics in lockstep. **The model itself is a systemic risk.**"

### Finding 2 — Speed *(scroll down)*

> "Second: speed. Same scenario at AI speed versus human speed — a 90-second delay per agent. This is the time for half the depositors to *decide*, not for cash to settle: about **5 seconds** versus **15**. Roughly **three times faster.**
>
> And moving money is rate-limited, so the requests arrive faster than the bank can pay. It freezes before most cash settles — only **5 of 12** got paid at AI speed, versus **11 of 12** at human speed. Machine speed doesn't move money faster — it freezes the bank faster and locks more people out."

### Finding 3 — The words decide *(scroll down)*

> "Third: we changed only the *wording* — same bank, same credibility label. **Soft language** — 'some concern, worth monitoring' — and 31% leaves; the bank survives. **Crisis language** — 'cannot process withdrawals' — and 93% drains in under nine seconds. The words, not the credibility tag, decide whether the bank lives.
>
> *(We tested more — a regulator, credibility sweeps. Happy to take those in Q&A.)*"

---

## 4:20 — Anchor + numbers *(Slides 5–6)*

> *(Slide 5 — SVB)* "Is this realistic? We don't model real banks. But for scale: in March 2023, Silicon Valley Bank lost **$42 billion in one day** — the fastest run in modern history. Why? Its depositors were all startups, advised by the same VCs, watching the same threads — but that took an unusual, tightly-correlated base. **AI delegation manufactures that correlation for any bank** — and adds a new axis: the same model."

> *(Slide 6)* "Two numbers to remember. **One: the model alone took a healthy bank from a 50% scare to a 100% run** — nothing else changed. **Two: AI delegation hit the halfway mark about 3× faster than humans.** Homogeneous and instant — that's the combination."

## 5:05 — Why it matters *(Slide 7)*

> "Three things for anyone building or regulating AI money-managers:
> 1. **The model is a systemic risk factor** — a fleet on one model panics in lockstep.
> 2. **Speed compresses the response window to seconds** — human oversight can't keep up.
> 3. **Agents react to alarming language, not stated credibility** — and they're just as confident when they're wrong.
>
> This is a twelve-agent sandbox, not a forecast. The point is to find these failure modes cheaply, now — before this is how finance actually works."

## 5:30 — Sandbox + close *(Slide 8 + recording)*

> "We didn't hard-code these scenarios. It all runs on a sandbox where you build any run. Here's a short recording."

**Play the recording.** Narrate lightly — don't read every control:

> "You describe an agent in plain English, set the bank's health and payout speed, choose the population mix, write the rumor, and optionally drop in a regulator or a counter-signal that talks the agents back. Name it, run it, reload it.
>
> *(As the result lands)* Same engine, different scenario. And this is really **infrastructure**: a regulator can stress-test its delegation rules before approving them, a fintech can test its agent before launch — and as you feed in real data on who delegates to which model, you can size the systemic risk we found here. Eventually you just *type* the crisis and the sandbox builds it. Twelve agents is the start — this is how anyone probes the next one. **Thank you — happy to dig into any of it.**"

> Recording: keep to ~30–40s, end on the Inspect view so the last thing on screen is an agent's reasoning. Pre-render it — do not run a live Sandbox simulation on stage.

---

*Q&A answers and backup-slide map (B1–B8): see the full `PRESENTATION_SCRIPT.md`.*
