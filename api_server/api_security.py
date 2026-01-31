#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API安全认证模块

提供API密钥认证和JWT令牌认证
"""

from fastapi import Security, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta
from jose import JWTError, jwt
from typing import Optional
import logging

from .config import get_settings

logger = logging.getLogger(__name__)

security = HTTPBearer()
settings = get_settings()


# ============================================
# JWT令牌管理
# ============================================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建JWT访问令牌

    参数:
        data: 要编码的数据字典
        expires_delta: 过期时间增量

    返回:
        JWT令牌字符串
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_minutes
        )

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def verify_token(token: str) -> dict:
    """
    验证JWT令牌

    参数:
        token: JWT令牌字符串

    返回:
        解码后的载荷数据

    异常:
        HTTPException: 令牌无效或过期
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        logger.warning(f"JWT验证失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================
# API密钥认证
# ============================================

def verify_api_key(api_key: str) -> bool:
    """
    验证API密钥是否有效

    参数:
        api_key: API密钥

    返回:
        是否有效
    """
    return api_key in settings.api_keys


async def get_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> str:
    """
    从请求头获取并验证API密钥

    FastAPI依赖注入函数，用于保护需要认证的端点

    参数:
        credentials: HTTP Authorization凭证

    返回:
        验证通过的API密钥

    异常:
        HTTPException: 认证失败
    """
    api_key = credentials.credentials

    if not verify_api_key(api_key):
        logger.warning(f"无效的API密钥尝试: {api_key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的API密钥",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return api_key


# ============================================
# JWT令牌认证
# ============================================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """
    从JWT令牌获取当前用户信息

    FastAPI依赖注入函数，用于保护需要JWT认证的端点

    参数:
        credentials: HTTP Authorization凭证

    返回:
        用户信息字典

    异常:
        HTTPException: 认证失败
    """
    token = credentials.credentials
    payload = verify_token(token)
    return payload


# ============================================
# IP白名单验证
# ============================================

async def verify_ip_whitelist(request: Request):
    """
    验证请求IP是否在白名单中

    FastAPI依赖注入函数

    参数:
        request: FastAPI请求对象

    异常:
        HTTPException: IP不在白名单中
    """
    # 如果没有配置白名单，则跳过验证
    if not settings.allowed_ips:
        return

    client_ip = request.client.host

    if client_ip not in settings.allowed_ips:
        logger.warning(f"拒绝来自未授权IP的请求: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"IP地址 {client_ip} 未被授权访问"
        )


# ============================================
# 组合认证依赖
# ============================================

async def verify_request(
    request: Request,
    api_key: str = Security(get_api_key)
):
    """
    组合认证：同时验证IP白名单和API密钥

    FastAPI依赖注入函数，用于需要完整认证的端点

    参数:
        request: FastAPI请求对象
        api_key: API密钥（通过get_api_key获取）

    异常:
        HTTPException: 认证失败
    """
    await verify_ip_whitelist(request)
    return api_key
