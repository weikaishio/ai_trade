# 超短线交易信号系统 - 实现完成总结

> 完成时间: 2026-03-01
> 版本: v1.0.0
> 状态: ✅ 全部完成

---

## 📋 项目概览

### 系统定位
基于**情绪周期判断**和**主线题材识别**的超短线交易信号提示系统。

### 核心价值
- ✅ 自动判断市场情绪状态（5种周期）
- ✅ 识别主线题材和龙头股
- ✅ 多因子选股评分（模型 + 情绪 + 题材）
- ✅ RESTful API，易于集成
- ✅ 完善的缓存机制，优化性能

### 安全特性
- ⚠️ **仅提供信号建议，不执行交易**
- ⚠️ **所有风控参数配置化管理**
- ⚠️ **完整的日志记录和审计**

---

## 🏗️ 系统架构

### 目录结构

```
quant_system/short_swing/
├── README.md                         # 完整使用文档
├── QUICKSTART.md                     # 快速启动指南
├── IMPLEMENTATION_SUMMARY.md         # 本文档
├── requirements.txt                  # 依赖清单
├── example_usage.py                  # 使用示例
├── main.py                           # FastAPI服务入口
├── config_short_swing.py             # 配置文件（所有参数）
├── engines/                          # 核心引擎
│   ├── sentiment_engine.py           # 情绪周期判断引擎
│   ├── theme_detector.py             # 主线题材识别引擎
│   └── stock_scorer.py               # 选股评分系统
├── data/                             # 数据层
│   ├── models.py                     # Pydantic数据模型
│   ├── data_fetcher.py               # 数据获取（东方财富+模型API）
│   └── cache_manager.py              # SQLite缓存管理器
└── api/                              # API层
    └── routes.py                     # FastAPI路由定义
```

### 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| **后端框架** | FastAPI | 异步高性能Web框架 |
| **数据验证** | Pydantic | 数据模型和验证 |
| **数据获取** | Requests | HTTP客户端 |
| **缓存** | SQLite | 轻量级数据库 |
| **日志** | Python logging | 标准日志模块 |
| **数据源** | 东方财富API | 市场行情数据 |
| **模型服务** | server_v2.py (port 5000) | 深度学习评分 |

---

## 🎯 核心功能实现

### 1. 情绪周期判断引擎 (`sentiment_engine.py`)

**功能**:
- 实时分析市场数据，判断当前情绪状态
- 5种情绪周期：freezing/warming/heating/climax/ebbing
- 基于涨停数量、涨幅分布、量比综合判断
- 提供交易建议和适合交易判断

**核心算法**:
```python
判断逻辑优先级:
1. 退潮期（最高优先级）: 下跌占比>55% + 放量>1.5倍
2. 高潮期: 涨停数量>60
3. 升温期: 涨停30-60 + 平均涨幅1.5-2.5% + 上涨占比45-60%
4. 回暖期: 涨停10-30 + 平均涨幅0.5-1.5% + 上涨占比30-45%
5. 冰点期（默认）: 其他情况
```

**接口**:
- `GET /api/v1/sentiment`
- 返回: 情绪状态 + 置信度 + 交易建议

### 2. 主线题材识别引擎 (`theme_detector.py`)

**功能**:
- 从涨停股和强势股中识别主线题材
- 基于关键词聚类（芯片/新能源/AI/医药等）
- 识别题材龙头股
- 计算题材强度评分（0-100分）

**龙头股识别标准**:
1. 涨停优先（+50分）
2. 量比放大>2倍（+20分）
3. 涨幅加成（涨幅×2分）
4. 最低评分50分才认定为龙头

**接口**:
- `GET /api/v1/themes`
- 返回: 题材列表 + 最强题材 + 龙头股信息

### 3. 选股评分系统 (`stock_scorer.py`)

**功能**:
- 整合市场数据、模型评分、情绪周期
- 生成选股候选列表
- 综合评分（0-100分）
- 信号分级（strong_buy/buy/watch/ignore）

**评分公式**:
```python
最终评分 =
  基础分（模型综合分）× 0.3 +
  涨停概率 × 0.4 × 100 +
  下跌风险 × (-0.3) × 100 +
  缠论风险 × (-0.2) × 100 +
  情绪周期加成 × 0.1 × 100 +
  主题加成（10分）
```

