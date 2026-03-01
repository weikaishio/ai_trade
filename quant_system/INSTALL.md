# 量化交易系统安装指南

## 系统要求

### 最低要求
- **操作系统**: macOS 10.14+ / Linux / Windows 10+
- **Python**: 3.8+
- **内存**: 2GB+
- **磁盘**: 500MB+

### 推荐配置
- **Python**: 3.9+
- **内存**: 4GB+
- **网络**: 稳定的互联网连接

## 安装步骤

### 第1步: 检查Python版本

```bash
python3 --version
# 应输出: Python 3.8.x 或更高
```

如果Python版本过低，请先升级Python。

### 第2步: 进入项目目录

```bash
cd /Users/tim/Documents/golang/auto_trade/quant_system
```

### 第3步: 安装依赖

#### 方式A: 使用pip安装（推荐）

```bash
pip3 install -r requirements_quant.txt
```

#### 方式B: 逐个安装核心依赖

```bash
# 核心框架
pip3 install fastapi uvicorn pydantic

# HTTP客户端
pip3 install requests urllib3

# 数据处理（可选）
pip3 install pandas numpy
```

### 第4步: 创建必要目录

```bash
mkdir -p logs data/risk
```

### 第5步: 验证安装

```bash
python3 -c "
from config_quant import *
from market_data_client import MarketDataClient
from model_client import ModelClient
from decision_engine import DecisionEngine
from risk_manager import RiskManager
print('✓ 所有核心模块导入成功！')
"
```

如果看到 "✓ 所有核心模块导入成功！"，说明安装成功。

## 配置系统

### 1. 基础配置

编辑 `config_quant.py`，根据需要修改以下参数：

```python
# 测试模式（首次使用必须开启）
TEST_MODE = True          # True: 测试模式
DRY_RUN = True            # True: 模拟运行
MOCK_DATA_ENABLED = True  # True: 使用模拟数据

# 模型API配置（如果有深度学习模型服务）
MODEL_API_URL = "http://localhost:5000/comprehensive_score_custom_api"

# 决策阈值（根据风险偏好调整）
SCORE_THRESHOLDS = {
    "strong_sell": 30,    # 评分<30: 强烈卖出
    "sell": 40,           # 评分30-40: 建议卖出
    "hold": 60,           # 评分40-60: 持有
    "buy": 80             # 评分>60: 可考虑持有
}

# 止损止盈
STOP_LOSS = -0.10         # 亏损10%止损
STOP_PROFIT = 0.20        # 盈利20%止盈

# 风控参数
MAX_DAILY_TRADES = 10     # 单日最大交易10次
DAILY_LOSS_LIMIT = -0.05  # 单日亏损5%触发熔断
```

### 2. 高级配置

如果需要连接实际的深度学习模型API，设置环境变量：

```bash
export MODEL_API_URL="http://your-model-server:5000/api"
```

## 快速测试

### 测试1: 运行测试套件

```bash
python3 test_quant_system.py
```

预期输出：
```
============================================================
量化交易系统测试套件
============================================================

测试市场数据客户端
============================================================
✓ 福能股份 (600483): 24.50 (+2.50%)
✓ 600483: 24.50
...

✓ 所有测试完成
```

### 测试2: 运行示例代码

```bash
python3 example_usage.py
```

### 测试3: 快速分析（使用模拟数据）

```bash
python3 quant_main.py --mode once --test --dry-run
```

## 常见安装问题

### 问题1: pip安装失败

**错误信息**:
```
ERROR: Could not find a version that satisfies the requirement...
```

**解决方案**:
```bash
# 升级pip
pip3 install --upgrade pip

# 重新安装
pip3 install -r requirements_quant.txt
```

### 问题2: 权限错误

**错误信息**:
```
Permission denied
```

**解决方案**:
```bash
# 使用用户安装
pip3 install --user -r requirements_quant.txt
```

### 问题3: SSL/证书错误

**错误信息**:
```
SSL: CERTIFICATE_VERIFY_FAILED
```

**解决方案**:
```bash
# macOS
/Applications/Python\ 3.x/Install\ Certificates.command

# 或使用--trusted-host
pip3 install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements_quant.txt
```

### 问题4: 模块导入失败

**错误信息**:
```
ModuleNotFoundError: No module named 'xxx'
```

**解决方案**:
```bash
# 确认安装路径
pip3 show xxx

# 检查Python路径
python3 -c "import sys; print(sys.path)"

# 重新安装
pip3 uninstall xxx
pip3 install xxx
```

## 依赖说明

### 核心依赖（必需）

| 包名 | 版本 | 用途 |
|------|------|------|
| fastapi | >=0.104.0 | Web框架 |
| uvicorn | >=0.24.0 | ASGI服务器 |
| pydantic | >=2.0.0 | 数据验证 |
| requests | >=2.31.0 | HTTP客户端 |

### 可选依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| pandas | >=2.0.0 | 数据处理 |
| numpy | >=1.24.0 | 数值计算 |
| schedule | >=1.2.0 | 定时任务 |
| akshare | >=1.11.0 | 备用数据源 |

### 开发依赖

| 包名 | 版本 | 用途 |
|------|------|------|
| pytest | >=7.4.0 | 单元测试 |
| black | >=23.0.0 | 代码格式化 |
| flake8 | >=6.0.0 | 代码检查 |

## 卸载

如果需要卸载系统：

```bash
# 卸载Python包
pip3 uninstall -r requirements_quant.txt -y

# 删除项目文件（谨慎操作！）
cd /Users/tim/Documents/golang/auto_trade
rm -rf quant_system
```

## 升级

### 升级依赖包

```bash
# 升级所有依赖到最新版本
pip3 install --upgrade -r requirements_quant.txt
```

### 检查新版本

```bash
pip3 list --outdated
```

## 故障排查

### 日志检查

如果系统运行异常，检查日志：

```bash
# 查看主日志
tail -f logs/quant_system.log

# 查看最近的错误
grep ERROR logs/quant_system.log | tail -20
```

### 配置验证

验证配置是否正确：

```bash
python3 -c "
from config_quant import *
print('模型API:', MODEL_API_URL)
print('决策阈值:', SCORE_THRESHOLDS)
print('止损线:', STOP_LOSS)
print('测试模式:', TEST_MODE)
"
```

### 网络连接测试

测试API连接：

```bash
# 测试市场数据API
curl "http://qt.gtimg.cn/q=sh600483"

# 测试模型API（如果有）
curl -X POST http://localhost:5000/comprehensive_score_custom_api \
  -H "Content-Type: application/json" \
  -d '{"stock_code": "600483"}'
```

## 下一步

安装完成后，建议：

1. ✅ 阅读快速启动指南: `QUICKSTART_QUANT.md`
2. ✅ 查看完整文档: `README_QUANT.md`
3. ✅ 运行测试模式验证功能
4. ✅ 根据需求调整配置
5. ✅ 在模拟模式下运行至少1周

## 获取帮助

### 文档资源

- **快速启动**: `QUICKSTART_QUANT.md`
- **完整文档**: `README_QUANT.md`
- **架构文档**: `ARCHITECTURE.md`
- **项目总结**: `PROJECT_SUMMARY.md`

### 测试和示例

- **测试脚本**: `test_quant_system.py`
- **使用示例**: `example_usage.py`

### 配置文件

- **系统配置**: `config_quant.py`
- **依赖清单**: `requirements_quant.txt`

---

**祝你使用愉快！** 🚀
