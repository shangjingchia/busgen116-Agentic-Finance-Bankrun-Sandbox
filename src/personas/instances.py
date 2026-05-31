"""
Canonical agent instances: 12 agents, 3 per archetype.

Each instance pairs archetype-level cost functions and trust profiles with
instance-specific demographics, background, and a starting portfolio. The
``background_narrative`` is where specificity lives — concrete numbers, dates,
obligations — so the LLM has texture to ground its reasoning in.

Portfolio keys: "<bank_id>:<asset_type>". Bank IDs match the standard scenario:
  bank_a — the bank under rumor (tight reserve ratio)
  bank_b — the safe-haven bank (healthy reserve ratio)

Three agents per archetype means persona-level heterogeneity is tested across
slightly varied circumstances within each type, not just across types.
"""

from __future__ import annotations

from src.core.agent import Agent, AgentState, OutcomeLedger
from src.personas.archetypes import (
    ARCHETYPE_AGGRESSIVE_TRADER,
    ARCHETYPE_CAUTIOUS_RETIREE,
    ARCHETYPE_GIG_WORKER,
    ARCHETYPE_INSTITUTIONAL_TREASURER,
    make_aggressive_trader,
    make_cautious_retiree,
    make_gig_worker,
    make_institutional_treasurer,
)


def _wrap_agent(*, agent_id: str, persona, portfolio: dict) -> Agent:
    starting_wealth = sum(portfolio.values())
    return Agent(
        agent_id=agent_id,
        persona=persona,
        portfolio=portfolio,
        subscriptions=["news_feed", "social_feed"],
        state=AgentState.ACTIVE,
        outcome_ledger=OutcomeLedger(
            agent_id=agent_id,
            principal_starting_value=starting_wealth,
            principal_current_value=starting_wealth,
        ),
    )


# ===========================================================================
# Cautious retirees (3)
# ===========================================================================


def make_margaret_chen() -> Agent:
    """Margaret Chen, 67, retired teacher.

    $50k 12-month CD at Bank A (4.8% APY, 3% early withdrawal penalty, 8 months
    left on the term). $12k checking at Bank B. Total $62k.
    Lives on SS + small pension; the CD interest covers the gap.
    """
    persona = make_cautious_retiree(
        name="CD Saver",
        age=67,
        income_annual=34_000,
        dependents=0,
        background_narrative=(
            "Margaret Chen taught elementary school for 40 years in Sacramento, "
            "retiring at 66. Her husband passed in 2019; her daughter lives two "
            "hours away. She lives frugally, drives a paid-off Camry, and has "
            "been building her CD ladder since 2015. The $50k 12-month CD at "
            "Bank A pays 4.8% and carries a 3% early-withdrawal penalty with "
            "8 months still on the term. Her greatest financial fear is "
            "outliving her money."
        ),
    )
    return _wrap_agent(
        agent_id="agent_margaret_chen",
        persona=persona,
        portfolio={
            "bank_a:deposit": 50_000.0,
            "bank_b:deposit": 12_000.0,
        },
    )


def make_robert_petersen() -> Agent:
    """Robert Petersen, 71, retired mail carrier.

    $42k 18-month CD at Bank A (2.5% early-withdrawal penalty, 9 months
    remaining). $9k checking at Bank B. Total $51k.
    One dependent: adult son with a cognitive disability.
    """
    persona = make_cautious_retiree(
        name="Dependent Retiree",
        age=71,
        income_annual=29_000,
        dependents=1,
        background_narrative=(
            "Robert Petersen spent 38 years as a rural mail carrier in Ohio, "
            "retiring at 63. His wife passed four years ago. His adult son "
            "Danny has a cognitive disability and lives in a group home that "
            "Robert supplements with $400 a month — money that comes directly "
            "from his CD interest. The $42k 18-month CD at Bank A carries a "
            "2.5% early-withdrawal penalty with 9 months left on the term. "
            "Robert tracks his finances in a paper ledger he keeps on the "
            "kitchen counter and has not logged into online banking in three years."
        ),
    )
    return _wrap_agent(
        agent_id="agent_robert_petersen",
        persona=persona,
        portfolio={
            "bank_a:deposit": 42_000.0,
            "bank_b:deposit": 9_000.0,
        },
    )


