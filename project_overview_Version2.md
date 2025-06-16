# Updated Pybit Bot System Architecture and Flow

## System Overview Flowchart

```
┌───────────────────────────────────────────────────────────────────┐
│                       CONFIGURATION LAYER                          │
│                                                                   │
│  .env                configs/                   utils/logger.py   │
│  API credentials     ├─ general.json                              │
│  BYBIT_API_KEY      │├─ strategy.json                             │
│  BYBIT_API_SECRET   ││├─ execution.json                           │
│  BYBIT_TESTNET      │││├─ indicators.json                         │
└──────────┬──────────┴┴┴┴───────────────────────────────────────────┘
           │
           ▼
┌───────────────────────────────────────────────────────────────────┐
│                          ENGINE LAYER                              │
│                                                                   │
│                         pybit_bot/engine.py                        │
└───────────────┬───────────────────┬───────────────────┬───────────┘
                │                   │                   │
                ▼                   ▼                   ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│  STRATEGY LAYER   │   │   MANAGER LAYER   │   │     CORE LAYER    │
│                   │   │                   │   │                   │
│ strategies/       │   │ managers/         │   │ core/             │
│ base_strategy.py  │   │ data_manager.py   │   │ client.py         │
│ strategy_a.py     │◄──┤ strategy_manager  │◄──┤ order_manager_    │
│ strategy_b.py     │   │ order_manager.py  │   │ client.py         │
│                   │   │ tpsl_manager.py   │   │                   │
└───────────────────┘   └───────────────────┘   └───────────────────┘
```

## Detailed Flow Description

### 1. Configuration Layer

#### Files:
- **.env** (in project root)
  - Purpose: Environment variables for sensitive data
  - Contains: `BYBIT_API_KEY`, `BYBIT_API_SECRET`, `BYBIT_TESTNET`
  - Used by: core/client.py when initializing API connections

- **pybit_bot/configs/general.json**
  - Purpose: General system and trading configuration
  - Contains: Trading pairs, timeframes, system settings
  - Used by: engine.py, data_manager.py

- **pybit_bot/configs/strategy.json**
  - Purpose: Strategy configuration and toggle mechanism
  - Contains: Enabled/disabled flags for each strategy, strategy-specific parameters
  - Used by: strategy_manager.py, strategy_a.py, strategy_b.py

- **pybit_bot/configs/execution.json**
  - Purpose: Order execution settings
  - Contains: Position sizing, risk management, TP/SL settings
  - Used by: order_manager.py, tpsl_manager.py, engine.py

- **pybit_bot/configs/indicators.json**
  - Purpose: Technical indicator parameters
  - Contains: Timeframes and parameters for each indicator
  - Used by: strategy implementations, data_manager.py

- **pybit_bot/utils/logger.py**
  - Purpose: Centralized logging system
  - Used by: All components

### 2. Engine Layer (Orchestration)

#### Files:
- **pybit_bot/engine.py**
  - Purpose: Orchestrates the entire trading system
  - Initializes: All managers and core components
  - Main loop: Fetches data, processes strategies, executes orders
  - Configuration: 
    - Loads from all config files in `configs/` directory
    - Uses general.json for system settings
    - Uses execution.json for risk management
  - Credentials: Passes API credentials to Core Layer

### 3. Manager Layer (Business Logic)

#### Files:
- **pybit_bot/managers/data_manager.py**
  - Purpose: Market data retrieval and caching
  - Configuration: Uses `general.json` for timeframes and symbols
  - API usage: Calls core client for market data
  - Returns: Historical data with proper column names

- **pybit_bot/managers/order_manager.py**
  - Purpose: Async wrapper for order execution
  - Configuration: Uses `execution.json` for risk/execution parameters
  - API usage: Wraps OrderManagerClient
  - Provides: High-level order functions like `enter_long_with_tp_sl()`

- **pybit_bot/managers/strategy_manager.py**
  - Purpose: Handles strategy selection and execution
  - Configuration: Uses `strategy.json` for strategy toggling
  - Key function: Loads only enabled strategies based on config
  - Initializes: Strategy instances based on enabled flags
  - Returns: Trade signals from active strategies

