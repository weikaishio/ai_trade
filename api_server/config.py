#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API服务配置管理模块

支持通过环境变量和.env文件配置
使用 pydantic-settings 进行类型安全的配置管理
"""

from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """API服务配置类"""

    # 服务器配置
    host: str = "127.0.0.1"
    port: int = 8080
    workers: int = 1  # GUI自动化必须单线程
    reload: bool = False  # 生产环境禁用热重载

    # API安全配置
    api_secret_key: str = "your-secret-key-change-this-in-production"
    api_keys: List[str] = ["test-api-key"]  # 允许的API密钥列表

    # JWT配置
    jwt_secret_key: str = "your-jwt-secret-change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # IP白名单（空列表表示不限制）
    allowed_ips: List[str] = []  # 例如: ["127.0.0.1", "192.168.1.100"]

    # 交易默认配置
    default_confirm: bool = False  # 默认不自动确认订单（安全考虑）
    request_timeout: int = 30  # 请求超时时间（秒）
    order_interval: float = 2.0  # 订单之间的间隔时间（秒）

    # 队列配置
    max_queue_size: int = 100  # 最大队列长度
    queue_timeout: int = 300  # 队列任务超时时间（秒）

    # 日志配置
    log_level: str = "INFO"
    log_file: Optional[str] = "api_server.log"

    # 同花顺应用配置
    ths_app_name: str = "同花顺"
    ths_use_relative_coords: bool = True

    # 市价保护配置
    market_price_protection: float = 0.99  # 市价买入时使用涨停价的99%

    # akshare配置（用于获取实时行情）
    enable_akshare: bool = True  # 是否启用akshare获取市价

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    获取配置单例
    使用缓存确保全局只有一个配置实例
    """
    return Settings()