def make_linda_vo() -> Agent:
    """Linda Vo, 69, retired paralegal.

    $25k high-yield savings at Bank A (no lock-in penalty). $18k at Bank B.
    Total $43k. Part-time legal consulting adds $14k/year.
    Slightly more financially sophisticated than the other retirees.
    """
    persona = make_cautious_retiree(
        name="Savvy Retiree",
        age=69,
        income_annual=48_000,
        dependents=0,
        financial_sophistication_score=0.55,
        background_narrative=(
            "Linda Vo worked as a paralegal at a law firm in San Jose for "
            "30 years, retiring at 67. She still takes on part-time contract "
            "work for two former clients. Unlike most retirees, she reads the "
            "Wall Street Journal on weekends and has a small brokerage account "
            "with about $12k in index funds. The $25k at Bank A is in a "
            "high-yield savings account with no early-withdrawal penalty — "
            "she specifically avoided CDs because she wanted the liquidity. "
            "She is not easily spooked but takes credible financial news seriously."
        ),
    )
    return _wrap_agent(
        agent_id="agent_linda_vo",
        persona=persona,
        portfolio={
            "bank_a:deposit": 25_000.0,
            "bank_b:deposit": 18_000.0,
        },
    )


# ===========================================================================
# Aggressive traders (3)
# ===========================================================================


def make_derek_walsh() -> Agent:
    """Derek Walsh, 28, senior software engineer at a fintech startup.

    $20k at Bank A (rotation cash, waiting for an equities entry point).
    $5k checking at Bank B. Total $25k in scope; ~$80k in equities elsewhere.
    """
    persona = make_aggressive_trader(
        name="Fintech Engineer",
        age=28,
        income_annual=145_000,
        dependents=0,
        background_narrative=(
            "Derek Walsh is a senior engineer at a mid-stage fintech in San "
            "Francisco, four years into his second startup. He maxes his 401k, "
            "holds about $80k in equities, and parks excess cash in short-term "
            "deposits while he waits for entry points. He follows financial "
            "Twitter daily and considers himself a contrarian — he has called "
            "two market bottoms correctly and one badly. The $20k at Bank A is "
            "rotation cash, not core savings."
        ),
    )
    return _wrap_agent(
        agent_id="agent_derek_walsh",
        persona=persona,
        portfolio={
            "bank_a:deposit": 20_000.0,
            "bank_b:deposit": 5_000.0,
        },
    )


def make_aisha_obi() -> Agent:
    """Aisha Obi, 31, options trader at a prop firm in Chicago.

    $38k at Bank A (earmarked for a real estate down payment she's been
    building toward). $9k at Bank B. Total $47k in scope.
    SVB-aware; has seen a bank run play out firsthand.
    """
    persona = make_aggressive_trader(
        name="Options Trader",
        age=31,
        income_annual=210_000,
        dependents=0,
        background_narrative=(
            "Aisha Obi trades equity options at a proprietary trading firm in "
            "Chicago. She has been accumulating a real-estate down-payment fund "
            "at Bank A for 18 months — the $38k is earmarked but not locked. "
            "She was following the SVB collapse in real time and watched the "
            "withdrawal cascade unfold on Twitter before the FDIC announcement. "
            "She believes she would have moved faster than most SVB depositors "
            "and has mentally rehearsed the decision since. She has no patience "
            "for waiting when the signal is clear."
        ),
    )
    return _wrap_agent(
        agent_id="agent_aisha_obi",
        persona=persona,
        portfolio={
            "bank_a:deposit": 38_000.0,
            "bank_b:deposit": 9_000.0,
        },
    )


