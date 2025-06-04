"""
登录窗口模块
提供用户登录、注册和密码重置功能的图形界面。
包含以下主要类：
- LoginWindow: 登录窗口
- RegisterWindow: 注册窗口
- ResetPasswordWindow: 重置密码窗口
- DataUtils: 用户数据管理工具类
"""
import sys
import json
import hashlib
import time
import random
import logging
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox, QStackedWidget, QCheckBox, QHBoxLayout
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QObject, QTimer

# 基础路径
STATIC_PATH = "data/static"
# 登录界面相关图标
ICON_LOGIN_BACKGROUND = f"{STATIC_PATH}/login_background.png"  # 登录界面背景图
ICON_APP = f"{STATIC_PATH}/app_icon.ico"  # 应用程序图标
ICON_USER = f"{STATIC_PATH}/登录.png"  # 用户图标
ICON_PASSWORD = f"{STATIC_PATH}/密码.png"  # 密码图标


class LoginSuccessSignal(QObject):
    """登录成功信号类"""
    login_success = pyqtSignal(str)  # 发送用户名或动作


# 创建全局信号对象
login_signal = LoginSuccessSignal()


class DataUtils:
    """用户数据管理工具类，处理用户数据的读写、加密和验证"""

    def __init__(self):
        self.data_path = Path("data/static/users.json")
        self._init_data_file()
        self._cache = {}
        self._load_cache()

    def _init_data_file(self):
        """初始化用户数据文件"""
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.data_path.exists():
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

    def _load_cache(self):
        try:
            self._cache = self.read_data()
        except Exception as e:
            logging.error(f"加载缓存失败: {e}")
            self._cache = {}

    def read_data(self):
        """读取用户数据文件"""
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"读取数据失败: {e}")
            return {}

    def write_data(self, data):
        """写入用户数据到文件"""
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._cache = data
        except Exception as e:
            logging.error(f"写入数据失败: {e}")
            raise

    def _generate_user_id(self):
        """生成8位用户ID"""
        timestamp = int(time.time() * 1000)
        random_bytes = random.getrandbits(32).to_bytes(4, 'big')
        combined = f"{timestamp}{random_bytes.hex()}"
        return hashlib.sha256(combined.encode()).hexdigest()[:8]

    def register_user(self, username, password):
        """注册新用户"""
        if not username or not password:
            return False, "用户名和密码不能为空"
        data = self.read_data()
        hashed_username = self._hash_username(username)
        if any(user_data["用户名"] == hashed_username for user_data in data.values()):
            return False, "用户名已存在"
        user_id = self._generate_user_id()
        data[user_id] = {
            "用户名": hashed_username,
            "密码": self._hash_password(password),
            "注册时间": time.time(),
            "当前考试": {},
            "考试记录": {}
        }
        self.write_data(data)
        return True, "注册成功"

    def verify_user(self, username, password):
        """验证用户登录信息"""
        try:
            if not username or not password:
                return False, "用户名和密码不能为空"
            data = self._cache
            hashed_username = self._hash_username(username)
            user_id = None
            for uid, user_data in data.items():
                if user_data["用户名"] == hashed_username:
                    user_id = uid
                    break
            if user_id is None:
                return False, "用户不存在"
            stored_password = data[user_id].get("密码")
            if not stored_password:
                return False, "用户数据无效"
            if not self._verify_password(password, stored_password):
                return False, "密码错误"
            return True, "登录成功"
        except Exception as e:
            logging.error(f"验证用户失败: {e}")
            return False, f"验证用户时发生错误：{str(e)}"

    def _hash_username(self, username):
        """对用户名进行哈希处理"""
        return hashlib.sha256(username.encode()).hexdigest()

    @staticmethod
    def _hash_password(password):
        """使用PBKDF2对密码进行哈希加密"""
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt,
            100000,
            dklen=32
        )
        return f"{salt.hex()}${key.hex()}"

    def _verify_password(self, password, stored_hash):
        """验证密码"""
        try:
            if not password or not stored_hash:
                return False
            if '$' not in stored_hash:
                return False
            salt_hex, key_hex = stored_hash.split('$')
            try:
                salt = bytes.fromhex(salt_hex)
                key = bytes.fromhex(key_hex)
            except ValueError:
                return False
            new_key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt,
                100000,
                dklen=32
            )
            return key == new_key
        except Exception as e:
            logging.error(f"密码验证失败: {e}")
            return False


