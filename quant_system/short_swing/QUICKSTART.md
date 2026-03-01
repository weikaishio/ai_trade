# 超短线信号系统 - 快速启动指南

> 5分钟快速上手超短线交易信号系统

---

## ⚡ 一分钟启动

### 前提条件

✅ 确保模型服务已启动（端口5000）

```bash
# 在另一个终端窗口运行
cd /Users/tim/Documents/golang/stock_tools/es_strategy/deepmodel
python3 server_v2.py
```

### 安装依赖

```bash
cd /Users/tim/Documents/golang/auto_trade
pip3 install fastapi uvicorn pydantic requests
```

### 启动服务

```bash
python3 -m quant_system.short_swing.main
```

看到以下信息表示启动成功：

```
============================================================
超短线交易信号系统启动中...
版本: 1.0.0
服务地址: http://0.0.0.0:8001
API文档: http://localhost:8001/docs
============================================================
```

---

## 🎯 三步获取交易信号

### 方法1: 使用API文档（推荐新手）

1. 浏览器打开: **http://localhost:8001/docs**
2. 点击任意接口，如 `GET /api/v1/sentiment`
3. 点击 "Try it out" → "Execute"
4. 查看响应结果

### 方法2: 使用示例脚本

```bash
python3 quant_system/short_swing/example_usage.py
```

会自动运行4个示例：
- 获取市场情绪状态
- 获取主线题材
- 获取选股候选
- 综合分析流程

### 方法3: 使用cURL命令

```bash
# 1. 获取市场情绪
curl http://localhost:8001/api/v1/sentiment

# 2. 获取主线题材
curl http://localhost:8001/api/v1/themes

# 3. 获取选股候选（评分≥75）
curl -X POST http://localhost:8001/api/v1/candidates \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "min_score": 75}'
```

---

## 📊 如何解读信号

### 情绪状态解读

| 状态 | 含义 | 操作建议 |
|------|------|---------|
| `freezing` | 冰点期 | 空仓观望，等待回暖 |
| `warming` | 回暖期 | 小仓位试探，关注龙头 |
| `heating` | 升温期 | 积极参与，控制仓位 |
| `climax` | 高潮期 | 谨慎追高，随时减仓 |
| `ebbing` | 退潮期 | 立即减仓或清仓 |

### 信号类型解读

| 信号 | 评分范围 | 操作建议 |
|------|---------|---------|
| `strong_buy` | ≥85分 | 强烈建议，优先关注 |
| `buy` | 75-84分 | 建议买入 |
| `watch` | 65-74分 | 关注观察 |
| `ignore` | <65分 | 忽略 |

---

## 🔧 常见问题

### Q1: 服务启动失败？

**检查模型服务**:
```bash
curl http://localhost:5000/health
```

如果失败，先启动模型服务：
```bash
cd /Users/tim/Documents/golang/stock_tools/es_strategy/deepmodel
python3 server_v2.py
```

### Q2: 端口被占用？

修改配置文件 `config_short_swing.py`:
```python
API_CONFIG = {
    "port": 8002,  # 改为其他端口
}
```

### Q3: 获取不到数据？

可能原因：
- 非交易时间（周末/节假日）
- 网络问题
- API限流

等待1-2分钟后重试。

### Q4: 如何自定义参数？

编辑 `quant_system/short_swing/config_short_swing.py`

例如修改选股过滤条件：
```python
SHORT_SWING_FILTERS = {
    "max_price": 20.0,         # 改为20元以下
    "min_volume_ratio": 2.0,   # 改为量比>2
}
```

修改后重启服务生效。

---

## 📱 前端集成（可选）

系统提供标准RESTful API，可以轻松集成到Web/移动端。

**API端点**:
- `GET /api/v1/sentiment` - 获取情绪状态
- `GET /api/v1/themes` - 获取主线题材
- `POST /api/v1/candidates` - 获取选股候选

**CORS配置**: 已支持跨域请求

**示例（JavaScript）**:
```javascript
// 获取选股候选
fetch('http://localhost:8001/api/v1/candidates', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ limit: 10, min_score: 75 })
})
.then(res => res.json())
.then(data => {
  console.log('候选股票:', data.candidates);
});
```

---

## ⚠️ 重要提示

1. **仅信号提示**
   - 系统不执行交易
   - 需手动下单

2. **风险控制**
   - 单股仓位: 30-50%
   - 止损: -5%
   - 止盈: +10%

3. **数据延迟**
   - 市场数据缓存60秒
   - 模型评分缓存5分钟
   - 实时性要求高时可减少缓存时间

4. **免责声明**
   - 信号仅供参考
   - 投资有风险，决策需谨慎

---

## 📚 更多文档

- [完整使用文档](README.md)
- [API接口文档](http://localhost:8001/docs)
- [配置说明](config_short_swing.py)
- [示例代码](example_usage.py)

---

## 🚀 开始使用

```bash
# 1. 启动模型服务（另一个终端）
cd /Users/tim/Documents/golang/stock_tools/es_strategy/deepmodel
python3 server_v2.py

# 2. 启动超短线系统
cd /Users/tim/Documents/golang/auto_trade
python3 -m quant_system.short_swing.main

# 3. 运行示例
python3 quant_system/short_swing/example_usage.py
```

祝您交易顺利！ 📈
