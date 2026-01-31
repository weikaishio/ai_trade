# 同花顺交易系统 HTTP API 服务文档

## 概述

基于 FastAPI 构建的同花顺 Mac 版自动化交易 HTTP API 服务，提供 RESTful API 接口用于远程控制同花顺进行股票交易操作。

### 核心特性

- ✅ **RESTful API**: 标准的 HTTP REST 接口
- ✅ **异步任务队列**: 单线程顺序执行 GUI 操作，避免冲突
- ✅ **JWT 认证**: 安全的令牌认证机制
- ✅ **市价买入**: 自动获取实时价格并添加价格保护
- ✅ **智能清仓**: OCR 识别持仓自动批量卖出
- ✅ **统一错误处理**: 友好的错误响应格式
- ✅ **完整日志**: 详细的请求和操作日志
- ✅ **Swagger 文档**: 自动生成的 API 交互文档

---

## 快速开始

### 1. 安装依赖

```bash
cd api_server
pip3 install -r requirements_api.txt
```

### 2. 配置环境

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置文件，修改密钥和参数
nano .env
```

**重要配置项**：

```bash
# API密钥（用于获取访问令牌）
API_KEYS=["your-secure-api-key"]

# JWT密钥
JWT_SECRET_KEY=your-jwt-secret-change-this

# 默认不自动确认订单（安全）
DEFAULT_CONFIRM=False

# 监听地址和端口
HOST=127.0.0.1
PORT=8080
```

### 3. 启动服务

```bash
# 方式1: 直接运行
python3 -m api_server.main

# 方式2: 使用 uvicorn
uvicorn api_server.main:app --host 127.0.0.1 --port 8080

# 开发模式（自动重载）
uvicorn api_server.main:app --reload
```

### 4. 访问文档

启动后访问：

- **Swagger UI**: http://127.0.0.1:8080/docs
- **ReDoc**: http://127.0.0.1:8080/redoc
- **OpenAPI JSON**: http://127.0.0.1:8080/openapi.json

---

## API 端点详解

### 基础 URL

```
http://127.0.0.1:8080/api/v1
```

### 认证流程

所有 API 调用需要在请求头中携带认证令牌：

```http
Authorization: Bearer <access_token>
```

---

## 1. 认证接口

### 1.1 获取访问令牌

**端点**: `POST /api/v1/auth/token`

**描述**: 使用 API 密钥换取 JWT 访问令牌

**请求体**:

```json
{
  "api_key": "your-api-key"
}
```

**响应**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

**示例**:

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your-api-key"}'
```

---

## 2. 交易接口

### 2.1 买入股票

**端点**: `POST /api/v1/trading/buy`

**描述**: 执行股票买入操作，支持限价和市价

**请求头**:

```http
Authorization: Bearer <access_token>
```

**请求体**:

```json
{
  "stock_code": "603993",
  "price": 24.5,
  "quantity": 100,
  "price_type": "limit",
  "confirm": false
}
```

**参数说明**:

| 参数        | 类型   | 必填 | 说明                                      |
| ----------- | ------ | ---- | ----------------------------------------- |
| stock_code  | string | ✅   | 股票代码（6位数字）                       |
| price       | float  | ⚠️   | 买入价格（限价时必填，市价时可选）        |
| quantity    | int    | ✅   | 买入数量（必须是100的倍数）               |
| price_type  | string | ❌   | 价格类型：`limit`=限价，`market`=市价     |
| confirm     | bool   | ❌   | 是否自动确认（不填则使用系统默认值）      |

**price_type 说明**:

- `limit`: 限价买入，必须指定 `price` 参数
- `market`: 市价买入，系统自动获取当前价（涨停价 × 0.99 保护）

**响应**:

```json
{
  "success": true,
  "message": "买入任务已提交",
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "data": {
    "stock_code": "603993",
    "quantity": 100,
    "price_type": "limit"
  }
}
```

**示例**:

```bash
# 限价买入
curl -X POST "http://127.0.0.1:8080/api/v1/trading/buy" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "603993",
    "price": 24.5,
    "quantity": 100,
    "price_type": "limit",
    "confirm": false
  }'

# 市价买入
curl -X POST "http://127.0.0.1:8080/api/v1/trading/buy" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "603993",
    "quantity": 100,
    "price_type": "market"
  }'
```

