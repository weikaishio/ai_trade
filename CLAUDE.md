# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a comprehensive automated stock trading system for the TongHuaShun (同花顺) Mac application, consisting of two major components:

1. **GUI Automation Layer** - PyAutoGUI-based automation for simulating mouse/keyboard operations in THS
2. **Quantitative Trading System** - Intelligent decision engine with deep learning model integration, risk management, and RESTful API

**CRITICAL**: This project automates real financial trading operations. Any code changes MUST be thoroughly tested with `confirm=False` and `--dry-run` modes before use in live trading environments.

## Core Architecture

### Layer 1: GUI Automation (ths_mac_trader.py)

**THSMacTrader** - Base class for all GUI automation operations:
- **Window Management**: AppleScript integration to activate/focus THS window
- **Coordinate System**: Dual-mode support (relative/absolute coordinates)
- **Input Methods**: Clipboard-based Chinese text input, secure password handling
- **Trading Operations**: buy(), sell(), place_order(), clear_all_positions()
- **OCR Integration**: Position/order extraction via ocr_positions.py, ocr_orders.py
- **Login Management**: Auto-detect login status, handle CAPTCHA, auto-login

**Key Helper Modules**:
- `ths_login_manager.py` - Advanced login detection and auto-recovery
- `ths_enhanced_trader.py` - Enhanced trader with retry logic
- `ths_auto_recovery.py` - Automatic state detection and recovery
- `ths_state_detector.py` - Detect THS application state

### Layer 2: Quantitative Trading System (quant_system/)

**Architecture Overview**:
```
MarketDataClient (Tencent API) → ModelClient (ML scoring) → DecisionEngine
                                                                    ↓
                              RiskManager ← TradeSignal + BuySignal
                                    ↓
                            QuantTradingSystem (orchestrator)
                                    ↓
                            THSMacTrader (execution)
```

**Core Components**:
1. **MarketDataClient** (`market_data_client.py`)
   - Fetches real-time stock data from Tencent API
   - Batch query support, intelligent caching
   - Data validation and parsing

2. **ModelClient** (`model_client.py`)
   - Connects to deep learning model API
   - Returns 0-100 scores with buy/sell/hold recommendations
   - Supports multiple model fusion strategies

3. **DecisionEngine** (`decision_engine.py`)
   - Multi-factor analysis (model score, price trend, P&L, holding time)
   - Stop-loss/stop-profit logic
   - Generates actionable TradeSignal objects

4. **BuyStrategy** (`buy_strategy.py`)
   - Stock selection and buy signal generation
   - Entry timing optimization
   - Position sizing recommendations

5. **RiskManager** (`risk_manager.py`)
   - Daily trade limits, loss limits, circuit breakers
   - Trade history tracking and statistics
   - ST stock restrictions

6. **StockSelector** (`stock_selector.py`)
   - Multi-dimensional stock screening
   - Model-based candidate selection
   - Priority ranking

### Layer 3: API Server (api_server/)

**FastAPI-based REST API**:
- `main.py` - FastAPI application with lifespan management
- `api_routes.py` - RESTful endpoint definitions
- `trading_executor.py` - Async task executor with queue
- `api_security.py` - IP whitelist, rate limiting
- `api_models.py` - Pydantic request/response models

### Key Functionality

**Trading Operations**:
- `place_order()` - Main order execution pipeline
- `buy()` / `sell()` - Convenience methods for trading
- `switch_direction()` - Toggle between buy/sell modes
- `input_stock_code()` / `input_price()` / `input_quantity()` - Form filling
- `clear_all_positions()` - Batch sell all positions
- `get_positions_from_input()` - Interactive position input helper
- `get_positions_from_ocr()` - OCR-based position extraction from screenshots
- `smart_sell()` - Intelligent sell with OCR position recognition

