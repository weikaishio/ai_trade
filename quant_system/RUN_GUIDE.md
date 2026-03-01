# 运行指南

## ✅ 正确的运行方式

**必须从项目根目录运行，使用 Python 模块方式**：

```bash
# 1. 切换到项目根目录
cd /Users/tim/Documents/golang/auto_trade

# 2. 以模块方式运行
python3 -m quant_system.quant_main --mode once --test --dry-run
```

## ❌ 错误的运行方式

```bash
# ❌ 不要这样运行（会报导入错误）
cd quant_system
python3 quant_main.py
```

## 📝 原因说明

quant_system 使用了 Python 包的相对导入（`from .config_quant import ...`）。

- **正确方式** (`python3 -m quant_system.quant_main`)：
  - Python 会把 quant_system 当作包
  - 相对导入正常工作
  - 路径自动正确

- **错误方式** (`python3 quant_main.py`)：
  - Python 把它当作普通脚本
  - 相对导入失败
  - 报错：`ImportError: attempted relative import with no known parent package`

## 🚀 快速命令参考

### 测试模式（模拟数据）
```bash
python3 -m quant_system.quant_main --mode once --test --dry-run
```

### 真实分析（OCR或手动输入）
```bash
python3 -m quant_system.quant_main --mode once --dry-run
```

### 自动监控模式
```bash
python3 -m quant_system.quant_main --mode auto --interval 300
```

### 实际交易（危险！）
```bash
python3 -m quant_system.quant_main --mode once
```

## 🔧 已修复的问题

1. ✅ 修复了相对导入兼容性
2. ✅ 自动创建日志目录
3. ✅ 自动创建数据目录
4. ✅ 更新了所有文档

## 📖 更多信息

详见 `QUICKSTART_QUANT.md`
