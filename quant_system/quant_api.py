"""
量化交易系统FastAPI服务模块

提供RESTful API端点，支持市场数据获取、模型评分、持仓分析和自动交易。
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

from .config_quant import (
    API_HOST,
    API_PORT,
    API_TITLE,
    API_VERSION,
    API_DESCRIPTION
)
from .market_data_client import MarketDataClient, StockData
from .model_client import ModelClient, ModelScore
from .decision_engine import DecisionEngine, Position, TradeSignal
from .risk_manager import RiskManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION
)

# 初始化核心组件
market_client = MarketDataClient()
model_client = ModelClient()
decision_engine = DecisionEngine()
risk_manager = RiskManager(
    data_dir="/Users/tim/Documents/golang/auto_trade/quant_system/data/risk"
)

# ============================================================================
# Pydantic模型定义
# ============================================================================

class PositionInput(BaseModel):
    """持仓输入模型"""
    code: str = Field(..., description="股票代码")
    name: str = Field(..., description="股票名称")
    quantity: int = Field(..., gt=0, description="持仓数量")
    cost_price: float = Field(..., gt=0, description="成本价")
    holding_days: int = Field(0, ge=0, description="持仓天数")


class MarketDataRequest(BaseModel):
    """市场数据请求"""
    stock_codes: List[str] = Field(..., min_items=1, description="股票代码列表")
    use_cache: bool = Field(True, description="是否使用缓存")


class ModelScoreRequest(BaseModel):
    """模型评分请求"""
    stock_code: str = Field(..., description="股票代码")
    current_price: Optional[float] = Field(None, description="当前价格")
    holding_days: Optional[int] = Field(None, description="持仓天数")
    profit_loss_ratio: Optional[float] = Field(None, description="盈亏比例")
    use_cache: bool = Field(True, description="是否使用缓存")


class AnalyzePositionsRequest(BaseModel):
    """分析持仓请求"""
    positions: List[PositionInput] = Field(..., min_items=1, description="持仓列表")
    total_portfolio_value: Optional[float] = Field(None, description="总资产价值")


class AutoTradeRequest(BaseModel):
    """自动交易请求"""
    positions: List[PositionInput] = Field(..., description="持仓列表")
    total_portfolio_value: float = Field(..., gt=0, description="总资产价值")
    dry_run: bool = Field(True, description="模拟运行（不实际交易）")
    execute_limit: Optional[int] = Field(None, description="最大执行数量")


# ============================================================================
# API端点
# ============================================================================

@app.get("/")
async def root():
    """根端点"""
    return {
        "service": API_TITLE,
        "version": API_VERSION,
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/v1/quant/status")
async def get_status():
    """
    获取系统状态

    返回系统运行状态、缓存统计、风险统计等信息
    """
    try:
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "market_client": {
                    "cache_stats": market_client.get_cache_stats()
                },
                "model_client": {
                    "cache_stats": model_client.get_cache_stats(),
                    "health": model_client.health_check()
                },
                "risk_manager": {
                    "daily_summary": risk_manager.get_daily_summary(),
                    "risk_stats": risk_manager.get_risk_statistics()
                }
            }
        }
    except Exception as e:
        logger.error(f"获取状态失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/quant/market-data")
async def get_market_data(request: MarketDataRequest):
    """
    获取市场数据

    批量获取股票实时行情数据
    """
    try:
        logger.info(f"获取市场数据: {request.stock_codes}")

        # 获取数据
        data_dict = market_client.get_batch_stock_data(
            request.stock_codes,
            use_cache=request.use_cache
        )

        # 转换为响应格式
        result = {}
        for code, stock_data in data_dict.items():
            if stock_data:
                result[code] = stock_data.to_dict()
            else:
                result[code] = None

        return {
            "success": True,
            "data": result,
            "count": len([v for v in result.values() if v is not None]),
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"获取市场数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/quant/model-score")
async def get_model_score(request: ModelScoreRequest):
    """
    获取模型评分

    调用深度学习模型API获取股票综合评分
    """
    try:
        logger.info(f"获取模型评分: {request.stock_code}")

        # 获取评分
        score = model_client.get_score(
            stock_code=request.stock_code,
            current_price=request.current_price,
            holding_days=request.holding_days,
            profit_loss_ratio=request.profit_loss_ratio,
            use_cache=request.use_cache
        )

        if not score:
            raise HTTPException(status_code=404, detail="无法获取评分")

        return {
            "success": True,
            "data": score.to_dict(),
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模型评分失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/quant/analyze-positions")
async def analyze_positions(request: AnalyzePositionsRequest):
    """
    分析持仓并给出建议

    综合市场数据、模型评分、风险评估，生成交易建议
    """
    try:
        logger.info(f"分析 {len(request.positions)} 个持仓")

        # 1. 转换持仓数据
        positions = [
            Position(
                code=p.code,
                name=p.name,
                quantity=p.quantity,
                cost_price=p.cost_price,
                holding_days=p.holding_days
            )
            for p in request.positions
        ]

        # 2. 获取市场数据
        stock_codes = [p.code for p in positions]
        market_data_dict = market_client.get_batch_stock_data(stock_codes)

        # 3. 获取模型评分
        positions_data = {}
        for pos, market_data in zip(positions, market_data_dict.values()):
            if market_data:
                pos.current_price = market_data.current_price
                positions_data[pos.code] = {
                    "current_price": market_data.current_price,
                    "holding_days": pos.holding_days,
                    "profit_loss_ratio": pos.calculate_profit_loss_ratio()
                }

        model_scores_dict = model_client.get_batch_scores(
            stock_codes,
            positions_data
        )

        # 4. 决策分析
        signals = decision_engine.analyze_positions_batch(
            positions,
            market_data_dict,
            model_scores_dict
        )

        # 5. 风险检查
        analyzed_signals = []
        for signal in signals:
            position = next(p for p in positions if p.code == signal.stock_code)

            risk_report = risk_manager.check_trade_permission(
                signal,
                position,
                request.total_portfolio_value or 0.0
            )

            analyzed_signals.append({
                "signal": signal.to_dict(),
                "risk_report": risk_report.to_dict(),
                "position_value": position.calculate_position_value(),
                "profit_loss": position.calculate_profit_loss(),
                "profit_loss_ratio": position.calculate_profit_loss_ratio()
            })

        # 6. 分类统计
        sell_signals = [s for s in signals if s.is_sell_signal()]
        high_priority = [s for s in signals if s.is_high_priority()]

        return {
            "success": True,
            "data": {
                "signals": analyzed_signals,
                "summary": {
                    "total_positions": len(positions),
                    "sell_signals": len(sell_signals),
                    "high_priority_signals": len(high_priority),
                    "total_portfolio_value": request.total_portfolio_value
                }
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"分析持仓失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/quant/auto-trade")
async def auto_trade(request: AutoTradeRequest, background_tasks: BackgroundTasks):
    """
    自动交易

    执行自动交易流程（仅在非dry_run模式下实际交易）
    """
    try:
        logger.info(f"自动交易请求: {len(request.positions)} 个持仓, dry_run={request.dry_run}")

        # 1. 分析持仓
        analyze_request = AnalyzePositionsRequest(
            positions=request.positions,
            total_portfolio_value=request.total_portfolio_value
        )
        analysis_result = await analyze_positions(analyze_request)

        if not analysis_result["success"]:
            raise HTTPException(status_code=500, detail="持仓分析失败")

        # 2. 提取卖出信号
        analyzed_signals = analysis_result["data"]["signals"]
        executable_trades = []

        for item in analyzed_signals:
            signal_dict = item["signal"]
            risk_dict = item["risk_report"]

            # 只执行卖出信号且风险检查通过
            if signal_dict["action"] in ["strong_sell", "sell"] and risk_dict["passed"]:
                executable_trades.append({
                    "stock_code": signal_dict["stock_code"],
                    "stock_name": signal_dict["stock_name"],
                    "action": signal_dict["action"],
                    "quantity": signal_dict["quantity"],
                    "price": signal_dict["price"],
                    "priority": signal_dict["priority"],
                    "reasons": signal_dict["reasons"]
                })

        # 3. 限制执行数量
        if request.execute_limit:
            executable_trades = executable_trades[:request.execute_limit]

        # 4. 执行交易（或模拟）
        execution_results = []

        for trade in executable_trades:
            if request.dry_run:
                # 模拟模式：仅记录
                result = {
                    "stock_code": trade["stock_code"],
                    "stock_name": trade["stock_name"],
                    "action": "simulated_sell",
                    "quantity": trade["quantity"],
                    "price": trade["price"],
                    "status": "simulated",
                    "message": "模拟交易（未实际执行）"
                }
            else:
                # 实际交易模式（需要集成ths_mac_trader）
                # TODO: 集成实际交易逻辑
                result = {
                    "stock_code": trade["stock_code"],
                    "stock_name": trade["stock_name"],
                    "action": "sell",
                    "quantity": trade["quantity"],
                    "price": trade["price"],
                    "status": "not_implemented",
                    "message": "实际交易功能待实现（需要集成THSMacTrader）"
                }

                # 记录交易（即使未实际执行）
                # risk_manager.record_trade(...)

            execution_results.append(result)

        return {
            "success": True,
            "data": {
                "executable_trades": executable_trades,
                "execution_results": execution_results,
                "summary": {
                    "total_analyzed": len(analyzed_signals),
                    "executable_count": len(executable_trades),
                    "executed_count": len(execution_results),
                    "dry_run": request.dry_run
                }
            },
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"自动交易失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/quant/clear-cache")
async def clear_cache():
    """清除所有缓存"""
    try:
        market_client.clear_cache()
        model_client.clear_cache()

        return {
            "success": True,
            "message": "缓存已清除",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"清除缓存失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/quant/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# 启动服务
# ============================================================================

if __name__ == "__main__":
    logger.info(f"启动量化交易API服务: {API_HOST}:{API_PORT}")

    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level="info"
    )
