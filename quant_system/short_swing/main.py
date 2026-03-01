"""
超短线交易信号系统主程序

FastAPI服务入口。
"""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from quant_system.short_swing.api.routes import router
from quant_system.short_swing.config_short_swing import API_CONFIG, LOGGING_CONFIG

# 配置日志
logging.basicConfig(
    level=getattr(logging, LOGGING_CONFIG["level"]),
    format=LOGGING_CONFIG["format"],
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOGGING_CONFIG["log_file"], encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="超短线交易信号系统",
    description="基于情绪周期和主线题材的超短线交易信号提示系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=API_CONFIG["cors_origins"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """服务启动时执行"""
    logger.info("=" * 60)
    logger.info("超短线交易信号系统启动中...")
    logger.info(f"版本: 1.0.0")
    logger.info(f"服务地址: http://{API_CONFIG['host']}:{API_CONFIG['port']}")
    logger.info(f"API文档: http://localhost:{API_CONFIG['port']}/docs")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """服务关闭时执行"""
    logger.info("超短线交易信号系统关闭")


def main():
    """主函数"""
    uvicorn.run(
        "quant_system.short_swing.main:app",
        host=API_CONFIG["host"],
        port=API_CONFIG["port"],
        reload=API_CONFIG.get("debug", False),
        log_level="info",
    )


if __name__ == "__main__":
    main()