---

### 2.2 卖出股票

**端点**: `POST /api/v1/trading/sell`

**描述**: 执行股票卖出操作

**请求体**:

```json
{
  "stock_code": "603993",
  "price": 25.0,
  "quantity": 100,
  "confirm": false
}
```

**参数说明**:

| 参数        | 类型   | 必填 | 说明                                      |
| ----------- | ------ | ---- | ----------------------------------------- |
| stock_code  | string | ✅   | 股票代码（6位数字）                       |
| price       | float  | ✅   | 卖出价格                                  |
| quantity    | int    | ✅   | 卖出数量                                  |
| confirm     | bool   | ❌   | 是否自动确认                              |

**响应**:

```json
{
  "success": true,
  "message": "卖出任务已提交",
  "task_id": "550e8400-e29b-41d4-a716-446655440001",
  "data": {
    "stock_code": "603993",
    "price": 25.0,
    "quantity": 100
  }
}
```

**示例**:

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/trading/sell" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "603993",
    "price": 25.0,
    "quantity": 100,
    "confirm": false
  }'
```

---

### 2.3 智能清仓

**端点**: `POST /api/v1/trading/smart-clear`

**描述**: 自动识别所有持仓并批量卖出

**请求体**:

```json
{
  "use_ocr": true,
  "confirm": false,
  "use_market_price": false
}
```

**参数说明**:

| 参数              | 类型 | 必填 | 说明                                     |
| ----------------- | ---- | ---- | ---------------------------------------- |
| use_ocr           | bool | ❌   | 是否使用 OCR 识别持仓（默认 true）       |
| confirm           | bool | ❌   | 是否自动确认                             |
| use_market_price  | bool | ❌   | 是否使用市价卖出（默认 false）           |

**响应**:

```json
{
  "success": true,
  "message": "智能清仓任务已提交",
  "task_id": "550e8400-e29b-41d4-a716-446655440002",
  "data": {
    "use_ocr": true,
    "use_market_price": false
  }
}
```

**示例**:

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/trading/smart-clear" \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "use_ocr": true,
    "confirm": false
  }'
```

---

## 3. 账户查询接口

### 3.1 获取持仓列表

**端点**: `GET /api/v1/account/positions`

**描述**: 查询当前账户的所有持仓

**查询参数**:

| 参数    | 类型 | 必填 | 说明                               |
| ------- | ---- | ---- | ---------------------------------- |
| use_ocr | bool | ❌   | 是否使用 OCR 识别（默认 true）     |

**响应**:

```json
{
  "success": true,
  "message": "持仓查询成功",
  "positions": [
    {
      "stock_code": "603993",
      "stock_name": "洛阳钼业",
      "available_qty": 100,
      "current_price": 24.5
    },
    {
      "stock_code": "600000",
      "stock_name": "浦发银行",
      "available_qty": 200,
      "current_price": 10.5
    }
  ],
  "total": 2
}
```

**示例**:

```bash
curl -X GET "http://127.0.0.1:8080/api/v1/account/positions?use_ocr=true" \
  -H "Authorization: Bearer <access_token>"
```

---

### 3.2 获取委托列表

**端点**: `GET /api/v1/account/orders`

**描述**: 查询当前的所有委托订单

**查询参数**:

| 参数    | 类型 | 必填 | 说明                               |
| ------- | ---- | ---- | ---------------------------------- |
| use_ocr | bool | ❌   | 是否使用 OCR 识别（默认 true）     |

**响应**:

```json
{
  "success": true,
  "message": "委托查询成功",
  "orders": [
    {
      "stock_code": "603993",
      "direction": "买入",
      "price": 24.5,
      "quantity": 100,
      "traded_quantity": 0,
      "status": "已报"
    }
  ],
  "total": 1
}
```

**示例**:

```bash
curl -X GET "http://127.0.0.1:8080/api/v1/account/orders?use_ocr=true" \
  -H "Authorization: Bearer <access_token>"
```

---

## 4. 系统管理接口

### 4.1 获取系统状态

**端点**: `GET /api/v1/system/status`

