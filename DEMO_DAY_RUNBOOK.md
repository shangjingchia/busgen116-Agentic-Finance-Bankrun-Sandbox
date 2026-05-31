# Demo-Day Runbook — AI Bank Run Sandbox

**Read this top-to-bottom the night before, then again 15 minutes before you present.**
This is everything you need to run the live demo **without Claude Code**. Companion files:
`PRESENTATION_SCRIPT_TIGHT.md` (what to say — the ~6:15 delivery script), `PRESENTATION_SCRIPT.md` (full version + Q&A answers), `SLIDES.pptx` (the deck), and your **Sandbox screen recording**.

## Format & logistics (from the organizers)
- **Length: 5–7 minutes.** The script targets ~6:15. Practice with a timer; if you're over 7:00, use the cut levers in the script.
- **A product demo is required** (live or pre-recorded). You have both — the live dashboard walk *and* the Sandbox recording. **Having the recording ready is non-negotiable**: it satisfies the requirement even if the live dashboard fails.
- **Slides are optional.** Yours bookend the demo — upload `SLIDES.pptx` (PowerPoint): 8 main slides + an appendix (B1–B8) for Q&A.
- **Judges:** a GSB community member + an industry professional — smart generalists. Lead with the idea and the one number; skip jargon.
- **Q&A** runs in the transitions between groups — keep the script's Q&A answers warm.
- **Canvas:** upload your materials (slides + recording) to the new assignment the **night before**, not in the room.

> **The single most important fact:** the demo runs off **pre-saved runs** — no internet, no API key, no LLM calls needed for the core walkthrough. The dashboard reads JSON files from the `runs/` folder. Don't let "the wifi is bad" panic you; the main demo doesn't touch the network.

---

## 0. The 60-second version (if you only read one box)

1. Open a terminal in the project folder.
2. `.\.venv\Scripts\Activate.ps1` then `streamlit run src/dashboard/app.py`
3. Browser opens at **http://localhost:8501**.
4. **Presets → 📂 Load saved run → "Strong rumor · Bank healthy · AI speed" → Load and view →**
5. Talk through **Inspect** (click agents, read reasoning) → **Findings** (scroll the 3 findings) → **Slides 5–7** → **play your Sandbox recording** (Slide 8) → thank you.
6. If anything breaks, the slides + the memorized numbers in §6 carry the whole talk.

---

## 1. The night before — checklist

Do these the evening before, not on the morning of.

- [ ] **Laptop charged** + charger packed. Bring it to ~100%.
- [ ] **Project folder present** and you know its path (e.g. `C:\Users\HP\agent-bankrun`).
- [ ] **Dashboard launches clean** — run the launch steps in §2 and confirm the page loads.
- [ ] **Saved runs exist** — in the dashboard, Presets → Load saved run shows a dropdown with options (not an empty "No saved runs" message). Confirm **"Strong rumor · Bank healthy · AI speed"** is selectable.
- [ ] **Findings page renders** with 3 findings + charts (Speed, Language, Oversight). If charts are blank, see §7.
- [ ] **Slides open** — open `SLIDES.pptx` in PowerPoint, start the slideshow (`F5`). Arrow keys move slides. 8 main slides + B1–B8 appendix for Q&A.
- [ ] **Screen recording made and queued** — see §5. This is the closing beat AND your required-demo insurance; record it in advance.
- [ ] **Materials uploaded to Canvas** — slides (`SLIDES.pptx`) + the Sandbox recording, to the new assignment. Do this tonight.
- [ ] **Timed a full run-through** — aim for ~6:15; must be inside 5–7 min. If over 7:00, use the script's cut levers.
- [ ] **Numbers memorized** — §6. Insurance if the screen dies.
- [ ] **Close other apps** — Slack, email, notifications off. Put the OS in Do-Not-Disturb / presentation mode.
- [ ] **Know your display setup** — HDMI/USB-C adapter, mirror vs extend. If extending, decide which screen shows the dashboard vs your notes.

---

## 2. Launching the dashboard (Windows PowerShell)

Open **PowerShell**, then navigate to the project and launch:

```powershell
cd C:\Users\HP\agent-bankrun
.\.venv\Scripts\Activate.ps1
streamlit run src/dashboard/app.py
```

