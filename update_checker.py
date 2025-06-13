import requests
import json
from pathlib import Path
import logging
from PyQt6.QtWidgets import QMessageBox, QCheckBox, QPushButton
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
import re
import datetime


class UpdateChecker(QObject):
    """版本更新检查器"""

    update_available = pyqtSignal(str, str)  # 信号：新版本号, 更新说明

    def __init__(self):
        super().__init__()
        self.current_version = self._get_current_version()  # 自动获取当前版本
        self.github_api_url = "https://api.github.com/repos/xdhdyp/Xdhdyp-BKT/releases/latest"
        self.github_release_url = "https://github.com/xdhdyp/Xdhdyp-BKT/releases/latest"
        self.config_file = Path("data/config/update_config.json")
        self.ignored_versions = self._load_ignored_versions()

    def _load_ignored_versions(self):
        """加载已忽略的版本列表"""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "ignored_versions" in data:
                        return data["ignored_versions"]
                    return []
            return []
        except Exception as e:
            logging.error(f"加载忽略版本配置失败: {e}")
            return []

    def _save_ignored_versions(self):
        """保存已忽略的版本列表"""
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            # 确保ignored_versions是列表类型
            if not isinstance(self.ignored_versions, list):
                self.ignored_versions = []
                logging.warning("ignored_versions不是列表类型，已重置为空列表")

            data = {
                "ignored_versions": self.ignored_versions,
                "last_update": str(datetime.datetime.now())
            }
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logging.info(f"已保存忽略版本配置到: {self.config_file}")
        except Exception as e:
            logging.error(f"保存忽略版本配置失败: {e}")

    def _get_current_version(self):
        """获取当前程序版本号"""
        try:
            version_file = Path("data/static/version.txt")
            if version_file.exists():
                with open(version_file, "r") as f:
                    version = f.read().strip()
                    if version:  # 确保版本号不为空
                        return version
            logging.error("version.txt 文件不存在或为空")
            return None
        except Exception as e:
            logging.error(f"获取当前版本失败: {e}")
            return None

    def check_for_updates(self):
        """检查更新"""
        try:
            # 确保有当前版本号
            if not self.current_version:
                logging.error("无法获取当前版本号，跳过更新检查")
                return False

            # 获取最新发布版本信息
            headers = {
                "User-Agent": "BKT-Simulation-Exam-System"  # 添加User-Agent头
            }
            # 添加超时参数，避免网络请求卡住
            response = requests.get(self.github_api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                release_info = response.json()
                latest_version = release_info['tag_name']

                # 兼容多种标签格式，提取版本号
                # 1. 先尝试正则提取 x.x.x
                match = re.search(r'(\d+\.\d+\.\d+)', latest_version)
                if match:
                    latest_version = match.group(1)
                else:
                    # 2. 如果没提取到，再尝试去除常见前缀
                    for prefix in ['v', 'BKT-Xhydra_', 'Xdhdyp-BKT_', 'Xdhdyp-BKT']:
                        if latest_version.startswith(prefix):
                            latest_version = latest_version.replace(prefix, '')
                    # 3. 再次尝试正则提取
                    match2 = re.search(r'(\d+\.\d+\.\d+)', latest_version)
                    if match2:
                        latest_version = match2.group(1)
                    else:
                        # 4. 最后尝试从发布说明body中提取
                        body = release_info.get('body', '')
                        match3 = re.search(r'(\d+\.\d+\.\d+)', body)
                        if match3:
                            latest_version = match3.group(1)
                        else:
                            logging.warning(f"无法从标签或发布说明中提取版本号: {release_info['tag_name']}")
                            return False

                # 验证提取的版本号格式
                if not re.match(r'^\d+\.\d+\.\d+$', latest_version):
                    logging.warning(f"提取的版本号格式不正确: {latest_version}")
                    return False

                # 检查是否已忽略此版本
                if latest_version in self.ignored_versions:
                    logging.info(f"版本 {latest_version} 已被用户忽略")
                    return False

                # 比较版本号
                if self._compare_versions(latest_version, self.current_version) > 0:
                    # 发送更新信号
                    self.update_available.emit(
                        latest_version,
                        release_info.get('body', '有新版本可用')
                    )
                    return True
                elif self._compare_versions(latest_version, self.current_version) < 0:
                    logging.info(f"当前版本 {self.current_version} 比 GitHub 版本 {latest_version} 更新")
                    return False
            return False

        except Exception as e:
            logging.error(f"检查更新失败: {e}")
            return False

    def _compare_versions(self, version1, version2):
        """比较版本号，返回1表示version1更新，-1表示version2更新，0表示相同"""
        try:
            # 确保版本号格式正确
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]

            # 补齐版本号长度
            max_length = max(len(v1_parts), len(v2_parts))
            v1_parts.extend([0] * (max_length - len(v1_parts)))
            v2_parts.extend([0] * (max_length - len(v2_parts)))

            # 逐位比较
            for v1, v2 in zip(v1_parts, v2_parts):
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1
            return 0
        except ValueError as e:
            logging.error(f"版本号格式错误: {version1} 或 {version2}")
            return 0

    def show_update_dialog(self, parent, new_version, update_info):
        """显示更新对话框"""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("发现新版本")
        msg.setText(f"发现新版本 v{new_version}")
        msg.setInformativeText(f"更新说明：\n{update_info}\n\n是否前往下载？")

        # 创建QCheckBox实例并将其传递给setCheckBox
        checkbox = QCheckBox("不再提醒此版本")
        msg.setCheckBox(checkbox)

        # 设置自定义按钮
        download_button = QPushButton("前往下载")
        remind_later_button = QPushButton("稍后提醒")

        msg.addButton(download_button, QMessageBox.ButtonRole.AcceptRole)
        msg.addButton(remind_later_button, QMessageBox.ButtonRole.RejectRole)

        msg.setDefaultButton(download_button)

        # 显示对话框并获取用户选择
        msg.exec()

        # 使用clickedButton()方法获取实际点击的按钮
        clicked_button = msg.clickedButton()

        if clicked_button == download_button:
            import webbrowser
            webbrowser.open(self.github_release_url)
        elif clicked_button == remind_later_button:
            if checkbox.isChecked():
                # 如果用户选择不再提醒，将此版本添加到忽略列表
                if new_version not in self.ignored_versions:
                    self.ignored_versions.append(new_version)
                    self._save_ignored_versions()
                    logging.info(f"已将版本 {new_version} 添加到忽略列表")


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from PyQt6.QtCore import QTimer

    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # 创建测试用的版本文件
    version_dir = Path("data/static")
    version_dir.mkdir(parents=True, exist_ok=True)
    with open(version_dir / "version.txt", "w") as f:
        f.write("1.0.0")  # 设置一个测试用的当前版本

    # 创建Qt应用
    app = QApplication(sys.argv)

    # 创建一个主窗口（这是必需的）
    main_window = QMainWindow()
    main_window.setWindowTitle("更新检查器测试")
    main_window.show()

    # 创建更新检查器实例
    checker = UpdateChecker()


    # 连接信号
    def on_update_available(new_version, update_info):
        print(f"发现新版本: {new_version}")
        print(f"更新说明: {update_info}")
        checker.show_update_dialog(main_window, new_version, update_info)


    checker.update_available.connect(on_update_available)

    # 使用定时器延迟执行更新检查，确保窗口已经显示
    QTimer.singleShot(1000, lambda: checker.check_for_updates())

    # 运行应用
    sys.exit(app.exec())
