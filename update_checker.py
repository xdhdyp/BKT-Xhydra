import requests
import json
from pathlib import Path
import logging
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal
import re

class UpdateChecker(QObject):
    """版本更新检查器"""
    
    update_available = pyqtSignal(str, str)  # 信号：新版本号, 更新说明
    
    def __init__(self):
        super().__init__()
        self.current_version = self._get_current_version()  # 自动获取当前版本
        self.github_api_url = "https://api.github.com/repos/xdhdyp/Xdhdyp-BKT/releases/latest"
        self.github_release_url = "https://github.com/xdhdyp/Xdhdyp-BKT/releases/latest"
        
    def _get_current_version(self):
        """获取当前程序版本号"""
        try:
            version_file = Path("version.txt")
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
            response = requests.get(self.github_api_url)
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
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            import webbrowser
            webbrowser.open(self.github_release_url) 