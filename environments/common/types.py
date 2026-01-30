"""
EvoEnv 标准数据类型定义

所有 Benchmark 使用统一的数据结构，确保接口一致性
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class Observation:
    """
    环境观察
    
    统一封装环境返回给 Agent 的信息
    """
    content: str                              # 文本观察（主要信息）
    available_actions: List[str] = field(default_factory=list)  # 可用动作列表（可选）
    visual: Optional[Any] = None              # 视觉观察（可选，用于多模态任务）
    metadata: Dict = field(default_factory=dict)  # 元数据（如历史消息、状态等）
    
    def __str__(self):
        return self.content


@dataclass
class Action:
    """
    Agent 动作
    
    统一封装 Agent 的工具调用
    """
    tool_name: str                            # 工具名称
    arguments: Dict                           # 工具参数
    raw: Any = None                           # 原始格式（如 tool_call 对象，用于兼容）
    
    @classmethod
    def from_tool_call(cls, tool_call):
        """
        从 OpenAI tool_call 对象创建 Action
        
        Args:
            tool_call: OpenAI 的 tool_call 对象
        
        Returns:
            Action 实例
        """
        import json
        
        return cls(
            tool_name=tool_call.function.name,
            arguments=json.loads(tool_call.function.arguments),
            raw=tool_call
        )


@dataclass
class StepResult:
    """
    单步执行结果
    
    封装环境执行一步后的所有信息
    """
    observation: Observation                  # 环境观察
    reward: float = 0.0                       # 奖励信号（可选，用于 RL）
    done: bool = False                        # 是否结束
    info: Dict = field(default_factory=dict)  # 额外信息


@dataclass
class EvaluationResult:
    """
    评估结果
    
    统一的评估结果格式，支持不同的评估方式
    """
    score: float                              # 得分
    max_score: float                          # 满分
    success: bool                             # 是否成功
    details: Dict = field(default_factory=dict)  # 详细信息
    metrics: Dict = field(default_factory=dict)  # 额外指标（如准确率、F1等）
    feedback: str = ""                        # 反馈信息（用于持续学习）
    
    @property
    def score_rate(self) -> float:
        """得分率"""
        return self.score / self.max_score if self.max_score > 0 else 0.0


@dataclass
class SampleConfig:
    """
    样本配置
    
    封装单个样本的配置信息
    """
    index: int = 0                            # 样本索引
    task_path: str = None                     # 任务路径（TraineeBench 使用）
    data_file: str = None                     # 数据文件路径（AgentBench 使用）
    metadata: Dict = field(default_factory=dict)  # 额外配置


@dataclass
class BenchmarkResult:
    """
    Benchmark 运行结果
    
    封装单个样本的完整运行结果
    """
    benchmark: str                            # Benchmark 名称
    sample_index: int                         # 样本索引
    evaluation: EvaluationResult              # 评估结果
    trajectory: List[Dict] = field(default_factory=list)  # 完整轨迹
    total_steps: int = 0                      # 总步数
    statistics: Dict = field(default_factory=dict)  # 统计信息


@dataclass
class ContinualLearningResult:
    """
    持续学习结果
    
    封装持续学习实验的完整结果
    """
    benchmark: str                            # Benchmark 名称
    samples: List[BenchmarkResult] = field(default_factory=list)  # 所有样本结果
    learning_curve: List[float] = field(default_factory=list)  # 得分曲线
    transfer_rate: float = 0.0                # 迁移率
    efficiency_gain: float = 0.0              # 效率提升
    statistics: Dict = field(default_factory=dict)  # 统计信息
    
    def plot_learning_curve(self, save_path: str = None):
        """
        绘制学习曲线
        
        Args:
            save_path: 保存路径（可选）
        """
        try:
            import matplotlib.pyplot as plt
            
            plt.figure(figsize=(10, 6))
            plt.plot(self.learning_curve, marker='o', linewidth=2)
            plt.xlabel('Sample Index', fontsize=12)
            plt.ylabel('Score', fontsize=12)
            plt.title(f'Learning Curve - {self.benchmark}', fontsize=14)
            plt.grid(True, alpha=0.3)
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
            else:
                plt.show()
                
        except ImportError:
            print("Warning: matplotlib not installed. Cannot plot learning curve.")
    
    def get_summary(self) -> Dict:
        """
        获取摘要信息
        
        Returns:
            包含关键指标的字典
        """
        return {
            "benchmark": self.benchmark,
            "total_samples": len(self.samples),
            "average_score": sum(self.learning_curve) / len(self.learning_curve) if self.learning_curve else 0,
            "final_score": self.learning_curve[-1] if self.learning_curve else 0,
            "transfer_rate": self.transfer_rate,
            "efficiency_gain": self.efficiency_gain,
            "success_rate": sum(1 for s in self.samples if s.evaluation.success) / len(self.samples) if self.samples else 0
        }
