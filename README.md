# Bybit Trading Bot - Modular Architecture

A comprehensive, modular Python trading bot for Bybit USDT Perpetuals with emphasis on reliability, testing, and production readiness.

## Features

### ✅ Phase 1 - Complete
- **Modular Architecture**: Clean separation of concerns
- **Comprehensive API Client**: Enhanced pybit wrapper with error handling
- **Configuration Management**: JSON + Environment variable support
- **Advanced Logging**: CSV output for trade tracking
- **Rate Limiting**: Built-in protection against API abuse
- **Comprehensive Testing**: 15+ test scenarios for validation

### 🚧 Phase 2 - In Development
- **WebSocket Manager**: Real-time data feeds
- **Order Manager**: State-first order tracking
- **Position Manager**: Advanced position management
- **Technical Indicators**: LuxFVGtrend, TVA, CVD, VFI, ATR

### 📋 Phase 3 - Planned
- **Strategy Engine**: Multi-indicator strategy framework
- **Risk Management**: Advanced TP/SL execution
- **Portfolio Management**: Multi-symbol support
- **Production Monitoring**: Health checks and alerts

## Quick Start

### 1. Installation

```bash
# Clone repository
git clone <repository-url>
cd bybit-trading-bot

# Install dependencies
pip install -r requirements.txt

# Or install as package
pip install -e .
```

### 2. Configuration

```bash
# Copy environment template
cp .env.template .env

# Edit with your API credentials
nano .env
```

**Required .env variables:**
```bash
BYBIT_API_KEY=your_testnet_api_key
BYBIT_API_SECRET=your_testnet_api_secret
BYBIT_TESTNET=true
```

### 3. Comprehensive Testing

```bash
# Run full test suite
python test_bot_comprehensive.py

# Or if installed as package
test-bot
```

## Test Suite Coverage

The comprehensive test covers:

1. **Connection Test** - Basic API connectivity
2. **API Credentials** - Authentication validation
3. **Signature Test** - HMAC signature verification
4. **Server Time** - Time synchronization check
5. **Wallet Balance** - Account balance retrieval
6. **Historical Klines** - 1000x 1m BTCUSDT bars
7. **Live Market Data** - Real-time ticker data
8. **Order Book** - Market depth data
9. **Position Status** - Current positions
10. **Place Limit Order** - Test limit order placement
11. **Cancel Order** - Order cancellation
12. **Place Market Order** - Market order execution
13. **Close Position** - Position closing
14. **WebSocket Connection** - Real-time feeds (Phase 2)
15. **Rate Limiting** - API protection validation

## Configuration

### JSON Configuration (config.json)

```json
{
  "testnet": true,
  "symbol": "BTCUSDT",
  "position_size": 0.01,
  "stop_loss_pct": 0.02,
  "take_profit_pct": 0.04,
  "lux_fvg_settings": {
    "period": 20,
    "sensitivity": 1.0
  },
  "tva_settings": {
    "period": 14,
    "smoothing": 3
  }
}
```

### Environment Variables

Sensitive data (API keys) should be stored in `.env`:

```bash
BYBIT_API_KEY=your_key
BYBIT_API_SECRET=your_secret
BYBIT_TESTNET=true
TRADING_SYMBOL=BTCUSDT
POSITION_SIZE=0.01
```

## Architecture Overview

```
pybit_bot/
├── core/
│   ├── client.py          # Enhanced Bybit API client
│   └── __init__.py
├── trading/               # Trading components (Phase 2)
│   ├── order_manager.py   # State-first order tracking
│   ├── position_manager.py # Position management
│   └── __init__.py
├── strategies/            # Strategy framework (Phase 3)
│   ├── base.py           # Strategy base class
│   ├── multi_indicator.py # Multi-indicator strategy
│   └── __init__.py
├── indicators/            # Technical indicators (Phase 2)
│   ├── lux_fvg.py        # LuxFVGtrend indicator
│   ├── tva.py            # TVA indicator
│   ├── cvd.py            # CVD indicator
│   ├── vfi.py            # VFI indicator
│   ├── atr.py            # ATR indicator
│   └── __init__.py
├── websocket/             # WebSocket manager (Phase 2)
│   ├── manager.py        # WebSocket connection management
│   ├── handlers.py       # Message handlers
│   └── __init__.py
├── utils/
│   ├── logger.py         # CSV logging system
│   ├── config.py         # Configuration management
│   ├── helpers.py        # Utility functions
│   └── __init__.py
├── exceptions.py          # Custom exceptions
└── __init__.py
```

## Logging

The bot provides comprehensive logging with CSV output:

### Log Files Generated
- `logs/BotTester_YYYYMMDD.log` - Standard logs
- `logs/trades_YYYYMMDD.csv` - Trade executions
- `logs/orders_YYYYMMDD.csv` - Order history
- `logs/positions_YYYYMMDD.csv` - Position updates
- `logs/signals_YYYYMMDD.csv` - Trading signals

### CSV Trade Log Example
```csv
timestamp,symbol,side,quantity,price,order_id,trade_id,commission,pnl,strategy
2024-01-01T12:00:00,BTCUSDT,Buy,0.001,45000.0,12345,67890,0.45,0.0,MultiIndicator
```

## Error Handling

Comprehensive error handling for:
- **API Errors**: Rate limits, authentication, invalid requests
- **Network Issues**: Timeouts, connection errors, retries
-