**Login & Authentication** (NEW):
- `check_login_status()` - Detect if user is logged in
- `auto_login()` - Automated login with account/password
- `ensure_logged_in()` - Auto-detect and login if needed
- `handle_captcha()` - Process CAPTCHA (manual or OCR)
- `capture_captcha_image()` - Screenshot CAPTCHA image

**Calibration Tools**:
- `calibrate()` - Interactive coordinate calibration wizard
- `get_mouse_position()` - Real-time mouse position tracker
- `capture_button_images()` - Image recognition setup tool

**Window Management**:
- `activate_ths_window()` - Brings THS to foreground using AppleScript
- `get_window_position()` - Retrieves window bounds for coordinate mapping

## Development Commands

### Environment Setup

```bash
# GUI Automation dependencies (required)
pip3 install pyautogui pillow pyobjc-framework-Quartz pyobjc-framework-ApplicationServices

# Quantitative trading system dependencies (optional)
pip3 install -r quant_system/requirements_quant.txt

# This includes: fastapi, uvicorn, pydantic, requests, pandas, etc.
```

### Coordinate Calibration (CRITICAL FIRST STEP for GUI automation)

```bash
# Use the calibration helper tool (recommended)
python3 calibrate_helper.py
# Select option 1: Calibrate coordinates with visual feedback

# Alternative: Advanced calibration with verification
python3 find_correct_positions.py

# Copy generated coordinates to ths_mac_trader.py
# Look for the coords_relative dictionary
```

### Running GUI Automation Only

```bash
# Interactive mode with menu
python3 ths_mac_trader.py

# Direct order placement (test scripts)
python3 test.py

# Test clear positions feature
python3 test_clear_positions.py

# Test OCR position extraction
python3 test_ocr_clear.py
```

### Running Quantitative Trading System

**IMPORTANT**: Must run from project root directory using module syntax:

```bash
# Navigate to project root
cd /Users/tim/Documents/golang/auto_trade

# Quick test with mock data (safe, recommended for first run)
python3 -m quant_system.quant_main --mode once --test --dry-run

# Real analysis with OCR positions (dry-run, no actual trades)
python3 -m quant_system.quant_main --mode once --dry-run

# Continuous monitoring mode (dry-run)
python3 -m quant_system.quant_main --mode auto --interval 300 --dry-run

# DANGER: Live trading mode (requires confirmation)
python3 -m quant_system.quant_main --mode once
```

**Why module syntax?** The quant_system uses Python package relative imports (`from .config_quant import ...`). Running with `-m` treats it as a package, enabling relative imports.

### Running API Server

```bash
# Start FastAPI server
cd api_server
python3 main.py

# Or with uvicorn directly
uvicorn api_server.main:app --host 0.0.0.0 --port 8000 --reload

# Access API documentation
open http://localhost:8000/docs
```

### Testing and Debugging

```bash
# Test coordinate calibration
python3 calibrate_helper.py  # Select option 2

# Test login detection
python3 test_login_detection_fix.py

# Test OCR functionality
python3 test_real_ocr_data.py
python3 test_cost_price_recognition.py

# Test quant system components
python3 quant_system/test_model_fusion.py
python3 quant_system/test_buy_integration.py
python3 quant_system/test_batch_performance.py

# Verify window position cache
python3 test_window_position_cache.py
```

## Important Constraints

### Security & Safety

1. **Always test with `confirm=False`** - Manual confirmation prevents accidental trades
2. **Screen must be visible** - GUI automation requires the THS window to be in foreground and unobstructed
3. **Coordinate calibration required** - Screen coordinates vary by resolution and window position
4. **macOS permissions** - Accessibility permissions must be granted to Terminal/Python/IDE

### Coordinate System

**Two coordinate modes available**:

1. **Relative Coordinate Mode** (default, recommended):
   - Stored in `self.coords_relative` dictionary (`ths_mac_trader.py:61-76`)
   - Coordinates are relative to THS window's top-left corner
   - Automatically converts to absolute screen coordinates at runtime
   - Works even when window is moved
   - Controlled by `self.use_relative_coords = True`

