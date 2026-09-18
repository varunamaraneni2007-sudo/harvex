"""
AI Explanation Layer — wraps a completed decision result in farmer-friendly text.

The decision engine (main.py) performs all numerical calculations.  This
module's only job is to ask a language model to explain those pre-computed
numbers in plain language.  If the API key is absent or the call fails, a
deterministic fallback is generated from the same structured data so the
app always returns a useful explanation.
"""
import os
from typing import Optional

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"


def _get_api_key() -> Optional[str]:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    return key if key else None


# ── Fallback generators (deterministic, no AI) ────────────────────────────────

def _fallback_submission(optimize_resp, plans_resp) -> str:
    rec = optimize_resp.recommended
    allocs = rec.allocations

    if not allocs:
        return (
            "No viable market could be found for this produce given the current "
            "prices, transport costs, and spoilage rates."
        )

    top = allocs[0]
    market_lines = []
    for ch in allocs:
        market_lines.append(
            f"• {ch.market_name} ({ch.location}): {ch.quantity_kg} kg "
            f"@ ₹{ch.price_per_kg}/kg — net ₹{ch.net_value:,.2f}"
        )

    plan_a = plans_resp.plan_a
    plan_b = plans_resp.plan_b
    plan_c = plans_resp.plan_c

    lines = [
        f"Recommended allocation ({rec.strategy_name}):",
        *market_lines,
        f"Total net value: ₹{rec.total_net_value:,.2f}",
        "",
        f"The top market is {top.market_name} in {top.location}, offering "
        f"₹{top.price_per_kg}/kg with a transport cost of ₹{top.transport_cost:,.2f} "
        f"and an expected spoilage loss of ₹{top.spoilage_loss_value:,.2f}.",
        "",
        "Your three plans:",
        f"• Plan A ({plan_a.plan_name}): ₹{plan_a.total_net_value:,.2f} — {plan_a.plan_tradeoff}",
        f"• Plan B ({plan_b.plan_name}): ₹{plan_b.total_net_value:,.2f} — {plan_b.plan_tradeoff}",
        f"• Plan C ({plan_c.plan_name}): ₹{plan_c.total_net_value:,.2f} — {plan_c.plan_tradeoff}",
    ]
    return "\n".join(lines)


def _fallback_whatif(resp) -> str:
    delta = resp.delta_net_value
    direction = "increase" if delta >= 0 else "decrease"
    sign = "+" if delta >= 0 else ""

    lines = [
        f"Scenario: {resp.scenario_description}",
        f"Current plan net value: ₹{resp.current_plan.total_net_value:,.2f}",
        f"What-if plan net value: ₹{resp.whatif_plan.total_net_value:,.2f}",
        f"Change: {sign}₹{abs(delta):,.2f} ({direction})",
    ]

    if resp.whatif_plan.allocations:
        top = resp.whatif_plan.allocations[0]
        lines.append(
            f"Under this scenario the best option is {top.market_name} "
            f"({top.location}) with a net of ₹{top.net_value:,.2f}."
        )
    else:
        lines.append("Under this scenario no viable market remains.")

    return "\n".join(lines)


# ── AI-powered generators ─────────────────────────────────────────────────────

def _submission_prompt(data, optimize_resp, plans_resp) -> str:
    rec = optimize_resp.recommended
    alloc_lines = "\n".join(
        f"  - {ch.market_name} ({ch.location}): {ch.quantity_kg} kg, "
        f"price ₹{ch.price_per_kg}/kg, gross ₹{ch.gross_revenue}, "
        f"transport ₹{ch.transport_cost}, spoilage loss ₹{ch.spoilage_loss_value}, "
        f"net ₹{ch.net_value}"
        + (f", road distance {ch.market_name}" if hasattr(ch, 'distance_km') else "")
        for ch in rec.allocations
    )

    alt_lines = "\n".join(
        f"  - {s.strategy_name}: net ₹{s.total_net_value}"
        for s in optimize_resp.alternatives
    )

    pa, pb, pc = plans_resp.plan_a, plans_resp.plan_b, plans_resp.plan_c

    return f"""A farmer in {data.farmer_location} has {data.quantity_kg} kg of {data.quality} {data.crop}
with {data.shelf_life_days} days of shelf life, harvested on {data.harvest_date}.

The decision engine has already calculated the optimal allocation. Your job is only to explain
these pre-computed numbers in simple, friendly language a farmer can understand.

RECOMMENDED ALLOCATION ({rec.strategy_name}):
{alloc_lines}
Total: {rec.total_quantity_allocated} kg allocated, gross ₹{rec.total_gross_revenue},
transport ₹{rec.total_transport_cost}, spoilage loss ₹{rec.total_spoilage_loss_value},
net ₹{rec.total_net_value}

ALTERNATIVE STRATEGIES:
{alt_lines if alt_lines else "  None (all strategies produced the same allocation)"}

THREE PLANS:
- Plan A ({pa.plan_name}): net ₹{pa.total_net_value} — {pa.plan_tradeoff}
- Plan B ({pb.plan_name}): net ₹{pb.total_net_value} — {pb.plan_tradeoff}
- Plan C ({pc.plan_name}): net ₹{pc.total_net_value} — {pc.plan_tradeoff}

Please write a clear, friendly explanation (3–5 short paragraphs) covering:
1. Why this allocation was recommended and what markets are included
2. How transport costs and spoilage risk affected the decision
3. What the three plans mean in practical terms for the farmer
4. Any key trade-offs the farmer should be aware of

Use plain language. Do not invent or change any numbers — only explain the ones above.
Keep it under 250 words."""


def _whatif_prompt(req, resp) -> str:
    cp = resp.current_plan
    wp = resp.whatif_plan

    whatif_allocs = "\n".join(
        f"  - {ch.market_name}: {ch.quantity_kg} kg, net ₹{ch.net_value}"
        for ch in wp.allocations
    ) or "  (no viable market)"

    return f"""A farmer has {req.produce.quantity_kg} kg of {req.produce.quality} {req.produce.crop}.

The decision engine ran a what-if scenario: {resp.scenario_description}

CURRENT PLAN (no changes):
  Net value: ₹{cp.total_net_value}, markets: {", ".join(ch.market_name for ch in cp.allocations) or "none"}

WHAT-IF PLAN ({resp.scenario_description}):
{whatif_allocs}
  Net value: ₹{wp.total_net_value}

IMPACT: ₹{resp.delta_net_value:+.2f} change in net value.

Please write a short, plain-language explanation (2–3 paragraphs) of:
1. What this scenario means for the farmer
2. How it changed the recommended allocation and why
3. What the farmer should consider given this outcome

Do not invent or change any numbers — only explain the ones above. Keep it under 150 words."""


def _call_anthropic(prompt: str) -> Optional[str]:
    """Call the Anthropic API and return the text, or None on any failure."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_get_api_key())
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception:
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def generate_explanation(data, optimize_resp, plans_resp) -> str:
    """
    Return an AI explanation of the submission result, falling back to a
    deterministic summary when the API key is absent or the call fails.
    """
    if _get_api_key():
        prompt = _submission_prompt(data, optimize_resp, plans_resp)
        result = _call_anthropic(prompt)
        if result:
            return result
    return _fallback_submission(optimize_resp, plans_resp)


def generate_whatif_explanation(req, resp) -> str:
    """
    Return an AI explanation of a what-if result, falling back to a
    deterministic summary when the API key is absent or the call fails.
    """
    if _get_api_key():
        prompt = _whatif_prompt(req, resp)
        result = _call_anthropic(prompt)
        if result:
            return result
    return _fallback_whatif(resp)
