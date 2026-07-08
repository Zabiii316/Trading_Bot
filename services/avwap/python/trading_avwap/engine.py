from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from math import isfinite

from trading_contracts.enums import EventType, MarketType, SweepOutcome, SweepState, Venue
from trading_contracts.events import (
    AnchoredVwapEvent,
    LiquidityLevelEvent,
    LiquiditySweepEvent,
    RawAggTradeEvent,
    RawTradeEvent,
    ReconstructedBookEvent,
)

from .models import AnchorKind, AvwapAnchor, AvwapUpdate
from .scoring import AvwapScorer, AvwapScoringConfig


@dataclass(frozen=True, slots=True)
class AvwapEngineConfig:
    source: str = "anchored-vwap-engine"
    band_sigma: float = 1.0
    min_anchor_quality: float = 0.35
    max_active_anchors_per_symbol: int = 64
    max_anchor_lifetime_ms: int = 24 * 60 * 60 * 1000
    emit_every_trade: bool = True
    session_anchor_hours_utc: tuple[int, ...] = (0, 8, 13)
    scoring: AvwapScoringConfig = AvwapScoringConfig()


class AnchoredVwapEngine:
    """Incremental AVWAP engine with structural, session and sweep anchors."""

    __slots__ = ("config", "scorer", "anchors", "_session_keys")

    def __init__(self, config: AvwapEngineConfig | None = None) -> None:
        self.config = config or AvwapEngineConfig()
        self.scorer = AvwapScorer(self.config.scoring)
        self.anchors: dict[str, list[AvwapAnchor]] = {}
        self._session_keys: set[tuple[str, int, int]] = set()

    def on_liquidity_level(self, level: LiquidityLevelEvent) -> list[AnchoredVwapEvent]:
        if not level.is_active or float(level.quality_score) < self.config.min_anchor_quality:
            return []
        anchor = AvwapAnchor.create(
            symbol=level.symbol,
            anchor_name=f"{level.level_type}:{level.price}",
            anchor_kind=AnchorKind.STRUCTURAL,
            anchor_time_ms=level.first_seen_ms,
            anchor_price=float(level.price),
            created_ms=level.event_time_ms,
        )
        self._add_anchor(anchor)
        return []

    def on_sweep(self, sweep: LiquiditySweepEvent) -> list[AnchoredVwapEvent]:
        if sweep.state not in {
            SweepState.PENETRATING_LEVEL,
            SweepState.CONSUMPTION_CONFIRMED,
            SweepState.REJECTION_CANDIDATE,
            SweepState.ACCEPTANCE_CANDIDATE,
            SweepState.ORDER_FLOW_CONFIRMED,
        }:
            return []
        anchor_price = float(sweep.sweep_extreme_price or sweep.level_price)
        existing = self._find_sweep_anchor(str(sweep.sweep_id))
        if existing is None:
            anchor = AvwapAnchor.create(
                symbol=sweep.symbol,
                anchor_name=f"sweep:{sweep.outcome}:{sweep.sweep_id}",
                anchor_kind=AnchorKind.SWEEP_EVENT,
                anchor_time_ms=sweep.event_time_ms,
                anchor_price=anchor_price,
                created_ms=sweep.event_time_ms,
                sweep_id=sweep.sweep_id,
                sweep_outcome=sweep.outcome,
            )
            self._add_anchor(anchor)
            return []
        existing.sweep_outcome = sweep.outcome
        return []

    def on_trade(self, event: RawAggTradeEvent | RawTradeEvent) -> list[AnchoredVwapEvent]:
        self._ensure_session_anchor(event)
        update = AvwapUpdate(
            symbol=event.symbol,
            event_time_ms=event.trade_time_ms,
            received_time_ms=event.received_time_ms,
            venue=str(event.venue),
            market_type=str(event.market_type),
            price=float(event.price),
            quantity=float(event.quantity),
        )
        if not isfinite(update.price) or not isfinite(update.quantity) or update.quantity <= 0:
            return []
        emitted: list[AnchoredVwapEvent] = []
        for anchor in list(self.anchors.get(event.symbol, [])):
            if self._expired(anchor, event.trade_time_ms):
                self.anchors[event.symbol].remove(anchor)
                continue
            before = anchor.avwap
            anchor.update(update)
            if before is not None and anchor.avwap is not None and self.config.emit_every_trade:
                emitted.append(self._to_event(anchor, price=update.price, event_time_ms=event.trade_time_ms, received_time_ms=event.received_time_ms, venue=event.venue, market_type=event.market_type))
        return emitted

    def on_book(self, event: ReconstructedBookEvent) -> list[AnchoredVwapEvent]:
        if not event.is_sequence_healthy:
            return []
        price = float((event.best_bid.price + event.best_ask.price) / Decimal("2"))
        emitted: list[AnchoredVwapEvent] = []
        for anchor in list(self.anchors.get(event.symbol, [])):
            if anchor.avwap is None:
                continue
            bullish = self.scorer.bias_for_outcome(anchor.sweep_outcome)
            is_reclaim, is_failure = anchor.update_side_and_flags(price, bullish)
            if anchor.anchor_kind == AnchorKind.SWEEP_EVENT and (is_reclaim or is_failure):
                emitted.append(self._to_event(anchor, price=price, event_time_ms=event.event_time_ms, received_time_ms=event.received_time_ms, venue=event.venue, market_type=event.market_type, is_reclaim=is_reclaim, is_failure=is_failure))
        return emitted

    def active_anchors(self, symbol: str | None = None) -> list[AvwapAnchor]:
        if symbol is None:
            return [anchor for anchors in self.anchors.values() for anchor in anchors]
        return list(self.anchors.get(symbol.upper(), []))

    def _add_anchor(self, anchor: AvwapAnchor) -> None:
        anchors = self.anchors.setdefault(anchor.symbol, [])
        # Avoid duplicated structural/session names at the same timestamp.
        for existing in anchors:
            if existing.anchor_name == anchor.anchor_name and existing.anchor_time_ms == anchor.anchor_time_ms:
                return
        anchors.append(anchor)
        if len(anchors) > self.config.max_active_anchors_per_symbol:
            anchors.sort(key=lambda a: (a.anchor_kind != AnchorKind.SWEEP_EVENT, a.created_ms))
            del anchors[0 : len(anchors) - self.config.max_active_anchors_per_symbol]

    def _find_sweep_anchor(self, sweep_id: str) -> AvwapAnchor | None:
        for anchors in self.anchors.values():
            for anchor in anchors:
                if str(anchor.sweep_id) == sweep_id:
                    return anchor
        return None

    def _ensure_session_anchor(self, event: RawAggTradeEvent | RawTradeEvent) -> None:
        hour_ms = 60 * 60 * 1000
        day_ms = 24 * hour_ms
        day_start = (event.trade_time_ms // day_ms) * day_ms
        hour = (event.trade_time_ms - day_start) // hour_ms
        if hour not in self.config.session_anchor_hours_utc:
            return
        key = (event.symbol, day_start, int(hour))
        if key in self._session_keys:
            return
        self._session_keys.add(key)
        self._add_anchor(
            AvwapAnchor.create(
                symbol=event.symbol,
                anchor_name=f"session_utc_{int(hour):02d}",
                anchor_kind=AnchorKind.SESSION,
                anchor_time_ms=event.trade_time_ms,
                anchor_price=float(event.price),
                created_ms=event.trade_time_ms,
            )
        )

    def _expired(self, anchor: AvwapAnchor, now_ms: int) -> bool:
        return now_ms - anchor.created_ms > self.config.max_anchor_lifetime_ms

    def _to_event(
        self,
        anchor: AvwapAnchor,
        *,
        price: float,
        event_time_ms: int,
        received_time_ms: int,
        venue: Venue | str,
        market_type: MarketType | str,
        is_reclaim: bool = False,
        is_failure: bool = False,
    ) -> AnchoredVwapEvent:
        avwap = anchor.avwap
        if avwap is None:
            raise ValueError("cannot emit AVWAP event before anchor has volume")
        sigma = anchor.sigma or 0.0
        upper = avwap + (self.config.band_sigma * sigma) if sigma > 0 else None
        lower = avwap - (self.config.band_sigma * sigma) if sigma > 0 else None
        score, confirmation, z, distance_bps = self.scorer.score(
            anchor=anchor,
            price=price,
            outcome=anchor.sweep_outcome,
            is_reclaim=is_reclaim,
            is_failure=is_failure,
        )
        return AnchoredVwapEvent(
            event_type=EventType.ANCHORED_VWAP,
            source=self.config.source,
            venue=venue,
            market_type=market_type,
            symbol=anchor.symbol,
            event_time_ms=event_time_ms,
            received_time_ms=received_time_ms,
            avwap_id=anchor.anchor_id,
            anchor_name=anchor.anchor_name,
            anchor_type=anchor.anchor_kind.value,
            anchor_time_ms=anchor.anchor_time_ms,
            anchor_price=Decimal(str(anchor.anchor_price)),
            avwap=Decimal(str(round(avwap, 12))),
            slope=Decimal(str(round(anchor.last_slope, 12))),
            upper_band_1=Decimal(str(round(upper, 12))) if upper is not None else None,
            lower_band_1=Decimal(str(round(lower, 12))) if lower is not None else None,
            band_z_score=Decimal(str(round(z, 8))) if z is not None else None,
            distance_from_price_bps=Decimal(str(round(distance_bps, 8))),
            confirmation=confirmation,
            confirmation_score=score,
            is_reclaim=is_reclaim,
            is_failure=is_failure,
            sweep_id=anchor.sweep_id,
        )
