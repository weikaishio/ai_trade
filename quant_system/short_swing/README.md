# 超短线交易信号系统

## 📋 系统简介

基于**情绪周期判断**和**主线题材识别**的超短线交易信号提示系统。

**核心功能**：
- ✅ 市场情绪周期实时判断（冰点/回暖/升温/高潮/退潮）
- ✅ 主线题材自动识别和龙头股检测
- ✅ 多因子选股评分（模型分数 + 情绪加成 + 题材加成）
- ✅ RESTful API接口，支持前端集成
- ✅ 完善的缓存机制，降低API调用频率
- ✅ 智能缓存策略，非交易时间返回上一交易日数据

**⚠️ 重要声明**：
- 本系统**仅提供信号建议**，不执行实际交易
- 所有信号仅供参考，不构成投资建议
- 投资有风险，入市需谨慎

---

## 🚀 快速开始

### 1. 环境准备

**Python版本要求**: Python 3.8+

**安装依赖**:
```bash
cd /Users/tim/Documents/golang/auto_trade
pip3 install fastapi uvicorn pydantic requests
```

### 2. 确保模型服务运行

超短线系统依赖模型服务（端口5000）获取股票评分。

**启动模型服务**:
```bash
cd /Users/tim/Documents/golang/stock_tools/es_strategy/deepmodel
python3 server_v2.py
```

验证模型服务：
```bash
curl http://localhost:5000/health
```

### 3. 启动超短线信号系统

```bash
cd /Users/tim/Documents/golang/auto_trade
python3 -m quant_system.short_swing.main
```

**服务启动成功后会显示**:
```
============================================================
超短线交易信号系统启动中...
版本: 1.0.0
服务地址: http://0.0.0.0:8001
API文档: http://localhost:8001/docs
============================================================
```

### 4. 访问API文档

浏览器打开: **http://localhost:8001/docs**

可以直接在页面上测试所有API接口。

---

## 📡 API接口说明

### 1. 获取市场情绪状态

**接口**: `GET /api/v1/sentiment`

**响应示例**:
```json
{
  "success": true,
  "sentiment": {
    "state": "heating",
    "limit_up_count": 45,
    "avg_change_percent": 1.85,
    "rising_ratio": 0.58,
    "falling_ratio": 0.35,
    "volume_ratio": 1.32,
    "confidence": 0.72,
    "timestamp": "2026-03-01T10:30:00",
    "description": "市场活跃度提升，情绪升温"
  },
  "message": "市场情绪升温，积极参与，但要注意仓位控制"
}
```

**情绪状态说明**:
- `freezing` - 冰点期：空仓观望
- `warming` - 回暖期：小仓位试探
- `heating` - 升温期：积极参与
- `climax` - 高潮期：谨慎追高
- `ebbing` - 退潮期：立即减仓

### 2. 获取主线题材

**接口**: `GET /api/v1/themes`

**响应示例**:
```json
{
  "success": true,
  "themes": [
    {
      "theme_name": "芯片",
      "stocks": [
        {
          "code": "sh688981",
          "name": "中芯国际",
          "change_percent": 8.5,
          "volume_ratio": 3.2,
          "is_leader": true
        }
      ],
      "leader_stock": {
        "code": "sh688981",
        "name": "中芯国际",
        "change_percent": 8.5,
        "volume_ratio": 3.2,
        "is_leader": true
      },
      "avg_change_percent": 6.8,
      "stock_count": 12,
      "score": 88.5
    }
  ],
  "top_theme": { ... },
  "message": "检测到 3 个主线题材"
}
```

### 3. 获取选股候选

**接口**: `POST /api/v1/candidates`

**请求体**:
```json
{
  "limit": 20,
  "min_score": 70,
  "exclude_codes": ["sh600000", "sz000001"]
}
```

**响应示例**:
```json
{
  "success": true,
  "candidates": [
    {
      "code": "sh603501",
      "name": "韦尔股份",
      "price": 24.56,
      "change_percent": 5.2,
      "volume_ratio": 2.8,
      "turnover": 8.5,
      "market_cap": 0.0,
      "limit_up_prob": 0.75,
      "downside_risk": 0.15,
      "chanlun_risk": 0.10,
      "final_score": 82.3,
      "signal": "strong_buy",
      "theme": "芯片",
      "is_leader": false,
      "sentiment_bonus": 0.6,
      "timestamp": "2026-03-01T10:35:00"
    }
  ],
  "sentiment_state": "heating",
  "total_count": 15,
  "message": "生成 15 个候选股票（情绪状态: heating）"
}
```

