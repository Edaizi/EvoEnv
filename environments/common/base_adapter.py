"""
Benchmark Adapter 基类

所有 Benchmark 适配器都继承自这个基类
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from .types import SampleConfig, Observation, Action, StepResult, EvaluationResult
from .tool_interface import ToolProvider
from .base_evaluator import BaseEvaluator


class BaseBenchmarkAdapter(ABC):
    """
    Benchmark 适配器抽象基类
    
    每个 Benchmark 需要：
    1. 提供工具（通过 ToolProvider）
    2. 提供评估器（通过 BaseEvaluator）
    3. 实现数据加载、环境重置、步进等核心方法
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化适配器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self._tool_provider: ToolProvider = None
        self._evaluator: BaseEvaluator = None
    
    @abstractmethod
    def get_tool_provider(self) -> ToolProvider:
        """
        返回工具提供者
        
        不同 Benchmark 可以返回不同的 ToolProvider 实现：
        - TraineeBench: MCPToolProvider
        - AgentBench: YAMLToolProvider
        - 自定义: DynamicToolProvider
        
        Returns:
            ToolProvider 实例
        """
        pass
    
    @abstractmethod
    def get_evaluator(self) -> BaseEvaluator:
        """
        返回评估器
        
        不同 Benchmark 可以返回不同的 Evaluator 实现：
        - TraineeBench: FunctionBasedEvaluator
        - AgentBench: EnvironmentBasedEvaluator
        - GAIA2: LLMJudgeEvaluator 或 HybridEvaluator
        
        Returns:
            BaseEvaluator 实例
        """
        pass
    
    @abstractmethod
    def load_sample(self, index: int) -> SampleConfig:
        """
        加载单个样本的配置
        
        Args:
            index: 样本索引
        
        Returns:
            SampleConfig: 样本配置
        """
        pass
    
    @abstractmethod
    def reset(self, sample_config: SampleConfig) -> Observation:
        """
        重置环境到样本的初始状态
        
        Args:
            sample_config: 样本配置
        
        Returns:
            Observation: 初始观察
        """
        pass
    
    @abstractmethod
    def step(self, action: Action) -> StepResult:
        """
        执行一步动作
        
        Args:
            action: Agent 的动作
        
        Returns:
            StepResult: 执行结果
        """
        pass
    
    def evaluate(self, **eval_params) -> EvaluationResult:
        """
        评估当前任务
        
        委托给 evaluator 执行，不同 Benchmark 传入不同的参数
        
        Args:
            **eval_params: 评估参数（每个 Benchmark 不同）
        
        Returns:
            EvaluationResult: 评估结果
        """
        evaluator = self.get_evaluator()
        return evaluator.evaluate(**eval_params)
    
    @abstractmethod
    def close(self):
        """
        清理资源
        
        关闭所有打开的服务、容器、文件等
        """
        pass
    
    # ============ 辅助方法 ============
    
    def get_sample_count(self) -> int:
        """
        获取总样本数
        
        Returns:
            样本总数（默认返回 0，子类可覆盖）
        """
        return 0
    
    def get_tools_schema(self) -> list:
        """
        获取工具 Schema（便捷方法）
        
        Returns:
            工具 Schema 列表
        """
        tool_provider = self.get_tool_provider()
        return tool_provider.get_tools_schema()
    
    def get_benchmark_info(self) -> Dict:
        """
        获取 Benchmark 元信息
        
        Returns:
            元信息字典
        """
        return {
            "name": self.__class__.__name__,
            "sample_count": self.get_sample_count(),
            "config": self.config
        }
