# 智能量化交易系统

基于深度学习和实时行情的智能量化交易系统，集成腾讯股票API、深度学习模型评分和自动交易执行。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                   量化交易系统                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 市场数据客户端 │  │ 模型客户端    │  │ 决策引擎      │ │
│  │              │  │              │  │              │ │
│  │ 腾讯股票API   │  │ 深度学习API   │  │ 多维度分析    │ │
│  │ 实时行情      │  │ 综合评分      │  │ 交易信号生成  │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 风险管理器    │  │ FastAPI服务  │  │ 主程序        │ │
│  │              │  │              │  │              │ │
│  │ 风控熔断      │  │ RESTful API  │  │ 自动化循环    │ │
│  │ 交易记录      │  │ Web界面      │  │ 手动分析      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## 核心功能

### 1. 市场数据获取
- **腾讯股票API**: 实时行情数据
- **批量查询**: 支持多股票同时查询
- **智能缓存**: 减少API调用，提升性能
- **数据解析**: 自动解析股票代码、价格、涨跌幅、成交量等

### 2. 深度学习评分
- **模型集成**: 连接深度学习模型API
- **综合评分**: 0-100分评分体系
- **推荐建议**: strong_sell, sell, hold, buy, strong_buy
- **置信度**: 评估模型预测可信度

### 3. 智能决策引擎
- **多维度分析**:
  - 模型评分 (权重50%)
  - 价格趋势 (权重20%)
  - 盈亏状态 (权重20%)
  - 持仓时间 (权重10%)
- **决策规则**:
  - 止损止盈机制
  - 持仓时间警告
  - 涨跌停检测
  - 黑白名单管理

### 4. 风险管理
- **交易限制**:
  - 单日交易次数限制
  - 单笔交易金额限制
  - 最小交易间隔
- **风险控制**:
  - 单日亏损熔断
  - ST股票特殊限制
  - 仓位比例控制
- **记录追踪**:
  - 交易记录持久化
  - 风险统计分析
  - 胜率计算

### 5. API服务
- **RESTful接口**:
  - `/api/v1/quant/market-data` - 获取市场数据
  - `/api/v1/quant/model-score` - 获取模型评分
  - `/api/v1/quant/analyze-positions` - 分析持仓
  - `/api/v1/quant/auto-trade` - 自动交易
  - `/api/v1/quant/status` - 系统状态

## 快速开始

### 1. 安装依赖

```bash
cd quant_system
pip3 install -r requirements_quant.txt
```

### 2. 配置系统

编辑 `config_quant.py`:

```python
# 模型API地址
MODEL_API_URL = "http://localhost:5000/comprehensive_score_custom_api"

# 决策阈值
SCORE_THRESHOLDS = {
    "strong_sell": 30,
    "sell": 40,
    "hold": 60,
    "buy": 80
}

# 止损止盈
STOP_LOSS = -0.10        # 亏损10%止损
STOP_PROFIT = 0.20       # 盈利20%止盈

# 测试模式
TEST_MODE = True         # True: 使用模拟数据
DRY_RUN = True           # True: 不实际交易
```

### 3. 运行方式

#### 方式一: 命令行模式

```bash
# 单次分析模式（推荐首次使用）
python3 quant_main.py --mode once --dry-run

# 自动监控模式
python3 quant_main.py --mode auto --interval 300

# 测试模式（使用模拟数据）
python3 quant_main.py --mode once --test --dry-run
```

#### 方式二: API服务模式

```bash
# 启动API服务
python3 quant_api.py

# 访问API文档
open http://localhost:8000/docs
```

#### 方式三: Python代码调用

```python
from quant_main import QuantTradingSystem

# 创建系统实例
system = QuantTradingSystem(test_mode=True, dry_run=True)

# 单次分析
system.run_once()

# 自动监控
system.run_auto(interval=300)
```

## 完整使用流程

### 流程1: 手动分析模式

```bash
# 1. 启动系统
python3 quant_main.py --mode once --dry-run

# 2. 系统会自动：
#    - 获取持仓（OCR或手动输入）
#    - 获取实时行情
#    - 调用模型评分
#    - 执行决策分析
#    - 风险检查
#    - 生成交易建议

# 3. 查看输出报告
```

### 流程2: API调用模式

