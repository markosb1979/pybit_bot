# PyBit Bot

A modular trading bot for Bybit USDT Perpetual contracts.

```markdown name=pybit_bot_architecture.md
# PyBit Bot: Architecture & Development Plan

## Project Overview

**PyBit Bot** is a Python-based trading bot designed for Bybit USDT Perpetual contracts. The project leverages a clear division of responsibilities:

- **Architecture Design**: ChatGPT
- **Implementation**: GitHub AI (Copilot)
- **Testing**: Mark (You)

## Core Design Principles

The bot architecture is founded on the following key principles:

1. **Modularity**: Clean separation of components for easier testing and maintenance
2. **Reliability**: Accurate order and position tracking as a foundation
3. **Resilience**: Designed to handle network issues, API errors, and disconnects
4. **Real-time Processing**: WebSocket-driven updates for market data
5. **Separation of Concerns**: Decoupled signal generation and execution logic

## System Architecture

### Module Structure

```
pybit_bot/
├── .env                           # API credentials & testnet settings (git-ignored)
├── config.json                    # Trading parameters configuration
├── main.py                        # Main bot entry point
└── pybit_bot/
    ├── core/
    │   ├── __init__.py
    │   ├── client.py              # Enhanced Bybit API client
    │   └── order_manager_client.py  # Order‐manager client interface
    │
    ├── managers/
    │   ├── __init__.py
    │   ├── order_manager.py       # Order handling with USDT position sizing
    │   ├── strategy_manager.py    # Trading signals & strategy execution
    │   ├── tpsl_manager.py        # Take profit / stop loss management
    │   └── data_manager.py        # Market data management
    │
    ├── indicators/
    │   ├── __init__.py
    │   ├── luxfvgtrend.py         # LuxFVGtrend indicator
    │   ├── tva.py                 # Time‐Volume Analysis
    │   ├── cvd.py                 # Cumulative Volume Delta
    │   ├── vfi.py                 # Volume Flow Indicator
    │   ├── atr.py                 # Average True Range
    │   └── base.py                # Base indicator class
    │
    ├── utils/
    │   ├── __init__.py
    │   ├── config_loader.py       # JSON config loading & validation
    │   ├── credentials.py         # .env file parsing
    │   └── logger.py              # Centralized logging setup
    │
    └── exceptions/
        ├── __init__.py
        └── errors.py             # Custom exception definitions

```

### Component Responsibilities

#### 1. Core Client
- Enhanced Bybit API wrapper with comprehensive error handling
- WebSocket connection management for real-time data
- Rate limiting to prevent API abuse
- Authentication and request signing

#### 2. OrderManager
- Converts USDT position sizes to contract quantities
- Tracks all orders and positions
- Handles order submission, amendment, and cancellation
- Maintains state synchronization with exchange

#### 3. StrategyManager
- Coordinates the five technical indicators
- Generates entry/exit signals
- Implements trading logic based on indicator outputs
- Decoupled from execution details

#### 4. TPSLManager
- Calculates take profit and stop loss levels
- Manages trailing stops if configured
- Closes positions when TP/SL conditions are met
- Implements partial profit-taking strategies

#### 5. DataManager
- Handles historical and real-time market data across timeframes
- Constructs candles from tick data
- Provides clean data interface to indicators
- Updates data at end of each candle period

#### Order Manager Client 
- API Translation Layer - Translates generic order commands into Bybit-specific API calls, abstracting exchange-specific details from the rest of the system
- Order State Management - Maintains the lifecycle and state of all orders, providing status tracking and updates through both REST polling and WebSocket notifications
- Error Handling & Resilience - Implements retry logic, error recovery, and connection stability mechanisms specific to order operations
- Position & Risk Management - Handles position sizing calculations, leverage settings, and risk parameters to enforce trading limits and safety mechanisms

## Technical Indicators

The bot implements five key technical indicators:

1. **LuxFVGtrend**: Fair Value Gap trend indicator
2. **TVA (Time-Volume Analysis)**: Analyzes volume patterns over time
3. **CVD (Cumulative Volume Delta)**: Tracks buying/selling pressure
4. **VFI (Volume Flow Indicator)**: Measures money flow volume
5. **ATR (Average True Range)**: Measures market volatility

## Configuration Management

### Environment Variables (.env)
```
# Bybit API Credentials
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
BYBIT_TESTNET=true           # true for testnet, false for mainnet


