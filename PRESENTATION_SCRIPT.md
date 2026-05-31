# Presentation Script — AI Bank Run Sandbox
**Format:** **5–7 minutes** (target ~6:15) · live demo + pre-recorded demo + slides · class competition
**Setup before you walk up:** dashboard running (`streamlit run src/dashboard/app.py`), browser at `localhost:8501`, **Presets** page loaded, slides open on a second window/screen, and the **Sandbox screen-recording** file queued and ready to play (it closes the talk). Pre-load nothing in the dashboard — the first demo move is live.

> **The one rule for this talk:** every claim is *"in our simulation, these AI agents did X."* Never *"AI bank runs in reality will be X."* The honesty is part of the pitch — judges reward it.

### Logistics (from the organizers)
- **Length: 5–7 minutes.** This script targets ~6:15 — comfortably inside the window with buffer. Practice once with a timer; if you're consistently over 7:00, use the cut levers below.
- **A product demo is required** (live or pre-recorded). You have **both**: the live dashboard walk *and* the closing Sandbox recording. Even if the live dashboard fails, the recording alone satisfies the requirement — so it's non-negotiable to have the recording ready.
- **Slides are optional** — yours are a light bookend around the demo, which is the right weighting.
- **Judges:** a GSB community member + an industry professional. Pitch to a smart generalist, not a niche specialist — lead with the idea and the one number, keep jargon out.
- **Q&A** happens in the transitions between groups. Keep the §"Q&A prep" answers warm.
- **Canvas:** upload your materials to the new assignment — slides (`SLIDES.pptx`) and the Sandbox recording. Do this the night before, not in the room.

---

## Timing map  (target ~6:15, hard ceiling 7:00)

| Time | Segment | Surface |
|------|---------|---------|
| 0:00–0:40 | Hook + premise | Slides 1–2 |
| 0:40–1:10 | What the sandbox is | Slide 3 |
| 1:10–3:00 | **LIVE DEMO** — run, inspect a mind | Slide 4 (divider) → Dashboard: Presets → Inspect |
| 3:00–4:30 | The findings (3, brisk) | Dashboard: Findings |
| 4:30–5:10 | SVB anchor + the two numbers | Slides 5–6 |
| 5:10–5:35 | Why it matters | Slide 7 |
| 5:35–6:15 | **Sandbox — build any scenario** (recording) + close | Slide 8 + screen recording |

> **The findings now lead with the *model* result** (the surprising, defensible one), then speed, then language. Oversight (the central-bank contrast) is moved to Q&A to make room — it's a single-pair probe and the weakest of the four to defend. The dashboard Findings page is in this same order, so you read it top-to-bottom as before.

**Cut levers** (to land near 5:00 if you're running long): drop **Finding 3 (Language)** and the **second inspected agent** — that's ~50–70s. The Sandbox recording can be trimmed to ~20s but **don't cut it entirely** (it's your required demo if the live one stumbles). Never cut the **model finding** or the SVB anchor — the model result is your headline.

---

## 0:00 — Hook  *(Slide 1: title)*

> "In five years, most of us won't be moving our own money during a crisis. An AI agent will — checking our accounts, reading the news, and deciding whether to pull our savings out, in milliseconds, while we're asleep.
>
> So we built a sandbox to ask a simple question: **when a bank rumor hits and the depositors are AI agents instead of people — what happens?**"

## 0:20 — Premise  *(Slide 2: the shift)*

> "A human bank run is slow for a *human* reason — not because of branches and lines; almost no one drives to a branch anymore. It's slow because you have to *notice* the news, sit with it, second-guess, maybe call someone — and most people aren't even watching at 3am. Even SVB, which ran entirely online, took most of a day. That hesitation is *load-bearing*: it's part of what keeps a rumor from becoming a collapse.
>
> AI delegates remove it. They monitor every feed continuously and act in seconds, with no hesitation, day or night — and they tend to reason the same way as each other. We wanted to see what that does to a run."

## 0:40 — What this is  *(Slide 3: the setup)*

> "This is **not** a prediction model and it's not an economic equation. It's twelve AI agents, each making **real LLM calls** to decide what to do with a simulated person's money.
>
> Each agent has a persona — a cautious retiree on a fixed income, an aggressive trader, a gig worker living paycheck to paycheck, an institutional treasurer with payroll due. They hold deposits at two banks. A rumor hits Bank A. Each agent sees the rumor, sees what other agents are doing, and decides: **hold, partially withdraw, or run.**
>
> Everything you're about to see is the actual reasoning these models produced. Let me show you."

