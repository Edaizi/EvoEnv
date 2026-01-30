"""
简化的 Benchmark 运行示例

展示如何使用新的 EvoEnv API 运行 TraineeBench
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from evoenv import EvoEnv
from agents.hybrid_memory import HybridMemoryAgent


def run_single_task():
    """运行单个任务"""
    print("\n" + "="*60)
    print("Example 1: Running Single Task")
    print("="*60)
    
    # 创建 Agent
    agent = HybridMemoryAgent(
        agent_name="Alice",
        model_name="gpt-4o"
    )
    
    # 运行 Benchmark
    result = EvoEnv.run_benchmark(
        benchmark="traineebench",
        config={
            "task_path": "./CLBench/benchs/scenario_1/day_1"
        },
        agent=agent,
        max_steps=50
    )
    
    # 查看结果
    print(f"\n✓ Task completed!")
    print(f"  Score: {result.evaluation.score}/{result.evaluation.max_score}")
    print(f"  Success: {result.evaluation.success}")
    print(f"  Total Steps: {result.total_steps}")
    
    if result.evaluation.feedback:
        print(f"  Feedback: {result.evaluation.feedback[:100]}...")


def run_continual_learning():
    """运行持续学习实验"""
    print("\n" + "="*60)
    print("Example 2: Running Continual Learning")
    print("="*60)
    
    # 创建 Agent
    agent = HybridMemoryAgent(
        agent_name="Alice",
        model_name="gpt-4o"
    )
    
    # 运行持续学习实验（3天）
    cl_result = EvoEnv.run_continual_learning(
        benchmark="traineebench",
        samples=[0, 1, 2],  # day_1, day_2, day_3
        agent=agent,
        reflection_config={"model": "gpt-4o"},
        max_steps=50,
        output_dir="./outputs/cl_experiment"
    )
    
    # 查看结果
    print(f"\n✓ Continual Learning completed!")
    print(f"  Total Samples: {len(cl_result.samples)}")
    print(f"  Learning Curve: {cl_result.learning_curve}")
    print(f"  Transfer Rate: {cl_result.transfer_rate:.2%}")
    print(f"  Efficiency Gain: {cl_result.efficiency_gain:.2%}")
    
    # 绘制学习曲线
    try:
        cl_result.plot_learning_curve(save_path="./outputs/learning_curve.png")
        print(f"  Learning curve saved to ./outputs/learning_curve.png")
    except Exception as e:
        print(f"  Note: Could not plot learning curve: {e}")


def list_available_benchmarks():
    """列出可用的 Benchmark"""
    print("\n" + "="*60)
    print("Example 3: List Available Benchmarks")
    print("="*60)
    
    benchmarks = EvoEnv.list_benchmarks()
    print(f"\nAvailable Benchmarks: {benchmarks}")
    
    for bench in benchmarks:
        info = EvoEnv.get_benchmark_info(bench)
        print(f"\n{bench}:")
        print(f"  Adapter: {info['adapter_class']}")
        print(f"  Module: {info['module']}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("EvoEnv Simple Examples")
    print("="*60)
    
    # 示例 1：列出可用的 Benchmark
    list_available_benchmarks()
    
    # 示例 2：运行单个任务（需要实际数据）
    # run_single_task()
    
    # 示例 3：运行持续学习实验（需要实际数据）
    # run_continual_learning()
    
    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)
    print("\nNote: To run actual tasks, uncomment the function calls")
    print("and ensure you have the required data in CLBench/benchs/")
    print("="*60 + "\n")