**超短线过滤条件**:
- 价格 ≤ 30元
- 量比 > 1.2
- 换手率 > 3%
- 市值 10-100亿
- 排除ST股票
- 排除涨停/跌停

**接口**:
- `POST /api/v1/candidates`
- 请求参数: limit, min_score, exclude_codes
- 返回: 候选列表 + 情绪状态 + 总数

### 4. 数据获取层 (`data_fetcher.py`)

**功能**:
- 从东方财富API获取市场数据
- 调用模型服务获取评分
- 支持重试机制（最多3次）
- 自动缓存（减少API调用）

**数据接口**:
- `get_market_snapshot()` - 全市场快照（5000只股票）
- `get_limit_up_stocks()` - 涨停股票列表
- `get_stock_info(code)` - 股票基本信息
- `get_model_scores(codes)` - 批量模型评分

**缓存策略**:
- 市场数据: 60秒
- 模型评分: 5分钟
- 股票信息: 1小时

### 5. 缓存管理器 (`cache_manager.py`)

**功能**:
- SQLite本地缓存
- 支持分类管理（market_data/model_score/stock_info）
- 自动过期清理
- 缓存统计

**核心方法**:
- `get(key, category)` - 获取缓存
- `set(key, value, category, ttl)` - 设置缓存
- `clear_expired()` - 清理过期数据
- `get_stats()` - 获取统计信息

---

## ⚙️ 配置管理

所有参数在 `config_short_swing.py` 集中管理，禁止硬编码。

### 核心配置项

**1. 情绪周期阈值** (`SENTIMENT_THRESHOLDS`):
- 5种状态的判断条件（涨停数/涨幅/占比）
- 可根据市场特征调整

**2. 选股评分权重** (`STOCK_SCORING_WEIGHTS`):
- 涨停概率: 40%
- 下跌风险: -30%（负权重）
- 缠论风险: -20%（负权重）
- 情绪加成: 10%

**3. 超短线过滤** (`SHORT_SWING_FILTERS`):
- 价格/量比/换手率/市值限制
- ST股票排除
- 新股排除（60天内）

**4. 风控参数** (`POSITION_MANAGEMENT`, `STOP_LOSS_PROFIT`):
- 单股仓位: 30-50%
- 止损: -5%
- 止盈: +10%
- 日亏损限制: -3%

**5. API服务** (`API_CONFIG`):
- 端口: 8001
- CORS配置
- Debug模式

---

## 🔌 API接口文档

### Base URL
```
http://localhost:8001/api/v1
```

### 接口列表

| 接口 | 方法 | 功能 | 响应时间 |
|------|------|------|---------|
| `/sentiment` | GET | 获取市场情绪状态 | ~2s |
| `/themes` | GET | 获取主线题材 | ~3s |
| `/candidates` | POST | 获取选股候选 | ~5s |
| `/health` | GET | 健康检查 | <100ms |

### 详细说明

**1. GET /api/v1/sentiment**

响应示例:
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
    "description": "市场活跃度提升，情绪升温"
  },
  "message": "市场情绪升温，积极参与，但要注意仓位控制"
}
```

**2. GET /api/v1/themes**

响应示例:
```json
{
  "success": true,
  "themes": [
    {
      "theme_name": "芯片",
      "stocks": [...],
      "leader_stock": {
        "code": "sh688981",
        "name": "中芯国际",
        "change_percent": 8.5,
        "is_leader": true
      },
      "avg_change_percent": 6.8,
      "stock_count": 12,
      "score": 88.5
    }
  ],
  "top_theme": {...}
}
```

**3. POST /api/v1/candidates**

请求体:
```json
{
  "limit": 20,
  "min_score": 75,
  "exclude_codes": []
}
```

响应示例:
```json
{
  "success": true,
  "candidates": [
    {
      "code": "sh603501",
      "name": "韦尔股份",
      "price": 24.56,
      "change_percent": 5.2,
      "final_score": 82.3,
      "signal": "strong_buy",
      "theme": "芯片",
      "is_leader": false,
      "limit_up_prob": 0.75,
      "downside_risk": 0.15
    }
  ],
  "sentiment_state": "heating",
  "total_count": 15
}
```

---

## 📦 依赖说明

### 必需依赖

```
fastapi>=0.104.0          # Web框架
uvicorn[standard]>=0.24.0 # ASGI服务器
pydantic>=2.0.0           # 数据验证
requests>=2.31.0          # HTTP客户端
```

### 外部服务依赖

**1. 模型服务** (必需)
- 路径: `/Users/tim/Documents/golang/stock_tools/es_strategy/deepmodel/server_v2.py`
- 端口: 5000
- 功能: 提供深度学习模型评分

**2. 东方财富API** (必需)
- URL: `https://push2.eastmoney.com/api`
- 功能: 提供市场行情数据
- 限制: 需注意API限流

