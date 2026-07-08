from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from trading_contracts.enums import TradeSide

from .models import AccountState, PositionSnapshot


@dataclass(frozen=True, slots=True)
class ExposureSnapshot:
    gross_quote: float
    net_quote: float
    by_symbol: dict[str, float] = field(default_factory=dict)
    by_strategy: dict[str, float] = field(default_factory=dict)
    by_cluster: dict[str, float] = field(default_factory=dict)

    def symbol_exposure(self, symbol: str) -> float:
        return self.by_symbol.get(symbol.upper(), 0.0)

    def strategy_exposure(self, strategy_id: str) -> float:
        return self.by_strategy.get(strategy_id, 0.0)

    def cluster_exposure(self, cluster: str | None) -> float:
        if not cluster:
            return 0.0
        return self.by_cluster.get(cluster, 0.0)


def signed_notional_for(side: TradeSide, notional: float) -> float:
    if side == TradeSide.LONG:
        return notional
    if side == TradeSide.SHORT:
        return -notional
    return 0.0


def exposure_snapshot(account: AccountState) -> ExposureSnapshot:
    by_symbol: dict[str, float] = defaultdict(float)
    by_strategy: dict[str, float] = defaultdict(float)
    by_cluster: dict[str, float] = defaultdict(float)
    gross = 0.0
    net = 0.0
    for position in account.open_positions:
        notional = position.notional_quote
        gross += notional
        net += position.signed_notional_quote
        by_symbol[position.symbol.upper()] += notional
        by_strategy[position.strategy_id] += notional
        if position.correlated_cluster:
            by_cluster[position.correlated_cluster] += notional
    return ExposureSnapshot(
        gross_quote=gross,
        net_quote=net,
        by_symbol=dict(by_symbol),
        by_strategy=dict(by_strategy),
        by_cluster=dict(by_cluster),
    )


def projected_exposures(
    *,
    snapshot: ExposureSnapshot,
    symbol: str,
    strategy_id: str,
    side: TradeSide,
    notional_quote: float,
    correlated_cluster: str | None,
) -> ExposureSnapshot:
    by_symbol = dict(snapshot.by_symbol)
    by_strategy = dict(snapshot.by_strategy)
    by_cluster = dict(snapshot.by_cluster)
    symbol_key = symbol.upper()
    by_symbol[symbol_key] = by_symbol.get(symbol_key, 0.0) + notional_quote
    by_strategy[strategy_id] = by_strategy.get(strategy_id, 0.0) + notional_quote
    if correlated_cluster:
        by_cluster[correlated_cluster] = by_cluster.get(correlated_cluster, 0.0) + notional_quote
    gross = snapshot.gross_quote + notional_quote
    net = snapshot.net_quote + signed_notional_for(side, notional_quote)
    return ExposureSnapshot(gross_quote=gross, net_quote=net, by_symbol=by_symbol, by_strategy=by_strategy, by_cluster=by_cluster)
