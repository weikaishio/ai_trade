"""
调试题材检测为空的问题

分析为什么 /api/v1/themes 返回空数组
"""

import sys
sys.path.insert(0, '.')

from quant_system.short_swing.data.data_fetcher import get_fetcher
from quant_system.short_swing.engines.theme_detector import ThemeDetector
from quant_system.short_swing.config_short_swing import THEME_DETECTION


def debug_theme_detection():
    """调试题材检测流程"""
    print("=" * 70)
    print("调试题材检测为空问题")
    print("=" * 70)

    fetcher = get_fetcher()
    detector = ThemeDetector()

    # Step 1: 获取涨停股票
    print("\n【Step 1】获取涨停股票...")
    limit_up_stocks = fetcher.get_limit_up_stocks()
    print(f"涨停股票数量: {len(limit_up_stocks)}")
    if limit_up_stocks:
        print("涨停股票示例:")
        for stock in limit_up_stocks[:3]:
            print(f"  - {stock.name} ({stock.code}): {stock.change_percent:+.2f}%")
    else:
        print("  ⚠️ 无涨停股票！")

    # Step 2: 获取强势股票（涨幅>5%）
    print("\n【Step 2】获取强势股票（涨幅 >= 5%）...")
    market_snapshot = fetcher.get_market_snapshot()
    strong_stocks = [q for q in market_snapshot if q.change_percent >= 5.0]
    print(f"市场总股票数: {len(market_snapshot)}")
    print(f"强势股票数量（涨幅>=5%）: {len(strong_stocks)}")
    if strong_stocks:
        print("强势股票示例:")
        for stock in strong_stocks[:3]:
            print(f"  - {stock.name} ({stock.code}): {stock.change_percent:+.2f}%")
    else:
        print("  ⚠️ 无强势股票（涨幅>=5%）！")

    # Step 3: 合并强势股票池
    print("\n【Step 3】合并强势股票池...")
    all_strong_stocks = detector._merge_and_deduplicate(limit_up_stocks, strong_stocks)
    print(f"合并后强势股票数量: {len(all_strong_stocks)}")

    if not all_strong_stocks:
        print("\n❌ 根本原因: 没有强势股票（涨幅>=5% 或 涨停）")
        print("   解决方案:")
        print("   1. 当前为非交易时间，市场数据可能为静态快照（涨幅都很小）")
        print("   2. 在交易时间内运行，或降低强势股票阈值（从5%改为3%）")
        return

    # Step 4: 基于关键词聚类
    print("\n【Step 4】基于关键词聚类...")
    themes = detector._cluster_by_keywords(all_strong_stocks)
    print(f"聚类后题材数量: {len(themes)}")

    if themes:
        print("\n聚类后题材详情:")
        for theme in themes:
            print(f"\n  题材: {theme.theme_name}")
            print(f"  股票数量: {theme.stock_count}")
            print(f"  平均涨幅: {theme.avg_change_percent:.2f}%")
            print(f"  股票列表:")
            for stock in theme.stocks[:3]:
                print(f"    - {stock.name} ({stock.code}): {stock.change_percent:+.2f}%")

    # Step 5: 题材有效性筛选
    print("\n【Step 5】题材有效性筛选...")
    print(f"配置要求:")
    print(f"  - 最少股票数: {THEME_DETECTION['min_stocks_per_theme']}")
    print(f"  - 平均涨幅: >= {THEME_DETECTION['min_avg_change_percent']}%")

    valid_themes = []
    for theme in themes:
        is_valid = detector._is_valid_theme(theme)
        status = "✅ 有效" if is_valid else "❌ 无效"
        print(f"\n  {theme.theme_name}: {status}")
        print(f"    股票数: {theme.stock_count} (要求>={THEME_DETECTION['min_stocks_per_theme']})")
        print(f"    平均涨幅: {theme.avg_change_percent:.2f}% (要求>={THEME_DETECTION['min_avg_change_percent']}%)")

        if is_valid:
            valid_themes.append(theme)

    print(f"\n最终有效题材数量: {len(valid_themes)}")

    if not valid_themes:
        print("\n❌ 根本原因: 没有题材通过有效性筛选")
        print("   可能原因:")
        print("   1. 题材内股票数量不足3只")
        print("   2. 题材平均涨幅未达到3%")
        print("   解决方案:")
        print("   - 降低 min_avg_change_percent 阈值（如改为2%或1.5%）")
        print("   - 降低 min_stocks_per_theme 阈值（如改为2只）")

    # Step 6: 完整检测流程
    print("\n【Step 6】运行完整检测流程...")
    final_themes = detector.detect_themes()
    print(f"最终返回题材数量: {len(final_themes)}")

    if final_themes:
        print("\n最终题材结果:")
        for theme in final_themes:
            print(f"\n  题材: {theme.theme_name}")
            print(f"  评分: {theme.score:.1f}")
            print(f"  股票数: {theme.stock_count}")
            print(f"  平均涨幅: {theme.avg_change_percent:.2f}%")
            if theme.leader_stock:
                print(f"  龙头: {theme.leader_stock.name} ({theme.leader_stock.code})")

    # 分析市场整体涨幅分布
    print("\n" + "=" * 70)
    print("【市场涨幅分布分析】")
    print("=" * 70)

    if market_snapshot:
        changes = [s.change_percent for s in market_snapshot]
        changes_sorted = sorted(changes, reverse=True)

        print(f"\n市场涨幅统计:")
        print(f"  最高涨幅: {changes_sorted[0]:.2f}%")
        print(f"  前10名平均: {sum(changes_sorted[:10])/10:.2f}%")
        print(f"  前20名平均: {sum(changes_sorted[:20])/20:.2f}%")
        print(f"  市场平均: {sum(changes)/len(changes):.2f}%")

        # 涨幅分布
        ranges = [
            (">= 9.8%（涨停）", lambda x: x >= 9.8),
            (">= 5%（强势）", lambda x: 5.0 <= x < 9.8),
            (">= 3%（活跃）", lambda x: 3.0 <= x < 5.0),
            (">= 1%（上涨）", lambda x: 1.0 <= x < 3.0),
            ("-1% ~ 1%（震荡）", lambda x: -1.0 <= x < 1.0),
            ("< -1%（下跌）", lambda x: x < -1.0),
        ]

        print(f"\n涨幅分布:")
        for label, condition in ranges:
            count = sum(1 for c in changes if condition(c))
            percentage = count / len(changes) * 100
            print(f"  {label}: {count} 只 ({percentage:.1f}%)")

    print("\n" + "=" * 70)
    print("调试完成")
    print("=" * 70)


if __name__ == "__main__":
    debug_theme_detection()
