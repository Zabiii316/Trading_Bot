from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import EventType, MarketType, SweepOutcome, SweepState, Venue
from trading_contracts.events import LiquidityLevelEvent, LiquiditySweepEvent, OrderFlowFeatureEvent
from trading_features.book_view import BookView

from .models import (
    SweepContext,
    SweepDirection,
    acceptance_outcome,
    classify_level_direction,
    rejection_outcome,
)
from .scoring import SweepScorer, SweepScoringConfig


@dataclass(frozen=True, slots=True)
class SweepEngineConfig:
    source: str = "liquidity-sweep-engine"
    tick_size: float = 0.10
    atr_value: float = 100.0
    approach_ticks: float = 20.0
    min_penetration_ticks: float = 3.0
    min_penetration_atr: float = 0.001
    min_level_quality: float = 0.30
    min_consumption_score: float = 0.55
    min_resolution_score: float = 0.58
    acceptance_hold_ms: int = 2_000
    max_sweep_lifetime_ms: int = 180_000
    max_armed_lifetime_ms: int = 900_000
    emit_repeated_state_events: bool = False
    scorer: SweepScoringConfig = SweepScoringConfig()


class LiquiditySweepStateMachine:
    """Deterministic event-driven liquidity-sweep state machine.

    Hot path complexity is bounded by the number of active levels per symbol. The
    engine emits contract-valid LiquiditySweepEvent objects only when a state
    transition occurs, keeping the downstream event bus clean and replayable.
    """

    __slots__ = ("config", "scorer", "contexts", "latest_flow", "_last_state_key")

    def __init__(self, config: SweepEngineConfig | None = None) -> None:
        self.config = config or SweepEngineConfig()
        self.scorer = SweepScorer(self.config.scorer)
        self.contexts: dict[tuple[str, str], SweepContext] = {}
        self.latest_flow: dict[str, OrderFlowFeatureEvent] = {}
        self._last_state_key: dict[str, tuple[str, str]] = {}

    def on_liquidity_level(self, level: LiquidityLevelEvent, current_price: float | None = None) -> list[LiquiditySweepEvent]:
        if not level.is_active or float(level.quality_score) < self.config.min_level_quality:
            return []
        direction = classify_level_direction(level, current_price=current_price)
        key = self._key(level.symbol, str(level.level_id))
        existing = self.contexts.get(key)
        now_ms = level.event_time_ms
        if existing is None or existing.state == SweepState.EXPIRED:
            ctx = SweepContext.create(level=level, now_ms=now_ms, direction=direction)
            self.contexts[key] = ctx
            return [self._to_event(ctx, now_ms, note="level armed")]
        existing.level = level
        existing.direction = existing.direction or direction
        existing.updated_ms = now_ms
        return []

    def on_order_flow(self, feature: OrderFlowFeatureEvent) -> list[LiquiditySweepEvent]:
        self.latest_flow[feature.symbol] = feature
        emitted: list[LiquiditySweepEvent] = []
        for ctx in self._contexts_for_symbol(feature.symbol):
            ctx.last_feature = feature
            if ctx.state in {SweepState.REJECTION_CANDIDATE, SweepState.ACCEPTANCE_CANDIDATE}:
                emitted.extend(self._maybe_confirm_order_flow(ctx, feature.event_time_ms))
        return emitted

    def on_book(self, book: BookView) -> list[LiquiditySweepEvent]:
        if not book.is_sequence_healthy or book.mid_price is None:
            return []
        emitted: list[LiquiditySweepEvent] = []
        now_ms = book.event_time_ms
        price = float(book.mid_price)
        feature = self.latest_flow.get(book.symbol)
        for ctx in self._contexts_for_symbol(book.symbol):
            ctx.last_mid_price = price
            if feature is not None:
                ctx.last_feature = feature
            if ctx.direction is None:
                ctx.direction = classify_level_direction(ctx.level, current_price=price)
            if ctx.direction is None:
                continue
            if self._should_expire(ctx, now_ms):
                emitted.append(self._expire(ctx, now_ms, "sweep expired"))
                continue
            before = ctx.state
            event = self._advance_with_price(ctx, price, now_ms)
            if event is not None:
                emitted.append(event)
            if ctx.state in {SweepState.REJECTION_CANDIDATE, SweepState.ACCEPTANCE_CANDIDATE}:
                emitted.extend(self._maybe_confirm_order_flow(ctx, now_ms))
            if before != ctx.state and ctx.state == SweepState.EXPIRED:
                self.contexts.pop(self._key(ctx.level.symbol, str(ctx.level.level_id)), None)
        return emitted

    def active_contexts(self, symbol: str | None = None) -> list[SweepContext]:
        if symbol is None:
            return list(self.contexts.values())
        return self._contexts_for_symbol(symbol.upper())

    def _contexts_for_symbol(self, symbol: str) -> list[SweepContext]:
        return [ctx for (ctx_symbol, _), ctx in self.contexts.items() if ctx_symbol == symbol.upper()]

    @staticmethod
    def _key(symbol: str, level_id: str) -> tuple[str, str]:
        return (symbol.upper(), level_id)

    def _should_expire(self, ctx: SweepContext, now_ms: int) -> bool:
        if ctx.state == SweepState.LEVEL_ARMED:
            return now_ms - ctx.created_ms > self.config.max_armed_lifetime_ms
        return now_ms - ctx.created_ms > self.config.max_sweep_lifetime_ms

    def _advance_with_price(self, ctx: SweepContext, price: float, now_ms: int) -> LiquiditySweepEvent | None:
        if ctx.state == SweepState.LEVEL_ARMED and self._is_approaching(ctx, price):
            ctx.approach_time_ms = now_ms
            ctx.set_state(SweepState.APPROACHING_LEVEL, now_ms, "price approaching liquidity zone")
            return self._to_event(ctx, now_ms)
        if ctx.state in {SweepState.LEVEL_ARMED, SweepState.APPROACHING_LEVEL} and self._is_penetrating(ctx, price):
            ctx.penetration_time_ms = now_ms
            ctx.sweep_extreme_price = price
            self._set_penetration_metrics(ctx, price)
            ctx.set_state(SweepState.PENETRATING_LEVEL, now_ms, "price penetrated liquidity zone")
            return self._to_event(ctx, now_ms)
        if ctx.state == SweepState.PENETRATING_LEVEL:
            self._update_extreme(ctx, price)
            score = self.scorer.consumption_score(ctx.last_feature, ctx.direction) if ctx.direction else 0.0
            ctx.order_flow_score = score
            if score >= self.config.min_consumption_score or self._penetration_is_large_enough(ctx):
                ctx.consumption_time_ms = now_ms
                ctx.set_state(SweepState.CONSUMPTION_CONFIRMED, now_ms, "liquidity consumption confirmed")
                return self._to_event(ctx, now_ms)
        if ctx.state == SweepState.CONSUMPTION_CONFIRMED:
            self._update_extreme(ctx, price)
            if self._is_reclaimed(ctx, price):
                ctx.outcome = rejection_outcome(ctx.direction)  # type: ignore[arg-type]
                ctx.resolution_time_ms = now_ms
                ctx.set_state(SweepState.REJECTION_CANDIDATE, now_ms, "sweep reclaimed into prior range")
                return self._to_event(ctx, now_ms)
            if self._is_accepted(ctx, price, now_ms):
                ctx.outcome = acceptance_outcome(ctx.direction)  # type: ignore[arg-type]
                ctx.resolution_time_ms = now_ms
                ctx.set_state(SweepState.ACCEPTANCE_CANDIDATE, now_ms, "price accepted beyond liquidity zone")
                return self._to_event(ctx, now_ms)
        return None

    def _maybe_confirm_order_flow(self, ctx: SweepContext, now_ms: int) -> list[LiquiditySweepEvent]:
        if ctx.outcome == SweepOutcome.UNRESOLVED:
            return []
        score = self.scorer.resolution_score(ctx.last_feature, ctx.outcome)
        ctx.order_flow_score = score
        if score < self.config.min_resolution_score:
            return []
        ctx.set_state(SweepState.ORDER_FLOW_CONFIRMED, now_ms, f"order flow confirmed {ctx.outcome.value}")
        return [self._to_event(ctx, now_ms)]

    def _is_approaching(self, ctx: SweepContext, price: float) -> bool:
        approach = self.config.approach_ticks * self.config.tick_size
        if ctx.direction == SweepDirection.UPSIDE:
            return ctx.zone_low - approach <= price <= ctx.zone_high
        if ctx.direction == SweepDirection.DOWNSIDE:
            return ctx.zone_low <= price <= ctx.zone_high + approach
        return False

    def _penetration_distance(self, ctx: SweepContext, price: float) -> float:
        if ctx.direction == SweepDirection.UPSIDE:
            return max(0.0, price - ctx.zone_high)
        if ctx.direction == SweepDirection.DOWNSIDE:
            return max(0.0, ctx.zone_low - price)
        return 0.0

    def _min_penetration_distance(self) -> float:
        return max(
            self.config.min_penetration_ticks * self.config.tick_size,
            self.config.min_penetration_atr * self.config.atr_value,
        )

    def _is_penetrating(self, ctx: SweepContext, price: float) -> bool:
        return self._penetration_distance(ctx, price) >= self._min_penetration_distance()

    def _set_penetration_metrics(self, ctx: SweepContext, price: float) -> None:
        distance = self._penetration_distance(ctx, price)
        ctx.penetration_ticks = distance / max(self.config.tick_size, 1e-12)
        ctx.penetration_atr = distance / max(self.config.atr_value, 1e-12)

    def _penetration_is_large_enough(self, ctx: SweepContext) -> bool:
        return (ctx.penetration_ticks or 0.0) >= self.config.min_penetration_ticks * 2

    def _update_extreme(self, ctx: SweepContext, price: float) -> None:
        if ctx.sweep_extreme_price is None:
            ctx.sweep_extreme_price = price
        elif ctx.direction == SweepDirection.UPSIDE:
            ctx.sweep_extreme_price = max(ctx.sweep_extreme_price, price)
        elif ctx.direction == SweepDirection.DOWNSIDE:
            ctx.sweep_extreme_price = min(ctx.sweep_extreme_price, price)
        self._set_penetration_metrics(ctx, ctx.sweep_extreme_price)

    def _is_reclaimed(self, ctx: SweepContext, price: float) -> bool:
        if ctx.direction == SweepDirection.UPSIDE:
            return price < ctx.zone_high
        if ctx.direction == SweepDirection.DOWNSIDE:
            return price > ctx.zone_low
        return False

    def _is_still_beyond_zone(self, ctx: SweepContext, price: float) -> bool:
        if ctx.direction == SweepDirection.UPSIDE:
            return price > ctx.zone_high
        if ctx.direction == SweepDirection.DOWNSIDE:
            return price < ctx.zone_low
        return False

    def _is_accepted(self, ctx: SweepContext, price: float, now_ms: int) -> bool:
        if ctx.penetration_time_ms is None:
            return False
        return self._is_still_beyond_zone(ctx, price) and now_ms - ctx.penetration_time_ms >= self.config.acceptance_hold_ms

    def _expire(self, ctx: SweepContext, now_ms: int, note: str) -> LiquiditySweepEvent:
        ctx.outcome = SweepOutcome.NO_TRADE
        ctx.set_state(SweepState.EXPIRED, now_ms, note)
        return self._to_event(ctx, now_ms)

    @staticmethod
    def _decimal_or_none(value: float | None, precision: int = 12) -> Decimal | None:
        if value is None:
            return None
        return Decimal(str(round(float(value), precision)))

    def _to_event(self, ctx: SweepContext, now_ms: int, note: str | None = None) -> LiquiditySweepEvent:
        if note:
            ctx.last_notes.append(note)
        reclaim_time_ms = None
        if ctx.resolution_time_ms is not None and ctx.penetration_time_ms is not None:
            reclaim_time_ms = ctx.resolution_time_ms - ctx.penetration_time_ms
        return LiquiditySweepEvent(
            event_id=uuid4(),
            event_type=EventType.LIQUIDITY_SWEEP,
            source=self.config.source,
            venue=Venue(ctx.level.venue),
            market_type=MarketType(ctx.level.market_type),
            symbol=ctx.level.symbol,
            event_time_ms=now_ms,
            received_time_ms=now_ms,
            sweep_id=ctx.sweep_id,
            level_id=ctx.level.level_id,
            state=ctx.state,
            outcome=ctx.outcome,
            level_price=Decimal(str(ctx.level_price)),
            sweep_extreme_price=self._decimal_or_none(ctx.sweep_extreme_price),
            penetration_ticks=self._decimal_or_none(ctx.penetration_ticks),
            penetration_atr=self._decimal_or_none(ctx.penetration_atr),
            reclaim_time_ms=reclaim_time_ms,
            liquidity_score=Decimal(str(round(ctx.liquidity_score, 8))),
            order_flow_score=self._decimal_or_none(ctx.order_flow_score, precision=8),
            avwap_score=None,
            notes="; ".join(ctx.last_notes[-4:]) if ctx.last_notes else None,
        )
