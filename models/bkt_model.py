from datetime import datetime
import json


class BKTModel:
    """贝叶斯知识追踪模型"""
    
    def __init__(self):
        # 模型参数
        self.p_L0 = 0.1  # 初始掌握概率
        self.p_T = 0.3   # 学习概率
        self.p_G = 0.1   # 猜测概率
        self.p_S = 0.1   # 失误概率
        
        # 题目难度参数
        self.question_difficulty = {}
        
    def load_answer_history(self, json_path):
        """加载答题历史数据"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except Exception as e:
            print(f"加载答题历史失败: {str(e)}")
            return None
            
    def calculate_mastery(self, answer_history):
        """计算题目掌握度"""
        mastery = {}
        
        for q_id, answers in answer_history.items():
            if not answers:  # 跳过没有答题记录的题目
                continue
                
            # 计算该题目的掌握度
            correct_count = sum(1 for ans in answers if ans['is_correct'])
            total_count = len(answers)
            
            # 使用BKT模型计算掌握概率
            p_mastery = self.p_L0
            for ans in answers:
                if ans['is_correct']:
                    p_mastery = (p_mastery * (1 - self.p_S)) / (
                        p_mastery * (1 - self.p_S) + (1 - p_mastery) * self.p_G
                    )
                else:
                    p_mastery = (p_mastery * self.p_S) / (
                        p_mastery * self.p_S + (1 - p_mastery) * (1 - self.p_G)
                    )
                p_mastery += (1 - p_mastery) * self.p_T
                
            mastery[q_id] = {
                'mastery_probability': float(p_mastery),
                'correct_rate': correct_count / total_count,
                'attempt_count': total_count
            }
            
        return mastery
        
    def update_question_difficulty(self, answer_history):
        """更新题目难度参数"""
        for q_id, answers in answer_history.items():
            if not answers:
                continue
                
            correct_count = sum(1 for ans in answers if ans['is_correct'])
            total_count = len(answers)
            
            # 计算难度系数 (0-1之间，越大越难)
            difficulty = 1 - (correct_count / total_count)
            
            # 考虑答题次数的影响
            if total_count > 5:  # 答题次数足够多时才更新难度
                self.question_difficulty[q_id] = difficulty
                
    def generate_recommendation(self, mastery, num_questions=50):
        """生成题目推荐"""
        # 计算每道题目的推荐分数
        recommendation_scores = {}
        
        for q_id, mastery_data in mastery.items():
            # 基础分数：掌握度越低，推荐分数越高
            base_score = 1 - mastery_data['mastery_probability']
            
            # 考虑题目难度
            difficulty = self.question_difficulty.get(q_id, 0.5)
            difficulty_factor = 1 - abs(0.7 - difficulty)  # 偏好中等难度题目
            
            # 考虑答题次数
            attempt_factor = 1 / (1 + mastery_data['attempt_count'])
            
            # 综合评分
            recommendation_scores[q_id] = base_score * 0.5 + difficulty_factor * 0.3 + attempt_factor * 0.2
            
        # 按推荐分数排序
        sorted_questions = sorted(
            recommendation_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 返回推荐题目ID列表
        return [q_id for q_id, _ in sorted_questions[:num_questions]]
        
    def save_recommendation(self, recommendation, output_path):
        """保存推荐结果"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'recommendation': recommendation,
                    'timestamp': datetime.now().isoformat(),
                    'model_params': {
                        'p_L0': self.p_L0,
                        'p_T': self.p_T,
                        'p_G': self.p_G,
                        'p_S': self.p_S
                    }
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存推荐结果失败: {str(e)}")
            return False 