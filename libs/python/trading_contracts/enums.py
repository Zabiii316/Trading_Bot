from enum import Enum


class EventType(str, Enum):
    RAW_AGG_TRADE = "raw.agg_trade"
    RAW_TRADE = "raw.trade"
    DEPTH_UPDATE = "raw.depth_update"
    ORDER_BOOK_SNAPSHOT = "raw.order_book_snapshot"
    BOOK_TICKER = "raw.book_ticker"
    RECONSTRUCTED_BOOK = "book.reconstructed"
    ORDER_FLOW_FEATURE = "features.order_flow"
    LIQUIDITY_LEVEL = "liquidity.level"
    LIQUIDITY_SWEEP = "liquidity.sweep"
    ANCHORED_VWAP = "features.anchored_vwap"
    SIGNAL = "signal.generated"
    RISK_DECISION = "risk.decision"
    EXECUTION_ORDER = "execution.order"
    EXECUTION_FILL = "execution.fill"
    KILL_SWITCH = "risk.kill_switch"


class Venue(str, Enum):
    BINANCE_SPOT = "binance_spot"
    BINANCE_USDM = "binance_usdm"
    BINANCE_COINM = "binance_coinm"
    TRADINGVIEW = "tradingview"
    PAPER = "paper"
    INTERNAL = "internal"


class MarketType(str, Enum):
    SPOT = "spot"
    PERPETUAL_FUTURES = "perpetual_futures"
    DELIVERY_FUTURES = "delivery_futures"
    FOREX = "forex"
    PAPER = "paper"


class AggressorSide(str, Enum):
    BUY = "buy"
    SELL = "sell"
    UNKNOWN = "unknown"


class TradeSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class LiquidityLevelType(str, Enum):
    PREVIOUS_DAY_HIGH = "previous_day_high"
    PREVIOUS_DAY_LOW = "previous_day_low"
    PREVIOUS_WEEK_HIGH = "previous_week_high"
    PREVIOUS_WEEK_LOW = "previous_week_low"
    SESSION_HIGH = "session_high"
    SESSION_LOW = "session_low"
    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"
    EQUAL_HIGHS = "equal_highs"
    EQUAL_LOWS = "equal_lows"
    ROUND_NUMBER = "round_number"
    CUSTOM = "custom"


class SweepState(str, Enum):
    INACTIVE = "inactive"
    LEVEL_ARMED = "level_armed"
    APPROACHING_LEVEL = "approaching_level"
    PENETRATING_LEVEL = "penetrating_level"
    CONSUMPTION_CONFIRMED = "consumption_confirmed"
    REJECTION_CANDIDATE = "rejection_candidate"
    ACCEPTANCE_CANDIDATE = "acceptance_candidate"
    AVWAP_CONFIRMATION_PENDING = "avwap_confirmation_pending"
    ORDER_FLOW_CONFIRMED = "order_flow_confirmed"
    SIGNAL_READY = "signal_ready"
    EXPIRED = "expired"


class SweepOutcome(str, Enum):
    BULLISH_REJECTION = "bullish_rejection"
    BEARISH_REJECTION = "bearish_rejection"
    BULLISH_ACCEPTANCE = "bullish_acceptance"
    BEARISH_ACCEPTANCE = "bearish_acceptance"
    NO_TRADE = "no_trade"
    UNRESOLVED = "unresolved"


class AvwapConfirmation(str, Enum):
    STRONG_BULLISH = "strong_bullish"
    WEAK_BULLISH = "weak_bullish"
    NEUTRAL = "neutral"
    WEAK_BEARISH = "weak_bearish"
    STRONG_BEARISH = "strong_bearish"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    MARKETABLE_LIMIT = "marketable_limit"
    STOP_MARKET = "stop_market"
    TAKE_PROFIT_MARKET = "take_profit_market"


class TimeInForce(str, Enum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    GTX = "gtx"  # Post-only where venue supports it


class OrderStatus(str, Enum):
    CREATED = "created"
    RISK_APPROVED = "risk_approved"
    SUBMITTED = "submitted"
    SUBMIT_UNKNOWN = "submit_unknown"  # POST timed out; position may exist
    ACKNOWLEDGED = "acknowledged"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_PENDING = "cancel_pending"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    RECONCILIATION_REQUIRED = "reconciliation_required"
    EMERGENCY_CLOSED = "emergency_closed"


class RiskDecisionStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    REDUCED_SIZE = "reduced_size"
    HALTED = "halted"


class KillSwitchLevel(str, Enum):
    NONE = "none"
    SOFT_STRATEGY_SUSPENSION = "soft_strategy_suspension"
    HARD_TRADING_HALT = "hard_trading_halt"
    EMERGENCY_FLATTEN = "emergency_flatten"