2. **Absolute Coordinate Mode** (legacy):
   - Stored in `self.coords` dictionary
   - Coordinates are relative to screen's top-left corner
   - Window must be in same position as during calibration
   - Controlled by `self.use_relative_coords = False`

**Calibration**:
- Use `calibrate_helper.py` tool for best results
- Generates both relative and absolute coordinates
- Must be recalibrated if window size or screen resolution changes

### Trading Constraints

- Only works during market hours (weekdays 9:30-11:30, 13:00-15:00 China time)
- Requires THS application to be logged in and trading panel visible
- Input method must be in English mode for reliable text input
- `pyautogui.FAILSAFE = True` - Move mouse to screen corner to abort

## Code Patterns

### GUI Automation Patterns

**Basic Order Placement**:
```python
from ths_mac_trader import THSMacTrader

trader = THSMacTrader()
trader.buy(
    code="603993",      # Stock code
    price=24.33,        # Price
    quantity=100,       # Quantity
    confirm=False       # CRITICAL: manual confirmation for safety
)
```

**Batch Orders**:
```python
orders = [
    ("600000", 10.5, 100, "buy"),
    ("603993", 25.0, 100, "sell"),
]

for code, price, qty, direction in orders:
    if direction == "buy":
        trader.buy(code, price, qty, confirm=False)
    else:
        trader.sell(code, price, qty, confirm=False)
    time.sleep(2)  # Rate limiting to avoid overwhelming THS
```

**Error Handling**:
```python
try:
    if not trader.activate_ths_window():
        raise RuntimeError("Failed to activate THS window")

    trader.buy(code, price, qty, confirm=False)
except Exception as e:
    print(f"Order failed: {e}")
    # Log error, send alert, etc.
```

### Clear All Positions Pattern

```python
from ths_mac_trader import THSMacTrader, Position

trader = THSMacTrader()

# Method 1: Interactive input
trader.clear_all_positions()

# Method 2: Predefined positions
positions = [
    Position("603993", "Stock A", 100, 24.33),
    Position("600000", "Stock B", 200, 10.50),
]
trader.clear_all_positions(positions=positions, confirm=False)

# Method 3: Market price mode (let THS auto-fill prices)
trader.clear_all_positions(
    positions=positions,
    use_market_price=True
)
```

**Auto Login Pattern**:
```python
from ths_mac_trader import THSMacTrader
import os

trader = THSMacTrader()

# Method 1: Simple auto login (password only)
trader.auto_login(password="your_password")

# Method 2: Auto login with account
trader.auto_login(
    account="your_account",
    password="your_password"
)

# Method 3: Ensure logged in (recommended)
# Auto-detect login status and login if needed
trader.ensure_logged_in(
    auto_login_enabled=True,
    account=os.getenv("THS_ACCOUNT"),
    password=os.getenv("THS_PASSWORD")
)

# Then proceed with trading
trader.buy(code, price, qty)
```

### Quantitative Trading Patterns

**Basic Quant System Usage**:
```python
from quant_system.quant_main import QuantTradingSystem

# Initialize with safety flags
system = QuantTradingSystem(test_mode=True, dry_run=True)

# Analyze positions once
system.run_once()

# Or run continuous monitoring
system.run_auto(check_interval=300)  # Check every 5 minutes
```

**Using Individual Components**:
```python
from quant_system.market_data_client import MarketDataClient
from quant_system.model_client import ModelClient
from quant_system.decision_engine import DecisionEngine

# Get market data
market_client = MarketDataClient()
stock_data = market_client.get_stock_data("603993")

# Get model score
model_client = ModelClient()
score = model_client.get_score("603993")

# Make decision
engine = DecisionEngine()
signal = engine.analyze_position(position, stock_data, score)
```

