"""
EvoEnv - 统一入口 API

提供极简的接口运行各种 Benchmark
"""

from typing import Dict, List, Any, Optional
from pathlib import Path
import json

# 自动导入所有 Benchmark
import environments
from environments.common import (
    BenchmarkRegistry,
    BenchmarkResult, ContinualLearningResult,
    SampleConfig, Action
)


class EvoEnv:  
    @staticmethod
    def run_benchmark(
        benchmark: str,
        config: Dict[str, Any],
        agent: Any,
        mode: str = "single",
        max_steps: int = 50,
        save_trajectory: bool = True,
        output_dir: str = None
    ) -> BenchmarkResult:
        """
        运行单个 Benchmark
        
        Args:
            benchmark: Benchmark 名称（如 "traineebench", "alfworld"）
            config: 配置字典
            agent: Agent 实例（必须有 forward 或类似方法）
            mode: 运行模式
                - "single": 单任务模式（测试原生性能）
                - "continual_learning": 持续学习模式（加载历史经验）
            max_steps: 最大步数
            save_trajectory: 是否保存轨迹
            output_dir: 输出目录（可选）
        
        Returns:
            BenchmarkResult: 包含评分、轨迹、统计信息
        
        Example:
            >>> from evoenv import EvoEnv
            >>> from agents import HybridMemoryAgent
            >>> 
            >>> agent = HybridMemoryAgent(model_name="gpt-4o")
            >>> result = EvoEnv.run_benchmark(
            ...     benchmark="traineebench",
            ...     config={"task_path": "./CLBench/benchs/day_1"},
            ...     agent=agent
            ... )
            >>> print(f"Score: {result.evaluation.score}")
        """
        # 创建适配器
        adapter = BenchmarkRegistry.create_adapter(benchmark, config)
        
        try:
            # 加载样本并重置环境
            sample_index = config.get("sample_index", 0)
            sample = adapter.load_sample(sample_index)
            obs = adapter.reset(sample)
            
            # 设置 Agent 的任务 Prompt
            if hasattr(agent, 'set_task_prompt'):
                agent.set_task_prompt(obs.content)
            
            # 获取工具 Schema
            tools_schema = adapter.get_tools_schema()
            
            # 执行任务
            trajectory = []
            total_steps = 0
            
            # 如果 Agent 有 forward 方法（TraineeBench 风格）
            if hasattr(agent, 'forward'):
                # 使用旧的 Environment 接口
                if benchmark == "traineebench" and hasattr(adapter, '_legacy_env'):
                    agent.forward(adapter._legacy_env, max_steps=max_steps)
                    total_steps = agent.step_count if hasattr(agent, 'step_count') else max_steps
                    
                    # 保存轨迹
                    if save_trajectory and hasattr(agent, 'messages'):
                        trajectory = agent.messages
                else:
                    # 通用的 step-by-step 执行
                    for step in range(max_steps):
                        # 这里需要 Agent 提供更通用的接口
                        # 暂时跳过，等待具体实现
                        pass
            
            # 评估
            evaluation = adapter.evaluate()
            
            # 构建结果
            result = BenchmarkResult(
                benchmark=benchmark,
                sample_index=sample_index,
                evaluation=evaluation,
                trajectory=trajectory,
                total_steps=total_steps,
                statistics={
                    "max_steps": max_steps,
                    "mode": mode
                }
            )
            
            # 保存结果
            if output_dir:
                output_path = Path(output_dir)
                output_path.mkdir(parents=True, exist_ok=True)
                
                result_file = output_path / f"{benchmark}_sample_{sample_index}_result.json"
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "benchmark": result.benchmark,
                        "sample_index": result.sample_index,
                        "evaluation": {
                            "score": result.evaluation.score,
                            "max_score": result.evaluation.max_score,
                            "success": result.evaluation.success,
                            "feedback": result.evaluation.feedback
                        },
                        "total_steps": result.total_steps,
                        "statistics": result.statistics
                    }, f, indent=2, ensure_ascii=False)
            
            return result
            
        finally:
            # 清理资源
            adapter.close()
    
    @staticmethod
    def run_continual_learning(
        benchmark: str,
        samples: List[int],
        agent: Any,
        reflection_config: Dict = None,
        max_steps: int = 50,
        output_dir: str = None
    ) -> ContinualLearningResult:
        """
        运行持续学习实验
        
        Args:
            benchmark: Benchmark 名称
            samples: 样本索引列表（按顺序执行）
            agent: Agent 实例
            reflection_config: 反思配置（可选）
            max_steps: 每个样本的最大步数
            output_dir: 输出目录（可选）
        
        Returns:
            ContinualLearningResult: 包含学习曲线、迁移率等
        
        Example:
            >>> result = EvoEnv.run_continual_learning(
            ...     benchmark="traineebench",
            ...     samples=[0, 1, 2, 3, 4],
            ...     agent=agent,
            ...     reflection_config={"model": "gpt-4o"}
            ... )
            >>> result.plot_learning_curve()
        """
        if reflection_config is None:
            reflection_config = {}
        
        # 准备输出目录
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
        else:
            output_path = Path(f"./outputs/{benchmark}_cl")
            output_path.mkdir(parents=True, exist_ok=True)
        
        # 运行所有样本
        results = []
        learning_curve = []
        experience_path = None
        
        for i, sample_idx in enumerate(samples):
            print(f"\n{'='*60}")
            print(f"Running Sample {i+1}/{len(samples)} (index={sample_idx})")
            print(f"{'='*60}")
            
            # 更新 Agent 的经验路径
            if hasattr(agent, 'exp_path'):
                agent.exp_path = experience_path
            
            # 构建配置
            config = {
                "sample_index": sample_idx
            }
            
            # 运行单个样本
            result = EvoEnv.run_benchmark(
                benchmark=benchmark,
                config=config,
                agent=agent,
                mode="continual_learning",
                max_steps=max_steps,
                output_dir=str(output_path / f"sample_{sample_idx}")
            )
            
            results.append(result)
            learning_curve.append(result.evaluation.score)
            
            # 反思阶段（如果不是最后一个样本）
            if i < len(samples) - 1 and reflection_config:
                print(f"\nReflection Phase...")
                
                # 生成新的经验文件路径
                experience_path = str(output_path / f"exp_after_sample_{sample_idx}.json")
                
                # 调用反思 Agent（如果配置了）
                if reflection_config.get("model"):
                    try:
                        from agents.reflect_agent import ReflectAgent
                        
                        reflect_agent = ReflectAgent(
                            model_name=reflection_config["model"]
                        )
                        
                        # 构建反思输入
                        feedback = result.evaluation.feedback
                        if feedback and hasattr(agent, 'messages'):
                            reflect_input = f"# Agent History\n{json.dumps(agent.messages, ensure_ascii=False)}\n\n# Feedback\n{feedback}"
                            
                            # 生成反思
                            reflections = reflect_agent.response(reflect_input)
                            
                            # 保存经验
                            if reflections:
                                with open(experience_path, 'w', encoding='utf-8') as f:
                                    json.dump(reflections, f, ensure_ascii=False, indent=2)
                                
                                print(f"✓ Saved reflections to {experience_path}")
                    
                    except ImportError:
                        print("Warning: ReflectAgent not available, skipping reflection")
        
        # 计算迁移率和效率提升
        transfer_rate = 0.0
        efficiency_gain = 0.0
        
        if len(learning_curve) > 1:
            # 简单的迁移率计算：最后一个样本相比第一个样本的提升
            transfer_rate = (learning_curve[-1] - learning_curve[0]) / learning_curve[0] if learning_curve[0] > 0 else 0
            
            # 效率提升：平均步数的下降
            steps = [r.total_steps for r in results]
            if len(steps) > 1:
                efficiency_gain = (steps[0] - steps[-1]) / steps[0] if steps[0] > 0 else 0
        
        # 构建结果
        cl_result = ContinualLearningResult(
            benchmark=benchmark,
            samples=results,
            learning_curve=learning_curve,
            transfer_rate=transfer_rate,
            efficiency_gain=efficiency_gain,
            statistics={
                "total_samples": len(samples),
                "reflection_config": reflection_config,
                "max_steps": max_steps
            }
        )
        
        # 保存总结
        summary_file = output_path / "cl_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(cl_result.get_summary(), f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*60}")
        print("Continual Learning Experiment Complete!")
        print(f"{'='*60}")
        print(f"Results saved to: {output_path}")
        print(f"Transfer Rate: {transfer_rate:.2%}")
        print(f"Efficiency Gain: {efficiency_gain:.2%}")
        print(f"{'='*60}\n")
        
        return cl_result
    
    @staticmethod
    def list_benchmarks() -> List[str]:
        """
        列出所有可用的 Benchmark
        
        Returns:
            Benchmark 名称列表
        
        Example:
            >>> benchmarks = EvoEnv.list_benchmarks()
            >>> print(benchmarks)
            ['traineebench', 'alfworld', 'dbbench']
        """
        return BenchmarkRegistry.list_all()
    
    @staticmethod
    def get_benchmark_info(benchmark: str) -> Dict:
        """
        获取 Benchmark 的详细信息
        
        Args:
            benchmark: Benchmark 名称
        
        Returns:
            信息字典
        
        Example:
            >>> info = EvoEnv.get_benchmark_info("traineebench")
            >>> print(info)
        """
        return BenchmarkRegistry.get_info(benchmark)


# 便捷函数
def run_benchmark(benchmark: str, config: Dict, agent: Any, **kwargs) -> BenchmarkResult:
    """便捷函数：运行单个 Benchmark"""
    return EvoEnv.run_benchmark(benchmark, config, agent, **kwargs)


def run_continual_learning(benchmark: str, samples: List[int], agent: Any, **kwargs) -> ContinualLearningResult:
    """便捷函数：运行持续学习实验"""
    return EvoEnv.run_continual_learning(benchmark, samples, agent, **kwargs)


def list_benchmarks() -> List[str]:
    """便捷函数：列出所有 Benchmark"""
    return EvoEnv.list_benchmarks()
