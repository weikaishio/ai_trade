Ultra think:

<extended-thinking-tips>
在开始实现之前，请深入思考以下方面：
1. 需求的本质是什么？是新功能、bug修复、重构还是优化？
2. 这个需求会影响哪些现有组件？需要修改哪些文件？
3. 有哪些潜在的风险点和边界情况需要考虑？
4. 实现顺序应该如何安排才能最高效？
</extended-thinking-tips>

分析以下需求并在auto_trade平台项目中实现：

$ARGUMENTS

---

## 执行指导

### 1. 需求分析阶段
- 如果是新功能需求或架构变更，首先使用 requirements-analyst-team agent 进行深入分析
- 理解需求对现有架构的影响，确保与项目所使用框架和架构的组件化设计一致

### 2. 实现规划
根据需求类型选择合适的执行路径：

**后端开发任务** (涉及Python代码、组件实现、API开发)：
- 使用 python-expert-developer agent 实现具体的逻辑

**全栈任务**：
- 先用 requirements-analyst-team 分析需求
- 按照 API定义 → 服务开发 → 测试用例开发验证 的顺序实现

### 5. 项目上下文
- **架构**：FastAPI web服务框架，分层架构，支持不同类型模型部署，用yaml配置文件管理
- **数据存储**：如果有需要：mysql持久化存储 + redis缓存
- **开发环境**：python3.8+

请根据以上指导，选择合适的agents并按照ZEUS目录规范实现需求。