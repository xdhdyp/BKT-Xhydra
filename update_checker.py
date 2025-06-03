import requests
import json
from pathlib import Path
import logging
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal

class UpdateChecker(QObject):
    """版本更新检查器"""
    
    update_available = pyqtSignal(str, str)  # 信号：新版本号, 更新说明
    
    def __init__(self):
        super().__init__()
        self.current_version = "1.1.1"  # 更新为当前版本
        self.github_api_url = "https://api.github.com/repos/xdhdyp/Xdhdyp-BKT/releases/latest"
        self.github_release_url = "https://github.com/xdhdyp/Xdhdyp-BKT/releases/latest"
        
    def check_for_updates(self):
        """检查更新"""
        try:
            # 获取最新发布版本信息
            response = requests.get(self.github_api_url)
            if response.status_code == 200:
                release_info = response.json()
                latest_version = release_info['tag_name']
                
                # 移除版本号前缀（如 'v' 或 'BKT-Xhydra_'）
                latest_version = latest_version.replace('v', '').replace('BKT-Xhydra_', '')
                
                # 比较版本号
                if self._compare_versions(latest_version, self.current_version) > 0:
                    # 发送更新信号
                    self.update_available.emit(
                        latest_version,
                        release_info.get('body', '有新版本可用')
                    )
                    return True
            return False
            
        except Exception as e:
            logging.error(f"检查更新失败: {e}")
            return False
            
    def _compare_versions(self, version1, version2):
        """比较版本号，返回1表示version1更新，-1表示version2更新，0表示相同"""
        try:
            v1_parts = [int(x) for x in version1.split('.')]
            v2_parts = [int(x) for x in version2.split('.')]
            
            for i in range(max(len(v1_parts), len(v2_parts))):
                v1 = v1_parts[i] if i < len(v1_parts) else 0
                v2 = v2_parts[i] if i < len(v2_parts) else 0
                
                if v1 > v2:
                    return 1
                elif v1 < v2:
                    return -1
            return 0
        except ValueError:
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