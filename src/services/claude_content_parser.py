"""
Claude内容解析器模块

解析Claude的JSON输出，识别思维过程、规划步骤、工具使用等结构化信息。
"""

import json
import re
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """内容类型枚举"""
    SYSTEM_INIT = "system_init"           # 系统初始化
    THINKING = "thinking"                 # 思维过程
    PLANNING = "planning"                 # 规划过程
    TOOL_USE = "tool_use"                # 工具使用
    TOOL_RESULT = "tool_result"          # 工具结果
    EXECUTION = "execution"              # 执行过程
    ANALYSIS = "analysis"                # 分析过程
    SUMMARY = "summary"                  # 总结
    ERROR_HANDLING = "error_handling"    # 错误处理
    STATUS_UPDATE = "status_update"      # 状态更新
    REGULAR_TEXT = "regular_text"        # 常规文本


@dataclass
class ParsedContent:
    """解析后的内容"""
    content_type: ContentType
    content: str
    metadata: Dict[str, Any]
    tool_info: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None
    timestamp: Optional[str] = None


class ClaudeContentParser:
    """Claude内容解析器"""
    
    def __init__(self):
        # 思维过程关键词
        self.thinking_keywords = [
            "我将", "让我", "我需要", "我的思路", "我认为", "分析", "考虑",
            "策略", "方法", "approach", "strategy", "thinking", "consider"
        ]
        
        # 规划过程关键词
        self.planning_keywords = [
            "规划", "计划", "步骤", "任务", "框架", "plan", "step", "task",
            "framework", "structure", "organize", "TodoWrite"
        ]
        
        # 执行过程关键词
        self.execution_keywords = [
            "执行", "开始", "现在", "接下来", "execute", "start", "begin",
            "proceed", "WebSearch", "WebFetch", "搜索", "查找"
        ]
        
        # 分析过程关键词
        self.analysis_keywords = [
            "分析", "研究", "发现", "结果", "数据", "趋势", "analyze", 
            "research", "findings", "results", "data", "trends"
        ]
        
        # 错误处理关键词
        self.error_keywords = [
            "错误", "失败", "问题", "限制", "无法", "error", "failed", 
            "problem", "unable", "limitation", "API Error"
        ]

    def parse_claude_json_line(self, json_line: str) -> Optional[ParsedContent]:
        """解析Claude输出的单行JSON"""
        try:
            if not json_line.strip():
                return None
                
            data = json.loads(json_line)
            return self._classify_and_parse_content(data)
            
        except json.JSONDecodeError as e:
            logger.warning(f"无法解析JSON行: {json_line[:100]}..., 错误: {e}")
            return None
        except Exception as e:
            logger.error(f"解析内容时出错: {e}")
            return None
    
    def parse_text_content(self, text: str) -> ParsedContent:
        """解析纯文本内容，识别思维过程和结构化信息"""
        if not text or not text.strip():
            return ParsedContent(
                content_type=ContentType.REGULAR_TEXT,
                content=text,
                metadata={}
            )
        
        # 分类内容类型
        content_type = self._classify_text_content(text)
        
        # 提取基本元数据
        metadata = {
            "text_length": len(text),
            "line_count": len(text.split('\n')),
            "classification_method": "text_analysis"
        }
        
        return ParsedContent(
            content_type=content_type,
            content=text,
            metadata=metadata
        )

    def _classify_and_parse_content(self, data: Dict[str, Any]) -> Optional[ParsedContent]:
        """分类和解析内容"""
        content_type = data.get("type", "")
        
        # 系统初始化
        if content_type == "system":
            return self._parse_system_content(data)
        
        # Assistant消息
        elif content_type == "assistant":
            return self._parse_assistant_content(data)
        
        # 用户消息（通常是工具结果）
        elif content_type == "user":
            return self._parse_user_content(data)
        
        # 结果类型
        elif content_type == "result":
            return self._parse_result_content(data)
        
        return None

    def _parse_system_content(self, data: Dict[str, Any]) -> ParsedContent:
        """解析系统内容"""
        subtype = data.get("subtype", "")
        session_id = data.get("session_id")
        
        metadata = {
            "subtype": subtype,
            "cwd": data.get("cwd"),
            "tools": data.get("tools", []),
            "model": data.get("model"),
            "agents": data.get("agents", [])
        }
        
        content = f"系统初始化完成 - 模型: {data.get('model', 'unknown')}, 工具数量: {len(data.get('tools', []))}"
        
        return ParsedContent(
            content_type=ContentType.SYSTEM_INIT,
            content=content,
            metadata=metadata,
            session_id=session_id
        )

    def _parse_assistant_content(self, data: Dict[str, Any]) -> Optional[ParsedContent]:
        """解析Assistant内容"""
        message = data.get("message", {})
        content_items = message.get("content", [])
        session_id = data.get("session_id")
        
        if not content_items:
            return None
        
        # 处理多个内容项
        for item in content_items:
            item_type = item.get("type", "")
            
            # 文本内容
            if item_type == "text":
                text_content = item.get("text", "")
                content_type = self._classify_text_content(text_content)
                
                return ParsedContent(
                    content_type=content_type,
                    content=text_content,
                    metadata={
                        "message_id": message.get("id"),
                        "model": message.get("model"),
                        "usage": message.get("usage", {})
                    },
                    session_id=session_id
                )
            
            # 工具使用
            elif item_type == "tool_use":
                tool_name = item.get("name", "")
                tool_input = item.get("input", {})
                
                # 特殊处理TodoWrite工具
                if tool_name == "TodoWrite":
                    content_type = ContentType.PLANNING
                    content = self._format_todo_content(tool_input)
                    # 提取 activeForm 信息
                    active_forms = self.extract_active_forms(tool_input)
                    metadata = {
                        "message_id": message.get("id"),
                        "model": message.get("model"),
                        "active_forms": active_forms
                    }
                else:
                    content_type = ContentType.TOOL_USE
                    content = f"使用工具: {tool_name}"
                    metadata = {
                        "message_id": message.get("id"),
                        "model": message.get("model")
                    }
                
                return ParsedContent(
                    content_type=content_type,
                    content=content,
                    metadata=metadata,
                    tool_info={
                        "tool_id": item.get("id"),
                        "tool_name": tool_name,
                        "tool_input": tool_input
                    },
                    session_id=session_id
                )
        
        return None

    def _parse_user_content(self, data: Dict[str, Any]) -> Optional[ParsedContent]:
        """解析用户内容（通常是工具结果）"""
        message = data.get("message", {})
        content_items = message.get("content", [])
        session_id = data.get("session_id")
        
        for item in content_items:
            if item.get("type") == "tool_result":
                tool_use_id = item.get("tool_use_id")
                result_content = item.get("content", "")
                is_error = item.get("is_error", False)
                
                content_type = ContentType.ERROR_HANDLING if is_error else ContentType.TOOL_RESULT
                
                return ParsedContent(
                    content_type=content_type,
                    content=result_content,
                    metadata={
                        "is_error": is_error,
                        "tool_use_id": tool_use_id
                    },
                    session_id=session_id
                )
        
        return None

    def _parse_result_content(self, data: Dict[str, Any]) -> ParsedContent:
        """解析结果内容"""
        result = data.get("result", {})
        session_id = data.get("session_id")
        
        return ParsedContent(
            content_type=ContentType.SUMMARY,
            content=str(result),
            metadata={"result_data": result},
            session_id=session_id
        )

    def _classify_text_content(self, text: str) -> ContentType:
        """分类文本内容"""
        text_lower = text.lower()
        
        # 检查错误处理
        if any(keyword in text_lower for keyword in self.error_keywords):
            return ContentType.ERROR_HANDLING
        
        # 检查规划过程
        if any(keyword in text_lower for keyword in self.planning_keywords):
            return ContentType.PLANNING
        
        # 检查思维过程
        if any(keyword in text_lower for keyword in self.thinking_keywords):
            return ContentType.THINKING
        
        # 检查执行过程
        if any(keyword in text_lower for keyword in self.execution_keywords):
            return ContentType.EXECUTION
        
        # 检查分析过程
        if any(keyword in text_lower for keyword in self.analysis_keywords):
            return ContentType.ANALYSIS
        
        return ContentType.REGULAR_TEXT

    def _format_todo_content(self, tool_input: Dict[str, Any]) -> str:
        """格式化Todo内容"""
        todos = tool_input.get("todos", [])
        if not todos:
            return "创建任务列表"
        
        formatted_todos = []
        for todo in todos:
            status = todo.get("status", "pending")
            content = todo.get("content", "")
            active_form = todo.get("activeForm", "")
            status_emoji = {
                "pending": "⏳",
                "in_progress": "🔄", 
                "completed": "✅"
            }.get(status, "📝")
            
            formatted_todos.append(f"{status_emoji} {content}")
        
        return f"任务规划:\n" + "\n".join(formatted_todos)
    
    def extract_active_forms(self, tool_input: Dict[str, Any]) -> List[str]:
        """提取所有的 activeForm 字段"""
        todos = tool_input.get("todos", [])
        active_forms = []
        
        for todo in todos:
            active_form = todo.get("activeForm", "")
            if active_form and active_form.strip():
                active_forms.append(active_form)
        
        return active_forms

    def extract_structured_info(self, parsed_contents: List[ParsedContent]) -> Dict[str, Any]:
        """从解析内容中提取结构化信息"""
        structured_info = {
            "thinking_process": [],
            "planning_steps": [],
            "tool_usage": [],
            "execution_flow": [],
            "error_handling": [],
            "analysis_results": [],
            "session_info": {}
        }
        
        for content in parsed_contents:
            if content.content_type == ContentType.THINKING:
                structured_info["thinking_process"].append({
                    "content": content.content,
                    "metadata": content.metadata
                })
            
            elif content.content_type == ContentType.PLANNING:
                planning_step = {
                    "content": content.content,
                    "tool_info": content.tool_info,
                    "metadata": content.metadata
                }
                
                # 添加 activeForm 信息
                active_forms = content.metadata.get("active_forms", [])
                if active_forms:
                    planning_step["active_forms"] = active_forms
                
                structured_info["planning_steps"].append(planning_step)
            
            elif content.content_type == ContentType.TOOL_USE:
                structured_info["tool_usage"].append({
                    "tool_name": content.tool_info.get("tool_name") if content.tool_info else "unknown",
                    "tool_input": content.tool_info.get("tool_input") if content.tool_info else {},
                    "content": content.content
                })
            
            elif content.content_type == ContentType.EXECUTION:
                structured_info["execution_flow"].append({
                    "content": content.content,
                    "metadata": content.metadata
                })
            
            elif content.content_type == ContentType.ERROR_HANDLING:
                structured_info["error_handling"].append({
                    "content": content.content,
                    "metadata": content.metadata
                })
            
            elif content.content_type == ContentType.ANALYSIS:
                structured_info["analysis_results"].append({
                    "content": content.content,
                    "metadata": content.metadata
                })
            
            # 收集会话信息
            if content.session_id and not structured_info["session_info"]:
                structured_info["session_info"] = {
                    "session_id": content.session_id,
                    "model": content.metadata.get("model"),
                    "tools_available": content.metadata.get("tools", [])
                }
        
        return structured_info


# 全局解析器实例
_content_parser: Optional[ClaudeContentParser] = None


def get_content_parser() -> ClaudeContentParser:
    """获取全局内容解析器实例"""
    global _content_parser
    if _content_parser is None:
        _content_parser = ClaudeContentParser()
    return _content_parser