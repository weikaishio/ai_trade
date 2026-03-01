"""
FastAPI路由定义

提供REST API接口供前端调用。
"""

import logging
from fastapi import APIRouter, HTTPException

from ..data.models import (
    SentimentResponse,
    ThemesResponse,
    CandidatesRequest,
    CandidatesResponse,
)
from ..engines.sentiment_engine import SentimentEngine
from ..engines.theme_detector import ThemeDetector
from ..engines.stock_scorer import StockScorer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["short_swing"])

# 初始化引擎实例
sentiment_engine = SentimentEngine()
theme_detector = ThemeDetector()
stock_scorer = StockScorer()


@router.get("/sentiment", response_model=SentimentResponse)
async def get_sentiment():
    """
    获取当前市场情绪状态

    Returns:
        情绪状态对象
    """
    try:
        logger.info("API: /sentiment called")
        sentiment = sentiment_engine.analyze_sentiment()

        return SentimentResponse(
            success=True,
            sentiment=sentiment,
            message=sentiment_engine.get_trading_advice(sentiment),
        )

    except Exception as e:
        logger.error(f"Failed to analyze sentiment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/themes", response_model=ThemesResponse)
async def get_themes():
    """
    获取当前市场主线题材

    Returns:
        题材列表
    """
    try:
        logger.info("API: /themes called")
        themes = theme_detector.detect_themes()
        top_theme = themes[0] if themes else None

        return ThemesResponse(
            success=True,
            themes=themes,
            top_theme=top_theme,
            message=f"检测到 {len(themes)} 个主线题材" if themes else "暂无明显主线题材",
        )

    except Exception as e:
        logger.error(f"Failed to detect themes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/candidates", response_model=CandidatesResponse)
async def get_candidates(request: CandidatesRequest):
    """
    获取选股候选列表

    Args:
        request: 选股请求参数

    Returns:
        候选股票列表
    """
    try:
        logger.info(f"API: /candidates called (limit={request.limit}, min_score={request.min_score})")

        # 获取情绪状态
        sentiment = sentiment_engine.analyze_sentiment()

        # 获取主线题材
        themes = theme_detector.detect_themes()

        # 生成候选列表
        candidates = stock_scorer.generate_candidates(
            sentiment=sentiment,
            themes=themes,
            limit=request.limit,
            min_score=request.min_score,
        )

        # 过滤排除列表
        if request.exclude_codes:
            candidates = [c for c in candidates if c.code not in request.exclude_codes]

        return CandidatesResponse(
            success=True,
            candidates=candidates,
            sentiment_state=sentiment.state,
            total_count=len(candidates),
            message=f"生成 {len(candidates)} 个候选股票（情绪状态: {sentiment.state}）",
        )

    except Exception as e:
        logger.error(f"Failed to generate candidates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    健康检查接口

    Returns:
        服务状态
    """
    return {
        "status": "ok",
        "service": "short_swing_signal_system",
        "version": "1.0.0",
    }