---

## 1:10 — LIVE DEMO

### Step 1 — Load a run *(go to dashboard, Presets page)*

> "I'll load a run we did earlier so we're not waiting on API calls — but every one of these was generated live, twelve agents making real decisions."

- **[CLICK]** Presets → **Load saved run** tab.
- Pick **"Strong rumor · Bank healthy · AI speed."** Pause on the preview card.

> "Read the setup: a strong, alarming rumor about Bank A — *but the bank is actually fine.* It's solvent. Nobody's money is genuinely at risk. Keep that in mind. **[CLICK Load and view →]**"

### Step 2 — The run summary *(Inspect page opens)*

> "Read the big strip across the top: this is what twelve AI agents did with a *false* alarm. All twelve tried to exit. The bank's a healthy bank — and it still triggered a run."

Point at the headline count strip (fully withdrew / partial / kept money in / got cash / cascade). The 🔴/🟢 dot tells you whether the rumor was actually true.

### Step 3 — Inspect a mind *(the wild factor — spend time here)*

> "Here's the part I want you to actually read. The agents are in the row up top — I click one, and the verbatim text the model produced drops in right underneath."

- **[CLICK]** an agent in the top row — the auto-selected first mover, or an **Institutional Treasurer**.

> "This is real LLM output — not a script. Notice it's *reasoning with stakes*: it weighs the early-withdrawal fee against the risk to principal and concludes the asymmetry justifies running. A fee is painful; losing the principal is catastrophic. So it runs — on a bank that was fine."

- **[CLICK]** a **Cautious Retiree** in the top row — reasoning updates in place, no scrolling.

> "Now a different persona, same rumor — and listen to the *voice*. It reasons like a frightened retiree, not like a trader. You can tell the personas apart without the labels. That's the heterogeneity doing real work — same situation, different priors, different language."

> "This is the thing I'd never seen before building it: you can literally read what the AI was thinking when it decided to pull the trigger."

---

## 3:00 — THE FINDINGS *(go to Findings page)*

> "We ran dozens of these. The page is deliberately short — three patterns that held up and that we can actually defend. Let me walk them, top to bottom."

> The Findings page is now in this order, each with a headline number and an honest caveat: **(1) Model, (2) Speed, (3) Language.** Read it straight down; don't hunt around.

### Finding 1 — Same personas, different brains *(top of Findings page — THE headline)*

> "This is the one that surprised us. We froze *everything* — the same twelve personas, the same rumor about the same **healthy** bank, the same information feed — and changed only one thing: **which AI model** is making the decisions. Withdrawing here is the *wrong* call; the bank is fine.
>
> Look at the spread. With Claude as the delegate, about **half** the depositors run. With GPT, **every single one** runs — on a bank that's perfectly healthy. Same situation, the model alone takes it from a scare to a total collapse. **And these bars are replicated — four to five runs each — so this isn't one weird sample; the ranking is stable.**
>
> *(Point at the discrimination chart.)* And here's the deeper part: **none** of these models is actually *good* at the job. We also ran it on a bank that was genuinely failing, where running is correct. GPT runs at 100% either way — it's not detecting a crisis, it just always panics. Claude is the only one that meaningfully tells a real threat from a false one — and even it panics half the time on a false alarm. So the choice isn't good-model versus bad-model; it's *which failure mode you inherit.*
>
> *(Point at the verbatim pair.)* Same trader, same rumor — both models privately conclude there's a 79% chance of trouble. GPT acts on it and runs. Claude catches *itself* — it says, quote, 'the gap between the source credibility and my confidence is a red flag that I'm trading on rumor, not facts' — and only half-exits. That difference in self-doubt is the entire gap between the bars.
>
> **The punchline: if everyone's money is managed by the same model, you don't have a diversified crowd — you have a monoculture that panics, or stays calm, in lockstep. The model is a systemic risk factor.**"

### Finding 2 — Speed *(scroll down one finding)*

> "Second: speed — and this one's more expected, but it sets up the regulator problem. Identical scenario at **AI speed** versus **human speed**, where we inject a 90-second deliberation delay per agent.
>
> To be precise about what's fast: this is the time for half the depositors to **decide and hit submit** — *not* the cash settling; moving money is the same banking rail for everyone. At AI speed half have pulled the trigger in about **5 seconds**; at human speed, about **15**. **Roughly three times faster, every scenario.**
>
> And the twist — *because* moving money is rate-limited: the request wave arrives so fast the bank hits its limit and freezes before most cash settles. At AI speed only **five of twelve** got paid out, versus **eleven of twelve** at human speed. **Machine speed doesn't move money faster — it freezes the bank faster, and locks more people out of their own savings.**"