def make_carlos_mendez() -> Agent:
    """Carlos Mendez, 35, day trader and crypto investor.

    $15k at Bank A (cash buffer between trades). $4k at Bank B. Total $19k.
    High conviction, fast trigger, uses Bloomberg and fintwit simultaneously.
    """
    persona = make_aggressive_trader(
        name="Day Trader",
        age=35,
        income_annual=120_000,
        dependents=0,
        background_narrative=(
            "Carlos Mendez left a hedge fund analyst role two years ago to trade "
            "full-time from his apartment in Miami. He keeps $15k at Bank A as a "
            "cash buffer between equities and crypto positions — it rotates in and "
            "out in a matter of days. He has Bloomberg on one monitor and "
            "financial Twitter on another at all times. He has been caught twice "
            "acting on rumors that turned out to be wrong and once badly right; "
            "his risk tolerance for 'being early and wrong' is moderate because "
            "his other positions are more than sufficient to absorb a loss here."
        ),
    )
    return _wrap_agent(
        agent_id="agent_carlos_mendez",
        persona=persona,
        portfolio={
            "bank_a:deposit": 15_000.0,
            "bank_b:deposit": 4_000.0,
        },
    )


# ===========================================================================
# Gig workers (3)
# ===========================================================================


def make_priya_nair() -> Agent:
    """Priya Nair, 34, freelance graphic designer + delivery driver.

    $3,200 emergency-fund savings at Bank A. $400 checking at Bank B.
    Total $3,600 — her entire liquid cushion. Rent due in 9 days.
    """
    persona = make_gig_worker(
        name="Freelance Designer",
        age=34,
        income_annual=41_000,
        dependents=1,
        background_narrative=(
            "Priya Nair is a freelance graphic designer in Chicago who supplements "
            "client work with delivery driving on slow weeks. She is a single "
            "mother to an 8-year-old daughter starting third grade in the fall. "
            "Her income varies by 40% month to month. She has fought hard to "
            "build her $3,200 emergency fund at Bank A and guards it intensely. "
            "Rent is due in 9 days and totals $1,650."
        ),
    )
    return _wrap_agent(
        agent_id="agent_priya_nair",
        persona=persona,
        portfolio={
            "bank_a:deposit": 3_200.0,
            "bank_b:deposit": 400.0,
        },
    )


def make_dmitri_petrov() -> Agent:
    """Dmitri Petrov, 29, freelance web developer.

    $2,900 at Bank A (emergency fund + client retainer deposit).
    $550 at Bank B. Total $3,450.
    Sends monthly remittances to a parent in Ukraine — cash flow is tighter
    than his income suggests.
    """
    persona = make_gig_worker(
        name="Freelance Developer",
        age=29,
        income_annual=47_000,
        dependents=0,
        background_narrative=(
            "Dmitri Petrov is a freelance web developer in Portland who "
            "emigrated from Ukraine six years ago. He sends $350 per month "
            "to his mother in Kyiv, which tightens his cash flow considerably. "
            "His Bank A balance is a combination of his emergency fund and a "
            "client retainer deposit he holds on behalf of one long-term client. "
            "That retainer money is not technically his to spend, which makes "
            "any bank risk feel doubly serious. He gets financial news through "
            "a Ukrainian-language Telegram channel he trusts and Reddit."
        ),
    )
    return _wrap_agent(
        agent_id="agent_dmitri_petrov",
        persona=persona,
        portfolio={
            "bank_a:deposit": 2_900.0,
            "bank_b:deposit": 550.0,
        },
    )


def make_yolanda_hayes() -> Agent:
    """Yolanda Hayes, 42, part-time home care aide + food delivery driver.

    $1,800 at Bank A (emergency fund). $350 at Bank B. Total $2,150.
    Two dependents (teenage kids). Car payment due in 5 days.
    Most financially precarious agent in the population.
    """
    persona = make_gig_worker(
        name="Part-Time Worker",
        age=42,
        income_annual=32_000,
        dependents=2,
        background_narrative=(
            "Yolanda Hayes works part-time as a home care aide three days a "
            "week and supplements with food delivery on evenings and weekends. "
            "She is raising two teenagers largely alone after a divorce four "
            "years ago. The $1,800 at Bank A is the emergency fund she rebuilt "
            "over 14 months after it was wiped out by a medical bill. A car "
            "payment of $380 is due in 5 days and she needs her Bank A "
            "debit card to work to cover it. If her bank account were frozen "
            "even temporarily, she would miss the payment and face a late fee "
            "she cannot absorb."
        ),
    )
    return _wrap_agent(
        agent_id="agent_yolanda_hayes",
        persona=persona,
        portfolio={
            "bank_a:deposit": 1_800.0,
            "bank_b:deposit": 350.0,
        },
    )


