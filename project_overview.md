# Pybit Bot Project Overview

**Current Date and Time (UTC):** 2025-06-16 04:53:08  
**Current User's Login:** markosb1979

## Project Structure

ChatGPT oversees architecture; Github AI implements; Mark tests. The project builds a modular Python trading bot for Bybit USDT Perpetuals, emphasizing reliable order tracking, testable components, and resilience to latency, API errors, and disconnects.

## Technical Features

It uses indicators:
- LuxFVGtrend
- TVA
- CVD
- VFI
- ATR

With state-first order logic, WebSocket-driven updates, and decoupled signal/execution.

## Development Phases

Development is phased:
1. Scaffolding
2. REST/WebSocket core
3. OrderManager
4. Strategy
5. Engine loop
6. TP/SL execution
7. Testing
8. Production

Configurable via JSON with CSV log output.