import json
import logging
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QScrollArea,
    QMessageBox, QRadioButton,
    QLineEdit, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont
from transformers import pipeline
import requests

# 配置日志记录
logging.basicConfig(
    filename='app.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


def get_model_preference():
    config_path = Path("data/config/model_preference.json")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f).get("preference", "auto")
    return "auto"


def set_model_preference(pref):
    config_path = Path("data/config/model_preference.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"preference": pref}, f, ensure_ascii=False, indent=2)


class ModelSelectDialog(QDialog):
    """模型选择对话框（按钮式）"""

    def __init__(self, parent=None, local_model_check=None, api_config_check=None):
        super().__init__(parent)
        self.setWindowTitle("选择模型")
        self.setFixedSize(350, 200)
        layout = QVBoxLayout(self)
        label = QLabel("请选择使用的模型")
        label.setFont(QFont("微软雅黑", 12, QFont.Weight.Bold))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        btn_layout = QHBoxLayout()
        self.local_btn = QPushButton("本地模型")
        self.api_btn = QPushButton("配置API")
        btn_layout.addWidget(self.local_btn)
        btn_layout.addWidget(self.api_btn)
        layout.addLayout(btn_layout)
        self.selected = None
        self.local_btn.clicked.connect(self._choose_local)
        self.api_btn.clicked.connect(self._choose_api)
        self.local_model_check = local_model_check
        self.api_config_check = api_config_check

    def _choose_local(self):
        if self.local_model_check and self.local_model_check():
            self.selected = 'local'
            self.accept()
        elif self.api_config_check and self.api_config_check():
            QMessageBox.information(self, "自动切换", "本地模型不可用，已自动切换到API。")
            self.selected = 'api'
            self.accept()
        else:
            QMessageBox.warning(self, "无法分析", "本地模型和API都不可用，请先配置。")

    def _choose_api(self):
        # 弹出API配置对话框
        config_dialog = APIConfigDialog(self)
        if config_dialog.exec() == QDialog.DialogCode.Accepted:
            # 配置成功后检测API配置
            if self.api_config_check and self.api_config_check():
                self.selected = 'api'
                self.accept()
            else:
                QMessageBox.warning(self, "配置失败", "API配置无效，请重新配置。")
                self.selected = None  # 添加这行，确保配置失败时重置selected
        else:
            # 用户取消配置
            self.selected = None  # 添加这行，确保用户取消时重置selected


class APIConfigDialog(QDialog):
    """API配置对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API 配置")
        self.setFixedSize(500, 320)

        layout = QVBoxLayout(self)

        # 标题，DeepSeek为可点击链接
        title = QLabel('API配置（推荐使用<a href="https://platform.deepseek.com/" style="color:#1a73e8;">DeepSeek</a>）')
        title.setFont(QFont("微软雅黑", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setOpenExternalLinks(True)
        layout.addWidget(title)

        # 表单布局
        form_layout = QFormLayout()

        # API密钥输入框
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)  # 密码模式
        form_layout.addRow("API密钥:", self.api_key_input)

        # API端点输入框
        self.api_endpoint_input = QLineEdit()
        self.api_endpoint_input.setPlaceholderText("例如: https://api.deepseek.com/v1/chat/completions")
        form_layout.addRow("API端点:", self.api_endpoint_input)

        # 模型名称输入框
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("例如: deepseek-chat")
        self.model_input.setText("deepseek-chat")  # 默认值
        form_layout.addRow("模型名称:", self.model_input)

        layout.addLayout(form_layout)

        # 说明文本
        help_text = QLabel("请填写API的配置信息。 API密钥、端点和，模型名称是必填项。\n"
                           "deepseek-chat为DeepSeek-V3-0324，"
                           "deepseek-reasoner为DeepSeek-R1-0528。")
        help_text.setWordWrap(True)
        layout.addWidget(help_text)

        # 按钮布局
        button_layout = QHBoxLayout()

        # 保存按钮
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save_config)
        button_layout.addWidget(save_btn)

        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # 加载现有配置
        self._load_existing_config()

    def _load_existing_config(self):
        """加载现有配置"""
        try:
            config_path = Path("data/config/api_config.json")
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                self.api_key_input.setText(config.get("api_key", ""))
                self.api_endpoint_input.setText(config.get("api_endpoint", ""))
                self.model_input.setText(config.get("model", "deepseek-chat"))
        except Exception as e:
            logging.error(f"加载API配置失败: {e}")

    def _save_config(self):
        """保存配置"""
        api_key = self.api_key_input.text().strip()
        api_endpoint = self.api_endpoint_input.text().strip()
        model = self.model_input.text().strip()

        if not api_key or not api_endpoint:
            QMessageBox.warning(self, "配置错误", "API密钥和端点是必填项！")
            return

        try:
            # 确保配置目录存在
            config_dir = Path("data/config")
            config_dir.mkdir(parents=True, exist_ok=True)

            # 保存配置
            config = {
                "api_key": api_key,
                "api_endpoint": api_endpoint,
                "model": model
            }

            with open(config_dir / "api_config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            QMessageBox.information(self, "保存成功", "API配置已保存！")
            self.accept()

        except Exception as e:
            logging.error(f"保存API配置失败: {e}")
            QMessageBox.critical(self, "保存失败", f"保存配置时发生错误：{str(e)}")


class AIExplanationWorker(QThread):
    """AI 解释工作线程"""
    explanation_ready = pyqtSignal(str)

    def __init__(self, parent, question_text, options, correct_answer, user_answer, get_explanation_func):
        super().__init__(parent)
        self.question_text = question_text
        self.options = options
        self.correct_answer = correct_answer
        self.user_answer = user_answer
        self.get_explanation_func = get_explanation_func

        # 记录传入的参数
        logging.debug(f"AI解释工作线程初始化参数:")
        logging.debug(f"问题文本: {question_text}")
        logging.debug(f"选项: {options}")
        logging.debug(f"正确答案: {correct_answer}")
        logging.debug(f"用户答案: {user_answer}")

    def run(self):
        try:
            explanation = self.get_explanation_func(
                self.question_text, self.options, self.correct_answer, self.user_answer
            )
            logging.debug(f"AI生成的解释: {explanation}")
            self.explanation_ready.emit(explanation)
        except Exception as e:
            logging.error(f"AI解释生成失败: {str(e)}")
            self.explanation_ready.emit(f"生成解释时发生错误: {str(e)}")


class AIExplanationDialog(QDialog):
    """AI 解答对话框"""

    def __init__(self, parent, question, user_answer):
        super().__init__(parent)
        self.model_type = None
        self._cancelled = False  # 统一初始化所有实例变量
        # 优先读取用户偏好
        pref = get_model_preference()

        def local_model_check():
            model_path = Path(self._get_model_path())
            return model_path.exists() and any(model_path.iterdir())

        def api_config_check():
            api_config_path = Path("data/config/api_config.json")
            if not api_config_path.exists():
                return False
            try:
                with open(api_config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                return bool(config.get("api_key")) and bool(config.get("api_endpoint"))
            except Exception:
                return False

        # 自动优先选择
        if pref == "local" and local_model_check():
            self.model_type = "local"
        elif pref == "api" and api_config_check():
            self.model_type = "api"
        elif local_model_check():
            self.model_type = "local"
        elif api_config_check():
            self.model_type = "api"
        else:
            # 都不可用才弹出选择
            if not self._show_model_select():
                self._cancelled = True
                self.close()
                return

        # 记录并显示传入的数据
        logging.debug("\n" + "=" * 50)
        logging.debug("传入的原始数据:")
        logging.debug(f"题目: {question.get('题目', '')}")
        logging.debug(f"{question.get('选项A', '')}")
        logging.debug(f"选项B: {question.get('选项B', '')}")
        logging.debug(f"选项C: {question.get('选项C', '')}")
        logging.debug(f"选项D: {question.get('选项D', '')}")
        logging.debug(f"正确答案: {question.get('答案', '')}")
        logging.debug(f"用户答案: {user_answer}")
        logging.debug("=" * 50)
        self.init_ui()
        # 只保留题库自带选项内容
        data_text = f"""传入的数据:\n题目: {question.get('题目', '')}\n\n选项:\n{question.get('选项A', '')}\n{question.get('选项B', '')}\n{question.get('选项C', '')}\n{question.get('选项D', '')}\n\n正确答案: {question.get('答案', '')}\n用户答案: {user_answer}\n\n请确认数据是否正确，然后点击\"开始分析\"按钮。"""
        self.explanation_text.setText(data_text)
        self.start_btn = QPushButton("开始分析")
        self.start_btn.clicked.connect(lambda: self._start_analysis(question, user_answer))
        self.layout().addWidget(self.start_btn)
        # 设置按钮
        self.settings_btn = QPushButton("设置")
        self.settings_btn.clicked.connect(self._show_settings_dialog)
        self.layout().addWidget(self.settings_btn)

    def _show_model_select(self):
        # 移除重复的函数定义，直接使用__init__方法中定义的函数
        dlg = ModelSelectDialog(self, self.local_model_check, self.api_config_check)
        while True:
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return False
            if dlg.selected == 'local':
                self.model_type = 'local'
                return True
            elif dlg.selected == 'api':
                self.model_type = 'api'
                return True
            elif dlg.selected == 'api_config':
                config_dlg = APIConfigDialog(self)
                config_dlg.exec()
                # 回到模型选择
            else:
                return False

    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("AI 解答")
        self.setFixedSize(600, 450)  # 固定大小，确保有足够空间

        layout = QVBoxLayout(self)

        # 标题标签
        title_label = QLabel("AI 解答")
        title_label.setFont(QFont("微软雅黑", 14, QFont.Weight.Bold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # AI 解释文本区域
        self.explanation_text = QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setFont(QFont("微软雅黑", 11))

        # 将 QTextEdit 放入 QScrollArea 以支持滚动
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.explanation_text)
        layout.addWidget(scroll_area)

    def _start_analysis(self, question, user_answer):
        # 直接用 self.model_type
        if not hasattr(self, 'model_type') or self.model_type not in ('local', 'api'):
            QMessageBox.warning(self, "未选择模型", "请先选择模型。")
            return

        # 保存数据
        self.question = question
        self.user_answer = user_answer

        # 禁用开始按钮
        self.start_btn.setEnabled(False)

        # 显示正在分析提示
        self.explanation_text.setText("正在分析，请稍候...")

        # 根据选择加载模型
        if self.model_type == "local":
            self._load_local_model()
        elif self.model_type == "api":
            self._load_api_model()

    def _load_local_model(self):
        """加载本地模型"""
        self.ai_model = None
        self.ai_tokenizer = None

        if self._load_ai_model():
            self._start_explanation()
        else:
            self.explanation_text.setText("本地模型加载失败，请检查模型文件是否存在。")
            self.start_btn.setEnabled(True)

    def _load_api_model(self):
        """加载API模型"""
        try:
            # 检查API配置文件
            api_config_path = Path("data/config/api_config.json")
            if not api_config_path.exists():
                # 显示API配置对话框
                config_dialog = APIConfigDialog(self)
                if config_dialog.exec() != QDialog.DialogCode.Accepted:
                    self.explanation_text.setText("已取消API配置。")
                    self.start_btn.setEnabled(True)
                    return

            # 重新检查配置文件
            if not api_config_path.exists():
                self.explanation_text.setText("API配置文件不存在，请先配置API。")
                self.start_btn.setEnabled(True)
                return

            with open(api_config_path, "r", encoding="utf-8") as f:
                api_config = json.load(f)

            if not api_config.get("api_key") or not api_config.get("api_endpoint"):
                self.explanation_text.setText("API配置不完整，请先配置API密钥和端点。")
                self.start_btn.setEnabled(True)
                return

            # 保存API配置
            self.api_config = api_config
            self._start_explanation()

        except Exception as e:
            logging.error(f"加载API配置失败: {e}")
            self.explanation_text.setText(f"加载API配置失败: {str(e)}")
            self.start_btn.setEnabled(True)

    def _load_ai_model(self):
        """加载 AI 模型"""
        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            model_path = Path("data/models/ai_model")
            if not model_path.exists():
                logging.error(f"模型路径不存在: {model_path}")
                return False
            self.ai_tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                low_cpu_mem_usage=True
            )
            self.ai_model = AutoModelForCausalLM.from_pretrained(
                str(model_path),
                low_cpu_mem_usage=True
            )
            return True
        except Exception as e:
            logging.error(f"加载本地 AI 模型失败: {e}")
            self.ai_model = None
            self.ai_tokenizer = None
            return False

    def _start_explanation(self):
        """开始生成解释"""
        # 获取当前题目信息
        question_text = self.question['题目']
        options = {
            'A': self.question.get('选项A', ''),
            'B': self.question.get('选项B', ''),
            'C': self.question.get('选项C', ''),
            'D': self.question.get('选项D', '')
        }
        correct_answer = str(self.question['答案']).strip()

        # 记录处理后的数据
        logging.debug("\n" + "=" * 50)
        logging.debug("开始生成解释:")
        logging.debug(f"问题文本: {question_text}")
        logging.debug(f"选项数据: {json.dumps(options, ensure_ascii=False, indent=2)}")
        logging.debug(f"正确答案: {correct_answer}")
        logging.debug(f"用户答案: {self.user_answer}")
        logging.debug("=" * 50)

        # 启动工作线程
        self.worker = AIExplanationWorker(
            self,
            question_text, options, correct_answer, self.user_answer,
            self._get_ai_explanation
        )
        self.worker.explanation_ready.connect(self._update_explanation)
        self.worker.start()

    def _get_ai_explanation(self, question_text, options, correct_answer, user_answer):
        """获取 AI 解释"""
        try:
            # 读取提示词模板
            prompt_path = Path("data/prompt.txt")
            if not prompt_path.exists():
                logging.error("提示词模板文件不存在")
                return "提示词模板文件不存在，请检查配置。"

            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_template = f.read()

            # 构建提示词
            prompt = prompt_template.format(
                question=question_text,
                option_a=options.get('A', ''),
                option_b=options.get('B', ''),
                option_c=options.get('C', ''),
                option_d=options.get('D', ''),
                correct_answer=correct_answer,
                user_answer=user_answer
            )

            logging.debug(f"提示词: {prompt}")

            # 根据模型类型生成解释 - 修改条件判断逻辑
            if self.model_type == "api":
                return self._get_ai_explanation_from_api(question_text, options, correct_answer, user_answer)
            else:
                return self._get_local_explanation(prompt)

        except Exception as e:
            logging.error(f"AI生成解释失败: {e}")
            return f"AI 生成解释失败：{str(e)}"

    def _get_local_explanation(self, prompt):
        """使用本地模型生成解释"""
        try:
            # 使用 pipeline 进行文本生成
            generator = pipeline(
                "text-generation",
                model=self.ai_model,
                tokenizer=self.ai_tokenizer,
                max_new_tokens=1024,
                do_sample=True,
                top_k=50,
                top_p=0.95,
                temperature=0.7
            )

            # 调用 generator 并获取结果
            result = generator(
                prompt,
                clean_up_tokenization_spaces=True,
                return_full_text=False,
                num_return_sequences=1
            )

            logging.debug(f"本地模型生成结果: {json.dumps(result, ensure_ascii=False, indent=2)}")

            if result and len(result) > 0 and 'generated_text' in result[0]:
                explanation = result[0]['generated_text'].strip()
                if explanation.startswith(prompt):
                    explanation = explanation[len(prompt):].strip()

                # 添加免责声明
                disclaimer = "本回答由本地AI模型生成，内容仅供参考，请仔细甄别。\n\n"
                final_explanation = disclaimer + explanation
                logging.debug(f"最终解释文本: {final_explanation}")
                return final_explanation
            else:
                logging.warning("本地模型未能生成有效解释")
                return "AI 未能生成有效的解释，请稍后再试。"

        except Exception as e:
            logging.error(f"本地模型生成解释失败: {e}")
            return f"本地模型生成解释失败：{str(e)}"

    def _get_ai_explanation_from_api(self, question_text, options, correct_answer, user_answer):
        try:
            headers = {
                "Authorization": f"Bearer {self.api_config['api_key']}",
                "Content-Type": "application/json"
            }
            base_prompt = f"""请分析以下题目并给出详细解释：\n\n题目：{question_text}\n\n选项：\n{options.get('A', '')}\n{options.get('B', '')}\n{options.get('C', '')}\n{options.get('D', '')}\n\n正确答案：{correct_answer}\n用户答案：{user_answer}\n\n请从以下几个方面给出详细解释：\n1. 每个选项的含义\n2. 正确答案的推理过程\n3. 解题思路和方法\n4. 如果用户答错了，分析错误原因"""
            messages = [
                {"role": "system", "content": "你是一个专业的题目解析助手，请详细分析题目并给出解释。"},
                {"role": "user", "content": base_prompt}
            ]
            all_content = ""
            max_loops = 5  # 最多自动续写5次，防止死循环
            for _ in range(max_loops):
                data = {
                    "model": self.api_config["model"],
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 8192
                }
                response = requests.post(
                    self.api_config["api_endpoint"],
                    headers=headers,
                    json=data,
                    timeout=120
                )
                response.raise_for_status()
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    all_content += content
                    finish_reason = result["choices"][0].get("finish_reason", "")
                    if finish_reason == "length":
                        # 继续补充
                        messages.append({"role": "assistant", "content": content})
                        messages.append({"role": "user", "content": "请继续补充上文，直到完整结束。"})
                        continue
                    else:
                        break
                else:
                    raise Exception("API响应格式错误")
            else:
                all_content += "\n\n【注意：内容可能已被API截断，如需更完整内容请缩短题目或分段提问】"
            return all_content
        except Exception as e:
            logging.error(f"处理API响应失败: {e}")
            raise Exception(f"处理API响应失败: {str(e)}")

    def _update_explanation(self, explanation):
        """更新解释文本"""
        logging.debug(f"更新UI显示的解释文本: {explanation}")
        self.explanation_text.setText(explanation)

    def _show_settings_dialog(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            settings = dlg.get_settings()
            set_model_preference(settings["preference"])
            # 保存本地模型路径
            config_path = Path("data/config/model_preference.json")
            config = {"preference": settings["preference"], "model_path": settings["model_path"]}
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            QMessageBox.information(self, "设置已保存", "设置已保存，重新打开AI解答将生效。")

    def _get_model_path(self):
        # 读取本地模型路径配置
        config_path = Path("data/config/model_preference.json")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            return config.get("model_path", "data/models/ai_model")
        return "data/models/ai_model"


class ModelPreferenceDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("默认模型设置")
        self.setFixedSize(300, 150)
        layout = QVBoxLayout(self)
        self.local_radio = QRadioButton("本地模型优先")
        self.api_radio = QRadioButton("API优先")
        pref = get_model_preference()
        if pref == "local":
            self.local_radio.setChecked(True)
        else:
            self.api_radio.setChecked(True)
        layout.addWidget(self.local_radio)
        layout.addWidget(self.api_radio)
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_preference(self):
        return "local" if self.local_radio.isChecked() else "api"


class SettingsDialog(QDialog):
    """AI解答设置界面：选择本地模型路径、编辑API配置、设置默认优先模型"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI解答设置")
        self.setFixedSize(420, 320)
        layout = QVBoxLayout(self)

        # 默认优先模型选择
        pref_label = QLabel("默认优先模型：")
        pref_label.setFont(QFont("微软雅黑", 11, QFont.Weight.Bold))
        layout.addWidget(pref_label)
        self.local_radio = QRadioButton("本地模型优先")
        self.api_radio = QRadioButton("API优先")
        pref = get_model_preference()
        if pref == "local":
            self.local_radio.setChecked(True)
        else:
            self.api_radio.setChecked(True)
        layout.addWidget(self.local_radio)
        layout.addWidget(self.api_radio)

        # 本地模型路径选择
        model_path_label = QLabel("本地模型路径：")
        model_path_label.setFont(QFont("微软雅黑", 11))
        layout.addWidget(model_path_label)
        self.model_path_edit = QLineEdit()
        self.model_path_edit.setText(str(Path("data/models/ai_model")))
        layout.addWidget(self.model_path_edit)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_model_path)
        layout.addWidget(browse_btn)

        # API配置编辑
        api_btn = QPushButton("编辑API配置")
        api_btn.clicked.connect(self._edit_api_config)
        layout.addWidget(api_btn)

        # 按钮
        btn_layout = QHBoxLayout()
        ok_btn = QPushButton("确定")
        cancel_btn = QPushButton("取消")
        ok_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(ok_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def _browse_model_path(self):
        from PyQt6.QtWidgets import QFileDialog
        path = QFileDialog.getExistingDirectory(self, "选择本地模型目录", self.model_path_edit.text())
        if path:
            self.model_path_edit.setText(path)

    def _edit_api_config(self):
        dlg = APIConfigDialog(self)
        dlg.exec()

    def get_settings(self):
        return {
            "preference": "local" if self.local_radio.isChecked() else "api",
            "model_path": self.model_path_edit.text().strip()
        }

# 在AI解答按钮点击时调用AIExplanationDialog().start_analysis()即可
