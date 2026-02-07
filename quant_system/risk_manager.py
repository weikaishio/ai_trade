"""
风险管理器模块

提供风险控制、交易限制、熔断机制等功能，确保系统安全运行。
"""

import logging
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from pathlib import Path
from enum import Enum

try:
    from .decision_engine import TradeSignal, Position, TradeAction, Priority
    from .buy_strategy import BuySignal
    from .config_quant import (
        MAX_DAILY_TRADES,
        MAX_POSITION_RATIO,
        MIN_TRADE_INTERVAL,
        MAX_SINGLE_TRADE_AMOUNT,
        MIN_TRADE_AMOUNT,
        DAILY_LOSS_LIMIT,
        CIRCUIT_BREAKER_COOLDOWN,
        ST_STOCK_MAX_RATIO,
        ALERT_THRESHOLDS,
        BUY_STRATEGY_CONFIG,
        is_trading_time
    )
except ImportError:
    from decision_engine import TradeSignal, Position, TradeAction, Priority
    from buy_strategy import BuySignal
    from config_quant import (
        MAX_DAILY_TRADES,
        MAX_POSITION_RATIO,
        MIN_TRADE_INTERVAL,
        MAX_SINGLE_TRADE_AMOUNT,
        MIN_TRADE_AMOUNT,
        DAILY_LOSS_LIMIT,
        CIRCUIT_BREAKER_COOLDOWN,
        ST_STOCK_MAX_RATIO,
        ALERT_THRESHOLDS,
        BUY_STRATEGY_CONFIG,
        is_trading_time
    )

# 配置日志
logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"          # 低风险
    MEDIUM = "medium"    # 中等风险
    HIGH = "high"        # 高风险
    CRITICAL = "critical"  # 极高风险


@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: datetime
    stock_code: str
    stock_name: str
    action: str
    quantity: int
    price: float
    amount: float
    profit_loss: float = 0.0

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "action": self.action,
            "quantity": self.quantity,
            "price": self.price,
            "amount": self.amount,
            "profit_loss": self.profit_loss
        }


@dataclass
class RiskReport:
    """风险报告"""
    risk_level: RiskLevel
    passed: bool
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metrics: Dict = field(default_factory=dict)
    wait_seconds: float = 0.0  # 需要等待的秒数（用于交易间隔限制）

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "risk_level": self.risk_level.value,
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "suggestions": self.suggestions,
            "metrics": self.metrics
        }


