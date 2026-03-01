# 量化交易系统快速启动指南

5分钟快速上手智能量化交易系统！

## 第一步: 安装依赖 (1分钟)

```bash
cd /Users/tim/Documents/golang/auto_trade
pip3 install -r quant_system/requirements_quant.txt
```

## 第二步: 初始化环境 (30秒)

环境会自动创建，无需手动操作。

## 第三步: 选择运行模式 (3分钟)

### 模式1: 快速测试（推荐首次使用）

使用模拟数据，不实际交易，快速体验系统功能。

**重要**: 必须从项目根目录运行！

```bash
# 确保在项目根目录
cd /Users/tim/Documents/golang/auto_trade

# 以Python模块方式运行
python3 -m quant_system.quant_main --mode once --test --dry-run
```

**你会看到**:
- ✓ 系统加载模拟持仓
- ✓ 获取实时行情
- ✓ 调用模型评分（模拟）
- ✓ 执行决策分析
- ✓ 生成交易建议
- ✓ 输出详细报告

### 模式2: 真实分析（需要OCR或手动输入）

使用真实持仓数据，但仍然是模拟交易。

```bash
python3 -m quant_system.quant_main --mode once --dry-run
```

**系统会提示**:
1. 使用OCR识别持仓（如果可用）
2. 或手动输入持仓信息
3. 然后执行完整分析流程

### 模式3: API服务模式

启动Web服务，通过API调用系统功能。

```bash
# 启动服务
python3 quant_api.py

# 访问API文档
open http://localhost:8000/docs
```

## 快速配置

### 配置1: 修改决策阈值

编辑 `config_quant.py`:

```python
# 调整这些参数以匹配你的风险偏好

SCORE_THRESHOLDS = {
    "strong_sell": 30,    # 评分<30强烈卖出
    "sell": 40,           # 评分30-40建议卖出
    "hold": 60,           # 评分40-60持有
}

STOP_LOSS = -0.10         # 亏损10%止损
STOP_PROFIT = 0.20        # 盈利20%止盈
```

### 配置2: 连接模型API

```python
# 修改模型API地址
MODEL_API_URL = "http://your-model-server:5000/comprehensive_score_custom_api"
```

### 配置3: 调整风控参数

```python
MAX_DAILY_TRADES = 10     # 单日最大交易次数
DAILY_LOSS_LIMIT = -0.05  # 单日亏损5%触发熔断
```

## 常见使用场景

### 场景1: 每天开盘前分析

```bash
# 早上9点运行一次分析
python3 -m quant_system.quant_main --mode once --dry-run
```

### 场景2: 交易时段自动监控

```bash
# 交易时段每5分钟自动检查
python3 -m quant_system.quant_main --mode auto --interval 300
```

### 场景3: API集成

```python
import requests

# 分析持仓
response = requests.post(
    "http://localhost:8000/api/v1/quant/analyze-positions",
    json={
        "positions": [
            {
                "code": "600483",
                "name": "福能股份",
                "quantity": 100,
                "cost_price": 24.50,
                "holding_days": 10
            }
        ]
    }
)

print(response.json())
```

## 输出示例

运行系统后，你会看到类似这样的输出：

```
============================================================
股票: 福能股份 (600483)
动作: SELL (优先级: high)
数量: 100股 @ 23.30元
置信度: 85.0%

持仓信息:
  成本价: 24.50元
  当前价: 23.30元
  盈亏: -120.00元 (-4.90%)
  持仓天数: 10天

决策原因:
  1. 模型评分极低 (28.5/100)，强烈建议卖出
  2. 大幅下跌 (-4.90%)
  3. 触发止损线 (-4.90%，亏损120.00元)

风险评估: MEDIUM
是否通过: 是
============================================================
```

## 下一步

### 学习更多
- 阅读完整文档: `README_QUANT.md`
- 查看配置说明: `config_quant.py`
- API文档: http://localhost:8000/docs

### 实盘前准备
1. ✅ 在测试模式运行至少1周
2. ✅ 验证决策逻辑符合预期
3. ✅ 确认风控参数合理
4. ✅ 测试所有异常情况
5. ✅ 准备好止损预案

### 切换到实盘

**警告**: 实盘交易有风险，请务必充分测试！

```python
# 修改 config_quant.py
TEST_MODE = False   # 关闭测试模式
DRY_RUN = False     # 关闭模拟运行

# 首次实盘建议
MAX_DAILY_TRADES = 3      # 减少交易次数
DAILY_LOSS_LIMIT = -0.02  # 降低熔断阈值
```

## 故障排查

### 问题: 无法获取行情数据
**解决**: 检查网络连接，确认股票代码正确

### 问题: 模型API连接失败
**解决**:
```bash
# 测试API连接
python3 -c "from model_client import ModelClient; print(ModelClient().health_check())"
```

### 问题: OCR识别失败
**解决**: 使用手动输入模式或提供清晰的截图

## 联系支持

- 文档: `README_QUANT.md`
- 测试: `test_quant_system.py`
- 配置: `config_quant.py`

---

**开始你的量化交易之旅！** 🚀
