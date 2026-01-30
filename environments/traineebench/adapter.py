"""
TraineeBench Adapter

将现有的 TraineeBench 包装为标准的 Benchmark Adapter
"""

from typing import Dict, Any
from pathlib import Path

from environments.common import (
    BaseBenchmarkAdapter,
    ToolProvider, MCPToolProvider,
    BaseEvaluator, FunctionBasedEvaluator,
    SampleConfig, Observation, Action, StepResult, EvaluationResult,
    register_benchmark
)


@register_benchmark("traineebench")
class TraineeBenchAdapter(BaseBenchmarkAdapter):
    """
    TraineeBench 适配器
    
    特点：
    - 使用 MCPToolProvider（现有的 MCP 工具系统）
    - 使用 FunctionBasedEvaluator（现有的评估函数）
    - 包装现有的 Environment 类，保持向后兼容
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 TraineeBench 适配器
        
        Args:
            config: 配置字典，必须包含 'task_path'
        
        Example:
            >>> adapter = TraineeBenchAdapter({
            ...     "task_path": "./CLBench/benchs/scenario_1/day_1"
            ... })
        """
        super().__init__(config)
        
        self.task_path = config.get("task_path")
        if not self.task_path:
            raise ValueError("TraineeBench requires 'task_path' in config")
        
        self.log_level = config.get("log_level", "INFO")
        self.log_path = config.get("log_path", "")
        
        # 延迟初始化（在 reset 时创建）
        self._legacy_env = None
        self._tool_provider = None
        self._evaluator = None
    
    def get_tool_provider(self) -> ToolProvider:
        """
        返回 MCP 工具提供者
        
        复用现有的 ToolManager 系统
        """
        if self._tool_provider is None:
            if self._legacy_env is None:
                raise RuntimeError(
                    "Environment not initialized. Call reset() first."
                )
            
            # 从旧的 Environment 获取配置
            import json
            from pathlib import Path
            
            config_file = Path(self.task_path) / 'config.json'
            with open(config_file, 'r', encoding='utf-8') as rf:
                config = json.load(rf)
            
            tools_config = config.get('tools', [])
            
            self._tool_provider = MCPToolProvider(
                servers=self._legacy_env.servers,
                tools_config=tools_config
            )
        
        return self._tool_provider
    
    def get_evaluator(self) -> BaseEvaluator:
        """
        返回函数式评估器
        
        使用现有的 EVALUATOR_REGISTRY
        """
        if self._evaluator is None:
            from environments.traineebench.schemas.registry import EVALUATOR_REGISTRY
            
            self._evaluator = FunctionBasedEvaluator(
                evaluator_registry=EVALUATOR_REGISTRY
            )
        
        return self._evaluator
    
    def load_sample(self, index: int = 0) -> SampleConfig:
        """
        加载样本配置
        
        TraineeBench 使用文件夹路径，不需要索引
        
        Args:
            index: 样本索引（TraineeBench 中未使用）
        
        Returns:
            SampleConfig: 样本配置
        """
        return SampleConfig(
            index=index,
            task_path=self.task_path
        )
    
    def reset(self, sample_config: SampleConfig) -> Observation:
        """
        重置环境到初始状态
        
        Args:
            sample_config: 样本配置
        
        Returns:
            Observation: 初始观察（任务描述）
        """
        # 初始化旧版 Environment
        from environment import Environment as LegacyEnv
        
        self._legacy_env = LegacyEnv(
            task_path=self.task_path,
            log_level=self.log_level,
            log_path=self.log_path
        )
        
        # 生成任务 Prompt
        agent_name = self._legacy_env.ego_agent_names[0]
        task_prompt = self._legacy_env.generate_tasks_prompt(agent_name)
        
        # 获取工具 Schema
        tools_schema = self.get_tools_schema()
        
        return Observation(
            content=task_prompt,
            metadata={
                "agent_name": agent_name,
                "tools_schema": tools_schema,
                "workspace": self._legacy_env.workspace,
                "clock": self._legacy_env.clock.now_str() if self._legacy_env.clock else None
            }
        )
    
    def step(self, action: Action) -> StepResult:
        """
        执行一步动作
        
        Args:
            action: Agent 的动作
        
        Returns:
            StepResult: 执行结果
        """
        if self._legacy_env is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        
        # 获取 agent_name
        agent_name = self._legacy_env.ego_agent_names[0]
        
        # 执行工具调用
        # 注意：这里需要将 Action 转换为 tool_calls 格式
        tool_calls = [action.raw] if action.raw else []
        
        if not tool_calls:
            # 如果没有原始格式，创建一个模拟的 tool_call
            # 这种情况通常不会发生，因为 Agent 会提供原始格式
            return StepResult(
                observation=Observation(
                    content="Error: No tool call provided"
                ),
                done=False,
                info={"error": "Missing tool call"}
            )
        
        # 调用旧版 execute_tool_calls
        results = self._legacy_env.execute_tool_calls(
            agent_name=agent_name,
            tool_calls=tool_calls
        )
        
        # 转换结果为标准格式
        # results 是一个列表，包含 tool 结果和可能的 system 消息
        observation_content = "\n".join(
            msg.get("content", "") for msg in results
        )
        
        return StepResult(
            observation=Observation(
                content=observation_content,
                metadata={
                    "results": results,
                    "clock": self._legacy_env.clock.now_str() if self._legacy_env.clock else None
                }
            ),
            done=False,  # TraineeBench 没有明确的 done 信号
            info={"raw_results": results}
        )
    
    def evaluate(self, **eval_params) -> EvaluationResult:
        """
        评估当前任务
        
        Args:
            **eval_params: 额外的评估参数（可选）
        
        Returns:
            EvaluationResult: 评估结果
        """
        if self._legacy_env is None:
            raise RuntimeError("Environment not initialized. Call reset() first.")
        
        evaluator = self.get_evaluator()
        
        # 从 config.json 读取评估配置
        all_results = []
        
        for task in self._legacy_env.tasks:
            eval_config = task.get('evaluation', {})
            if eval_config:
                # 调用评估函数
                result = evaluator.evaluate(
                    evaluator_name=eval_config['name'],
                    workspace_path=self._legacy_env.workspace,
                    **eval_config.get('args', {})
                )
                all_results.append(result)
        
        # 如果有多个任务，合并结果
        if not all_results:
            return EvaluationResult(
                score=0,
                max_score=1,
                success=False,
                feedback="No evaluation configured"
            )
        elif len(all_results) == 1:
            return all_results[0]
        else:
            # 合并多个任务的评估结果
            total_score = sum(r.score for r in all_results)
            total_max = sum(r.max_score for r in all_results)
            all_success = all(r.success for r in all_results)
            combined_feedback = "\n\n".join(
                f"Task {i+1}: {r.feedback}" 
                for i, r in enumerate(all_results) 
                if r.feedback
            )
            
            return EvaluationResult(
                score=total_score,
                max_score=total_max,
                success=all_success,
                details={
                    "task_results": [r.details for r in all_results]
                },
                feedback=combined_feedback
            )
    
    def close(self):
        """清理资源"""
        if self._legacy_env:
            self._legacy_env.close()
            self._legacy_env = None
        
        if self._tool_provider:
            self._tool_provider.close()
            self._tool_provider = None
    
    def get_sample_count(self) -> int:
        """
        获取样本总数
        
        TraineeBench 通常是单个任务，返回 1
        """
        return 1
    
    def get_benchmark_info(self) -> Dict:
        """获取 Benchmark 元信息"""
        info = super().get_benchmark_info()
        info.update({
            "benchmark_type": "traineebench",
            "task_path": self.task_path,
            "description": "TraineeBench - Office environment simulation"
        })
        return info
