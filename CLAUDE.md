# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a GUI automation project for automated stock trading on the TongHuaShun (同花顺) Mac application. The system uses PyAutoGUI to simulate mouse and keyboard operations to fill in stock orders automatically.

**Critical**: This project automates financial trading operations. Any code changes must be thoroughly tested in simulated trading mode before real trading use.

## Core Architecture

### Main Components

1. **THSMacTrader** (`ths_mac_trader.py:45-349`)
   - Base class for coordinate-based GUI automation
   - Uses AppleScript to activate and control the THS window
   - Relies on pre-calibrated screen coordinates for UI elements
   - Contains methods for buying, selling, and order placement

2. **ImageBasedTrader** (`ths_mac_trader.py:351-414`)
   - Enhanced version using image recognition instead of fixed coordinates
   - More stable across different window positions
   - Requires pre-captured button images

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
# Install all dependencies
pip3 install pyautogui pillow pyobjc-framework-Quartz pyobjc-framework-ApplicationServices

# Optional packages for extended functionality
pip3 install schedule  # For scheduled trading
pip3 install akshare   # For market data integration
```

### Coordinate Calibration (CRITICAL FIRST STEP)

```bash
# NEW: Use the calibration helper tool (recommended)
python3 calibrate_helper.py
# Select option 1 to calibrate coordinates with visual feedback

# Copy the generated coordinate configuration to ths_mac_trader.py
```

### Running the Application

```bash
# Interactive mode with menu
python3 ths_mac_trader.py

# Direct trading (from test.py example)
python3 test.py
```

### Testing and Debugging

```bash
# Test coordinates visually
python3 calibrate_helper.py
# Select option 2 to test specific coordinates

# Real-time mouse position tracker
python3 calibrate_helper.py
# Select option 3 for live position tracking
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

### Order Placement Pattern

```python
from ths_mac_trader import THSMacTrader

trader = THSMacTrader()
trader.buy(
    code="603993",      # Stock code
    price=24.33,        # Price
    quantity=100,       # Quantity
    confirm=False       # Safety: manual confirmation
)
```

### Batch Orders Pattern

```python
orders = [
    ("600000", 10.5, 100, "buy"),
    ("603993", 25.0, 100, "sell"),
]

for code, price, qty, direction in orders:
    if direction == "buy":
        trader.buy(code, price, qty)
    else:
        trader.sell(code, price, qty)
    time.sleep(2)  # Rate limiting
```

### Error Handling Pattern

```python
try:
    if not trader.activate_ths_window():
        raise RuntimeError("Failed to activate THS window")

    trader.buy(code, price, qty, confirm=False)
except Exception as e:
    print(f"Order failed: {e}")
    # Send alert notification
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

### Auto Login Pattern (NEW)

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

## Project-Specific Conventions

1. **Coordinate Format**: All coordinates stored as tuples `(x, y)`
2. **Chinese Comments**: Many comments in Chinese to match domain (stock trading terminology)
3. **AppleScript Integration**: Uses subprocess to call osascript for macOS window control
4. **Clipboard Method**: For Chinese input, uses pbcopy/pbpaste instead of direct typing
5. **Safety First**: Default `confirm=False` to require manual verification

## File Structure

```
auto_trade/
├── ths_mac_trader.py          # Main automation logic
├── test.py                    # Example usage (buy/sell)
├── test_clear_positions.py    # Clear positions test
├── test_ocr_clear.py          # OCR clear positions test
├── test_auto_login.py         # Auto login test (NEW)
├── example_clear.py           # Simple clear example
├── example_auto_login.py      # Auto login examples (NEW)
├── ocr_positions.py           # OCR position extraction
├── calibrate_helper.py        # Coordinate calibration tool
├── find_correct_positions.py  # Interactive calibration with verification
├── README.md                  # User documentation (Chinese)
├── QUICKSTART.md              # Quick start guide
├── TROUBLESHOOTING.md         # Troubleshooting guide
├── CLEAR_POSITIONS_GUIDE.md   # Clear positions guide
├── AUTO_LOGIN_GUIDE.md        # Auto login guide (NEW)
├── OCR_GUIDE.md               # OCR usage guide
├── OCR_SUMMARY.md             # OCR quick reference
├── CLAUDE.md                  # Documentation for Claude Code
├── coordinates_config.txt     # Generated coordinates config
└── .claude/
    ├── commands/
    │   └── deepthink.md       # Custom slash command template
    └── agents/                # Custom agent definitions
```

## When Making Changes

1. **Before modifying trading logic**: Understand the order execution pipeline in `place_order()` (`ths_mac_trader.py:209-254`)
2. **When adding new UI elements**:
   - Update `self.coords_relative` dictionary
   - Update `calibrate_helper.py` to include the new element
   - Update both `calibrate()` method in `ths_mac_trader.py`
3. **When changing coordinate system**:
   - Test both relative and absolute modes
   - Update `get_absolute_coords()` method if logic changes
4. **Testing changes**:
   - Always test with `confirm=False` first
   - Test in simulated trading environment
   - Verify coordinates with `calibrate_helper.py` option 2
5. **GUI timing**:
   - Respect `pyautogui.PAUSE = 0.3` and additional `time.sleep()` calls
   - Increased delays in `clear_and_type()` and `input_text_via_clipboard()` to ensure focus changes
   - GUI needs time to respond - faster is not always better

## Common Issues and Solutions

### Issue: Inputs go to wrong location (e.g., top search box)

**Root Cause**: Coordinates not calibrated for user's screen layout

**Solution**:
1. Run `python3 calibrate_helper.py`
2. Follow the calibration wizard
3. Copy generated coordinates to `ths_mac_trader.py`
4. Ensure `self.use_relative_coords = True` is set

See `QUICKSTART.md` and `TROUBLESHOOTING.md` for detailed steps.

### Issue: Window position cannot be detected

**Root Cause**: AppleScript permission or app name mismatch

**Solution**:
1. Verify app name is exactly "同花顺" in Finder
2. Check Accessibility permissions in System Preferences
3. Fall back to absolute coordinate mode: `self.use_relative_coords = False`
