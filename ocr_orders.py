#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
委托OCR识别工具
从同花顺委托界面截图中提取委托信息
"""

import pyautogui
import time
import subprocess
import re
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Order:
    """委托订单数据类"""
    order_no: str          # 委托编号
    stock_code: str        # 股票代码
    stock_name: str        # 股票名称
    direction: str         # 买卖方向（买入/卖出）
    price: float           # 委托价格
    quantity: int          # 委托数量
    traded_quantity: int   # 成交数量
    status: str           # 状态（已报/部成/已成/已撤等）

    def __str__(self):
        return f"Order({self.stock_code}, {self.direction}, {self.price}×{self.quantity}, {self.status})"


class OrderOCR:
    """委托OCR识别器"""

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

    def capture_order_area(self, region: tuple = None, save_path: str = "orders_screenshot.png",
                          use_calibrated_region: bool = True) -> str:
        """
        截取委托区域

        参数:
            region: (x, y, width, height) 截图区域，None表示使用校准的坐标
            save_path: 保存路径
            use_calibrated_region: 是否使用校准的固定坐标区域（默认True）

        返回:
            截图文件路径
        """
        print("\n" + "="*70)
        print("📸 截取委托区域")
        print("="*70)

        # 激活窗口
        if not self.activate_ths_window():
            print("⚠️  无法激活同花顺窗口")
            return None

        # 切换到委托标签页（确保显示委托界面）
        trader_instance = None
        try:
            from ths_mac_trader import THSMacTrader
            trader_instance = THSMacTrader()
            trader_instance.switch_to_order_tab()
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
                rel_x, rel_y, width, height = trader_instance.coords_relative.get('order_list_region', (259, 378, 1102, 689))

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
            print("1. 将鼠标移动到委托列表的左上角")
            input("2. 按 Enter 记录第一个点...")
            x1, y1 = pyautogui.position()
            print(f"   ✅ 左上角: ({x1}, {y1})")

            print("\n3. 将鼠标移动到委托列表的右下角")
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

    def extract_orders_with_ocr(self, screenshot_path: str) -> List[Order]:
        """
        使用OCR从截图中提取委托信息

        参数:
            screenshot_path: 截图路径

        返回:
            Order对象列表
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

        # 解析委托信息
        orders = self._parse_orders_from_text(text)

        return orders

    def _parse_orders_from_text(self, text: str) -> List[Order]:
        """
        从OCR文本中解析委托信息

        委托表格实际列顺序（同花顺）：
        1. 委托日期(8位) 2. 时间 3. 证券代码(6位) 4. 证券名称 5. 操作（买入/卖出）
        6. 备注 7. 委托数量 8. 已成交 9. 委托价格

        参数:
            text: OCR识别的文本

        返回:
            Order对象列表
        """
        orders = []

        # 按行处理
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过表头行
            if '委托日期' in line or '证券代码' in line or '委托数量' in line:
                continue

            # 识别买卖方向（必须包含买卖操作才是有效行）
            direction = "未知"
            if "买" in line or "买入" in line:
                direction = "买入"
            elif "卖" in line or "卖出" in line:
                direction = "卖出"
            else:
                # 不包含买卖方向的行，跳过
                continue

            # 使用正则表达式分别提取关键信息
            # 1. 查找股票代码（6位数字，且要在时间之后）
            # 避免日期(8位)和时间被误识别
            code_pattern = r'\b([0-9]{6})\b'
            codes = re.findall(code_pattern, line)

            # 过滤掉可能是日期或时间的部分（通常在最前面）
            # 股票代码通常是 300XXX, 600XXX, 000XXX, 002XXX, 603XXX 等
            stock_code = None
            for code in codes:
                # 检查是否是有效的股票代码格式
                if code.startswith(('0', '3', '6')):
                    stock_code = code
                    break

            if not stock_code and codes:
                # 如果没有找到以0/3/6开头的，取最后一个6位数字
                stock_code = codes[-1] if len(codes[-1]) == 6 else None

            if not stock_code:
                continue

            # 2. 提取所有数字（包括小数）
            # 使用更精确的模式，避免日期时间干扰
            number_pattern = r'\b(\d+\.\d+|\d+)\b'
            all_numbers = re.findall(number_pattern, line)

            # 3. 查找价格（带小数点的数字，通常在20-50范围内）
            price = 0.0
            for num in all_numbers:
                if '.' in num:
                    val = float(num)
                    # 股票价格通常在 0.01 - 1000 范围内
                    if 0.01 <= val <= 1000:
                        price = val
                        break

            # 4. 查找委托数量和已成交数量
            # 委托数量通常是100的倍数，且较大（如100, 200, 400等）
            # 已成交数量紧跟在委托数量之后
            integers = []
            integer_positions = []  # 记录数字在行中的位置
            for num in all_numbers:
                if '.' not in num:
                    val = int(num)
                    # 过滤掉明显是日期(8位)、时间(6位)的数字
                    if len(num) <= 5 and val >= 0:
                        integers.append(val)
                        integer_positions.append(line.find(num))

            quantity = 0
            traded_qty = 0
            quantity_idx = -1

            # 查找委托数量（通常是较大的整数，且是100的倍数）
            for i, val in enumerate(integers):
                if val >= 100 and val % 100 == 0:
                    quantity = val
                    quantity_idx = i
                    break

            # 如果没找到100的倍数，在合理范围内取最大的正整数
            if quantity == 0 and integers:
                # 过滤掉太小的数字（如15, 21这种可能是时间的部分）
                valid_quantities = [v for v in integers if v >= 50]
                if valid_quantities:
                    quantity = max(valid_quantities)
                    quantity_idx = integers.index(quantity)
                else:
                    quantity = max(integers)
                    quantity_idx = integers.index(quantity)

            # 查找已成交数量（在委托数量之后的第一个数字）
            if quantity_idx >= 0 and quantity_idx + 1 < len(integers):
                traded_qty = integers[quantity_idx + 1]

            # 5. 提取股票名称（在股票代码后的中文字符）
            stock_name = ""
            code_pos = line.find(stock_code)
            if code_pos != -1:
                # 查找股票代码后的第一段中文
                after_code = line[code_pos + 6:]
                name_match = re.search(r'[\u4e00-\u9fa5]+', after_code)
                if name_match:
                    stock_name = name_match.group(0)

            # 6. 提取状态信息
            status = "未知"
            if "未成交" in line:
                status = "未成交"
            elif "已成" in line and "部成" not in line:
                status = "已成"
            elif "部成" in line:
                status = "部成"
            elif "已撤" in line:
                status = "已撤"

            try:
                order = Order(
                    order_no="",
                    stock_code=stock_code,
                    stock_name=stock_name,
                    direction=direction,
                    price=price,
                    quantity=quantity,
                    traded_quantity=traded_qty,
                    status=status
                )
                orders.append(order)
                print(f"  ✅ 识别: {stock_code} ({stock_name}) {direction} {price}×{quantity} (已成交:{traded_qty})")
            except (ValueError, IndexError) as e:
                print(f"  ⚠️  解析失败: {e}")
                continue

        return orders

    def get_orders_interactive(self) -> List[Order]:
        """
        交互式获取委托信息

        流程:
        1. 截取委托区域
        2. OCR识别
        3. 返回委托列表

        返回:
            Order对象列表
        """
        print("\n" + "="*70)
        print("📊 获取委托信息")
        print("="*70)
        print("\n选择方式：")
        print("1. 使用固定坐标截图 + OCR识别（推荐，快速）")
        print("2. 手动指定区域截图 + OCR识别")
        print("3. 从已有截图识别")
        print("="*70)

        choice = input("\n请选择 [1-3]: ").strip()

        if choice == '1':
            # 使用固定坐标自动截图 + OCR
            screenshot_path = self.capture_order_area(use_calibrated_region=True)
            if screenshot_path:
                orders = self.extract_orders_with_ocr(screenshot_path)
                return orders
            else:
                print("\n⚠️  截图失败")
                return []

        elif choice == '2':
            # 手动指定区域截图 + OCR
            screenshot_path = self.capture_order_area(use_calibrated_region=False)
            if screenshot_path:
                orders = self.extract_orders_with_ocr(screenshot_path)
                return orders
            else:
                print("\n⚠️  截图失败")
                return []

        elif choice == '3':
            # 从截图文件识别
            screenshot_path = input("请输入截图路径 (或按 Enter 使用默认 orders_screenshot.png): ").strip()
            if not screenshot_path:
                screenshot_path = "orders_screenshot.png"
            return self.extract_orders_with_ocr(screenshot_path)

        else:
            print("无效选择")
            return []


