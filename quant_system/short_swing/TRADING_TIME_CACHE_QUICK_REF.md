# 交易时间智能缓存 - 快速参考

## 🎯 核心功能

**智能缓存策略**：根据当前时间，自动选择数据源

- **交易时间** (9:30-11:30, 13:00-15:00) → 获取实时数据 + 缓存
- **非交易时间** (周末/盘后/盘前) → 返回上一交易日缓存数据

## 🚀 快速开始

### 1. 首次部署（重要）

在**交易时间内**运行一次系统，建立缓存：

```bash
# 方式1: 启动API服务
python3 -m quant_system.short_swing.main

# 访问任一API接口即可触发缓存
curl http://localhost:8001/api/v1/sentiment

# 方式2: 运行测试脚本
python3 quant_system/short_swing/test_trading_time_cache.py
```

**建议时间**: 周一至周五 10:00-14:00

### 2. 验证缓存已建立

```bash
python3 -c "
from quant_system.short_swing.data.cache_manager import get_cache
cache = get_cache()
snapshot = cache.get('market_snapshot_last_trading_day', category='market_data')
limit_up = cache.get('limit_up_last_trading_day', category='market_data')
print(f'✅ 市场快照缓存: {len(snapshot) if snapshot else 0} 只股票')
print(f'✅ 涨停数据缓存: {len(limit_up) if limit_up else 0} 只股票')
"
```

**期望输出**:
```
✅ 市场快照缓存: 100 只股票
✅ 涨停数据缓存: 91 只股票
```

### 3. 测试非交易时间表现

周末或盘后运行：

```bash
curl http://localhost:8001/api/v1/sentiment
```

**期望结果**（应与交易时间一致）:
```json
{
  "sentiment": {
    "state": "heating",
    "limit_up_count": 91
  }
}
```

## 📊 缓存机制说明

### 缓存键

| 缓存键 | 用途 | TTL | 何时更新 |
|--------|------|-----|---------|
| `market_snapshot_last_trading_day` | 上一交易日全市场快照 | 24小时 | 仅交易时间 |
| `limit_up_last_trading_day` | 上一交易日涨停股票 | 24小时 | 仅交易时间 |

### 数据流向

```
交易时间:
  用户请求 → 实时API → 返回数据
                ├─→ 缓存到 "last_trading_day" (24h)
                └─→ 短期缓存 (60s)

非交易时间:
  用户请求 → "last_trading_day" 缓存 → 返回数据
           └─→ 缓存不存在时 → 实时API（但有警告）
```

## 🛠️ 常用命令

### 检查当前时间状态

```bash
python3 -c "
from quant_system.short_swing.utils.trading_time import is_trading_time, should_use_cached_data
is_trading, stage = is_trading_time()
print(f'是否交易时间: {is_trading}')
print(f'所处阶段: {stage}')
print(f'使用缓存数据: {should_use_cached_data()}')
"
```

### 查看缓存统计

```bash
python3 -c "
from quant_system.short_swing.data.cache_manager import get_cache
cache = get_cache()
stats = cache.get_stats()
print(f\"总记录: {stats['total']}, 有效: {stats['valid']}, 过期: {stats['expired']}\")
print(f\"分类统计: {stats['by_category']}\")
"
```

### 清空缓存（排查问题时使用）

```bash
# 删除缓存数据库
rm -f quant_system/short_swing/short_swing.db

# 或清空特定分类
python3 -c "
from quant_system.short_swing.data.cache_manager import get_cache
cache = get_cache()
cache.clear_category('market_data')
print('✅ 市场数据缓存已清空')
"
```

## 📝 日志关键字

### 成功日志

```
INFO - Cached 100 stocks to last_trading_day (trading stage: morning)
INFO - Cached 91 limit-up stocks to last_trading_day (trading stage: morning)
INFO - Non-trading time detected, loaded last trading day snapshot (100 stocks)
INFO - Non-trading time detected, loaded last trading day limit-up stocks (91 stocks)
```

### 警告日志

```
WARNING - Non-trading time but no cached data available, falling back to real-time API
```

**含义**: 非交易时间调用，但缓存不存在，需在交易时间内运行一次系统。

## ❓ 常见问题

### Q1: 非交易时间仍显示 freezing 状态？

**原因**: 缓存为空

**解决**:
```bash
# 检查缓存
python3 quant_system/short_swing/test_trading_time_cache.py

# 如果提示缓存为空，在交易时间内运行一次
python3 -m quant_system.short_swing.main
```

### Q2: 缓存何时过期？

**答**:
- TTL = 24小时
- 每个交易日收盘后会保留到次日下午
- 建议每日交易时间内至少运行一次，更新缓存

### Q3: 节假日怎么办？

**答**:
- 当前仅判断工作日（周一至周五）
- 法定节假日会被误判为交易日
- 如需完整支持，需接入交易日历API

### Q4: 缓存数据库在哪？

**答**:
```
quant_system/short_swing/short_swing.db
```

可手动删除清空缓存，不影响系统运行。

## 🔗 相关文档

- **详细修复报告**: `BUGFIX_TRADING_TIME_CACHE.md`
- **测试脚本**: `test_trading_time_cache.py`
- **交易时间工具**: `utils/trading_time.py`
- **数据获取器**: `data/data_fetcher.py`

## 📞 技术支持

**调试命令**:
```bash
# 查看日志
tail -f quant_system/logs/short_swing.log | grep -E "(trading|cache)"

# 测试完整功能
python3 quant_system/short_swing/test_trading_time_cache.py

# 手动触发API
curl http://localhost:8001/api/v1/sentiment
curl http://localhost:8001/api/v1/themes
```

**问题报告**: 请检查 `quant_system/logs/short_swing.log`

---

**最后更新**: 2026-03-01
**版本**: v1.0.0
