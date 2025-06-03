##login_window.py

import sys
import json
import hashlib
import time
import random
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QMessageBox, QStackedWidget, QCheckBox, QHBoxLayout
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt, pyqtSignal, QSettings, QObject, QTimer

# 定义登录成功信号
class LoginSuccessSignal(QObject):
    login_success = pyqtSignal(str)  # 发送用户名或动作

# 创建全局信号对象
login_signal = LoginSuccessSignal()

class DataUtils:
    """
    用户数据管理工具类
    
    负责处理用户数据的读写、用户注册、登录验证等功能。
    用户数据以JSON格式存储在本地文件中，密码使用PBKDF2加密。
    """
    
    def __init__(self):
        """
        初始化数据工具类
        
        设置用户数据文件路径并确保数据文件存在
        """
        self.data_path = Path("data/static/users.json")
        self._init_data_file()
        self._cache = {}  # 添加缓存
        self._load_cache()  # 加载缓存

    def _init_data_file(self):
        """
        初始化用户数据文件
        
        如果数据文件不存在，则创建一个空的JSON文件
        """
        self.data_path.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
        if not self.data_path.exists():
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

    def _load_cache(self):
        """加载数据到缓存"""
        try:
            self._cache = self.read_data()
        except Exception as e:
            logging.error(f"加载缓存失败: {e}")
            self._cache = {}

    def read_data(self):
        """
        读取用户数据
        
        Returns:
            dict: 包含所有用户信息的字典
        """
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"读取数据失败: {e}")
            return {}

    def write_data(self, data):
        """
        写入用户数据到文件
        
        Args:
            data (dict): 要写入的用户数据字典
        """
        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._cache = data  # 更新缓存
        except Exception as e:
            logging.error(f"写入数据失败: {e}")
            raise

    def _generate_user_id(self):
        """
        生成8位用户ID
        
        基于Unix时间戳生成一个8位的伪随机ID
        
        Returns:
            str: 8位用户ID
        """
        # 使用更安全的ID生成方式
        timestamp = int(time.time() * 1000)  # 毫秒级时间戳
        random_bytes = random.getrandbits(32).to_bytes(4, 'big')
        combined = f"{timestamp}{random_bytes.hex()}"
        return hashlib.sha256(combined.encode()).hexdigest()[:8]

    def register_user(self, username, password):
        """
        注册新用户
        
        Args:
            username (str): 用户名
            password (str): 密码
            
        Returns:
            tuple: (成功状态(bool), 消息(str))
        """
        # 只校验非空
        if not username or not password:
            return False, "用户名和密码不能为空"

        data = self.read_data()
        hashed_username = self._hash_username(username)
        
        # 检查用户名是否已存在
        if any(user_data["用户名"] == hashed_username for user_data in data.values()):
            return False, "用户名已存在"

        # 生成用户ID并创建新用户记录
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
        """
        验证用户登录信息
        
        Args:
            username (str): 用户名
            password (str): 密码
            
        Returns:
            tuple: (验证结果(bool), 消息(str))
        """
        try:
            if not username or not password:
                return False, "用户名和密码不能为空"

            data = self._cache  # 使用缓存
            hashed_username = self._hash_username(username)
            
            # 查找用户
            user_id = None
            for uid, user_data in data.items():
                if user_data["用户名"] == hashed_username:
                    user_id = uid
                    break
            
            if user_id is None:
                return False, "用户不存在"

            # 验证密码
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
        """
        对用户名进行哈希处理
        
        Args:
            username (str): 原始用户名
            
        Returns:
            str: 哈希后的用户名
        """
        return hashlib.sha256(username.encode()).hexdigest()

    @staticmethod
    def _hash_password(password):
        """使用PBKDF2对密码进行哈希加密"""
        import hashlib
        import os
        salt = os.urandom(16)  # 生成随机盐值
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt,
            100000,  # 迭代次数
            dklen=32  # 密钥长度
        )
        return f"{salt.hex()}${key.hex()}"

    def _verify_password(self, password, stored_hash):
        """
        验证密码
        
        Args:
            password (str): 用户输入的密码
            stored_hash (str): 存储的密码哈希值
            
        Returns:
            bool: 密码是否匹配
        """
        try:
            if not password or not stored_hash:
                return False
                
            # 检查存储的哈希值格式
            if '$' not in stored_hash:
                return False
                
            salt_hex, key_hex = stored_hash.split('$')
            if not salt_hex or not key_hex:
                return False
                
            try:
                salt = bytes.fromhex(salt_hex)
                key = bytes.fromhex(key_hex)
            except ValueError:
                return False
                
            # 使用相同的参数重新计算哈希值
            new_key = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode(),
                salt,
                100000,  # 迭代次数
                dklen=32  # 密钥长度
            )
            
            return key == new_key
            
        except Exception as e:
            logging.error(f"密码验证失败: {e}")
            return False


