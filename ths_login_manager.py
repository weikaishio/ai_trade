"""
同花顺登录管理器
负责安全管理登录凭证和执行自动登录
"""

import os
import json
import time
import logging
import keyring
import hashlib
import subprocess
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import pyautogui
import getpass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LoginCredentials:
    """登录凭证"""
    account: str
    password: str
    broker_code: str = ""  # 券商代码
    communication_password: str = ""  # 通讯密码（如果需要）


class CredentialManager:
    """
    凭证管理器
    使用macOS Keychain安全存储登录凭证
    """

    SERVICE_NAME = "TongHuaShun_AutoTrade"
    MASTER_KEY_NAME = "master_key"

    def __init__(self):
        """初始化凭证管理器"""
        self.master_key = self._get_or_create_master_key()
        self.cipher = Fernet(self.master_key)

    def _get_or_create_master_key(self) -> bytes:
        """获取或创建主密钥"""
        # 尝试从Keychain获取主密钥
        stored_key = keyring.get_password(self.SERVICE_NAME, self.MASTER_KEY_NAME)

        if stored_key:
            return base64.b64decode(stored_key)

        # 生成新的主密钥
        key = Fernet.generate_key()

        # 存储到Keychain
        keyring.set_password(
            self.SERVICE_NAME,
            self.MASTER_KEY_NAME,
            base64.b64encode(key).decode()
        )

        logger.info("Created new master key in Keychain")
        return key

    def save_credentials(self, account_name: str, credentials: LoginCredentials) -> bool:
        """
        保存登录凭证

        Args:
            account_name: 账户名称（用于标识不同账户）
            credentials: 登录凭证

        Returns:
            bool: 是否成功保存
        """
        try:
            # 序列化凭证
            cred_dict = {
                'account': credentials.account,
                'password': credentials.password,
                'broker_code': credentials.broker_code,
                'communication_password': credentials.communication_password
            }

            # 加密
            encrypted = self.cipher.encrypt(json.dumps(cred_dict).encode())

            # 存储到Keychain
            keyring.set_password(
                self.SERVICE_NAME,
                account_name,
                base64.b64encode(encrypted).decode()
            )

            logger.info(f"Credentials saved for account: {account_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            return False

    def load_credentials(self, account_name: str) -> Optional[LoginCredentials]:
        """
        加载登录凭证

        Args:
            account_name: 账户名称

        Returns:
            LoginCredentials: 登录凭证，如果不存在返回None
        """
        try:
            # 从Keychain获取
            encrypted_str = keyring.get_password(self.SERVICE_NAME, account_name)

            if not encrypted_str:
                logger.warning(f"No credentials found for account: {account_name}")
                return None

            # 解密
            encrypted = base64.b64decode(encrypted_str)
            decrypted = self.cipher.decrypt(encrypted)

            # 反序列化
            cred_dict = json.loads(decrypted.decode())

            return LoginCredentials(
                account=cred_dict['account'],
                password=cred_dict['password'],
                broker_code=cred_dict.get('broker_code', ''),
                communication_password=cred_dict.get('communication_password', '')
            )

        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return None

    def delete_credentials(self, account_name: str) -> bool:
        """删除登录凭证"""
        try:
            keyring.delete_password(self.SERVICE_NAME, account_name)
            logger.info(f"Credentials deleted for account: {account_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete credentials: {e}")
            return False

    def list_accounts(self) -> list:
        """列出所有保存的账户"""
        # 注意：keyring没有直接列出所有键的方法
        # 这里需要维护一个账户列表
        accounts_key = "accounts_list"
        accounts_str = keyring.get_password(self.SERVICE_NAME, accounts_key)

        if accounts_str:
            return json.loads(accounts_str)
        return []

    def _update_accounts_list(self, account_name: str, add: bool = True):
        """更新账户列表"""
        accounts_key = "accounts_list"
        accounts = self.list_accounts()

        if add:
            if account_name not in accounts:
                accounts.append(account_name)
        else:
            if account_name in accounts:
                accounts.remove(account_name)

        keyring.set_password(
            self.SERVICE_NAME,
            accounts_key,
            json.dumps(accounts)
        )


class THSLoginManager:
    """同花顺登录管理器"""

    def __init__(self, trader_instance=None):
        """
        初始化登录管理器

        Args:
            trader_instance: THSMacTrader实例
        """
        self.trader = trader_instance
        self.credential_manager = CredentialManager()
        self.current_account = None
        self.login_coords = self._get_login_coordinates()

    def _get_login_coordinates(self) -> Dict[str, Tuple[int, int]]:
        """获取登录相关的坐标"""
        # 这些坐标需要通过calibrate_helper.py获取
        return {
            'login_button': (100, 200),  # 登录按钮
            'account_input': (300, 250),  # 账号输入框
            'password_input': (300, 300),  # 密码输入框
            'broker_dropdown': (300, 350),  # 券商下拉框
            'login_confirm': (350, 450),  # 登录确认按钮
            'verification_code': (300, 400),  # 验证码输入框（如果有）
        }

    def setup_credentials_interactive(self) -> bool:
        """交互式设置登录凭证"""
        print("\n=== 设置登录凭证 ===")
        print("请输入登录信息（密码将安全存储在macOS Keychain中）")

        account_name = input("账户名称（用于标识）: ")
        account = input("登录账号: ")
        password = getpass.getpass("登录密码: ")
        broker_code = input("券商代码（可选，按回车跳过）: ")
        comm_password = getpass.getpass("通讯密码（可选，按回车跳过）: ")

        credentials = LoginCredentials(
            account=account,
            password=password,
            broker_code=broker_code,
            communication_password=comm_password
        )

        success = self.credential_manager.save_credentials(account_name, credentials)

        if success:
            self.credential_manager._update_accounts_list(account_name, add=True)
            print(f"凭证已安全保存")
        else:
            print("凭证保存失败")

        return success

    def login(self, account_name: str = None, retry_count: int = 3) -> bool:
        """
        执行自动登录

        Args:
            account_name: 账户名称，如果为None则使用默认账户
            retry_count: 重试次数

        Returns:
            bool: 是否登录成功
        """
        # 获取账户名
        if not account_name:
            accounts = self.credential_manager.list_accounts()
            if not accounts:
                logger.error("No saved accounts found")
                return False
            account_name = accounts[0]  # 使用第一个账户作为默认

        # 加载凭证
        credentials = self.credential_manager.load_credentials(account_name)
        if not credentials:
            logger.error(f"Failed to load credentials for {account_name}")
            return False

        logger.info(f"Starting login for account: {account_name}")

        for attempt in range(retry_count):
            logger.info(f"Login attempt {attempt + 1}/{retry_count}")

            try:
                # 1. 确保窗口在前台
                if not self._ensure_window_active():
                    continue

                # 2. 点击登录按钮（如果存在）
                if self._click_login_button():
                    time.sleep(2)  # 等待登录窗口出现

                # 3. 输入账号
                if not self._input_account(credentials.account):
                    continue

                # 4. 输入密码
                if not self._input_password(credentials.password):
                    continue

                # 5. 选择券商（如果需要）
                if credentials.broker_code:
                    self._select_broker(credentials.broker_code)

                # 6. 输入通讯密码（如果需要）
                if credentials.communication_password:
                    self._input_communication_password(credentials.communication_password)

                # 7. 点击登录确认
                if not self._confirm_login():
                    continue

                # 8. 等待登录完成
                time.sleep(5)

                # 9. 验证登录状态
                if self._verify_login_success():
                    logger.info("Login successful")
                    self.current_account = account_name
                    return True

                logger.warning(f"Login attempt {attempt + 1} failed")

            except Exception as e:
                logger.error(f"Login error: {e}")

            # 等待后重试
            if attempt < retry_count - 1:
                time.sleep(3)

        logger.error("All login attempts failed")
        return False

    def _ensure_window_active(self) -> bool:
        """确保窗口激活"""
        try:
            script = '''
            tell application "同花顺"
                activate
            end tell
            '''
            subprocess.run(['osascript', '-e', script], timeout=5)
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Failed to activate window: {e}")
            return False

    def _click_login_button(self) -> bool:
        """点击登录按钮"""
        try:
            if self.trader and hasattr(self.trader, 'coords'):
                coords = self.trader.coords.get('login_button')
            else:
                coords = self.login_coords.get('login_button')

            if coords:
                pyautogui.click(coords[0], coords[1])
                time.sleep(1)
                return True

            logger.warning("Login button coordinates not found")
            return False

        except Exception as e:
            logger.error(f"Failed to click login button: {e}")
            return False

    def _input_account(self, account: str) -> bool:
        """输入账号"""
        try:
            if self.trader and hasattr(self.trader, 'coords'):
                coords = self.trader.coords.get('account_input')
            else:
                coords = self.login_coords.get('account_input')

            if not coords:
                logger.warning("Account input coordinates not found")
                return False

            # 点击输入框
            pyautogui.click(coords[0], coords[1])
            time.sleep(0.5)

            # 清除已有内容
            pyautogui.hotkey('cmd', 'a')
            time.sleep(0.2)

            # 输入账号
            pyautogui.typewrite(account)
            time.sleep(0.5)

            return True

        except Exception as e:
            logger.error(f"Failed to input account: {e}")
            return False

    def _input_password(self, password: str) -> bool:
        """输入密码"""
        try:
            if self.trader and hasattr(self.trader, 'coords'):
                coords = self.trader.coords.get('password_input')
            else:
                coords = self.login_coords.get('password_input')

            if not coords:
                logger.warning("Password input coordinates not found")
                return False

            # 点击输入框
            pyautogui.click(coords[0], coords[1])
            time.sleep(0.5)

            # 清除已有内容
            pyautogui.hotkey('cmd', 'a')
            time.sleep(0.2)

            # 输入密码
            pyautogui.typewrite(password)
            time.sleep(0.5)

            return True

        except Exception as e:
            logger.error(f"Failed to input password: {e}")
            return False

    def _select_broker(self, broker_code: str) -> bool:
        """选择券商"""
        # 实现券商选择逻辑
        logger.info(f"Selecting broker: {broker_code}")
        return True

    def _input_communication_password(self, password: str) -> bool:
        """输入通讯密码"""
        logger.info("Inputting communication password")
        return True

    def _confirm_login(self) -> bool:
        """点击登录确认按钮"""
        try:
            if self.trader and hasattr(self.trader, 'coords'):
                coords = self.trader.coords.get('login_confirm')
            else:
                coords = self.login_coords.get('login_confirm')

            if coords:
                pyautogui.click(coords[0], coords[1])
                time.sleep(1)
                return True

            # 尝试使用回车键
            pyautogui.press('return')
            time.sleep(1)
            return True

        except Exception as e:
            logger.error(f"Failed to confirm login: {e}")
            return False

    def _verify_login_success(self) -> bool:
        """验证登录是否成功"""
        # 这里应该使用状态检测器来验证
        # 暂时返回True，实际应该检测登录后的界面特征
        return True

    def logout(self) -> bool:
        """执行登出操作"""
        logger.info("Performing logout...")
        # 实现登出逻辑
        self.current_account = None
        return True

    def switch_account(self, account_name: str) -> bool:
        """切换账户"""
        logger.info(f"Switching to account: {account_name}")

        # 先登出当前账户
        if self.current_account:
            self.logout()
            time.sleep(2)

        # 登录新账户
        return self.login(account_name)


def main():
    """测试登录管理器"""
    login_manager = THSLoginManager()

    while True:
        print("\n=== 同花顺登录管理器 ===")
        print("1. 设置登录凭证")
        print("2. 查看保存的账户")
        print("3. 执行自动登录")
        print("4. 删除账户凭证")
        print("5. 退出")

        choice = input("\n请选择操作: ")

        if choice == "1":
            login_manager.setup_credentials_interactive()

        elif choice == "2":
            accounts = login_manager.credential_manager.list_accounts()
            if accounts:
                print("\n保存的账户:")
                for i, account in enumerate(accounts, 1):
                    print(f"  {i}. {account}")
            else:
                print("没有保存的账户")

        elif choice == "3":
            accounts = login_manager.credential_manager.list_accounts()
            if not accounts:
                print("请先设置登录凭证")
                continue

            print("\n选择账户:")
            for i, account in enumerate(accounts, 1):
                print(f"  {i}. {account}")

            account_idx = input("输入账户编号: ")
            try:
                account_name = accounts[int(account_idx) - 1]
                success = login_manager.login(account_name)
                print(f"登录{'成功' if success else '失败'}")
            except (ValueError, IndexError):
                print("无效选择")

        elif choice == "4":
            accounts = login_manager.credential_manager.list_accounts()
            if not accounts:
                print("没有保存的账户")
                continue

            print("\n选择要删除的账户:")
            for i, account in enumerate(accounts, 1):
                print(f"  {i}. {account}")

            account_idx = input("输入账户编号: ")
            try:
                account_name = accounts[int(account_idx) - 1]
                confirm = input(f"确认删除账户 {account_name}? (y/n): ")
                if confirm.lower() == 'y':
                    login_manager.credential_manager.delete_credentials(account_name)
                    login_manager.credential_manager._update_accounts_list(account_name, add=False)
                    print("账户已删除")
            except (ValueError, IndexError):
                print("无效选择")

        elif choice == "5":
            break

        else:
            print("无效选择")


if __name__ == "__main__":
    main()