- The prompt should now show `(.venv)`. A browser tab opens automatically at **http://localhost:8501**. If it doesn't, open that URL manually.
- **Leave this PowerShell window open** for the whole talk — closing it kills the dashboard.

**If `Activate.ps1` is blocked** (red "running scripts is disabled" error), run this once in the same window, then retry:

```powershell
Set-ExecutionPolicy -Scope Process -Bypass
```

**If activation still won't work**, skip the venv and launch directly:

```powershell
.\.venv\Scripts\streamlit.exe run src/dashboard/app.py
```

**If `streamlit` isn't found at all**, install dependencies once (needs internet):

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

Then relaunch with the command above.

---

## 3. Pre-flight (do this 10–15 min before you go on)

- [ ] Dashboard up at localhost:8501; **Presets** page showing.
- [ ] Load **"Strong rumor · Bank healthy · AI speed"** once now, click into **Inspect**, confirm an agent's reasoning text appears. Then click **Findings**, scroll once to confirm charts draw. (Pre-warming means no surprises live.)
- [ ] Click back to **Presets** so you start clean.
- [ ] `SLIDES.pptx` open in PowerPoint on a second window/screen, on **Slide 1**, slideshow mode tested (`F5`).
- [ ] Sandbox recording file open in your media player, paused at the start.
- [ ] Phone silenced, laptop on Do-Not-Disturb, screen-sleep disabled.
- [ ] Glass of water. Breathe.

> Optional: bump the browser zoom to ~110–125% (`Ctrl` `+`) so the back row can read the agent reasoning and the big headline numbers.

---

## 4. The click path (the spine of the talk)

Full narration is in `PRESENTATION_SCRIPT.md`. This is just the operational sequence so you never get lost.