def main():
    """主函数 - 演示用法"""
    ocr = OrderOCR()

    print("""
╔══════════════════════════════════════════════════════════╗
║              委托OCR识别工具                              ║
╠══════════════════════════════════════════════════════════╣
║  1. 交互式获取委托（推荐）                                ║
║  2. 从截图文件识别                                        ║
║  3. 使用固定坐标截图（快速）                              ║
║  4. 测试OCR功能                                           ║
║  0. 退出                                                  ║
╚══════════════════════════════════════════════════════════╝
    """)

    while True:
        choice = input("\n请选择功能 [0-4]: ").strip()

        if choice == '0':
            print("再见！")
            break

        elif choice == '1':
            orders = ocr.get_orders_interactive()
            if orders:
                print("\n委托列表:")
                for order in orders:
                    print(f"  {order}")

        elif choice == '2':
            path = input("截图路径: ").strip() or "orders_screenshot.png"
            orders = ocr.extract_orders_with_ocr(path)
            if orders:
                print("\n委托列表:")
                for order in orders:
                    print(f"  {order}")

        elif choice == '3':
            screenshot_path = ocr.capture_order_area(use_calibrated_region=True)
            if screenshot_path:
                print(f"✅ 截图完成: {screenshot_path}")
                test = input("是否立即识别？(y/n): ").strip().lower()
                if test == 'y':
                    orders = ocr.extract_orders_with_ocr(screenshot_path)
                    if orders:
                        print("\n委托列表:")
                        for order in orders:
                            print(f"  {order}")

        elif choice == '4':
            try:
                import pytesseract
                from PIL import Image
                print("✅ OCR依赖已安装")
                print(f"Tesseract版本: {pytesseract.get_tesseract_version()}")
            except ImportError:
                print("❌ 缺少OCR依赖，请安装:")
                print("   pip install pytesseract pillow")
                print("   brew install tesseract tesseract-lang")

        else:
            print("无效选择")


if __name__ == "__main__":
    main()
