from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .enums import (
    AggressorSide,
    AvwapConfirmation,
    EventType,
    KillSwitchLevel,
    LiquidityLevelType,
    MarketType,
    OrderSide,
    OrderStatus,
    OrderType,
    RiskDecisionStatus,
    SweepOutcome,
    SweepState,
    TimeInForce,
    TradeSide,
    Venue,
)

SCHEMA_VERSION = "1.3.0"


class ContractModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=True,
        json_encoders={Decimal: str, UUID: str},
    )


class EventEnvelope(ContractModel):
    schema_version: str = Field(default=SCHEMA_VERSION)
    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    source: str = Field(..., min_length=1, description="Service or connector that emitted event")
    venue: Venue
    market_type: MarketType
    symbol: str = Field(..., min_length=3, examples=["BTCUSDT"])
    event_time_ms: int = Field(..., ge=0)
    received_time_ms: int = Field(..., ge=0)
    trace_id: UUID = Field(default_factory=uuid4)

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, value: str) -> str:
        return value.upper().strip()

    @model_validator(mode="after")
    def received_not_before_event_by_excessive_margin(self) -> "EventEnvelope":
        # Allow small exchange/client clock drift, but protect against obviously broken timestamps.
        if self.received_time_ms + 60_000 < self.event_time_ms:
            raise ValueError("received_time_ms cannot be more than 60s before event_time_ms")
        return self


class PriceLevel(ContractModel):
    price: Decimal = Field(..., gt=Decimal("0"))
    quantity: Decimal = Field(..., ge=Decimal("0"))


class RawAggTradeEvent(EventEnvelope):
    event_type: Literal[EventType.RAW_AGG_TRADE] = EventType.RAW_AGG_TRADE
    agg_trade_id: int = Field(..., ge=0)
    price: Decimal = Field(..., gt=Decimal("0"))
    quantity: Decimal = Field(..., gt=Decimal("0"))
    first_trade_id: int = Field(..., ge=0)
    last_trade_id: int = Field(..., ge=0)
    trade_time_ms: int = Field(..., ge=0)
    is_buyer_maker: bool
    aggressor_side: AggressorSide
    raw: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_trade_ids(self) -> "RawAggTradeEvent":
        if self.last_trade_id < self.first_trade_id:
            raise ValueError("last_trade_id cannot be lower than first_trade_id")
        expected = AggressorSide.SELL if self.is_buyer_maker else AggressorSide.BUY
        if self.aggressor_side != expected:
            raise ValueError("aggressor_side must match is_buyer_maker interpretation")
        return self


class RawTradeEvent(EventEnvelope):
    event_type: Literal[EventType.RAW_TRADE] = EventType.RAW_TRADE
    trade_id: int = Field(..., ge=0)
    price: Decimal = Field(..., gt=Decimal("0"))
    quantity: Decimal = Field(..., gt=Decimal("0"))
    trade_time_ms: int = Field(..., ge=0)
    is_buyer_maker: bool
    aggressor_side: AggressorSide
    raw: dict[str, Any] | None = None


class DepthUpdateEvent(EventEnvelope):
    event_type: Literal[EventType.DEPTH_UPDATE] = EventType.DEPTH_UPDATE
    first_update_id: int = Field(..., ge=0)
    final_update_id: int = Field(..., ge=0)
    previous_final_update_id: int | None = Field(default=None, ge=0)
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    raw: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_update_ids(self) -> "DepthUpdateEvent":
        if self.final_update_id < self.first_update_id:
            raise ValueError("final_update_id cannot be lower than first_update_id")
        return self


class OrderBookSnapshotEvent(EventEnvelope):
    event_type: Literal[EventType.ORDER_BOOK_SNAPSHOT] = EventType.ORDER_BOOK_SNAPSHOT
    last_update_id: int = Field(..., ge=0)
    bids: list[PriceLevel]
    asks: list[PriceLevel]
    depth_limit: int = Field(..., ge=1)
    raw: dict[str, Any] | None = None