**描述**: 查询 API 服务运行状态和统计信息

**响应**:

```json
{
  "status": "online",
  "queue_size": 2,
  "total_requests": 150,
  "successful_requests": 145,
  "failed_requests": 5,
  "uptime_seconds": 3600.5
}
```

**status 说明**:

- `online`: 在线正常
- `offline`: 离线
- `busy`: 繁忙（队列接近满载）

**示例**:

```bash
curl -X GET "http://127.0.0.1:8080/api/v1/system/status" \
  -H "Authorization: Bearer <access_token>"
```

---

### 4.2 查询任务状态

**端点**: `GET /api/v1/system/task/{task_id}`

**描述**: 查询指定任务的执行状态和结果

**路径参数**:

| 参数    | 类型   | 说明   |
| ------- | ------ | ------ |
| task_id | string | 任务ID |

**响应**:

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_type": "buy",
  "status": "completed",
  "message": "任务执行成功",
  "created_at": "2026-01-31T10:00:00",
  "started_at": "2026-01-31T10:00:01",
  "completed_at": "2026-01-31T10:00:05",
  "result": {
    "stock_code": "603993",
    "price": 24.5,
    "quantity": 100,
    "success": true
  },
  "error": null
}
```

**status 说明**:

- `pending`: 排队中
- `processing`: 执行中
- `completed`: 已完成
- `failed`: 失败
- `timeout`: 超时

**示例**:

```bash
curl -X GET "http://127.0.0.1:8080/api/v1/system/task/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer <access_token>"
```

---

### 4.3 健康检查

**端点**: `GET /api/v1/system/health`

**描述**: 简单的健康检查（不需要认证）

**响应**:

```json
{
  "status": "healthy",
  "service": "ths-trading-api",
  "version": "1.0.0"
}
```

**示例**:

```bash
curl -X GET "http://127.0.0.1:8080/api/v1/system/health"
```

---

## 完整使用流程示例

### Python 客户端示例

```python
import requests
import time

# API配置
BASE_URL = "http://127.0.0.1:8080/api/v1"
API_KEY = "your-api-key"

# 1. 获取访问令牌
def get_token():
    response = requests.post(
        f"{BASE_URL}/auth/token",
        json={"api_key": API_KEY}
    )
    return response.json()["access_token"]

# 2. 创建请求头
token = get_token()
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# 3. 市价买入股票
def market_buy(stock_code, quantity):
    response = requests.post(
        f"{BASE_URL}/trading/buy",
        headers=headers,
        json={
            "stock_code": stock_code,
            "quantity": quantity,
            "price_type": "market"
        }
    )
    return response.json()

# 4. 限价卖出股票
def limit_sell(stock_code, price, quantity):
    response = requests.post(
        f"{BASE_URL}/trading/sell",
        headers=headers,
        json={
            "stock_code": stock_code,
            "price": price,
            "quantity": quantity,
            "confirm": False
        }
    )
    return response.json()

# 5. 查询任务状态
def check_task(task_id):
    response = requests.get(
        f"{BASE_URL}/system/task/{task_id}",
        headers=headers
    )
    return response.json()

# 6. 获取持仓
def get_positions():
    response = requests.get(
        f"{BASE_URL}/account/positions?use_ocr=true",
        headers=headers
    )
    return response.json()

# 7. 智能清仓
def smart_clear():
    response = requests.post(
        f"{BASE_URL}/trading/smart-clear",
        headers=headers,
        json={
            "use_ocr": True,
            "confirm": False
        }
    )
    return response.json()

# 示例：市价买入并等待完成
result = market_buy("603993", 100)
task_id = result["task_id"]
print(f"任务已提交: {task_id}")

# 轮询任务状态
while True:
    status = check_task(task_id)
    print(f"任务状态: {status['status']}")

    if status["status"] in ["completed", "failed", "timeout"]:
        print(f"任务完成: {status}")
        break

    time.sleep(2)

