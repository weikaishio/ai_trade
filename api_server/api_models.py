#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API数据模型定义

使用 Pydantic 进行数据验证和序列化
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


# ============================================
# 枚举类型定义
# ============================================

class PriceType(str, Enum):
    """价格类型枚举"""
    LIMIT = "limit"  # 限价
    MARKET = "market"  # 市价


class TradeDirection(str, Enum):
    """交易方向枚举"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """订单状态枚举"""
    PENDING = "pending"  # 排队中
    PROCESSING = "processing"  # 执行中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"  # 失败
    TIMEOUT = "timeout"  # 超时


# ============================================
# 请求模型
# ============================================

class BuyRequest(BaseModel):
    """买入请求"""
    stock_code: str = Field(..., description="股票代码", min_length=6, max_length=6)
    price: Optional[float] = Field(None, description="买入价格（市价时可不填）", gt=0)
    quantity: int = Field(..., description="买入数量", gt=0)
    price_type: PriceType = Field(PriceType.LIMIT, description="价格类型: limit=限价, market=市价")
    confirm: Optional[bool] = Field(None, description="是否自动确认（不填则使用系统默认值）")

    @validator("stock_code")
    def validate_stock_code(cls, v):
        """验证股票代码格式"""
        if not v.isdigit():
            raise ValueError("股票代码必须是6位数字")
        return v

    @validator("quantity")
    def validate_quantity(cls, v):
        """验证数量必须是100的倍数（A股规则）"""
        if v % 100 != 0:
            raise ValueError("买入数量必须是100的倍数")
        return v

    @validator("price")
    def validate_price_with_type(cls, v, values):
        """验证价格：限价时必填，市价时可选"""
        if "price_type" in values:
            if values["price_type"] == PriceType.LIMIT and v is None:
                raise ValueError("限价买入时必须指定价格")
        return v


class SellRequest(BaseModel):
    """卖出请求"""
    stock_code: str = Field(..., description="股票代码", min_length=6, max_length=6)
    price: float = Field(..., description="卖出价格", gt=0)
    quantity: int = Field(..., description="卖出数量", gt=0)
    confirm: Optional[bool] = Field(None, description="是否自动确认")

    @validator("stock_code")
    def validate_stock_code(cls, v):
        if not v.isdigit():
            raise ValueError("股票代码必须是6位数字")
        return v


class SmartClearRequest(BaseModel):
    """智能清仓请求"""
    use_ocr: bool = Field(True, description="是否使用OCR识别持仓")
    confirm: Optional[bool] = Field(None, description="是否自动确认")
    use_market_price: bool = Field(False, description="是否使用市价")


class TokenRequest(BaseModel):
    """认证令牌请求"""
    api_key: str = Field(..., description="API密钥")


# ============================================
# 响应模型
# ============================================

class Position(BaseModel):
    """持仓信息"""
    stock_code: str = Field(..., description="股票代码")
    stock_name: str = Field("", description="股票名称")
    available_qty: int = Field(..., description="可用数量")
    current_price: float = Field(0.0, description="当前价格")


class Order(BaseModel):
    """委托订单信息"""
    stock_code: str = Field(..., description="股票代码")
    direction: str = Field(..., description="交易方向")
    price: float = Field(..., description="委托价格")
    quantity: int = Field(..., description="委托数量")
    traded_quantity: int = Field(0, description="已成交数量")
    status: str = Field("", description="订单状态")


class TaskResponse(BaseModel):
    """任务响应"""
    task_id: str = Field(..., description="任务ID")
    status: OrderStatus = Field(..., description="任务状态")
    message: str = Field("", description="状态消息")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")


class TradeResponse(BaseModel):
    """交易响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="响应消息")
    task_id: Optional[str] = Field(None, description="任务ID（异步模式）")
    data: Optional[dict] = Field(None, description="额外数据")


class PositionsResponse(BaseModel):
    """持仓列表响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field("", description="响应消息")
    positions: List[Position] = Field([], description="持仓列表")
    total: int = Field(0, description="持仓总数")


class OrdersResponse(BaseModel):
    """委托列表响应"""
    success: bool = Field(..., description="是否成功")
    message: str = Field("", description="响应消息")
    orders: List[Order] = Field([], description="委托列表")
    total: int = Field(0, description="委托总数")


class SystemStatus(BaseModel):
    """系统状态"""
    status: Literal["online", "offline", "busy"] = Field(..., description="系统状态")
    queue_size: int = Field(0, description="当前队列长度")
    total_requests: int = Field(0, description="总请求数")
    successful_requests: int = Field(0, description="成功请求数")
    failed_requests: int = Field(0, description="失败请求数")
    uptime_seconds: float = Field(0.0, description="运行时长（秒）")


class TokenResponse(BaseModel):
    """令牌响应"""
    access_token: str = Field(..., description="访问令牌")
    token_type: str = Field("bearer", description="令牌类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class ErrorResponse(BaseModel):
    """错误响应"""
    success: bool = Field(False, description="是否成功")
    error: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误消息")
    details: Optional[dict] = Field(None, description="详细信息")
