#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
持仓OCR识别工具
从同花顺持仓界面截图中提取持仓信息
"""

import pyautogui
import time
import subprocess
import re
from typing import List, Optional
from ths_mac_trader import Position


class PositionOCR:
    """持仓OCR识别器"""

    def __init__(self):
        self.app_name = "同花顺"

    def activate_ths_window(self) -> bool:
        """激活同花顺窗口"""
        script = f'''
        tell application "{self.app_name}"
            activate
        end tell
        '''
        try:
            subprocess.run(['osascript', '-e', script], check=True, capture_output=True)
            time.sleep(0.5)
            return True
        except:
            return False

    def get_window_position(self) -> Optional[tuple]:
        """获取同花顺窗口位置"""
        script = f'''
        tell application "System Events"
            tell process "{self.app_name}"
                set frontWindow to front window
                set windowPosition to position of frontWindow
                set windowSize to size of frontWindow
                return {{item 1 of windowPosition, item 2 of windowPosition, item 1 of windowSize, item 2 of windowSize}}
            end tell
        end tell
        '''
        try:
            result = subprocess.run(
                ['osascript', '-e', script],
                check=True, capture_output=True, text=True
            )
            coords = result.stdout.strip().split(', ')
            return tuple(int(c) for c in coords)
        except Exception as e:
            print(f"获取窗口位置失败: {e}")
            return None

    def capture_position_area(self, region: tuple = None, save_path: str = "positions_screenshot.png",
                             use_calibrated_region: bool = True) -> str:
        """
        截取持仓区域

        参数:
            region: (x, y, width, height) 截图区域，None表示使用校准的坐标
            save_path: 保存路径
            use_calibrated_region: 是否使用校准的固定坐标区域（默认True）

        返回:
            截图文件路径
        """
        print("\n" + "="*70)
        print("📸 截取持仓区域")
        print("="*70)

        # 激活窗口
        if not self.activate_ths_window():
            print("⚠️  无法激活同花顺窗口")
            return None

        # 切换到持仓标签页（修复bug：确保显示持仓界面）
        trader_instance = None
        try:
            from ths_mac_trader import THSMacTrader
            trader_instance = THSMacTrader()
            trader_instance.switch_to_position_tab()
        except Exception as e:
            print(f"⚠️  切换标签页失败: {e}")
            print("   继续执行截图...")

        if region is None and use_calibrated_region:
            # 使用校准的固定坐标
            window_pos = self.get_window_position()
            if window_pos:
                win_x, win_y, win_w, win_h = window_pos

                # 获取trader实例（重用之前创建的或新建）
                if trader_instance is None:
                    from ths_mac_trader import THSMacTrader
                    trader_instance = THSMacTrader()

                # 获取相对坐标配置
                rel_x, rel_y, width, height = trader_instance.coords_relative.get('position_list_region', (550, 40, 560, 140))

                # 转换为绝对坐标
                abs_x = win_x + rel_x
                abs_y = win_y + rel_y
                region = (abs_x, abs_y, width, height)

                print(f"✅ 使用校准的固定坐标")
                print(f"   窗口位置: ({win_x}, {win_y})")
                print(f"   相对坐标: ({rel_x}, {rel_y}, {width}, {height})")
                print(f"   绝对坐标: ({abs_x}, {abs_y}, {width}, {height})")
            else:
                print("⚠️  无法获取窗口位置，切换到手动模式")
                use_calibrated_region = False

        if region is None:
            # 交互式指定区域
            print("\n请按以下步骤操作：")
            print("1. 将鼠标移动到持仓列表的左上角")
            input("2. 按 Enter 记录第一个点...")
            x1, y1 = pyautogui.position()
            print(f"   ✅ 左上角: ({x1}, {y1})")

            print("\n3. 将鼠标移动到持仓列表的右下角")
            input("4. 按 Enter 记录第二个点...")
            x2, y2 = pyautogui.position()
            print(f"   ✅ 右下角: ({x2}, {y2})")

            # 计算区域
            region = (
                min(x1, x2),
                min(y1, y2),
                abs(x2 - x1),
                abs(y2 - y1)
            )

        print(f"\n截图区域: {region}")
        print("正在截图...")

        # 截图
        screenshot = pyautogui.screenshot(region=region)
        screenshot.save(save_path)

        print(f"✅ 截图已保存: {save_path}")
        return save_path

    def extract_positions_manual(self, screenshot_path: str = None) -> List[Position]:
        """
        手动查看截图并输入持仓信息
        这是一个辅助方法，用户看着截图手动输入

        参数:
            screenshot_path: 截图路径，None表示使用最近的截图

        返回:
            Position对象列表
        """
        if screenshot_path:
            print(f"\n📷 请查看截图: {screenshot_path}")
            # 在Mac上打开截图
            subprocess.run(['open', screenshot_path])
            time.sleep(1)

        print("\n" + "="*70)
        print("📊 根据截图输入持仓信息")
        print("="*70)
        print("格式: 股票代码,数量,价格")
        print("例如: 603993,100,24.5")
        print("输入完成后，按 Enter 结束")
        print("="*70 + "\n")

        positions = []
        while True:
            line = input("持仓 (或按 Enter 结束): ").strip()
            if not line:
                break

            try:
                parts = line.split(',')
                if len(parts) >= 2:
                    code = parts[0].strip()
                    qty = int(parts[1].strip())
                    price = float(parts[2].strip()) if len(parts) >= 3 else 0.0
                    cost = float(parts[3].strip()) if len(parts) >= 4 else price  # 成本价，默认使用市价

                    position = Position(
                        stock_code=code,
                        stock_name="",
                        available_qty=qty,
                        current_price=price,
                        cost_price=cost
                    )
                    positions.append(position)
                    print(f"  ✅ 已添加: {code} - {qty}股 @ {price if price > 0 else '待定'}")
                else:
                    print("  ❌ 格式错误，请重新输入")
            except ValueError as e:
                print(f"  ❌ 输入错误: {e}")

        print(f"\n共添加 {len(positions)} 个持仓")
        return positions

    def extract_positions_with_ocr(self, screenshot_path: str) -> List[Position]:
        """
        使用OCR从截图中提取持仓信息
        需要安装: pip install pytesseract pillow
        macOS还需要: brew install tesseract tesseract-lang

        参数:
            screenshot_path: 截图路径

        返回:
            Position对象列表
        """
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            print("❌ OCR功能需要安装依赖:")
            print("   pip install pytesseract pillow")
            print("   brew install tesseract tesseract-lang")
            return []

        print(f"\n🔍 正在识别截图: {screenshot_path}")

        # 读取图片
        img = Image.open(screenshot_path)

        # OCR识别
        # 配置中文识别
        custom_config = r'--oem 3 --psm 6 -l chi_sim+eng'
        text = pytesseract.image_to_string(img, config=custom_config)

        print("\n识别到的文本:")
        print("="*70)
        print(text)
        print("="*70)

        # 解析持仓信息
        positions = self._parse_positions_from_text(text)

        return positions

    def _parse_positions_from_text(self, text: str) -> List[Position]:
        """
        从OCR文本中解析持仓信息

        同花顺持仓表格列顺序（用户明确指定）：
        1. 证券代码
        2. 证券名称
        3. 市价
        4. 盈亏
        5. 当日盈亏
        6. 浮动盈亏比(%)
        7. 实际数量
        8. 股票余额
        9. 可用余额
        10. 冻结余额
        11. 成本价
        12. 市值

        参数:
            text: OCR识别的文本

        返回:
            Position对象列表
        """
        positions = []

        # 股票代码模式 (6位数字)
        code_pattern = r'\b[0-9]{6}\b'

        # 按行处理
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 查找股票代码
            code_match = re.search(code_pattern, line)
            if not code_match:
                continue

            code = code_match.group()

            # 按空白字符分割所有字段
            fields = line.split()

            # 提取所有数字型字段（去除股票代码和名称）
            numbers = []
            for field in fields:
                # 跳过股票代码本身
                if field == code:
                    continue

                # 尝试解析为数字
                try:
                    # 移除千分位逗号
                    clean_field = field.replace(',', '')
                    # 尝试转换为浮点数
                    num = float(clean_field)
                    numbers.append(clean_field)
                except ValueError:
                    # 非数字字段（股票名称等），跳过
                    continue

            # 严格按照列顺序解析（去除股票代码和名称后）：
            # 索引0: 市价
            # 索引1: 盈亏
            # 索引2: 当日盈亏
            # 索引3: 浮动盈亏比(%)
            # 索引4: 实际数量
            # 索引5: 股票余额
            # 索引6: 可用余额
            # 索引7: 冻结余额
            # 索引8: 成本价
            # 索引9: 市值

            if len(numbers) < 9:  # 至少需要10个数字列
                print(f"  ⚠️  数据列不完整: {code} (仅{len(numbers)}列，需要至少10列)")
                print(f"     数字列表: {numbers}")
                continue

            try:
                # ========================================
                # 定义字段类型和小数点修正规则
                # ========================================
                # 有小数的字段：市价、盈亏、当日盈亏、浮动盈亏比、可用余额、成本价、市值
                # 无小数的字段：实际数量、股票余额、冻结余额（索引4,5,7）

                def correct_decimal_point(value: float, field_name: str, is_price: bool = True) -> float:
                    """
                    智能修正小数点丢失

                    Args:
                        value: 原始值
                        field_name: 字段名称（用于日志）
                        is_price: 是否是价格类字段（价格范围0.5-999.99，其他字段范围更宽）

                    Returns:
                        修正后的值
                    """
                    original_value = value

                    # 价格字段的合理范围
                    if is_price:
                        min_val, max_val = 0.5, 999.99
                    else:
                        min_val, max_val = 0.01, 999999.99

                    # 情况1：值>=10000（明显异常，小数点向左移3位或更多）
                    if value >= 10000:
                        for divisor in [1000, 100, 10]:
                            corrected = value / divisor
                            if min_val <= corrected <= max_val:
                                print(f"  🔧 {field_name}修正: {code} - {original_value:.2f} → {corrected:.2f} (小数点丢失,除以{divisor})")
                                return corrected
                        print(f"  ⚠️  {field_name}异常: {code} - {original_value:.2f} (无法自动修正)")
                        return value

                    # 情况2：值在1000-9999之间
                    elif 1000 <= value < 10000:
                        # 优先尝试除以1000（如19990 → 19.99，27840 → 27.84）
                        corrected = value / 1000
                        if min_val <= corrected <= max_val:
                            print(f"  🔧 {field_name}修正: {code} - {original_value:.0f} → {corrected:.2f} (小数点丢失,除以1000)")
                            return corrected
                        # 否则尝试除以100
                        corrected = value / 100
                        if min_val <= corrected <= max_val:
                            print(f"  🔧 {field_name}修正: {code} - {original_value:.2f} → {corrected:.2f} (小数点丢失,除以100)")
                            return corrected
                        print(f"  ⚠️  {field_name}异常: {code} - {original_value:.2f} (无法自动修正)")
                        return value

                    # 情况3：值在100-999之间，检查是否可能是小数点丢失
                    elif 100 <= value < 1000:
                        corrected = value / 100
                        # 如果原值是整数（小数部分为0），且修正后在合理范围内，则修正
                        if value == int(value) and min_val <= corrected <= (10 if is_price else 999.99):
                            print(f"  🔧 {field_name}修正: {code} - {original_value:.0f} → {corrected:.2f} (可能的小数点丢失,除以100)")
                            return corrected
                        return value

                    # 情况4：值过低
                    elif is_price and value < 0.5 and value > 0:
                        print(f"  ⚠️  {field_name}过低: {code} - {value:.2f} (可能识别错误)")
                        return value

                    return value

                # ========================================
                # 按固定索引提取并修正数据
                # ========================================

                # 索引0: 市价（有小数）
                price = correct_decimal_point(float(numbers[0]), "市价", is_price=True)

                # 索引4: 实际数量（无小数，整数）
                qty = int(float(numbers[4]))

                # 索引8: 成本价（有小数）
                cost_price = correct_decimal_point(float(numbers[8]), "成本价", is_price=True)

                # ========================================
                # 数量合理性检查
                # ========================================
                if qty <= 0 or qty % 100 != 0:
                    print(f"  ⚠️  数量异常: {code} - {qty} (不是100的倍数或<=0)")
                    # 尝试寻找其他合理的数量（索引5或6）
                    for idx in [5, 6]:
                        try:
                            alt_qty = int(float(numbers[idx]))
                            if alt_qty > 0 and alt_qty % 100 == 0:
                                qty = alt_qty
                                print(f"  🔧 数量修正: {code} - 使用索引{idx}的值: {qty}")
                                break
                        except (ValueError, IndexError):
                            continue

                # 创建Position对象
                position = Position(
                    stock_code=code,
                    stock_name="",
                    available_qty=qty,
                    current_price=price,
                    cost_price=cost_price
                )
                positions.append(position)

                # 计算盈亏用于验证
                profit_loss = position.calculate_profit_loss()
                profit_ratio = position.calculate_profit_loss_ratio()

                # 显示识别结果
                print(f"  ✅ 识别: {code} - {qty}股 @ 市价{price:.2f}/成本{cost_price:.2f} (盈亏:{profit_loss:.2f}元, {profit_ratio:.2%})")

            except (ValueError, IndexError) as e:
                print(f"  ⚠️  解析失败 {code}: {e}")
                print(f"     数字列表: {numbers}")
                continue

        return positions

    def get_positions_automatic(self) -> List[Position]:
        """
        自动获取持仓信息（无需人工交互）

        流程:
        1. 自动切换到持仓Tab
        2. 使用固定坐标截图
        3. OCR识别持仓
        4. 返回结果（失败返回空列表）

        返回:
            Position对象列表（失败时返回空列表）
        """
        try:
            # 激活窗口
            if not self.activate_ths_window():
                print("⚠️  无法激活同花顺窗口")
                return []

            # 切换到持仓标签页
            try:
                from ths_mac_trader import THSMacTrader
                trader = THSMacTrader()
                trader.switch_to_position_tab()
                time.sleep(0.5)  # 等待界面切换
            except Exception as e:
                print(f"⚠️  切换标签页失败: {e}")
                # 继续尝试，可能已经在持仓页面

            # 使用固定坐标自动截图
            screenshot_path = self.capture_position_area(use_calibrated_region=True)
            if not screenshot_path:
                print("⚠️  自动截图失败")
                return []

            # OCR识别
            positions = self.extract_positions_with_ocr(screenshot_path)
            if positions:
                print(f"✅ 自动识别成功，获取 {len(positions)} 个持仓")
                return positions
            else:
                print("⚠️  OCR识别失败，返回空列表")
                return []

        except Exception as e:
            print(f"❌ 自动获取持仓失败: {e}")
            return []

    def get_positions_interactive(self) -> List[Position]:
        """
        交互式获取持仓信息

        流程:
        1. 截取持仓区域
        2. 尝试OCR识别
        3. 如果OCR失败，手动输入

        返回:
            Position对象列表
        """
        print("\n" + "="*70)
        print("📊 获取持仓信息")
        print("="*70)
        print("\n选择方式：")
        print("1. 使用固定坐标截图 + OCR识别（推荐，快速）")
        print("2. 手动指定区域截图 + OCR识别")
        print("3. 查看已有截图 + 手动输入")
        print("4. 直接手动输入")
        print("="*70)

        choice = input("\n请选择 [1-4]: ").strip()

        if choice == '1':
            # 使用固定坐标自动截图 + OCR
            screenshot_path = self.capture_position_area(use_calibrated_region=True)
            if screenshot_path:
                positions = self.extract_positions_with_ocr(screenshot_path)
                if positions:
                    return positions
                else:
                    print("\n⚠️  OCR识别失败，切换到手动输入")
                    return self.extract_positions_manual(screenshot_path)
            else:
                print("\n⚠️  截图失败，切换到手动输入")
                return self.extract_positions_manual()

        elif choice == '2':
            # 手动指定区域截图 + OCR
            screenshot_path = self.capture_position_area(use_calibrated_region=False)
            if screenshot_path:
                positions = self.extract_positions_with_ocr(screenshot_path)
                if positions:
                    return positions
                else:
                    print("\n⚠️  OCR识别失败，切换到手动输入")
                    return self.extract_positions_manual(screenshot_path)
            else:
                print("\n⚠️  截图失败，切换到手动输入")
                return self.extract_positions_manual()

        elif choice == '3':
            # 查看截图 + 手动输入
            screenshot_path = input("请输入截图路径 (或按 Enter 使用默认): ").strip()
            if not screenshot_path:
                screenshot_path = "screemshot/img.png"
            return self.extract_positions_manual(screenshot_path)

        else:
            # 直接手动输入
            return self.extract_positions_manual(None)


def main():
    """主函数 - 演示用法"""
    ocr = PositionOCR()

    print("""
