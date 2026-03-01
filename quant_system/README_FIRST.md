# 🚀 量化交易系统 - 从这里开始

欢迎使用智能量化交易系统！这是您开始使用系统的第一步。

## 📋 快速导航

### 新手入门（按顺序阅读）

1. **[安装指南](INSTALL.md)** ⬅️ 从这里开始
   - 系统要求
   - 安装步骤
   - 依赖配置
   - 故障排查

2. **[快速启动](QUICKSTART_QUANT.md)** 
   - 5分钟上手
   - 运行示例
   - 常见场景
   - 快速测试

3. **[完整文档](README_QUANT.md)**
   - 系统功能
   - 使用方法
   - API文档
   - 最佳实践

### 进阶学习

4. **[架构文档](ARCHITECTURE.md)**
   - 系统设计
   - 模块说明
   - 数据流图
   - 扩展指南

5. **[项目总结](PROJECT_SUMMARY.md)**
   - 项目概览
   - 技术特点
   - 使用场景
   - 性能指标

### 参考资料

- **[测试脚本](test_quant_system.py)** - 运行测试验证安装
- **[使用示例](example_usage.py)** - 代码使用示例
- **[配置文件](config_quant.py)** - 系统配置说明
- **[交付清单](DELIVERY_CHECKLIST.md)** - 项目交付详情

## 🎯 30秒快速开始

```bash
# 1. 安装依赖
cd quant_system
pip3 install -r requirements_quant.txt

# 2. 创建目录
mkdir -p logs data/risk

# 3. 运行测试
python3 test_quant_system.py

# 4. 快速体验（使用模拟数据）
python3 quant_main.py --mode once --test --dry-run
```

## 📊 系统概览

```
智能量化交易系统
├── 实时行情获取 (腾讯股票API)
├── 深度学习评分 (模型API集成)
├── 智能决策引擎 (多维度分析)
├── 风险管理系统 (熔断保护)
├── FastAPI服务 (RESTful API)
└── 自动化交易 (定时监控)
```

## 🔥 核心特性

✅ **智能决策** - 多维度综合分析，AI辅助决策  
✅ **风险控制** - 多层风控机制，熔断保护  
✅ **实时监控** - 自动化循环，实时行情追踪  
✅ **易于使用** - 命令行/API/代码三种方式  
✅ **安全可靠** - 测试模式，模拟运行  
✅ **完整文档** - 详尽文档，丰富示例  

## ⚡ 三种使用方式

### 1. 命令行模式

```bash
# 单次分析
python3 quant_main.py --mode once --dry-run

# 自动监控
python3 quant_main.py --mode auto --interval 300
```

### 2. API服务模式

```bash
# 启动服务
python3 quant_api.py

# 访问文档
open http://localhost:8000/docs
```

### 3. Python代码模式

```python
from quant_main import QuantTradingSystem

system = QuantTradingSystem(test_mode=True, dry_run=True)
system.run_once()
```

## 📁 项目结构

```
quant_system/
├── config_quant.py              # 配置管理
├── market_data_client.py        # 市场数据
├── model_client.py              # 模型客户端
├── decision_engine.py           # 决策引擎
├── risk_manager.py              # 风险管理
├── quant_api.py                 # API服务
├── quant_main.py                # 主程序
├── test_quant_system.py         # 测试脚本
├── example_usage.py             # 使用示例
├── requirements_quant.txt       # 依赖清单
└── 📚 文档/
    ├── README_FIRST.md          # 本文件
    ├── INSTALL.md               # 安装指南
    ├── QUICKSTART_QUANT.md      # 快速启动
    ├── README_QUANT.md          # 完整文档
    ├── ARCHITECTURE.md          # 架构文档
    ├── PROJECT_SUMMARY.md       # 项目总结
    └── DELIVERY_CHECKLIST.md    # 交付清单
```

## ⚠️ 重要提示

### 安全第一

- ✅ **首次使用必须开启测试模式**
- ✅ **模拟运行验证逻辑正确性**
- ✅ **实盘前至少测试1周**
- ✅ **设置合理的风控参数**

### 风险警告

⚠️ 本系统仅供学习和研究使用  
⚠️ 股市有风险，投资需谨慎  
⚠️ 使用者需自行承担风险  

## 🆘 遇到问题？

### 安装问题
查看 [INSTALL.md](INSTALL.md) 的故障排查部分

### 使用问题
查看 [README_QUANT.md](README_QUANT.md) 的常见问题部分

### 配置问题
查看 [config_quant.py](config_quant.py) 的配置说明

## 📞 获取帮助

1. 阅读相关文档
2. 运行测试脚本验证
3. 查看示例代码
4. 检查日志文件

## 🎓 学习路径

### 初级用户
1. 安装系统
2. 运行测试
3. 使用测试模式
4. 理解基本概念

### 中级用户
1. 调整配置参数
2. 自定义决策规则
3. 集成实际交易
4. 优化策略参数

### 高级用户
1. 扩展新功能
2. 集成新数据源
3. 开发自定义策略
4. 性能优化调优

## 🌟 下一步

准备好了吗？从 [安装指南](INSTALL.md) 开始您的量化交易之旅！

---

**版本**: v1.0.0  
**更新**: 2026-01-31  
**祝您投资顺利！** 💰