**信号类型说明**:
- `strong_buy` - 强烈建议（评分≥85）
- `buy` - 建议买入（评分≥75）
- `watch` - 关注观察（评分≥65）
- `ignore` - 忽略（评分<65）

### 4. 健康检查

**接口**: `GET /api/v1/health`

**响应示例**:
```json
{
  "status": "ok",
  "service": "short_swing_signal_system",
  "version": "1.0.0"
}
```

---

## 🔧 配置说明

所有配置参数在 `quant_system/short_swing/config_short_swing.py` 中统一管理。

### 核心配置项

**1. 情绪周期阈值** (`SENTIMENT_THRESHOLDS`):
```python
"heating": {
    "limit_up_count": 60,      # 涨停数量 30-60
    "avg_change_percent": 1.8, # 平均涨幅 1.5%-2.5%
    "rising_ratio": 0.6,       # 上涨股票占比 45%-60%
}
```

**2. 选股评分权重** (`STOCK_SCORING_WEIGHTS`):
```python
{
    "limit_up_prob": 0.4,    # 涨停概率权重
    "downside_risk": -0.3,   # 下跌风险（负权重）
    "chanlun_risk": -0.2,    # 缠论风险（负权重）
    "sentiment_bonus": 0.1,  # 情绪周期加成
}
```

**3. 超短线过滤条件** (`SHORT_SWING_FILTERS`):
```python
{
    "max_price": 30.0,           # 价格 <= 30元
    "min_volume_ratio": 1.2,     # 量比 > 1.2
    "min_turnover": 3.0,         # 换手率 > 3%
    "market_cap_range": (10e8, 100e8),  # 市值 10-100亿
    "exclude_st": True,          # 排除ST股票
}
```

**4. API服务配置** (`API_CONFIG`):
```python
{
    "host": "0.0.0.0",
    "port": 8001,
    "cors_origins": ["http://localhost:3000"],
}
```

---

## 📊 使用示例

### Python调用示例

```python
import requests

# 1. 获取市场情绪
response = requests.get("http://localhost:8001/api/v1/sentiment")
sentiment = response.json()
print(f"当前情绪: {sentiment['sentiment']['state']}")
print(f"交易建议: {sentiment['message']}")

# 2. 获取主线题材
response = requests.get("http://localhost:8001/api/v1/themes")
themes = response.json()
if themes['top_theme']:
    top = themes['top_theme']
    print(f"最强题材: {top['theme_name']}")
    print(f"龙头股: {top['leader_stock']['name']}")

# 3. 获取选股候选
response = requests.post(
    "http://localhost:8001/api/v1/candidates",
    json={"limit": 10, "min_score": 75}
)
candidates = response.json()
for i, stock in enumerate(candidates['candidates'][:5], 1):
    print(f"{i}. {stock['name']} ({stock['code']}): "
          f"评分={stock['final_score']:.1f}, 信号={stock['signal']}")
```

### cURL调用示例

```bash
# 获取情绪状态
curl http://localhost:8001/api/v1/sentiment

# 获取主线题材
curl http://localhost:8001/api/v1/themes

# 获取选股候选
curl -X POST http://localhost:8001/api/v1/candidates \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "min_score": 75}'
```

---

## 🏗️ 系统架构

```
quant_system/short_swing/
├── __init__.py
├── main.py                       # FastAPI服务入口
├── config_short_swing.py         # 配置文件
├── engines/                      # 核心引擎
│   ├── sentiment_engine.py       # 情绪周期判断
│   ├── theme_detector.py         # 主线题材识别
│   └── stock_scorer.py           # 选股评分系统
├── data/                         # 数据层
│   ├── models.py                 # Pydantic数据模型
│   ├── data_fetcher.py           # 数据获取（东方财富+模型API）
│   └── cache_manager.py          # SQLite缓存管理
└── api/                          # API层
    └── routes.py                 # FastAPI路由
```

**数据流**:
```
东方财富API → data_fetcher → cache_manager → 引擎处理 → API响应
模型服务API ↗
```

---

## 🛠️ 故障排查

### 问题0: 数据获取错误 (已修复)

**错误信息**: `Failed to parse quote item: string indices must be integers`

**状态**: ✅ **已修复** (2026-03-01)

**说明**: 东方财富API数据解析问题已修复，详见 `BUGFIX_EASTMONEY_API.md`

**验证修复**:
```bash
python3 quant_system/short_swing/test_fix.py
```

### 问题0.5: 模型API解析错误 (已修复)

**错误信息**: `Failed to parse model score: 'stock_code'`

**状态**: ✅ **已修复** (2026-03-01)

