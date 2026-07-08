from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from trading_contracts.enums import EventType
from trading_contracts.events import (
    BookTickerEvent,
    DepthUpdateEvent,
    EventEnvelope,
    OrderBookSnapshotEvent,
    RawAggTradeEvent,
    RawTradeEvent,
    ReconstructedBookEvent,
    OrderFlowFeatureEvent,
    LiquidityLevelEvent,
    LiquiditySweepEvent,
    AnchoredVwapEvent,
    SignalEvent,
    RiskDecisionEvent,
    KillSwitchEvent,
    ExecutionOrderEvent,
    ExecutionFillEvent,
)

from .serialization import bool_to_u8, decimal_to_str, json_dumps_str, ms_to_ch_datetime64


@dataclass(frozen=True)
class TableBatch:
    table_name: str
    rows: list[dict[str, Any]]


def _base(event: EventEnvelope) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "schema_version": event.schema_version,
        "source": event.source,
        "venue": event.venue,
        "market_type": event.market_type,
        "symbol": event.symbol,
        "event_time": ms_to_ch_datetime64(event.event_time_ms),
        "event_time_ms": event.event_time_ms,
        "received_time_ms": event.received_time_ms,
        "trace_id": str(event.trace_id),
    }


def raw_trade_row(event: RawAggTradeEvent | RawTradeEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "event_type": event.event_type,
            "trade_id": getattr(event, "trade_id", None),
            "agg_trade_id": getattr(event, "agg_trade_id", None),
            "price": decimal_to_str(event.price),
            "quantity": decimal_to_str(event.quantity),
            "first_trade_id": getattr(event, "first_trade_id", None),
            "last_trade_id": getattr(event, "last_trade_id", None),
            "trade_time_ms": event.trade_time_ms,
            "is_buyer_maker": bool_to_u8(event.is_buyer_maker),
            "aggressor_side": event.aggressor_side,
            "raw_json": json_dumps_str(event.raw or {}),
        }
    )
    return row


def depth_update_row(event: DepthUpdateEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "first_update_id": event.first_update_id,
            "final_update_id": event.final_update_id,
            "previous_final_update_id": event.previous_final_update_id,
            "bids_json": json_dumps_str(event.bids),
            "asks_json": json_dumps_str(event.asks),
            "raw_json": json_dumps_str(event.raw or {}),
        }
    )
    return row


def snapshot_row(event: OrderBookSnapshotEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "last_update_id": event.last_update_id,
            "depth_limit": event.depth_limit,
            "bids_json": json_dumps_str(event.bids),
            "asks_json": json_dumps_str(event.asks),
            "raw_json": json_dumps_str(event.raw or {}),
        }
    )
    return row


def reconstructed_book_row(event: ReconstructedBookEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "last_update_id": event.last_update_id,
            "best_bid_price": decimal_to_str(event.best_bid.price),
            "best_bid_quantity": decimal_to_str(event.best_bid.quantity),
            "best_ask_price": decimal_to_str(event.best_ask.price),
            "best_ask_quantity": decimal_to_str(event.best_ask.quantity),
            "spread": decimal_to_str(event.spread),
            "spread_bps": decimal_to_str(event.spread_bps),
            "bid_depth_notional_10": decimal_to_str(event.bid_depth_notional_10),
            "ask_depth_notional_10": decimal_to_str(event.ask_depth_notional_10),
            "book_checksum": event.book_checksum,
            "is_sequence_healthy": bool_to_u8(event.is_sequence_healthy),
        }
    )
    return row


def book_ticker_row(event: BookTickerEvent) -> dict[str, Any]:
    # Book tickers are intentionally persisted as reconstructed_books-compatible
    # lightweight snapshots only when a full reconstructed book is unavailable.
    row = _base(event)
    row.update(
        {
            "last_update_id": event.update_id or 0,
            "best_bid_price": decimal_to_str(event.best_bid_price),
            "best_bid_quantity": decimal_to_str(event.best_bid_quantity),
            "best_ask_price": decimal_to_str(event.best_ask_price),
            "best_ask_quantity": decimal_to_str(event.best_ask_quantity),
            "spread": decimal_to_str(event.best_ask_price - event.best_bid_price),
            "spread_bps": decimal_to_str(((event.best_ask_price - event.best_bid_price) / event.best_ask_price) * 10000),
            "bid_depth_notional_10": decimal_to_str(event.best_bid_price * event.best_bid_quantity),
            "ask_depth_notional_10": decimal_to_str(event.best_ask_price * event.best_ask_quantity),
            "book_checksum": None,
            "is_sequence_healthy": 1,
        }
    )
    return row