class BookTickerEvent(EventEnvelope):
    event_type: Literal[EventType.BOOK_TICKER] = EventType.BOOK_TICKER
    update_id: int | None = Field(default=None, ge=0)
    best_bid_price: Decimal = Field(..., gt=Decimal("0"))
    best_bid_quantity: Decimal = Field(..., ge=Decimal("0"))
    best_ask_price: Decimal = Field(..., gt=Decimal("0"))
    best_ask_quantity: Decimal = Field(..., ge=Decimal("0"))

    @model_validator(mode="after")
    def validate_crossed_market(self) -> "BookTickerEvent":
        if self.best_bid_price > self.best_ask_price:
            raise ValueError("best_bid_price cannot exceed best_ask_price")
        return self


class ReconstructedBookEvent(EventEnvelope):
    event_type: Literal[EventType.RECONSTRUCTED_BOOK] = EventType.RECONSTRUCTED_BOOK
    last_update_id: int = Field(..., ge=0)
    best_bid: PriceLevel
    best_ask: PriceLevel
    spread: Decimal = Field(..., ge=Decimal("0"))
    spread_bps: Decimal = Field(..., ge=Decimal("0"))
    bid_depth_notional_10: Decimal = Field(..., ge=Decimal("0"))
    ask_depth_notional_10: Decimal = Field(..., ge=Decimal("0"))
    book_checksum: str | None = None
    is_sequence_healthy: bool

    @model_validator(mode="after")
    def validate_book(self) -> "ReconstructedBookEvent":
        if self.best_bid.price > self.best_ask.price:
            raise ValueError("reconstructed book is crossed")
        expected_spread = self.best_ask.price - self.best_bid.price
        if self.spread != expected_spread:
            raise ValueError("spread must equal best_ask.price - best_bid.price")
        return self


class OrderFlowFeatureEvent(EventEnvelope):
    event_type: Literal[EventType.ORDER_FLOW_FEATURE] = EventType.ORDER_FLOW_FEATURE
    window_ms: int = Field(..., gt=0)
    trade_count: int = Field(..., ge=0)
    buy_volume: Decimal = Field(..., ge=Decimal("0"))
    sell_volume: Decimal = Field(..., ge=Decimal("0"))
    delta: Decimal
    normalized_delta: Decimal = Field(..., ge=Decimal("-1"), le=Decimal("1"))
    cumulative_volume_delta: Decimal
    queue_imbalance_l1: Decimal | None = Field(default=None, ge=Decimal("-1"), le=Decimal("1"))
    queue_imbalance_l5: Decimal | None = Field(default=None, ge=Decimal("-1"), le=Decimal("1"))
    queue_imbalance_l10: Decimal | None = Field(default=None, ge=Decimal("-1"), le=Decimal("1"))
    ofi_l1: Decimal | None = None
    ofi_l5: Decimal | None = None
    absorption_ratio: Decimal | None = Field(default=None, ge=Decimal("0"))
    depth_depletion_bid: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    depth_depletion_ask: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    depth_replenishment_bid: Decimal | None = Field(default=None, ge=Decimal("0"))
    depth_replenishment_ask: Decimal | None = Field(default=None, ge=Decimal("0"))

    @model_validator(mode="after")
    def validate_delta(self) -> "OrderFlowFeatureEvent":
        if self.delta != self.buy_volume - self.sell_volume:
            raise ValueError("delta must equal buy_volume - sell_volume")
        total = self.buy_volume + self.sell_volume
        if total > 0:
            expected = self.delta / total
            # Decimal exactness can vary if upstream rounding was applied; allow tiny tolerance.
            if abs(expected - self.normalized_delta) > Decimal("0.00000001"):
                raise ValueError("normalized_delta must equal delta / total_volume")
        return self


