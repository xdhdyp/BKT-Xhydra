import sys
import logging
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer

# 添加库路径
if getattr(sys, 'frozen', False):
    # 如果是打包后的程序
    lib_path = Path(sys._MEIPASS) / 'lib'
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log', encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_version():
    """只从 data/static/version.txt 读取版本号，读取失败返回空字符串"""
    try:
        version_file = Path("data/static/version.txt")
        if version_file.exists():
            with open(version_file, "r") as f:
                version = f.read().strip()
                if version:
                    return version
        logging.error("version.txt 文件不存在或内容为空")
        return ""
    except Exception as e:
        logging.error(f"读取版本号失败: {e}")
        return ""

def exception_hook(exctype, value, tb):
    """全局异常处理钩子"""
    error_msg = ''.join(traceback.format_exception(exctype, value, tb))
    logger.critical(f"未捕获的异常:\n{error_msg}")
    
    # 显示错误对话框
    try:
        QMessageBox.critical(None, "程序错误",
            f"程序发生错误，详细信息已记录到日志文件。\n\n"
            f"错误类型: {exctype.__name__}\n"
            f"错误信息: {str(value)}")
    except:
        pass
    
    # 调用默认的异常处理
    sys.__excepthook__(exctype, value, tb)

def setup_application():
    """设置应用程序环境"""
    try:
        # 设置异常钩子
        sys.excepthook = exception_hook
        
        # 创建必要的目录
        for dir_path in ["data/static"]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        
        # 设置应用程序信息
        app = QApplication(sys.argv)
        app.setApplicationName("BKT模拟考试系统")
        app.setApplicationVersion(get_version())
        app.setOrganizationName("xdhdyp")
        app.setOrganizationDomain("github.com/xdhdyp")
        
        # 设置应用程序样式
        app.setStyle('Fusion')
        
        # 设置应用程序图标
        app_icon = QIcon("data/static/app_icon.ico")
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)
        
        return app
    except Exception as e:
        logger.error(f"应用程序初始化失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def load_login_window():
    """延迟加载登录窗口"""
    try:
        from login_window import LoginWindow
        window = LoginWindow()
        window.show()
        return window
    except Exception as e:
        logger.error(f"加载登录窗口失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def main():
    """主函数：创建并显示应用程序窗口"""
    try:
        # 设置应用程序
        app = setup_application()
        
        # 使用QTimer延迟加载登录窗口，提高启动速度
        QTimer.singleShot(100, load_login_window)
        
        # 执行应用程序的主循环
        exit_code = app.exec()
        
        # 正常退出
        logger.info(f"应用程序正常退出，退出代码: {exit_code}")
        return exit_code
        
    except Exception as e:
        logger.critical(f"应用程序运行失败: {str(e)}")
        logger.critical(traceback.format_exc())
        return 1

if __name__ == '__main__':
    sys.exit(main())