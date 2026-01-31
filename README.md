![img.png](img.png)# 同花顺 Mac 版自动化交易指南

## 📌 概述

本方案通过 **GUI 自动化**（模拟鼠标键盘操作）实现同花顺 Mac 版的自动下单功能。

**原理**: 使用 PyAutoGUI 库模拟用户操作，自动填写股票代码、价格、数量，并点击下单按钮。

---

## ⚙️ 环境准备

### 1. 安装 Python 依赖

```bash
# 基础依赖
pip3 install pyautogui pillow

# Mac 特定依赖（用于屏幕捕获和鼠标控制）
pip3 install pyobjc-framework-Quartz pyobjc-framework-ApplicationServices

# 可选：定时任务
pip3 install schedule

# 可选：行情数据
pip3 install akshare  # 或 tushare
```

### 2. 授权辅助功能权限

⚠️ **这一步非常重要！**

1. 打开 **系统偏好设置** → **安全性与隐私** → **隐私**
2. 左侧选择 **辅助功能**
3. 点击左下角🔒解锁
4. 添加并勾选以下应用：
   - **终端** (Terminal)
   - **Python** (如果单独运行)
   - **VS Code** (如果用 VS Code 运行)

![授权示意](https://support.apple.com/library/content/dam/edam/applecare/images/en_US/macos/Big-Sur/macos-big-sur-system-preferences-security-privacy-accessibility.png)

### 3. 确保同花顺已登录

- 打开同花顺 Mac 版
- 登录你的券商账户（如平安证券）
- 确保交易面板已显示

---

## 🚀 快速开始

### 步骤 1: 校准坐标

首次使用 **必须** 校准界面元素坐标：

```bash
python3 ths_mac_trader.py
# 选择 1. 校准坐标
```

按提示将鼠标移动到各个按钮/输入框位置，按 Enter 记录坐标。

### 步骤 2: 更新坐标配置

将校准得到的坐标复制到代码中：

```python
self.coords = {
    'buy_button': (271, 90),      # 替换为你的实际坐标
    'sell_button': (329, 90),
    'code_input': (280, 140),
    'price_input': (280, 175),
    'quantity_input': (280, 212),
    'confirm_button': (305, 258),
}
```

### 步骤 3: 测试下单

```python
from ths_mac_trader import THSMacTrader

trader = THSMacTrader()

# 测试买入（不自动确认）
trader.buy(
    code="603993",    # 股票代码
    price=24.33,      # 价格
    quantity=100,     # 数量
    confirm=False     # False=手动确认, True=自动确认
)
```

---

## 📊 代码结构

```
ths_mac_trader/
├── ths_mac_trader.py       # 基础交易类
├── ths_strategy_executor.py # 策略执行框架
└── README.md               # 使用说明
```

---

## 💡 使用示例

### 示例 1: 简单下单

```python
from ths_mac_trader import THSMacTrader

trader = THSMacTrader()

# 买入
trader.buy("600000", price=10.5, quantity=100)

# 卖出
trader.sell("600000", price=11.0, quantity=100)
```

### 示例 2: 批量下单

```python
orders = [
    ("600000", 10.5, 100, "buy"),
    ("000001", 15.2, 200, "buy"),
    ("603993", 25.0, 100, "sell"),
]

for code, price, qty, direction in orders:
    if direction == "buy":
        trader.buy(code, price, qty)
    else:
        trader.sell(code, price, qty)
    time.sleep(2)  # 每单间隔2秒
```

### 示例 3: 网格交易策略

```python
from ths_strategy_executor import GridStrategy, StrategyExecutor

# 创建网格策略
strategy = GridStrategy(
    stock_code="603993",
    base_price=24.33,
    grid_size=0.02,      # 2%网格间距
    quantity_per_grid=100
)

# 创建执行器并运行
executor = StrategyExecutor(trader, auto_confirm=False)
executor.add_strategy(strategy)
executor.run_scheduled(interval_seconds=60)  # 每分钟检查
```

### 示例 4: 定时任务

```python
import schedule
import time

def morning_buy():
    """每天早上9:30买入"""
    trader.buy("600000", price=10.0, quantity=100, confirm=True)

def afternoon_sell():
    """每天下午2:50卖出"""
    trader.sell("600000", price=10.5, quantity=100, confirm=True)

# 设置定时任务
schedule.every().day.at("09:30").do(morning_buy)
schedule.every().day.at("14:50").do(afternoon_sell)

# 运行
while True:
    schedule.run_pending()
    time.sleep(1)
```

---

## ⚠️ 重要注意事项

### 风险提示

1. **先用模拟盘测试** - 确保坐标和流程正确后再用于实盘
2. **不要完全自动化** - 建议 `confirm=False`，手动确认最后一步
3. **设置止损** - 程序可能出错，务必设置券商条件单止损
4. **保持屏幕可见** - GUI 自动化需要窗口在前台且不被遮挡

### 常见问题

#### Q: 点击位置不准确？
A: 重新运行校准程序，确保同花顺窗口位置与校准时一致

#### Q: 无法控制鼠标？
A: 检查辅助功能权限是否已授权

#### Q: 输入内容不正确？
A: 确保输入法是英文状态，或使用剪贴板方式输入

#### Q: 程序卡住了？
A: 快速将鼠标移到屏幕角落触发 FAILSAFE 机制

### 最佳实践

```python
# ✅ 推荐：手动确认
trader.buy(code, price, qty, confirm=False)

# ⚠️ 谨慎：自动确认
trader.buy(code, price, qty, confirm=True)

# ✅ 推荐：添加异常处理
try:
    trader.buy(code, price, qty)
except Exception as e:
    print(f"下单失败: {e}")
    # 发送告警通知
```

---

## 🔧 进阶配置

### 图像识别模式

更稳定的方式，不依赖固定坐标：

```python
from ths_mac_trader import ImageBasedTrader

trader = ImageBasedTrader()

# 首先截取按钮图片
trader.capture_button_images()

# 之后可以用图像识别点击
trader.find_and_click("buy_button")
```

### 对接行情数据

```python
import akshare as ak

def get_price(code):
    """获取实时价格"""
    df = ak.stock_zh_a_spot_em()
    row = df[df['代码'] == code]
    return float(row.iloc[0]['最新价'])

# 获取当前价格后下单
current_price = get_price("603993")
trader.buy("603993", price=current_price, quantity=100)
```

---

## 📋 交易时间检查

```python
from datetime import datetime

def is_trading_time():
    """检查是否在交易时间"""
    now = datetime.now()
    
    # 周末不交易
    if now.weekday() >= 5:
        return False
    
    # 交易时段：9:30-11:30, 13:00-15:00
    current_time = now.time()
    morning = (datetime.strptime("09:30", "%H:%M").time(), 
               datetime.strptime("11:30", "%H:%M").time())
    afternoon = (datetime.strptime("13:00", "%H:%M").time(),
                 datetime.strptime("15:00", "%H:%M").time())
    
    return (morning[0] <= current_time <= morning[1] or
            afternoon[0] <= current_time <= afternoon[1])

# 使用
if is_trading_time():
    trader.buy(...)
```

---

## 🆘 获取帮助

如果遇到问题：

1. 使用 `trader.get_mouse_position()` 检查坐标
2. 确认同花顺窗口在前台且完全显示
3. 检查辅助功能权限
4. 查看终端错误信息

---

## 📜 免责声明

本工具仅供学习研究使用。股市有风险，投资需谨慎。使用本工具进行交易造成的任何损失，作者不承担任何责任。
