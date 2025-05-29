import os
import json
import pandas as pd
from .bkt_model import BKTModel
from .forgetting_curve import ForgettingCurve
from .question_processor import QuestionProcessor
import random

class Recommender:
    """智能推荐系统"""
    
    def __init__(self):
        self.bkt_model = BKTModel()
        self.forgetting_curve = ForgettingCurve()
        self.question_processor = QuestionProcessor()
        
    def process_answer_history(self, answer_json_path):
        """处理答题历史"""
        try:
            # 加载答题历史
            with open(answer_json_path, 'r', encoding='utf-8') as f:
                answer_data = json.load(f)
                
            # 转换答题记录格式
            answer_history = {}
            for q_id, answer in answer_data['answers'].items():
                if q_id not in answer_history:
                    answer_history[q_id] = []
                    
                # 判断答案是否正确
                is_correct = answer == answer_data.get('correct_answers', {}).get(q_id)
                
                answer_history[q_id].append({
                    'answer': answer,
                    'is_correct': is_correct,
                    'timestamp': answer_data['timestamp']
                })
                
            return answer_history
        except Exception as e:
            print(f"处理答题历史失败: {str(e)}")
            return None
            
    def update_models(self, answer_history):
        """更新模型"""
        # 更新BKT模型
        mastery = self.bkt_model.calculate_mastery(answer_history)
        self.bkt_model.update_question_difficulty(answer_history)
        
        # 更新遗忘曲线
        review_history = self.forgetting_curve.load_review_history(
            os.path.join(self.data_dir, 'models', 'review_history.json')
        )
        
        for q_id, answers in answer_history.items():
            for answer in answers:
                review_history = self.forgetting_curve.update_review_history(
                    q_id,
                    answer['is_correct'],
                    review_history
                )
                
        # 保存更新后的复习历史
        self.forgetting_curve.save_review_history(
            review_history,
            os.path.join(self.data_dir, 'models', 'review_history.json')
        )
        
        return mastery, review_history
        
    def generate_recommendation(self, xlsx_path, answer_json_paths, num_questions=50):
        # 1. 读取题库
        df = pd.read_excel(xlsx_path)
        correct_answers = {str(i): str(row['答案']).strip().upper() for i, row in df.iterrows()}
        total_questions = len(df)

        # 2. 合并所有答题记录
        user_history = {}
        for json_path in answer_json_paths:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for idx_str, user_ans in data.get('user_answers', {}).items():
                idx = int(idx_str)
                if idx not in user_history:
                    user_history[idx] = {'wrong_count': 0, 'view_answer_count': 0, 'total_time': 0.0}
                if str(user_ans).strip().upper() != correct_answers.get(idx_str, ''):
                    user_history[idx]['wrong_count'] += 1
                # 可统计view_answer_count、total_time等

        # 3. 推荐逻辑（错题优先，未做题次之，已掌握题目偶尔出现）
        all_questions = list(range(total_questions))
        new_questions = [i for i in all_questions if i not in user_history]
        old_questions = [i for i in all_questions if i in user_history]
        old_questions_sorted = sorted(
            old_questions,
            key=lambda i: (
                -user_history[i]['wrong_count'],
                -user_history[i]['view_answer_count'],
                -user_history[i]['total_time']
            )
        )
        num_new = int(num_questions * 0.6)
        num_old = num_questions - num_new
        selected_new = random.sample(new_questions, min(num_new, len(new_questions)))
        selected_old = old_questions_sorted[:num_old]
        question_order = selected_new + selected_old
        random.shuffle(question_order)
        # 补足题目
        if len(question_order) < num_questions:
            supplement = [i for i in old_questions_sorted if i not in question_order]
            question_order += supplement[:num_questions - len(question_order)]
        if len(question_order) < num_questions:
            supplement = [i for i in new_questions if i not in question_order]
            question_order += supplement[:num_questions - len(question_order)]
        question_order = question_order[:num_questions]
        return question_order

    def get_recommendation_summary(self, recommendation_path):
        """获取推荐结果摘要"""
        try:
            with open(recommendation_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            return {
                'recommendation_count': len(data['recommendation']),
                'timestamp': data['timestamp'],
                'model_info': data.get('model_info', {})
            }
        except Exception as e:
            print(f"获取推荐摘要失败: {str(e)}")
            return None

def load_user_history(history_path):
    """加载用户历史答题数据，返回字典：{题目索引: {'wrong_count': int, 'view_answer_count': int, 'total_time': float}}"""
    if not os.path.exists(history_path):
        return {}
    with open(history_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # 假设history.json结构为 {"answers": {题号: {...}}, ...}
    answers = data.get('answers', {})
    history = {}
    for k, v in answers.items():
        idx = int(k)
        history[idx] = {
            'wrong_count': v.get('wrong_count', 0),
            'view_answer_count': v.get('view_answer_count', 0),
            'total_time': v.get('total_time', 0.0)
        }
    return history

def generate_recommendation(total_questions=740, num_questions=50, new_ratio=0.6, history_path='user_history.json', output_path='project/models/recommendation.json'):
    all_questions = list(range(total_questions))
    user_history = load_user_history(history_path)
    new_questions = [i for i in all_questions if i not in user_history]
    old_questions = [i for i in all_questions if i in user_history]
    old_questions_sorted = sorted(
        old_questions,
        key=lambda i: (
            -user_history[i]['wrong_count'],
            -user_history[i]['view_answer_count'],
            -user_history[i]['total_time']
        )
    )
    num_new = int(num_questions * new_ratio)
    num_old = num_questions - num_new
    selected_new = random.sample(new_questions, min(num_new, len(new_questions)))
    selected_old = old_questions_sorted[:num_old]
    question_order = selected_new + selected_old
    random.shuffle(question_order)
    # 补足题目
    if len(question_order) < num_questions:
        supplement = [i for i in old_questions_sorted if i not in question_order]
        question_order += supplement[:num_questions - len(question_order)]
    if len(question_order) < num_questions:
        supplement = [i for i in new_questions if i not in question_order]
        question_order += supplement[:num_questions - len(question_order)]
    question_order = question_order[:num_questions]
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({'question_order': question_order}, f, ensure_ascii=False, indent=2)
    print(f'已生成推荐顺序，写入{output_path}')

if __name__ == '__main__':
    # 示例用法
    xlsx_path = 'data/static/单选题.xlsx'
    answer_dir = 'data/answers'
    answer_json_paths = [os.path.join(answer_dir, f) for f in os.listdir(answer_dir) if f.endswith('.json') and f.startswith('answer_')]
    recommender = Recommender()
    question_order = recommender.generate_recommendation(xlsx_path, answer_json_paths, num_questions=50)
    print('推荐题目顺序:', question_order) 