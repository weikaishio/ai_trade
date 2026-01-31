"""
量化交易系统测试脚本

快速测试系统各个模块的功能
"""

import logging
from datetime import datetime

from quant_system import MOCK_POSITIONS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_market_data():
    """测试市场数据客户端"""
    print("\n" + "=" * 60)
    print("测试市场数据客户端")
    print("=" * 60)

    from market_data_client import MarketDataClient

    client = MarketDataClient()

    # 测试单个查询
    print("\n1. 测试单个股票查询...")
    data = client.get_stock_data(MOCK_POSITIONS[0]["code"])
    if data:
        print(f"✓ {data.name} ({data.code}): {data.current_price} ({data.change_percent:+.2f}%)")
    else:
        print("✗ 获取失败")

    # 测试批量查询
    print("\n2. 测试批量查询...")
    codes = ["002532", "301026", "603993"]
    batch_data = client.get_batch_stock_data(codes)
    for code, data in batch_data.items():
        if data:
            print(f"✓ {code}: {data.current_price}")
        else:
            print(f"✗ {code}: 获取失败")

    # 测试缓存
    print("\n3. 测试缓存...")
    stats = client.get_cache_stats()
    print(f"缓存统计: {stats['valid_cached']}/{stats['total_cached']}")


def test_model_client():
    """测试模型客户端"""
    print("\n" + "=" * 60)
    print("测试模型客户端")
    print("=" * 60)

    from model_client import ModelClient

    client = ModelClient()

    # 健康检查
    print("\n1. 健康检查...")
    is_healthy = client.health_check()
    if is_healthy:
        print("✓ 模型API可用")
    else:
        print("✗ 模型API不可用，将使用模拟数据")

        # 使用模拟客户端
        class MockModelClient(ModelClient):
            def get_score(self, stock_code, **kwargs):
                import random
                from model_client import ModelScore
                from config_quant import get_decision_level
                score = random.uniform(20, 90)
                return ModelScore(
                    stock_code=stock_code,
                    score=score,
                    recommendation=get_decision_level(score),
                    confidence=random.uniform(0.6, 0.95),
                    factors={},
                    timestamp=datetime.now()
                )

        client = MockModelClient()

    # 测试评分
    print("\n2. 测试评分...")
    score = client.get_score(
        stock_code="002532",
        current_price=24.5,
        holding_days=10,
        profit_loss_ratio=-0.05
    )
    if score:
        print(f"✓ 评分: {score.score:.2f} ({score.recommendation})")
    else:
        print("✗ 获取评分失败")


def test_decision_engine():
    """测试决策引擎"""
    print("\n" + "=" * 60)
    print("测试决策引擎")
    print("=" * 60)

    from decision_engine import DecisionEngine, Position
    from market_data_client import StockData
    from model_client import ModelScore

    engine = DecisionEngine()

    # 创建测试数据
    position = Position(
        code="002532",
        name="天山钻业",
        quantity=100,
        cost_price=24.50,
        holding_days=10,
        current_price=23.30
    )

    market_data = StockData(
        code="002532",
        name="天山钻业",
        current_price=23.30,
        change_amount=-1.20,
        change_percent=-4.90,
        volume=50000,
        turnover=11650.0,
        highest=24.00,
        lowest=23.10,
        open_price=24.00,
        previous_close=24.50,
        timestamp=datetime.now()
    )

    model_score = ModelScore(
        stock_code="600483",
        score=28.5,
        recommendation="strong_sell",
        confidence=0.85,
        factors={},
        timestamp=datetime.now()
    )

    # 执行分析
    print("\n1. 分析持仓...")
    signal = engine.analyze_position(position, market_data, model_score)

    print(f"✓ 交易信号: {signal.action.value}")
    print(f"  优先级: {signal.priority.value}")
    print(f"  置信度: {signal.confidence:.2%}")
    print(f"  决策原因: {len(signal.reasons)}条")


def test_risk_manager():
    """测试风险管理器"""
    print("\n" + "=" * 60)
    print("测试风险管理器")
    print("=" * 60)

    from risk_manager import RiskManager
    from decision_engine import TradeSignal, Position, TradeAction, Priority

    risk_mgr = RiskManager(data_dir="data/risk")

    # 创建测试信号
    signal = TradeSignal(
        stock_code="600483",
        stock_name="福能股份",
        action=TradeAction.SELL,
        priority=Priority.HIGH,
        quantity=100,
        price=24.50,
        confidence=0.85
    )

    position = Position(
        code="600483",
        name="福能股份",
        quantity=100,
        cost_price=25.00,
        current_price=24.50,
        holding_days=10
    )

    # 风险检查
    print("\n1. 风险检查...")
    report = risk_mgr.check_trade_permission(signal, position, 100000)

    print(f"{'✓' if report.passed else '✗'} 风险等级: {report.risk_level.value}")
    if report.warnings:
        print(f"  警告: {len(report.warnings)}条")
    if report.errors:
        print(f"  错误: {len(report.errors)}条")

    # 统计信息
    print("\n2. 风险统计...")
    stats = risk_mgr.get_risk_statistics()
    print(f"✓ 最近7天: {stats['trade_count']}笔交易")


def test_full_workflow():
    """测试完整工作流"""
    print("\n" + "=" * 60)
    print("测试完整工作流")
    print("=" * 60)

    from quant_main import QuantTradingSystem
    from decision_engine import Position

    # 创建系统
    system = QuantTradingSystem(test_mode=True, dry_run=True)

    # 创建模拟持仓
    positions = [
        Position(
            code="600483",
            name="福能股份",
            quantity=100,
            cost_price=24.50,
            holding_days=10
        ),
        Position(
            code="603993",
            name="洛阳钼业",
            quantity=200,
            cost_price=6.80,
            holding_days=25
        )
    ]

    # 执行分析
    print("\n1. 执行完整分析流程...")
    signals = system.analyze_and_execute(positions, total_portfolio_value=100000)

    print(f"✓ 生成 {len(signals)} 个交易信号")

    # 打印日报
    print("\n2. 当日摘要...")
    system._print_daily_summary()


def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("量化交易系统测试套件")
    print("=" * 60)

    try:
        # 基础模块测试
        test_market_data()
        test_model_client()
        test_decision_engine()
        test_risk_manager()

        # 完整流程测试
        test_full_workflow()

        print("\n" + "=" * 60)
        print("✓ 所有测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