class RiskManager:
    """
    风险管理器

    功能：
    1. 交易次数限制
    2. 仓位控制
    3. 交易金额限制
    4. 熔断机制
    5. 风险评估
    6. 交易记录管理
    """

    def __init__(self, data_dir: str = "data/risk"):
        """
        初始化风险管理器

        Args:
            data_dir: 数据存储目录
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # 交易记录
        self.trade_records: List[TradeRecord] = []
        self.load_trade_records()

        # 熔断状态
        self.circuit_breaker_active = False
        self.circuit_breaker_until: Optional[datetime] = None

        # 统计数据
        self.daily_trade_count = 0
        self.daily_buy_count = 0  # 单日买入次数
        self.daily_profit_loss = 0.0
        self.last_trade_time: Optional[datetime] = None
        self.last_buy_time: Optional[datetime] = None  # 上次买入时间

        # 加载今日数据
        self._load_daily_stats()

        logger.info("风险管理器初始化完成")

    def check_trade_permission(
        self,
        signal: TradeSignal,
        position: Optional[Position] = None,
        total_portfolio_value: float = 0.0
    ) -> RiskReport:
        """
        检查交易是否允许执行

        Args:
            signal: 交易信号
            position: 持仓信息（用于计算仓位）
            total_portfolio_value: 总资产价值（用于仓位计算）

        Returns:
            RiskReport: 风险报告
        """
        report = RiskReport(
            risk_level=RiskLevel.LOW,
            passed=True
        )

        # 1. 检查熔断状态
        if not self._check_circuit_breaker(report):
            report.passed = False
            report.risk_level = RiskLevel.CRITICAL
            return report

        # 2. 检查交易时间
        if not self._check_trading_time(report):
            report.passed = False
            report.risk_level = RiskLevel.HIGH
            return report

        # 3. 检查交易次数限制
        if not self._check_daily_trade_limit(report):
            report.passed = False
            report.risk_level = RiskLevel.HIGH
            return report

        # 4. 检查交易间隔
        if not self._check_trade_interval(report):
            report.passed = False
            report.risk_level = RiskLevel.MEDIUM
            return report

        # 5. 检查交易金额
        if position:
            trade_amount = position.current_price * signal.quantity
            if not self._check_trade_amount(trade_amount, report):
                report.passed = False
                report.risk_level = RiskLevel.HIGH
                return report

        # 6. 检查仓位比例
        if position and total_portfolio_value > 0:
            position_value = position.calculate_position_value()
            position_ratio = position_value / total_portfolio_value
            if not self._check_position_ratio(
                signal.stock_code,
                position,
                position_ratio,
                report
            ):
                report.passed = False
                report.risk_level = RiskLevel.MEDIUM
                return report

        # 7. 检查单日亏损限制
        if not self._check_daily_loss_limit(report):
            # 触发熔断
            self._trigger_circuit_breaker()
            report.passed = False
            report.risk_level = RiskLevel.CRITICAL
            return report

        # 8. ST股票特殊检查
        if position and position.is_st_stock():
            if not self._check_st_stock(position, total_portfolio_value, report):
                report.passed = False
                report.risk_level = RiskLevel.HIGH
                return report

        # 添加建议
        if signal.priority == Priority.CRITICAL:
            report.suggestions.append("紧急交易，建议立即执行")
        elif signal.confidence < 0.6:
            report.suggestions.append(f"决策置信度较低 ({signal.confidence:.1%})，建议谨慎操作")

        # 设置指标
        report.metrics = {
            "daily_trade_count": self.daily_trade_count,
            "daily_profit_loss": self.daily_profit_loss,
            "circuit_breaker_active": self.circuit_breaker_active,
            "signal_confidence": signal.confidence
        }

        logger.info(f"风险检查通过: {signal.stock_code} ({report.risk_level.value})")
        return report

    def check_buy_permission(
        self,
        buy_signal: BuySignal,
        current_positions: List[Position],
        available_cash: float,
        total_capital: float
    ) -> RiskReport:
        """
        检查买入权限

        Args:
            buy_signal: 买入信号
            current_positions: 当前持仓列表
            available_cash: 可用资金
            total_capital: 总资金

        Returns:
            RiskReport: 风险报告
        """
        report = RiskReport(
            risk_level=RiskLevel.LOW,
            passed=True
        )

        # 1. 检查熔断状态
        if not self._check_circuit_breaker(report):
            report.passed = False
            report.risk_level = RiskLevel.CRITICAL
            return report

        # 2. 检查交易时间
        if not self._check_trading_time(report):
            report.passed = False
            report.risk_level = RiskLevel.HIGH
            return report

        # 3. 检查单日买入次数限制
        max_daily_buy = BUY_STRATEGY_CONFIG.get("max_daily_buy_count", 5)
        if self.daily_buy_count >= max_daily_buy:
            report.errors.append(
                f"已达单日买入次数上限 ({self.daily_buy_count}/{max_daily_buy})"
            )
            report.passed = False
            report.risk_level = RiskLevel.HIGH
            return report

        if self.daily_buy_count >= max_daily_buy * 0.8:
            report.warnings.append(
                f"买入次数接近上限 ({self.daily_buy_count}/{max_daily_buy})"
            )

        # 4. 检查买入间隔
        min_buy_interval = BUY_STRATEGY_CONFIG.get("min_buy_interval", 60)
        if self.last_buy_time:
            elapsed = (datetime.now() - self.last_buy_time).total_seconds()
            if elapsed < min_buy_interval:
                wait_time = min_buy_interval - elapsed
                report.wait_seconds = wait_time
                report.errors.append(
                    f"距上次买入时间过短 ({elapsed:.0f}秒 < {min_buy_interval}秒)，需等待 {wait_time:.1f}秒"
                )
                report.passed = False
                report.risk_level = RiskLevel.MEDIUM
                return report

        # 5. 检查最大持仓数量
        max_positions = BUY_STRATEGY_CONFIG.get("max_positions", 10)
        current_position_count = len(current_positions)
        if current_position_count >= max_positions:
            report.errors.append(
                f"已达最大持仓数量 ({current_position_count}/{max_positions})"
            )
            report.passed = False
            report.risk_level = RiskLevel.HIGH
            return report

        # 检查是否已持有该股票
        for pos in current_positions:
            if pos.code == buy_signal.stock_code:
                report.warnings.append(
                    f"已持有 {buy_signal.stock_name}，建议避免重复买入"
                )
                # 不阻止执行，仅警告
                break

        # 6. 检查单股仓位比例
        if total_capital > 0:
            max_single_position = BUY_STRATEGY_CONFIG.get("max_single_position", 0.2)
            position_ratio = buy_signal.amount / total_capital

            if position_ratio > max_single_position:
                report.errors.append(
                    f"单股仓位比例过高 ({position_ratio:.1%} > {max_single_position:.1%})"
                )
                report.passed = False
                report.risk_level = RiskLevel.HIGH
                return report

            if position_ratio > max_single_position * 0.9:
                report.warnings.append(
                    f"单股仓位比例接近上限 ({position_ratio:.1%})"
                )

        # 7. 检查单日新增仓位比例
        if total_capital > 0:
            # 计算今日已买入金额（需要从交易记录中统计）
            today = date.today()
            today_buy_amount = sum(
                r.amount for r in self.trade_records
                if r.timestamp.date() == today and r.action == "buy"
            )
            total_new_position = today_buy_amount + buy_signal.amount
            new_position_ratio = total_new_position / total_capital

            max_new_position_ratio = BUY_STRATEGY_CONFIG.get("max_new_position_ratio", 0.5)
            if new_position_ratio > max_new_position_ratio:
                report.errors.append(
                    f"单日新增仓位比例过高 ({new_position_ratio:.1%} > {max_new_position_ratio:.1%})"
                )
                report.passed = False
                report.risk_level = RiskLevel.HIGH
                return report

            if new_position_ratio > max_new_position_ratio * 0.8:
                report.warnings.append(
                    f"单日新增仓位接近上限 ({new_position_ratio:.1%})"
                )

        # 8. 检查买入金额
        min_amount = BUY_STRATEGY_CONFIG.get("min_position_value", 5000)
        if buy_signal.amount < min_amount:
            report.errors.append(
                f"买入金额低于最小值 ({buy_signal.amount:.2f}元 < {min_amount}元)"
            )
            report.passed = False
            report.risk_level = RiskLevel.MEDIUM
            return report

        if buy_signal.amount > MAX_SINGLE_TRADE_AMOUNT:
            report.errors.append(
                f"买入金额超过上限 ({buy_signal.amount:.2f}元 > {MAX_SINGLE_TRADE_AMOUNT}元)"
            )
            report.passed = False
            report.risk_level = RiskLevel.HIGH
            return report

        # 9. 检查资金充足性
        # 预留5%的缓冲
        required_cash = buy_signal.amount * 1.05
        if available_cash < required_cash:
            report.errors.append(
                f"可用资金不足 (需要{required_cash:.2f}元，可用{available_cash:.2f}元)"
            )
            report.passed = False
            report.risk_level = RiskLevel.CRITICAL
            return report

        # 检查是否保留足够现金储备
        cash_reserve_ratio = BUY_STRATEGY_CONFIG.get("cash_reserve_ratio", 0.1)
        min_cash_reserve = total_capital * cash_reserve_ratio
        remaining_cash = available_cash - buy_signal.amount

        if remaining_cash < min_cash_reserve:
            report.warnings.append(
                f"买入后现金储备不足 (剩余{remaining_cash:.2f}元 < {min_cash_reserve:.2f}元)"
            )

        # 10. ST股票特殊检查
        if any(prefix in buy_signal.stock_name for prefix in ["ST", "*ST", "S*ST"]):
            report.warnings.append(f"{buy_signal.stock_name} 为ST股票，风险较高")

            # 检查ST股票总仓位
            st_positions_value = sum(
                pos.calculate_position_value()
                for pos in current_positions
                if pos.is_st_stock()
            )
            new_st_total = st_positions_value + buy_signal.amount

            if total_capital > 0:
                st_ratio = new_st_total / total_capital
                if st_ratio > ST_STOCK_MAX_RATIO:
                    report.errors.append(
                        f"ST股票总仓位过高 ({st_ratio:.1%} > {ST_STOCK_MAX_RATIO:.1%})"
                    )
                    report.passed = False
                    report.risk_level = RiskLevel.HIGH
                    return report

        # 添加建议
        if buy_signal.priority == Priority.HIGH:
            report.suggestions.append("高优先级买入信号，建议优先执行")
        elif buy_signal.confidence < 0.7:
            report.suggestions.append(
                f"买入信号置信度较低 ({buy_signal.confidence:.1%})，建议谨慎操作"
            )

        if buy_signal.score >= 85:
            report.suggestions.append(f"高评分股票 ({buy_signal.score:.1f}分)，质量较好")

        # 设置指标
        report.metrics = {
            "daily_trade_count": self.daily_trade_count,
            "daily_buy_count": self.daily_buy_count,
            "daily_profit_loss": self.daily_profit_loss,
            "circuit_breaker_active": self.circuit_breaker_active,
            "signal_confidence": buy_signal.confidence,
            "signal_score": buy_signal.score,
            "available_cash": available_cash,
            "buy_amount": buy_signal.amount,
            "remaining_cash": available_cash - buy_signal.amount
        }

        logger.info(
            f"买入风险检查通过: {buy_signal.stock_code} "
            f"({report.risk_level.value}, 置信度{buy_signal.confidence:.1%})"
        )
        return report

    def record_trade(
        self,
        stock_code: str,
        stock_name: str,
        action: str,
        quantity: int,
        price: float,
        profit_loss: float = 0.0
    ) -> None:
        """
        记录交易

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            action: 交易动作（buy/sell）
            quantity: 数量
            price: 价格
            profit_loss: 盈亏金额
        """
        record = TradeRecord(
            timestamp=datetime.now(),
            stock_code=stock_code,
            stock_name=stock_name,
            action=action,
            quantity=quantity,
            price=price,
            amount=price * quantity,
            profit_loss=profit_loss
        )

        self.trade_records.append(record)
        self.daily_trade_count += 1
        self.daily_profit_loss += profit_loss
        self.last_trade_time = datetime.now()

        # 如果是买入操作，更新买入统计
        if action.lower() == "buy":
            self.daily_buy_count += 1
            self.last_buy_time = datetime.now()

        # 保存记录
        self._save_trade_record(record)
        self._save_daily_stats()

        logger.info(
            f"记录交易: {stock_code} {action} {quantity}股 @{price} "
            f"盈亏: {profit_loss:.2f}元"
        )

    def get_daily_summary(self) -> Dict:
        """
        获取当日交易摘要

        Returns:
            交易摘要字典
        """
        today = date.today()
        today_records = [
            r for r in self.trade_records
            if r.timestamp.date() == today
        ]

        total_amount = sum(r.amount for r in today_records)
        total_profit_loss = sum(r.profit_loss for r in today_records)

        return {
            "date": today.isoformat(),
            "trade_count": len(today_records),
            "total_amount": total_amount,
            "total_profit_loss": total_profit_loss,
            "avg_profit_loss": total_profit_loss / len(today_records) if today_records else 0,
            "circuit_breaker_active": self.circuit_breaker_active,
            "records": [r.to_dict() for r in today_records]
        }

    def get_risk_statistics(self) -> Dict:
        """
        获取风险统计信息

        Returns:
            风险统计字典
        """
        # 最近7天数据
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_records = [
            r for r in self.trade_records
            if r.timestamp >= seven_days_ago
        ]

        if not recent_records:
            return {
                "period": "7_days",
                "trade_count": 0,
                "total_profit_loss": 0.0,
                "win_rate": 0.0,
                "avg_profit_loss": 0.0,
                "winning_trades": 0,
                "losing_trades": 0,
                "max_profit": 0.0,
                "max_loss": 0.0
            }

        # 计算统计数据
        winning_trades = [r for r in recent_records if r.profit_loss > 0]
        losing_trades = [r for r in recent_records if r.profit_loss < 0]

        total_profit_loss = sum(r.profit_loss for r in recent_records)
        win_rate = len(winning_trades) / len(recent_records) if recent_records else 0

        return {
            "period": "7_days",
            "trade_count": len(recent_records),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "total_profit_loss": total_profit_loss,
            "win_rate": win_rate,
            "avg_profit_loss": total_profit_loss / len(recent_records),
            "max_profit": max((r.profit_loss for r in recent_records), default=0),
            "max_loss": min((r.profit_loss for r in recent_records), default=0)
        }

    def _check_circuit_breaker(self, report: RiskReport) -> bool:
        """检查熔断状态"""
        if self.circuit_breaker_active:
            if datetime.now() < self.circuit_breaker_until:
                cooldown_remaining = (self.circuit_breaker_until - datetime.now()).seconds
                report.errors.append(
                    f"系统处于熔断状态，剩余冷却时间: {cooldown_remaining}秒"
                )
                return False
            else:
                # 解除熔断
                self._deactivate_circuit_breaker()

        return True

    def _check_trading_time(self, report: RiskReport) -> bool:
        """检查交易时间"""
        if not is_trading_time():
            report.errors.append("当前不在交易时间内")
            return False
        return True

    def _check_daily_trade_limit(self, report: RiskReport) -> bool:
        """检查单日交易次数限制"""
        if self.daily_trade_count >= MAX_DAILY_TRADES:
            report.errors.append(
                f"已达单日交易次数上限 ({self.daily_trade_count}/{MAX_DAILY_TRADES})"
            )
            return False

        if self.daily_trade_count >= MAX_DAILY_TRADES * 0.8:
            report.warnings.append(
                f"交易次数接近上限 ({self.daily_trade_count}/{MAX_DAILY_TRADES})"
            )

        return True

    def _check_trade_interval(self, report: RiskReport) -> bool:
        """检查交易间隔"""
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < MIN_TRADE_INTERVAL:
                wait_time = MIN_TRADE_INTERVAL - elapsed
                report.wait_seconds = wait_time
                report.errors.append(
                    f"距上次交易时间过短 ({elapsed:.0f}秒 < {MIN_TRADE_INTERVAL}秒)，需等待 {wait_time:.1f}秒"
                )
                return False
        return True

    def _check_trade_amount(self, amount: float, report: RiskReport) -> bool:
        """检查交易金额"""
        if amount > MAX_SINGLE_TRADE_AMOUNT:
            report.errors.append(
                f"交易金额超过上限 ({amount:.2f} > {MAX_SINGLE_TRADE_AMOUNT})"
            )
            return False

        if amount < MIN_TRADE_AMOUNT:
            report.warnings.append(
                f"交易金额低于建议最小值 ({amount:.2f} < {MIN_TRADE_AMOUNT})"
            )

        return True

    def _check_position_ratio(
        self,
        stock_code: str,
        position: Position,
        position_ratio: float,
        report: RiskReport
    ) -> bool:
        """检查仓位比例"""
        if position_ratio > MAX_POSITION_RATIO:
            report.warnings.append(
                f"持仓比例过高 ({position_ratio:.1%} > {MAX_POSITION_RATIO:.1%})"
            )

        return True

    def _check_daily_loss_limit(self, report: RiskReport) -> bool:
        """检查单日亏损限制"""
        if self.daily_profit_loss < 0:
            # 计算亏损比例（需要总资产数据，这里简化处理）
            loss_ratio = abs(self.daily_profit_loss) / 100000  # 假设总资产10万

            if loss_ratio >= abs(DAILY_LOSS_LIMIT):
                report.errors.append(
                    f"单日亏损达到熔断线 ({self.daily_profit_loss:.2f}元)"
                )
                return False

            if loss_ratio >= abs(DAILY_LOSS_LIMIT) * 0.8:
                report.warnings.append(
                    f"单日亏损接近熔断线 ({self.daily_profit_loss:.2f}元)"
                )

        return True

    def _check_st_stock(
        self,
        position: Position,
        total_portfolio_value: float,
        report: RiskReport
    ) -> bool:
        """检查ST股票特殊限制"""
        if total_portfolio_value > 0:
            position_value = position.calculate_position_value()
            st_ratio = position_value / total_portfolio_value

            if st_ratio > ST_STOCK_MAX_RATIO:
                report.warnings.append(
                    f"ST股票仓位过高 ({st_ratio:.1%} > {ST_STOCK_MAX_RATIO:.1%})"
                )

        report.warnings.append(f"{position.name} 为ST股票，风险较高")
        return True

    def _trigger_circuit_breaker(self) -> None:
        """触发熔断"""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now() + timedelta(seconds=CIRCUIT_BREAKER_COOLDOWN)
        logger.warning(f"触发熔断机制，冷却至: {self.circuit_breaker_until}")

    def _deactivate_circuit_breaker(self) -> None:
        """解除熔断"""
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None
        logger.info("熔断机制已解除")

    def _save_trade_record(self, record: TradeRecord) -> None:
        """保存单条交易记录"""
        date_str = record.timestamp.strftime("%Y%m%d")
        file_path = self.data_dir / f"trades_{date_str}.jsonl"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    def load_trade_records(self, days: int = 7) -> None:
        """
        加载最近N天的交易记录

        Args:
            days: 加载天数
        """
        self.trade_records = []
        cutoff_date = datetime.now() - timedelta(days=days)

        for file_path in sorted(self.data_dir.glob("trades_*.jsonl")):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        data = json.loads(line)
                        record = TradeRecord(
                            timestamp=datetime.fromisoformat(data["timestamp"]),
                            stock_code=data["stock_code"],
                            stock_name=data["stock_name"],
                            action=data["action"],
                            quantity=data["quantity"],
                            price=data["price"],
                            amount=data["amount"],
                            profit_loss=data.get("profit_loss", 0.0)
                        )

                        if record.timestamp >= cutoff_date:
                            self.trade_records.append(record)

            except Exception as e:
                logger.error(f"加载交易记录失败 {file_path}: {e}")

        logger.info(f"加载了 {len(self.trade_records)} 条交易记录")

    def _save_daily_stats(self) -> None:
        """保存当日统计数据"""
        today_str = date.today().strftime("%Y%m%d")
        stats_file = self.data_dir / f"stats_{today_str}.json"

        stats = {
            "date": today_str,
            "daily_trade_count": self.daily_trade_count,
            "daily_buy_count": self.daily_buy_count,
            "daily_profit_loss": self.daily_profit_loss,
            "last_trade_time": self.last_trade_time.isoformat() if self.last_trade_time else None,
            "last_buy_time": self.last_buy_time.isoformat() if self.last_buy_time else None,
            "circuit_breaker_active": self.circuit_breaker_active,
            "circuit_breaker_until": self.circuit_breaker_until.isoformat() if self.circuit_breaker_until else None
        }

        with open(stats_file, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    def _load_daily_stats(self) -> None:
        """加载当日统计数据"""
        today_str = date.today().strftime("%Y%m%d")
        stats_file = self.data_dir / f"stats_{today_str}.json"

        if stats_file.exists():
            try:
                with open(stats_file, "r", encoding="utf-8") as f:
                    stats = json.load(f)

                self.daily_trade_count = stats.get("daily_trade_count", 0)
                self.daily_buy_count = stats.get("daily_buy_count", 0)
                self.daily_profit_loss = stats.get("daily_profit_loss", 0.0)

                if stats.get("last_trade_time"):
                    self.last_trade_time = datetime.fromisoformat(stats["last_trade_time"])

                if stats.get("last_buy_time"):
                    self.last_buy_time = datetime.fromisoformat(stats["last_buy_time"])

                self.circuit_breaker_active = stats.get("circuit_breaker_active", False)

                if stats.get("circuit_breaker_until"):
                    self.circuit_breaker_until = datetime.fromisoformat(stats["circuit_breaker_until"])

                logger.info(
                    f"加载当日统计: 交易{self.daily_trade_count}次 "
                    f"(其中买入{self.daily_buy_count}次)，盈亏{self.daily_profit_loss:.2f}元"
                )

            except Exception as e:
                logger.error(f"加载当日统计失败: {e}")


# ============================================================================
# 使用示例和测试
# ============================================================================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 创建风险管理器
    risk_mgr = RiskManager(data_dir="/Users/tim/Documents/golang/auto_trade/quant_system/data/risk")

    print("\n=== 风险管理器测试 ===")

    # 模拟交易信号
    from decision_engine import TradeSignal, TradeAction, Priority

    signal = TradeSignal(
        stock_code="600483",
        stock_name="福能股份",
        action=TradeAction.SELL,
        priority=Priority.HIGH,
        quantity=100,
        price=24.50,
        confidence=0.85
    )

    # 模拟持仓
    position = Position(
        code="600483",
        name="福能股份",
        quantity=100,
        cost_price=25.00,
        current_price=24.50,
        holding_days=10
    )

    # 风险检查
    print("\n=== 风险检查 ===")
    report = risk_mgr.check_trade_permission(signal, position, total_portfolio_value=100000)

    print(f"风险等级: {report.risk_level.value}")
    print(f"是否通过: {report.passed}")
    print(f"警告: {report.warnings}")
    print(f"错误: {report.errors}")
    print(f"建议: {report.suggestions}")
    print(f"指标: {report.metrics}")

    # 记录交易
    if report.passed:
        print("\n=== 记录交易 ===")
        risk_mgr.record_trade(
            stock_code="600483",
            stock_name="福能股份",
            action="sell",
            quantity=100,
            price=24.50,
            profit_loss=-50.0
        )

    # 当日摘要
    print("\n=== 当日交易摘要 ===")
    summary = risk_mgr.get_daily_summary()
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # 风险统计
    print("\n=== 风险统计 ===")
    stats = risk_mgr.get_risk_statistics()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