class LiquidityLevelEvent(EventEnvelope):
    event_type: Literal[EventType.LIQUIDITY_LEVEL] = EventType.LIQUIDITY_LEVEL
    level_id: UUID = Field(default_factory=uuid4)
    level_type: LiquidityLevelType
    price: Decimal = Field(..., gt=Decimal("0"))
    zone_low: Decimal = Field(..., gt=Decimal("0"))
    zone_high: Decimal = Field(..., gt=Decimal("0"))
    quality_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    touches: int = Field(..., ge=0)
    first_seen_ms: int = Field(..., ge=0)
    last_seen_ms: int = Field(..., ge=0)
    is_active: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_zone(self) -> "LiquidityLevelEvent":
        if self.zone_low > self.zone_high:
            raise ValueError("zone_low cannot be greater than zone_high")
        if not (self.zone_low <= self.price <= self.zone_high):
            raise ValueError("price must lie inside liquidity zone")
        return self


class LiquiditySweepEvent(EventEnvelope):
    event_type: Literal[EventType.LIQUIDITY_SWEEP] = EventType.LIQUIDITY_SWEEP
    sweep_id: UUID = Field(default_factory=uuid4)
    level_id: UUID
    state: SweepState
    outcome: SweepOutcome = SweepOutcome.UNRESOLVED
    level_price: Decimal = Field(..., gt=Decimal("0"))
    sweep_extreme_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    penetration_ticks: Decimal | None = Field(default=None, ge=Decimal("0"))
    penetration_atr: Decimal | None = Field(default=None, ge=Decimal("0"))
    reclaim_time_ms: int | None = Field(default=None, ge=0)
    liquidity_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    order_flow_score: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    avwap_score: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("1"))
    notes: str | None = None


class AnchoredVwapEvent(EventEnvelope):
    event_type: Literal[EventType.ANCHORED_VWAP] = EventType.ANCHORED_VWAP
    avwap_id: UUID = Field(default_factory=uuid4)
    anchor_name: str = Field(..., min_length=1)
    anchor_type: str = Field(default="custom", min_length=1)
    anchor_time_ms: int = Field(..., ge=0)
    anchor_price: Decimal = Field(..., gt=Decimal("0"))
    avwap: Decimal = Field(..., gt=Decimal("0"))
    slope: Decimal
    upper_band_1: Decimal | None = Field(default=None, gt=Decimal("0"))
    lower_band_1: Decimal | None = Field(default=None, gt=Decimal("0"))
    band_z_score: Decimal | None = None
    distance_from_price_bps: Decimal
    confirmation: AvwapConfirmation
    confirmation_score: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), le=Decimal("1"))
    is_reclaim: bool = False
    is_failure: bool = False
    sweep_id: UUID | None = None

    @model_validator(mode="after")
    def validate_bands(self) -> "AnchoredVwapEvent":
        if self.upper_band_1 is not None and self.upper_band_1 < self.avwap:
            raise ValueError("upper_band_1 cannot be below avwap")
        if self.lower_band_1 is not None and self.lower_band_1 > self.avwap:
            raise ValueError("lower_band_1 cannot be above avwap")
        return self


class SignalEvent(EventEnvelope):
    event_type: Literal[EventType.SIGNAL] = EventType.SIGNAL
    signal_id: UUID = Field(default_factory=uuid4)
    strategy_id: str = Field(..., min_length=1)
    sweep_id: UUID | None = None
    side: TradeSide
    outcome: SweepOutcome
    entry_candidate: Decimal = Field(..., gt=Decimal("0"))
    stop: Decimal = Field(..., gt=Decimal("0"))
    target_1: Decimal = Field(..., gt=Decimal("0"))
    target_2: Decimal | None = Field(default=None, gt=Decimal("0"))
    liquidity_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    order_flow_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    avwap_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    regime_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    execution_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    final_score: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    expected_net_return_bps: Decimal
    expires_at_ms: int = Field(..., ge=0)
    feature_snapshot_id: UUID
    rationale: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_directional_stop(self) -> "SignalEvent":
        if self.side == TradeSide.LONG and self.stop >= self.entry_candidate:
            raise ValueError("long signal stop must be below entry_candidate")
        if self.side == TradeSide.SHORT and self.stop <= self.entry_candidate:
            raise ValueError("short signal stop must be above entry_candidate")
        return self


