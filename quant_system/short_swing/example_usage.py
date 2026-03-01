"""
超短线交易信号系统使用示例

演示如何调用API接口获取交易信号。
"""

import requests
import json


def print_json(data):
    """美化打印JSON数据"""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def example_1_get_sentiment():
    """示例1: 获取市场情绪状态"""
    print("=" * 60)
    print("示例1: 获取市场情绪状态")
    print("=" * 60)

    response = requests.get("http://localhost:8001/api/v1/sentiment")

    if response.status_code == 200:
        data = response.json()
        sentiment = data["sentiment"]

        print(f"\n当前情绪状态: {sentiment['state']}")
        print(f"涨停数量: {sentiment['limit_up_count']}")
        print(f"平均涨幅: {sentiment['avg_change_percent']:.2f}%")
        print(f"上涨股票占比: {sentiment['rising_ratio']:.2%}")
        print(f"置信度: {sentiment['confidence']:.2f}")
        print(f"描述: {sentiment['description']}")
        print(f"\n交易建议: {data['message']}")
    else:
        print(f"请求失败: {response.status_code}")


def example_2_get_themes():
    """示例2: 获取主线题材"""
    print("\n" + "=" * 60)
    print("示例2: 获取主线题材")
    print("=" * 60)

    response = requests.get("http://localhost:8001/api/v1/themes")

    if response.status_code == 200:
        data = response.json()
        themes = data["themes"]

        print(f"\n检测到 {len(themes)} 个主线题材:")

        for i, theme in enumerate(themes[:5], 1):  # 只显示前5个
            print(f"\n{i}. {theme['theme_name']}")
            print(f"   股票数量: {theme['stock_count']}")
            print(f"   平均涨幅: {theme['avg_change_percent']:.2f}%")
            print(f"   强度评分: {theme['score']:.1f}")

            if theme['leader_stock']:
                leader = theme['leader_stock']
                print(f"   龙头股: {leader['name']} ({leader['code']}), "
                      f"涨幅={leader['change_percent']:.2f}%")
            else:
                print("   龙头股: 暂无")

        if data['top_theme']:
            top = data['top_theme']
            print(f"\n最强主线题材: {top['theme_name']} (评分={top['score']:.1f})")
    else:
        print(f"请求失败: {response.status_code}")


def example_3_get_candidates():
    """示例3: 获取选股候选"""
    print("\n" + "=" * 60)
    print("示例3: 获取选股候选")
    print("=" * 60)

    # 构造请求
    request_data = {
        "limit": 10,
        "min_score": 70,
        "exclude_codes": []
    }

    response = requests.post(
        "http://localhost:8001/api/v1/candidates",
        json=request_data
    )

    if response.status_code == 200:
        data = response.json()
        candidates = data["candidates"]

        print(f"\n当前情绪状态: {data['sentiment_state']}")
        print(f"生成候选数量: {data['total_count']}")
        print(f"\n推荐股票列表:\n")

        for i, stock in enumerate(candidates, 1):
            signal_emoji = {
                "strong_buy": "🔥",
                "buy": "✅",
                "watch": "👀",
                "ignore": "❌"
            }.get(stock['signal'], "")

            print(f"{i}. {stock['name']} ({stock['code']}) {signal_emoji}")
            print(f"   当前价格: {stock['price']:.2f} 元")
            print(f"   涨跌幅: {stock['change_percent']:+.2f}%")
            print(f"   量比: {stock['volume_ratio']:.2f}")
            print(f"   换手率: {stock['turnover']:.2f}%")
            print(f"   综合评分: {stock['final_score']:.1f}")
            print(f"   信号类型: {stock['signal']}")

            if stock['theme']:
                print(f"   所属题材: {stock['theme']}")
                if stock['is_leader']:
                    print(f"   龙头股标记: ⭐")

            print(f"   模型评分:")
            print(f"     - 涨停概率: {stock['limit_up_prob']:.2%}")
            print(f"     - 下跌风险: {stock['downside_risk']:.2%}")
            print(f"     - 缠论风险: {stock['chanlun_risk']:.2%}")
            print()
    else:
        print(f"请求失败: {response.status_code}")