╔══════════════════════════════════════════════════════════╗
║              持仓OCR识别工具                              ║
╠══════════════════════════════════════════════════════════╣
║  1. 交互式获取持仓（推荐）                                ║
║  2. 从截图文件识别                                        ║
║  3. 使用固定坐标截图（快速）                              ║
║  4. 手动指定区域截图                                      ║
║  5. 测试OCR功能                                           ║
║  9. 校准持仓列表区域坐标                                  ║
║  0. 退出                                                  ║
╚══════════════════════════════════════════════════════════╝
    """)

    while True:
        choice = input("\n请选择功能 [0-5,9]: ").strip()

        if choice == '0':
            print("再见！")
            break

        elif choice == '1':
            positions = ocr.get_positions_interactive()
            if positions:
                print("\n持仓列表:")
                for pos in positions:
                    print(f"  {pos.stock_code}: {pos.available_qty}股 @ {pos.current_price}")

        elif choice == '2':
            path = input("截图路径: ").strip() or "screemshot/img.png"
            positions = ocr.extract_positions_with_ocr(path)
            if positions:
                print("\n持仓列表:")
                for pos in positions:
                    print(f"  {pos.stock_code}: {pos.available_qty}股 @ {pos.current_price}")

        elif choice == '3':
            # 使用固定坐标截图
            screenshot_path = ocr.capture_position_area(use_calibrated_region=True)
            if screenshot_path:
                print(f"✅ 截图完成: {screenshot_path}")
                # 询问是否识别
                test = input("是否立即识别？(y/n): ").strip().lower()
                if test == 'y':
                    positions = ocr.extract_positions_with_ocr(screenshot_path)
                    if positions:
                        print("\n持仓列表:")
                        for pos in positions:
                            print(f"  {pos.stock_code}: {pos.available_qty}股 @ {pos.current_price}")

        elif choice == '4':
            # 手动指定区域截图
            ocr.capture_position_area(use_calibrated_region=False)

        elif choice == '5':
            try:
                import pytesseract
                from PIL import Image
                print("✅ OCR依赖已安装")
                print(f"Tesseract版本: {pytesseract.get_tesseract_version()}")
            except ImportError:
                print("❌ 缺少OCR依赖，请安装:")
                print("   pip install pytesseract pillow")
                print("   brew install tesseract tesseract-lang")

        elif choice == '9':
            # 校准持仓列表区域
            print("\n正在启动校准工具...")
            import subprocess
            import sys
            subprocess.run([sys.executable, "calibrate_position_region.py"])

        else:
            print("无效选择")


if __name__ == "__main__":
    main()
