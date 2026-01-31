#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交易执行器模块

管理GUI自动化任务队列，确保单线程顺序执行
提供异步任务管理和状态跟踪
"""

import asyncio
import uuid
import time
import logging
from typing import Dict, Optional, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

from .config import get_settings
from .api_models import OrderStatus

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    task_type: str  # 'buy', 'sell', 'smart_clear', etc.
    params: dict
    status: OrderStatus = OrderStatus.PENDING
    message: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class TradingExecutor:
    """
    交易执行器

    单例模式，管理全局任务队列
    确保GUI自动化操作单线程顺序执行
    """

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化执行器（仅执行一次）"""
        if self._initialized:
            return

        self.tasks: Dict[str, Task] = {}  # 任务字典
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=settings.max_queue_size)
        self.is_running: bool = False
        self.worker_task: Optional[asyncio.Task] = None

        # 统计数据
        self.total_requests: int = 0
        self.successful_requests: int = 0
        self.failed_requests: int = 0
        self.start_time: float = time.time()

        # 导入交易器（延迟导入避免循环依赖）
        self.trader = None

        self._initialized = True
        logger.info("交易执行器已初始化")

    def _get_trader(self):
        """
        获取交易器实例（懒加载）

        返回:
            THSMacTrader实例
        """
        if self.trader is None:
            import sys
            import os

            # 添加父目录到路径以导入ths_mac_trader
            parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            from ths_mac_trader import THSMacTrader

            self.trader = THSMacTrader()
            self.trader.use_relative_coords = settings.ths_use_relative_coords
            logger.info("交易器实例已创建")

        return self.trader

    async def start(self):
        """启动任务处理器"""
        if self.is_running:
            logger.warning("任务处理器已在运行")
            return

        self.is_running = True
        self.worker_task = asyncio.create_task(self._process_queue())
        logger.info("任务处理器已启动")

    async def stop(self):
        """停止任务处理器"""
        if not self.is_running:
            return

        self.is_running = False

        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        logger.info("任务处理器已停止")

    async def _process_queue(self):
        """
        队列处理器（后台任务）

        持续从队列中取出任务并执行
        """
        logger.info("开始处理任务队列")

        while self.is_running:
            try:
                # 从队列获取任务（带超时）
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )

                # 执行任务
                await self._execute_task(task)

                # 标记任务完成
                self.task_queue.task_done()

                # 任务间隔
                await asyncio.sleep(settings.order_interval)

            except asyncio.TimeoutError:
                # 队列为空，继续等待
                continue
            except Exception as e:
                logger.error(f"队列处理器异常: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _execute_task(self, task: Task):
        """
        执行单个任务

        参数:
            task: 任务对象
        """
        task.status = OrderStatus.PROCESSING
        task.started_at = datetime.now()

        logger.info(f"开始执行任务 {task.task_id}: {task.task_type}")

        try:
            # 根据任务类型调用不同的执行函数
            if task.task_type == "buy":
                result = await self._execute_buy(task.params)
            elif task.task_type == "sell":
                result = await self._execute_sell(task.params)
            elif task.task_type == "smart_clear":
                result = await self._execute_smart_clear(task.params)
            else:
                raise ValueError(f"未知的任务类型: {task.task_type}")

            # 任务成功
            task.status = OrderStatus.COMPLETED
            task.message = "任务执行成功"
            task.result = result
            self.successful_requests += 1

            logger.info(f"任务 {task.task_id} 执行成功")

        except Exception as e:
            # 任务失败
            task.status = OrderStatus.FAILED
            task.message = f"任务执行失败: {str(e)}"
            task.error = str(e)
            self.failed_requests += 1

            logger.error(f"任务 {task.task_id} 执行失败: {e}", exc_info=True)

        finally:
            task.completed_at = datetime.now()

    async def _execute_buy(self, params: dict) -> dict:
        """
        执行买入任务

        参数:
            params: 买入参数（stock_code, price, quantity, price_type, confirm）

        返回:
            执行结果字典
        """
        trader = self._get_trader()

        stock_code = params["stock_code"]
        quantity = params["quantity"]
        price_type = params.get("price_type", "limit")
        confirm = params.get("confirm", settings.default_confirm)

        # 处理价格
        if price_type == "market":
            # 市价买入：获取实时价格
            price = await self._get_market_price(stock_code)
            logger.info(f"市价买入 {stock_code}: 获取到实时价格 {price}")
        else:
            # 限价买入：使用指定价格
            price = params["price"]

        # 在独立线程中执行GUI操作（避免阻塞事件循环）
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            trader.buy,
            stock_code,
            price,
            quantity,
            confirm
        )

        return {
            "stock_code": stock_code,
            "price": price,
            "quantity": quantity,
            "price_type": price_type,
            "success": success
        }

    async def _execute_sell(self, params: dict) -> dict:
        """
        执行卖出任务

        参数:
            params: 卖出参数（stock_code, price, quantity, confirm）

        返回:
            执行结果字典
        """
        trader = self._get_trader()

        stock_code = params["stock_code"]
        price = params["price"]
        quantity = params["quantity"]
        confirm = params.get("confirm", settings.default_confirm)

        # 在独立线程中执行GUI操作
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            trader.sell,
            stock_code,
            price,
            quantity,
            confirm
        )

        return {
            "stock_code": stock_code,
            "price": price,
            "quantity": quantity,
            "success": success
        }

    async def _execute_smart_clear(self, params: dict) -> dict:
        """
        执行智能清仓任务

        参数:
            params: 清仓参数（use_ocr, confirm, use_market_price）

        返回:
            执行结果字典
        """
        trader = self._get_trader()

        use_ocr = params.get("use_ocr", True)
        confirm = params.get("confirm", settings.default_confirm)
        use_market_price = params.get("use_market_price", False)

        # 在独立线程中执行GUI操作
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(
            None,
            trader.clear_all_positions,
            None,  # positions (None表示自动获取)
            confirm,
            use_market_price,
            use_ocr
        )

        return {
            "use_ocr": use_ocr,
            "use_market_price": use_market_price,
            "success": success
        }

    async def _get_market_price(self, stock_code: str) -> float:
        """
        获取股票市价

        参数:
            stock_code: 股票代码

        返回:
            当前价格（带价格保护）

        异常:
            RuntimeError: 无法获取市价
        """
        if not settings.enable_akshare:
            raise RuntimeError("akshare未启用，无法获取市价")

        try:
            import akshare as ak

            # 获取实时行情
            loop = asyncio.get_event_loop()
            df = await loop.run_in_executor(
                None,
                ak.stock_zh_a_spot_em
            )

            # 查找目标股票
            stock_data = df[df["代码"] == stock_code]

            if stock_data.empty:
                raise RuntimeError(f"未找到股票 {stock_code} 的行情数据")

            # 获取当前价和涨停价
            current_price = float(stock_data.iloc[0]["最新价"])
            limit_up_price = float(stock_data.iloc[0]["涨停价"])

            # 价格保护：使用涨停价的99%确保成交
            protected_price = limit_up_price * settings.market_price_protection

            # 返回较小值
            final_price = min(current_price, protected_price)

            logger.info(
                f"股票 {stock_code} 市价: {current_price}, "
                f"涨停价: {limit_up_price}, "
                f"保护价: {protected_price}, "
                f"最终价: {final_price}"
            )

            return final_price

        except ImportError:
            raise RuntimeError("请安装akshare: pip install akshare")
        except Exception as e:
            logger.error(f"获取市价失败: {e}", exc_info=True)
            raise RuntimeError(f"获取市价失败: {str(e)}")

    async def submit_task(self, task_type: str, params: dict) -> str:
        """
        提交新任务到队列

        参数:
            task_type: 任务类型
            params: 任务参数

        返回:
            任务ID

        异常:
            RuntimeError: 队列已满
        """
        # 生成任务ID
        task_id = str(uuid.uuid4())

        # 创建任务对象
        task = Task(
            task_id=task_id,
            task_type=task_type,
            params=params
        )

        # 添加到任务字典
        self.tasks[task_id] = task
        self.total_requests += 1

        # 加入队列
        try:
            self.task_queue.put_nowait(task)
            logger.info(f"任务 {task_id} 已加入队列 (类型: {task_type})")
        except asyncio.QueueFull:
            task.status = OrderStatus.FAILED
            task.message = "队列已满"
            self.failed_requests += 1
            raise RuntimeError("任务队列已满，请稍后重试")

        return task_id

    def get_task_status(self, task_id: str) -> Optional[Task]:
        """
        获取任务状态

        参数:
            task_id: 任务ID

        返回:
            任务对象，如果不存在则返回None
        """
        return self.tasks.get(task_id)

    def get_statistics(self) -> dict:
        """
        获取统计数据

        返回:
            统计数据字典
        """
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "queue_size": self.task_queue.qsize(),
            "uptime_seconds": time.time() - self.start_time,
            "is_running": self.is_running
        }

    async def get_positions(self, use_ocr: bool = True) -> list:
        """
        获取持仓列表

        参数:
            use_ocr: 是否使用OCR识别

        返回:
            持仓列表
        """
        trader = self._get_trader()

        loop = asyncio.get_event_loop()

        if use_ocr:
            positions = await loop.run_in_executor(
                None,
                trader.get_positions_from_ocr,
                True  # quick_mode
            )
        else:
            positions = await loop.run_in_executor(
                None,
                trader.get_positions_from_input
            )

        return positions

    async def get_orders(self, use_ocr: bool = True) -> list:
        """
        获取委托列表

        参数:
            use_ocr: 是否使用OCR识别

        返回:
            委托列表
        """
        trader = self._get_trader()

        loop = asyncio.get_event_loop()

        orders = await loop.run_in_executor(
            None,
            trader.get_orders_from_ocr,
            True  # quick_mode
        )

        return orders


# 全局执行器实例
executor = TradingExecutor()
