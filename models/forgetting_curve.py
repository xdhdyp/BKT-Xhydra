import numpy as np
from datetime import datetime, timedelta
import json

class ForgettingCurve:
    """艾宾浩斯遗忘曲线模型"""
    
    def __init__(self):
        # 遗忘曲线参数
        self.decay_rate = 0.1  # 遗忘速率
        self.review_intervals = [1, 2, 4, 7, 15, 30]  # 复习间隔（天）
        
    def calculate_memory_strength(self, last_review_time, review_count):
        """计算记忆强度"""
        if not last_review_time:
            return 0.0
            
        # 计算距离上次复习的天数
        days_passed = (datetime.now() - last_review_time).days
        
        # 基础记忆强度
        base_strength = np.exp(-self.decay_rate * days_passed)
        
        # 考虑复习次数的影响
        review_factor = 1 - np.exp(-review_count * 0.5)
        
        # 综合记忆强度 (0-1之间)
        memory_strength = base_strength * (0.7 + 0.3 * review_factor)
        
        return float(memory_strength)
        
    def get_next_review_time(self, review_count):
        """获取下次复习时间"""
        if review_count >= len(self.review_intervals):
            # 如果超过预设的复习次数，使用最后一个间隔
            interval = self.review_intervals[-1]
        else:
            interval = self.review_intervals[review_count]
            
        return datetime.now() + timedelta(days=interval)
        
    def update_review_history(self, question_id, is_correct, review_history):
        """更新复习历史"""
        if question_id not in review_history:
            review_history[question_id] = {
                'review_count': 0,
                'last_review_time': None,
                'next_review_time': None,
                'memory_strength': 0.0,
                'correct_count': 0,
                'total_count': 0
            }
            
        history = review_history[question_id]
        
        # 更新复习次数和正确率
        history['review_count'] += 1
        history['total_count'] += 1
        if is_correct:
            history['correct_count'] += 1
            
        # 更新复习时间
        history['last_review_time'] = datetime.now().isoformat()
        history['next_review_time'] = self.get_next_review_time(
            history['review_count']
        ).isoformat()
        
        # 更新记忆强度
        history['memory_strength'] = self.calculate_memory_strength(
            datetime.fromisoformat(history['last_review_time']),
            history['review_count']
        )
        
        return review_history
        
    def save_review_history(self, review_history, output_path):
        """保存复习历史"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'review_history': review_history,
                    'timestamp': datetime.now().isoformat(),
                    'model_params': {
                        'decay_rate': self.decay_rate,
                        'review_intervals': self.review_intervals
                    }
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存复习历史失败: {str(e)}")
            return False
            
    def load_review_history(self, json_path):
        """加载复习历史"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('review_history', {})
        except Exception as e:
            print(f"加载复习历史失败: {str(e)}")
            return {} 