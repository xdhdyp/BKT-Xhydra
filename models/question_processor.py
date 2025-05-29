import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import json
from datetime import datetime
import os
from pathlib import Path
import logging

class QuestionProcessor:
    """题目处理器"""
    
    def __init__(self, username):
        self.username = username
        self.question_stats_file = Path("data/models/question_stats.json")
        self.recommendation_file = Path("data/models/model_yh/recommendation.json")
        self.history_dir = Path("data/recommendation/history")
        self.static_dir = Path("data/static")
        self.question_stats = self._load_question_stats()
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None
        )
        self.cluster_model = KMeans(n_clusters=10)
        self.question_clusters = {}
        self.question_features = {}
        
    def _load_question_stats(self):
        """加载题目统计信息"""
        if self.question_stats_file.exists():
            try:
                with open(self.question_stats_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"加载题目统计信息失败: {e}")
                return {}
        return {}
    
    def _save_question_stats(self):
        """保存题目统计信息"""
        try:
            os.makedirs(self.question_stats_file.parent, exist_ok=True)
            with open(self.question_stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.question_stats, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存题目统计信息失败: {e}")
    
    def _save_recommendation(self, recommendation):
        """保存推荐信息"""
        try:
            os.makedirs(self.recommendation_file.parent, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            recommendation_file = self.recommendation_file.parent / f"recommendation_{timestamp}.json"
            with open(recommendation_file, 'w', encoding='utf-8') as f:
                json.dump(recommendation, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存推荐信息失败: {e}")
    
    def _load_question_bank(self):
        """加载题库"""
        try:
            excel_file = self.static_dir / "单选题.xlsx"
            if not excel_file.exists():
                raise FileNotFoundError("题库文件不存在")
            df = pd.read_excel(excel_file)
            return df.to_dict('records')
        except Exception as e:
            logging.error(f"加载题库失败: {e}")
            return []
    
    def process_answer_file(self, answer_file):
        """处理答题记录文件"""
        try:
            with open(answer_file, 'r', encoding='utf-8') as f:
                answer_data = json.load(f)
            
            # 获取原始题目索引和答案
            original_indices = answer_data.get('original_indices', [])
            user_answers = answer_data.get('answers', {})
            
            # 加载题库
            questions = self._load_question_bank()
            if not questions:
                return
            
            # 更新题目统计信息
            for idx_str, user_ans in user_answers.items():
                idx = int(idx_str)
                if idx < len(original_indices):
                    real_idx = original_indices[idx]
                    correct_ans = str(questions[real_idx]['答案']).strip().upper()
                    user_ans = str(user_ans).strip().upper()
                    
                    # 更新统计信息
                    if str(real_idx) not in self.question_stats:
                        self.question_stats[str(real_idx)] = {
                            'correct': 0,
                            'wrong': 0,
                            'total': 0
                        }
                    
                    self.question_stats[str(real_idx)]['total'] += 1
                    if user_ans == correct_ans:
                        self.question_stats[str(real_idx)]['correct'] += 1
                    else:
                        self.question_stats[str(real_idx)]['wrong'] += 1
            
            # 保存统计信息
            self._save_question_stats()
            
            # 生成推荐
            self._generate_recommendation()
            
        except Exception as e:
            logging.error(f"处理答题记录失败: {e}")
    
    def _generate_recommendation(self):
        """生成题目推荐"""
        try:
            # 加载题库
            questions = self._load_question_bank()
            if not questions:
                return
            
            # 计算每个题目的错误率
            question_weights = {}
            for idx, question in enumerate(questions):
                stats = self.question_stats.get(str(idx), {'correct': 0, 'wrong': 0, 'total': 0})
                if stats['total'] == 0:
                    # 未做过的题目优先
                    question_weights[idx] = 1.0
                else:
                    # 错误率高的题目优先
                    error_rate = stats['wrong'] / stats['total']
                    question_weights[idx] = error_rate
            
            # 按权重排序
            sorted_questions = sorted(question_weights.items(), key=lambda x: x[1], reverse=True)
            
            # 生成推荐
            recommendation = {
                'timestamp': datetime.now().isoformat(),
                'username': self.username,
                'question_weights': {str(idx): weight for idx, weight in sorted_questions},
                'recommended_questions': [idx for idx, _ in sorted_questions[:50]]  # 只推荐50题
            }
            
            # 保存推荐
            self._save_recommendation(recommendation)
            
        except Exception as e:
            logging.error(f"生成推荐失败: {e}")
    
    def process_all_history(self):
        """处理所有历史记录"""
        try:
            # 获取用户的所有历史记录
            history_files = sorted(
                self.history_dir.glob(f"answers_{self.username}_*.json"),
                key=lambda x: x.stat().st_mtime
            )
            
            # 处理每个历史记录
            for file in history_files:
                self.process_answer_file(file)
                
        except Exception as e:
            logging.error(f"处理历史记录失败: {e}")
        
    def load_questions(self, excel_path):
        """加载题目数据"""
        try:
            df = pd.read_excel(excel_path)
            return df
        except Exception as e:
            print(f"加载题目失败: {str(e)}")
            return None
            
    def preprocess_questions(self, questions_df):
        """预处理题目数据"""
        # 合并题目和选项文本
        questions_df['text'] = questions_df.apply(
            lambda row: f"{row['题目']} {row['选项A']} {row['选项B']} {row['选项C']} {row['选项D']}",
            axis=1
        )
        
        # 提取文本特征
        text_features = self.vectorizer.fit_transform(questions_df['text'])
        
        # 保存特征
        self.question_features = {
            str(i): features.toarray()[0].tolist()
            for i, features in enumerate(text_features)
        }
        
        return text_features
        
    def cluster_questions(self, text_features):
        """对题目进行聚类"""
        # 使用K-means聚类
        clusters = self.cluster_model.fit_predict(text_features)
        
        # 保存聚类结果
        self.question_clusters = {
            str(i): int(cluster)
            for i, cluster in enumerate(clusters)
        }
        
        return clusters
        
    def calculate_similarity(self, q1_id, q2_id):
        """计算题目相似度"""
        if q1_id not in self.question_features or q2_id not in self.question_features:
            return 0.0
            
        # 计算余弦相似度
        features1 = np.array(self.question_features[q1_id])
        features2 = np.array(self.question_features[q2_id])
        
        similarity = np.dot(features1, features2) / (
            np.linalg.norm(features1) * np.linalg.norm(features2)
        )
        
        return float(similarity)
        
    def get_similar_questions(self, question_id, top_k=5):
        """获取相似题目"""
        if question_id not in self.question_features:
            return []
            
        # 计算与所有题目的相似度
        similarities = []
        for q_id, features in self.question_features.items():
            if q_id != question_id:
                similarity = self.calculate_similarity(question_id, q_id)
                similarities.append((q_id, similarity))
                
        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return [q_id for q_id, _ in similarities[:top_k]]
        
    def generate_recommendation(self, answer_history, review_history, num_questions=50):
        """生成个性化题目推荐"""
        # 获取错题ID列表
        wrong_questions = [
            q_id for q_id, answers in answer_history.items()
            if any(not ans['is_correct'] for ans in answers)
        ]
        
        # 获取需要复习的题目
        review_questions = [
            q_id for q_id, history in review_history.items()
            if datetime.fromisoformat(history['next_review_time']) <= datetime.now()
        ]
        
        # 获取相似题目
        similar_questions = []
        for q_id in wrong_questions:
            similar_questions.extend(self.get_similar_questions(q_id))
            
        # 合并所有推荐题目
        recommended_questions = list(set(
            wrong_questions + review_questions + similar_questions
        ))
        
        # 如果推荐题目不足，添加聚类中的其他题目
        if len(recommended_questions) < num_questions:
            cluster_questions = []
            for q_id in recommended_questions:
                cluster = self.question_clusters.get(q_id)
                if cluster is not None:
                    # 获取同簇的其他题目
                    cluster_questions.extend([
                        q for q, c in self.question_clusters.items()
                        if c == cluster and q not in recommended_questions
                    ])
                    
            # 添加同簇题目直到达到目标数量
            recommended_questions.extend(
                cluster_questions[:num_questions - len(recommended_questions)]
            )
            
        return recommended_questions[:num_questions]
        
    def save_recommendation(self, recommendation, output_path):
        """保存推荐结果"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'recommendation': recommendation,
                    'timestamp': datetime.now().isoformat(),
                    'model_info': {
                        'n_clusters': self.cluster_model.n_clusters,
                        'feature_dim': len(next(iter(self.question_features.values())))
                    }
                }, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存推荐结果失败: {str(e)}")
            return False 