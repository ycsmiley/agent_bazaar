"""Quote matching — buyer-side algorithm that picks the winning Quote.

Score formula (higher is better):

    score = (confidence * success_rate) / price_per_atomic

Ties are broken by faster `estimated_delivery_ms`. Quotes that violate the
RFQ's `min_reputation_score` or `max_usdc_atomic` are filtered out before
scoring — these are hard constraints, not soft penalties.
"""

from __future__ import annotations

from dataclasses import dataclass

from schemas.quote import QuoteMessage
from schemas.rfq import RFQMessage


@dataclass(frozen=True)
class ScoredQuote:
    quote: QuoteMessage
    score: float
    reason: str


def _violates_hard_constraints(rfq: RFQMessage, q: QuoteMessage) -> str | None:
    if q.quote_price_atomic > rfq.budget.max_usdc_atomic:
        return f"price {q.quote_price_atomic} > budget {rfq.budget.max_usdc_atomic}"
    if q.erc8004_reputation.success_rate < rfq.constraints.min_reputation_score:
        return (
            f"reputation {q.erc8004_reputation.success_rate:.3f} < "
            f"min {rfq.constraints.min_reputation_score:.3f}"
        )
    return None


def score_quote(rfq: RFQMessage, q: QuoteMessage) -> float:
    return (
        q.confidence_score
        * max(q.erc8004_reputation.success_rate, 0.01)
        / q.quote_price_atomic
    )


def rank_quotes(rfq: RFQMessage, quotes: list[QuoteMessage]) -> list[ScoredQuote]:
    """Return all quotes sorted best-first, annotated with the reason any
    losing quote was scored lower — useful in the demo UI for explaining
    why the winner won.
    """
    eligible: list[ScoredQuote] = []
    rejected: list[ScoredQuote] = []
    for q in quotes:
        violation = _violates_hard_constraints(rfq, q)
        if violation is not None:
            rejected.append(ScoredQuote(q, float("-inf"), f"rejected: {violation}"))
            continue
        eligible.append(ScoredQuote(q, score_quote(rfq, q), "eligible"))

    eligible.sort(
        key=lambda s: (s.score, -s.quote.estimated_delivery_ms),
        reverse=True,
    )
    return eligible + rejected


def select_best(rfq: RFQMessage, quotes: list[QuoteMessage]) -> QuoteMessage | None:
    ranked = rank_quotes(rfq, quotes)
    if not ranked or ranked[0].score == float("-inf"):
        return None
    return ranked[0].quote