```

### Trading Configuration (config.json)
```json
{
  "trading": {
    "symbol": "BTCUSDT",
    "timeframe": "1m",
    "position_size_usdt": 50.0,
    "max_positions": 3
  },
  "risk": {
    "stop_loss_pct": 0.02,
    "take_profit_pct": 0.04,
    "max_daily_loss_usdt": 100.0
  },
  "indicators": {
    "luxfvgtrend": {
      "length": 14,
      "mult": 2.0
    },
    "tva": {
      "volume_ma_period": 20
    },
    "cvd": {
      "length": 20
    },
    "vfi": {
      "period": 130
    },
    "atr": {
      "period": 14
    }
  },
  "data": {
    "lookback_bars": {
      "1m": 2000,
      "5m": 1000,
      "1h": 200
    },
    "update_interval": 60
  },
  "system": {
    "log_level": "INFO"
  }
}
```

## Development Roadmap

The project will follow a phased development approach:

### Phase 1: Foundation
- Core client implementation
- Project structure setup
- Base configuration management

### Phase 2: Data Management
- REST API data retrieval
- WebSocket connection management
- Historical data loading
- Real-time data processing

### Phase 3: Order Management
- Order submission, tracking, and cancellation
- Position management
- USDT-based position sizing

### Phase 4: Strategy Implementation
- Indicator development and integration
- Signal generation logic
- Strategy manager

### Phase 5: Risk Management
- Take-profit/stop-loss execution
- Trailing stop implementation
- Position exit logic

### Phase 6: System Integration
- Main processing loop
- Component integration
- Event handling system

### Phase 7: Testing & Optimization
- Comprehensive test suite
- Performance optimization
- Stability testing

### Phase 8: Production Deployment
- Final review and adjustments
- Production setup
- Monitoring and alerting

## Logging & Analytics

- CSV output format for trade logging
- Detailed execution logs
- Performance metrics tracking
- Error and exception logging

## Error Handling & Resilience

- Comprehensive error catching and recovery
- Automatic reconnection for WebSocket disconnects
- State reconciliation after disconnections
- Throttling to prevent API rate limit issues
- Graceful shutdown procedures

## Testing Strategy

- Unit tests for individual components
- Integration tests for component interactions
- End-to-end system tests
- Testnet validation before mainnet deployment
- Stress testing under various market conditions

## Conclusion

The PyBit Bot is designed as a robust, modular trading system with emphasis on reliability and resilience. By leveraging WebSocket-driven updates and maintaining clear separation of concerns, the system aims to provide a stable foundation for algorithmic trading on Bybit perpetual contracts.
```

## Installation