# ===========================================================================
# Institutional treasurers (3)
# ===========================================================================


def make_james_okonkwo() -> Agent:
    """Meridian Manufacturing — 140-person manufacturing firm.

    $480k at Bank A (primary operating account). $210k at Bank B (backup).
    Payroll on the 15th totals $1.2M; supplier payments at month-end add $800k.
    """
    persona = make_institutional_treasurer(
        name="Manufacturer",
        age=45,
        income_annual=195_000,
        dependents=2,
        background_narrative=(
            "Meridian Manufacturing is a 140-person manufacturing firm whose "
            "treasury function manages $700k in operating deposits across two banks. "
            "The treasurer is CTP-certified, reports to the CFO, "
            "and has a standing agenda item at the monthly board meeting. The "
            "next payroll cycle hits in 9 days and totals $1.2M; supplier "
            "payments at month-end add another $800k. The board has given the "
            "treasurer explicit authority to move capital between approved banks at "
            "their discretion when verified information warrants it."
        ),
    )
    return _wrap_agent(
        agent_id="agent_james_okonkwo",
        persona=persona,
        portfolio={
            "bank_a:deposit": 480_000.0,
            "bank_b:deposit": 210_000.0,
        },
    )


def make_sarah_kim() -> Agent:
    """Verity Systems — 90-person Series B SaaS startup.

    $310k at Bank A (14 months of operating runway). $85k at Bank B.
    Total $395k. SVB survivor — previous banking relationship was SVB.
    The most hair-trigger of the institutional treasurers.
    """
    persona = make_institutional_treasurer(
        name="Tech Startup",
        age=38,
        income_annual=175_000,
        dependents=0,
        risk_tolerance_score=0.28,
        background_narrative=(
            "Verity Systems is a 90-person SaaS company in Austin "
            "that raised a $22M Series B eight months ago. The company's "
            "previous banking relationship was with SVB; on March 10, 2023, "
            "the finance team spent 48 hours scrambling to secure emergency "
            "payroll funding after the FDIC seizure. The VP Finance had to "
            "tell the CEO they might not make payroll. The company has since "
            "diversified across two banks and has a standing procedure to move "
            "the operating balance within hours of any verified bank-stability "
            "signal. The $310k at Bank A represents 14 months of runway at "
            "current burn rate. The VP Finance is authorized to move capital "
            "unilaterally up to $500k; anything above requires a call to the CEO."
        ),
    )
    return _wrap_agent(
        agent_id="agent_sarah_kim",
        persona=persona,
        portfolio={
            "bank_a:deposit": 310_000.0,
            "bank_b:deposit": 85_000.0,
        },
    )


def make_robert_achebe() -> Agent:
    """Cascade Health System — three-hospital regional health system.

    $590k at Bank A (operating). $260k at Bank B. Total $850k.
    Any capital movement > $100k requires CFO co-sign — most process-bound
    agent in the population. Moves huge amounts but very deliberately.
    """
    persona = make_institutional_treasurer(
        name="Hospital System",
        age=52,
        income_annual=185_000,
        dependents=2,
        risk_tolerance_score=0.40,
        financial_sophistication_score=0.90,
        background_narrative=(
            "Cascade Health System is a three-hospital regional health "
            "system employing about 800 people, managing $850k in operating "
            "deposits across two institutions. Its governance structure is "
            "strict: capital movements above $100k require CFO co-signature "
            "and a documented justification memo. This means any move "
            "takes at least 2-4 hours of internal approval. The organization "
            "has never moved faster, and board audit has commended this discipline. "
            "Payroll for 800 employees runs twice monthly; the next cycle "
            "is in 11 days. The controller has a direct relationship with the Bank A "
            "regional director and would contact that person before doing anything."
        ),
    )
    return _wrap_agent(
        agent_id="agent_robert_achebe",
        persona=persona,
        portfolio={
            "bank_a:deposit": 590_000.0,
            "bank_b:deposit": 260_000.0,
        },
    )