def order_flow_feature_row(event: OrderFlowFeatureEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "window_ms": event.window_ms,
            "trade_count": event.trade_count,
            "buy_volume": decimal_to_str(event.buy_volume),
            "sell_volume": decimal_to_str(event.sell_volume),
            "delta": decimal_to_str(event.delta),
            "normalized_delta": decimal_to_str(event.normalized_delta),
            "cumulative_volume_delta": decimal_to_str(event.cumulative_volume_delta),
            "queue_imbalance_l1": decimal_to_str(event.queue_imbalance_l1) if event.queue_imbalance_l1 is not None else None,
            "queue_imbalance_l5": decimal_to_str(event.queue_imbalance_l5) if event.queue_imbalance_l5 is not None else None,
            "queue_imbalance_l10": decimal_to_str(event.queue_imbalance_l10) if event.queue_imbalance_l10 is not None else None,
            "ofi_l1": decimal_to_str(event.ofi_l1) if event.ofi_l1 is not None else None,
            "ofi_l5": decimal_to_str(event.ofi_l5) if event.ofi_l5 is not None else None,
            "absorption_ratio": decimal_to_str(event.absorption_ratio) if event.absorption_ratio is not None else None,
            "depth_depletion_bid": decimal_to_str(event.depth_depletion_bid) if event.depth_depletion_bid is not None else None,
            "depth_depletion_ask": decimal_to_str(event.depth_depletion_ask) if event.depth_depletion_ask is not None else None,
            "depth_replenishment_bid": decimal_to_str(event.depth_replenishment_bid) if event.depth_replenishment_bid is not None else None,
            "depth_replenishment_ask": decimal_to_str(event.depth_replenishment_ask) if event.depth_replenishment_ask is not None else None,
        }
    )
    return row


def liquidity_level_row(event: LiquidityLevelEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "level_id": str(event.level_id),
            "level_type": event.level_type,
            "price": decimal_to_str(event.price),
            "zone_low": decimal_to_str(event.zone_low),
            "zone_high": decimal_to_str(event.zone_high),
            "quality_score": decimal_to_str(event.quality_score),
            "touches": event.touches,
            "first_seen_ms": event.first_seen_ms,
            "last_seen_ms": event.last_seen_ms,
            "is_active": bool_to_u8(event.is_active),
            "metadata_json": json_dumps_str(event.metadata),
        }
    )
    return row


def liquidity_sweep_row(event: LiquiditySweepEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "sweep_id": str(event.sweep_id),
            "level_id": str(event.level_id),
            "state": event.state,
            "outcome": event.outcome,
            "level_price": decimal_to_str(event.level_price),
            "sweep_extreme_price": decimal_to_str(event.sweep_extreme_price) if event.sweep_extreme_price is not None else None,
            "penetration_ticks": decimal_to_str(event.penetration_ticks) if event.penetration_ticks is not None else None,
            "penetration_atr": decimal_to_str(event.penetration_atr) if event.penetration_atr is not None else None,
            "reclaim_time_ms": event.reclaim_time_ms,
            "liquidity_score": decimal_to_str(event.liquidity_score),
            "order_flow_score": decimal_to_str(event.order_flow_score) if event.order_flow_score is not None else None,
            "avwap_score": decimal_to_str(event.avwap_score) if event.avwap_score is not None else None,
            "notes": event.notes,
        }
    )
    return row


def anchored_vwap_row(event: AnchoredVwapEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "avwap_id": str(event.avwap_id),
            "anchor_name": event.anchor_name,
            "anchor_type": event.anchor_type,
            "anchor_time_ms": event.anchor_time_ms,
            "anchor_price": decimal_to_str(event.anchor_price),
            "avwap": decimal_to_str(event.avwap),
            "slope": decimal_to_str(event.slope),
            "upper_band_1": decimal_to_str(event.upper_band_1) if event.upper_band_1 is not None else None,
            "lower_band_1": decimal_to_str(event.lower_band_1) if event.lower_band_1 is not None else None,
            "band_z_score": decimal_to_str(event.band_z_score) if event.band_z_score is not None else None,
            "distance_from_price_bps": decimal_to_str(event.distance_from_price_bps),
            "confirmation": event.confirmation,
            "confirmation_score": decimal_to_str(event.confirmation_score),
            "is_reclaim": bool_to_u8(event.is_reclaim),
            "is_failure": bool_to_u8(event.is_failure),
            "sweep_id": str(event.sweep_id) if event.sweep_id is not None else None,
        }
    )
    return row


def signal_event_row(event: SignalEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "signal_id": str(event.signal_id),
            "strategy_id": event.strategy_id,
            "sweep_id": str(event.sweep_id) if event.sweep_id is not None else None,
            "side": event.side,
            "outcome": event.outcome,
            "entry_candidate": decimal_to_str(event.entry_candidate),
            "stop": decimal_to_str(event.stop),
            "target_1": decimal_to_str(event.target_1),
            "target_2": decimal_to_str(event.target_2) if event.target_2 is not None else None,
            "liquidity_score": decimal_to_str(event.liquidity_score),
            "order_flow_score": decimal_to_str(event.order_flow_score),
            "avwap_score": decimal_to_str(event.avwap_score),
            "regime_score": decimal_to_str(event.regime_score),
            "execution_score": decimal_to_str(event.execution_score),
            "final_score": decimal_to_str(event.final_score),
            "expected_net_return_bps": decimal_to_str(event.expected_net_return_bps),
            "expires_at_ms": event.expires_at_ms,
            "feature_snapshot_id": str(event.feature_snapshot_id),
            "rationale_json": json_dumps_str(event.rationale),
        }
    )
    return row


