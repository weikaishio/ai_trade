#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API路由定义模块

定义所有API端点和业务逻辑
"""

from fastapi import APIRouter, Depends, HTTPException, status, Request
from datetime import timedelta
import logging

from .api_models import (
    BuyRequest, SellRequest, SmartClearRequest, TokenRequest,
    TradeResponse, PositionsResponse, OrdersResponse,
    SystemStatus, TokenResponse, ErrorResponse,
    Position, Order
)
from .api_security import (
    verify_request, verify_api_key, create_access_token
)
from .trading_executor import executor
from .config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# 创建路由器
router = APIRouter()


# ============================================
# 认证端点
# ============================================

@router.post(
    "/auth/token",
    response_model=TokenResponse,
    summary="获取访问令牌",
    description="使用API密钥换取JWT访问令牌"
)
async def get_token(request: TokenRequest):
    """
    获取JWT访问令牌

    用于后续API调用的身份验证
    """
    # 验证API密钥
    from .api_security import verify_api_key

    if not verify_api_key(request.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API密钥"
        )

    # 创建访问令牌
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": "api_user"},
        expires_delta=access_token_expires
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60
    )


# ============================================
# 交易端点
# ============================================

@router.post(
    "/trading/buy",
    response_model=TradeResponse,
    summary="买入股票",
    description="执行股票买入操作，支持限价和市价"
)
async def buy_stock(
    request: BuyRequest,
    api_key: str = Depends(verify_request)
):
    """
    买入股票

    支持两种价格类型：
    - limit: 限价买入，必须指定价格
    - market: 市价买入，系统自动获取当前价格（涨停价*0.99保护）

    返回任务ID，可通过 /system/task/{task_id} 查询执行状态
    """
    try:
        # 确定confirm参数
        confirm = request.confirm if request.confirm is not None else settings.default_confirm

        # 准备任务参数
        params = {
            "stock_code": request.stock_code,
            "quantity": request.quantity,
            "price_type": request.price_type.value,
            "confirm": confirm
        }

        # 限价模式需要价格
        if request.price_type.value == "limit":
            params["price"] = request.price

        # 提交任务
        task_id = await executor.submit_task("buy", params)

        logger.info(
            f"买入任务已提交: {request.stock_code} "
            f"x {request.quantity} @ {request.price_type.value}"
        )

        return TradeResponse(
            success=True,
            message="买入任务已提交",
            task_id=task_id,
            data={
                "stock_code": request.stock_code,
                "quantity": request.quantity,
                "price_type": request.price_type.value
            }
        )

    except Exception as e:
        logger.error(f"买入请求处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"买入请求处理失败: {str(e)}"
        )


@router.post(
    "/trading/sell",
    response_model=TradeResponse,
    summary="卖出股票",
    description="执行股票卖出操作"
)
async def sell_stock(
    request: SellRequest,
    api_key: str = Depends(verify_request)
):
    """
    卖出股票

    需要指定股票代码、价格和数量
    """
    try:
        # 确定confirm参数
        confirm = request.confirm if request.confirm is not None else settings.default_confirm

        # 准备任务参数
        params = {
            "stock_code": request.stock_code,
            "price": request.price,
            "quantity": request.quantity,
            "confirm": confirm
        }

        # 提交任务
        task_id = await executor.submit_task("sell", params)

        logger.info(
            f"卖出任务已提交: {request.stock_code} "
            f"x {request.quantity} @ {request.price}"
        )

        return TradeResponse(
            success=True,
            message="卖出任务已提交",
            task_id=task_id,
            data={
                "stock_code": request.stock_code,
                "price": request.price,
                "quantity": request.quantity
            }
        )

    except Exception as e:
        logger.error(f"卖出请求处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"卖出请求处理失败: {str(e)}"
        )


@router.post(
    "/trading/smart-clear",
    response_model=TradeResponse,
    summary="智能清仓",
    description="自动识别所有持仓并批量卖出"
)
async def smart_clear(
    request: SmartClearRequest,
    api_key: str = Depends(verify_request)
):
    """
    智能清仓

    自动识别所有持仓（OCR或手动输入），然后批量卖出

    use_ocr=True: 使用OCR识别持仓（需要同花顺窗口可见）
    use_market_price=True: 使用市价卖出
    """
    try:
        # 确定confirm参数
        confirm = request.confirm if request.confirm is not None else settings.default_confirm

        # 准备任务参数
        params = {
            "use_ocr": request.use_ocr,
            "confirm": confirm,
            "use_market_price": request.use_market_price
        }

        # 提交任务
        task_id = await executor.submit_task("smart_clear", params)

        logger.info(f"智能清仓任务已提交 (OCR: {request.use_ocr})")

        return TradeResponse(
            success=True,
            message="智能清仓任务已提交",
            task_id=task_id,
            data={
                "use_ocr": request.use_ocr,
                "use_market_price": request.use_market_price
            }
        )

    except Exception as e:
        logger.error(f"智能清仓请求处理失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"智能清仓请求处理失败: {str(e)}"
        )


# ============================================
# 账户查询端点
# ============================================

@router.get(
    "/account/positions",
    response_model=PositionsResponse,
    summary="获取持仓列表",
    description="查询当前账户的所有持仓"
)
async def get_positions(
    use_ocr: bool = True,
    api_key: str = Depends(verify_request)
):
    """
    获取持仓列表

    use_ocr=True: 使用OCR识别（推荐）
    use_ocr=False: 手动输入（需要交互）
    """
    try:
        positions = await executor.get_positions(use_ocr=use_ocr)

        # 转换为响应模型
        position_models = [
            Position(
                stock_code=pos.stock_code,
                stock_name=pos.stock_name,
                available_qty=pos.available_qty,
                current_price=pos.current_price
            )
            for pos in positions
        ]

        return PositionsResponse(
            success=True,
            message="持仓查询成功",
            positions=position_models,
            total=len(position_models)
        )

    except Exception as e:
        logger.error(f"持仓查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"持仓查询失败: {str(e)}"
        )


@router.get(
    "/account/orders",
    response_model=OrdersResponse,
    summary="获取委托列表",
    description="查询当前的所有委托订单"
)
async def get_orders(
    use_ocr: bool = True,
    api_key: str = Depends(verify_request)
):
    """
    获取委托列表

    使用OCR识别同花顺窗口中的委托信息
    """
    try:
        orders = await executor.get_orders(use_ocr=use_ocr)

        # 转换为响应模型
        order_models = [
            Order(
                stock_code=order.stock_code,
                direction=order.direction,
                price=order.price,
                quantity=order.quantity,
                traded_quantity=order.traded_quantity,
                status=order.status
            )
            for order in orders
        ]

        return OrdersResponse(
            success=True,
            message="委托查询成功",
            orders=order_models,
            total=len(order_models)
        )

    except Exception as e:
        logger.error(f"委托查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"委托查询失败: {str(e)}"
        )


# ============================================
# 系统管理端点
# ============================================

@router.get(
    "/system/status",
    response_model=SystemStatus,
    summary="获取系统状态",
    description="查询API服务运行状态和统计信息"
)
async def get_system_status(api_key: str = Depends(verify_request)):
    """
    获取系统状态

    返回队列状态、请求统计、运行时长等信息
    """
    try:
        stats = executor.get_statistics()

        # 判断系统状态
        if not stats["is_running"]:
            sys_status = "offline"
        elif stats["queue_size"] >= settings.max_queue_size * 0.8:
            sys_status = "busy"
        else:
            sys_status = "online"

        return SystemStatus(
            status=sys_status,
            queue_size=stats["queue_size"],
            total_requests=stats["total_requests"],
            successful_requests=stats["successful_requests"],
            failed_requests=stats["failed_requests"],
            uptime_seconds=stats["uptime_seconds"]
        )

    except Exception as e:
        logger.error(f"系统状态查询失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"系统状态查询失败: {str(e)}"
        )


@router.get(
    "/system/task/{task_id}",
    summary="查询任务状态",
    description="查询指定任务的执行状态和结果"
)
async def get_task_status(
    task_id: str,
    api_key: str = Depends(verify_request)
):
    """
    查询任务状态

    根据任务ID查询任务的当前状态、进度和结果
    """
    task = executor.get_task_status(task_id)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {task_id} 不存在"
        )

    return {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "status": task.status.value,
        "message": task.message,
        "created_at": task.created_at.isoformat(),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "result": task.result,
        "error": task.error
    }


@router.get(
    "/system/health",
    summary="健康检查",
    description="简单的健康检查端点（不需要认证）"
)
async def health_check():
    """
    健康检查

    用于负载均衡器或监控系统检查服务是否正常运行
    """
    return {
        "status": "healthy",
        "service": "ths-trading-api",
        "version": "1.0.0"
    }
