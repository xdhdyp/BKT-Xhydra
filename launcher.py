import sys
import logging
import traceback
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from login_window import LoginWindow

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
        app.setApplicationName("原神！启动！！！")
        app.setApplicationVersion("v1.0.0-alpha")
        app.setOrganizationName("原神！启动！！！")
        app.setOrganizationDomain("原神！启动！！！")
        
        # 设置应用程序样式
        app.setStyle('Fusion')
        
        # 设置应用程序图标
        app_icon = QIcon("data/static/app_icon.ico")
        if not app_icon.isNull():
            app.setWindowIcon(app_icon)
        
        # 设置高DPI支持
        # 在 PyQt6 中，这些属性已经被移除，因为高 DPI 支持现在是默认启用的
        # 如果需要禁用高 DPI 缩放，可以使用环境变量：
        # os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
        
        return app
    except Exception as e:
        logger.error(f"应用程序初始化失败: {str(e)}")
        logger.error(traceback.format_exc())
        raise

# def cleanup_application():
#     """清理应用程序资源"""
#     try:
#         # 清理临时文件
#         temp_dir = Path("data/answers")
#         if temp_dir.exists():
#             for temp_file in temp_dir.glob("temp_answer_*.json"):
#                 try:
#                     temp_file.unlink()
#                 except Exception as e:
#                     logger.warning(f"清理临时文件失败 {temp_file}: {e}")
#     except Exception as e:
#         logger.error(f"清理应用程序资源失败: {e}")

def main():
    """主函数：创建并显示应用程序窗口"""
    try:
        # 设置应用程序
        app = setup_application()
        
        # 创建并显示登录窗口
        window = LoginWindow()
        window.show()
        
        # # 注册清理函数
        # app.aboutToQuit.connect(cleanup_application)
        
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