#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同花顺交易API客户端示例

演示如何调用API进行交易操作
"""

import requests
import time
from typing import Optional, Dict, Any


class THSAPIClient:
    """同花顺交易API客户端"""

    def __init__(self, base_url: str = "http://127.0.0.1:8080/api/v1", api_key: str = "test-api-key"):
        """
        初始化客户端

        参数:
            base_url: API基础URL
            api_key: API密钥
        """
        self.base_url = base_url
        self.api_key = api_key
        self.access_token: Optional[str] = None

    def get_token(self) -> str:
        """
        获取访问令牌

        返回:
            JWT访问令牌
        """
        url = f"{self.base_url}/auth/token"
        response = requests.post(url, json={"api_key": self.api_key})

        if response.status_code == 200:
            data = response.json()
            self.access_token = data["access_token"]
            print(f"✅ 获取令牌成功，有效期: {data['expires_in']}秒")
            return self.access_token
        else:
            raise Exception(f"获取令牌失败: {response.text}")

    def _get_headers(self) -> Dict[str, str]:
        """
        获取请求头

        返回:
            包含认证信息的请求头
        """
        if not self.access_token:
            self.get_token()

        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def market_buy(self, stock_code: str, quantity: int, confirm: bool = False) -> Dict[str, Any]:
        """
        市价买入

        参数:
            stock_code: 股票代码
            quantity: 买入数量
            confirm: 是否自动确认

        返回:
            响应数据
        """
        url = f"{self.base_url}/trading/buy"
        data = {
            "stock_code": stock_code,
            "quantity": quantity,
            "price_type": "market",
            "confirm": confirm
        }

        response = requests.post(url, headers=self._get_headers(), json=data)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 市价买入任务已提交: {stock_code} x {quantity}")
            print(f"   任务ID: {result['task_id']}")
            return result
        else:
            raise Exception(f"市价买入失败: {response.text}")

    def limit_buy(self, stock_code: str, price: float, quantity: int, confirm: bool = False) -> Dict[str, Any]:
        """
        限价买入

        参数:
            stock_code: 股票代码
            price: 买入价格
            quantity: 买入数量
            confirm: 是否自动确认

        返回:
            响应数据
        """
        url = f"{self.base_url}/trading/buy"
        data = {
            "stock_code": stock_code,
            "price": price,
            "quantity": quantity,
            "price_type": "limit",
            "confirm": confirm
        }

        response = requests.post(url, headers=self._get_headers(), json=data)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 限价买入任务已提交: {stock_code} x {quantity} @ {price}")
            print(f"   任务ID: {result['task_id']}")
            return result
        else:
            raise Exception(f"限价买入失败: {response.text}")

    def sell(self, stock_code: str, price: float, quantity: int, confirm: bool = False) -> Dict[str, Any]:
        """
        卖出股票

        参数:
            stock_code: 股票代码
            price: 卖出价格
            quantity: 卖出数量
            confirm: 是否自动确认

        返回:
            响应数据
        """
        url = f"{self.base_url}/trading/sell"
        data = {
            "stock_code": stock_code,
            "price": price,
            "quantity": quantity,
            "confirm": confirm
        }

        response = requests.post(url, headers=self._get_headers(), json=data)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 卖出任务已提交: {stock_code} x {quantity} @ {price}")
            print(f"   任务ID: {result['task_id']}")
            return result
        else:
            raise Exception(f"卖出失败: {response.text}")

    def smart_clear(self, use_ocr: bool = True, confirm: bool = False) -> Dict[str, Any]:
        """
        智能清仓

        参数:
            use_ocr: 是否使用OCR识别持仓
            confirm: 是否自动确认

        返回:
            响应数据
        """
        url = f"{self.base_url}/trading/smart-clear"
        data = {
            "use_ocr": use_ocr,
            "confirm": confirm,
            "use_market_price": False
        }

        response = requests.post(url, headers=self._get_headers(), json=data)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 智能清仓任务已提交")
            print(f"   任务ID: {result['task_id']}")
            return result
        else:
            raise Exception(f"智能清仓失败: {response.text}")

    def get_positions(self, use_ocr: bool = True) -> Dict[str, Any]:
        """
        获取持仓列表

        参数:
            use_ocr: 是否使用OCR识别

        返回:
            持仓数据
        """
        url = f"{self.base_url}/account/positions"
        params = {"use_ocr": use_ocr}

        response = requests.get(url, headers=self._get_headers(), params=params)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 持仓查询成功，共 {result['total']} 个持仓")
            return result
        else:
            raise Exception(f"持仓查询失败: {response.text}")

    def get_orders(self, use_ocr: bool = True) -> Dict[str, Any]:
        """
        获取委托列表

        参数:
            use_ocr: 是否使用OCR识别

        返回:
            委托数据
        """
        url = f"{self.base_url}/account/orders"
        params = {"use_ocr": use_ocr}

        response = requests.get(url, headers=self._get_headers(), params=params)

        if response.status_code == 200:
            result = response.json()
            print(f"✅ 委托查询成功，共 {result['total']} 个委托")
            return result
        else:
            raise Exception(f"委托查询失败: {response.text}")

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态

        参数:
            task_id: 任务ID

        返回:
            任务状态数据
        """
        url = f"{self.base_url}/system/task/{task_id}"

        response = requests.get(url, headers=self._get_headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"任务查询失败: {response.text}")

    def wait_for_task(self, task_id: str, timeout: int = 300, interval: int = 2) -> Dict[str, Any]:
        """
        等待任务完成

        参数:
            task_id: 任务ID
            timeout: 超时时间（秒）
            interval: 轮询间隔（秒）

        返回:
            任务结果
        """
        print(f"等待任务完成: {task_id}")

        start_time = time.time()

        while True:
            # 检查超时
            if time.time() - start_time > timeout:
                raise TimeoutError(f"任务超时: {task_id}")

            # 查询任务状态
            status = self.get_task_status(task_id)

            print(f"  状态: {status['status']} - {status['message']}")

            # 检查是否完成
            if status["status"] in ["completed", "failed", "timeout"]:
                return status

            # 等待
            time.sleep(interval)

    def get_system_status(self) -> Dict[str, Any]:
        """
        获取系统状态

        返回:
            系统状态数据
        """
        url = f"{self.base_url}/system/status"

        response = requests.get(url, headers=self._get_headers())

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"系统状态查询失败: {response.text}")


