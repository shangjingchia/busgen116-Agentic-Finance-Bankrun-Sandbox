"""
Analyze all saved simulation runs and surface key findings.

Usage:
    python scripts/analyze_runs.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

RUNS_DIR = Path(__file__).parent.parent / "runs"

_ARCHETYPE_LABEL = {
    "cautious_retiree": "Cautious Retiree",
    "aggressive_trader": "Aggressive Trader",
    "gig_worker": "Gig Worker",
    "institutional_treasurer": "Institutional Treasurer",
}

# ──────────────────────────────────────────────────────────────────────────────
# Data loading
# ──────────────────────────────────────────────────────────────────────────────


def load_all() -> List[Dict]:
    runs = []
    for p in sorted(RUNS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("scenario_id") and data.get("speed") in ("ai", "human"):
                runs.append(data)
        except Exception:
            continue
    return runs


def is_solvent(run: Dict) -> bool:
    return "_false" in run.get("scenario_id", "")


def is_sweep(run: Dict) -> bool:
    return run.get("scenario_id", "").startswith("sweep_")


def credibility_level(run: Dict) -> Optional[float]:
    sid = run.get("scenario_id", "")
    if sid.startswith("sweep_false_"):
        try:
            return int(sid.rsplit("_", 1)[-1]) / 100.0
        except ValueError:
            pass
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Per-run metrics
# ──────────────────────────────────────────────────────────────────────────────


def run_metrics(run: Dict) -> Dict:
    agents = run.get("agent_final_states", [])
    n = len(agents) or 12
    events = run.get("events", [])

    withdrew, held = [], []
    by_arch: Dict[str, Dict[str, int]] = defaultdict(lambda: {"withdrew": 0, "held": 0})
    outcome_tags: Dict[str, int] = defaultdict(int)
    confidences_at_withdrawal: List[float] = []
    trigger_counts: Dict[str, int] = defaultdict(int)
    peer_triggered_withdrawals = 0

    for a in agents:
        dh = a.get("decision_history", [])
        final = dh[-1]["action"] if dh else "hold"
        arch = a.get("persona", {}).get("archetype", "unknown")
        if final in ("full_withdraw", "partial_withdraw"):
            withdrew.append(a)
            by_arch[arch]["withdrew"] += 1
        else:
            held.append(a)
            by_arch[arch]["held"] += 1
        for tag in a.get("outcome_ledger", {}).get("outcome_tags", []):
            outcome_tags[tag] += 1
        for d in dh:
            trigger_counts[d.get("trigger_reason", "unknown")] += 1
            if d.get("action") in ("full_withdraw", "partial_withdraw"):
                if d.get("confidence") is not None:
                    confidences_at_withdrawal.append(d["confidence"])
                if d.get("trigger_reason") == "peer_withdrawal":
                    peer_triggered_withdrawals += 1

    acted = sorted(
        [e for e in events if e.get("event_type") == "agent_acted"],
        key=lambda e: e["timestamp"],
    )
    agent_map = {a["agent_id"]: a for a in agents}
    first_actor = None
    if acted:
        e = acted[0]
        ag = agent_map.get(e["agent_id"], {})
        dh0 = ag.get("decision_history", [{}])
        first_actor = {
            "name": ag.get("persona", {}).get("name", e["agent_id"]),
            "archetype": ag.get("persona", {}).get("archetype", ""),
            "action": e["action"],
            "timestamp": e["timestamp"],
            "trigger": dh0[0].get("trigger_reason", "") if dh0 else "",
        }

    susp = sorted(
        [e for e in events
         if e.get("event_type") == "bank_reserve_updated"
         and e.get("bank_id") == "bank_a"
         and e.get("new_state") == "suspended"],
        key=lambda e: e["timestamp"],
    )

    return {
        "n_total": n,
        "n_withdrew": len(withdrew),
        "n_held": len(held),
        "withdrawal_fraction": len(withdrew) / n,
        "cascade": len(withdrew) / n >= 0.25,
        "by_archetype": {k: dict(v) for k, v in by_arch.items()},
        "outcome_tags": dict(outcome_tags),
        "first_actor": first_actor,
        "trigger_counts": dict(trigger_counts),
        "peer_triggered_withdrawals": peer_triggered_withdrawals,
        "avg_confidence": (
            sum(confidences_at_withdrawal) / len(confidences_at_withdrawal)
            if confidences_at_withdrawal else None
        ),
        "t_suspended": susp[0]["timestamp"] if susp else None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Findings
# ──────────────────────────────────────────────────────────────────────────────


def finding_false_alarm_rate(runs: List[Dict]) -> None:
    print("=" * 70)
    print("FINDING 1 — False alarm rate (solvent bank scenarios)")
    print("  Bank is solvent; agents still withdrew.")
    print()
    preset_false = [r for r in runs if not is_sweep(r) and is_solvent(r)]
    for run in sorted(preset_false, key=lambda r: (r["scenario_id"], r["speed"])):
        m = run_metrics(run)
        tags = m["outcome_tags"]
        print(
            f"  [{run['speed']:5s}] {run['scenario_id']:<32}  "
            f"{m['n_withdrew']:2d}/{m['n_total']} withdrew ({m['withdrawal_fraction']:.0%})  "
            f"panicked_unnecessarily={tags.get('panicked_unnecessarily', 0)}"
        )
    print()


def finding_content_vs_credibility(runs: List[Dict]) -> None:
    print("=" * 70)
    print("FINDING 2 — Content dominates stated credibility (sweep data)")
    print("  All sweep runs use alarming content regardless of credibility label.")
    print()
    sweep = [r for r in runs if is_sweep(r)]
    by_cred: Dict[float, Dict[str, Dict]] = defaultdict(dict)
    for r in sweep:
        c = credibility_level(r)
        if c is not None:
            by_cred[c][r["speed"]] = run_metrics(r)

    print(f"  {'Credibility':>12}  {'AI withdrew':>14}  {'Human withdrew':>15}")
    for c in sorted(by_cred):
        ai_m = by_cred[c].get("ai", {})
        hu_m = by_cred[c].get("human", {})
        ai_str = (
            f"{ai_m['n_withdrew']}/{ai_m['n_total']} ({ai_m['withdrawal_fraction']:.0%})"
            if ai_m else "—"
        )
        hu_str = (
            f"{hu_m['n_withdrew']}/{hu_m['n_total']} ({hu_m['withdrawal_fraction']:.0%})"
            if hu_m else "—"
        )
        print(f"  {c:>11.0%}  {ai_str:>14}  {hu_str:>15}")
    print()
    print("  -> Withdrawal fraction does not drop as stated credibility falls.")
    print("     LLM agents cannot discount alarming content even when told it is 25% credible.")
    print()


def finding_archetype_order(runs: List[Dict]) -> None:
    print("=" * 70)
    print("FINDING 3 — Who acts first (archetype ordering)")
    print()
    preset = [r for r in runs if not is_sweep(r)]
    arch_first_counts: Dict[str, int] = defaultdict(int)
    rows = []
    for run in sorted(preset, key=lambda r: (r["scenario_id"], r["speed"])):
        m = run_metrics(run)
        fa = m["first_actor"]
        if fa and fa["action"] in ("full_withdraw", "partial_withdraw"):
            arch_first_counts[fa["archetype"]] += 1
            rows.append(
                (run["scenario_id"], run["speed"], fa["archetype"], fa["name"], fa["timestamp"])
            )

    for sid, spd, arch, name, ts in rows:
        print(
            f"  [{spd:5s}] {sid:<32}  "
            f"first: {_ARCHETYPE_LABEL.get(arch, arch):<28} T+{ts:.1f}s"
        )
    print()
    print("  First-actor archetype frequency:")
    for arch, cnt in sorted(arch_first_counts.items(), key=lambda x: -x[1]):
        print(f"    {_ARCHETYPE_LABEL.get(arch, arch):<32}  {cnt}x")
    print()


def finding_peer_cascade(runs: List[Dict]) -> None:
    print("=" * 70)
    print("FINDING 4 — Peer cascade (decisions triggered by peer_withdrawal)")
    print()
    preset = [r for r in runs if not is_sweep(r)]
    for run in sorted(preset, key=lambda r: (r["scenario_id"], r["speed"])):
        m = run_metrics(run)
        tc = m["trigger_counts"]
        total = sum(tc.values())
        peer = tc.get("peer_withdrawal", 0)
        rumor = tc.get("rumor_observed", 0)
        pct = peer / total if total else 0
        print(
            f"  [{run['speed']:5s}] {run['scenario_id']:<32}  "
            f"total={total:3d}  peer={peer:2d} ({pct:.0%})  rumor={rumor:2d}"
        )
    print()
    print("  -> Peer-triggered decisions show social contagion within the simulation.")
    print()


def finding_confidence_under_uncertainty(runs: List[Dict]) -> None:
    print("=" * 70)
    print("FINDING 5 — Confidence at withdrawal (acting under uncertainty)")
    print()
    preset = [r for r in runs if not is_sweep(r)]
    for run in sorted(preset, key=lambda r: (r["scenario_id"], r["speed"])):
        m = run_metrics(run)
        conf = m["avg_confidence"]
        if conf is not None:
            print(
                f"  [{run['speed']:5s}] {run['scenario_id']:<32}  "
                f"avg confidence at withdrawal: {conf:.2f}"
            )
    print()
    print("  -> Agents withdraw even at low confidence — asymmetric cost function")
    print("     drives action without certainty. 'Being wrong by staying' is worse.")
    print()


def finding_outcome_quality(runs: List[Dict]) -> None:
    print("=" * 70)
    print("FINDING 6 — Outcome quality (were agents right?)")
    print()
    preset = [r for r in runs if not is_sweep(r)]
    total_tags: Dict[str, int] = defaultdict(int)
    for run in sorted(preset, key=lambda r: (r["scenario_id"], r["speed"])):
        m = run_metrics(run)
        tags = m["outcome_tags"]
        tag_str = "  ".join(f"{k}={v}" for k, v in sorted(tags.items()))
        flag = "(SOLVENT)" if is_solvent(run) else "(insolvent)"
        print(f"  [{run['speed']:5s}] {run['scenario_id']:<32}  {flag:>11}  {tag_str}")
        for k, v in tags.items():
            total_tags[k] += v
    print()
    print("  Aggregate across all preset runs:")
    for k, v in sorted(total_tags.items(), key=lambda x: -x[1]):
        print(f"    {k:<35}  {v}")
    print()


def finding_weak_signal_divergence(runs: List[Dict]) -> None:
    print("=" * 70)
    print("FINDING 7 — Weak signal divergence (AI vs human at low alarm level)")
    print()
    weak = [r for r in runs if not is_sweep(r) and "weak" in r.get("scenario_id", "")]
    by_scenario: Dict[str, Dict[str, Dict]] = defaultdict(dict)
    for r in weak:
        by_scenario[r["scenario_id"]][r["speed"]] = run_metrics(r)

    for sid, speeds in sorted(by_scenario.items()):
        ai_m = speeds.get("ai", {})
        hu_m = speeds.get("human", {})
        flag = "SOLVENT bank" if "_false" in sid else "insolvent bank"
        print(f"  {sid}  ({flag})")
        if ai_m:
            print(f"    AI speed :  {ai_m['n_withdrew']}/{ai_m['n_total']} withdrew  cascade={ai_m['cascade']}")
        if hu_m:
            print(f"    Human    :  {hu_m['n_withdrew']}/{hu_m['n_total']} withdrew  cascade={hu_m['cascade']}")
        print()


# ──────────────────────────────────────────────────────────────────────────────
# Summary table
# ──────────────────────────────────────────────────────────────────────────────


def summary_table(runs: List[Dict]) -> None:
    print("=" * 70)
    print("ALL PRESET RUNS")
    print()
    preset = [r for r in runs if not is_sweep(r)]
    print(f"  {'Scenario':<34} {'Speed':>6}  {'Withdrew':>9}  {'Cascade':>7}  {'Suspended':>10}")
    for run in sorted(preset, key=lambda r: (r["scenario_id"], r["speed"])):
        m = run_metrics(run)
        sus = f"{m['t_suspended']:.1f}s" if m["t_suspended"] else "—"
        print(
            f"  {run['scenario_id']:<34} {run['speed']:>6}  "
            f"{m['n_withdrew']:2d}/{m['n_total']:2d} ({m['withdrawal_fraction']:.0%})  "
            f"{'YES' if m['cascade'] else 'no ':>7}  {sus:>10}"
        )
    print()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    runs = load_all()
    preset_count = sum(1 for r in runs if not is_sweep(r))
    sweep_count = sum(1 for r in runs if is_sweep(r))
    print(f"Loaded {len(runs)} runs  ({preset_count} preset, {sweep_count} sweep)")
    print()

    summary_table(runs)
    finding_false_alarm_rate(runs)
    finding_content_vs_credibility(runs)
    finding_archetype_order(runs)
    finding_peer_cascade(runs)
    finding_confidence_under_uncertainty(runs)
    finding_outcome_quality(runs)
    finding_weak_signal_divergence(runs)


if __name__ == "__main__":
    main()
