from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from uuid import UUID

from trading_contracts.enums import KillSwitchLevel, TradeSide
from trading_contracts.events import SignalEvent


class RiskRejectReason(str, Enum):
    KILL_SWITCH_ACTIVE = "kill_switch_active"
    STALE_SIGNAL = "stale_signal"
    SIGNAL_EXPIRED = "signal_expired"
    INVALID_SIGNAL_SIDE = "invalid_signal_side"
    INVALID_STOP_DISTANCE = "invalid_stop_distance"
    EQUITY_NOT_POSITIVE = "equity_not_positive"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    WEEKLY_LOSS_LIMIT = "weekly_loss_limit"
    DRAWDOWN_LIMIT = "drawdown_limit"
    STRATEGY_DRAWDOWN_LIMIT = "strategy_drawdown_limit"
    MAX_GROSS_EXPOSURE = "max_gross_exposure"
    MAX_NET_EXPOSURE = "max_net_exposure"
    MAX_SYMBOL_EXPOSURE = "max_symbol_exposure"
    MAX_STRATEGY_EXPOSURE = "max_strategy_exposure"
    MAX_CORRELATED_EXPOSURE = "max_correlated_exposure"
    MAX_LEVERAGE = "max_leverage"
    MARGIN_BUFFER = "margin_buffer"
    MIN_QUANTITY = "min_quantity"
    MIN_NOTIONAL = "min_notional"
    MAX_ORDER_NOTIONAL = "max_order_notional"
    DUPLICATE_SIGNAL = "duplicate_signal"
    PRICE_OUT_OF_BOUNDS = "price_out_of_bounds"


class RiskAction(str, Enum):
    APPROVE = "approve"
    REDUCE_SIZE = "reduce_size"
    REJECT = "reject"
    HALT = "halt"


@dataclass(frozen=True, slots=True)
class RiskLimits:
    """Static limits used by the pre-trade risk engine.

    Fractions are expressed as fractions of current account equity unless the
    name explicitly says quote. These defaults are intentionally conservative
    for early paper/live deployment.
    """

    risk_fraction_per_trade: float = 0.0025
    max_risk_fraction_per_trade: float = 0.005
    max_gross_exposure_fraction: float = 2.0
    max_net_exposure_fraction: float = 1.0
    max_symbol_exposure_fraction: float = 0.5
    max_strategy_exposure_fraction: float = 0.75
    max_correlated_cluster_fraction: float = 0.75
    max_order_notional_fraction: float = 0.5
    max_leverage: float = 2.0
    min_margin_buffer_fraction: float = 0.25
    daily_loss_limit_fraction: float = 0.015
    weekly_loss_limit_fraction: float = 0.04
    portfolio_drawdown_limit_fraction: float = 0.08
    strategy_drawdown_limit_fraction: float = 0.06
    min_quantity: float = 0.0
    quantity_step: float = 0.0
    min_notional_quote: float = 0.0
    max_signal_age_ms: int = 60_000
    fail_closed_on_unknown_price: bool = True

    def validate(self) -> None:
        numeric_fields = {
            "risk_fraction_per_trade": self.risk_fraction_per_trade,
            "max_risk_fraction_per_trade": self.max_risk_fraction_per_trade,
            "max_gross_exposure_fraction": self.max_gross_exposure_fraction,
            "max_net_exposure_fraction": self.max_net_exposure_fraction,
            "max_symbol_exposure_fraction": self.max_symbol_exposure_fraction,
            "max_strategy_exposure_fraction": self.max_strategy_exposure_fraction,
            "max_correlated_cluster_fraction": self.max_correlated_cluster_fraction,
            "max_order_notional_fraction": self.max_order_notional_fraction,
            "max_leverage": self.max_leverage,
            "min_margin_buffer_fraction": self.min_margin_buffer_fraction,
            "daily_loss_limit_fraction": self.daily_loss_limit_fraction,
            "weekly_loss_limit_fraction": self.weekly_loss_limit_fraction,
            "portfolio_drawdown_limit_fraction": self.portfolio_drawdown_limit_fraction,
            "strategy_drawdown_limit_fraction": self.strategy_drawdown_limit_fraction,
            "min_quantity": self.min_quantity,
            "quantity_step": self.quantity_step,
            "min_notional_quote": self.min_notional_quote,
        }
        for name, value in numeric_fields.items():
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.risk_fraction_per_trade <= 0:
            raise ValueError("risk_fraction_per_trade must be positive")
        if self.max_risk_fraction_per_trade <= 0:
            raise ValueError("max_risk_fraction_per_trade must be positive")
        if self.risk_fraction_per_trade > self.max_risk_fraction_per_trade:
            raise ValueError("risk_fraction_per_trade cannot exceed max_risk_fraction_per_trade")
        if self.max_leverage <= 0:
            raise ValueError("max_leverage must be positive")
        if self.max_signal_age_ms < 0:
            raise ValueError("max_signal_age_ms cannot be negative")