# ============================================
# 使用示例
# ============================================

def main():
    """主函数 - 演示API调用"""

    print("="*70)
    print("  同花顺交易API客户端示例")
    print("="*70)

    # 创建客户端
    client = THSAPIClient(
        base_url="http://127.0.0.1:8080/api/v1",
        api_key="test-api-key"  # 修改为你的API密钥
    )

    try:
        # 1. 获取系统状态
        print("\n1. 获取系统状态")
        print("-"*70)
        status = client.get_system_status()
        print(f"系统状态: {status['status']}")
        print(f"队列长度: {status['queue_size']}")
        print(f"成功请求: {status['successful_requests']}")
        print(f"失败请求: {status['failed_requests']}")

        # 2. 查询持仓
        print("\n2. 查询持仓")
        print("-"*70)
        positions = client.get_positions(use_ocr=True)
        for pos in positions.get("positions", []):
            print(f"  {pos['stock_code']} ({pos['stock_name']})")
            print(f"    可用数量: {pos['available_qty']}")
            print(f"    当前价格: {pos['current_price']}")

        # 3. 市价买入示例（不自动确认）
        print("\n3. 市价买入示例")
        print("-"*70)
        result = client.market_buy("603993", 100, confirm=False)
        task_id = result["task_id"]

        # 等待任务完成
        task_result = client.wait_for_task(task_id)
        print(f"任务结果: {task_result['status']}")
        if task_result.get("result"):
            print(f"  执行价格: {task_result['result'].get('price')}")

        # 4. 限价卖出示例（不自动确认）
        print("\n4. 限价卖出示例")
        print("-"*70)
        result = client.sell("603993", 25.0, 100, confirm=False)
        task_id = result["task_id"]

        # 等待任务完成
        task_result = client.wait_for_task(task_id)
        print(f"任务结果: {task_result['status']}")

        # 5. 查询委托
        print("\n5. 查询委托")
        print("-"*70)
        orders = client.get_orders(use_ocr=True)
        for order in orders.get("orders", []):
            print(f"  {order['stock_code']} {order['direction']}")
            print(f"    价格: {order['price']}, 数量: {order['quantity']}")
            print(f"    状态: {order['status']}")

        print("\n"+"="*70)
        print("  ✅ 示例执行完成")
        print("="*70)

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
