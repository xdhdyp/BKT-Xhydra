import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QMessageBox, QListWidget, QDialog, QScrollArea, QGridLayout, QHBoxLayout, QSpacerItem, QSizePolicy
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
from update_checker import UpdateChecker
import webbrowser

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
        
        # 初始化题目编号集合
        self.all_question_indices = set()
        self.done_question_indices = set()
        self.unmastered_indices = set()
        
        # 加载用户数据
        self._load_user_data()
        
        # 更新UI
        self._update_ui()
        
        # 设置窗口关闭事件处理
        self.closeEvent = self._handle_close_event
        
        # 初始化更新检查器
        self.update_checker = UpdateChecker()
        self.update_checker.update_available.connect(self._handle_update_available)
        
        # 启动时检查更新
        QTimer.singleShot(1000, self._check_for_updates)

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
            # 只在有update_progress_labels时调用，否则忽略
            if hasattr(self, 'update_progress_labels'):
                self.total_label.setText("总题目数：0")
                self.done_btn.setText("已做题目数：0")
                self.undone_btn.setText("未做题目数：0")
                self.unmastered_btn.setText("未掌握题目数：0")
            self.user_data = {
                "用户名": self.username,
                "考试记录": {},
                "当前考试": {}
            }

        self._update_progress_labels()

    def _update_progress(self):
        """更新学习进度（基于所有历史记录）"""
        try:
            # 读取题库
            question_file = Path("data/static/单选题.xlsx")
            if not question_file.exists():
                if hasattr(self, 'progress_label'):
                    self.progress_label.setText("题库不存在")
                return
            df = pd.read_excel(question_file)
            questions = df.to_dict('records')
            total = len(questions)
            all_indices = set(range(1, total + 1))  # 题号从1开始

            # 遍历所有历史答题记录，收集已做题目编号
            history_dir = Path("data/recommendation/history")
            answer_files = list(history_dir.glob(f"answers_{self.username}_*.json"))
            done_indices = set()
            
            # 初始化BKT模型
            from models.bkt_model import BKTModel
            bkt_model = BKTModel()
            
            # 处理所有答题记录
            answer_history = {}
            for answer_file in answer_files:
                try:
                    with open(answer_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        q_order = data.get('original_indices', [])
                        user_answers = data.get('user_answers', {})
                        correct_answers = data.get('correct_answers', {})
                        
                        # 收集答题历史
                        for idx in q_order:
                            q_id = str(idx + 1)  # 转换为1开始的题号
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
                            
                            # 记录已做题目
                            done_indices.add(idx + 1)
                except Exception as e:
                    logging.error(f"读取答题文件失败 {answer_file}: {e}")
                    continue

            # 使用BKT模型计算掌握度
            mastery = bkt_model.calculate_mastery(answer_history)
            
            # 判断已掌握题目
            mastered_indices = set()
            for q_id, mastery_data in mastery.items():
                # 使用BKT掌握概率判断
                bkt_prob = mastery_data['mastery_probability']
                correct_rate = mastery_data['correct_rate']
                attempt_count = mastery_data['attempt_count']
                
                # 如果BKT掌握概率大于0.7，且正确率大于0.6，且至少做过2次，则认为已掌握
                if bkt_prob > 0.7 and correct_rate > 0.6 and attempt_count >= 2:
                    mastered_indices.add(int(q_id))
            
            # 计算未掌握题目
            unmastered_indices = done_indices - mastered_indices
            undone_indices = all_indices - done_indices

            self.done_question_indices = done_indices
            self.unmastered_indices = unmastered_indices
            self.all_question_indices = all_indices

            # 统计数据
            done = len(done_indices)
            undone = len(undone_indices)
            unmastered = len(unmastered_indices)
            mastered = len(mastered_indices)

            self.progress.update({
                'total': total,
                'done': done,
                'undone': undone,
                'unmastered': unmastered,
                'mastered': mastered
            })

            # 更新进度显示
            if hasattr(self, 'progress_label'):
                self.progress_label.setText(
                    f"总题目数：{total}\n"
                    f"已做题目数：{done}\n"
                    f"未做题目数：{undone}\n"
                    f"已掌握题目数：{mastered}\n"
                    f"未掌握题目数：{unmastered}"
                )

            # 更新饼图
            if hasattr(self, 'progress_pie'):
                self._update_progress_pie(mastered, unmastered, undone)

        except Exception as e:
            logging.error(f"更新进度失败: {e}")
            if hasattr(self, 'progress_label'):
                self.progress_label.setText("总题目数：0\n已做题目数：0\n未做题目数：0\n未掌握题目数：0")

        self._update_progress_labels()

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

        self._update_progress_labels()

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
                    
            # 更新最近考试记录显示
            if hasattr(self, 'recent_exams_list'):
                self.recent_exams_list.clear()
                for exam in recent_exams:
                    self.recent_exams_list.addItem(
                        f"{exam['date']} - 得分：{exam['score']} ({exam['correct']}/{exam['total']})"
                    )
            
        except Exception as e:
            logging.error(f"更新最近考试记录失败: {e}")

    def _update_charts(self):
        """更新图表显示"""
        # 更新进度饼图
        if hasattr(self, 'progress_pie'):
            self._update_progress_pie(
                self.progress.get('mastered', 0),
                self.progress.get('unmastered', 0),
                self.progress.get('undone', 0)
            )

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
        
        # 统计信息
        self.total_label = QLabel()
        self.done_label = QLabel()
        self.undone_label = QLabel()
        self.mastered_label = QLabel()
        self.unmastered_label = QLabel()
        # 设置字体样式
        for label in [self.total_label, self.done_label, self.undone_label, self.mastered_label, self.unmastered_label]:
            label.setStyleSheet("font-size: 22px; color: #000; margin-bottom: 6px; font-weight: bold;")

        # 第一行：总题目数
        left_layout.addWidget(self.total_label)

        # 后四行：统计+按钮
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
        self._update_progress_labels()
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
                    
                    # 保存到history，使用统一的文件名格式
                    history_dir = Path('data/recommendation/history')
                    history_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    history_file = history_dir / f"answers_{self.username}_{timestamp}.json"
                    
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
                    processor.process_answer_file(str(history_file))
            
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
            "版本：v1.2.18<br>"
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

        # GitHub按钮区域
        github_btn_layout = QHBoxLayout()
        github_btn = QPushButton("  GitHub")
        github_btn.setIcon(QIcon("data/static/github.png"))  # 图标路径
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
            
            # 保存答题记录到历史文件
            history_dir = Path('data/recommendation/history')
            history_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用统一的文件名格式
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            history_file = history_dir / f"answers_{self.username}_{timestamp}.json"
            
            # 添加时间戳到答题数据
            answer_data['timestamp'] = datetime.now().isoformat()
            
            # 保存答题记录
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(answer_data, f, ensure_ascii=False, indent=2)
            
            # 处理答题记录并生成推荐
            from models.question_processor import QuestionProcessor
            processor = QuestionProcessor(self.username)
            processor.process_answer_file(str(history_file))
            
            # 关键：更新UI，刷新全部UI（进度区、最近考试、图表等）
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
                        # 检查是否已提交且未过期
                        if not data.get('submitted', False):
                            # 检查是否超过考试时间
                            if 'start_time' in data:
                                start_time = datetime.fromisoformat(data['start_time'])
                                current_time = datetime.now()
                                time_diff = (current_time - start_time).total_seconds()
                                if time_diff <= 50 * 60:  # 50分钟
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

    def _check_for_updates(self):
        """检查更新"""
        try:
            self.update_checker.check_for_updates()
        except Exception as e:
            logging.error(f"检查更新失败: {e}")

    def _handle_update_available(self, new_version, update_info):
        """处理发现新版本"""
        self.update_checker.show_update_dialog(self, new_version, update_info)

    # 更新进度标签内容
    def _update_progress_labels(self):
        """同步更新统计数字"""
        self.total_label.setText(f"总题目数：{self.progress.get('total', 0)}")
        self.done_label.setText(f"已做题目数：{self.progress.get('done', 0)}")
        self.undone_label.setText(f"未做题目数：{self.progress.get('undone', 0)}")
        self.mastered_label.setText(f"已掌握题目数：{self.progress.get('mastered', 0)}")
        self.unmastered_label.setText(f"未掌握题目数：{self.progress.get('unmastered', 0)}")

    # 显示已做题目编号
    def _show_done_indices(self):
        """弹窗显示已做题目编号"""
        indices = sorted(self.done_question_indices)
        self._show_indices_dialog("已做题目编号", indices)

    # 显示未做题目编号
    def _show_undone_indices(self):
        """弹窗显示未做题目编号"""
        indices = sorted(self.all_question_indices - self.done_question_indices)
        self._show_indices_dialog("未做题目编号", indices)

    # 显示已掌握题目编号
    def _show_mastered_indices(self):
        """弹窗显示已掌握题目编号"""
        indices = sorted(self.all_question_indices - self.unmastered_indices - (self.all_question_indices - self.done_question_indices))
        self._show_indices_dialog("已掌握题目编号", indices)

    # 显示未掌握题目编号
    def _show_unmastered_indices(self):
        """弹窗显示未掌握题目编号"""
        indices = sorted(self.unmastered_indices)
        self._show_indices_dialog("未掌握题目编号", indices)

    # 通用弹窗显示编号（每个编号可点击预览题目）
    def _show_indices_dialog(self, title, indices):
        """弹窗显示全部编号，每行5个编号按钮，可点击预览题目，内容少时自动缩放，高于一页时滚动"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea, QWidget, QGridLayout, QHBoxLayout, QSpacerItem, QSizePolicy

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(400)
        dialog.setMaximumHeight(500)  # 最大高度，超出则滚动

        layout = QVBoxLayout(dialog)
        label = QLabel(f"共 {len(indices)} 个")
        layout.addWidget(label)

        # 滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(400)  # 超过400才滚动，否则自适应
        inner = QWidget()

        # grid布局装按钮
        grid = QGridLayout()
        for idx, qid in enumerate(indices):
            btn = QPushButton(str(qid))
            btn.setStyleSheet("min-width:60px; min-height:28px;")
            btn.clicked.connect(lambda _, i=qid: self._preview_question(i))
            row = idx // 5
            col = idx % 5
            grid.addWidget(btn, row, col)

        # 外层hbox，左边是grid，右边加spacer
        hbox = QHBoxLayout()
        hbox.addLayout(grid)
        hbox.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
        inner.setLayout(hbox)

        scroll.setWidget(inner)
        layout.addWidget(scroll)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        # 让弹窗高度自适应内容（但不超过最大高度）
        dialog.adjustSize()
        dialog.exec()

    def _preview_question(self, q_index):
        """
        预览指定题号的题干、选项和答案，自动去除选项内容前的A. B.等前缀
        """
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        import pandas as pd
        from pathlib import Path

        # 读取题库
        question_file = Path("data/static/单选题.xlsx")
        if not question_file.exists():
            return

        df = pd.read_excel(question_file)
        questions = df.to_dict('records')
        # 题号从1开始
        if not (1 <= q_index <= len(questions)):
            return

        q = questions[q_index - 1]
        dialog = QDialog(self)
        dialog.setWindowTitle(f"题目预览 - 编号{q_index}")
        dialog.setFixedSize(500, 350)
        layout = QVBoxLayout(dialog)

        # 题干
        layout.addWidget(QLabel(f"<b>题目：</b>{q.get('题目', '')}"))

        # 选项（去除A. B.等前缀）
        for opt in ['A', 'B', 'C', 'D']:
            text = str(q.get('选项'+opt, '')).strip()
            # 去除前缀"A."、"A．"、"A、"、"A "等
            for prefix in [f"{opt}.", f"{opt}．", f"{opt}、", f"{opt} "]:
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                    break
            layout.addWidget(QLabel(f"{opt}. {text}"))

        # 答案
        layout.addWidget(QLabel(f"<b>正确答案：</b>{q.get('答案', '')}"))

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.exec()

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