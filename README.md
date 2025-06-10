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
├── .env                       # API credentials & testnet setting (gitignored)
├── config.json                # Trading parameters configuration
├── main.py                    # Main bot entry point
└── pybit_bot/
    ├── core/
    │   ├── __init__.py
    │   └── client.py          # Enhanced Bybit API client
    ├── managers/
    │   ├── __init__.py
    │   ├── order_manager.py   # Order handling with USDT position sizing
    │   ├── strategy_manager.py # Trading signals and strategy execution
    │   ├── tpsl_manager.py    # Take profit/stop loss management
    │   └── data_manager.py    # Market data management
    ├── indicators/
    │   ├── __init__.py
    │   ├── luxfvgtrend.py     # LuxFVGtrend indicator
    │   ├── tva.py             # Time-Volume Analysis
    │   ├── cvd.py             # Cumulative Volume Delta
    │   ├── vfi.py             # Volume Flow Indicator
    │   ├── atr.py             # Average True Range
    │   └── base.py            # Base indicator class
    ├── utils/
    │   ├── __init__.py
    │   ├── config_loader.py   # JSON config loading and validation
    │   ├── credentials.py     # .env file loading
    │   └── logger.py          # Logging functionality
    └── exceptions/
        ├── __init__.py
        └── errors.py          # Custom exceptions
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