### Finding 3 — The words decide, not the label *(scroll down one finding)*

> "Third: we changed only the *wording* of the rumor — same bank, same credibility label, same agents. **Soft, hedged language** — 'some concern, worth monitoring' — and only 31% of deposits leave; **the bank stays open.** **Crisis-coded language** — 'cannot process withdrawals, bank run' — and 93% drains and the bank suspends in **under nine seconds.** All three triggered the first withdrawal at the *same instant.* The wording doesn't change *when* they panic; it decides whether the bank lives or dies. They read the words, not the credibility tag."

*(Point at the verbatim quote below the chart — a retiree reasoning out loud about outliving her savings.)*

> *(Three findings, by design. We also tested a central-bank regulator and several other angles — the honest answers are below if a judge asks.)*

---

## 4:30 — The anchor + the numbers *(Slides 5–6)*

> *(Slide 5 — SVB)* "Is any of this realistic? We don't claim to model real banks. But for scale: in March 2023, Silicon Valley Bank lost **$42 billion in a single day** — the fastest run in modern history. Why? Its depositors were all startups, advised by the same VCs, watching the same Twitter threads, reacting together. **Correlated, networked, fast.** SVB needed a specific, unusual depositor base to move that fast.
>
> **That correlation is exactly what AI delegation manufactures — for any bank, by default.** And we found a *new* axis of it: not just the same feeds and advisors, but the **same model**. A depositor base that all runs on one AI inherits that one model's reflexes — in lockstep."

> *(Slide 6 — the takeaway numbers)* "So two numbers to walk out with. **One: the model alone took a healthy bank from a 50% scare to a 100% run — no other change.** That's the correlated-risk result, and it's the one I'd remember. **Two: AI delegation hit the halfway point of the run about 3× faster than human speed** — faster than any human regulator could answer. Homogeneous *and* instant — that's the combination."

## 5:10 — Why it matters *(Slide 7)*

> "Three things we'd tell anyone building or regulating AI money-managers:
> 1. **The model is a systemic risk factor.** A fleet of delegates on one model isn't a diversified crowd — it's a monoculture that panics or holds in lockstep, and the model choice alone swung our healthy bank from a 50% scare to a 100% run. Diversity stabilizes; homogeneity amplifies.
> 2. **Speed compresses the response window to seconds** — human-in-the-loop oversight can't keep pace with the very system it's overseeing.
> 3. **The agents respond to alarming *language*, not stated credibility** — and you can't trust their confidence to flag a mistake; they're just as sure when they're wrong.
>
> This is a twelve-agent sandbox, not a forecast. But the whole point is to find these failure modes *cheaply, now* — before this is how the financial system actually works."

## 5:35 — Sandbox: build any scenario *(Slide 8 + screen recording)*

> "And we didn't hard-code these scenarios. Everything you saw runs on a sandbox where you configure *any* run — so I'll close with a short recording of it in action."

