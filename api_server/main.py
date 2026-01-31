#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同花顺交易系统 HTTP API 服务

FastAPI主应用入口
提供RESTful API用于远程控制同花顺自动交易
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import sys
import os
from typing import Union

from .config import get_settings
from .api_routes import router
from .trading_executor import executor
from .api_models import ErrorResponse

# 配置日志
settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(settings.log_file) if settings.log_file else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)


# ============================================
# 应用生命周期管理
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时初始化，关闭时清理资源
    """
    # 启动
    logger.info("="*60)
    logger.info("同花顺交易API服务启动中...")
    logger.info("="*60)

    # 启动任务执行器
    await executor.start()
    logger.info("✅ 任务执行器已启动")

    # 显示配置信息
    logger.info(f"监听地址: {settings.host}:{settings.port}")
    logger.info(f"日志级别: {settings.log_level}")
    logger.info(f"默认确认模式: {settings.default_confirm}")
    logger.info(f"队列最大长度: {settings.max_queue_size}")

    if settings.allowed_ips:
        logger.info(f"IP白名单: {', '.join(settings.allowed_ips)}")
    else:
        logger.info("IP白名单: 未启用")

    logger.info("="*60)
    logger.info("✅ 服务启动成功")
    logger.info("="*60)

    yield

    # 关闭
    logger.info("="*60)
    logger.info("同花顺交易API服务关闭中...")
    logger.info("="*60)

    # 停止任务执行器
    await executor.stop()
    logger.info("✅ 任务执行器已停止")

    logger.info("="*60)
    logger.info("✅ 服务已关闭")
    logger.info("="*60)


# ============================================
# 创建FastAPI应用
# ============================================

app = FastAPI(
    title="同花顺交易API",
    description="基于PyAutoGUI的同花顺Mac版自动化交易API服务",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


# ============================================
# 中间件配置
# ============================================

# CORS中间件（如果需要跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    记录所有HTTP请求

    包括请求路径、方法、客户端IP和响应状态码
    """
    client_ip = request.client.host
    method = request.method
    path = request.url.path

    logger.info(f"📨 {method} {path} from {client_ip}")

    try:
        response = await call_next(request)
        logger.info(f"✅ {method} {path} -> {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"❌ {method} {path} -> Error: {e}", exc_info=True)
        raise


# ============================================
# 异常处理器
# ============================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    全局异常处理器

    捕获所有未处理的异常并返回统一格式的错误响应
    """
    logger.error(f"全局异常: {exc}", exc_info=True)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            success=False,
            error="InternalServerError",
            message="服务器内部错误",
            details={"exception": str(exc)}
        ).dict()
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """
    值错误处理器

    处理输入验证错误
    """
    logger.warning(f"值错误: {exc}")

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            success=False,
            error="ValueError",
            message="请求参数错误",
            details={"exception": str(exc)}
        ).dict()
    )


# ============================================
# 挂载路由
# ============================================

app.include_router(
    router,
    prefix="/api/v1",
    tags=["API v1"]
)


# ============================================
# 根路径
# ============================================

@app.get("/", tags=["Root"])
async def root():
    """
    API根路径

    返回服务基本信息和文档链接
    """
    return {
        "service": "同花顺交易API",
        "version": "1.0.0",
        "description": "基于PyAutoGUI的同花顺Mac版自动化交易API服务",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        },
        "endpoints": {
            "auth": "/api/v1/auth/token",
            "trading": {
                "buy": "/api/v1/trading/buy",
                "sell": "/api/v1/trading/sell",
                "smart_clear": "/api/v1/trading/smart-clear"
            },
            "account": {
                "positions": "/api/v1/account/positions",
                "orders": "/api/v1/account/orders"
            },
            "system": {
                "status": "/api/v1/system/status",
                "health": "/api/v1/system/health"
            }
        }
    }


# ============================================
# 启动入口
# ============================================

def main():
    """
    主函数

    使用uvicorn启动FastAPI应用
    """
    import uvicorn

    logger.info("启动uvicorn服务器...")

    uvicorn.run(
        "api_server.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.reload,
        log_level=settings.log_level.lower()
    )


if __name__ == "__main__":
    main()