---

## 🚀 部署与运行

### 标准启动流程

```bash
# 1. 启动模型服务（终端1）
cd /Users/tim/Documents/golang/stock_tools/es_strategy/deepmodel
python3 server_v2.py

# 2. 启动超短线系统（终端2）
cd /Users/tim/Documents/golang/auto_trade
python3 -m quant_system.short_swing.main

# 3. 验证服务
curl http://localhost:8001/api/v1/health

# 4. 运行示例（终端3）
python3 quant_system/short_swing/example_usage.py
```

### 访问地址

- **API文档**: http://localhost:8001/docs
- **ReDoc文档**: http://localhost:8001/redoc
- **健康检查**: http://localhost:8001/api/v1/health

---

## 🧪 测试建议

### 功能测试

**1. 基础功能测试**:
```bash
# 测试情绪判断
curl http://localhost:8001/api/v1/sentiment | jq .

# 测试题材识别
curl http://localhost:8001/api/v1/themes | jq .

# 测试选股
curl -X POST http://localhost:8001/api/v1/candidates \
  -H "Content-Type: application/json" \
  -d '{"limit": 5, "min_score": 70}' | jq .
```

**2. 性能测试**:
```bash
# 第一次请求（无缓存）
time curl http://localhost:8001/api/v1/sentiment

# 第二次请求（有缓存）- 应该明显更快
time curl http://localhost:8001/api/v1/sentiment
```

**3. 异常处理测试**:
```bash
# 测试错误参数
curl -X POST http://localhost:8001/api/v1/candidates \
  -H "Content-Type: application/json" \
  -d '{"limit": -1, "min_score": 200}'  # 应返回验证错误
```

### 模型服务依赖测试

**确保模型服务正常**:
```bash
# 测试模型服务健康
curl http://localhost:5000/health

# 测试模型评分接口
curl -X POST http://localhost:5000/comprehensive_score_custom_api \
  -H "Content-Type: application/json" \
  -d '{"codes": ["600519", "000001"]}'
```

---

## 📊 日志管理

### 日志配置

- **日志文件**: `quant_system/logs/short_swing.log`
- **日志级别**: INFO
- **日志格式**: 时间 - 模块 - 级别 - 消息
- **日志轮转**: 10MB / 5个备份

### 查看日志

```bash
# 实时查看日志
tail -f quant_system/logs/short_swing.log

# 查看错误日志
grep ERROR quant_system/logs/short_swing.log

# 查看API调用日志
grep "API:" quant_system/logs/short_swing.log
```

---

## ⚠️ 重要注意事项

### 1. 系统定位

**✅ 仅提供信号建议**
- 不执行实际交易
- 需配合同花顺等交易软件手动下单
- 所有信号仅供参考

### 2. 风险控制

**建议参数**:
- 单股仓位: 30-50%
- 止损: -5%
- 止盈: +10%
- 日亏损限制: -3%

**操作建议**:
- 严格遵守配置文件中的风控参数
- 不同情绪状态调整策略
- 退潮期立即减仓

### 3. 数据准确性

**注意事项**:
- 市场数据有60秒缓存
- 模型评分有5分钟缓存
- 非交易时间数据可能陈旧
- 东方财富API可能限流

### 4. 性能优化

**建议**:
- 首次启动会较慢（无缓存）
- 后续请求会明显加快
- 定期清理过期缓存
- 非交易时间可延长缓存时间

---

## 🔧 故障排查

### 常见问题

