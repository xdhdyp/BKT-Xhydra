"""
主窗口模块
提供学习仪表盘、考试记录查看、进度分析等功能
"""

import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QMessageBox, QListWidget, QDialog, QScrollArea,
    QGridLayout, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QSettings, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QPixmap
import json
from datetime import datetime
import logging
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from login_window import DataUtils
from update_checker import UpdateChecker
import webbrowser



# ----------- 中文支持 -----------
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS']
matplotlib.rcParams['axes.unicode_minus'] = False
# -------------------------------

# 全局路径定义
DATA_PATH = Path("data")
RECOMMENDATION_PATH = DATA_PATH / "recommendation"
HISTORY_PATH = RECOMMENDATION_PATH / "history"
SAVE_PATH = RECOMMENDATION_PATH / "save"
STATIC_PATH = DATA_PATH / "static"
QUESTION_FILE = STATIC_PATH / "单选题.xlsx"
VERSION_FILE = STATIC_PATH / "version.txt"

# 图标路径
ICON_GITHUB = STATIC_PATH / "github.png"
ICON_WECHAT = STATIC_PATH / "wechat_optimized.png"
ICON_ALIPAY = STATIC_PATH / "alipay_optimized.png"


class MainWindow(QMainWindow):
    """主窗口类，提供学习进度分析和考试管理功能"""

    def __init__(self, username="admin"):
        super().__init__()
        self.username = username
        self._init_state()
        self._init_window()
        self._init_ui()
        self._load_user_data()
        self._update_progress_labels()
        self.closeEvent = self._handle_close_event
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self._handle_update_available)
        QTimer.singleShot(1000, self._check_for_updates)

    def _init_state(self):
        """初始化状态变量"""
        self.exam_window = None
        self.user_data = None
        self.last_answer_file = None
        self.progress = {
            'total': 0,
            'done': 0,
            'undone': 0,
            'mastered': 0,
            'unmastered': 0
        }

    def _load_user_data(self):
        """加载用户数据"""
        try:
            data_utils = DataUtils()
            data = data_utils.read_data()
            hashed_username = data_utils._hash_username(self.username)

            user_id = None
            for uid, user_data in data.items():
                if user_data["用户名"] == hashed_username:
                    user_id = uid
                    break

            if user_id:
                self.user_data = data[user_id]
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
            self.user_data = {
                "用户名": hashed_username,
                "考试记录": {},
                "当前考试": {}
            }
        self._update_progress_labels()

    def _update_progress(self):
        """更新学习进度（基于所有历史记录）"""
        try:
            if not QUESTION_FILE.exists():
                return

            df = pd.read_excel(QUESTION_FILE)
            questions = df.to_dict('records')
            total = len(questions)
            all_indices = set(range(1, total + 1))

            history_files = sorted(
                HISTORY_PATH.glob(f"answers_{self.username}_*.json"),
                key=lambda x: x.stat().st_mtime,
                reverse=True
            )

            done_indices = set()
            answer_history = {}

            for answer_file in history_files:
                try:
                    with open(answer_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        q_order = data.get('original_indices', [])
                        user_answers = data.get('user_answers', {})
                        correct_answers = data.get('correct_answers', {})

                        for idx in q_order:
                            q_id = str(idx + 1)
                            if q_id not in answer_history:
                                answer_history[q_id] = []

                            user_ans = user_answers.get(str(idx), '')
                            correct_ans = correct_answers.get(str(idx), '')
                            is_correct = user_ans.strip().upper() == correct_ans.strip().upper()

                            answer_history[q_id].append({
                                'answer': user_ans,
                                'is_correct': is_correct,
                                'timestamp': data.get('timestamp', datetime.now().isoformat())
                            })
                            done_indices.add(idx + 1)
                except Exception as e:
                    logging.error(f"读取答题文件失败 {answer_file}: {e}")
                    continue

            from models.bkt_model import BKTModel
            bkt_model = BKTModel()
            mastery = bkt_model.calculate_mastery(answer_history)
            
            # 使用BKT模型判断已掌握题目
            mastered_indices = bkt_model.get_mastered_questions(mastery)

            unmastered_indices = done_indices - mastered_indices
            undone_indices = all_indices - done_indices

            self.done_question_indices = done_indices
            self.unmastered_indices = unmastered_indices
            self.all_question_indices = all_indices

            self.progress.update({
                'total': total,
                'done': len(done_indices),
                'undone': len(undone_indices),
                'mastered': len(mastered_indices),
                'unmastered': len(unmastered_indices)
            })

            if hasattr(self, 'progress_pie'):
                self._update_progress_pie(
                    self.progress['mastered'],
                    self.progress['unmastered'],
                    self.progress['undone']
                )
        except Exception as e:
            logging.error(f"更新进度失败: {e}")

        self._update_progress_labels()

    def _init_window(self):
        """初始化窗口属性"""
        self.setWindowTitle("学习仪表盘")
        self.setWindowIcon(QIcon(str(STATIC_PATH / "app_icon.ico")))

        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()

        window_width = int(screen_width * 0.7)
        window_height = int(window_width * 9 / 16)

        self.setGeometry(
            (screen_width - window_width) // 2,
            (screen_height - window_height) // 2,
            window_width,
            window_height
        )

    def _init_ui(self):
        """初始化用户界面"""
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()

        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)

        main_layout.setStretch(0, 2)
        main_layout.setStretch(1, 3)

    def _create_left_panel(self):
        """创建左侧面板"""
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        left_widget.setFixedWidth(self.width() // 3)

        welcome_label = QLabel(f"欢迎回来，{self.username}！")
        welcome_label.setStyleSheet("font-size: 28px; font-weight: bold; margin-bottom: 20px;")
        left_layout.addWidget(welcome_label)
        left_layout.addSpacing(20)

        self.total_label = QLabel()
        self.done_label = QLabel()
        self.undone_label = QLabel()
        self.mastered_label = QLabel()
        self.unmastered_label = QLabel()

        for label in [self.total_label, self.done_label, self.undone_label,
                      self.mastered_label, self.unmastered_label]:
            label.setStyleSheet("font-size: 22px; color: #000; margin-bottom: 6px; font-weight: bold;")

        left_layout.addWidget(self.total_label)

        for label, btn_func in [
            (self.done_label, self._show_done_indices),
            (self.undone_label, self._show_undone_indices),
            (self.mastered_label, self._show_mastered_indices),
            (self.unmastered_label, self._show_unmastered_indices),
        ]:
            h = QHBoxLayout()
            h.addWidget(label)
            btn = QPushButton("🔍")
            btn.setFixedWidth(30)
            btn.setStyleSheet("padding:0;")
            btn.clicked.connect(btn_func)
            h.addWidget(btn)
            h.addStretch()
            left_layout.addLayout(h)

        left_layout.addSpacing(30)

        self.continue_btn = QPushButton("继续做题")
        self.continue_btn.setFixedHeight(40)
        self.continue_btn.setStyleSheet("font-size: 18px;")
        self.continue_btn.clicked.connect(self._handle_continue)
        self.continue_btn.setEnabled(False)

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
        self._update_progress_labels()
        return left_widget

    def _create_right_panel(self):
        """创建右侧面板"""
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        title_label = QLabel("学习进度分析")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; margin-bottom: 20px;")
        right_layout.addWidget(title_label)

        self.progress_pie = FigureCanvas(Figure(figsize=(5, 5)))
        self.progress_pie.setMinimumHeight(400)
        self.progress_pie.setMinimumWidth(400)
        right_layout.addWidget(self.progress_pie, alignment=Qt.AlignmentFlag.AlignHCenter)
        right_layout.addStretch()
        return right_widget

    def _handle_start(self):
        """处理开始做题"""
        try:
            save_dir = SAVE_PATH
            if save_dir.exists():
                files = sorted(save_dir.glob(f"answers_{self.username}_*.json"),
                               key=lambda x: x.stat().st_mtime, reverse=True)
                if files:
                    latest_file = files[0]
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    data['submitted'] = True

                    history_dir = HISTORY_PATH
                    history_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    history_file = history_dir / f"answers_{self.username}_{timestamp}.json"

                    with open(history_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)

                    for file in files:
                        try:
                            file.unlink()
                        except Exception as e:
                            logging.error(f"删除临时文件失败: {e}")

                    from models.question_processor import QuestionProcessor
                    processor = QuestionProcessor(self.username)
                    processor.process_answer_file(str(history_file))

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

    def _handle_continue(self):
        """处理继续做题"""
        try:
            latest_answer_file = self._get_latest_answer_file()
            if latest_answer_file:
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

    def _handle_history(self):
        """处理历史记录"""
        history_dir = HISTORY_PATH
        if not history_dir.exists():
            auto_information(self, "提示", "没有历史记录")
            return

        files = sorted(history_dir.glob(f"answers_{self.username}_*.json"),
                       key=lambda x: x.stat().st_mtime, reverse=True)
        if not files:
            auto_information(self, "提示", "没有历史记录")
            return

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
        window = QuestionSystem(username=self.username)
        window.load_answer_file(file_path)
        window.submitted = True
        window.timer.stop()
        window.show_answer_btn.setEnabled(False)
        for btn in window.option_buttons:
            btn.setEnabled(False)
        window.show()

    def _handle_settings(self):
        """处理关于信息显示"""
        dialog = QDialog(self)
        dialog.setWindowTitle("关于")
        dialog.setFixedSize(750, 700)
        main_layout = QVBoxLayout(dialog)

        about_label = QLabel(
            "<b>模拟考试系统</b><br>"
            f"版本：v{self._get_version()}<br>"
            "开发者：xdhdyp<br>"
            "更新地址：<a href='https://github.com/xdhdyp/Xdhdyp-BKT'>https://github.com/xdhdyp/Xdhdyp-BKT</a><br>"
            "<br>"
            "本软件为个人学习与模拟考试用途开发。<br>"
            "如需升级请联系开发者，或关注后续版本发布。<br>"
            "如果觉得好用，欢迎扫码支持！"
        )
        about_label.setOpenExternalLinks(True)
        about_label.setTextFormat(Qt.TextFormat.RichText)
        main_layout.addWidget(about_label, alignment=Qt.AlignmentFlag.AlignCenter)

        github_btn_layout = QHBoxLayout()
        github_btn = QPushButton("  GitHub")
        github_btn.setIcon(QIcon(str(ICON_GITHUB)))
        github_btn.setStyleSheet("""
            QPushButton {
                background-color: #24292f;
                color: white;
                border-radius: 8px;
                padding: 8px 20px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #444c56;
            }
        """)
        github_btn.clicked.connect(lambda: webbrowser.open("https://github.com/xdhdyp/Xdhdyp-BKT"))
        github_btn_layout.addWidget(github_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addLayout(github_btn_layout)

        qr_layout = QHBoxLayout()
        wechat_label = QLabel()
        wechat_pix = QPixmap(str(ICON_WECHAT))
        wechat_label.setPixmap(
            wechat_pix.scaled(810, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        qr_layout.addWidget(wechat_label, alignment=Qt.AlignmentFlag.AlignCenter)

        alipay_label = QLabel()
        alipay_pix = QPixmap(str(ICON_ALIPAY))
        alipay_label.setPixmap(
            alipay_pix.scaled(810, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
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
                if hasattr(self, 'exam_window') and self.exam_window:
                    self.exam_window.close()
                    self.exam_window = None
                self._save_current_state()
                from login_window import login_signal
                login_signal.login_success.emit("logout")
                self.hide()
        except Exception as e:
            logging.error(f"退出登录失败: {e}")

    def _handle_exit(self):
        """处理退出系统"""
        try:
            reply = QMessageBox.question(
                self, "确认退出",
                "确定要退出系统吗？\n这将关闭所有窗口并结束程序。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                if hasattr(self, 'exam_window') and self.exam_window:
                    self.exam_window.close()
                    self.exam_window = None
                self._save_current_state()
                QApplication.quit()
        except Exception as e:
            logging.error(f"退出系统失败: {e}")

    def _handle_answer_submitted(self, answer_data):
        """处理答题提交"""
        try:
            if self.user_data:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.user_data['考试记录'][timestamp] = {
                    'score': answer_data.get('score', 0),
                    'correct_count': answer_data.get('correct_count', 0),
                    'total_questions': answer_data.get('total_questions', 0)
                }

                data_utils = DataUtils()
                data = data_utils.read_data()
                for uid, user_data in data.items():
                    if user_data["用户名"] == data_utils._hash_username(self.username):
                        data[uid] = self.user_data
                        break
                data_utils.write_data(data)

            history_dir = HISTORY_PATH
            history_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            history_file = history_dir / f"answers_{self.username}_{timestamp}.json"

            answer_data['timestamp'] = datetime.now().isoformat()

            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(answer_data, f, ensure_ascii=False, indent=2)

            from models.question_processor import QuestionProcessor
            processor = QuestionProcessor(self.username)
            processor.process_answer_file(str(history_file))

            self._update_progress()
            self.show()
        except Exception as e:
            logging.error(f"保存答题记录失败: {e}")

    def _get_latest_answer_file(self):
        """获取最新的未提交答案文件"""
        try:
            save_dir = SAVE_PATH
            if not save_dir.exists():
                save_dir.mkdir(parents=True, exist_ok=True)
                return None

            json_files = list(save_dir.glob(f"answers_{self.username}_*.json"))
            if not json_files:
                return None

            json_files = sorted(json_files, key=lambda x: x.stat().st_mtime, reverse=True)
            for file in json_files:
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if not data.get('submitted', False):
                            if 'start_time' in data:
                                start_time = datetime.fromisoformat(data['start_time'])
                                current_time = datetime.now()
                                time_diff = (current_time - start_time).total_seconds()
                                if time_diff <= 50 * 60:
                                    return str(file)
                            else:
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
            self._save_current_state()
            if hasattr(self, 'exam_window') and self.exam_window:
                self.exam_window.close()
                self.exam_window = None
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
        """更新进度饼图"""
        ax = self.progress_pie.figure.subplots()
        ax.clear()
        labels = ['已掌握', '未掌握', '未做']
        sizes = [mastered, unmastered, undone]
        colors = ['#4CAF50', '#FF9800', '#BDBDBD']

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

        ax.legend(wedges, ['已掌握', '未掌握', '未做'],
                  title="图例", loc='upper right', bbox_to_anchor=(1.125, 1.125),
                  fontsize=10, title_fontsize=10)
        ax.axis('equal')
        self.progress_pie.draw()

    def _check_for_updates(self):
        """检查更新"""
        try:
            self.update_checker.check_for_updates()
        except Exception as e:
            logging.error(f"检查更新失败: {e}")

    def _handle_update_available(self, new_version, update_info):
        """处理发现新版本"""
        self.update_checker.show_update_dialog(self, new_version, update_info)

    def _update_progress_labels(self):
        """同步更新统计数字"""
        self.total_label.setText(f"总题目数：{self.progress.get('total', 0)}")
        self.done_label.setText(f"已做题目数：{self.progress.get('done', 0)}")
        self.undone_label.setText(f"未做题目数：{self.progress.get('undone', 0)}")
        self.mastered_label.setText(f"已掌握题目数：{self.progress.get('mastered', 0)}")
        self.unmastered_label.setText(f"未掌握题目数：{self.progress.get('unmastered', 0)}")

    def _show_done_indices(self):
        """弹窗显示已做题目编号"""
        indices = sorted(self.done_question_indices)
        self._show_indices_dialog("已做题目编号", indices)

    def _show_undone_indices(self):
        """弹窗显示未做题目编号"""
        indices = sorted(self.all_question_indices - self.done_question_indices)
        self._show_indices_dialog("未做题目编号", indices)

    def _show_mastered_indices(self):
        """弹窗显示已掌握题目编号"""
        indices = sorted(self.all_question_indices - self.unmastered_indices - (
                    self.all_question_indices - self.done_question_indices))
        self._show_indices_dialog("已掌握题目编号", indices)

    def _show_unmastered_indices(self):
        """弹窗显示未掌握题目编号"""
        indices = sorted(self.unmastered_indices)
        self._show_indices_dialog("未掌握题目编号", indices)

    def _show_indices_dialog(self, title, indices):
        """弹窗显示全部编号"""
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(400)
        dialog.setMaximumHeight(500)
        layout = QVBoxLayout(dialog)
        label = QLabel(f"共 {len(indices)} 个")
        layout.addWidget(label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)
        inner = QWidget()

        grid = QGridLayout()
        for idx, qid in enumerate(indices):
            btn = QPushButton(str(qid))
            btn.setStyleSheet("min-width:60px; min-height:28px;")
            btn.clicked.connect(lambda _, i=qid: self._preview_question(i))
            row = idx // 5
            col = idx % 5
            grid.addWidget(btn, row, col)

        hbox = QHBoxLayout()
        hbox.addLayout(grid)
        hbox.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        inner.setLayout(hbox)
        scroll.setWidget(inner)
        layout.addWidget(scroll)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.adjustSize()
        dialog.exec()

    def _preview_question(self, q_index):
        """预览指定题号的题干、选项和答案"""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"题目预览 - 编号{q_index}")
        dialog.setFixedSize(500, 350)
        layout = QVBoxLayout(dialog)

        try:
            df = pd.read_excel(QUESTION_FILE)
            questions = df.to_dict('records')

            if not (1 <= q_index <= len(questions)):
                return

            q = questions[q_index - 1]
            layout.addWidget(QLabel(f"<b>题目：</b>{q.get('题目', '')}"))

            for opt in ['A', 'B', 'C', 'D']:
                text = str(q.get('选项' + opt, '')).strip()
                for prefix in [f"{opt}.", f"{opt}．", f"{opt}、", f"{opt} "]:
                    if text.startswith(prefix):
                        text = text[len(prefix):].strip()
                        break
                layout.addWidget(QLabel(f"{opt}. {text}"))

            layout.addWidget(QLabel(f"<b>正确答案：</b>{q.get('答案', '')}"))

            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)
        except Exception as e:
            logging.error(f"预览题目失败: {e}")
            layout.addWidget(QLabel("无法加载题目信息"))
            close_btn = QPushButton("关闭")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

        dialog.exec()

    def _get_version(self):
        """获取当前版本号"""
        try:
            if VERSION_FILE.exists():
                with open(VERSION_FILE, "r") as f:
                    version = f.read().strip()
                    if version:
                        return version
            logging.error("version.txt 文件不存在或内容为空")
            return ""
        except Exception as e:
            logging.error(f"读取版本号失败: {e}")
            return ""


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