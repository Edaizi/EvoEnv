"""
工具提供者接口

支持不同 Benchmark 的工具定义方式（MCP, YAML, JSON 等）
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class ToolProvider(ABC):
    """
    工具提供者抽象接口
    
    不同 Benchmark 可以有不同的工具定义方式，
    但都需要实现这个统一接口
    """
    
    @abstractmethod
    def get_tools_schema(self) -> List[Dict]:
        """
        返回工具的 Schema（OpenAI Function Calling 格式）
        
        Returns:
            List[Dict]: 工具定义列表
            
        Example:
            [
                {
                    "type": "function",
                    "function": {
                        "name": "take_action",
                        "description": "Take an action in the environment.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "description": "The action to take"
                                }
                            },
                            "required": ["action"]
                        }
                    }
                }
            ]
        """
        pass
    
    @abstractmethod
    def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """
        执行工具调用
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数（字典格式）
        
        Returns:
            工具执行结果
        """
        pass
    
    @abstractmethod
    def close(self):
        """清理资源（如关闭服务器、容器等）"""
        pass


class MCPToolProvider(ToolProvider):
    """
    基于 MCP (Model Context Protocol) 的工具提供者
    
    用于 TraineeBench，工具定义在 Python 类中
    """
    
    def __init__(self, servers: Dict, tools_config: List[Dict]):
        """
        初始化 MCP 工具提供者
        
        Args:
            servers: 服务器实例字典（如 DockerSandbox, CloudDisk 等）
            tools_config: 工具配置列表
        """
        from tools_parser import ToolManager
        
        self.servers = servers
        self.tool_manager = ToolManager(servers)
        
        # 加载工具模块
        tool_names = [tc.get('name') for tc in tools_config]
        self.tool_manager.load_tools(modules=tool_names)
    
    def get_tools_schema(self) -> List[Dict]:
        """
        返回 MCP 工具的 Schema
        
        将 MCP 工具转换为 OpenAI Function Calling 格式
        """
        return self.tool_manager.tools_schema
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """
        执行 MCP 工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        
        Returns:
            工具执行结果
        """
        if tool_name not in self.tool_manager.tools:
            raise ValueError(f"Tool '{tool_name}' not found in MCP tools")
        
        return self.tool_manager.tools[tool_name](**arguments)
    
    def close(self):
        """清理 MCP 服务器资源"""
        for server in self.servers.values():
            if hasattr(server, 'close'):
                server.close()


class YAMLToolProvider(ToolProvider):
    """
    基于 YAML 定义的工具提供者
    
    用于 AgentBench，工具定义在 YAML 配置文件中
    """
    
    def __init__(self, tools_yaml: List[Dict], env_instance: Any):
        """
        初始化 YAML 工具提供者
        
        Args:
            tools_yaml: YAML 中定义的工具列表（已解析为字典）
            env_instance: 环境实例（如 ALFWorld 的 env）
        """
        self.tools_schema = tools_yaml
        self.env = env_instance
    
    def get_tools_schema(self) -> List[Dict]:
        """返回 YAML 定义的工具 Schema"""
        return self.tools_schema
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """
        执行 YAML 定义的工具
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        
        Returns:
            工具执行结果
        """
        # AgentBench 通常只有一个 take_action 工具
        if tool_name == "take_action":
            action = arguments.get("action")
            if not action:
                raise ValueError("Missing 'action' argument")
            
            # 调用环境的 step 方法
            obs, reward, done, info = self.env.step(action)
            
            return {
                "observation": obs,
                "reward": reward,
                "done": done,
                "info": info
            }
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def close(self):
        """清理环境资源"""
        if hasattr(self.env, 'close'):
            self.env.close()


class DynamicToolProvider(ToolProvider):
    """
    动态工具提供者
    
    支持运行时动态添加工具，用于灵活的场景
    """
    
    def __init__(self):
        self.tools_schema = []
        self.tools = {}
    
    def register_tool(self, name: str, schema: Dict, executor: callable):
        """
        注册一个工具
        
        Args:
            name: 工具名称
            schema: 工具 Schema（Function Calling 格式）
            executor: 工具执行函数
        """
        self.tools_schema.append(schema)
        self.tools[name] = executor
    
    def get_tools_schema(self) -> List[Dict]:
        """返回所有已注册工具的 Schema"""
        return self.tools_schema
    
    def execute_tool(self, tool_name: str, arguments: Dict) -> Any:
        """执行已注册的工具"""
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not registered")
        
        return self.tools[tool_name](**arguments)
    
    def close(self):
        """清理资源"""
        pass