```bash
# 1. 启动API服务
python3 quant_api.py

# 2. 调用API分析持仓
curl -X POST "http://localhost:8000/api/v1/quant/analyze-positions" \
  -H "Content-Type: application/json" \
  -d '{
    "positions": [
      {
        "code": "600483",
        "name": "福能股份",
        "quantity": 100,
        "cost_price": 24.50,
        "holding_days": 10
      }
    ],
    "total_portfolio_value": 100000
  }'

# 3. 查看返回的交易建议
```

### 流程3: 自动化循环模式

```bash
# 1. 配置自动化参数
# 编辑 config_quant.py:
AUTO_CHECK_INTERVAL = 300  # 5分钟检查一次

# 2. 启动自动监控
python3 quant_main.py --mode auto

# 3. 系统会定时：
#    - 检查交易时间
#    - 刷新持仓数据
#    - 执行分析和交易
#    - 记录日志
```

## 数据流详解

### 完整数据流

```
1. 持仓识别
   ├─ OCR识别（推荐）
   ├─ 手动输入
   └─ 模拟数据

2. 市场数据获取
   ├─ 批量查询腾讯API
   ├─ 解析股票信息
   └─ 更新持仓当前价

3. 模型评分
   ├─ 构造请求数据
   ├─ 调用深度学习API
   └─ 解析评分结果

4. 决策分析
   ├─ 多维度综合分析
   │  ├─ 模型评分分析
   │  ├─ 实时行情分析
   │  ├─ 盈亏状态分析
   │  └─ 持仓时间分析
   └─ 生成交易信号

5. 风险检查
   ├─ 熔断状态检查
   ├─ 交易时间检查
   ├─ 交易次数限制
   ├─ 交易金额检查
   └─ 仓位比例检查

6. 执行交易
   ├─ 模拟模式：仅记录
   └─ 实盘模式：调用THSMacTrader

7. 记录和统计
   ├─ 保存交易记录
   ├─ 更新统计数据
   └─ 生成日报
```

## 配置参数说明

### 决策阈值

```python
SCORE_THRESHOLDS = {
    "strong_sell": 30,    # 评分<30: 强烈卖出
    "sell": 40,           # 评分30-40: 建议卖出
    "hold": 60,           # 评分40-60: 持有观望
    "buy": 80             # 评分>60: 可考虑持有
}
```

### 止损止盈

```python
STOP_LOSS = -0.10         # 亏损10%强制止损
STOP_PROFIT = 0.20        # 盈利20%止盈
EMERGENCY_STOP_LOSS = -0.15  # 紧急止损线15%
```

### 风控参数

```python
MAX_DAILY_TRADES = 10     # 单日最大交易10次
MAX_POSITION_RATIO = 0.3  # 单股最大仓位30%
DAILY_LOSS_LIMIT = -0.05  # 单日亏损5%触发熔断
```

### 决策权重

```python
DECISION_WEIGHTS = {
    "model_score": 0.5,      # 模型评分权重50%
    "price_trend": 0.2,      # 价格趋势权重20%
    "profit_loss": 0.2,      # 盈亏状态权重20%
    "holding_time": 0.1      # 持仓时间权重10%
}
```

## API文档

### 1. 获取市场数据

**请求**:
```bash
POST /api/v1/quant/market-data
Content-Type: application/json

{
  "stock_codes": ["600483", "603993"],
  "use_cache": true
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "600483": {
      "code": "600483",
      "name": "福能股份",
      "current_price": 24.50,
      "change_percent": -2.5,
      "volume": 50000
    }
  },
  "count": 1
}
```

### 2. 获取模型评分

**请求**:
```bash
POST /api/v1/quant/model-score
Content-Type: application/json

{
  "stock_code": "600483",
  "current_price": 24.50,
  "holding_days": 10,
  "profit_loss_ratio": -0.05
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "stock_code": "600483",
    "score": 35.6,
    "recommendation": "sell",
    "confidence": 0.82
  }
}
```

### 3. 分析持仓

**请求**:
```bash
POST /api/v1/quant/analyze-positions
Content-Type: application/json

{
  "positions": [
    {
      "code": "600483",
      "name": "福能股份",
      "quantity": 100,
      "cost_price": 24.50,
      "holding_days": 10
    }
  ],
  "total_portfolio_value": 100000
}
```

**响应**:
```json
{
  "success": true,
  "data": {
    "signals": [
      {
        "signal": {
          "stock_code": "600483",
          "action": "sell",
          "priority": 2,
          "quantity": 100,
          "confidence": 0.85
        },
        "risk_report": {
          "passed": true,
          "risk_level": "medium"
        }
      }
    ],
    "summary": {
      "total_positions": 1,
      "sell_signals": 1
    }
  }
}
```