| # | Surface | Action |
|---|---------|--------|
| 1 | **Slides 1–3** | Hook → the shift → what the sandbox is (~90s). |
| 2 | **Presets → Load saved run** | Select **"Strong rumor · Bank healthy · AI speed"** → **Load and view →**. Lands on Inspect. |
| 3 | **Inspect — top strip** | Point at the big headline stats. Note 🔴/🟢 = whether the rumor was actually true. *(Here it's a FALSE alarm — bank was fine — yet they ran.)* |
| 4 | **Inspect — agent row** | Click an agent in the **top row**; the reasoning appears directly below. Read part of it aloud. Then click a **Cautious Retiree** — show the different *voice*. |
| 5 | **Findings** | Scroll slowly through the **3 findings**: Speed → Language → Oversight. Each has a big number + an honest caveat. (The Central Bank contrast loads automatically.) |
| 6 | **Slides 4–5** | SVB anchor ($42B/day) → the 3× number. |
| 7 | **Slide 6** | Why it matters (the 3 lessons). |
| 8 | **Slide 7 + recording** | "It isn't a fixed demo —" → **play the Sandbox recording** → thank you. |

Navigation reminders:
- Switch pages using the **left sidebar** (Presets / Inspect / Findings / Sandbox).
- The dashboard remembers the loaded run across pages — load once, inspect and re-inspect freely.

---

## 5. The Sandbox screen recording (make this in advance)

You're showing a **pre-recorded** clip, not driving the Sandbox live (live = LLM latency + cost + failure risk on stage). Record it on a day when you have internet and OpenRouter credits.

### What you need to record live (needs `.env` API key + internet)
The Sandbox makes real LLM calls. Confirm your key works first: launch the dashboard, go to **Sandbox**, and do one throwaway run. If it completes, you're good to record.

### Recording steps
1. Start your screen recorder (Windows: **Xbox Game Bar**, `Win` + `G` → record; or OBS / your tool of choice). Record just the browser window.
2. Dashboard → **Sandbox** page.
3. **Name the scenario** at the top (e.g. *"Healthy bank · charged rumour · all retirees"*) — so it's clearly a deliberate build.
4. Quickly show the controls (don't dwell): build/select an agent, set **bank health**, set the **population mix** (e.g. crank retirees up), pick/write the **rumour**, optionally flip on the **counter-signal** and/or **Central Bank**.
5. Click **▶ Run Sandbox**. Let it complete (~30–90s — you'll **trim this wait out** in editing).
6. When it finishes, click **→ Inspect agent reasoning** and end the recording on an agent's reasoning on screen.
7. **Edit to ~30–40 seconds**: cut the LLM wait, keep the config sweep + the result + one reasoning panel. End on reasoning.

### Quality bar
- Final clip **≤ 40s**, no dead air.
- Last frame = an agent's verbatim reasoning (mirrors the live Inspect moment).
- Export as MP4. Put it somewhere you can open instantly on the day.

---

## 6. Numbers to memorize (insurance if the screen fails)

If the dashboard dies, you can deliver the entire talk from the slides + these. All are "**in our simulation**" claims — never "in reality."

- **Headline:** AI delegation reached **50% withdrawn ~3× faster** than human speed. (~**5 seconds** vs ~**15 seconds**.) Consistent across every scenario.
- **The lock-out twist:** at AI speed the bank froze so fast that only **5 of 12** depositors got cash, vs **11 of 12** at human speed. Faster ≠ more out — it locks people out.
- **Language:** same rumor, only the wording changed. **Soft** wording → **31%** of deposits drained, **bank stayed open**. **Charged** wording → **93%** drained, **bank suspended in ~8–9 seconds**. All three first-moved at the **same instant**.
- **Oversight:** in the false-alarm cascade (**10 of 12** ran), the **AI regulator chose to do nothing** (correctly — reserves healthy, nobody had actually withdrawn yet); the **rule-based one fired a blanket guarantee regardless**. Both only worked because they ran at machine speed — the window is **seconds**, human regulators take hours/days.
- **Empirical anchor:** SVB, March 2023 — **$42 billion withdrawn in a single day**, fastest run in modern history; its depositors were all networked startups watching the same feeds. AI delegation recreates that correlation by default.
- **Scope honesty:** 12 agents, simplified mechanics, a controlled probe — not a forecast.

---

## 7. Troubleshooting & failure drills

**Dashboard won't start / browser shows nothing**
- Confirm the PowerShell window is still running `streamlit` (no error, no closed window).
- Try the URL manually: http://localhost:8501
- Port busy? Launch on another port: `streamlit run src/dashboard/app.py --server.port 8502` then open http://localhost:8502
- Still dead → **present from slides + §6 numbers.** You lose nothing essential; the story is in the slides.

**Findings charts are blank**
- Plotly may be missing: `.\.venv\Scripts\python.exe -m pip install plotly` then reload the page. (Numbers still show even without charts.)

**Dropdown says "No saved runs"**
- You're likely in the wrong folder. Confirm you launched from the project root and a `runs\` folder with `.json` files exists there.

**A page errors out mid-demo**
- Use the sidebar to switch to another page and back, or press **R** / the "Rerun" prompt. Worst case, reload the browser tab — the dashboard reloads in a couple seconds.

**Sandbox recording won't play**
- Describe it in one line — "the whole thing runs on a sandbox where you configure any scenario in plain English" — land the v2 "just type the crisis" line, and go to thank-you. It's the flourish, not the core.

**Trimming to the 5:00 floor (5 min is the minimum, not an emergency)**
- Slides 1–2 → one Inspect agent → the Speed finding → SVB slide → the 3 lessons → ~20s of the Sandbox recording. Skip findings 2–3 and the second agent. Keep a demo in it — never drop the recording entirely (it's the required demo).

---

## 8. Do NOT do these on stage

- **Don't run a live Sandbox simulation.** Use the recording. (Live = 30–90s of latency, real cost, and the most ways to fail.)
- **Don't run a live "Run new simulation"** unless you have time *and* solid internet *and* you've decided to — it costs credits and can stall on the network.
- **Don't claim real-world predictions.** Every number is "in our simulation." Judges reward the honesty; overclaiming invites a kill-shot question.
- **Don't substitute the `rumor_high` Central Bank runs** for the Oversight finding — only the `sweep_false_045` pair shows the "AI does nothing / rule fires blindly" contrast, and the Findings page already loads the right ones.
- **Don't close the PowerShell window** until the talk is over.

---

## 9. After the talk
- Stop the screen recorder if it's still running.
- `Ctrl` + `C` in the PowerShell window to stop the dashboard (or just close the window).
- Keep the laptop awake until Q&A is fully done — judges may ask you to pull something back up.