1. Clone the repository
```bash
git clone https://github.com/markosb1979/pybit_bot.git
cd pybit_bot


Phase 4: Strategy Implementation - Requirements Confirmation
new files required at minimum
Strategy_manager 
TP/SL manager
indicator.json
1. Indicator Development and Integration
•	Custom Indicators Implementation: 
Provided indicator source code
•	Data Requirements: 
o	Indicators can run on 1m, 2m, and 1h timeframes configure in indicator.json.
•	Configuration: 
o	Can configure via new Indicator.json_file
2. Signal Generation Logic STRATEGY A
Entry Logic (always based on the previous closed bar):
1.	Filter Confluence
o	Check each enabled indicator on the previous bar (never the forming bar):
	CVD: Require cvd > 0 for long, or cvd < 0 for short (if enabled).
	TVA: Require rb > 0 for long, or rr < 0 for short (if enabled).
	VFI: Require vfi > 0 for long, or vfi < 0 for short (if enabled).
	FVG (Fair Value Gap): Require fvg_type == +1 for a bullish gap (long), or fvg_type == –1 for a bearish gap (short), if enabled.
o	All enabled filters must pass for a new signal to be considered. configure in indicator.json.
2.	Determine Entry Price
o	If using market entry, the candidate price is simply the previous bar’s close.
o	If using limit entry, the candidate price is the previous bar’s FVG midpoint (the center of the most recent fair-value gap) +/- atr value

example; long trade FVG midpoint prive (100,000)+ 1minute ATR value (50) = limit buy at 100,050
example short trade FVG midpoint prive (100,000)- 1 minutes ATR value (50) = limit buy at 99950
3.	________________________________________
Exit Logic (TP/SL Automation via new TPSLManager.py):
•	Stop‐Loss (SL) and Take‐Profit (TP) Levels
o	Based on the entry price and previous bar’s ATR:
	For a long (BUY) trade:
o	SL = entry price – (ATR × stop_loss_multiplier) configure in indicator.json.
	
o	TP = entry price + (ATR × take_profit_multiplier) configure in indicator.json.
	
	For a short (SELL) trade:
o	SL = entry price + (ATR × stop_loss_multiplier) configure in indicator.json.
	
o	TP = entry price – (ATR × take_profit_multiplier) configure in indicator.json.
	
•	Post‐Fill TP/SL Placement
o	Only after the entry order is confirmed filled does the bot place two OCO (one-cancels-other) orders:
	A limit order at the TP price (for a long) or at the TP price (for a short).
	A stop-market order at the SL price (for a long) or at the SL price (for a short).
o	This ensures no TP or SL is active until the entry is fully in.
•	OCO Management
o	As soon as one of the TP or SL orders fills, the TPSLManager automatically cancels the other.
o	P&L is calculated at the actual fill price, fees are deducted, and the trade is marked closed.
•	Failsafe Pre-Entry Logic
o	If an opposite signal appears before a pending limit entry has filled, the bot cancels the unfilled entry to avoid entering on a market reversal.
•	End‐of‐Data or Timeout
o	If neither TP nor SL is triggered before data ends (or before a configured timeout), the trade is closed at the final bar’s close price.
•	Trade limit
o	User defined 1 long trade configure in indicator.json.
user defined 1 short trade configure in indicator.json.
o	In this scenario, 2 opposite trades could potentially be open

Exit Logic (TP/SL Automation via TPSLManager):
•	Stop‐Loss (SL) and Take‐Profit (TP) Levels
o	Based on the entry price and previous bar’s ATR:
	For a long (BUY) trade:
o	SL = entry price – (ATR × stop_loss_multiplier) configure in indicator.json.

o	TP = entry price + (ATR × take_profit_multiplier) configure in indicator.json.

	For a short (SELL) trade:
o	SL = entry price + (ATR × stop_loss_multiplier) configure in indicator.json.

o	TP = entry price – (ATR × take_profit_multiplier) configure in indicator.json.

•	Post‐Fill TP/SL Placement
o	Only after the entry order is confirmed filled does the bot place two OCO (one-cancels-other) orders:
	A limit order at the TP price (for a long) or at the TP price (for a short).
	A stop-market order at the SL price (for a long) or at the SL price (for a short).
o	This ensures no TP or SL is active until the entry is fully in.
o	Running (Trailing) Stop (if enabled) configure in indicator.json.
o	Initial SL = entry price ∓ (atr × SLtrail_atr_mult) configure in indicator.json.
o	Long: stop_price = entry_price − (atr × trail_atr_mult) configure in indicator.json.
never stop down
o	Short: stop_price = entry_price + (atr × trail_atr_mult) configure in indicator.json.
never stop up
o	Initial TP= TP = entry price – (ATR × TPtrail_atr_mult))
o	after placing your Initial TP level, you won’t activate the trailing stop immediately. Instead, you wait until the market moves at least halfway toward your profit target—i.e. reaches 50% of the distance between your entry price and TP. At that point, you turn on the ATR-based trailing stop, which then follows the price at your chosen ATR multiple to lock in gains as the market continues in your favor

o	Should signals have strength/confidence metrics? NO
•	Combination Rules: 
o	How should multiple indicator signals be combined? 
They work independently 
o	Are there priority rules between indicators?
•	Filtering: No
o	Any specific market conditions to filter signals (volatility, time of day, etc.)?
No
3. Strategy Manager
•	Architecture: 
o	How should the Strategy Manager interact with the OrderManager?
the strategy manager will send “triggers” to the ordermanger. Buy, sell, amend, cancel, place, check orders, check price etc. The
o	Should strategies be pluggable/interchangeable at runtime?
there will be 2 strategies A & B. Both do not run together.



Indicator inputs and outputs
Here’s a quick reference of each indicator’s user-configurable inputs (with their default values) and the exact output series names you’ll see on the chart (as produced by the code):
________________________________________
1. ATR
•	Function signature: calculate_atr(df, length: int = 14)
•	User input:
o	length – ATR window size (default 14) (configure in json)
•	Output:
o	A single pd.Series of ATR values, typically added as column atr (use in strategyA)
________________________________________
2. CVD (Cumulative Volume Delta)
•	Function signature: calculate_cvd(df, cumulation_length: int = 14)
•	User input:
o	cumulation_length – EMA span for smoothing the signed-volume delta (default 25) (configure in json)
•	Output:
o	A single pd.Series of CVD values, typically added as column cvd use in strategyA)

________________________________________
3. TVA (Trend Volume Acceleration)
•	Function signature: calculate_tva(df, length: int = 15)
•	User inputs:
o	length – lookback for the WMA/SMA oscillator (default 15) (configure in json)
o	(Note: smo = 3 and mult = 5.0 are currently hard-coded in the routine)
•	Outputs:
o	rb – Rising Bull accumulator (reset-on-flip)
o	rr – Rising Bear accumulator (reset-on-flip)
o	db – Declining Bull accumulator (negative, reset-on-flip)
o	dr – Declining Bear accumulator (negative, reset-on-flip)
o	upper – Upper “wave” level (gray reference line)
o	lower – Lower “wave” level (gray reference line)
________________________________________
4. VFI (Volume Flow Imbalance)
•	Function signature: calculate_vfi(df, lookback: int = 50)
•	User input:
o	lookback – window size for the rolling buy/sell volume sums (default 50) (configure in json)
•	Output:
o	A single pd.Series of VFI values (imbalance ratio), typically added as column vfi use in strategyA)

________________________________________
5. LuxFVGtrend (Fair Value Gap Trend)
•	Function signature: calculate_luxfvgtrend(df)
•	User inputs:
o	None — step_size is currently hard-coded to 1.0 inside the function (configure in json)
•	Outputs (three pd.Series):
o	fvg_signal – 1 = bullish gap, –1 = bearish gap, 0 = none use in strategyA)
o	fvg_midpoint – price midpoint of the detected gap (or 0.0 if none) use in strategyA)
o	fvg_counter – incremental trend counter (positive for bull streaks, negative for bear streaks) use in strategyA)
________________________________________
________________________________________
Key Points:
•	Everything references the previous closed bar’s values (never the in-progress bar).
•	All indicator checks, spacing checks, and price calculations are driven by ATR and indicator outputs from that prior bar.
•	Risk levels (TP/SL) are fixed multiples of ATR, ensuring a consistent risk-reward framework.
•	TP/SL orders are only placed upon confirmed entry fills, and managed via OCO so that only one side can ever execute.
•	A failsafe cancels any pending entry if an opposite signal forms before the order can fill.
•	No code snippets are included—just a concise description of entry-and-exit rules.