**说明**: 模型API返回字段名不匹配问题已修复，详见 `BUGFIX_MODEL_API_PARSING.md`

**验证修复**:
```bash
python3 quant_system/short_swing/test_model_api_fix.py
```

### 问题0.6: 非交易时间情绪分析数据错误 (已修复)

**错误现象**: 周末/盘后调用API，涨停数量为0，情绪状态不符合实际

**状态**: ✅ **已修复** (2026-03-01)

**说明**: 实现智能缓存策略，非交易时间返回上一交易日数据，详见 `BUGFIX_TRADING_TIME_CACHE.md`

**验证修复**:
```bash
python3 quant_system/short_swing/test_trading_time_cache.py
```

**重要提示**: 首次部署需在交易时间内（9:30-15:00）运行一次系统，建立缓存数据

### 问题0.7: 主线题材检测返回空数组 (已修复)

**错误现象**: API返回 `{"themes": [], "top_theme": null}`

**状态**: ✅ **已修复** (2026-03-01)

**说明**:
- 扩展了题材关键词库（新增9个题材类别，30+关键词）
- 降低了题材有效性阈值（股票数3→2，涨幅3%→2.5%）
- 详见 `BUGFIX_THEME_EMPTY.md`

**验证修复**:
```bash
python3 quant_system/short_swing/debug_theme_empty.py
```

**注意**: 非交易时间市场冷清时，题材检测可能返回空数组（正常现象）

### 问题1: 模型服务连接失败

**错误信息**: `Failed to fetch model scores: Connection refused`

**解决方案**:
```bash
# 检查模型服务是否运行（端口已改为8999）
curl http://localhost:8999/health

# 如果未运行，启动模型服务
cd /Users/tim/Documents/golang/stock_tools/es_strategy/deepmodel
python3 server_v2.py
```

### 问题2: 东方财富API请求失败

**错误信息**: `Failed to fetch market snapshot`

**可能原因**:
- 网络问题
- API限流
- 非交易时间（周末/节假日）

**解决方案**:
- 检查网络连接
- 等待1-2分钟后重试（缓存过期）
- 确认当前是交易日

### 问题3: 缓存数据库错误

**错误信息**: `sqlite3.OperationalError: unable to open database file`

**解决方案**:
```bash
# 确保目录存在
mkdir -p quant_system/short_swing
mkdir -p quant_system/logs

# 检查文件权限
chmod 755 quant_system/short_swing
```

### 问题4: 端口被占用

**错误信息**: `Address already in use: 8001`

**解决方案**:
```bash
# 查找占用端口的进程
lsof -i :8001

# 杀死进程
kill -9 <PID>

# 或修改配置文件中的端口号
```

---

## 📈 性能优化建议

1. **缓存策略**:
   - 市场数据缓存60秒
   - 模型评分缓存5分钟
   - 非交易时间可延长缓存时间

2. **批量请求**:
   - 模型API支持批量请求（最多100只股票）
   - 减少HTTP请求次数

3. **定时清理**:
```bash
# 定期清理过期缓存
python3 -c "from quant_system.short_swing.data.cache_manager import get_cache; get_cache().clear_expired()"
```

---

## ⚠️ 安全注意事项

1. **仅信号提示**:
   - 本系统不执行实际交易
   - 需配合同花顺等交易软件手动下单

2. **风险控制**:
   - 严格遵守配置文件中的风控参数
   - 建议仓位: 30-50% per stock
   - 止损: -5%, 止盈: +10%

3. **数据安全**:
   - 不收集敏感信息（账号/密码）
   - 所有数据本地缓存
   - 可删除 `short_swing.db` 清空缓存

4. **回测验证**:
   - 新策略参数建议先回测验证
   - 小仓位试运行后再扩大规模

---

## 📝 更新日志

### v1.0.0 (2026-03-01)

**初始版本发布**:
- ✅ 情绪周期判断引擎
- ✅ 主线题材识别引擎
- ✅ 选股评分系统
- ✅ RESTful API接口
- ✅ SQLite缓存机制
- ✅ 完整文档

---

## 📞 技术支持

如有问题或建议，请：
1. 查看本文档的故障排查章节
2. 检查日志文件: `quant_system/logs/short_swing.log`
3. 访问API文档: http://localhost:8001/docs

---

## 📜 免责声明

本系统为量化交易研究工具，提供的信号仅供参考，不构成任何投资建议。

用户应：
- 理解超短线交易的高风险特性
- 根据自身风险承受能力决策
- 对交易结果负全部责任

**投资有风险，入市需谨慎！**
