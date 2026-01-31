# 同花顺交易API - 快速入门指南

## 5分钟上手

### 第1步: 安装依赖

```bash
cd /Users/tim/Documents/golang/auto_trade/api_server
pip3 install -r requirements_api.txt
```

### 第2步: 配置服务

```bash
# 复制配置文件
cp .env.example .env

# 编辑配置（至少修改API密钥）
nano .env
```

**最小配置**:
```bash
API_KEYS=["my-secure-api-key"]
DEFAULT_CONFIRM=False
```

### 第3步: 启动服务

```bash
# 方式1: 使用启动脚本
./start_server.sh

# 方式2: 直接运行
python3 -m api_server.main

# 方式3: 使用uvicorn（开发模式）
cd ..
uvicorn api_server.main:app --reload
```

### 第4步: 测试API

打开浏览器访问：http://127.0.0.1:8080/docs

或使用curl测试：

```bash
# 获取访问令牌
TOKEN=$(curl -s -X POST "http://127.0.0.1:8080/api/v1/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"api_key": "my-secure-api-key"}' | jq -r .access_token)

echo $TOKEN

# 查询系统状态
curl -X GET "http://127.0.0.1:8080/api/v1/system/status" \
  -H "Authorization: Bearer $TOKEN"

# 市价买入（测试 - 不会实际执行）
curl -X POST "http://127.0.0.1:8080/api/v1/trading/buy" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "603993",
    "quantity": 100,
    "price_type": "market",
    "confirm": false
  }'
```

---

## 常用API示例

### 1. 市价买入

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/trading/buy" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "603993",
    "quantity": 100,
    "price_type": "market"
  }'
```

### 2. 限价卖出

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/trading/sell" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "stock_code": "603993",
    "price": 25.0,
    "quantity": 100
  }'
```

### 3. 查询持仓

```bash
curl -X GET "http://127.0.0.1:8080/api/v1/account/positions?use_ocr=true" \
  -H "Authorization: Bearer $TOKEN"
```

### 4. 智能清仓

```bash
curl -X POST "http://127.0.0.1:8080/api/v1/trading/smart-clear" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "use_ocr": true,
    "confirm": false
  }'
```

---

## Python客户端示例

```python
from api_server.example_client import THSAPIClient

# 创建客户端
client = THSAPIClient(
    base_url="http://127.0.0.1:8080/api/v1",
    api_key="my-secure-api-key"
)

# 市价买入
result = client.market_buy("603993", 100, confirm=False)
task_id = result["task_id"]

# 等待完成
task_result = client.wait_for_task(task_id)
print(f"执行结果: {task_result['status']}")

# 查询持仓
positions = client.get_positions()
for pos in positions["positions"]:
    print(f"{pos['stock_code']}: {pos['available_qty']}股")
```

---

## 注意事项

⚠️ **安全警告**:

1. **默认不自动确认**: `confirm=False` 时需要手动点击确认按钮
2. **仅本地访问**: 默认监听 `127.0.0.1`，不对外暴露
3. **妥善保管密钥**: 不要将API密钥提交到版本控制

⚠️ **使用限制**:

1. **同花顺窗口必须可见**: GUI自动化需要窗口在前台
2. **单线程执行**: 一次只能处理一个订单，避免冲突
3. **市场时间**: 仅在交易时间内使用

---

## 下一步

- 阅读完整文档: [README_API.md](README_API.md)
- 查看API交互文档: http://127.0.0.1:8080/docs
- 运行示例客户端: `python3 example_client.py`

---

**问题排查**: 如遇到问题，参考 [README_API.md](README_API.md) 的"故障排查"章节
