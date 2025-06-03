import sys
import pandas as pd
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QPushButton, QLabel, QRadioButton, QButtonGroup,
    QScrollArea, QFrame, QFileDialog, QMessageBox, QTextEdit
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QFont
import json
import os
from datetime import datetime
import random
import shutil
import glob
from pathlib import Path
import logging


class QuestionSystem(QMainWindow):
    # 定义信号
    answer_submitted = pyqtSignal(dict)

    def __init__(self, username="admin"):
        super().__init__()
        self.username = username
        self.questions = []
        self.original_indices = []  # 存储原始题号映射
        self.current_question = 0
        self.user_answers = {}
        self.total_time = 50 * 60  # 50分钟倒计时
        self.remaining_time = self.total_time
        self.viewed_answers = set()  # 记录用户查看过答案的题目索引
        self.submitted = False  # 是否已提交
        self.start_time = None  # 记录开始时间
        self.current_answer_file = None  # 当前答题文件路径

        # 初始化必要的目录和文件
        self._init_directories_and_files()

        # 设置窗口
        self.setWindowTitle("Xdhdyp-BKT")
        self.setGeometry(100, 100, 1344, 756)  # 16:9比例，占屏幕70%
        self.center_window()

        # 初始化界面
        self.init_ui()

        # 设置定时器
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_timer)

        # 尝试加载本地xlsx文件
        self.load_local_excel()

    def _init_directories_and_files(self):
        """初始化必要的目录和文件"""
        try:
            # 创建必要的目录
            directories = [
                'data/recommendation/history',
                'data/recommendation/save',
                'data/models',
                'data/models/model_yh'
            ]
            for directory in directories:
                os.makedirs(directory, exist_ok=True)

            # 初始化题目统计文件
            stats_file = Path("data/models/question_stats.json")
            if not stats_file.exists():
                with open(stats_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)

            # 初始化推荐文件
            recommendation_file = Path("data/models/model_yh/recommendation.json")
            if not recommendation_file.exists():
                with open(recommendation_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        'timestamp': datetime.now().isoformat(),
                        'username': self.username,
                        'question_weights': {},
                        'recommended_questions': []
                    }, f, ensure_ascii=False, indent=2)

            # 处理所有历史记录，生成初始推荐
            try:
                from models.question_processor import QuestionProcessor
                processor = QuestionProcessor(self.username)
                processor.process_all_history()
            except Exception as e:
                logging.error(f"初始化推荐失败: {e}")

        except Exception as e:
            logging.error(f"初始化目录和文件失败: {e}")

    def center_window(self):
        """将窗口居中显示"""
        screen = QApplication.primaryScreen().geometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)

    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QHBoxLayout(central_widget)

        # 左侧题号按钮区域
        self.create_question_buttons_area(main_layout)

        # 右侧主要内容区域
        self.create_main_content_area(main_layout)

        # 设置布局比例
        main_layout.setStretch(0, 3)  # 左侧占30%
        main_layout.setStretch(1, 7)  # 右侧占70%

    def create_question_buttons_area(self, parent_layout):
        """创建左侧题号按钮区域"""
        left_frame = QFrame()
        left_frame.setFrameStyle(QFrame.Shape.Box)
        left_layout = QVBoxLayout(left_frame)

        # 题号按钮标题
        title_label = QLabel("题号")
        title_label.setFont(QFont("微软雅黑", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title_label)

        # 滚动区域
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.question_grid = QGridLayout(scroll_widget)

        # 创建50个题号按钮
        self.question_buttons = []
        for i in range(50):
            btn = QPushButton(str(i + 1))
            btn.setFixedSize(50, 40)
            btn.setFont(QFont("微软雅黑", 10))
            btn.clicked.connect(lambda checked, idx=i: self.jump_to_question(idx))

            row = i // 5
            col = i % 5
            self.question_grid.addWidget(btn, row, col)
            self.question_buttons.append(btn)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        left_layout.addWidget(scroll_area)

        # 文件操作按钮
        file_layout = QVBoxLayout()

        load_btn = QPushButton("加载Excel文件")
        load_btn.setFont(QFont("微软雅黑", 10))
        load_btn.clicked.connect(self.load_excel_file)
        file_layout.addWidget(load_btn)

        save_btn = QPushButton("保存答案")
        save_btn.setFont(QFont("微软雅黑", 10))
        save_btn.clicked.connect(self.save_answers)
        file_layout.addWidget(save_btn)

        left_layout.addLayout(file_layout)
        parent_layout.addWidget(left_frame)

    def create_main_content_area(self, parent_layout):
        """创建右侧主要内容区域"""
        right_frame = QFrame()
        right_frame.setFrameStyle(QFrame.Shape.Box)
        right_layout = QVBoxLayout(right_frame)

        # 顶部信息栏
        self.create_top_info_bar(right_layout)

        # 题目内容区域
        self.create_question_content_area(right_layout)

        # 底部控制按钮
        self.create_bottom_controls(right_layout)

        parent_layout.addWidget(right_frame)

    def create_top_info_bar(self, parent_layout):
        """创建顶部信息栏，并为统计项添加可点击按钮"""
        top_layout = QHBoxLayout()

        # 当前题号
        self.current_question_label = QLabel("请先导入题库")
        self.current_question_label.setFont(QFont("微软雅黑", 12, QFont.Weight.Bold))
        top_layout.addWidget(self.current_question_label)

        top_layout.addStretch()

        # 倒计时
        self.timer_label = QLabel("剩余时间: --:--")
        self.timer_label.setFont(QFont("微软雅黑", 12, QFont.Weight.Bold))
        self.timer_label.setStyleSheet("color: red;")
        top_layout.addWidget(self.timer_label)

        # 提交按钮
        submit_btn = QPushButton("提交")
        submit_btn.setFont(QFont("微软雅黑", 10))
        submit_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 5px 15px; }")
        submit_btn.clicked.connect(self.submit_answers)
        top_layout.addWidget(submit_btn)

        parent_layout.addLayout(top_layout)

    def create_question_content_area(self, parent_layout):
        """创建题目内容区域"""
        content_frame = QFrame()
        content_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        content_layout = QVBoxLayout(content_frame)
        # 题目文本
        self.question_text = QTextEdit()
        self.question_text.setFont(QFont("微软雅黑", 12))
        self.question_text.setReadOnly(True)
        self.question_text.setMaximumHeight(150)
        self.question_text.setText("没有题库，请点击左侧'加载Excel文件'按钮导入题目")
        content_layout.addWidget(self.question_text)
        # 选项区域
        self.options_layout = QVBoxLayout()
        self.option_group = QButtonGroup()
        self.option_group.setExclusive(False)  # ✅ 允许取消选中
        self.option_buttons = []
        for i, option_text in enumerate(['A', 'B', 'C', 'D']):
            option_btn = QRadioButton(f"{option_text}. ")
            option_btn.setFont(QFont("微软雅黑", 11))
            option_btn.setEnabled(False)  # 默认禁用
            self.option_group.addButton(option_btn, i)
            self.option_buttons.append(option_btn)
            self.options_layout.addWidget(option_btn)
        content_layout.addLayout(self.options_layout)
        # 答案显示区域
        self.answer_frame = QFrame()
        self.answer_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        self.answer_frame.setStyleSheet("background-color: #f0f0f0;")
        answer_layout = QVBoxLayout(self.answer_frame)
        self.answer_label = QLabel("正确答案: ")
        self.answer_label.setFont(QFont("微软雅黑", 11, QFont.Weight.Bold))
        self.answer_label.setStyleSheet("color: green;")
        answer_layout.addWidget(self.answer_label)
        self.answer_frame.hide()  # 默认隐藏答案
        content_layout.addWidget(self.answer_frame)
        content_layout.addStretch()
        parent_layout.addWidget(content_frame)

    def create_bottom_controls(self, parent_layout):
        """创建底部控制按钮"""
        bottom_layout = QHBoxLayout()

        # 设置按钮统一宽度
        btn_width = 100

        # 上一题按钮
        self.prev_btn = QPushButton("上一题")
        self.prev_btn.setFont(QFont("微软雅黑", 10))
        self.prev_btn.setEnabled(False)  # 默认禁用
        self.prev_btn.clicked.connect(self.previous_question)
        # 修改：设置固定宽度
        self.prev_btn.setFixedWidth(btn_width)
        bottom_layout.addWidget(self.prev_btn)

        # 查看答案按钮
        self.show_answer_btn = QPushButton("查看答案")
        self.show_answer_btn.setFont(QFont("微软雅黑", 10))
        self.show_answer_btn.setEnabled(False)  # 默认禁用
        self.show_answer_btn.clicked.connect(self.toggle_answer)
        # 修改：设置固定宽度
        self.show_answer_btn.setFixedWidth(btn_width)
        # 中间添加伸缩空间
        bottom_layout.addStretch()  # 新增：让中间按钮居中
        bottom_layout.addWidget(self.show_answer_btn)
        bottom_layout.addStretch()  # 新增：让中间按钮居中

        # 下一题按钮
        self.next_btn = QPushButton("下一题")
        self.next_btn.setFont(QFont("微软雅黑", 10))
        self.next_btn.setEnabled(False)  # 默认禁用
        self.next_btn.clicked.connect(self.next_question)
        # 修改：设置固定宽度
        self.next_btn.setFixedWidth(btn_width)
        bottom_layout.addWidget(self.next_btn)

        parent_layout.addLayout(bottom_layout)

    def load_local_excel(self):
        """尝试加载本地Excel文件"""
        local_file = os.path.join(os.getcwd(), "data", "static", "单选题.xlsx")
        logging.info(f"尝试加载题库文件: {local_file}")
        if os.path.exists(local_file):
            self.load_excel_from_path(local_file)
        else:
            logging.error("题库文件不存在！")
            self.show_no_questions_message()
        self.current_answer_file = None  # 新增：当前答题文件路径

    def show_no_questions_message(self):
        """显示没有题库的提示信息"""
        self.current_question_label.setText("没有题库，请导入")
        self.timer_label.setText("剩余时间: --:--")
        self.question_text.setText("没有题库，请点击左侧'加载Excel文件'按钮导入题目")

        # 禁用所有控制按钮
        for btn in self.question_buttons:
            btn.setEnabled(False)
            btn.setStyleSheet("QPushButton { background-color: #cccccc; }")

        for btn in self.option_buttons:
            btn.setEnabled(False)

        self.prev_btn.setEnabled(False)
        self.next_btn.setEnabled(False)
        self.show_answer_btn.setEnabled(False)

    def load_excel_from_path(self, file_path):
        """从指定路径加载Excel文件"""
        try:
            df = pd.read_excel(file_path)
            required_columns = ['题号', '题目', '选项A', '选项B', '选项C', '选项D', '答案']
            if all(col in df.columns for col in required_columns):
                original_data = df.to_dict('records')
                # 每次都重新初始化题目顺序
                self.original_indices = random.sample(range(len(original_data)), 50)
                self.questions = [original_data[i] for i in self.original_indices]
                
                # 新增：判断单选/多选
                for q in self.questions:
                    ans = str(q['答案']).strip()
                    q['is_multi'] = len(ans) > 1
                
                self.current_question = 0
                self.user_answers = {}
                self.submitted = False
                self.start_time = datetime.now()  # 记录开始时间
                
                # 启用界面控件
                self.enable_interface()
                self.update_question_display()
                self.update_question_buttons()
                
                # 重置并开始倒计时
                self.remaining_time = self.total_time
                self.timer.start(1000)
                
                # 创建保存目录
                os.makedirs('data/recommendation', exist_ok=True)
                
                auto_information(self, "成功", f"成功加载 {len(self.questions)} 道题目")
            else:
                logging.error("Excel文件缺少必要列")
                self.show_no_questions_message()
        except Exception as e:
            logging.error(f"加载题库失败: {e}")
            self.show_no_questions_message()

    def enable_interface(self):
        """启用界面控件"""
        for btn in self.option_buttons:
            btn.setEnabled(True)

        self.prev_btn.setEnabled(True)
        self.next_btn.setEnabled(True)
        self.show_answer_btn.setEnabled(True)

    def load_excel_file(self):
        """加载Excel文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择Excel文件", "", "Excel files (*.xlsx *.xls)"
        )

        if file_path:
            self.load_excel_from_path(file_path)

    def update_question_display(self):
        """更新题目显示"""
        if not self.questions:
            self.show_no_questions_message()
            return
            
        # 断开之前的信号连接
        try:
            self.option_group.buttonClicked.disconnect(self.save_current_answer)
        except:
            pass
            
        # 清除旧的按钮组
        for btn in self.option_buttons:
            self.option_group.removeButton(btn)
            self.options_layout.removeWidget(btn)
            btn.deleteLater()
            
        # 创建新的按钮组
        self.option_group = QButtonGroup()
        self.option_buttons = []
        
        question = self.questions[self.current_question]
        # 设置单选/多选模式
        self.option_group.setExclusive(not question.get('is_multi', False))
        
        # 创建新的选项按钮
        options = [question['选项A'], question['选项B'], question['选项C'], question['选项D']]
        for i, option_text in enumerate(options):
            option_btn = QRadioButton(option_text)
            option_btn.setFont(QFont("微软雅黑", 11))
            option_btn.setEnabled(not self.submitted and self.current_question not in self.viewed_answers)
            self.option_group.addButton(option_btn, i)
            self.option_buttons.append(option_btn)
            self.options_layout.addWidget(option_btn)
            
        # 更新题号
        self.current_question_label.setText(f"第 {self.current_question + 1} 题 / 共 {len(self.questions)} 题")
        
        # 更新题目内容
        self.question_text.setText(question['题目'])
            
        # 恢复用户之前的选择
        if self.current_question in self.user_answers:
            answer = self.user_answers[self.current_question]
            if question.get('is_multi', False):
                # 多选，answer为字符串如"AC"
                for i, btn in enumerate(self.option_buttons):
                    if chr(ord('A') + i) in answer:
                        btn.setChecked(True)
            else:
                # 单选
                answer_index = ord(answer) - ord('A')
                if 0 <= answer_index < len(self.option_buttons):
                    self.option_buttons[answer_index].setChecked(True)
                    
        # 更新答案显示
        self.answer_label.setText(f"正确答案: {question['答案']}")
        
        # 检查是否已查看过答案
        if self.current_question in self.viewed_answers:
            self.answer_frame.show()
            self.show_answer_btn.setText("看过还想改？")
            for btn in self.option_buttons:
                btn.setEnabled(False)
        elif self.submitted:
            self.answer_frame.show()
            self.show_answer_btn.setText("隐藏答案")
            for btn in self.option_buttons:
                btn.setEnabled(False)
        else:
            self.answer_frame.hide()
            self.show_answer_btn.setText("查看答案")
            for btn in self.option_buttons:
                btn.setEnabled(True)
                
        # 重新连接信号
        self.option_group.buttonClicked.connect(self.save_current_answer)

    def save_current_answer(self):
        """保存当前题目的答案"""
        question = self.questions[self.current_question]
        if question.get('is_multi', False):
            # 多选，收集所有被选中的选项
            answer = ''
            for i, btn in enumerate(self.option_buttons):
                if btn.isChecked():
                    answer += chr(ord('A') + i)
            if answer:
                self.user_answers[self.current_question] = answer
            elif self.current_question in self.user_answers:
                del self.user_answers[self.current_question]
        else:
            # 单选
            checked_button = self.option_group.checkedButton()
            if checked_button:
                button_index = self.option_group.id(checked_button)
                answer = chr(ord('A') + button_index)
                self.user_answers[self.current_question] = answer
            else:
                if self.current_question in self.user_answers:
                    del self.user_answers[self.current_question]
        self.update_question_buttons()
        
        # 每完成10题自动保存
        if len(self.user_answers) % 10 == 0:
            self.auto_save_answers()

    def update_question_buttons(self):
        """更新题号按钮状态"""
        for i, btn in enumerate(self.question_buttons):
            if i < len(self.questions):
                if self.submitted:
                    btn.setEnabled(True)
                    # 正确绿色，答错红色，未作答灰色
                    if i in self.user_answers:
                        # 判断正误
                        user_ans = self.user_answers[i]
                        correct_ans = str(self.questions[i]['答案']).strip()
                        if user_ans == correct_ans:
                            btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
                        else:
                            btn.setStyleSheet("QPushButton { background-color: #ff4444; color: white; }")
                    else:
                        btn.setStyleSheet("QPushButton { background-color: #cccccc; color: black; }")
                else:
                    btn.setEnabled(True)
                    if i in self.viewed_answers:
                        # 查看过答案的题目显示橙色
                        btn.setStyleSheet("QPushButton { background-color: #FFA500; color: white; }")
                    elif i in self.user_answers:
                        btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
                    elif i == self.current_question:
                        btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; }")
                    else:
                        btn.setStyleSheet("")
            else:
                btn.setEnabled(False)
                btn.setStyleSheet("QPushButton { background-color: #cccccc; }")

    def jump_to_question(self, question_index):
        """跳转到指定题目"""
        if 0 <= question_index < len(self.questions):
            self.current_question = question_index
            self.update_question_display()
            self.update_question_buttons()

    def previous_question(self):
        """上一题"""
        if self.current_question > 0:
            self.current_question -= 1
            self.update_question_display()
            self.update_question_buttons()

    def next_question(self):
        """下一题"""
        if self.current_question < len(self.questions) - 1:
            self.current_question += 1
            self.update_question_display()
            self.update_question_buttons()

    def toggle_answer(self):
        """切换答案显示"""
        if not self.answer_frame.isVisible():
            self.answer_frame.show()
            self.show_answer_btn.setText("看过还想改？")
            # 添加当前题目到查看过的集合
            self.viewed_answers.add(self.current_question)
            # 删除用户的答案（如果存在）
            if self.current_question in self.user_answers:
                del self.user_answers[self.current_question]
            # 禁用所有选项按钮
            for btn in self.option_buttons:
                btn.setEnabled(False)
            self.update_question_buttons()

    def update_timer(self):
        """更新倒计时"""
        if self.remaining_time > 0:
            self.remaining_time -= 1
            minutes = self.remaining_time // 60
            seconds = self.remaining_time % 60
            self.timer_label.setText(f"剩余时间: {minutes:02d}:{seconds:02d}")

            # 最后5分钟变红色闪烁
            if self.remaining_time <= 300:
                if self.remaining_time % 2 == 0:
                    self.timer_label.setStyleSheet("color: red; font-weight: bold;")
                else:
                    self.timer_label.setStyleSheet("color: darkred; font-weight: bold;")
        else:
            self.timer.stop()
            self.timer_label.setText("时间到！")
            self.submit_answers()

    def auto_save_answers(self):
        """自动保存答案到 save 目录"""
        if not self.questions:
            return

        try:
            # 创建保存数据
            save_data = {
                "answers": self.user_answers,
                "timestamp": datetime.now().isoformat(),
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "total_questions": len(self.questions),
                "answered_questions": len(self.user_answers),
                "original_indices": self.original_indices,
                "username": self.username,
                "submitted": False,
                "viewed_answers": list(self.viewed_answers),
                "remaining_time": self.remaining_time
            }

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"answers_{self.username}_{timestamp}.json"
            file_path = os.path.join('data', 'recommendation', 'save', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 保存文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
            
            # 更新当前答题文件路径
            self.current_answer_file = file_path
        except Exception as e:
            logging.error(f"自动保存失败：{str(e)}")

    def save_answers(self):
        """手动保存答案到 save 目录"""
        if not self.user_answers:
            auto_warning(self, "警告", "没有答案需要保存")
            return

        try:
            # 创建保存数据
            save_data = {
                "answers": self.user_answers,
                "timestamp": datetime.now().isoformat(),
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "total_questions": len(self.questions),
                "answered_questions": len(self.user_answers),
                "original_indices": self.original_indices,
                "username": self.username,
                "submitted": False,
                "viewed_answers": list(self.viewed_answers),
                "remaining_time": self.remaining_time
            }

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"answers_{self.username}_{timestamp}.json"
            file_path = os.path.join('data', 'recommendation', 'save', filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            # 删除该用户之前的临时保存文件
            save_dir = Path('data/recommendation/save')
            if save_dir.exists():
                for old_file in save_dir.glob(f"answers_{self.username}_*.json"):
                    try:
                        old_file.unlink()
                    except Exception as e:
                        logging.error(f"删除旧临时文件失败: {e}")

            # 保存新的临时文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            auto_information(self, "成功", f"答案已保存到：{file_path}")
            self.current_answer_file = file_path
        except Exception as e:
            auto_critical(self, "错误", f"保存失败：{str(e)}")

    def submit_answers(self):
        """提交答案"""
        self.timer.stop()
        self.submitted = True

        # 计算得分
        correct_count = 0
        total_count = len(self.questions)
        wrong_questions = set()

        # 初始化BKT模型
        from models.bkt_model import BKTModel
        bkt_model = BKTModel()

        # 收集答题历史
        answer_history = {}
        for i, question in enumerate(self.questions):
            q_id = str(i + 1)  # 转换为1开始的题号
            if q_id not in answer_history:
                answer_history[q_id] = []
            
            # 判断答案是否正确
            is_correct = False
            if i in self.user_answers and i not in self.viewed_answers:
                user_ans = self.user_answers[i]
                correct_ans = str(question['答案']).strip()
                is_correct = user_ans == correct_ans
                if is_correct:
                    correct_count += 1
                else:
                    wrong_questions.add(i)
            
            # 添加到答题历史
            answer_history[q_id].append({
                'answer': self.user_answers.get(i, ''),
                'is_correct': is_correct,
                'timestamp': datetime.now().isoformat()
            })

        score = (correct_count / total_count) * 100 if total_count > 0 else 0

        # 使用BKT模型计算掌握度
        mastery = bkt_model.calculate_mastery(answer_history)
        
        # 判断已掌握题目
        mastered_questions = set()
        for q_id, mastery_data in mastery.items():
            # 使用BKT掌握概率判断
            bkt_prob = mastery_data['mastery_probability']
            correct_rate = mastery_data['correct_rate']
            attempt_count = mastery_data['attempt_count']
            
            # 如果BKT掌握概率大于0.7，且正确率大于0.6，且至少做过2次，则认为已掌握
            if bkt_prob > 0.7 and correct_rate > 0.6 and attempt_count >= 2:
                mastered_questions.add(int(q_id) - 1)  # 转换回0开始的索引

        # 显示所有答案
        self.answer_frame.show()
        self.show_answer_btn.setText("隐藏答案")

        # 更新左侧题号按钮颜色
        self.update_question_buttons()

        # 显示得分信息
        result_text = f"""考试结束！\n总题数：{total_count}\n已答题数：{len(self.user_answers)}\n正确题数：{correct_count}\n得分：{score:.1f}分\n已掌握题目数：{len(mastered_questions)}"""

        auto_information(self, "考试结束", result_text)

        # 禁用相关按钮
        for btn in self.option_buttons:
            btn.setEnabled(False)
        self.show_answer_btn.setEnabled(False)
        self.prev_btn.setEnabled(True)
        self.next_btn.setEnabled(True)

        # 刷新当前题目显示
        self.update_question_display()

        # 组装要保存的数据
        save_data = {
            "answers": {str(k): v for k, v in self.user_answers.items()},
            "timestamp": datetime.now().isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "total_questions": len(self.questions),
            "answered_questions": len(self.user_answers),
            "original_indices": self.original_indices,
            "username": self.username,
            "submitted": True,
            "viewed_answers": list(self.viewed_answers),
            "remaining_time": self.remaining_time,
            "unanswered_questions": [i for i in range(len(self.questions)) if i not in self.user_answers],
            "mastered_questions": list(mastered_questions),
            "mastery_data": {
                q_id: {
                    "mastery_probability": data["mastery_probability"],
                    "correct_rate": data["correct_rate"],
                    "attempt_count": data["attempt_count"]
                }
                for q_id, data in mastery.items()
            }
        }

        try:
            # 保存到history
            os.makedirs('data/recommendation/history', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"answers_{self.username}_{timestamp}.json"
            file_path = os.path.join('data', 'recommendation', 'history', filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            # 删除save目录下的所有临时文件
            save_dir = Path('data/recommendation/save')
            if save_dir.exists():
                # 获取所有该用户的临时文件
                temp_files = list(save_dir.glob(f"answers_{self.username}_*.json"))
                for temp_file in temp_files:
                    try:
                        # 确保文件存在且可访问
                        if temp_file.exists() and temp_file.is_file():
                            # 尝试关闭可能打开的文件句柄
                            try:
                                if hasattr(self, 'current_answer_file') and self.current_answer_file:
                                    with open(self.current_answer_file, 'r') as f:
                                        pass  # 确保文件句柄已关闭
                            except:
                                pass
                            # 删除文件
                            temp_file.unlink()
                            logging.info(f"成功删除临时文件: {temp_file}")
                    except Exception as e:
                        logging.error(f"删除临时文件失败 {temp_file}: {e}")

            self.current_answer_file = None

            # 处理答题记录并生成推荐
            from models.question_processor import QuestionProcessor
            processor = QuestionProcessor(self.username)
            processor.process_answer_file(file_path)

            # 删除旧的推荐文件
            recommendation_dir = Path("data/models/model_yh")
            if recommendation_dir.exists():
                old_recommendations = list(recommendation_dir.glob("recommendation_*.json"))
                for old_file in old_recommendations:
                    try:
                        old_file.unlink()
                        logging.info(f"成功删除旧推荐文件: {old_file}")
                    except Exception as e:
                        logging.error(f"删除旧推荐文件失败 {old_file}: {e}")

        except Exception as e:
            logging.error(f"保存历史记录失败: {e}")

        # 发送答题结果信号
        answer_data = {
            'timestamp': datetime.now().isoformat(),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'username': self.username,
            'score': score,
            'correct_count': correct_count,
            'total_questions': total_count,
            'user_answers': self.user_answers,
            'viewed_answers': list(self.viewed_answers),
            'original_indices': self.original_indices,
            'question_times': {},
            'mastered_questions': list(mastered_questions),
            'mastery_data': save_data['mastery_data']
        }
        self.answer_submitted.emit(answer_data)

        self.mastered_questions = mastered_questions  # 保存到self，供统计用

    def load_answer_file(self, file_path):
        """加载保存的答案文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 检查是否超过考试时间
            if 'start_time' in data:
                start_time = datetime.fromisoformat(data['start_time'])
                current_time = datetime.now()
                time_diff = (current_time - start_time).total_seconds()
                
                # 如果超过50分钟，自动结束考试
                if time_diff > self.total_time:
                    auto_warning(self, "提示", "考试时间已超过50分钟，将自动结束考试")
                    self.submitted = True
                    self.timer.stop()
                    self.show_answer_btn.setText("隐藏答案")
                    self.answer_frame.show()
                    self.remaining_time = 0  # 设置剩余时间为0
                    self.timer_label.setText("剩余时间: 00:00")
                    self.timer_label.setStyleSheet("color: red; font-weight: bold;")
                    
                    # 记录未完成的题目
                    if 'answers' in data:
                        answered_questions = set(int(idx) for idx in data['answers'].keys())
                        all_questions = set(range(len(self.original_indices)))
                        unfinished_questions = all_questions - answered_questions
                        
                        # 更新json文件，记录未完成的题目
                        data['unfinished_questions'] = list(unfinished_questions)
                        data['remaining_time'] = 0
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                else:
                    # 计算剩余时间
                    self.remaining_time = self.total_time - int(time_diff)
                    self.timer.start(1000)
            else:
                self.remaining_time = self.total_time
                self.timer.start(1000)

            # 恢复原始题号映射
            if 'original_indices' in data:
                self.original_indices = data['original_indices']
            else:
                self.original_indices = list(range(50))

            # 加载题库
            local_file = os.path.join(os.getcwd(), "data", "static", "单选题.xlsx")
            if not os.path.exists(local_file):
                auto_critical(self, "错误", "题库文件不存在，无法恢复答题记录")
                return

            df = pd.read_excel(local_file)
            original_data = df.to_dict('records')

            # 按 original_indices 顺序重排题目
            self.questions = [original_data[i] for i in self.original_indices]
            for q in self.questions:
                ans = str(q['答案']).strip()
                q['is_multi'] = len(ans) > 1

            self.current_question = 0
            self.user_answers = {}
            self.viewed_answers = set()
            self.start_time = None

            # 恢复用户答案（直接用题号映射）
            if 'answers' in data:
                self.user_answers = {int(idx): ans for idx, ans in data['answers'].items()}
                
            # 恢复查看过的答案
            if 'viewed_answers' in data:
                self.viewed_answers = set(int(idx) for idx in data['viewed_answers'])
                
            # 恢复开始时间
            if 'start_time' in data:
                self.start_time = datetime.fromisoformat(data['start_time'])
                
            # 恢复提交状态
            if 'submitted' in data and data['submitted']:
                self.submitted = True
                self.timer.stop()
                self.show_answer_btn.setText("隐藏答案")
                self.answer_frame.show()
                self.remaining_time = 0  # 确保倒计时显示为00:00
                self.timer_label.setText("剩余时间: 00:00")
                self.timer_label.setStyleSheet("color: red; font-weight: bold;")

            # 更新界面
            self.update_question_display()
            self.update_question_buttons()
                
            auto_information(self, "成功", "成功加载上次答题记录")
            
            self.current_answer_file = file_path  # 新增：当前答题文件路径
            
        except Exception as e:
            logging.error(f"加载答案文件失败：{str(e)}")
            auto_critical(self, "错误", f"加载答案文件失败：{str(e)}")
            self.load_local_excel()  # 如果加载失败，重新加载题库

    def closeEvent(self, event):
        """处理窗口关闭事件
        1. 只有未提交时才自动保存答题进度到 save 目录，并弹出主界面。
        2. 如果已提交（self.submitted == True），则不再保存、不再弹主界面，直接关闭窗口。
        这样可避免提交后出现两个主界面，也不会生成多余 save 文件影响掌握度统计。
        """
        try:
            # 只有未提交时才自动保存
            if not self.submitted:
                self.auto_save_answers()
                # 只在未提交时弹主界面
                from main_window import MainWindow
                main_window = MainWindow(username=self.username)
                main_window.show()
            # 如果已提交，什么都不做，直接关闭
            event.accept()
        except Exception as e:
            logging.error(f"关闭窗口时发生错误: {e}")
            event.accept()


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

    # 设置应用样式
    app.setStyle('Fusion')

    window = QuestionSystem()
    window.show()

    sys.exit(app.exec())


# if __name__ == '__main__':
#     main()