class BaseWindow(QWidget):
    """基础窗口类，提供通用功能"""
    switch_window = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.background_label = QLabel(self)
        self._setup_background()
        self._setup_style()

    def _setup_background(self):
        """设置窗口背景图片"""
        try:
            pixmap = QPixmap(ICON_LOGIN_BACKGROUND)
            scaled_pixmap = pixmap.scaled(
                400, 600,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            crop_x = (scaled_pixmap.width() - 400) // 2 if scaled_pixmap.width() > 400 else 0
            cropped_pixmap = scaled_pixmap.copy(crop_x, 0, 400, 600)
            self.background_label.setPixmap(cropped_pixmap)
            self.background_label.setGeometry(0, 0, 400, 600)
        except Exception as e:
            logging.error(f"背景图片加载失败: {e}")

    def _setup_style(self):
        """设置窗口样式"""
        self.setStyleSheet("""
            QLineEdit {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid #ddd;
                padding: 10px;
                margin: 5px 0;
                border-radius: 5px;
            }
            QPushButton {
                background: #2c3e50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #34495e;
            }
            QLabel#instruction {
                color: #7f8c8d;
                margin-top: 20px;
            }
            QLabel#tab-title {
                font-size: 20px;
                font-weight: bold;
                margin-bottom: 20px;
            }
        """)


class LoginWindow(BaseWindow):
    """登录窗口类"""

    def __init__(self):
        super().__init__()
        self.username = None
        self.password = None
        self.remember_me = None
        self.login_window = None
        self.stacked_widget = None
        self.login_page = None
        self.setWindowTitle("Xdhdyp-BKT")
        self.setWindowIcon(QIcon(ICON_APP))
        self.setFixedSize(800, 600)
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.setGeometry(0, 0, 800, 600)
        self.login_page = QWidget()
        self.register_page = RegisterWindow()
        self.reset_page = ResetPasswordWindow()
        self.init_ui()
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.register_page)
        self.stacked_widget.addWidget(self.reset_page)
        self.switch_window.connect(self._handle_window_switch)
        self.register_page.switch_window.connect(self._handle_window_switch)
        self.reset_page.switch_window.connect(self._handle_window_switch)
        login_signal.login_success.connect(self._handle_login_signal)
        self._load_saved_username()
        self.center_window()
        self.closeEvent = self._handle_close_event
        self._check_auto_login()

    def _check_auto_login(self):
        """检查是否需要自动登录"""
        settings = QSettings("模拟考试系统", "Login")
        saved_username = settings.value("username", "")
        if saved_username:
            QTimer.singleShot(750, lambda: self._auto_login(saved_username))

    def _auto_login(self, username):
        """执行自动登录"""
        try:
            settings = QSettings("模拟考试系统", "Login")
            password = settings.value(f"password_{username}", "")
            if password:
                data_utils = DataUtils()
                success, msg = data_utils.verify_user(username, password)
                if success:
                    from main_window import MainWindow
                    self.login_window = MainWindow(username=username)
                    self.login_window.show()
                    self.hide()
                    login_signal.login_success.emit(username)
                else:
                    settings.remove(f"password_{username}")
                    settings.remove("username")
        except Exception as e:
            logging.error(f"自动登录失败: {e}")

    def _handle_window_switch(self, target):
        """处理窗口切换"""
        try:
            if target == "register":
                self.stacked_widget.setCurrentWidget(self.register_page)
            elif target == "reset":
                self.stacked_widget.setCurrentWidget(self.reset_page)
            elif target == "login":
                self.stacked_widget.setCurrentWidget(self.login_page)
        except Exception as e:
            logging.error(f"切换窗口失败: {e}")
            QMessageBox.critical(self, "错误", f"切换窗口时发生错误：{str(e)}")

    def _handle_login_signal(self, action):
        """处理登录信号"""
        try:
            if action == "logout":
                settings = QSettings("模拟考试系统", "Login")
                settings.remove("username")
                settings.remove(f"password_{self.username.text()}")
                self.username.clear()
                self.password.clear()
                self.remember_me.setChecked(False)
                self.show()
                self.stacked_widget.setCurrentWidget(self.login_page)
        except Exception as e:
            logging.error(f"处理登录信号失败: {e}")
            QMessageBox.critical(self, "错误", f"处理登录信号时发生错误：{str(e)}")

    def _handle_close_event(self, event):
        """处理窗口关闭事件"""
        try:
            settings = QSettings("模拟考试系统", "Login")
            if self.remember_me.isChecked():
                settings.setValue("username", self.username.text())
            else:
                settings.remove("username")
            if self.login_window:
                self.login_window.close()
                self.login_window = None
            if self.isVisible():
                reply = QMessageBox.question(
                    self, "确认退出",
                    "确定要退出系统吗？\n这将关闭所有窗口并结束程序。",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.Yes:
                    event.accept()
                    QApplication.quit()
                else:
                    event.ignore()
            else:
                event.accept()
        except Exception as e:
            logging.error(f"关闭窗口时发生错误: {e}")
            event.accept()

    def center_window(self):
        """将窗口居中显示"""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def init_ui(self):
        """初始化登录窗口的用户界面"""
        container = QWidget(self.login_page)
        container.setGeometry(400, 0, 400, 600)
        layout = QVBoxLayout(container)
        title = QLabel("登录")
        title.setObjectName("tab-title")
        layout.addWidget(title)

        # 用户名输入框
        self.username = QLineEdit()
        self.username.setPlaceholderText("请输入用户名")
        self.username.addAction(QIcon(ICON_USER), QLineEdit.ActionPosition.LeadingPosition)
        layout.addWidget(self.username)

        # 密码输入框
        self.password = QLineEdit()
        self.password.setPlaceholderText("请输入密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.addAction(QIcon(ICON_PASSWORD), QLineEdit.ActionPosition.LeadingPosition)
        layout.addWidget(self.password)

        # 记住我复选框
        self.remember_me = QCheckBox("记住我")
        layout.addWidget(self.remember_me)

        login_btn = QPushButton("登录")
        login_btn.clicked.connect(self.handle_login)
        layout.addWidget(login_btn)

        links_layout = QHBoxLayout()
        register_link = QLabel("<a href='register' style='color: #3498db; text-decoration: none;'>没有账号？去注册</a>")
        register_link.linkActivated.connect(lambda: self.switch_window.emit("register"))
        forget_link = QLabel("<a href='reset' style='color: #3498db; text-decoration: none;'>忘记密码？</a>")
        forget_link.linkActivated.connect(lambda: self.switch_window.emit("reset"))
        links_layout.addWidget(register_link)
        links_layout.addWidget(forget_link)
        layout.addLayout(links_layout)

        QTimer.singleShot(0, self._fix_icon_pos)

    def _fix_icon_pos(self):
        """修正图标位置和高度"""
        self.username.show()
        self.password.show()

    def _load_saved_username(self):
        """加载保存的用户名"""
        settings = QSettings("模拟考试系统", "Login")
        saved_username = settings.value("username", "")
        if saved_username:
            self.username.setText(saved_username)
            self.remember_me.setChecked(True)

    def handle_login(self):
        """处理用户登录逻辑"""
        try:
            username = self.username.text().strip()
            password = self.password.text().strip()
            if not username or not password:
                QMessageBox.warning(self, "错误", "用户名和密码不能为空")
                return

            settings = QSettings("模拟考试系统", "Login")
            if self.remember_me.isChecked():
                settings.setValue("username", username)
                settings.setValue(f"password_{username}", password)
            else:
                settings.remove("username")
                settings.remove(f"password_{username}")

            data_utils = DataUtils()
            success, msg = data_utils.verify_user(username, password)
            if success:
                QMessageBox.information(self, "成功", f"欢迎回来，{username}！")
                from main_window import MainWindow
                self.login_window = MainWindow(username=username)
                self.login_window.show()
                self.hide()
                login_signal.login_success.emit(username)
            else:
                QMessageBox.warning(self, "错误", msg)
        except Exception as e:
            logging.error(f"登录处理失败: {e}")
            QMessageBox.critical(self, "错误", f"登录过程中发生错误：{str(e)}")

    def handle_logout(self):
        """处理退出登录"""
        try:
            reply = QMessageBox.question(
                self, "确认退出",
                "确定要退出登录吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                if self.login_window:
                    self.login_window.close()
                    self.login_window = None
                self.username.clear()
                self.password.clear()
                self.remember_me.setChecked(False)
                self.show()
        except Exception as e:
            logging.error(f"退出登录失败: {e}")
            QMessageBox.critical(self, "错误", f"退出登录时发生错误：{str(e)}")


class RegisterWindow(BaseWindow):
    """注册窗口类"""

    def __init__(self):
        super().__init__()
        self.username = None
        self.password = None
        self.confirm_password = None
        self.show_password = None
        self.setWindowTitle("模拟考试系统 - 注册")
        self.init_ui()

    def init_ui(self):
        """初始化注册界面"""
        container = QWidget(self)
        container.setGeometry(400, 0, 400, 600)
        layout = QVBoxLayout(container)
        title = QLabel("注册")
        title.setObjectName("tab-title")
        layout.addWidget(title)

        # 用户名输入框
        self.username = QLineEdit()
        self.username.setPlaceholderText("请输入用户名")
        self.username.addAction(QIcon(ICON_USER), QLineEdit.ActionPosition.LeadingPosition)
        layout.addWidget(self.username)

        # 密码输入框
        self.password = QLineEdit()
        self.password.setPlaceholderText("请输入密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.addAction(QIcon(ICON_PASSWORD), QLineEdit.ActionPosition.LeadingPosition)
        layout.addWidget(self.password)

        # 确认密码输入框
        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("请确认密码")
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.addAction(QIcon(ICON_PASSWORD), QLineEdit.ActionPosition.LeadingPosition)
        layout.addWidget(self.confirm_password)

        self.show_password = QCheckBox("显示密码")
        self.show_password.stateChanged.connect(self._toggle_password_visibility)
        layout.addWidget(self.show_password)

        register_btn = QPushButton("注册")
        register_btn.clicked.connect(self.handle_registration)
        layout.addWidget(register_btn)

        login_link = QLabel("<a href='login' style='color: #3498db; text-decoration: none;'>已有账号？去登录</a>")
        login_link.linkActivated.connect(lambda: self.switch_window.emit("login"))
        layout.addWidget(login_link)

        QTimer.singleShot(0, self._fix_icon_pos)

    def _fix_icon_pos(self):
        """修正图标位置和高度"""
        self.username.show()
        self.password.show()
        self.confirm_password.show()

    def _toggle_password_visibility(self, state):
        """切换密码显示状态"""
        if state == Qt.CheckState.Checked.value:
            self.password.setEchoMode(QLineEdit.EchoMode.Normal)
            self.confirm_password.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.password.setEchoMode(QLineEdit.EchoMode.Password)
            self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)

    def handle_registration(self):
        """处理注册请求"""
        try:
            username = self.username.text().strip()
            password = self.password.text()
            confirm = self.confirm_password.text()
            if not username or not password or not confirm:
                QMessageBox.warning(self, "错误", "用户名和密码不能为空")
                return
            if password != confirm:
                QMessageBox.warning(self, "错误", "两次输入的密码不一致")
                return
            data_utils = DataUtils()
            success, msg = data_utils.register_user(username, password)
            if success:
                QMessageBox.information(self, "成功", "注册成功，请登录")
                self.username.clear()
                self.password.clear()
                self.confirm_password.clear()
                self.show_password.setChecked(False)
                self.switch_window.emit("login")
            else:
                QMessageBox.warning(self, "错误", msg)
        except Exception as e:
            logging.error(f"注册失败: {e}")
            QMessageBox.critical(self, "错误", f"注册过程中发生错误：{str(e)}")


class ResetPasswordWindow(BaseWindow):
    """重置密码窗口类"""

    def __init__(self):
        super().__init__()
        self.username = None
        self.password = None
        self.confirm_password = None
        self.init_ui()

    def init_ui(self):
        """初始化重置密码界面"""
        container = QWidget(self)
        container.setGeometry(400, 0, 400, 600)
        layout = QVBoxLayout(container)
        title = QLabel("重置密码")
        title.setObjectName("tab-title")
        layout.addWidget(title)

        # 用户名输入框
        self.username = QLineEdit()
        self.username.setPlaceholderText("请输入用户名")
        self.username.addAction(QIcon(ICON_USER), QLineEdit.ActionPosition.LeadingPosition)
        layout.addWidget(self.username)

        # 密码输入框
        self.password = QLineEdit()
        self.password.setPlaceholderText("请输入新密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.addAction(QIcon(ICON_PASSWORD), QLineEdit.ActionPosition.LeadingPosition)
        layout.addWidget(self.password)

        # 确认密码输入框
        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("请确认新密码")
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password.addAction(QIcon(ICON_PASSWORD), QLineEdit.ActionPosition.LeadingPosition)
        layout.addWidget(self.confirm_password)

        reset_btn = QPushButton("重置密码")
        reset_btn.clicked.connect(self.handle_reset)
        layout.addWidget(reset_btn)

        login_link = QLabel("<a href='login' style='color: #3498db; text-decoration: none;'>返回登录</a>")
        login_link.linkActivated.connect(lambda: self.switch_window.emit("login"))
        layout.addWidget(login_link)

        QTimer.singleShot(0, self._fix_icon_pos)

    def _fix_icon_pos(self):
        """修正图标位置和高度"""
        self.username.show()
        self.password.show()
        self.confirm_password.show()

    def handle_reset(self):
        """处理密码重置请求"""
        try:
            username = self.username.text().strip()
            password = self.password.text()
            confirm = self.confirm_password.text()
            if not all([username, password, confirm]):
                QMessageBox.warning(self, "错误", "所有字段都必须填写")
                return
            if password != confirm:
                QMessageBox.warning(self, "错误", "两次输入的密码不一致")
                return
            data_utils = DataUtils()
            data = data_utils.read_data()
            hashed_username = data_utils._hash_username(username)
            user_id = None
            for uid, user_data in data.items():
                if user_data["用户名"] == hashed_username:
                    user_id = uid
                    break
            if user_id is None:
                QMessageBox.warning(self, "错误", "用户不存在")
                return
            data[user_id]["密码"] = data_utils._hash_password(password)
            data_utils.write_data(data)
            QMessageBox.information(self, "成功", "密码重置成功，请登录")
            self.username.clear()
            self.password.clear()
            self.confirm_password.clear()
            self.switch_window.emit("login")
        except Exception as e:
            logging.error(f"重置密码失败: {e}")
            QMessageBox.critical(self, "错误", f"重置密码过程中发生错误：{str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())