class BaseWindow(QWidget):
    """
    基础窗口类
    
    提供登录和注册窗口的通用功能，包括背景设置、样式定义和窗口切换信号。
    所有具体的窗口类都应该继承此类。
    """
    
    # 定义窗口切换信号，用于在登录和注册窗口间切换
    switch_window = pyqtSignal(str)

    def __init__(self):
        """
        初始化基础窗口
        
        设置背景图片和通用样式
        """
        super().__init__()
        
        # 创建背景标签用于显示背景图片
        self.background_label = QLabel(self)
        
        # 设置背景图片
        self._setup_background()
        
        # 设置窗口样式表
        self._setup_style()

    def _setup_background(self):
        """
        设置窗口背景图片
        
        加载背景图片并进行适当的缩放和裁剪以适应窗口大小
        """
        try:
            pixmap = QPixmap("data/static/login_background.png")
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
            print(f"背景图片加载失败: {e}")

    def _setup_style(self):
        """设置窗口样式"""
        self.setStyleSheet("""
            /* 输入框样式 */
            QLineEdit {
                background: rgba(255, 255, 255, 0.1);  /* 半透明白色背景 */
                border: 1px solid #ddd;  /* 浅灰色边框 */
                padding: 10px;  /* 内边距 */
                margin: 5px 0;  /* 外边距 */
                border-radius: 5px;  /* 圆角 */
            }
            /* 按钮样式 */
            QPushButton {
                background: #2c3e50;  /* 深蓝色背景 */
                color: white;  /* 白色文字 */
                padding: 10px 20px;  /* 内边距 */
                border: none;  /* 无边框 */
                border-radius: 5px;  /* 圆角 */
            }
            /* 按钮悬停效果 */
            QPushButton:hover {
                background: #34495e;  /* 悬停时的深灰色 */
            }
            /* 说明文字样式 */
            QLabel#instruction {
                color: #7f8c8d;  /* 灰色文字 */
                margin-top: 20px;  /* 上边距 */
            }
            /* 标题样式 */
            QLabel#tab-title {
                font-size: 20px;  /* 字体大小 */
                font-weight: bold;  /* 粗体 */
                margin-bottom: 20px;  /* 下边距 */
            }
        """)