def risk_decision_row(event: RiskDecisionEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "risk_snapshot_id": str(event.risk_snapshot_id),
            "signal_id": str(event.signal_id),
            "status": event.status,
            "approved_quantity": decimal_to_str(event.approved_quantity),
            "max_loss_quote": decimal_to_str(event.max_loss_quote),
            "account_equity_quote": decimal_to_str(event.account_equity_quote),
            "risk_fraction": decimal_to_str(event.risk_fraction),
            "rejection_reasons_json": json_dumps_str(event.rejection_reasons),
        }
    )
    return row


def execution_order_row(event: ExecutionOrderEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "order_id": str(event.order_id),
            "client_order_id": event.client_order_id,
            "signal_id": str(event.signal_id),
            "risk_snapshot_id": str(event.risk_snapshot_id),
            "side": event.side,
            "order_type": event.order_type,
            "time_in_force": event.time_in_force,
            "status": event.status,
            "quantity": decimal_to_str(event.quantity),
            "limit_price": decimal_to_str(event.limit_price) if event.limit_price is not None else None,
            "stop_price": decimal_to_str(event.stop_price) if event.stop_price is not None else None,
            "reduce_only": bool_to_u8(event.reduce_only),
            "venue_order_id": event.venue_order_id,
        }
    )
    return row


def execution_fill_row(event: ExecutionFillEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "fill_id": str(event.fill_id),
            "order_id": str(event.order_id),
            "client_order_id": event.client_order_id,
            "venue_order_id": event.venue_order_id,
            "side": event.side,
            "fill_price": decimal_to_str(event.fill_price),
            "fill_quantity": decimal_to_str(event.fill_quantity),
            "fee_asset": event.fee_asset,
            "fee_amount": decimal_to_str(event.fee_amount),
            "is_maker": None if event.is_maker is None else bool_to_u8(event.is_maker),
            "liquidity_tag": event.liquidity_tag,
        }
    )
    return row


def kill_switch_row(event: KillSwitchEvent) -> dict[str, Any]:
    row = _base(event)
    row.update(
        {
            "level": event.level,
            "is_active": bool_to_u8(event.is_active),
            "reason": event.reason,
            "triggered_by": event.triggered_by,
            "applies_to_strategy_id": event.applies_to_strategy_id,
            "applies_to_symbol": event.applies_to_symbol,
        }
    )
    return row


RowMapper = Callable[[Any], dict[str, Any]]

_EVENT_TABLES: dict[str, tuple[str, RowMapper]] = {
    EventType.RAW_AGG_TRADE.value: ("raw_trades", raw_trade_row),
    EventType.RAW_TRADE.value: ("raw_trades", raw_trade_row),
    EventType.DEPTH_UPDATE.value: ("raw_depth_updates", depth_update_row),
    EventType.ORDER_BOOK_SNAPSHOT.value: ("raw_order_book_snapshots", snapshot_row),
    EventType.RECONSTRUCTED_BOOK.value: ("reconstructed_books", reconstructed_book_row),
    EventType.BOOK_TICKER.value: ("reconstructed_books", book_ticker_row),
    EventType.ORDER_FLOW_FEATURE.value: ("order_flow_features", order_flow_feature_row),
    EventType.LIQUIDITY_LEVEL.value: ("liquidity_levels", liquidity_level_row),
    EventType.LIQUIDITY_SWEEP.value: ("liquidity_sweeps", liquidity_sweep_row),
    EventType.ANCHORED_VWAP.value: ("anchored_vwaps", anchored_vwap_row),
    EventType.SIGNAL.value: ("signals", signal_event_row),
    EventType.RISK_DECISION.value: ("risk_decisions", risk_decision_row),
    EventType.EXECUTION_ORDER.value: ("execution_orders", execution_order_row),
    EventType.EXECUTION_FILL.value: ("execution_fills", execution_fill_row),
    EventType.KILL_SWITCH.value: ("kill_switch_events", kill_switch_row),
}


def table_for_event(event: EventEnvelope) -> str:
    return _EVENT_TABLES[event.event_type][0]


def row_for_event(event: EventEnvelope) -> dict[str, Any]:
    try:
        _, mapper = _EVENT_TABLES[event.event_type]
    except KeyError as exc:
        raise ValueError(f"No storage mapping registered for {event.event_type}") from exc
    return mapper(event)


def group_events_for_clickhouse(events: list[EventEnvelope]) -> list[TableBatch]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        table = table_for_event(event)
        grouped.setdefault(table, []).append(row_for_event(event))
    return [TableBatch(table_name=table, rows=rows) for table, rows in grouped.items()]
