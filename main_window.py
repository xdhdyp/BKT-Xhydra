import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QMessageBox, QListWidget, QDialog
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QIcon, QPixmap
import json
from datetime import datetime
from pathlib import Path
import logging
from login_window import DataUtils
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import os

# ----------- 中文支持 -----------
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False
# -------------------------------

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self, username="admin"):
        super().__init__()
        self.username = username
        self._init_state()  # 初始化状态
        self._init_window()
        self._init_ui()
        
        # 初始化答题记录目录
        # self.answer_dir = Path("data/answers")
        # self.answer_dir.mkdir(parents=True, exist_ok=True)
        
        # 加载用户数据
        self._load_user_data()
        
        # 更新UI
        self._update_ui()
        
        # 设置窗口关闭事件处理
        self.closeEvent = self._handle_close_event

    def _init_state(self):
        """初始化状态变量"""
        self.exam_window = None
        self.user_data = None
        self.last_answer_file = None
        self.progress = {
            'total': 740,
            'completed': 0,
            'correct': 0,
            'wrong': 0
        }

    def _load_user_data(self):
        """加载用户数据"""
        try:
            data_utils = DataUtils()
            data = data_utils.read_data()
            hashed_username = data_utils._hash_username(self.username)
            
            # 查找用户
            user_id = None
            for uid, user_data in data.items():
                if user_data["用户名"] == hashed_username:
                    user_id = uid
                    break
                    
            if user_id:
                self.user_data = data[user_id]
                # 确保用户数据包含必要的字段
                if "考试记录" not in self.user_data:
                    self.user_data["考试记录"] = {}
                if "当前考试" not in self.user_data:
                    self.user_data["当前考试"] = {}
                self._update_progress()
            else:
                logging.warning(f"未找到用户数据: {self.username}")
                self.user_data = {
                    "用户名": hashed_username,
                    "考试记录": {},
                    "当前考试": {}
                }
                
        except Exception as e:
            logging.error(f"加载用户数据失败: {e}")
            auto_warning(self, "警告", "加载用户数据失败，将使用默认设置")
            self.user_data = {
                "用户名": self.username,
                "考试记录": {},
                "当前考试": {}
            }

    def _update_progress(self):
        """更新学习进度（基于所有历史记录）"""
        try:
            # 读取题库
            question_file = Path("data/static/单选题.xlsx")
            if not question_file.exists():
                self.progress_label.setText("题库不存在")
                return
            df = pd.read_excel(question_file)
            questions = df.to_dict('records')
            total = len(questions)

            # 合并所有历史答题记录
            history_dir = Path("data/recommendation/history")
            answer_files = list(history_dir.glob(f"answers_{self.username}_*.json"))
            question_stats = {i: {'correct': 0, 'wrong': 0, 'done': 0} for i in range(total)}
            for answer_file in answer_files:
                try:
                    with open(answer_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        q_order = data.get('original_indices', [])
                        u_ans = data.get('answers', {})
                        for idx_str, ans in u_ans.items():
                            idx = int(idx_str)
                            if idx < len(q_order):
                                real_idx = q_order[idx]
                                correct_ans = str(questions[real_idx]['答案']).strip().upper()
                                if str(ans).strip().upper() == correct_ans:
                                    question_stats[real_idx]['correct'] += 1
                                else:
                                    question_stats[real_idx]['wrong'] += 1
                                question_stats[real_idx]['done'] += 1
                except Exception as e:
                    logging.error(f"读取答题文件失败 {answer_file}: {e}")
                    continue

            mastered = sum(1 for stat in question_stats.values() if stat['correct'] >= 5 and stat['wrong'] == 0)
            unmastered = sum(1 for stat in question_stats.values() if stat['done'] > 0 and (stat['correct'] < 5 or stat['wrong'] > 0))
            undone = sum(1 for stat in question_stats.values() if stat['done'] == 0)
            remaining = unmastered + undone

            self.progress.update({
                'total': total,
                'remaining': remaining,
                'unmastered': unmastered,
                'undone': undone,
                'mastered': mastered
            })

            if hasattr(self, 'progress_label'):
                self.progress_label.setText(
                    f"剩余题目数：{remaining}\n未掌握题目数：{unmastered}"
                )

            # 可视化数据
            if hasattr(self, 'progress_pie'):
                self._update_progress_pie(mastered, unmastered, undone)

        except Exception as e:
            logging.error(f"更新进度失败: {e}")
            if hasattr(self, 'progress_label'):
                self.progress_label.setText("剩余题目数：0\n未掌握题目数：0")

    def _update_ui(self):
        """更新UI显示"""
        self._update_progress()
        self._update_recent_exams()
        self._update_charts()
        
        # 检查是否有未完成的考试
        latest_file = self._get_latest_answer_file()
        if latest_file:
            self.continue_btn.setEnabled(True)
            self.continue_btn.setToolTip(f"继续上次未完成的考试\n保存时间：{Path(latest_file).stat().st_mtime}")
        else:
            self.continue_btn.setEnabled(False)
            self.continue_btn.setToolTip("没有未完成的考试")

    def _update_recent_exams(self):
        """更新最近考试记录"""
        try:
            recent_exams = []
            history_dir = Path('data/recommendation/history')
            if not history_dir.exists():
                return
                
            for answer_file in sorted(
                history_dir.glob(f"answers_{self.username}_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )[:5]:  # 只显示最近5次
                try:
                    with open(answer_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        recent_exams.append({
                            'date': datetime.fromisoformat(data['timestamp']).strftime('%Y-%m-%d %H:%M'),
                            'score': data.get('score', 0),
                            'correct': data.get('correct_count', 0),
                            'total': data.get('total_questions', 0)
                        })
                except Exception:
                    continue
                    
            # TODO: 更新最近考试记录显示
            pass
            
        except Exception as e:
            logging.error(f"更新最近考试记录失败: {e}")

    def _update_charts(self):
        """更新图表显示"""
        # TODO: 实现图表更新
        pass

    def _init_window(self):
        """初始化窗口属性"""
        self.setWindowTitle("学习仪表盘")
        self.setWindowIcon(QIcon("data/static/app_icon.ico"))
        
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        # 计算窗口尺寸（屏幕的70%）
        window_width = int(screen_width * 0.7)
        window_height = int(window_width * 9 / 16)  # 保持16:9比例
        
        # 设置窗口大小和位置
        self.setGeometry(
            (screen_width - window_width) // 2,  # x坐标
            (screen_height - window_height) // 2,  # y坐标
            window_width,
            window_height
        )

    def _init_ui(self):
        """初始化用户界面"""
        # 主布局
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # 左侧面板
        left_panel = self._create_left_panel()
        main_layout.addWidget(left_panel)

        # 右侧面板
        right_panel = self._create_right_panel()
        main_layout.addWidget(right_panel)

        # 美化：调整左右比例
        main_layout.setStretch(0, 2)  # 左侧 2
        main_layout.setStretch(1, 3)  # 右侧 3

    def _create_left_panel(self):
        """创建左侧面板"""
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        left_widget.setFixedWidth(self.width() // 3)
        
        # 欢迎信息
        welcome_label = QLabel(f"欢迎回来，{self.username}！")
        welcome_label.setStyleSheet("font-size: 28px; font-weight: bold; margin-bottom: 20px;")
        left_layout.addWidget(welcome_label)
        left_layout.addSpacing(20)
        
        # 进度信息
        self.progress_label = QLabel("剩余题目数：0\n未掌握题目数：0")
        self.progress_label.setStyleSheet("font-size: 22px; margin-bottom: 20px;")
        left_layout.addWidget(self.progress_label)
        left_layout.addSpacing(30)
        
        # 按钮组
        self.continue_btn = QPushButton("继续做题")
        self.continue_btn.setFixedHeight(40)
        self.continue_btn.setStyleSheet("font-size: 18px;")
        self.continue_btn.clicked.connect(self._handle_continue)
        self.continue_btn.setEnabled(False)
        
        # 添加其他按钮
        buttons = [
            ("开始做题", self._handle_start),
            (self.continue_btn, None),
            ("历史记录", self._handle_history),
            ("关于", self._handle_settings),
            ("退出登录", self._handle_logout),
            ("退出系统", self._handle_exit)
        ]
        
        for btn_or_text, handler in buttons:
            if isinstance(btn_or_text, str):
                btn = QPushButton(btn_or_text)
                btn.setFixedHeight(40)
                btn.setStyleSheet("font-size: 18px;")
                btn.clicked.connect(handler)
                left_layout.addWidget(btn)
            else:
                left_layout.addWidget(btn_or_text)
            left_layout.addSpacing(15)
            
        left_layout.addStretch()
        return left_widget

    def _create_right_panel(self):
        """创建右侧面板"""
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        
        # 标题
        title_label = QLabel("学习进度分析")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; margin-bottom: 20px;")
        right_layout.addWidget(title_label)
        
        # 饼图区域（放大，居中）
        self.progress_pie = FigureCanvas(Figure(figsize=(5, 5)))
        self.progress_pie.setMinimumHeight(400)
        self.progress_pie.setMinimumWidth(400)
        right_layout.addWidget(self.progress_pie, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        right_layout.addStretch()
        
        return right_widget

    def _handle_start(self):
        """处理开始做题"""
        try:
            # 检查save目录下是否有未提交文件
            save_dir = Path('data/recommendation/save')
            if save_dir.exists():
                files = sorted(save_dir.glob(f"answers_{self.username}_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
                if files:
                    # 取最新一份，转为提交格式，保存到history
                    latest_file = files[0]
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    data['submitted'] = True
                    
                    # 保存到history
                    os.makedirs('data/recommendation/history', exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"answers_{self.username}_{timestamp}.json"
                    history_file = os.path.join('data', 'recommendation', 'history', filename)
                    with open(history_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    
                    # 删除save目录下所有文件
                    for file in files:
                        try:
                            file.unlink()
                        except Exception as e:
                            logging.error(f"删除临时文件失败: {e}")
                    
                    # 处理答题记录并生成推荐
                    from models.question_processor import QuestionProcessor
                    processor = QuestionProcessor(self.username)
                    processor.process_answer_file(history_file)
            
            # 开始新的答题
            from system import QuestionSystem
            if hasattr(self, 'exam_window') and self.exam_window:
                self.exam_window.close()
                self.exam_window = None
            self.exam_window = QuestionSystem(username=self.username)
            self.exam_window.answer_submitted.connect(self._handle_answer_submitted)
            self.exam_window.show()
            self.hide()
            
        except Exception as e:
            logging.error(f"启动考试系统失败: {e}")
            auto_critical(self, "错误", f"启动考试系统失败：{str(e)}")

    def _handle_continue(self):
        """处理继续做题"""
        try:
            # 获取最新的未完成答题文件
            latest_answer_file = self._get_latest_answer_file()
            if latest_answer_file:
                # 如果已有考试窗口，先关闭
                if hasattr(self, 'exam_window') and self.exam_window:
                    self.exam_window.close()
                    self.exam_window = None
                    
                from system import QuestionSystem
                self.exam_window = QuestionSystem(username=self.username)
                self.exam_window.load_answer_file(latest_answer_file)
                self.exam_window.answer_submitted.connect(self._handle_answer_submitted)
                self.exam_window.show()
                self.hide()
            else:
                auto_information(self, "提示", "没有找到未完成的考试记录")
        except Exception as e:
            logging.error(f"继续考试失败: {e}")
            auto_critical(self, "错误", f"加载上次考试失败：{str(e)}")

    def _handle_history(self):
        """处理历史记录"""
        history_dir = Path('data/recommendation/history')
        if not history_dir.exists():
            auto_information(self, "提示", "没有历史记录")
            return

        files = sorted(history_dir.glob(f"answers_{self.username}_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        if not files:
            auto_information(self, "提示", "没有历史记录")
            return

        # 弹出选择窗口
        dialog = QDialog(self)
        dialog.setWindowTitle("历史记录")
        layout = QVBoxLayout(dialog)
        list_widget = QListWidget(dialog)
        for file in files:
            list_widget.addItem(file.name)
        layout.addWidget(list_widget)
        btn = QPushButton("查看详情", dialog)
        layout.addWidget(btn)

        def show_detail():
            idx = list_widget.currentRow()
            if idx < 0:
                auto_warning(dialog, "提示", "请选择一条记录")
                return
            file_path = str(files[idx])
            dialog.accept()
            self._show_history_detail(file_path)

        btn.clicked.connect(show_detail)
        dialog.exec()

    def _show_history_detail(self, file_path):
        from system import QuestionSystem
        # 只读答题详情窗口（单个文件）
        window = QuestionSystem(username=self.username)
        window.load_answer_file(file_path)
        window.submitted = True  # 强制只读
        window.timer.stop()
        window.show_answer_btn.setEnabled(False)
        for btn in window.option_buttons:
            btn.setEnabled(False)
        window.show()

    def _handle_settings(self):
        """处理设置，弹出带二维码的关于信息大窗口"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel
        from PyQt6.QtGui import QPixmap

        dialog = QDialog(self)
        dialog.setWindowTitle("关于")
        dialog.setFixedSize(750, 700)  # 放大窗口

        main_layout = QVBoxLayout(dialog)

        # 顶部关于信息
        about_label = QLabel(
            "<b>模拟考试系统</b><br>"
            "版本：v1.0.0-alpha<br>"
            "开发者：xdhdyp<br>"
            "更新地址：<a href='https://your-update-url.com'>https://your-update-url.com</a><br>"
            "<br>"
            "本软件为个人学习与模拟考试用途开发。<br>"
            "如需升级请联系开发者，或关注后续版本发布。<br>"
            "如果觉得好用，欢迎扫码支持！"
        )
        about_label.setOpenExternalLinks(True)
        about_label.setTextFormat(Qt.TextFormat.RichText)
        main_layout.addWidget(about_label, alignment=Qt.AlignmentFlag.AlignCenter)

        # 二维码区域
        qr_layout = QHBoxLayout()
        # 微信二维码
        wechat_label = QLabel()
        wechat_pix = QPixmap("data/static/wechat_optimized.png")
        wechat_label.setPixmap(wechat_pix.scaled(810, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        qr_layout.addWidget(wechat_label, alignment=Qt.AlignmentFlag.AlignCenter)
        # 支付宝二维码
        alipay_label = QLabel()
        alipay_pix = QPixmap("data/static/alipay_optimized.png")
        alipay_label.setPixmap(alipay_pix.scaled(810, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        qr_layout.addWidget(alipay_label, alignment=Qt.AlignmentFlag.AlignCenter)

        main_layout.addLayout(qr_layout)

        dialog.exec()

    def _handle_logout(self):
        """处理退出登录"""
        try:
            reply = QMessageBox.question(
                self, "确认退出",
                "确定要退出登录吗？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 清理考试窗口
                if hasattr(self, 'exam_window') and self.exam_window:
                    self.exam_window.close()
                    self.exam_window = None
                
                # 保存当前状态
                self._save_current_state()
                
                # 发送退出登录信号
                from login_window import login_signal
                login_signal.login_success.emit("logout")
                
                # 隐藏主窗口
                self.hide()
                
        except Exception as e:
            logging.error(f"退出登录失败: {e}")
            auto_critical(self, "错误", f"退出登录时发生错误：{str(e)}")

    def _handle_exit(self):
        """处理退出系统"""
        try:
            reply = QMessageBox.question(
                self, "确认退出",
                "确定要退出系统吗？\n这将关闭所有窗口并结束程序。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 清理考试窗口
                if hasattr(self, 'exam_window') and self.exam_window:
                    self.exam_window.close()
                    self.exam_window = None
                
                # 保存当前状态
                self._save_current_state()
                
                # 直接退出应用程序
                QApplication.quit()
                
        except Exception as e:
            logging.error(f"退出系统失败: {e}")
            auto_critical(self, "错误", f"退出系统时发生错误：{str(e)}")

    def _handle_answer_submitted(self, answer_data):
        """处理答题提交"""
        try:
            # 更新用户数据
            if self.user_data:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.user_data['考试记录'][timestamp] = {
                    'score': answer_data.get('score', 0),
                    'correct_count': answer_data.get('correct_count', 0),
                    'total_questions': answer_data.get('total_questions', 0)
                }
                # 保存更新后的用户数据
                data_utils = DataUtils()
                data = data_utils.read_data()
                for uid, user_data in data.items():
                    if user_data["用户名"] == data_utils._hash_username(self.username):
                        data[uid] = self.user_data
                        break
                data_utils.write_data(data)
            
            # 更新UI
            self._update_ui()
            
            # 显示主窗口
            self.show()
            
        except Exception as e:
            logging.error(f"保存答题记录失败: {e}")
            auto_critical(self, "错误", f"保存答题记录失败：{str(e)}")

    def _get_latest_answer_file(self):
        """获取最新的未提交答案文件（只查找 save 目录）"""
        try:
            # 获取data/recommendation/save目录下最新的JSON文件
            save_dir = Path('data/recommendation/save')
            if not save_dir.exists():
                save_dir.mkdir(parents=True, exist_ok=True)
                return None
            
            # 获取该用户的所有临时文件
            json_files = list(save_dir.glob(f"answers_{self.username}_*.json"))
            if not json_files:
                return None
            
            # 按修改时间排序，返回最新的未提交文件
            json_files = sorted(json_files, key=lambda x: x.stat().st_mtime, reverse=True)
            for file in json_files:
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if not data.get('submitted', False):
                            return str(file)
                except Exception as e:
                    logging.error(f"读取文件失败 {file}: {e}")
                    continue
            return None
        except Exception as e:
            logging.error(f"获取最新答案文件失败: {e}")
            return None

    def _handle_close_event(self, event):
        """处理窗口关闭事件"""
        try:
            # 保存当前状态
            self._save_current_state()
            
            # 清理资源
            if hasattr(self, 'exam_window') and self.exam_window:
                self.exam_window.close()
                self.exam_window = None
                
            # 接受关闭事件
            event.accept()
            
        except Exception as e:
            logging.error(f"关闭窗口时发生错误: {e}")
            event.accept()

    def _save_current_state(self):
        """保存当前状态"""
        try:
            settings = QSettings("模拟考试系统", "MainWindow")
            settings.setValue("window_geometry", self.saveGeometry())
            settings.setValue("window_state", self.saveState())
        except Exception as e:
            logging.error(f"保存窗口状态失败: {e}")

    def _load_saved_state(self):
        """加载保存的状态"""
        try:
            settings = QSettings("模拟考试系统", "MainWindow")
            geometry = settings.value("window_geometry")
            state = settings.value("window_state")
            
            if geometry:
                self.restoreGeometry(geometry)
            if state:
                self.restoreState(state)
        except Exception as e:
            logging.error(f"加载窗口状态失败: {e}")

    def _update_progress_pie(self, mastered, unmastered, undone):
        ax = self.progress_pie.figure.subplots()
        ax.clear()
        labels = ['已掌握', '未掌握', '未做']
        sizes = [mastered, unmastered, undone]
        colors = ['#4CAF50', '#FF9800', '#BDBDBD']

        # 避免全为0时matplotlib报错
        if sum(sizes) == 0:
            sizes = [1, 0, 0]
            colors = ['#BDBDBD', '#FFFFFF', '#FFFFFF']

        def autopct_format(pct):
            return ('%1.1f%%' % pct) if pct > 0 else ''

        wedges, texts, autotexts = ax.pie(
            sizes, labels=None, autopct=autopct_format, colors=colors, startangle=90,
            textprops={'fontsize': 18, 'fontweight': 'bold'},
            pctdistance=0.7
        )
        for autotext in autotexts:
            autotext.set_fontsize(20)
            autotext.set_fontweight('bold')
        # 图例放在饼图外部右侧中间
        ax.legend(wedges, ['已掌握', '未掌握', '未做'],
                  title="图例", loc='upper right', bbox_to_anchor=(1.125, 1.125), fontsize=10, title_fontsize=10)
        ax.axis('equal')
        self.progress_pie.draw()

def auto_information(parent, title, text, timeout=1500):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.NoButton)
    QTimer.singleShot(timeout, box.accept)
    box.exec()

def auto_warning(parent, title, text, timeout=1500):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.NoButton)
    QTimer.singleShot(timeout, box.accept)
    box.exec()

def auto_critical(parent, title, text, timeout=1500):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(title)
    box.setText(text)
    box.setStandardButtons(QMessageBox.StandardButton.NoButton)
    QTimer.singleShot(timeout, box.accept)
    box.exec()

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main() 