- **pybit_bot/managers/tpsl_manager.py**
  - Purpose: Manages take profit/stop loss execution
  - Configuration: Uses `execution.json` section `tpsl_manager`
  - API usage: Uses OrderManagerClient for position management
  - Provides: Position monitoring and TP/SL execution

### 4. Core Layer (API Communication)

#### Files:
- **pybit_bot/core/client.py**
  - Purpose: Base API communication with Bybit
  - Configuration: Minimal, mainly credentials
  - Credentials: Directly loads from .env file or environment variables
  - Provides: Low-level API access (REST/WebSocket)

- **pybit_bot/core/order_manager_client.py**
  - Purpose: Specialized order execution client
  - Configuration: Uses execution.json for trading parameters
  - Credentials: Uses via BybitClient
  - Provides: Direct order execution, position sizing

### 5. Strategy Layer (Trade Logic)

#### Files:
- **pybit_bot/strategies/base_strategy.py**
  - Purpose: Base class for all strategies, defines interface
  - Provides: TradeSignal class definition

- **pybit_bot/strategies/strategy_a.py**
  - Purpose: Multi-indicator confluence strategy
  - Configuration: Uses `strategy.json` → strategy_a section
  - Enabled/Disabled: Controlled by `strategy.json` → strategies → strategy_a → enabled
  - Indicators: Uses configurations from `indicators.json`

- **pybit_bot/strategies/strategy_b.py**
  - Purpose: SMA crossover strategy
  - Configuration: Uses `strategy.json` → strategy_b section
  - Enabled/Disabled: Controlled by `strategy.json` → strategies → strategy_b → enabled
  - Indicators: Uses SMA and ATR with parameters from strategy.json

## Operational Flow

1. **Initialization Flow**:
   ```
   engine.py
     ├─ Loads all config files from configs/ directory
     ├─ Creates BybitClient with credentials from .env
     ├─ Initializes DataManager with general.json settings
     ├─ Initializes OrderManagerClient with BybitClient
     ├─ Initializes OrderManager with execution.json settings
     ├─ Initializes StrategyManager with strategy.json settings
     │   └─ StrategyManager loads only enabled strategies based on toggle
     ├─ Initializes TPSLManager with execution.json settings
     └─ Starts main trading loop
   ```

2. **Strategy Toggle Mechanism**:
   ```
   strategy_manager.py
     ├─ Loads strategy.json
     ├─ For each strategy (strategy_a, strategy_b, etc.):
     │   └─ Checks "enabled" flag in strategy config
     │       ├─ If true: Instantiates strategy and adds to active strategies
     │       └─ If false: Skips loading that strategy
     └─ Only processes data through enabled strategies
   ```

3. **Main Loop Flow**:
   ```
   engine._main_loop()
     ├─ For each symbol/timeframe from general.json:
     │   ├─ DataManager.get_historical_data()  (calls client.py)
     │   ├─ StrategyManager.process_data()     (only through enabled strategies)
     │   │   └─ Returns TradeSignal objects
     │   └─ If signals exist:
     │       ├─ Order validation using execution.json risk parameters
     │       └─ OrderManager.enter_long/short_with_tp_sl()
     │
     ├─ TPSLManager.check_positions()  (monitors active positions)
     │   └─ Calls OrderManagerClient methods to adjust/close positions
     │
     └─ Loop with interval from general.json system settings
   ```

4. **API Credential Usage**:
   - **Source**: .env file in project root containing:
     - BYBIT_API_KEY
     - BYBIT_API_SECRET
     - BYBIT_TESTNET
   - **Loading**: BybitClient loads credentials directly from environment
   - **Propagation**: All other components use credentials via BybitClient instance

This updated overview accurately reflects how the Pybit Bot uses multiple configuration files for different aspects of the system and implements a strategy toggle mechanism through the "enabled" flags in the strategy.json configuration.