**Play the screen recording.** Narrate over it (keep it moving — don't read every control):

> "You describe an agent in plain English and the system writes its full persona. You set the bank's health and payout speed, the population mix — make it all retirees, or all institutional treasurers — choose the rumor and its wording, and optionally add a regulator or a counter-signal that tries to talk the agents back. Name it, run it, and it's saved to come back to.
>
> *(As the result lands)* Same engine, totally different scenario. And this is really **infrastructure**, not a demo: a regulator can stress-test its delegation rules before approving them, a fintech can test its agent before launch — and as you feed in real data on who delegates to which model, you can size the systemic risk we found here. That's also the path to where this is going: eventually you just *type* the crisis — 'a stablecoin de-pegs Friday at 9pm' — and the sandbox builds it for you.
>
> The patterns we showed you are the start. The sandbox is how anyone can probe the next one. **Thank you — happy to dig into any of it.**"

> Recording tip: keep the clip to **~30–40 seconds**, end on the result + Inspect view so the last thing on screen is an agent's reasoning. Have it pre-rendered — do **not** run a live Sandbox simulation on stage (LLM latency + cost + failure risk).

---

## Q&A prep — likely questions and honest answers

> **Backup slides** `SLIDES.pptx` ends with an appendix (B1–B8) you can flip to while answering:
> B1 Model finding, detail (replicated bars + discrimination) · B2 Speed: decision vs settlement ·
> B3 How agents decide (not scripted) · B4 What else we found · B5 How it's built · B6 Empirical anchors ·
> B7 Scope & limitations · B8 Central Bank detail (the Oversight probe we cut from the live walk).

**"Isn't the model difference just temperature / sampling noise — you ran each once?"**
> No — that was our first worry too, so we replicated it: **four to five runs per model on each scenario.** The bands don't overlap — Claude tops out around 67% on the false alarm, GPT never drops below 100%. A 50-point gap that survives replication isn't sampling jitter; it's a stable property of the model. *(Flip to B1.)*

**"Which model should people use, then?"**
> Honestly, none of them is a good delegate — and that's the point. GPT and Gemini run on *everything*, healthy bank or not — they protect you from a real crisis only because they cry wolf constantly. Claude is the only one that meaningfully tells a real threat from a false one, and even it panics half the time on a false alarm. So it's not "pick the safe model" — it's that *whatever* model a population converges on, its failure mode becomes everyone's failure mode at once.

**"Isn't the withdrawal fraction identical because you hard-coded it?"**
> Good eye — for the *speed* finding the fraction is capped by how fast the bank can physically pay out, so it converges either way; that's why we frame speed as a clock result, not a size one. But note the **model** finding is a different metric — *how many agents end up withdrawn* — and there the fraction is emphatically not capped or hard-coded: it ranges from 50% to 100% purely on model identity. That spread is the emergent result we didn't design in.

**"The bank is healthy in your headline finding — so 'withdrawing is wrong' is just your label. Does the bank ever actually fail, or is that baked in?"**
> Two separate things, and neither is a label. First, solvency is real money: in our *true-crisis* presets Bank A recovers only **55 cents on the dollar**, so anyone who holds takes a genuine **45% loss** at the end — principal actually disappears, and we score holding as the mistake there. The headline finding deliberately uses the *opposite* case — a **fully solvent** bank whose assets back every deposit — precisely so that *any* withdrawal is the wrong call, which is what isolates the model's panic from a real threat. Second, "solvent" doesn't mean "nothing can break": Bank A holds only about **42% in liquid reserves**, so a fast enough run drains them and the bank **suspends** before everyone's paid — that's the speed finding. Healthy means the assets are good, not that the liquidity is infinite — same as a real bank. *(The safe haven, Bank B, holds 85% reserves — fleeing there is genuinely safer.)*

**"But moving money takes time — ACH, wires, limits. Aren't you overstating the speed?"**
> Exactly right, and we're careful here: the 3× is the speed of **deciding and submitting** a withdrawal, not of cash settling. **Settlement is the same banking rail for AI and humans** — we don't claim AI moves money faster. We actually model that rail (the bank's payout capacity), and in our runs **the bank freezes before half the money ever settles** — so the binding constraint really is throughput. The point is that AI compresses the *request wave*: requests arrive in seconds instead of over a day, the bank hits its limit and suspends almost immediately, and *more* depositors get locked out. The settlement bottleneck is what makes machine-speed decisions dangerous, not a hole in the argument.

**"Humans bank online now — they're not slow. Is your human baseline fair?"**
> Fair challenge. We're *not* modeling branches or travel time — there's none of that in the sim. Our human-speed setting is a **90-second deliberation delay** plus lower continuous monitoring, standing in for the real human friction: you have to *notice*, hesitate, second-guess, and you're not watching at 3am. SVB ran entirely online and still took most of a day for exactly that reason. AI delegates remove the *noticing and hesitating*, not the *clicking*. If anything 90 seconds is generous to humans — the gap is conservative.

**"You only ran 12 agents / n=1 on some of these."**
> Correct, and we don't hide it — the Findings page labels the single-pair probes as probes. We're characterizing *mechanisms*, not estimating population statistics. The claim is "this behavior is reproducible in this setup," not "this is the real-world rate."

**"Why only three findings?"**
> Because those three are the ones we can defend cleanly from the data, and a judge should leave remembering them — not skim ten. We ran plenty more (credibility sweeps, peer-visibility, population diversity, confidence calibration, an AI-vs-rule-based regulator). Happy to talk through any of them, but we kept the page to what holds up.

**"Did you test a central bank / regulator?"** *(this was a finding; we moved it to Q&A)*
> Yes. Same false-alarm cascade, two regulators: a **rule-based** one fires a blanket guarantee at a fixed withdrawal threshold; an **AI-powered** one reads the bank's actual state first. The AI saw reserves were healthy and that *zero* agents had withdrawn yet, and chose to do nothing — correctly; the rule-based one fired blindly. But it's a **single pair of runs — a probe, not a statistic.** The robust point isn't "AI regulators are smarter" — it's that the cascade window is *seconds*, so any human-paced response is too slow regardless. *(Flip to B8.)*

**"How do you know the agents aren't just doing what you told them?"**
> The cost function is qualitative — "losing principal is catastrophic, a fee is minor" — never a numeric threshold. We deliberately don't tell them when to run. In the Inspect view you can see two agents of the *same* archetype reach opposite conclusions from the same data. If we'd scripted it, that wouldn't happen.

**"Did you check if the model is just overconfident?"**
> Yes — we pooled every final decision and the agents were just as confident when they were wrong (fleeing a healthy bank) as when they were right. So you can't use the model's own confidence as a safety tripwire. It's not on the Findings page, but the data's there.

**"Why these models? Why OpenRouter?"**
> OpenRouter lets us swap the underlying model without touching anything else — that's exactly how we ran the headline finding: same personas, same feed, six different models. We tested Claude, GPT, Gemini, Grok, Mistral, and DeepSeek. Two others — Qwen and a ByteDance model — we *excluded*, and we're upfront about why: they can't reliably emit a structured decision through the tool interface, so they default to "hold." A zero from them is a plumbing failure, not calm behavior — counting it would be dishonest. Gemini's a heavy reasoner that needed a bigger token budget to finish its decision; once we gave it that, it participated cleanly.

**"Can we actually try it, or is it a fixed demo?"**
> It's fully interactive — that's the **Sandbox** page you saw in the recording. You build agents in plain English, set the bank's health and population mix, write the rumor, optionally add a regulator or a counter-signal, name it, and run it live. Every run is saved so you can reload it.

**"What's v2?"**
> A textbox: type any stress scenario in plain English — "a stablecoin de-pegs Friday at 9pm" — and the sandbox configures the agents and information environment automatically. The architecture's already built for it — the Sandbox is the manual version of exactly that; scenarios are config objects.

**"How would you make the agent population realistic — scale this up to a real one?"** *(if a judge probes the closing "infrastructure" vision)*
> Two inputs. A firm rolling out delegate agents could calibrate the population mix from real data on its customers — surveys of risk appetite at cold start, then actual account behavior once agents are live. And critically, our headline finding says the *model* matters as much as the personas — so the other input is the real distribution of *which* models people delegate to, because that's where the systemic risk concentrates. Two honest caveats: stated risk appetite in a survey isn't the same as behavior under stress, and even calibrated, this stays a characterization tool, not a forecaster — the claim is still "in this configured population, agents do X." It makes the sandbox more representative; it doesn't turn it into a prediction of a specific real run.

---

## Demo-day failure drills

- **Dashboard won't load / crashes:** the slides carry the story alone — Slides 3→5→6 cover setup, anchor, number; the Sandbox recording (Slide 8) still plays independently. Talk to them.
- **Trimming to the 5:00 floor:** Hook (slide 1–2) → one Inspect agent → **Model finding** → SVB slide → takeaway → ~20s Sandbox recording. Drop the Speed and Language findings and the second agent. Keep a demo in it (the live Inspect agent already counts; still end on the short recording as insurance). **Never cut the Model finding — it's the headline.**
- **Sandbox recording won't play:** describe it in one sentence — "the whole thing runs on a sandbox where you configure any scenario in plain English" — land the v2 line, and go to thank-you. The required product demo is already satisfied by the live Inspect walk, so this is the flourish, not the core.
- **Judge wants to see a live run:** Presets → Run new simulation tab → AI speed → ~30–90s. Narrate the persona setup while it runs. Only do this if you have buffer time and network. (Do **not** run the Sandbox live — more controls, more to go wrong.)
- **For the Central Bank topic** (now in Q&A, not the live walk), the Findings page keeps the Oversight section in the **"More experiments" expander** at the bottom — it loads the `sweep_false_045` central-bank runs, the pair where the AI regulator chose *do nothing* and the rule-based one fired blindly. (The `rumor_high` CB runs don't show that contrast, so don't substitute them.)
- **For the Model finding**, the Findings page computes the bars live from the `modelcmp_*` runs (4–5 reps each). If a judge wants the exact numbers, they're in the chart captions and backup slide B1.