def example_4_combined_analysis():
    """示例4: 综合分析流程"""
    print("\n" + "=" * 60)
    print("示例4: 综合分析流程")
    print("=" * 60)

    # 步骤1: 判断市场情绪
    print("\n步骤1: 判断市场情绪...")
    sentiment_response = requests.get("http://localhost:8001/api/v1/sentiment")
    if sentiment_response.status_code != 200:
        print("获取情绪失败，退出分析")
        return

    sentiment_data = sentiment_response.json()
    sentiment_state = sentiment_data["sentiment"]["state"]

    print(f"情绪状态: {sentiment_state}")
    print(f"建议: {sentiment_data['message']}")

    # 步骤2: 识别主线题材
    print("\n步骤2: 识别主线题材...")
    themes_response = requests.get("http://localhost:8001/api/v1/themes")
    if themes_response.status_code != 200:
        print("获取题材失败，退出分析")
        return

    themes_data = themes_response.json()
    top_theme = themes_data.get("top_theme")

    if top_theme:
        print(f"最强题材: {top_theme['theme_name']} (评分={top_theme['score']:.1f})")
        if top_theme['leader_stock']:
            print(f"龙头股: {top_theme['leader_stock']['name']}")
    else:
        print("暂无明显主线题材")

    # 步骤3: 根据情绪调整选股策略
    print("\n步骤3: 生成选股候选...")

    # 根据情绪状态调整最低评分
    min_score_map = {
        "freezing": 90,  # 冰点期：只看最优质标的
        "warming": 80,   # 回暖期：中等评分即可
        "heating": 75,   # 升温期：降低门槛
        "climax": 85,    # 高潮期：提高标准（风险高）
        "ebbing": 95,    # 退潮期：极高标准或空仓
    }

    min_score = min_score_map.get(sentiment_state, 75)
    print(f"根据情绪状态({sentiment_state})，最低评分设为: {min_score}")

    candidates_response = requests.post(
        "http://localhost:8001/api/v1/candidates",
        json={"limit": 5, "min_score": min_score}
    )

    if candidates_response.status_code == 200:
        candidates_data = candidates_response.json()
        candidates = candidates_data["candidates"]

        if candidates:
            print(f"\n推荐关注以下 {len(candidates)} 只股票:\n")
            for i, stock in enumerate(candidates, 1):
                print(f"{i}. {stock['name']} ({stock['code']})")
                print(f"   评分: {stock['final_score']:.1f}, 信号: {stock['signal']}")
        else:
            print("\n当前市场无符合条件的股票，建议观望")
    else:
        print("获取候选失败")

    # 步骤4: 给出操作建议
    print("\n步骤4: 操作建议")
    print("-" * 60)

    if sentiment_state in ["freezing", "ebbing"]:
        print("⚠️ 市场情绪不佳，建议空仓观望，等待机会")
    elif sentiment_state == "warming":
        print("✅ 市场开始回暖，可小仓位试探，重点关注主线题材龙头")
    elif sentiment_state == "heating":
        print("🔥 市场情绪升温，积极参与，但要注意仓位控制（建议单股30-50%）")
    elif sentiment_state == "climax":
        print("⚠️ 市场情绪高潮，谨慎追高，注意随时获利了结")

    print("-" * 60)


def main():
    """主函数"""
    print("\n超短线交易信号系统使用示例\n")

    try:
        # 检查服务是否运行
        response = requests.get("http://localhost:8001/api/v1/health", timeout=2)
        if response.status_code != 200:
            print("服务未正常运行，请先启动服务:")
            print("python3 -m quant_system.short_swing.main")
            return
    except requests.exceptions.RequestException:
        print("无法连接到服务，请确认服务已启动:")
        print("python3 -m quant_system.short_swing.main")
        return

    # 运行示例
    example_1_get_sentiment()
    example_2_get_themes()
    example_3_get_candidates()
    example_4_combined_analysis()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
