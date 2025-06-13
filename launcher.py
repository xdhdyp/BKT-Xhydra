import sys
import logging
import traceback
from pathlib import Path

# import logger  # 注释掉这行，因为后面会重新定义logger
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QTimer
import os

# PyTorch配置预处理 - 在导入torch之前处理
try:
    # 设置环境变量来禁用某些PyTorch功能
    os.environ['TORCH_DISABLE_GPU'] = '0'  # 允许GPU
    os.environ['CUDA_VISIBLE_DEVICES'] = '0'  # 使用第一个GPU
    
    import torch
    # 进一步配置PyTorch
    torch_config_modules = []
    
    # 检测并配置GPU
    if torch.cuda.is_available():
        # 获取可用的GPU数量
        gpu_count = torch.cuda.device_count()
        # logger.info(f"检测到 {gpu_count} 个GPU设备")  # 注释掉，因为logger还没定义
        
        # 设置默认设备为第一个可用的GPU
        torch.cuda.set_device(0)
        # logger.info(f"使用GPU: {torch.cuda.get_device_name(0)}")  # 注释掉，因为logger还没定义
        
        # 设置CUDA相关参数
        torch.backends.cudnn.benchmark = True  # 启用cuDNN自动调优
        torch.backends.cudnn.deterministic = False  # 关闭确定性模式以提高性能
    else:
        # logger.info("未检测到GPU，使用CPU模式")  # 注释掉，因为logger还没定义
        # CPU模式下的优化
        torch.set_num_threads(4)  # 设置CPU线程数
        torch.set_num_interop_threads(4)  # 设置线程间操作数
except ImportError:
    # logger.warning("PyTorch导入失败，将使用CPU模式")  # 注释掉，因为logger还没定义
    pass

# 添加库路径
if getattr(sys, 'frozen', False):
    # 如果是打包后的程序
    lib_path = Path(sys._MEIPASS) / 'lib'
    if lib_path.exists():
        sys.path.insert(0, str(lib_path))

# 配置日志
def setup_logging():
    """配置日志系统 - 只在有错误时才写入文件"""
    # 创建自定义日志处理器
    class ErrorFileHandler(logging.FileHandler):
        """只在有错误时才写入文件的处理器"""
        def __init__(self, filename, mode='a', encoding=None, delay=False):
            super().__init__(filename, mode, encoding, delay)
            self.has_error = False
            self.filename = filename  # 保存文件名
            
        def emit(self, record):
            if record.levelno >= logging.ERROR:
                self.has_error = True
                super().emit(record)
                
        def close(self):
            super().close()  # 先关闭文件
            if not self.has_error:
                # 如果没有错误，删除日志文件
                try:
                    if os.path.exists(self.filename):
                        os.remove(self.filename)
                except:
                    pass
    
    # 配置日志
    handlers = [
        ErrorFileHandler('app.log', encoding='utf-8', mode='a'),
        logging.StreamHandler()  # 控制台输出
    ]
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

# 在logger定义后添加GPU检测日志
try:
    import torch
    if torch.cuda.is_available():
        gpu_count = torch.cuda.device_count()
        logger.info(f"检测到 {gpu_count} 个GPU设备")
        logger.info(f"使用GPU: {torch.cuda.get_device_name(0)}")
    else:
        logger.info("未检测到GPU，使用CPU模式")
except:
    logger.warning("PyTorch导入失败，将使用CPU模式")

def get_version():
    """只从 data/static/version.txt 读取版本号，读取失败返回空字符串"""
    try:
        version_file = Path("data/static/version.txt")
        if version_file.exists():
            with open(version_file, "r") as f:
                version = f.read().strip()
                if version:
                    return version
        logger.error("version.txt 文件不存在或内容为空")  # 修复：使用logger对象
        return ""
    except Exception as e:
        logger.error(f"读取版本号失败: {e}")  # 修复：使用logger对象
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
    except Exception as e:  # 修复：明确捕获异常类型
        logger.warning(f"无法显示错误对话框: {e}")

    # 调用默认的异常处理
    sys.__excepthook__(exctype, value, tb)


def setup_application():
    """设置应用程序环境"""
    try:
        # 设置异常钩子
        sys.excepthook = exception_hook

        # 创建必要的目录 (修复：添加更多需要的目录)
        required_dirs = [
            "data/static",
            "data/user",
            "data/questions",
            "data/recommendation/history",
            "data/recommendation/save"
        ]
        for dir_path in required_dirs:
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
        else:
            logger.warning("无法加载应用程序图标")  # 修复：添加图标加载失败的提示

        return app
    except Exception as e:
        logger.error(f"应用程序初始化失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def load_login_window():
    """延迟加载登录窗口"""
    try:
        # 注意：延迟导入是为了提高启动速度
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
