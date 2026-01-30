"""
评估器接口

支持不同 Benchmark 的评估方式（函数式、环境内置、LLM-judge、混合）
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
import json

from .types import EvaluationResult


class BaseEvaluator(ABC):
    """
    评估器抽象基类
    
    不同 Benchmark 可以有完全不同的评估逻辑
    """
    
    @abstractmethod
    def evaluate(self, **kwargs) -> EvaluationResult:
        """
        执行评估
        
        Args:
            **kwargs: 评估所需的参数（每个 Benchmark 可能不同）
        
        Returns:
            EvaluationResult: 统一的评估结果
        """
        pass


class FunctionBasedEvaluator(BaseEvaluator):
    """
    基于预定义函数的评估器
    
    适用于：TraineeBench, GAIA2
    
    特点：
    - 任务完成后，调用特定函数检查工作区文件
    - 支持复杂的逻辑判断
    """
    
    def __init__(self, evaluator_registry: Dict[str, callable]):
        """
        初始化函数式评估器
        
        Args:
            evaluator_registry: 评估函数注册表
                例如：{"top_sales_employee": evaluate_top_sales_employee}
        """
        self.registry = evaluator_registry
    
    def evaluate(
        self,
        evaluator_name: str,
        workspace_path: str,
        **eval_params
    ) -> EvaluationResult:
        """
        调用注册的评估函数
        
        Args:
            evaluator_name: 评估器名称
            workspace_path: 工作区路径
            **eval_params: 评估函数所需的额外参数
        
        Returns:
            EvaluationResult: 评估结果
        
        Example:
            >>> evaluator.evaluate(
            ...     evaluator_name="top_sales_employee",
            ...     workspace_path="./workspace",
            ...     output_path="output.json",
            ...     answer_dir="./answers",
            ...     department="Sales",
            ...     quarter=1
            ... )
        """
        if evaluator_name not in self.registry:
            available = list(self.registry.keys())
            raise ValueError(
                f"Evaluator '{evaluator_name}' not found. "
                f"Available evaluators: {available}"
            )
        
        eval_func = self.registry[evaluator_name]
        
        # 调用评估函数
        result = eval_func(
            workspace_path=workspace_path,
            **eval_params
        )
        
        # 转换为统一格式
        return EvaluationResult(
            score=result.get("total_score", 0),
            max_score=result.get("full_score", 1),
            success=result.get("total_score", 0) >= result.get("full_score", 1),
            details=result,
            feedback=result.get("notes", "")
        )


class EnvironmentBasedEvaluator(BaseEvaluator):
    """
    基于环境内置奖励的评估器
    
    适用于：AgentBench (ALFWorld, DBBench 等)
    
    特点：
    - 每一步 env.step() 都返回 reward
    - 累积 reward 作为最终得分
    - 通常有明确的成功/失败标志（done + reward）
    """
    
    def __init__(self):
        self.trajectory = []  # 记录所有 step 的结果
        self.cumulative_reward = 0.0
    
    def record_step(self, reward: float, done: bool, info: Dict = None):
        """
        记录每一步的奖励
        
        Args:
            reward: 该步的奖励
            done: 是否结束
            info: 额外信息
        """
        self.trajectory.append({
            "reward": reward,
            "done": done,
            "info": info or {}
        })
        self.cumulative_reward += reward
    
    def reset(self):
        """重置评估器状态"""
        self.trajectory = []
        self.cumulative_reward = 0.0
    
    def evaluate(self, **kwargs) -> EvaluationResult:
        """
        基于累积奖励评估
        
        Returns:
            EvaluationResult: 评估结果
        """
        # 判断是否成功（通常是最后一步的 reward 或 done 标志）
        success = False
        if self.trajectory:
            last_step = self.trajectory[-1]
            # AgentBench 通常用 reward=1 表示成功
            success = last_step.get("reward", 0) == 1
        
        return EvaluationResult(
            score=self.cumulative_reward,
            max_score=1.0,  # AgentBench 通常是 0 或 1
            success=success,
            details={
                "trajectory": self.trajectory,
                "total_steps": len(self.trajectory),
                "cumulative_reward": self.cumulative_reward
            }
        )


class LLMJudgeEvaluator(BaseEvaluator):
    """
    基于 LLM 判断的评估器
    
    适用于：GAIA2, 开放式任务
    
    特点：
    - 调用 LLM 对 Agent 的输出进行评分
    - 适用于没有标准答案的开放式任务
    """
    
    def __init__(self, judge_model: str = "gpt-4o", api_key: str = None):
        """
        初始化 LLM-judge 评估器
        
        Args:
            judge_model: 评判模型名称
            api_key: OpenAI API Key（可选）
        """
        self.judge_model = judge_model
        self.api_key = api_key
    
    def evaluate(
        self,
        agent_output: str,
        task_description: str,
        rubric: str = None,
        **kwargs
    ) -> EvaluationResult:
        """
        使用 LLM 评估 Agent 的输出
        
        Args:
            agent_output: Agent 的最终输出
            task_description: 任务描述
            rubric: 评分标准（可选）
            **kwargs: 其他参数
        
        Returns:
            EvaluationResult: 评估结果
        """
        # 构造 Prompt
        rubric_section = f"Rubric:\n{rubric}" if rubric else ""
        
        prompt = f"""You are an expert evaluator. Please evaluate the following agent's output.