**Q1: 模型服务连接失败**
```
错误: Failed to fetch model scores: Connection refused
解决:
1. 确认模型服务是否启动: curl http://localhost:5000/health
2. 检查端口是否正确（默认5000）
3. 查看模型服务日志
```

**Q2: 东方财富API请求失败**
```
错误: Failed to fetch market snapshot
解决:
1. 检查网络连接
2. 确认是否交易时间
3. 等待1-2分钟后重试（可能是限流）
```

**Q3: 端口被占用**
```
错误: Address already in use: 8001
解决:
1. lsof -i :8001 查找占用进程
2. kill -9 <PID> 杀死进程
3. 或修改配置文件端口号
```

**Q4: 缓存数据库错误**
```
错误: sqlite3.OperationalError
解决:
1. mkdir -p quant_system/short_swing
2. chmod 755 quant_system/short_swing
3. 删除 short_swing.db 重建数据库
```

---

## 📈 后续优化方向

### 功能增强

1. **更精准的题材识别**
   - 接入概念板块API
   - 使用NLP技术分析新闻
   - 题材持续性跟踪

2. **模型优化**
   - 增加更多模型维度
   - 动态调整评分权重
   - 机器学习优化参数

3. **风控增强**
   - 资金管理模块
   - 风险敞口监控
   - 回撤控制

4. **可视化**
   - Web前端界面
   - 实时图表展示
   - 历史回测功能

### 性能优化

1. **缓存优化**
   - Redis替代SQLite
   - 更智能的缓存策略
   - 预加载机制

2. **并发优化**
   - 异步数据获取
   - 批量处理优化
   - 连接池管理

---

## 📞 技术支持

### 文档资源

- **完整文档**: `README.md`
- **快速启动**: `QUICKSTART.md`
- **示例代码**: `example_usage.py`
- **API文档**: http://localhost:8001/docs

### 调试工具

```bash
# 查看系统状态
curl http://localhost:8001/api/v1/health

# 查看日志
tail -f quant_system/logs/short_swing.log

# 清理缓存
python3 -c "from quant_system.short_swing.data.cache_manager import get_cache; get_cache().clear_expired()"

# 查看缓存统计
python3 -c "from quant_system.short_swing.data.cache_manager import get_cache; import json; print(json.dumps(get_cache().get_stats(), indent=2))"
```

---

## ✅ 验收清单

**核心功能**:
- [x] 情绪周期判断引擎（5种状态）
- [x] 主线题材识别引擎
- [x] 选股评分系统
- [x] FastAPI服务和路由
- [x] 数据获取和缓存

**文档**:
- [x] 完整使用文档（README.md）
- [x] 快速启动指南（QUICKSTART.md）
- [x] 实现总结（本文档）
- [x] 示例代码（example_usage.py）
- [x] 依赖清单（requirements.txt）

**代码质量**:
- [x] 类型提示（Type Hints）
- [x] 文档字符串（Docstrings）
- [x] 错误处理（Try-Except）
- [x] 日志记录（Logging）
- [x] 配置管理（Config File）

**测试**:
- [x] 健康检查接口
- [x] API文档页面
- [x] 示例脚本可运行
- [x] 缓存机制正常

---

## 🎉 总结

超短线交易信号系统已**全部完成**！

**交付成果**:
- ✅ 16个文件
- ✅ 3个核心引擎（情绪/题材/评分）
- ✅ 4个API接口
- ✅ 完整的缓存机制
- ✅ 详细的使用文档

**系统特点**:
- 🔥 基于情绪周期和主线题材的超短线选股
- 🔥 整合深度学习模型评分
- 🔥 RESTful API，易于集成
- 🔥 所有参数配置化管理
- 🔥 完善的日志和错误处理

**使用提醒**:
- ⚠️ 仅信号提示，不执行交易
- ⚠️ 严格遵守风控参数
- ⚠️ 投资有风险，决策需谨慎

---

**立即开始使用**:

```bash
# 启动模型服务
cd /Users/tim/Documents/golang/stock_tools/es_strategy/deepmodel
python3 server_v2.py

# 启动超短线系统
cd /Users/tim/Documents/golang/auto_trade
python3 -m quant_system.short_swing.main

# 运行示例
python3 quant_system/short_swing/example_usage.py
```

祝您交易顺利！📈