## 测试和调试

### 单元测试

```bash
# 测试市场数据客户端
python3 market_data_client.py

# 测试模型客户端
python3 model_client.py

# 测试决策引擎
python3 decision_engine.py

# 测试风险管理器
python3 risk_manager.py
```

### 集成测试

```bash
# 使用模拟数据测试完整流程
python3 quant_main.py --mode once --test --dry-run
```

### API测试

```bash
# 启动服务
python3 quant_api.py

# 访问Swagger文档
open http://localhost:8000/docs

# 健康检查
curl http://localhost:8000/api/v1/quant/health
```

## 日志和监控

### 日志文件

```
logs/
├── quant_system.log      # 主系统日志
└── uvicorn.log           # API服务日志
```

### 交易记录

```
data/risk/
├── trades_20260131.jsonl  # 交易记录
└── stats_20260131.json    # 统计数据
```

### 日志级别

```python
# 修改日志级别
logging.basicConfig(level=logging.DEBUG)  # DEBUG, INFO, WARNING, ERROR
```

## 安全注意事项

### 1. 测试模式
- **首次使用必须开启测试模式**: `TEST_MODE = True`
- **模拟运行验证逻辑**: `DRY_RUN = True`
- **使用模拟数据测试**: `MOCK_DATA_ENABLED = True`

### 2. 实盘前检查
- ✅ 确认模型API地址正确
- ✅ 验证决策阈值合理
- ✅ 测试风控参数有效
- ✅ 检查交易时间设置
- ✅ 确认止损止盈线合理

### 3. 风险控制
- 设置合理的单日交易次数限制
- 启用熔断机制
- 监控单日亏损
- 定期检查交易记录
- 及时调整策略参数

## 扩展和定制

### 添加新的决策因子

编辑 `decision_engine.py`:

```python
def _analyze_custom_factor(self, position, reasons):
    """自定义分析因子"""
    # 添加你的分析逻辑
    signal = 0.0
    reasons.append("自定义因子分析结果")
    return signal
```

### 集成新的数据源

编辑 `market_data_client.py`:

```python
class CustomDataClient:
    """自定义数据客户端"""
    def get_data(self, code):
        # 实现你的数据获取逻辑
        pass
```

### 自定义风控规则

编辑 `risk_manager.py`:

```python
def _check_custom_rule(self, report):
    """自定义风控规则"""
    # 添加你的风控逻辑
    return True
```

## 故障排查

### 问题1: 无法获取市场数据

**原因**: 腾讯API访问失败

**解决**:
- 检查网络连接
- 验证股票代码格式
- 查看日志详细错误信息

### 问题2: 模型评分失败

**原因**: 深度学习API不可用

**解决**:
- 检查MODEL_API_URL配置
- 确认模型服务运行中
- 使用health_check测试连接

### 问题3: OCR识别失败

**原因**: OCR模块未安装或截图质量差

**解决**:
- 安装ocr_positions模块
- 使用清晰的持仓截图
- 改用手动输入模式

## 性能优化

### 1. 缓存优化
- 启用智能缓存: `CACHE_ENABLED = True`
- 调整缓存时间: `CACHE_TTL = 60`

### 2. 批量查询
- 使用批量接口减少网络请求
- 合并多个股票查询

### 3. 并发处理
- 使用异步请求（Future）
- 多线程处理大量持仓

## 版本历史

### v1.0.0 (2026-01-31)
- ✅ 完整的量化交易系统
- ✅ 市场数据集成
- ✅ 深度学习模型集成
- ✅ 智能决策引擎
- ✅ 风险管理系统
- ✅ FastAPI服务
- ✅ 自动化循环
- ✅ 完整文档

## 贡献指南

欢迎贡献代码和建议！

### 开发流程
1. Fork项目
2. 创建特性分支
3. 编写代码和测试
4. 提交Pull Request

### 代码规范
- 遵循PEP 8
- 使用类型提示
- 编写文档字符串
- 添加单元测试

## 许可证

MIT License

## 联系方式

- 项目地址: `/Users/tim/Documents/golang/auto_trade/quant_system`
- 文档: `README_QUANT.md`
- 问题反馈: 创建Issue

## 致谢

- 腾讯股票API提供实时行情数据
- FastAPI提供高性能Web框架
- THSMacTrader提供交易执行能力

---

**警告**: 本系统仅供学习和研究使用。股市有风险，投资需谨慎。使用本系统进行实盘交易需自行承担风险。
