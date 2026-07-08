from __future__ import annotations

from decimal import Decimal
from time import time
from typing import Iterable

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.openmetrics.exposition import CONTENT_TYPE_LATEST

from trading_contracts.enums import (
    EventType,
    KillSwitchLevel,
    OrderStatus,
    RiskDecisionStatus,
)
from trading_contracts.events import (
    AnchoredVwapEvent,
    EventEnvelope,
    ExecutionFillEvent,
    ExecutionOrderEvent,
    KillSwitchEvent,
    LiquidityLevelEvent,
    LiquiditySweepEvent,
    OrderFlowFeatureEvent,
    ReconstructedBookEvent,
    RiskDecisionEvent,
    SignalEvent,
)


def _label(value) -> str:
    return str(getattr(value, "value", value))

def _to_float(value: Decimal | int | float | None, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


class TradingMetrics:
    """Prometheus metric facade for the trading pipeline.

    The object owns a CollectorRegistry so tests and multiple local app instances do not collide
    in the global Prometheus registry. Hot-path methods are intentionally small and label sets are
    bounded to avoid high-cardinality explosions.
    """

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry(auto_describe=True)

        self.events_total = Counter(
            "trading_events_total",
            "Total normalized pipeline events observed by type, venue and symbol.",
            ("event_type", "venue", "symbol"),
            registry=self.registry,
        )
        self.event_lag_ms = Histogram(
            "trading_event_lag_ms",
            "Received-time minus exchange event-time lag in milliseconds.",
            ("event_type", "venue", "symbol"),
            buckets=(1, 5, 10, 25, 50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000),
            registry=self.registry,
        )
        self.component_up = Gauge(
            "trading_component_up",
            "Component liveness flag: 1 healthy/live, 0 unhealthy.",
            ("component",),
            registry=self.registry,
        )
        self.component_ready = Gauge(
            "trading_component_ready",
            "Component readiness flag: 1 ready, 0 not ready.",
            ("component",),
            registry=self.registry,
        )
        self.component_last_heartbeat_ms = Gauge(
            "trading_component_last_heartbeat_ms",
            "Last component heartbeat timestamp in milliseconds.",
            ("component",),
            registry=self.registry,
        )

        self.websocket_reconnects_total = Counter(
            "trading_websocket_reconnects_total",
            "WebSocket reconnect count by venue, stream and symbol.",
            ("venue", "stream", "symbol"),
            registry=self.registry,
        )
        self.websocket_messages_total = Counter(
            "trading_websocket_messages_total",
            "WebSocket message count by venue, stream and symbol.",
            ("venue", "stream", "symbol"),
            registry=self.registry,
        )
        self.websocket_decode_errors_total = Counter(
            "trading_websocket_decode_errors_total",
            "WebSocket decode errors by venue, stream and symbol.",
            ("venue", "stream", "symbol"),
            registry=self.registry,
        )

        self.orderbook_sequence_healthy = Gauge(
            "trading_orderbook_sequence_healthy",
            "Latest reconstructed book sequence health flag.",
            ("venue", "symbol"),
            registry=self.registry,
        )
        self.orderbook_spread_bps = Gauge(
            "trading_orderbook_spread_bps",
            "Latest reconstructed book spread in basis points.",
            ("venue", "symbol"),
            registry=self.registry,
        )
        self.orderbook_rebuilds_total = Counter(
            "trading_orderbook_rebuilds_total",
            "Order-book rebuild/resync count.",
            ("venue", "symbol", "reason"),
            registry=self.registry,
        )

        self.orderflow_delta = Gauge(
            "trading_orderflow_delta",
            "Latest rolling trade delta.",
            ("venue", "symbol", "window_ms"),
            registry=self.registry,
        )
        self.orderflow_cvd = Gauge(
            "trading_orderflow_cvd",
            "Latest cumulative volume delta.",
            ("venue", "symbol"),
            registry=self.registry,
        )
        self.orderflow_queue_imbalance_l1 = Gauge(
            "trading_orderflow_queue_imbalance_l1",
            "Latest L1 queue imbalance.",
            ("venue", "symbol"),
            registry=self.registry,
        )
        self.orderflow_absorption_ratio = Gauge(
            "trading_orderflow_absorption_ratio",
            "Latest absorption ratio.",
            ("venue", "symbol"),
            registry=self.registry,
        )

        self.liquidity_levels_active = Gauge(
            "trading_liquidity_levels_active",
            "Active liquidity-level count by type.",
            ("venue", "symbol", "level_type"),
            registry=self.registry,
        )
        self.liquidity_level_quality = Gauge(
            "trading_liquidity_level_quality",
            "Latest liquidity-level quality score by type.",
            ("venue", "symbol", "level_type"),
            registry=self.registry,
        )
        self.sweeps_total = Counter(
            "trading_liquidity_sweeps_total",
            "Liquidity sweep lifecycle events by state and outcome.",
            ("venue", "symbol", "state", "outcome"),
            registry=self.registry,
        )

        self.avwap_confirmation_score = Gauge(
            "trading_avwap_confirmation_score",
            "Latest AVWAP confirmation score by confirmation state.",
            ("venue", "symbol", "confirmation"),
            registry=self.registry,
        )
        self.avwap_distance_bps = Gauge(
            "trading_avwap_distance_bps",
            "Latest distance from price to AVWAP in basis points.",
            ("venue", "symbol", "anchor_type"),
            registry=self.registry,
        )

        self.signals_total = Counter(
            "trading_signals_total",
            "Generated signals by strategy and side.",
            ("venue", "symbol", "strategy_id", "side", "outcome"),
            registry=self.registry,
        )
        self.signal_final_score = Gauge(
            "trading_signal_final_score",
            "Latest final signal score.",
            ("venue", "symbol", "strategy_id", "side"),
            registry=self.registry,
        )
        self.signal_expected_net_return_bps = Gauge(
            "trading_signal_expected_net_return_bps",
            "Latest expected net return in basis points.",
            ("venue", "symbol", "strategy_id", "side"),
            registry=self.registry,
        )

        self.risk_decisions_total = Counter(
            "trading_risk_decisions_total",
            "Risk decisions by status.",
            ("venue", "symbol", "status"),
            registry=self.registry,
        )
        self.risk_rejections_total = Counter(
            "trading_risk_rejections_total",
            "Risk rejection reasons.",
            ("venue", "symbol", "reason"),
            registry=self.registry,
        )
        self.risk_approved_quantity = Gauge(
            "trading_risk_approved_quantity",
            "Latest approved order quantity from the risk engine.",
            ("venue", "symbol"),
            registry=self.registry,
        )
        self.account_equity_quote = Gauge(
            "trading_account_equity_quote",
            "Latest account equity in quote currency observed by risk engine.",
            ("venue",),
            registry=self.registry,
        )

        self.orders_total = Counter(
            "trading_execution_orders_total",
            "Execution order lifecycle events by status and side.",
            ("venue", "symbol", "status", "side"),
            registry=self.registry,
        )
        self.fills_total = Counter(
            "trading_execution_fills_total",
            "Execution fills by side and maker flag.",
            ("venue", "symbol", "side", "is_maker"),
            registry=self.registry,
        )
        self.filled_quantity = Counter(
            "trading_execution_filled_quantity_total",
            "Total filled quantity.",
            ("venue", "symbol", "side"),
            registry=self.registry,
        )
        self.fill_fee_amount = Counter(
            "trading_execution_fill_fee_amount_total",
            "Total fill fees in reported fee units.",
            ("venue", "symbol", "fee_asset"),
            registry=self.registry,
        )

        self.kill_switch_active = Gauge(
            "trading_kill_switch_active",
            "Kill-switch active flag by level, strategy and symbol.",
            ("level", "strategy_id", "symbol"),
            registry=self.registry,
        )
        self.kill_switch_events_total = Counter(
            "trading_kill_switch_events_total",
            "Kill-switch events by level and active flag.",
            ("level", "is_active", "triggered_by"),
            registry=self.registry,
        )

    def observe_event(self, event: EventEnvelope) -> None:
        labels = (_label(event.event_type), _label(event.venue), event.symbol)
        self.events_total.labels(*labels).inc()
        lag = max(0, event.received_time_ms - event.event_time_ms)
        self.event_lag_ms.labels(*labels).observe(lag)

        if isinstance(event, ReconstructedBookEvent):
            self.observe_reconstructed_book(event)
        elif isinstance(event, OrderFlowFeatureEvent):
            self.observe_order_flow(event)
        elif isinstance(event, LiquidityLevelEvent):
            self.observe_liquidity_level(event)
        elif isinstance(event, LiquiditySweepEvent):
            self.observe_sweep(event)
        elif isinstance(event, AnchoredVwapEvent):
            self.observe_avwap(event)
        elif isinstance(event, SignalEvent):
            self.observe_signal(event)
        elif isinstance(event, RiskDecisionEvent):
            self.observe_risk_decision(event)
        elif isinstance(event, ExecutionOrderEvent):
            self.observe_order(event)
        elif isinstance(event, ExecutionFillEvent):
            self.observe_fill(event)
        elif isinstance(event, KillSwitchEvent):
            self.observe_kill_switch(event)

    def observe_component(self, component: str, is_live: bool, is_ready: bool, heartbeat_ms: int | None = None) -> None:
        self.component_up.labels(component).set(1 if is_live else 0)
        self.component_ready.labels(component).set(1 if is_ready else 0)
        self.component_last_heartbeat_ms.labels(component).set(heartbeat_ms or int(time() * 1000))

    def observe_websocket_message(self, venue: str, stream: str, symbol: str) -> None:
        self.websocket_messages_total.labels(venue, stream, symbol.upper()).inc()

    def observe_websocket_reconnect(self, venue: str, stream: str, symbol: str) -> None:
        self.websocket_reconnects_total.labels(venue, stream, symbol.upper()).inc()

    def observe_websocket_decode_error(self, venue: str, stream: str, symbol: str) -> None:
        self.websocket_decode_errors_total.labels(venue, stream, symbol.upper()).inc()

    def observe_orderbook_rebuild(self, venue: str, symbol: str, reason: str) -> None:
        self.orderbook_rebuilds_total.labels(venue, symbol.upper(), reason).inc()

    def observe_reconstructed_book(self, event: ReconstructedBookEvent) -> None:
        self.orderbook_sequence_healthy.labels(_label(event.venue), event.symbol).set(1 if event.is_sequence_healthy else 0)
        self.orderbook_spread_bps.labels(_label(event.venue), event.symbol).set(_to_float(event.spread_bps))

    def observe_order_flow(self, event: OrderFlowFeatureEvent) -> None:
        window = str(event.window_ms)
        self.orderflow_delta.labels(_label(event.venue), event.symbol, window).set(_to_float(event.delta))
        self.orderflow_cvd.labels(_label(event.venue), event.symbol).set(_to_float(event.cumulative_volume_delta))
        if event.queue_imbalance_l1 is not None:
            self.orderflow_queue_imbalance_l1.labels(_label(event.venue), event.symbol).set(_to_float(event.queue_imbalance_l1))
        if event.absorption_ratio is not None:
            self.orderflow_absorption_ratio.labels(_label(event.venue), event.symbol).set(_to_float(event.absorption_ratio))

    def observe_liquidity_level(self, event: LiquidityLevelEvent) -> None:
        active_delta = 1 if event.is_active else 0
        self.liquidity_levels_active.labels(_label(event.venue), event.symbol, _label(event.level_type)).set(active_delta)
        self.liquidity_level_quality.labels(_label(event.venue), event.symbol, _label(event.level_type)).set(_to_float(event.quality_score))

    def observe_sweep(self, event: LiquiditySweepEvent) -> None:
        self.sweeps_total.labels(_label(event.venue), event.symbol, _label(event.state), _label(event.outcome)).inc()

    def observe_avwap(self, event: AnchoredVwapEvent) -> None:
        self.avwap_confirmation_score.labels(_label(event.venue), event.symbol, _label(event.confirmation)).set(_to_float(event.confirmation_score))
        self.avwap_distance_bps.labels(_label(event.venue), event.symbol, event.anchor_type).set(_to_float(event.distance_from_price_bps))

    def observe_signal(self, event: SignalEvent) -> None:
        self.signals_total.labels(_label(event.venue), event.symbol, event.strategy_id, _label(event.side), _label(event.outcome)).inc()
        self.signal_final_score.labels(_label(event.venue), event.symbol, event.strategy_id, _label(event.side)).set(_to_float(event.final_score))
        self.signal_expected_net_return_bps.labels(_label(event.venue), event.symbol, event.strategy_id, _label(event.side)).set(_to_float(event.expected_net_return_bps))

    def observe_risk_decision(self, event: RiskDecisionEvent) -> None:
        self.risk_decisions_total.labels(_label(event.venue), event.symbol, _label(event.status)).inc()
        self.risk_approved_quantity.labels(_label(event.venue), event.symbol).set(_to_float(event.approved_quantity))
        self.account_equity_quote.labels(_label(event.venue)).set(_to_float(event.account_equity_quote))
        if event.status in {RiskDecisionStatus.REJECTED, RiskDecisionStatus.HALTED}:
            for reason in event.rejection_reasons or ["unspecified"]:
                self.risk_rejections_total.labels(_label(event.venue), event.symbol, reason).inc()

    def observe_order(self, event: ExecutionOrderEvent) -> None:
        self.orders_total.labels(_label(event.venue), event.symbol, _label(event.status), _label(event.side)).inc()

    def observe_fill(self, event: ExecutionFillEvent) -> None:
        is_maker = "unknown" if event.is_maker is None else str(event.is_maker).lower()
        self.fills_total.labels(_label(event.venue), event.symbol, _label(event.side), is_maker).inc()
        self.filled_quantity.labels(_label(event.venue), event.symbol, _label(event.side)).inc(_to_float(event.fill_quantity))
        self.fill_fee_amount.labels(_label(event.venue), event.symbol, event.fee_asset or "unknown").inc(_to_float(event.fee_amount))

    def observe_kill_switch(self, event: KillSwitchEvent) -> None:
        strategy = event.applies_to_strategy_id or "all"
        symbol = event.applies_to_symbol or event.symbol or "all"
        self.kill_switch_active.labels(_label(event.level), strategy, symbol).set(1 if event.is_active else 0)
        self.kill_switch_events_total.labels(_label(event.level), str(event.is_active).lower(), event.triggered_by).inc()

    def export_text(self) -> bytes:
        return generate_latest(self.registry)

    @property
    def content_type(self) -> str:
        return CONTENT_TYPE_LATEST


def observe_many(metrics: TradingMetrics, events: Iterable[EventEnvelope]) -> int:
    count = 0
    for event in events:
        metrics.observe_event(event)
        count += 1
    return count
