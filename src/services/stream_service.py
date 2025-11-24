"""
流式响应服务模块

处理Server-Sent Events格式的流式响应。
"""

import json
import asyncio
from typing import AsyncIterator, Dict, Any, Optional, List
import logging

from ..models.response import (
    ChatCompletionStreamResponse,
    Delta,
    MessageRole,
    FinishReason
)
from ..utils.exceptions import StreamingError
from .claude_content_parser import get_content_parser, ContentType, ParsedContent

logger = logging.getLogger(__name__)


class StreamService:
    """流式响应服务"""

    def __init__(self):
        self.active_streams: Dict[str, asyncio.Event] = {}

    async def create_claude_stream(
        self,
        response_id: str,
        claude_output: AsyncIterator[str],
        model: str = "claude-3-sonnet-20240229"
    ) -> AsyncIterator[str]:
        """创建Claude输出的流式响应

        返回符合OpenAI SSE格式的数据流，包含结构化的思维过程信息
        """
        try:
            parser = get_content_parser()
            parsed_contents = []
            
            # 发送开始角色（通常只在第一个chunk中）
            yield self._format_sse_data(
                ChatCompletionStreamResponse.create(
                    response_id=response_id,
                    delta_role=MessageRole.ASSISTANT,
                    delta_content="",
                    model=model
                ).dict(exclude_none=True)
            )

            # 流式处理Claude输出
            content_buffer = ""
            line_count = 0
            async for line in claude_output:
                line_count += 1
                
                if line.strip():  # 忽略空行
                    # 解析JSON行，识别思维过程
                    parsed_content = parser.parse_text_content(line)
                    
                    if parsed_content:
                        parsed_contents.append(parsed_content)
                        
                        # 根据内容类型发送不同的响应
                        response_data = self._create_structured_response(
                            response_id, parsed_content, model
                        )
                        
                        if response_data:
                            formatted_data = self._format_sse_data(response_data)
                            yield formatted_data
                    
                    # 同时保持原有的文本流
                    content_buffer += line + "\n"

            # 发送结构化总结信息
            if parsed_contents:
                structured_info = parser.extract_structured_info(parsed_contents)
                summary_response = self._create_summary_response(
                    response_id, structured_info, model
                )
                yield self._format_sse_data(summary_response)

            # 发送结束标记
            yield self._format_sse_data(
                ChatCompletionStreamResponse.create(
                    response_id=response_id,
                    finish_reason=FinishReason.STOP,
                    model=model
                ).dict(exclude_none=True)
            )

            # 发送完成标记
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"Error in Claude stream: {e}", extra={
                "response_id": response_id
            })
            # 发送错误响应
            yield self._format_sse_data({
                "error": {
                    "message": str(e),
                    "type": "streaming_error",
                    "code": "stream_interrupted"
                }
            })

    async def create_non_streaming_response(
        self,
        response_id: str,
        claude_output: AsyncIterator[str],
        model: str = "claude-3-sonnet-20240229"
    ) -> str:
        """创建非流式响应

        收集所有Claude输出并返回完整响应
        """
        try:
            content_parts = []
            async for line in claude_output:
                if line.strip():
                    content_parts.append(line)

            full_content = "".join(content_parts)

            from ..models.response import ChatCompletionResponse, Usage, Message

            response = ChatCompletionResponse.create(
                response_id=response_id,
                message_content=full_content,
                model=model
            )

            # 估算token使用量（简化实现）
            response.usage = Usage(
                prompt_tokens=0,  # TODO: 实现实际的token计算
                completion_tokens=len(full_content.split()),
                total_tokens=len(full_content.split())
            )

            return response.json()

        except Exception as e:
            logger.error(f"Error creating non-streaming response: {e}", extra={
                "response_id": response_id
            })
            raise StreamingError(f"Failed to create response: {e}")

    def _create_structured_response(
        self, 
        response_id: str, 
        parsed_content: ParsedContent, 
        model: str
    ) -> Optional[Dict[str, Any]]:
        """创建结构化响应数据"""
        # 根据内容类型创建不同的响应
        if parsed_content.content_type == ContentType.THINKING:
            return {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": int(asyncio.get_event_loop().time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": parsed_content.content,
                        "thinking_process": {
                            "type": "thinking",
                            "content": parsed_content.content,
                            "metadata": parsed_content.metadata
                        }
                    },
                    "finish_reason": None
                }]
            }
        
        elif parsed_content.content_type == ContentType.PLANNING:
            planning_process = {
                "type": "planning",
                "content": parsed_content.content,
                "tool_info": parsed_content.tool_info,
                "metadata": parsed_content.metadata
            }
            
            # 添加 activeForm 信息
            active_forms = parsed_content.metadata.get("active_forms", [])
            if active_forms:
                planning_process["active_forms"] = active_forms
            
            return {
                "id": response_id,
                "object": "chat.completion.chunk", 
                "created": int(asyncio.get_event_loop().time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": parsed_content.content,
                        "planning_process": planning_process
                    },
                    "finish_reason": None
                }]
            }
        
        elif parsed_content.content_type == ContentType.TOOL_USE:
            return {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": int(asyncio.get_event_loop().time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": parsed_content.content,
                        "tool_usage": {
                            "type": "tool_use",
                            "tool_name": parsed_content.tool_info.get("tool_name") if parsed_content.tool_info else "unknown",
                            "tool_input": parsed_content.tool_info.get("tool_input") if parsed_content.tool_info else {},
                            "metadata": parsed_content.metadata
                        }
                    },
                    "finish_reason": None
                }]
            }
        
        elif parsed_content.content_type == ContentType.EXECUTION:
            return {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": int(asyncio.get_event_loop().time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": parsed_content.content,
                        "execution_process": {
                            "type": "execution",
                            "content": parsed_content.content,
                            "metadata": parsed_content.metadata
                        }
                    },
                    "finish_reason": None
                }]
            }
        
        elif parsed_content.content_type == ContentType.ERROR_HANDLING:
            return {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": int(asyncio.get_event_loop().time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {
                        "content": parsed_content.content,
                        "error_handling": {
                            "type": "error_handling",
                            "content": parsed_content.content,
                            "metadata": parsed_content.metadata
                        }
                    },
                    "finish_reason": None
                }]
            }
        
        elif parsed_content.content_type == ContentType.REGULAR_TEXT:
            # 常规文本内容
            return ChatCompletionStreamResponse.create(
                response_id=response_id,
                delta_content=parsed_content.content,
                model=model
            ).dict()
        
        return None

    def _create_summary_response(
        self, 
        response_id: str, 
        structured_info: Dict[str, Any], 
        model: str
    ) -> Dict[str, Any]:
        """创建总结响应"""
        return {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": int(asyncio.get_event_loop().time()),
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "claude_analysis": {
                        "thinking_process_count": len(structured_info.get("thinking_process", [])),
                        "planning_steps_count": len(structured_info.get("planning_steps", [])),
                        "tools_used": [tool["tool_name"] for tool in structured_info.get("tool_usage", [])],
                        "execution_steps_count": len(structured_info.get("execution_flow", [])),
                        "errors_handled": len(structured_info.get("error_handling", [])),
                        "session_info": structured_info.get("session_info", {}),
                        "structured_data": structured_info
                    }
                },
                "finish_reason": None
            }]
        }

    def _format_sse_data(self, data: Dict[str, Any]) -> str:
        """格式化SSE数据

        Args:
            data: 要发送的数据字典

        Returns:
            格式化的SSE字符串
        """
        try:
            json_data = json.dumps(data, ensure_ascii=False)
            return f"data: {json_data}\n\n"
        except Exception as e:
            logger.error(f"Error formatting SSE data: {e}")
            return f"data: {{\"error\": \"Failed to format response\"}}\n\n"

    def create_stream_id(self) -> str:
        """创建流ID"""
        import uuid
        return str(uuid.uuid4())

    def register_stream(self, stream_id: str) -> asyncio.Event:
        """注册流"""
        event = asyncio.Event()
        self.active_streams[stream_id] = event
        return event

    def unregister_stream(self, stream_id: str) -> None:
        """取消注册流"""
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]

    def signal_stream_complete(self, stream_id: str) -> None:
        """通知流完成"""
        if stream_id in self.active_streams:
            self.active_streams[stream_id].set()

    async def wait_for_stream_complete(self, stream_id: str, timeout: Optional[float] = None) -> bool:
        """等待流完成"""
        if stream_id not in self.active_streams:
            return False

        try:
            await asyncio.wait_for(self.active_streams[stream_id].wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def get_active_stream_count(self) -> int:
        """获取活跃流数量"""
        return len(self.active_streams)

    async def cleanup_expired_streams(self, timeout: float = 300.0) -> None:
        """清理过期流"""
        # TODO: 实现基于时间的流清理逻辑
        pass


# 全局流服务实例
_stream_service: Optional[StreamService] = None


def get_stream_service() -> StreamService:
    """获取全局流服务实例"""
    global _stream_service
    if _stream_service is None:
        _stream_service = StreamService()
    return _stream_service