Task Description:
{task_description}

Agent Output:
{agent_output}

{rubric_section}

Please provide:
1. A score from 0 to 100
2. Whether the task was successfully completed (yes/no)
3. Detailed feedback

Format your response as JSON:
{{
    "score": <number>,
    "success": <boolean>,
    "feedback": "<string>"
}}
"""
        
        try:
            # 调用 LLM
            from openai import OpenAI
            
            client = OpenAI(api_key=self.api_key) if self.api_key else OpenAI()
            
            response = client.chat.completions.create(
                model=self.judge_model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return EvaluationResult(
                score=result.get("score", 0),
                max_score=100,
                success=result.get("success", False),
                feedback=result.get("feedback", ""),
                details=result
            )
            
        except Exception as e:
            # 如果 LLM 调用失败，返回默认结果
            return EvaluationResult(
                score=0,
                max_score=100,
                success=False,
                feedback=f"LLM evaluation failed: {str(e)}",
                details={"error": str(e)}
            )


class HybridEvaluator(BaseEvaluator):
    """
    混合评估器
    
    结合多种评估方式，例如：
    - 先用函数式评估基本正确性
    - 再用 LLM 评估质量
    """
    
    def __init__(self, evaluators: List[BaseEvaluator], weights: List[float] = None):
        """
        初始化混合评估器
        
        Args:
            evaluators: 评估器列表
            weights: 权重列表（可选，默认平均）
        """
        self.evaluators = evaluators
        
        if weights:
            if len(weights) != len(evaluators):
                raise ValueError("Number of weights must match number of evaluators")
            self.weights = weights
        else:
            self.weights = [1.0 / len(evaluators)] * len(evaluators)
    
    def evaluate(self, **kwargs) -> EvaluationResult:
        """
        组合多个评估器的结果
        
        Args:
            **kwargs: 传递给所有评估器的参数
        
        Returns:
            EvaluationResult: 组合后的评估结果
        """
        results = []
        
        for evaluator in self.evaluators:
            try:
                result = evaluator.evaluate(**kwargs)
                results.append(result)
            except Exception as e:
                # 如果某个评估器失败，记录错误但继续
                print(f"Warning: Evaluator {evaluator.__class__.__name__} failed: {e}")
                results.append(EvaluationResult(
                    score=0,
                    max_score=1,
                    success=False,
                    feedback=f"Evaluator failed: {str(e)}"
                ))
        
        if not results:
            return EvaluationResult(
                score=0,
                max_score=1,
                success=False,
                feedback="All evaluators failed"
            )
        
        # 加权平均
        total_score = sum(
            r.score * w for r, w in zip(results, self.weights)
        )
        total_max = sum(
            r.max_score * w for r, w in zip(results, self.weights)
        )
        
        # 所有评估器都成功才算成功
        all_success = all(r.success for r in results)
        
        # 合并反馈
        feedback_parts = [r.feedback for r in results if r.feedback]
        combined_feedback = "\n\n".join(feedback_parts)
        
        return EvaluationResult(
            score=total_score,
            max_score=total_max,
            success=all_success,
            details={
                "sub_results": [r.details for r in results],
                "individual_scores": [r.score for r in results],
                "weights": self.weights
            },
            feedback=combined_feedback
        )
