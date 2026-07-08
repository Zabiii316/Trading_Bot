"""Phase 3 local order-book reconstruction package.

The hot data structures are exported without importing the service layer. The service
layer depends on market-data publisher abstractions, so importing it lazily avoids
forcing optional runtime dependencies into offline feature/replay tools.
"""

from .book import BookIntegrityError, LocalOrderBook, SideBook
from .sequencer import BookSyncState, DepthSequencer, SequenceGapError, StaleDepthUpdate
from .snapshot import BinanceDepthSnapshotClient

__all__ = [
    "LocalOrderBook",
    "SideBook",
    "BookIntegrityError",
    "BookSyncState",
    "DepthSequencer",
    "SequenceGapError",
    "StaleDepthUpdate",
    "BinanceDepthSnapshotClient",
    "OrderBookReconstructionService",
]


def __getattr__(name: str):
    if name == "OrderBookReconstructionService":
        from .service import OrderBookReconstructionService

        return OrderBookReconstructionService
    raise AttributeError(name)