@dataclass(frozen=True, slots=True)
class PositionSnapshot:
    symbol: str
    side: TradeSide
    quantity: float
    entry_price: float
    mark_price: float
    strategy_id: str
    signal_id: UUID | None = None
    correlated_cluster: str | None = None

    @property
    def notional_quote(self) -> float:
        return abs(self.quantity * self.mark_price)

    @property
    def signed_notional_quote(self) -> float:
        sign = 1.0 if self.side == TradeSide.LONG else -1.0
        return sign * self.notional_quote


@dataclass(frozen=True, slots=True)
class AccountState:
    equity_quote: float
    balance_quote: float | None = None
    available_margin_quote: float | None = None
    peak_equity_quote: float | None = None
    realized_pnl_today_quote: float = 0.0
    realized_pnl_week_quote: float = 0.0
    open_positions: tuple[PositionSnapshot, ...] = ()
    strategy_drawdowns: dict[str, float] = field(default_factory=dict)
    seen_signal_ids: frozenset[UUID] = frozenset()

    def validate(self) -> None:
        if not isfinite(self.equity_quote) or self.equity_quote <= 0:
            raise ValueError("equity_quote must be positive")
        if self.available_margin_quote is not None and self.available_margin_quote < 0:
            raise ValueError("available_margin_quote cannot be negative")
        if self.peak_equity_quote is not None and self.peak_equity_quote <= 0:
            raise ValueError("peak_equity_quote must be positive when provided")

    @property
    def gross_exposure_quote(self) -> float:
        return sum(p.notional_quote for p in self.open_positions)

    @property
    def net_exposure_quote(self) -> float:
        return sum(p.signed_notional_quote for p in self.open_positions)

    @property
    def portfolio_drawdown_quote(self) -> float:
        peak = self.peak_equity_quote or self.equity_quote
        return max(0.0, peak - self.equity_quote)


@dataclass(frozen=True, slots=True)
class KillSwitchState:
    level: KillSwitchLevel = KillSwitchLevel.NONE
    is_active: bool = False
    reason: str = "none"
    applies_to_strategy_id: str | None = None
    applies_to_symbol: str | None = None

    def applies_to(self, *, strategy_id: str, symbol: str) -> bool:
        if not self.is_active or self.level == KillSwitchLevel.NONE:
            return False
        if self.applies_to_strategy_id and self.applies_to_strategy_id != strategy_id:
            return False
        if self.applies_to_symbol and self.applies_to_symbol.upper() != symbol.upper():
            return False
        return True


@dataclass(frozen=True, slots=True)
class RiskDecisionDetail:
    action: RiskAction
    approved_quantity: float
    max_loss_quote: float
    risk_fraction: float
    notional_quote: float
    leverage_after_trade: float
    rejection_reasons: tuple[str, ...] = ()
    reduction_reasons: tuple[str, ...] = ()
    diagnostics: dict[str, float | str] = field(default_factory=dict)

    @property
    def approved(self) -> bool:
        return self.action in {RiskAction.APPROVE, RiskAction.REDUCE_SIZE} and self.approved_quantity > 0


@dataclass(frozen=True, slots=True)
class RiskRequest:
    signal: SignalEvent
    account: AccountState
    event_time_ms: int
    mark_price: float | None = None
    correlated_cluster: str | None = None
    kill_switch: KillSwitchState = KillSwitchState()

    @property
    def symbol(self) -> str:
        return self.signal.symbol.upper()