# 查询持仓
positions = get_positions()
print(f"当前持仓: {positions}")
```

---

## 错误处理

所有错误响应遵循统一格式：

```json
{
  "success": false,
  "error": "ErrorType",
  "message": "错误描述",
  "details": {
    "exception": "详细异常信息"
  }
}
```

### 常见错误码

| HTTP状态码 | 错误类型                  | 说明               |
| ---------- | ------------------------- | ------------------ |
| 400        | ValueError                | 请求参数错误       |
| 401        | Unauthorized              | 认证失败           |
| 403        | Forbidden                 | IP未授权           |
| 404        | NotFound                  | 资源不存在         |
| 500        | InternalServerError       | 服务器内部错误     |

---

## 安全建议

### 1. 密钥管理

- ✅ 使用强随机字符串作为 `API_SECRET_KEY` 和 `JWT_SECRET_KEY`
- ✅ 不要在代码中硬编码密钥
- ✅ 使用环境变量或密钥管理服务
- ✅ 定期轮换密钥

### 2. 网络安全

- ✅ 仅监听 `127.0.0.1`（本地访问）
- ✅ 如需远程访问，使用 VPN 或 SSH 隧道
- ✅ 启用 IP 白名单限制访问
- ✅ 生产环境使用 HTTPS（配置反向代理）

### 3. 交易安全

- ✅ 默认 `confirm=False`，需要手动确认订单
- ✅ 设置合理的 `REQUEST_TIMEOUT` 和 `ORDER_INTERVAL`
- ✅ 监控日志文件检测异常活动
- ✅ 定期审查交易记录

---

## 性能优化

### 1. 队列配置

```bash
# 根据交易频率调整队列大小
MAX_QUEUE_SIZE=100

# 订单间隔避免触发风控
ORDER_INTERVAL=2.0
```

### 2. 日志管理

```bash
# 生产环境使用WARNING级别
LOG_LEVEL=WARNING

# 定期清理日志文件
# 可配置日志轮转
```

### 3. 资源限制

```bash
# 单线程执行（GUI自动化要求）
WORKERS=1

# 合理的超时设置
REQUEST_TIMEOUT=30
QUEUE_TIMEOUT=300
```

---

## 故障排查

### 问题1: 无法启动服务

**症状**: 运行 `python3 -m api_server.main` 报错

**解决方案**:

```bash
# 检查依赖是否安装
pip3 list | grep fastapi

# 重新安装依赖
pip3 install -r api_server/requirements_api.txt

# 检查端口是否被占用
lsof -i :8080

# 更换端口
PORT=8081 python3 -m api_server.main
```

---

### 问题2: 认证失败

**症状**: 返回 401 Unauthorized

**解决方案**:

```bash
# 检查API密钥配置
cat .env | grep API_KEYS

# 验证令牌是否过期
# 重新获取令牌

# 检查请求头格式
# 正确: Authorization: Bearer <token>
# 错误: Authorization: <token>
```

---

### 问题3: 市价买入失败

**症状**: 返回 "无法获取市价"

**解决方案**:

```bash
# 检查akshare是否安装
pip3 list | grep akshare

# 安装akshare
pip3 install akshare

# 检查配置
cat .env | grep ENABLE_AKSHARE

# 启用akshare
ENABLE_AKSHARE=True
```

---

### 问题4: OCR识别失败

**症状**: 持仓或委托查询返回空列表

**解决方案**:

```bash
# 确保同花顺窗口可见且在前台
# 检查OCR模块是否安装

# 使用手动输入模式
curl -X GET "http://127.0.0.1:8080/api/v1/account/positions?use_ocr=false" \
  -H "Authorization: Bearer <token>"
```

---

## 开发指南

### 添加新的API端点

1. 在 `api_models.py` 中定义请求/响应模型
2. 在 `api_routes.py` 中添加路由处理函数
3. 在 `trading_executor.py` 中实现业务逻辑
4. 更新本文档

### 测试

```bash
# 运行单元测试（TODO: 添加测试）
pytest tests/

# 手动测试
python3 -m api_server.main
# 访问 http://127.0.0.1:8080/docs 进行交互测试
```

---

## 许可证

本项目仅供学习研究使用，请勿用于违反法律法规的场景。

---

## 技术支持

如有问题，请参考：

1. **主项目文档**: `/README.md`
2. **故障排查**: `/TROUBLESHOOTING.md`
3. **Swagger文档**: http://127.0.0.1:8080/docs

---

**最后更新**: 2026-01-31
