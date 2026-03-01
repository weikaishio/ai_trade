<extended-thinking-tips>
Before starting implementation, think deeply about:
1. What is the essence of this requirement? New trading strategy, bug fix, system optimization, or risk control improvement?
2. Which components will be affected? GUI automation, quantitative engine, risk manager, or API server?
3. Does this involve real money operations? What are the financial risks?
4. Is coordinate recalibration needed? Will it work across different screen resolutions?
5. How will this affect trading performance and system stability?
6. What are potential failure modes and edge cases in live trading?
7. Does this require dry-run testing before live deployment?
</extended-thinking-tips>

Analyze the following requirement and provide deep analysis and implementation:

$ARGUMENTS

---

## 🚨 权威规范来源

**所有开发规范请参考：[CLAUDE.md](../../CLAUDE.md)**

这份文档是本项目的权威规范来源，包含：
- 三层架构（GUI自动化 + 量化系统 + API服务）
- 坐标系统（相对坐标 vs 绝对坐标）
- 风控机制（止损止盈、熔断、交易限制）
- OCR集成（持仓识别、订单识别）
- 配置管理（config_quant.py、环境变量）
- 安全约束（confirm=False、dry-run、测试优先）

---

## 🔄 工作流程

```
User Requirement (交易需求)
      ↓
[Stage 1] 需求分析 → 理解交易逻辑、评估风险
      ↓
[Stage 2] 方案设计 → 设计技术方案、确定安全措施
      ↓
[Stage 3] 实现规划 → 分解任务、制定测试计划
      ↓ (CHECKPOINT: 用户审批 - 必须明确风险)
[Stage 4] 代码实现 → 遵循CLAUDE.md规范
      ↓
[Stage 5] 测试验证 → Mock数据 → Dry-run → 小仓位
      ↓
[Stage 6] 安全审查 → 代码审查、风控检查
      ↓
      ├─ APPROVED → [Stage 7]
      └─ REJECTED → 返回 [Stage 4]
            ↓
[Stage 7] 文档更新 → 更新相关文档和使用指南
      ↓
Production-Ready ✅ (但仍建议谨慎使用)
```

### 关键检查点
- **Stage 3 后**: 用户必须审批方案，明确风险和测试计划
- **Stage 5**: 严格的三步测试（Mock → Dry-run → 小仓位）
- **Stage 6**: 如被拒绝，循环回 Stage 4 修复
- **全程**: 日志记录完整，所有决策可追溯

---

## 🎯 核心原则

### 1. 安全第一 - 永不妥协
- 涉及真实资金的代码必须经过充分测试
- 默认使用 `confirm=False` 和 `--dry-run`
- 任何风控参数修改必须在配置文件，不能硬编码
- 不确定时选择更保守的方案

### 2. 渐进实现 - 逐步验证
三阶段流程：
1. **Mock数据测试**: 使用模拟数据验证逻辑 → 用户确认
2. **Dry-run模式**: 真实数据但不实际交易 → 验证完整流程
3. **小仓位试运行**: 最小仓位实盘验证 → 确认无误后扩大

### 3. 每次修改后必须检查
```bash
# 坐标类修改 - 必须重新校准
python3 calibrate_helper.py

# 量化系统修改 - 先测试
python3 -m quant_system.quant_main --mode once --test --dry-run

# 检查日志
tail -f quant_system/logs/quant_system.log
```

---

## 📋 项目组件职责

| 组件 | 职责 | 关键文件 |
|----|------|---------|
| GUI自动化 | 控制THS窗口、下单执行 | ths_mac_trader.py |
| 量化引擎 | 决策生成、策略执行 | decision_engine.py, buy_strategy.py |
| 风控管理 | 风险限制、熔断保护 | risk_manager.py |
| 市场数据 | 行情获取、数据缓存 | market_data_client.py |
| 模型服务 | AI评分、信号生成 | model_client.py |
| API服务 | RESTful接口、任务队列 | api_server/main.py |

---

## 🚨 四个"不"原则

1. **不猜测** - 不确定就问用户
2. **不跳过** - 测试步骤必须完整
3. **不冒险** - 优先选择保守方案
4. **不隐瞒** - 明确告知风险和限制

---

## 📤 交付格式

```markdown
## Feature Delivered: [功能名称]

### ⚠️ 风险评估
- 涉及资金风险: 是/否
- 影响范围: [描述]
- 建议测试方案: [Mock → Dry-run → 小仓位]

### ✅ Completed:
- ✅ 功能完全实现
- ✅ CLAUDE.md规范遵守
- ✅ Mock数据测试通过
- ✅ Dry-run模式验证
- ✅ 安全检查完成
- ✅ 日志记录完整
- ✅ 文档已更新

### 📝 Files Modified:
- [文件列表及修改说明]

### 🧪 Testing Instructions:
```bash
# 步骤1: Mock数据测试
[命令]

# 步骤2: Dry-run验证
[命令]

# 步骤3: 小仓位试运行（可选）
[命令及注意事项]
```

### ⚠️ Important Notes:
- [使用注意事项]
- [已知限制]
- [风险提示]
```

---

## 🔧 技术栈速查

### Python环境
- Python 3.8+
- PyAutoGUI (GUI自动化)
- FastAPI (API服务)
- Logging (日志系统)

### 核心模式
- **坐标模式**: 相对坐标（推荐）vs 绝对坐标
- **运行模式**: 测试模式 vs 实盘模式
- **确认模式**: 手动确认 vs 自动确认
- **数据模式**: Mock数据 vs 真实数据

### 配置文件
- `config_quant.py` - 量化系统配置
- `api_server/config.py` - API服务配置
- `ths_mac_trader.py` - 坐标配置（coords_relative）
- 环境变量 - 敏感信息（THS_ACCOUNT, THS_PASSWORD）

---

## 💡 典型场景处理

### 场景1: 新增交易策略
1. 在 `config_quant.py` 定义参数
2. 在 `buy_strategy.py` 或自定义模块实现逻辑
3. Mock数据测试 → Dry-run验证
4. 文档记录策略逻辑和风险

### 场景2: 修改风控参数
1. **必须**在 `config_quant.py` 修改，不能硬编码
2. 评估新参数的风险影响
3. 在测试模式充分验证
4. 更新相关文档

### 场景3: GUI坐标调整
1. 使用 `calibrate_helper.py` 重新校准
2. 更新 `coords_relative` 字典
3. 使用选项2测试新坐标
4. 确保相对坐标模式启用

### 场景4: OCR功能优化
1. 参考 `docs/OCR_GUIDE.md`
2. 校准OCR区域坐标
3. 测试多种真实数据
4. 添加价格修正规则（如需要）