**API Server Usage**:
```python
import requests

# Get market data via API
response = requests.post(
    "http://localhost:8000/api/v1/quant/market-data",
    json={"stock_codes": ["603993", "600000"]}
)
data = response.json()

# Analyze positions
response = requests.post(
    "http://localhost:8000/api/v1/quant/analyze-positions",
    json={
        "positions": [
            {"code": "603993", "quantity": 100, "cost_price": 24.33}
        ],
        "dry_run": True
    }
)
```

## Project-Specific Conventions

### General
1. **Coordinate Format**: All coordinates stored as tuples `(x, y)` or `(x, y, width, height)` for regions
2. **Chinese Comments**: Many comments/strings in Chinese to match domain (stock trading terminology)
3. **AppleScript Integration**: Uses subprocess to call osascript for macOS window control
4. **Clipboard Method**: For Chinese input, uses pbcopy/pbpaste instead of direct PyAutoGUI typing
5. **Safety First**: Default `confirm=False` to require manual verification before actual trades

### Module Organization
- **Root directory scripts**: Standalone tools and basic GUI automation
- **quant_system/**: Quantitative trading system (must run with `python3 -m quant_system.xxx`)
- **api_server/**: FastAPI REST API service
- **docs/**: Additional documentation and guides

### Configuration Files
- `config_quant.py` - Quant system configuration (thresholds, API URLs, risk parameters)
- `api_server/config.py` - API server configuration
- Coordinates stored directly in `ths_mac_trader.py` (coords_relative dict)

### Logging
- All modules use Python's `logging` module
- Log files stored in `quant_system/logs/` for quant system
- Console output enabled by default for debugging

## File Structure

```
auto_trade/
├── ths_mac_trader.py              # Main GUI automation class
├── ths_login_manager.py           # Login detection & auto-recovery
├── ths_enhanced_trader.py         # Enhanced trader with retry logic
├── ths_auto_recovery.py           # State detection and recovery
├── ths_state_detector.py          # THS application state detector
├── ocr_positions.py               # OCR position extraction
├── ocr_orders.py                  # OCR order extraction
│
├── calibrate_helper.py            # Coordinate calibration tool
├── find_correct_positions.py      # Advanced calibration with verification
├── calibrate_captcha_region.py    # CAPTCHA region calibration
│
├── test_*.py                      # Various test scripts
│
├── quant_system/                  # Quantitative trading system
│   ├── __init__.py
│   ├── quant_main.py              # Main entry point
│   ├── config_quant.py            # Configuration
│   ├── market_data_client.py      # Market data from Tencent API
│   ├── model_client.py            # Deep learning model client
│   ├── decision_engine.py         # Trading decision engine
│   ├── buy_strategy.py            # Buy signal generation
│   ├── risk_manager.py            # Risk management & limits
│   ├── stock_selector.py          # Stock screening & selection
│   ├── requirements_quant.txt     # Dependencies
│   ├── logs/                      # Log files (auto-created)
│   ├── data/                      # Data storage (auto-created)
│   └── test_*.py                  # Test scripts
│
├── api_server/                    # FastAPI REST API
│   ├── main.py                    # FastAPI app
│   ├── api_routes.py              # Route definitions
│   ├── trading_executor.py        # Async task executor
│   ├── api_security.py            # Security middleware
│   ├── api_models.py              # Pydantic models
│   └── config.py                  # API config
│
├── docs/                          # Additional documentation
│   ├── CLEAR_POSITIONS_GUIDE.md
│   ├── OCR_GUIDE.md
│   ├── POSITION_OCR_QUICK_START.md
│   ├── SMART_SELL_GUIDE.md
│   └── *.md                       # Various fix summaries
│
├── README.md                      # Main README (Chinese)
├── QUICKSTART.md                  # Quick start guide
├── CLAUDE.md                      # This file
├── quant_system/QUICKSTART_QUANT.md   # Quant system quick start
├── quant_system/RUN_GUIDE.md          # How to run quant system
└── .claude/                       # Claude Code configuration
    ├── commands/
    │   └── deepthink.md
    └── agents/
```

## When Making Changes

### GUI Automation Changes

1. **Before modifying trading logic**:
   - Understand the order execution pipeline in `place_order()` method
   - Review the coordinate conversion logic in `get_absolute_coords()`
   - Test with `confirm=False` to prevent accidental trades

2. **When adding new UI elements**:
   - Add entry to `self.coords_relative` dictionary in `ths_mac_trader.py`
   - Update `calibrate_helper.py` to include calibration for the new element
   - Document the new coordinate in comments
   - Test with `calibrate_helper.py` option 2 to verify

3. **When changing coordinate system**:
   - Test both relative mode (`use_relative_coords=True`) and absolute mode
   - Update `get_absolute_coords()` if coordinate mapping logic changes
   - Verify window position caching works correctly
   - Update coordinate documentation

4. **GUI timing considerations**:
   - Respect `pyautogui.PAUSE = 0.3` global delay
   - Additional `time.sleep()` calls in methods are intentional for GUI stability
   - Increased delays in `clear_and_type()` and `input_text_via_clipboard()` ensure focus changes complete
   - **DO NOT reduce delays** without extensive testing - faster is not better for GUI automation

### Quantitative System Changes

1. **Before modifying decision logic**:
   - Review `DecisionEngine.analyze_position()` multi-factor analysis
   - Understand weight distribution (model: 50%, trend: 20%, P&L: 20%, time: 10%)
   - Check risk thresholds in `config_quant.py`

2. **When adding new data sources**:
   - Follow the pattern in `MarketDataClient`
   - Add caching to reduce API calls
   - Include data validation and error handling
   - Update mock data in `config_quant.py` for testing

3. **When adding new strategies**:
   - Inherit from base strategy pattern (see `BuyStrategy`)
   - Implement signal generation with confidence scores
   - Add comprehensive logging
   - Create test file in `quant_system/test_*.py`

4. **Risk management modifications**:
   - Update thresholds in `config_quant.py`, not hardcoded
   - Test circuit breaker logic thoroughly
   - Verify trade history persistence
   - Add appropriate logging for auditing

### API Server Changes

1. **When adding new endpoints**:
   - Define Pydantic models in `api_models.py`
   - Add route in `api_routes.py`
   - Update OpenAPI docs with descriptions
   - Test with dry-run mode first

2. **Security considerations**:
   - Review IP whitelist in `api_security.py`
   - Rate limiting for resource-intensive endpoints
   - Validate all user inputs
   - Never expose sensitive credentials

## Common Issues and Solutions

### GUI Automation Issues

**Issue: Inputs go to wrong location (e.g., top search box)**
- **Root Cause**: Coordinates not calibrated for user's screen layout
- **Solution**:
  1. Run `python3 calibrate_helper.py`
  2. Follow the calibration wizard carefully
  3. Copy generated coordinates to `ths_mac_trader.py` (coords_relative dict)
  4. Ensure `self.use_relative_coords = True`
  5. See `QUICKSTART.md` for detailed steps

**Issue: Window position cannot be detected**
- **Root Cause**: AppleScript permission or app name mismatch
- **Solution**:
  1. Verify app name is exactly "同花顺" in Finder
  2. Check Accessibility permissions in System Preferences → Security & Privacy → Privacy → Accessibility
  3. Add Terminal/Python/IDE to allowed apps
  4. If still failing, fall back to absolute mode: `self.use_relative_coords = False`

**Issue: Login detection not working**
- **Root Cause**: THS UI changes or screenshot timing
- **Solution**:
  1. Check `LOGIN_DETECTION_FIX_V2_SUMMARY.md`
  2. Recalibrate login button coordinates
  3. Verify CAPTCHA region with `calibrate_captcha_region.py`
  4. Test with `test_login_detection_fix.py`

**Issue: OCR returns incorrect values**
- **Root Cause**: OCR region not properly calibrated or image quality issues
- **Solution**:
  1. Review `docs/OCR_GUIDE.md`
  2. Recalibrate position_list_region coordinates
  3. Check OCR price correction rules in `OCR_PRICE_CORRECTION_GUIDE.md`
  4. Test with `test_real_ocr_data.py`

### Quantitative System Issues

**Issue: ImportError with relative imports**
- **Root Cause**: Running as script instead of module
- **Solution**:
  - ❌ Wrong: `cd quant_system && python3 quant_main.py`
  - ✅ Correct: `cd /path/to/auto_trade && python3 -m quant_system.quant_main`
  - See `quant_system/RUN_GUIDE.md`

**Issue: Model API connection failed**
- **Root Cause**: Model server not running or URL misconfigured
- **Solution**:
  1. Check `MODEL_API_URL` in `config_quant.py`
  2. Verify model server is running
  3. Test with curl: `curl -X POST http://localhost:5000/comprehensive_score_custom_api`
  4. Enable `MOCK_MODEL_ENABLED = True` for testing without model

**Issue: No positions detected**
- **Root Cause**: OCR failed or positions list empty
- **Solution**:
  1. Enable `MOCK_DATA_ENABLED = True` for testing
  2. Manually input positions when prompted
  3. Check OCR calibration
  4. Review logs in `quant_system/logs/`

### API Server Issues

**Issue: 403 Forbidden on API requests**
- **Root Cause**: IP not in whitelist
- **Solution**:
  1. Check `ALLOWED_IPS` in `api_server/config.py`
  2. Add your IP or disable whitelist for local testing
  3. Check logs for client IP address

**Issue: Async loop errors**
- **Root Cause**: Multiple event loops or improper async handling
- **Solution**:
  - See `api_server/BUGFIX_ASYNCIO_LOOP.md`
  - Ensure proper use of `asyncio.create_task()`
  - Don't mix sync and async code inappropriately

## Important Notes for Development

### Safety Practices
1. **ALWAYS use dry-run mode first**: `--dry-run` flag or `confirm=False` parameter
2. **Test in simulated environment**: Use mock data before live trading
3. **Verify coordinates**: After any screen resolution or THS update
4. **Monitor logs**: Check `quant_system/logs/` for issues
5. **Backup configurations**: Before making changes to `config_quant.py`

### Testing Workflow
```bash
# Step 1: Test GUI automation with manual confirmation
python3 -c "from ths_mac_trader import THSMacTrader; t = THSMacTrader(); t.buy('603993', 24.33, 100, confirm=False)"

# Step 2: Test quant system with mock data
python3 -m quant_system.quant_main --mode once --test --dry-run

# Step 3: Test with real data but dry-run
python3 -m quant_system.quant_main --mode once --dry-run

# Step 4: Only after thorough testing, enable live trading
python3 -m quant_system.quant_main --mode once
```

### Configuration Priority
1. **config_quant.py**: Main quantitative system configuration
2. **api_server/config.py**: API server settings (can override via env vars)
3. **ths_mac_trader.py**: Coordinates stored directly in code (coords_relative dict)
4. **Environment variables**: For sensitive data (THS_ACCOUNT, THS_PASSWORD)

### Documentation References
- **General usage**: `README.md`, `QUICKSTART.md`
- **Quant system**: `quant_system/QUICKSTART_QUANT.md`, `quant_system/RUN_GUIDE.md`
- **Specific features**: `docs/CLEAR_POSITIONS_GUIDE.md`, `docs/OCR_GUIDE.md`, `docs/SMART_SELL_GUIDE.md`
- **Troubleshooting**: Various `*_FIX_SUMMARY.md` files
- **API documentation**: Access `/docs` endpoint when server is running

### Key Differences from Typical Python Projects
1. **macOS-specific**: Requires macOS for AppleScript and Accessibility features
2. **GUI automation**: Inherently fragile, requires precise timing and coordinates
3. **Financial domain**: Requires extra safety measures and testing
4. **Hybrid architecture**: Combines GUI automation with ML-based decision making
5. **Module syntax required**: quant_system must run with `python3 -m` syntax
