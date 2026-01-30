"""
Benchmark 注册机制

通过注册表管理所有 Benchmark，支持插件式扩展
"""

from typing import Dict, List, Type
from .base_adapter import BaseBenchmarkAdapter


class BenchmarkRegistry:
    """
    Benchmark 注册表
    
    所有 Benchmark 通过注册机制接入，无需修改核心代码
    """
    
    _registry: Dict[str, Type[BaseBenchmarkAdapter]] = {}
    
    @classmethod
    def register(cls, name: str, adapter_class: Type[BaseBenchmarkAdapter]):
        """
        注册 Benchmark
        
        Args:
            name: Benchmark 名称（如 "traineebench", "alfworld"）
            adapter_class: Adapter 类（必须继承 BaseBenchmarkAdapter）
        
        Raises:
            ValueError: 如果 Benchmark 已存在或 adapter_class 类型错误
        
        Example:
            >>> BenchmarkRegistry.register("alfworld", ALFWorldAdapter)
        """
        if name in cls._registry:
            raise ValueError(
                f"Benchmark '{name}' is already registered. "
                f"Use a different name or unregister first."
            )
        
        if not issubclass(adapter_class, BaseBenchmarkAdapter):
            raise TypeError(
                f"Adapter class must inherit from BaseBenchmarkAdapter, "
                f"got {adapter_class.__name__}"
            )
        
        cls._registry[name] = adapter_class
        print(f"✓ Registered benchmark: {name} -> {adapter_class.__name__}")
    
    @classmethod
    def unregister(cls, name: str):
        """
        取消注册 Benchmark
        
        Args:
            name: Benchmark 名称
        """
        if name in cls._registry:
            del cls._registry[name]
            print(f"✓ Unregistered benchmark: {name}")
        else:
            print(f"Warning: Benchmark '{name}' not found in registry")
    
    @classmethod
    def get(cls, name: str) -> Type[BaseBenchmarkAdapter]:
        """
        获取 Benchmark Adapter 类
        
        Args:
            name: Benchmark 名称
        
        Returns:
            Adapter 类
        
        Raises:
            ValueError: 如果 Benchmark 不存在
        """
        if name not in cls._registry:
            available = cls.list_all()
            raise ValueError(
                f"Benchmark '{name}' not registered. "
                f"Available benchmarks: {available}"
            )
        
        return cls._registry[name]
    
    @classmethod
    def list_all(cls) -> List[str]:
        """
        列出所有已注册的 Benchmark
        
        Returns:
            Benchmark 名称列表
        """
        return list(cls._registry.keys())
    
    @classmethod
    def get_info(cls, name: str = None) -> Dict:
        """
        获取 Benchmark 信息
        
        Args:
            name: Benchmark 名称（可选，如果为 None 则返回所有）
        
        Returns:
            信息字典
        """
        if name:
            if name not in cls._registry:
                raise ValueError(f"Benchmark '{name}' not registered")
            
            adapter_class = cls._registry[name]
            return {
                "name": name,
                "adapter_class": adapter_class.__name__,
                "module": adapter_class.__module__
            }
        else:
            return {
                bench_name: {
                    "adapter_class": adapter_class.__name__,
                    "module": adapter_class.__module__
                }
                for bench_name, adapter_class in cls._registry.items()
            }
    
    @classmethod
    def create_adapter(cls, name: str, config: Dict) -> BaseBenchmarkAdapter:
        """
        创建 Benchmark Adapter 实例
        
        Args:
            name: Benchmark 名称
            config: 配置字典
        
        Returns:
            Adapter 实例
        """
        adapter_class = cls.get(name)
        return adapter_class(config)


def register_benchmark(name: str):
    """
    Benchmark 注册装饰器
    
    使用装饰器简化注册流程
    
    Args:
        name: Benchmark 名称
    
    Returns:
        装饰器函数
    
    Example:
        >>> @register_benchmark("alfworld")
        >>> class ALFWorldAdapter(BaseBenchmarkAdapter):
        >>>     ...
    """
    def decorator(adapter_class: Type[BaseBenchmarkAdapter]):
        BenchmarkRegistry.register(name, adapter_class)
        return adapter_class
    
    return decorator
