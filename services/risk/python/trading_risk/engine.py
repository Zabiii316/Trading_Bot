from __future__ import annotations

from decimal import Decimal
from math import isfinite

from trading_contracts.enums import KillSwitchLevel, RiskDecisionStatus, TradeSide
from trading_contracts.events import RiskDecisionEvent, SignalEvent

from .exposure import exposure_snapshot, projected_exposures
from .models import (
    AccountState,
    KillSwitchState,
    RiskAction,
    RiskDecisionDetail,
    RiskLimits,
    RiskRejectReason,
    RiskRequest,
)
from .sizing import round_down_to_step, safe_div


class RiskEngine:
    """Fail-closed pre-trade risk engine.

    This service is intentionally deterministic and free of I/O on the hot path.
    It accepts a SignalEvent plus account/position snapshots and returns both an
    internal detail object and a contract-valid RiskDecisionEvent.
    """

    __slots__ = ("limits",)

    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()
        self.limits.validate()

    def evaluate(self, request: RiskRequest) -> tuple[RiskDecisionDetail, RiskDecisionEvent]:
        request.account.validate()
        signal = request.signal
        reasons: list[str] = []
        reductions: list[str] = []
        diagnostics: dict[str, float | str] = {}

        side = TradeSide(signal.side)
        if side not in {TradeSide.LONG, TradeSide.SHORT}:
            reasons.append(RiskRejectReason.INVALID_SIGNAL_SIDE.value)

        if signal.signal_id in request.account.seen_signal_ids:
            reasons.append(RiskRejectReason.DUPLICATE_SIGNAL.value)

        age_ms = max(0, request.event_time_ms - signal.event_time_ms)
        diagnostics["signal_age_ms"] = float(age_ms)
        if age_ms > self.limits.max_signal_age_ms:
            reasons.append(RiskRejectReason.STALE_SIGNAL.value)
        if request.event_time_ms > signal.expires_at_ms:
            reasons.append(RiskRejectReason.SIGNAL_EXPIRED.value)

        kill_state = request.kill_switch
        if kill_state.applies_to(strategy_id=signal.strategy_id, symbol=signal.symbol):
            reasons.append(RiskRejectReason.KILL_SWITCH_ACTIVE.value)
            if kill_state.level in {KillSwitchLevel.HARD_TRADING_HALT, KillSwitchLevel.EMERGENCY_FLATTEN}:
                return self._event_for(
                    request,
                    RiskDecisionDetail(
                        action=RiskAction.HALT,
                        approved_quantity=0.0,
                        max_loss_quote=0.0,
                        risk_fraction=self.limits.risk_fraction_per_trade,
                        notional_quote=0.0,
                        leverage_after_trade=safe_div(request.account.gross_exposure_quote, request.account.equity_quote),
                        rejection_reasons=tuple(reasons),
                        diagnostics=diagnostics,
                    ),
                )

        equity = request.account.equity_quote
        if equity <= 0 or not isfinite(equity):
            reasons.append(RiskRejectReason.EQUITY_NOT_POSITIVE.value)

        if request.account.realized_pnl_today_quote <= -equity * self.limits.daily_loss_limit_fraction:
            reasons.append(RiskRejectReason.DAILY_LOSS_LIMIT.value)
        if request.account.realized_pnl_week_quote <= -equity * self.limits.weekly_loss_limit_fraction:
            reasons.append(RiskRejectReason.WEEKLY_LOSS_LIMIT.value)
        if request.account.portfolio_drawdown_quote >= equity * self.limits.portfolio_drawdown_limit_fraction:
            reasons.append(RiskRejectReason.DRAWDOWN_LIMIT.value)
        strategy_drawdown = request.account.strategy_drawdowns.get(signal.strategy_id, 0.0)
        if strategy_drawdown >= equity * self.limits.strategy_drawdown_limit_fraction:
            reasons.append(RiskRejectReason.STRATEGY_DRAWDOWN_LIMIT.value)

        entry = float(signal.entry_candidate)
        stop = float(signal.stop)
        mark = request.mark_price if request.mark_price is not None else entry
        if not isfinite(mark) or mark <= 0:
            if self.limits.fail_closed_on_unknown_price:
                reasons.append(RiskRejectReason.PRICE_OUT_OF_BOUNDS.value)
            mark = entry
        if entry <= 0 or not isfinite(entry):
            reasons.append(RiskRejectReason.PRICE_OUT_OF_BOUNDS.value)
        risk_per_unit = abs(entry - stop)
        if risk_per_unit <= 0 or not isfinite(risk_per_unit):
            reasons.append(RiskRejectReason.INVALID_STOP_DISTANCE.value)

        diagnostics["entry_price"] = entry
        diagnostics["stop_price"] = stop
        diagnostics["risk_per_unit"] = risk_per_unit
        diagnostics["equity_quote"] = equity

        if reasons:
            return self._event_for(
                request,
                RiskDecisionDetail(
                    action=RiskAction.REJECT if RiskRejectReason.KILL_SWITCH_ACTIVE.value not in reasons else RiskAction.HALT,
                    approved_quantity=0.0,
                    max_loss_quote=0.0,
                    risk_fraction=self.limits.risk_fraction_per_trade,
                    notional_quote=0.0,
                    leverage_after_trade=safe_div(request.account.gross_exposure_quote, equity),
                    rejection_reasons=tuple(reasons),
                    diagnostics=diagnostics,
                ),
            )

        risk_budget_quote = equity * self.limits.risk_fraction_per_trade
        raw_quantity = risk_budget_quote / risk_per_unit
        quantity = round_down_to_step(raw_quantity, self.limits.quantity_step)
        notional = quantity * entry
        max_order_notional = equity * self.limits.max_order_notional_fraction
        if notional > max_order_notional:
            quantity = round_down_to_step(max_order_notional / entry, self.limits.quantity_step)
            notional = quantity * entry
            reductions.append(RiskRejectReason.MAX_ORDER_NOTIONAL.value)

        current = exposure_snapshot(request.account)
        projected = projected_exposures(
            snapshot=current,
            symbol=signal.symbol,
            strategy_id=signal.strategy_id,
            side=side,
            notional_quote=notional,
            correlated_cluster=request.correlated_cluster,
        )

        caps = [
            ("gross", projected.gross_quote, equity * self.limits.max_gross_exposure_fraction, RiskRejectReason.MAX_GROSS_EXPOSURE.value),
            ("net", abs(projected.net_quote), equity * self.limits.max_net_exposure_fraction, RiskRejectReason.MAX_NET_EXPOSURE.value),
            ("symbol", projected.symbol_exposure(signal.symbol), equity * self.limits.max_symbol_exposure_fraction, RiskRejectReason.MAX_SYMBOL_EXPOSURE.value),
            ("strategy", projected.strategy_exposure(signal.strategy_id), equity * self.limits.max_strategy_exposure_fraction, RiskRejectReason.MAX_STRATEGY_EXPOSURE.value),
            ("cluster", projected.cluster_exposure(request.correlated_cluster), equity * self.limits.max_correlated_cluster_fraction, RiskRejectReason.MAX_CORRELATED_EXPOSURE.value),
        ]
        max_allowed_notional = notional
        for name, projected_value, cap, reason in caps:
            diagnostics[f"projected_{name}_exposure_quote"] = projected_value
            diagnostics[f"max_{name}_exposure_quote"] = cap
            excess = projected_value - cap
            if excess > 1e-9:
                max_allowed_notional = min(max_allowed_notional, max(0.0, notional - excess))
                reductions.append(reason)

        leverage_after = safe_div(projected.gross_quote, equity)
        diagnostics["projected_leverage"] = leverage_after
        if leverage_after > self.limits.max_leverage:
            excess_notional = projected.gross_quote - equity * self.limits.max_leverage
            max_allowed_notional = min(max_allowed_notional, max(0.0, notional - excess_notional))
            reductions.append(RiskRejectReason.MAX_LEVERAGE.value)

        if max_allowed_notional < notional:
            quantity = round_down_to_step(max_allowed_notional / entry, self.limits.quantity_step)
            notional = quantity * entry
            leverage_after = safe_div(current.gross_quote + notional, equity)

        if request.account.available_margin_quote is not None:
            required_margin = notional / self.limits.max_leverage
            required_buffer = equity * self.limits.min_margin_buffer_fraction
            diagnostics["required_margin_quote"] = required_margin
            diagnostics["available_margin_quote"] = request.account.available_margin_quote
            if request.account.available_margin_quote - required_margin < required_buffer:
                reasons.append(RiskRejectReason.MARGIN_BUFFER.value)

        if quantity <= 0 or quantity < self.limits.min_quantity:
            reasons.append(RiskRejectReason.MIN_QUANTITY.value)
        if notional < self.limits.min_notional_quote:
            reasons.append(RiskRejectReason.MIN_NOTIONAL.value)

        max_loss = quantity * risk_per_unit
        diagnostics["approved_quantity"] = quantity
        diagnostics["approved_notional_quote"] = notional
        diagnostics["max_loss_quote"] = max_loss
        diagnostics["risk_fraction_effective"] = safe_div(max_loss, equity)

        if max_loss > equity * self.limits.max_risk_fraction_per_trade + 1e-9:
            reasons.append(RiskRejectReason.INVALID_STOP_DISTANCE.value)

        if reasons:
            detail = RiskDecisionDetail(
                action=RiskAction.REJECT,
                approved_quantity=0.0,
                max_loss_quote=0.0,
                risk_fraction=self.limits.risk_fraction_per_trade,
                notional_quote=0.0,
                leverage_after_trade=safe_div(current.gross_quote, equity),
                rejection_reasons=tuple(reasons),
                reduction_reasons=tuple(reductions),
                diagnostics=diagnostics,
            )
        else:
            detail = RiskDecisionDetail(
                action=RiskAction.REDUCE_SIZE if reductions else RiskAction.APPROVE,
                approved_quantity=quantity,
                max_loss_quote=max_loss,
                risk_fraction=self.limits.risk_fraction_per_trade,
                notional_quote=notional,
                leverage_after_trade=leverage_after,
                rejection_reasons=(),
                reduction_reasons=tuple(reductions),
                diagnostics=diagnostics,
            )
        return self._event_for(request, detail)

    @staticmethod
    def _event_status(detail: RiskDecisionDetail) -> RiskDecisionStatus:
        if detail.action == RiskAction.HALT:
            return RiskDecisionStatus.HALTED
        if detail.action == RiskAction.REJECT:
            return RiskDecisionStatus.REJECTED
        if detail.action == RiskAction.REDUCE_SIZE:
            return RiskDecisionStatus.REDUCED_SIZE
        return RiskDecisionStatus.APPROVED

    def _event_for(self, request: RiskRequest, detail: RiskDecisionDetail) -> tuple[RiskDecisionDetail, RiskDecisionEvent]:
        event = RiskDecisionEvent(
            source="risk_engine",
            venue=request.signal.venue,
            market_type=request.signal.market_type,
            symbol=request.signal.symbol,
            event_time_ms=request.event_time_ms,
            received_time_ms=request.event_time_ms,
            signal_id=request.signal.signal_id,
            status=self._event_status(detail),
            approved_quantity=Decimal(str(detail.approved_quantity)),
            max_loss_quote=Decimal(str(detail.max_loss_quote)),
            account_equity_quote=Decimal(str(request.account.equity_quote)),
            risk_fraction=Decimal(str(detail.risk_fraction)),
            rejection_reasons=list(detail.rejection_reasons),
        )
        return detail, event