class RiskDecisionEvent(EventEnvelope):
    event_type: Literal[EventType.RISK_DECISION] = EventType.RISK_DECISION
    risk_snapshot_id: UUID = Field(default_factory=uuid4)
    signal_id: UUID
    status: RiskDecisionStatus
    approved_quantity: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    max_loss_quote: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    account_equity_quote: Decimal = Field(..., gt=Decimal("0"))
    risk_fraction: Decimal = Field(..., ge=Decimal("0"), le=Decimal("1"))
    rejection_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_rejection_reasons(self) -> "RiskDecisionEvent":
        if self.status == RiskDecisionStatus.REJECTED and not self.rejection_reasons:
            raise ValueError("rejected risk decisions require at least one rejection reason")
        return self


class ExecutionOrderEvent(EventEnvelope):
    event_type: Literal[EventType.EXECUTION_ORDER] = EventType.EXECUTION_ORDER
    order_id: UUID = Field(default_factory=uuid4)
    client_order_id: str = Field(..., min_length=8)
    signal_id: UUID
    risk_snapshot_id: UUID
    side: OrderSide
    order_type: OrderType
    time_in_force: TimeInForce
    status: OrderStatus
    quantity: Decimal = Field(..., gt=Decimal("0"))
    limit_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    stop_price: Decimal | None = Field(default=None, gt=Decimal("0"))
    reduce_only: bool = False
    venue_order_id: str | None = None

    @model_validator(mode="after")
    def validate_limit_order_price(self) -> "ExecutionOrderEvent":
        if self.order_type in {OrderType.LIMIT, OrderType.MARKETABLE_LIMIT} and self.limit_price is None:
            raise ValueError("limit_price is required for limit and marketable_limit orders")
        return self


class ExecutionFillEvent(EventEnvelope):
    event_type: Literal[EventType.EXECUTION_FILL] = EventType.EXECUTION_FILL
    fill_id: UUID = Field(default_factory=uuid4)
    order_id: UUID
    client_order_id: str
    venue_order_id: str | None = None
    side: OrderSide
    fill_price: Decimal = Field(..., gt=Decimal("0"))
    fill_quantity: Decimal = Field(..., gt=Decimal("0"))
    fee_asset: str | None = None
    fee_amount: Decimal = Field(default=Decimal("0"), ge=Decimal("0"))
    is_maker: bool | None = None
    liquidity_tag: str | None = None


class KillSwitchEvent(EventEnvelope):
    event_type: Literal[EventType.KILL_SWITCH] = EventType.KILL_SWITCH
    level: KillSwitchLevel
    is_active: bool
    reason: str = Field(..., min_length=1)
    triggered_by: str = Field(..., min_length=1)
    applies_to_strategy_id: str | None = None
    applies_to_symbol: str | None = None


_EVENT_MODELS = [
    RawAggTradeEvent,
    RawTradeEvent,
    DepthUpdateEvent,
    OrderBookSnapshotEvent,
    BookTickerEvent,
    ReconstructedBookEvent,
    OrderFlowFeatureEvent,
    LiquidityLevelEvent,
    LiquiditySweepEvent,
    AnchoredVwapEvent,
    SignalEvent,
    RiskDecisionEvent,
    ExecutionOrderEvent,
    ExecutionFillEvent,
    KillSwitchEvent,
]

EVENT_MODEL_REGISTRY: dict[str, type[EventEnvelope]] = {cls.__name__: cls for cls in _EVENT_MODELS}
EVENT_TYPE_MODEL_REGISTRY: dict[str, type[EventEnvelope]] = {str(cls.model_fields["event_type"].default.value): cls for cls in _EVENT_MODELS}


def model_for_event_type(event_type: str) -> type[EventEnvelope]:
    try:
        return EVENT_TYPE_MODEL_REGISTRY[event_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported event_type: {event_type}") from exc
