from __future__ import annotations

from dataclasses import dataclass
from heapq import nlargest

from .models import CandidateLevel, PriceCluster
from .tolerance import ToleranceModel


@dataclass(frozen=True, slots=True)
class ClusteringConfig:
    max_clusters_per_symbol: int = 250
    top_emit_count: int = 30


class LiquidityClusterBook:
    """Hot-path in-memory clustering for liquidity candidates.

    For V1 the cluster count is intentionally capped. This keeps updates cheap and
    prevents ancient levels from dominating memory. Later phases can shard this by
    symbol/timeframe or persist full historical cluster state.
    """

    __slots__ = ("config", "tolerance_model", "_clusters")

    def __init__(self, tolerance_model: ToleranceModel, config: ClusteringConfig | None = None) -> None:
        self.config = config or ClusteringConfig()
        self.tolerance_model = tolerance_model
        self._clusters: list[PriceCluster] = []

    @property
    def clusters(self) -> tuple[PriceCluster, ...]:
        return tuple(self._clusters)

    def add(self, candidate: CandidateLevel) -> PriceCluster:
        tolerance = self.tolerance_model.tolerance(candidate.price)
        best: PriceCluster | None = None
        best_distance = float("inf")
        for cluster in self._clusters:
            if cluster.can_absorb(candidate, tolerance):
                distance = abs(cluster.price - candidate.price)
                if distance < best_distance:
                    best = cluster
                    best_distance = distance
        if best is not None:
            best.absorb(candidate, tolerance)
            return best

        cluster = PriceCluster(
            symbol=candidate.symbol,
            venue=candidate.venue,
            market_type=candidate.market_type,
            level_type=candidate.level_type,
            price=candidate.price,
            zone_low=candidate.price - tolerance,
            zone_high=candidate.price + tolerance,
            touches=1,
            first_seen_ms=candidate.time_ms,
            last_seen_ms=candidate.time_ms,
            total_weight=max(candidate.weight, 0.000001),
            total_volume=max(candidate.volume, 0.0),
            sources={candidate.source},
            metadata=dict(candidate.metadata),
        )
        self._clusters.append(cluster)
        if len(self._clusters) > self.config.max_clusters_per_symbol:
            self._prune(candidate.time_ms)
        return cluster

    def _prune(self, now_ms: int) -> None:
        # Keep recent/touched clusters. This does not delete persisted emitted events.
        self._clusters.sort(key=lambda c: (c.touches, c.last_seen_ms), reverse=True)
        del self._clusters[self.config.max_clusters_per_symbol :]

    def top_clusters(self, score_fn, count: int | None = None) -> list[PriceCluster]:
        count = count or self.config.top_emit_count
        return nlargest(count, self._clusters, key=score_fn)
