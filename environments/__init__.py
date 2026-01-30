"""
EvoEnv Environments Package

自动导入所有 Benchmark 以触发注册
"""

# 导入 common 模块
from . import common

# 导入所有 Benchmark 以触发 @register_benchmark 装饰器
try:
    from . import traineebench
except ImportError as e:
    print(f"Warning: Failed to import traineebench: {e}")

# 未来的 Benchmark 可以在这里添加
# try:
#     from . import alfworld
# except ImportError:
#     pass

__all__ = ['common', 'traineebench']