class LoginWindow(BaseWindow):
    """登录窗口类"""
    
    def __init__(self):
        """初始化登录窗口"""
        super().__init__()
        
        # 初始化属性
        self.username = None
        self.password = None
        self.remember_me = None
        self.login_window = None
        self.stacked_widget = None
        self.login_page = None
        
        # 设置窗口标题和图标
        self.setWindowTitle("原神！启动！！！")
        self.setWindowIcon(QIcon("data/static/app_icon.ico"))
        
        # 设置固定窗口大小
        self.setFixedSize(800, 600)
        
        # 创建堆叠窗口管理器
        self.stacked_widget = QStackedWidget(self)
        self.stacked_widget.setGeometry(0, 0, 800, 600)
        
        # 创建各个窗口
        self.login_page = QWidget()
        self.register_page = RegisterWindow()
        self.reset_page = ResetPasswordWindow()
        
        # 初始化登录页面
        self.init_ui()
        
        # 将各个页面添加到堆叠窗口
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.register_page)
        self.stacked_widget.addWidget(self.reset_page)
        
        # 连接信号
        self.switch_window.connect(self._handle_window_switch)
        self.register_page.switch_window.connect(self._handle_window_switch)
        self.reset_page.switch_window.connect(self._handle_window_switch)
        login_signal.login_success.connect(self._handle_login_signal)  # 连接登录信号
        
        # 加载保存的用户名
        self._load_saved_username()
        
        # 将窗口居中显示
        self.center_window()
        
        # 设置窗口关闭事件处理
        self.closeEvent = self._handle_close_event
        
        # 检查是否需要自动登录
        self._check_auto_login()

    def _check_auto_login(self):
        """检查是否需要自动登录"""
        settings = QSettings("模拟考试系统", "Login")
        saved_username = settings.value("username", "")
        if saved_username:
            # 延迟0.75秒后自动登录
            QTimer.singleShot(750, lambda: self._auto_login(saved_username))

    def _auto_login(self, username):
        """执行自动登录"""
        try:
            # 从本地存储中获取密码
            settings = QSettings("模拟考试系统", "Login")
            password = settings.value(f"password_{username}", "")
            
            if password:
                # 验证用户
                data_utils = DataUtils()
                success, msg = data_utils.verify_user(username, password)
                
                if success:
                    # 延迟导入主窗口
                    from main_window import MainWindow
                    
                    # 创建并显示主界面
                    self.login_window = MainWindow(username=username)
                    self.login_window.show()
                    
                    # 隐藏登录窗口
                    self.hide()
                    
                    # 发送登录成功信号
                    login_signal.login_success.emit(username)
                else:
                    # 如果自动登录失败，清除保存的密码
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
                # 清除自动登录信息
                settings = QSettings("模拟考试系统", "Login")
                settings.remove("username")
                settings.remove(f"password_{self.username.text() if self.username else ''}")
                
                # 重置登录窗口状态
                if hasattr(self, 'username') and self.username:
                    self.username.clear()
                if hasattr(self, 'password') and self.password:
                    self.password.clear()
                if hasattr(self, 'remember_me') and self.remember_me:
                    self.remember_me.setChecked(False)
                
                # 显示登录窗口
                self.show()
                # 确保显示登录页面
                if hasattr(self, 'stacked_widget'):
                    self.stacked_widget.setCurrentWidget(self.login_page)
        except Exception as e:
            logging.error(f"处理登录信号失败: {e}")
            QMessageBox.critical(self, "错误", f"处理登录信号时发生错误：{str(e)}")

    def _handle_close_event(self, event):
        """处理窗口关闭事件"""
        try:
            # 保存用户名设置
            settings = QSettings("模拟考试系统", "Login")
            if self.remember_me and self.remember_me.isChecked():
                settings.setValue("username", self.username.text() if self.username else "")
            else:
                settings.remove("username")
            
            # 清理资源
            if hasattr(self, 'login_window') and self.login_window:
                self.login_window.close()
                self.login_window = None
            
            # 如果是主窗口关闭，询问是否退出系统
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
        # 创建右侧容器（登录表单区域）
        container = QWidget(self.login_page)
        container.setGeometry(400, 0, 400, 600)  # 设置容器位置和大小
        
        # 创建垂直布局
        layout = QVBoxLayout(container)

        # 创建标题标签
        title = QLabel("登录")
        title.setObjectName("tab-title")
        layout.addWidget(title)

        # 创建用户名输入框
        self.username = QLineEdit()
        self.username.setPlaceholderText("请输入用户名")
        
        # 创建密码输入框
        self.password = QLineEdit()
        self.password.setPlaceholderText("请输入密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        # 创建"记住我"复选框
        self.remember_me = QCheckBox("记住我")
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        layout.addWidget(self.remember_me)

        # 创建登录按钮
        login_btn = QPushButton("登录")
        login_btn.clicked.connect(self.handle_login)
        layout.addWidget(login_btn)

        # 创建忘记密码和注册链接（同一行）
        links_layout = QHBoxLayout()
        
        # 注册链接
        register_link = QLabel("<a href='register' style='color: #3498db; text-decoration: none;'>没有账号？去注册</a>")
        register_link.linkActivated.connect(lambda: self.switch_window.emit("register"))
        
        # 忘记密码链接
        forget_link = QLabel("<a href='reset' style='color: #3498db; text-decoration: none;'>忘记密码？</a>")
        forget_link.linkActivated.connect(lambda: self.switch_window.emit("reset"))
        
        links_layout.addWidget(register_link)
        links_layout.addWidget(forget_link)
        layout.addLayout(links_layout)

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

            # 记住我功能
            settings = QSettings("模拟考试系统", "Login")
            if self.remember_me.isChecked():
                # 保存用户名和密码
                settings.setValue("username", username)
                settings.setValue(f"password_{username}", password)
            else:
                # 清除保存的信息
                settings.remove("username")
                settings.remove(f"password_{username}")

            # 验证用户
            data_utils = DataUtils()
            success, msg = data_utils.verify_user(username, password)
            
            if success:
                QMessageBox.information(self, "成功", f"欢迎回来，{username}！")
                
                # 延迟导入主窗口
                from main_window import MainWindow
                
                # 创建并显示主界面
                self.login_window = MainWindow(username=username)
                self.login_window.show()
                
                # 隐藏登录窗口
                self.hide()
                
                # 发送登录成功信号
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
                # 清理主窗口
                if hasattr(self, 'login_window') and self.login_window:
                    self.login_window.close()
                    self.login_window = None
                
                # 重置登录窗口状态，但保留"记住我"的设置
                if self.username:
                    self.username.clear()
                if self.password:
                    self.password.clear()
                if self.remember_me:
                    self.remember_me.setChecked(False)
                
                # 显示登录窗口
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
        
        # 设置窗口标题
        self.setWindowTitle("模拟考试系统 - 注册")
        
        # 初始化UI
        self.init_ui()

    def init_ui(self):
        """初始化注册界面"""
        container = QWidget(self)
        container.setGeometry(400, 0, 400, 600)
        layout = QVBoxLayout(container)

        # 标题
        title = QLabel("注册")
        title.setObjectName("tab-title")
        layout.addWidget(title)

        # 用户名输入框
        self.username = QLineEdit()
        self.username.setPlaceholderText("请输入用户名")
        
        # 密码输入框
        self.password = QLineEdit()
        self.password.setPlaceholderText("请输入密码")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        
        # 确认密码输入框
        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("请确认密码")
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)

        # 显示密码复选框
        self.show_password = QCheckBox("显示密码")
        self.show_password.stateChanged.connect(self._toggle_password_visibility)

        # 注册按钮
        register_btn = QPushButton("注册")
        register_btn.clicked.connect(self.handle_registration)

        # 返回登录链接
        login_link = QLabel("<a href='login' style='color: #3498db; text-decoration: none;'>已有账号？去登录</a>")
        login_link.linkActivated.connect(lambda: self.switch_window.emit("login"))

        # 添加组件到布局
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        layout.addWidget(self.confirm_password)
        layout.addWidget(self.show_password)
        layout.addWidget(register_btn)
        layout.addWidget(login_link)

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

            # 只验证非空
            if not username or not password or not confirm:
                QMessageBox.warning(self, "错误", "用户名和密码不能为空")
                return
                
            if password != confirm:
                QMessageBox.warning(self, "错误", "两次输入的密码不一致")
                return

            # 注册用户
            data_utils = DataUtils()
            success, msg = data_utils.register_user(username, password)
            
            if success:
                QMessageBox.information(self, "成功", "注册成功，请登录")
                # 清空输入框
                self.username.clear()
                self.password.clear()
                self.confirm_password.clear()
                self.show_password.setChecked(False)
                # 返回登录页面
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
        
        # 设置窗口标题
        self.setWindowTitle("模拟考试系统 - 重置密码")
        
        # 初始化UI
        self.init_ui()

    def init_ui(self):
        """初始化重置密码界面"""
        container = QWidget(self)
        container.setGeometry(400, 0, 400, 600)
        layout = QVBoxLayout(container)

        # 标题
        title = QLabel("重置密码")
        title.setObjectName("tab-title")
        layout.addWidget(title)

        # 输入框
        self.username = QLineEdit()
        self.username.setPlaceholderText("请输入用户名")
        
        self.password = QLineEdit()
        self.password.setPlaceholderText("请输入新密码（至少6个字符）")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.confirm_password = QLineEdit()
        self.confirm_password.setPlaceholderText("请确认新密码")
        self.confirm_password.setEchoMode(QLineEdit.EchoMode.Password)

        # 重置按钮
        reset_btn = QPushButton("重置密码")
        reset_btn.clicked.connect(self.handle_reset)

        # 返回登录链接
        login_link = QLabel("<a href='login' style='color: #3498db; text-decoration: none;'>返回登录</a>")
        login_link.linkActivated.connect(lambda: self.switch_window.emit("login"))

        # 添加组件到布局
        layout.addWidget(self.username)
        layout.addWidget(self.password)
        layout.addWidget(self.confirm_password)
        layout.addWidget(reset_btn)
        layout.addWidget(login_link)

    def handle_reset(self):
        """处理密码重置请求"""
        try:
            username = self.username.text().strip()
            password = self.password.text()
            confirm = self.confirm_password.text()

            # 输入验证
            if not all([username, password, confirm]):
                QMessageBox.warning(self, "错误", "所有字段都必须填写")
                return
                
            if password != confirm:
                QMessageBox.warning(self, "错误", "两次输入的密码不一致")
                return

            # 重置密码
            data_utils = DataUtils()
            data = data_utils.read_data()
            hashed_username = data_utils._hash_username(username)
            
            # 查找用户
            user_id = None
            for uid, user_data in data.items():
                if user_data["用户名"] == hashed_username:
                    user_id = uid
                    break
                    
            if user_id is None:
                QMessageBox.warning(self, "错误", "用户不存在")
                return

            # 更新密码
            data[user_id]["密码"] = data_utils._hash_password(password)
            data_utils.write_data(data)
            
            QMessageBox.information(self, "成功", "密码重置成功，请登录")
            # 清空输入框
            self.username.clear()
            self.password.clear()
            self.confirm_password.clear()
            # 返回登录页面
            self.switch_window.emit("login")
            
        except Exception as e:
            logging.error(f"重置密码失败: {e}")
            QMessageBox.critical(self, "错误", f"重置密码过程中发生错误：{str(e)}")


# 程序入口点
if __name__ == '__main__':
    """
    应用程序主入口
    
    创建QApplication实例，显示主窗口，并启动事件循环
    """
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec())