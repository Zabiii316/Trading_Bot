from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import isfinite
from uuid import uuid4

from trading_contracts.enums import EventType, MarketType, SweepOutcome, TradeSide, Venue
from trading_contracts.events import SignalEvent

from .models import ScoreBreakdown, SignalCandidate


BULLISH_OUTCOMES = {SweepOutcome.BULLISH_REJECTION.value, SweepOutcome.BULLISH_ACCEPTANCE.value}
BEARISH_OUTCOMES = {SweepOutcome.BEARISH_REJECTION.value, SweepOutcome.BEARISH_ACCEPTANCE.value}


@dataclass(frozen=True, slots=True)
class SignalScoringConfig:
    strategy_id: str = "sweep_orderflow_avwap_v1"
    liquidity_weight: float = 0.30
    order_flow_weight: float = 0.30
    avwap_weight: float = 0.20
    regime_weight: float = 0.10
    execution_weight: float = 0.10
    min_final_score: float = 0.72
    min_liquidity_score: float = 0.60
    min_order_flow_score: float = 0.60
    min_avwap_score: float = 0.55
    min_regime_score: float = 0.50
    min_execution_score: float = 0.50
    max_spread_bps: float = 4.0
    ideal_spread_bps: float = 1.0
    min_depth_notional_10: float = 10_000.0
    assumed_fee_bps: float = 4.0
    assumed_slippage_bps: float = 1.5
    uncertainty_buffer_bps: float = 1.0
    stop_buffer_ticks: float = 3.0
    tick_size: float = 0.10
    min_reward_r_multiple: float = 1.25
    target_2_r_multiple: float = 2.0
    signal_ttl_ms: int = 60_000
    default_regime_score: float = 0.65
    stale_book_ms: int = 2_000
    stale_feature_ms: int = 5_000
    stale_avwap_ms: int = 5_000

    def normalized_weights(self) -> tuple[float, float, float, float, float]:
        total = (
            self.liquidity_weight
            + self.order_flow_weight
            + self.avwap_weight
            + self.regime_weight
            + self.execution_weight
        )
        if total <= 0:
            raise ValueError("signal scoring weights must sum to a positive value")
        return (
            self.liquidity_weight / total,
            self.order_flow_weight / total,
            self.avwap_weight / total,
            self.regime_weight / total,
            self.execution_weight / total,
        )


class RuleBasedSignalScorer:
    """Fast deterministic scorer that converts confirmed sweeps into SignalEvents."""

    __slots__ = ("config",)

    def __init__(self, config: SignalScoringConfig | None = None) -> None:
        self.config = config or SignalScoringConfig()

    def score(self, candidate: SignalCandidate) -> ScoreBreakdown:
        cfg = self.config
        rationale: list[str] = []
        rejection: list[str] = []

        side = candidate.side
        if side == TradeSide.FLAT:
            rejection.append("unsupported or unresolved sweep outcome")

        liquidity_score = self._clip01(float(candidate.sweep.liquidity_score))
        order_flow_score = self._clip01(self._order_flow_score(candidate))
        avwap_score = self._clip01(self._avwap_score(candidate))
        regime_score = self._clip01(candidate.regime.score if candidate.regime.is_tradeable else 0.0)
        execution_score = self._clip01(self._execution_score(candidate))

        if liquidity_score < cfg.min_liquidity_score:
            rejection.append(f"liquidity score below threshold: {liquidity_score:.4f}")
        if order_flow_score < cfg.min_order_flow_score:
            rejection.append(f"order-flow score below threshold: {order_flow_score:.4f}")
        if avwap_score < cfg.min_avwap_score:
            rejection.append(f"AVWAP score below threshold: {avwap_score:.4f}")
        if regime_score < cfg.min_regime_score:
            rejection.append(f"regime score below threshold: {regime_score:.4f}")
        if execution_score < cfg.min_execution_score:
            rejection.append(f"execution score below threshold: {execution_score:.4f}")
        if not candidate.regime.is_tradeable:
            rejection.append(f"regime is not tradeable: {candidate.regime.name}")

        wl, wo, wv, wr, we = cfg.normalized_weights()
        final_score = (
            wl * liquidity_score
            + wo * order_flow_score
            + wv * avwap_score
            + wr * regime_score
            + we * execution_score
        )
        final_score = self._clip01(final_score)
        if final_score < cfg.min_final_score:
            rejection.append(f"final score below threshold: {final_score:.4f}")

        expected_net_return_bps = self._expected_net_return_bps(candidate, final_score)
        if expected_net_return_bps <= 0:
            rejection.append(f"expected net return is not positive: {expected_net_return_bps:.4f} bps")

        rationale.extend(
            [
                f"outcome={candidate.sweep.outcome}",
                f"side={side.value if hasattr(side, 'value') else side}",
                f"liquidity={liquidity_score:.4f}",
                f"order_flow={order_flow_score:.4f}",
                f"avwap={avwap_score:.4f}",
                f"regime={regime_score:.4f}:{candidate.regime.name}",
                f"execution={execution_score:.4f}",
                f"final={final_score:.4f}",
                f"expected_net_return_bps={expected_net_return_bps:.4f}",
            ]
        )
        if candidate.regime.reasons:
            rationale.extend(candidate.regime.reasons)
        return ScoreBreakdown(
            liquidity_score=liquidity_score,
            order_flow_score=order_flow_score,
            avwap_score=avwap_score,
            regime_score=regime_score,
            execution_score=execution_score,
            final_score=final_score,
            expected_net_return_bps=expected_net_return_bps,
            rejection_reasons=rejection,
            rationale=rationale,
        )

    def build_signal(self, candidate: SignalCandidate, breakdown: ScoreBreakdown) -> SignalEvent:
        if breakdown.is_rejected:
            raise ValueError("cannot build SignalEvent from rejected score breakdown")
        entry, stop, target_1, target_2 = self._levels(candidate)
        feature_snapshot_id = (
            getattr(candidate.order_flow, "event_id", None)
            or getattr(candidate.avwap, "event_id", None)
            or candidate.sweep.event_id
        )
        return SignalEvent(
            event_id=uuid4(),
            event_type=EventType.SIGNAL,
            source="rule-based-signal-scorer",
            venue=Venue(candidate.sweep.venue),
            market_type=MarketType(candidate.sweep.market_type),
            symbol=candidate.sweep.symbol,
            event_time_ms=max(
                candidate.sweep.event_time_ms,
                candidate.order_flow.event_time_ms if candidate.order_flow else 0,
                candidate.avwap.event_time_ms if candidate.avwap else 0,
                candidate.execution.event_time_ms if candidate.execution else 0,
            ),
            received_time_ms=max(
                candidate.sweep.received_time_ms,
                candidate.order_flow.received_time_ms if candidate.order_flow else 0,
                candidate.avwap.received_time_ms if candidate.avwap else 0,
            ),
            strategy_id=self.config.strategy_id,
            sweep_id=candidate.sweep.sweep_id,
            side=candidate.side,
            outcome=candidate.sweep.outcome,
            entry_candidate=Decimal(str(round(entry, 8))),
            stop=Decimal(str(round(stop, 8))),
            target_1=Decimal(str(round(target_1, 8))),
            target_2=Decimal(str(round(target_2, 8))),
            liquidity_score=Decimal(str(round(breakdown.liquidity_score, 8))),
            order_flow_score=Decimal(str(round(breakdown.order_flow_score, 8))),
            avwap_score=Decimal(str(round(breakdown.avwap_score, 8))),
            regime_score=Decimal(str(round(breakdown.regime_score, 8))),
            execution_score=Decimal(str(round(breakdown.execution_score, 8))),
            final_score=Decimal(str(round(breakdown.final_score, 8))),
            expected_net_return_bps=Decimal(str(round(breakdown.expected_net_return_bps, 8))),
            expires_at_ms=max(candidate.sweep.event_time_ms, candidate.avwap.event_time_ms if candidate.avwap else candidate.sweep.event_time_ms)
            + self.config.signal_ttl_ms,
            feature_snapshot_id=feature_snapshot_id,
            rationale=breakdown.rationale,
        )

    def _order_flow_score(self, candidate: SignalCandidate) -> float:
        if candidate.sweep.order_flow_score is not None:
            base = float(candidate.sweep.order_flow_score)
        elif candidate.order_flow is None:
            return 0.0
        else:
            # Conservative fallback from the latest feature if the sweep event did
            # not already include its own order-flow score.
            feature = candidate.order_flow
            base = 0.5 + 0.5 * abs(float(feature.normalized_delta))
            if feature.absorption_ratio is not None:
                base = min(1.0, base + min(float(feature.absorption_ratio) / 100.0, 0.15))
        return base

    @staticmethod
    def _avwap_score(candidate: SignalCandidate) -> float:
        if candidate.avwap is not None:
            if candidate.avwap.is_failure:
                return 0.0
            return float(candidate.avwap.confirmation_score)
        if candidate.sweep.avwap_score is not None:
            return float(candidate.sweep.avwap_score)
        return 0.0

    def _execution_score(self, candidate: SignalCandidate) -> float:
        execution = candidate.execution
        if execution is None:
            return 0.40
        if not execution.is_sequence_healthy:
            return 0.0
        spread_score = 1.0
        if execution.spread_bps > self.config.max_spread_bps:
            spread_score = 0.0
        elif execution.spread_bps > self.config.ideal_spread_bps:
            span = self.config.max_spread_bps - self.config.ideal_spread_bps
            spread_score = max(0.0, 1.0 - ((execution.spread_bps - self.config.ideal_spread_bps) / span))
        depth = min(execution.bid_depth_notional_10, execution.ask_depth_notional_10)
        depth_score = min(1.0, depth / max(self.config.min_depth_notional_10, 1.0))
        return 0.65 * spread_score + 0.35 * depth_score

    def _expected_net_return_bps(self, candidate: SignalCandidate, final_score: float) -> float:
        entry, stop, target_1, _ = self._levels(candidate)
        if entry <= 0:
            return -999.0
        gross = abs(target_1 - entry) / entry * 10_000.0
        cost = self.config.assumed_fee_bps + self.config.assumed_slippage_bps + self.config.uncertainty_buffer_bps
        if candidate.execution is not None:
            cost += candidate.execution.spread_bps
        return (gross * final_score) - cost

    def _levels(self, candidate: SignalCandidate) -> tuple[float, float, float, float]:
        side = candidate.side
        sweep = candidate.sweep
        buffer = max(self.config.stop_buffer_ticks * self.config.tick_size, self.config.tick_size)
        if candidate.execution is not None:
            entry = candidate.execution.best_ask if side == TradeSide.LONG else candidate.execution.best_bid
        elif candidate.avwap is not None:
            entry = float(candidate.avwap.avwap)
        else:
            entry = float(sweep.level_price)

        level_price = float(sweep.level_price)
        extreme = float(sweep.sweep_extreme_price) if sweep.sweep_extreme_price is not None else level_price
        if side == TradeSide.LONG:
            stop = min(extreme, level_price) - buffer
            risk = max(entry - stop, self.config.tick_size)
            target_1 = entry + risk * self.config.min_reward_r_multiple
            target_2 = entry + risk * self.config.target_2_r_multiple
        elif side == TradeSide.SHORT:
            stop = max(extreme, level_price) + buffer
            risk = max(stop - entry, self.config.tick_size)
            target_1 = entry - risk * self.config.min_reward_r_multiple
            target_2 = entry - risk * self.config.target_2_r_multiple
        else:
            stop = entry
            target_1 = entry
            target_2 = entry
        return entry, stop, target_1, target_2

    @staticmethod
    def _clip01(value: float) -> float:
        if not isfinite(value):
            return 0.0
        return max(0.0, min(1.0, float(value)))
