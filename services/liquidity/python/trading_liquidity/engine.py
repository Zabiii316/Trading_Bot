from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid4

from trading_contracts.enums import EventType, LiquidityLevelType, MarketType, Venue
from trading_contracts.events import LiquidityLevelEvent

from .clustering import ClusteringConfig, LiquidityClusterBook
from .models import Bar, CandidateLevel, PivotKind, PriceCluster
from .reference import ReferenceLevelEngine
from .rolling import RollingAtr, RollingVolatility
from .round_numbers import RoundNumberConfig, RoundNumberDetector
from .scoring import LiquidityQualityConfig, LiquidityQualityScorer
from .sessions import DEFAULT_SESSIONS, SessionLevelEngine, SessionSpec
from .swings import SwingDetector, SwingDetectorConfig
from .tolerance import ToleranceModel, ZoneToleranceConfig


@dataclass(frozen=True, slots=True)
class LiquidityLevelEngineConfig:
    source: str = "liquidity-level-engine"
    atr_period: int = 14
    volatility_period: int = 20
    swing: SwingDetectorConfig = SwingDetectorConfig()
    tolerance: ZoneToleranceConfig = ZoneToleranceConfig()
    clustering: ClusteringConfig = ClusteringConfig()
    quality: LiquidityQualityConfig = LiquidityQualityConfig()
    round_numbers: RoundNumberConfig = RoundNumberConfig()
    min_emit_score: float = 0.30
    emit_on_every_touch: bool = True
    sessions: tuple[SessionSpec, ...] = DEFAULT_SESSIONS


class LiquidityLevelEngine:
    """Incremental structural liquidity engine.

    The hot path accepts one normalized bar at a time and emits contract-valid
    LiquidityLevelEvent objects. It never rescans full history, which keeps update
    complexity bounded by window sizes and cluster count.
    """

    __slots__ = (
        "config",
        "atr",
        "volatility",
        "tolerance_model",
        "swing_detector",
        "session_engine",
        "reference_engine",
        "round_detector",
        "cluster_book",
        "scorer",
        "_last_emitted",
    )

    def __init__(self, config: LiquidityLevelEngineConfig | None = None) -> None:
        self.config = config or LiquidityLevelEngineConfig()
        self.atr = RollingAtr(self.config.atr_period)
        self.volatility = RollingVolatility(self.config.volatility_period)
        self.tolerance_model = ToleranceModel(self.config.tolerance)
        self.swing_detector = SwingDetector(self.config.swing)
        self.session_engine = SessionLevelEngine(self.config.sessions)
        self.reference_engine = ReferenceLevelEngine()
        self.round_detector = RoundNumberDetector(self.config.round_numbers)
        self.cluster_book = LiquidityClusterBook(self.tolerance_model, self.config.clustering)
        self.scorer = LiquidityQualityScorer(self.config.quality)
        self._last_emitted: dict[tuple[str, str, int], float] = {}

    def update(self, bar: Bar) -> list[LiquidityLevelEvent]:
        atr = self.atr.update(bar)
        volatility = self.volatility.update(bar)
        self.tolerance_model.update_context(atr=atr, volatility=volatility)
        candidates: list[CandidateLevel] = []
        candidates.extend(self._pivots_to_candidates(self.swing_detector.update(bar)))
        candidates.extend(self.session_engine.update(bar))
        candidates.extend(self.reference_engine.update(bar))
        candidates.extend(self.round_detector.update(bar))
        # Equality is discovered through clustering: a swing cluster with multiple touches is
        # upgraded to EQUAL_HIGHS/EQUAL_LOWS at event emission time.
        events: list[LiquidityLevelEvent] = []
        for candidate in candidates:
            cluster = self.cluster_book.add(candidate)
            cluster = self._maybe_promote_equal_cluster(cluster)
            event = self._cluster_to_event(cluster, bar.event_time_ms)
            if event.quality_score >= Decimal(str(self.config.min_emit_score)) and self._should_emit(event):
                events.append(event)
        return events

    @staticmethod
    def _pivot_type(kind: PivotKind) -> LiquidityLevelType:
        return LiquidityLevelType.SWING_HIGH if kind == PivotKind.HIGH else LiquidityLevelType.SWING_LOW

    def _pivots_to_candidates(self, pivots) -> list[CandidateLevel]:
        out: list[CandidateLevel] = []
        for pivot in pivots:
            out.append(
                CandidateLevel(
                    symbol=pivot.symbol,
                    venue=pivot.venue,
                    market_type=pivot.market_type,
                    level_type=self._pivot_type(pivot.kind),
                    price=pivot.price,
                    time_ms=pivot.time_ms,
                    source="swing_detector",
                    volume=pivot.volume,
                    weight=1.0,
                    metadata={
                        "pivot_kind": pivot.kind.value,
                        "confirmed_time_ms": pivot.confirmed_time_ms,
                        "left_strength": pivot.left_strength,
                        "right_strength": pivot.right_strength,
                        **pivot.metadata,
                    },
                )
            )
        return out

    @staticmethod
    def _maybe_promote_equal_cluster(cluster: PriceCluster) -> PriceCluster:
        # If multiple swing highs/lows cluster tightly, treat them as equal-high/low liquidity.
        type_value = cluster.level_type.value if hasattr(cluster.level_type, "value") else str(cluster.level_type)
        if cluster.touches >= 2 and type_value == LiquidityLevelType.SWING_HIGH.value:
            cluster.level_type = LiquidityLevelType.EQUAL_HIGHS
        elif cluster.touches >= 2 and type_value == LiquidityLevelType.SWING_LOW.value:
            cluster.level_type = LiquidityLevelType.EQUAL_LOWS
        return cluster

    def _cluster_to_event(self, cluster: PriceCluster, now_ms: int) -> LiquidityLevelEvent:
        score = self.scorer.score(cluster, now_ms)
        return LiquidityLevelEvent(
            event_id=uuid4(),
            event_type=EventType.LIQUIDITY_LEVEL,
            source=self.config.source,
            venue=Venue(cluster.venue),
            market_type=MarketType(cluster.market_type),
            symbol=cluster.symbol,
            event_time_ms=now_ms,
            received_time_ms=now_ms,
            level_type=cluster.level_type,
            price=Decimal(str(round(cluster.price, 12))),
            zone_low=Decimal(str(round(cluster.zone_low, 12))),
            zone_high=Decimal(str(round(cluster.zone_high, 12))),
            quality_score=Decimal(str(round(score, 8))),
            touches=cluster.touches,
            first_seen_ms=cluster.first_seen_ms,
            last_seen_ms=cluster.last_seen_ms,
            is_active=True,
            metadata={
                **cluster.metadata,
                "sources": sorted(cluster.sources),
                "total_weight": round(cluster.total_weight, 8),
                "total_volume": round(cluster.total_volume, 8),
                "zone_width": round(cluster.zone_high - cluster.zone_low, 12),
            },
        )

    def _should_emit(self, event: LiquidityLevelEvent) -> bool:
        if self.config.emit_on_every_touch:
            return True
        key = (event.symbol, event.level_type, event.touches)
        previous = self._last_emitted.get(key)
        score = float(event.quality_score)
        if previous is None or abs(score - previous) >= 0.02:
            self._last_emitted[key] = score
            return True
        return False