# ===========================================================================
# Convenience accessors
# ===========================================================================

_CANONICAL_BUILDERS = {
    ARCHETYPE_CAUTIOUS_RETIREE: make_margaret_chen,
    ARCHETYPE_AGGRESSIVE_TRADER: make_derek_walsh,
    ARCHETYPE_GIG_WORKER: make_priya_nair,
    ARCHETYPE_INSTITUTIONAL_TREASURER: make_james_okonkwo,
}

_ALL_BUILDERS = [
    # Cautious retirees (3)
    make_margaret_chen,
    make_robert_petersen,
    make_linda_vo,
    # Aggressive traders (3)
    make_derek_walsh,
    make_aisha_obi,
    make_carlos_mendez,
    # Gig workers (3)
    make_priya_nair,
    make_dmitri_petrov,
    make_yolanda_hayes,
    # Institutional treasurers (3)
    make_james_okonkwo,
    make_sarah_kim,
    make_robert_achebe,
]


# Per-archetype builder lists (3 distinct named instances each), in canonical order.
_ARCHETYPE_BUILDERS = {
    ARCHETYPE_CAUTIOUS_RETIREE: [make_margaret_chen, make_robert_petersen, make_linda_vo],
    ARCHETYPE_AGGRESSIVE_TRADER: [make_derek_walsh, make_aisha_obi, make_carlos_mendez],
    ARCHETYPE_GIG_WORKER: [make_priya_nair, make_dmitri_petrov, make_yolanda_hayes],
    ARCHETYPE_INSTITUTIONAL_TREASURER: [make_james_okonkwo, make_sarah_kim, make_robert_achebe],
}


def make_agents_for_archetype(archetype: str, n: int) -> list[Agent]:
    """Return `n` agents of one archetype, cycling its 3 named instances.

    When `n` exceeds the 3 distinct instances, later agents reuse a builder but
    get a unique agent_id and a name suffix so they never collide in a run.
    Used by the Sandbox's population-mix control to build, e.g., 8 retirees.
    """
    if archetype not in _ARCHETYPE_BUILDERS:
        raise ValueError(
            f"No instances for archetype {archetype!r}. Known: {sorted(_ARCHETYPE_BUILDERS)}"
        )
    builders = _ARCHETYPE_BUILDERS[archetype]
    out: list[Agent] = []
    for i in range(max(0, n)):
        agent = builders[i % len(builders)]()
        if i >= len(builders):
            copy_n = i // len(builders) + 1
            agent.agent_id = f"{agent.agent_id}_x{copy_n}"
            agent.persona.name = f"{agent.persona.name} #{copy_n}"
        out.append(agent)
    return out


def make_canonical_agent(archetype: str) -> Agent:
    """Return one canonical agent for the given archetype."""
    if archetype not in _CANONICAL_BUILDERS:
        raise ValueError(
            f"No canonical instance for archetype {archetype!r}. "
            f"Known: {sorted(_CANONICAL_BUILDERS)}"
        )
    return _CANONICAL_BUILDERS[archetype]()


def make_all_canonical_agents() -> list[Agent]:
    """Return canonical agents for all archetypes."""
    return [
        _CANONICAL_BUILDERS[a]()
        for a in (
            ARCHETYPE_CAUTIOUS_RETIREE,
            ARCHETYPE_AGGRESSIVE_TRADER,
            ARCHETYPE_GIG_WORKER,
            ARCHETYPE_INSTITUTIONAL_TREASURER,
        )
    ]


def make_all_agents() -> list[Agent]:
    """Return all 12 agents: 3+3+3+3 distribution."""
    return [builder() for builder in _ALL_BUILDERS]
