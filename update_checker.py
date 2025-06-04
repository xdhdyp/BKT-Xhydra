import requests
from pathlib import Path
import logging
from PyQt6.QtWidgets import QMessageBox, QProgressDialog
from PyQt6.QtCore import QObject, pyqtSignal, QThread
import re
import os
import hashlib
import json
import zipfile
import shutil
import sys
import subprocess

class DownloadThread(QThread):
    """下载线程"""
    progress = pyqtSignal(int)
    complete = pyqtSignal()
    error = pyqtSignal(str)
    
    def __init__(self, url, save_path):
        super().__init__()
        self.url = url
        self.save_path = save_path
        
    def run(self):
        try:
            response = requests.get(self.url, stream=True)
            total_size = int(response.headers.get('content-length', 0))
            block_size = 1024
            downloaded = 0
            
            with open(self.save_path, 'wb') as f:
                for data in response.iter_content(block_size):
                    f.write(data)
                    downloaded += len(data)
                    self.progress.emit(int(downloaded * 100 / total_size))
            self.complete.emit()
        except Exception as e:
            self.error.emit(str(e))

class UpdateChecker(QObject):
    """版本更新检查器"""
    
    update_available = pyqtSignal(str, str)  # 信号：新版本号, 更新说明
    download_progress = pyqtSignal(int)  # 信号：下载进度
    download_complete = pyqtSignal()  # 信号：下载完成
    download_error = pyqtSignal(str)  # 信号：下载错误
    update_ready = pyqtSignal(str, str)  # 信号：更新准备就绪（新版本号, 更新说明）
    
    def __init__(self):
        super().__init__()
        self.current_version = self._get_current_version()  # 自动获取当前版本
        self.github_api_url = "https://api.github.com/repos/xdhdyp/Xdhdyp-BKT/releases/latest"
        self.github_release_url = "https://github.com/xdhdyp/Xdhdyp-BKT/releases/latest"
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
        self.download_thread = None
        self.latest_version = None
        self.update_info = None
        self.patch_file = None
        self.setup_file = None
        
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
                    # 保存更新信息
                    self.latest_version = latest_version
                    self.update_info = release_info.get('body', '有新版本可用')
                    # 开始后台下载
                    self._start_background_download(release_info)
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
        
    def _start_background_download(self, release_info):
        """开始后台下载"""
        try:
            assets = release_info.get('assets', [])
            
            # 查找增量更新包和安装程序
            self.patch_file = None
            self.setup_file = None
            for asset in assets:
                if asset['name'].endswith('.patch'):
                    self.patch_file = asset
                elif asset['name'].endswith('.exe'):
                    self.setup_file = asset
                    
            if not self.patch_file and not self.setup_file:
                raise Exception("未找到更新文件")
                
            # 优先下载增量更新包
            if self.patch_file:
                self._download_file(self.patch_file, is_patch=True)
            else:
                # 如果没有增量更新包，直接下载安装程序
                self._download_file(self.setup_file, is_patch=False)
            
        except Exception as e:
            self.download_error.emit(str(e))
            logging.error(f"开始下载失败: {e}")
            
    def _download_file(self, asset, is_patch=True):
        """下载文件"""
        try:
            # 准备下载
            download_url = asset['browser_download_url']
            file_name = asset['name']
            file_path = self.temp_dir / file_name
            
            # 创建并启动下载线程
            self.download_thread = DownloadThread(download_url, file_path)
            self.download_thread.progress.connect(self.download_progress)
            self.download_thread.complete.connect(lambda: self._on_download_complete(file_path, is_patch))
            self.download_thread.error.connect(self._on_download_error)
            self.download_thread.start()
            
        except Exception as e:
            self.download_error.emit(str(e))
            logging.error(f"下载文件失败: {e}")
            
    def _on_download_error(self, error_msg):
        """下载错误处理"""
        if self.patch_file and not self.setup_file:
            # 如果增量更新下载失败，尝试下载完整安装包
            self._download_file(self.setup_file, is_patch=False)
        else:
            self.download_error.emit(error_msg)
            
    def _on_download_complete(self, file_path, is_patch):
        """下载完成处理"""
        try:
            if is_patch:
                # 应用增量更新
                if self._apply_patch(file_path):
                    # 发送更新准备就绪信号
                    self.update_ready.emit(self.latest_version, self.update_info)
                    self.download_complete.emit()
                else:
                    # 如果增量更新失败，尝试下载完整安装包
                    if self.setup_file:
                        self._download_file(self.setup_file, is_patch=False)
                    else:
                        raise Exception("增量更新失败且未找到完整安装包")
            else:
                # 保存安装程序路径
                self.setup_path = file_path
                # 发送更新准备就绪信号
                self.update_ready.emit(self.latest_version, self.update_info)
                self.download_complete.emit()
                
        except Exception as e:
            self.download_error.emit(str(e))
            logging.error(f"应用更新失败: {e}")
            
    def _apply_patch(self, patch_file):
        """应用增量更新"""
        try:
            # 读取补丁文件
            with open(patch_file, 'r', encoding='utf-8') as f:
                patch_data = json.load(f)
                
            # 验证文件完整性
            for file_info in patch_data['files']:
                file_path = Path(file_info['path'])
                if file_path.exists():
                    current_hash = self._calculate_file_hash(file_path)
                    if current_hash != file_info['old_hash']:
                        raise Exception(f"文件 {file_path} 已被修改，无法应用增量更新")
                        
            # 应用更新
            for file_info in patch_data['files']:
                file_path = Path(file_info['path'])
                if file_info['action'] == 'update':
                    # 更新文件
                    with open(file_path, 'wb') as f:
                        f.write(bytes.fromhex(file_info['content']))
                elif file_info['action'] == 'delete':
                    # 删除文件
                    if file_path.exists():
                        file_path.unlink()
                        
            # 清理临时文件
            patch_file.unlink()
            return True
            
        except Exception as e:
            logging.error(f"应用增量更新失败: {e}")
            return False
            
    def _calculate_file_hash(self, file_path):
        """计算文件哈希值"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
        
    def show_update_dialog(self, parent, new_version, update_info):
        """显示更新对话框"""
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle("更新已准备就绪")
        msg.setText(f"新版本 v{new_version} 已下载完成")
        msg.setInformativeText(f"更新说明：\n{update_info}\n\n是否立即安装更新？")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg.exec() == QMessageBox.StandardButton.Yes:
            if hasattr(self, 'setup_path'):
                # 运行安装程序
                subprocess.Popen([str(self.setup_path)])
            # 重启应用
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit() 