"""
聊天完成API路由模块

实现OpenAI兼容的/v1/chat/completions端点。
"""

import uuid
import json
from datetime import datetime
from typing import Union
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
import logging

from ...models.message import ChatCompletionRequest
from ...models.response import (
    ChatCompletionResponse,
    ErrorResponse,
    ModelsResponse
)
from ...services.claude_service import get_claude_service, ClaudeProcess
from ...services.stream_service import get_stream_service
from ...services.session_manager import get_session_manager
from ...models.session import SessionCreateRequest, SessionUpdateRequest
from ...utils.exceptions import ClaudeAPIError, ValidationError
from ...utils.config import config

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(tags=["chat"])


@router.post("/chat/completions", response_model=None)
async def chat_completions(request: ChatCompletionRequest) -> Union[ChatCompletionResponse, StreamingResponse]:
    """
    创建聊天完成

    完全兼容OpenAI的chat completions API格式。
    支持流式和非流式响应。
    """
    try:
        # 验证请求
        if not request.messages:
            raise ValidationError("Messages cannot be empty")

        # 生成响应ID
        response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}-{int(datetime.now().timestamp())}"

        logger.info(f"Chat completion request received", extra={
            "response_id": response_id,
            "model": request.model,
            "stream": request.stream,
            "message_count": len(request.messages),
            "session_id": request.get_session_id()
        })

        # 获取最后一条用户消息
        last_user_message = request.get_last_user_message()
        if not last_user_message:
            raise ValidationError("No user message found in request")

        # 获取服务实例
        claude_service = get_claude_service()
        session_manager = get_session_manager()

        # 处理会话
        session_id = request.get_session_id()
        if session_id:
            # 更新现有会话或获取会话
            session = await session_manager.get_or_create_session(
                session_id=session_id,
                claude_working_dir=str(config.claude_working_path) if config.claude_working_path is not None else None
            )
            logger.debug(f"Using existing session", extra={
                "session_id": session_id,
                "message_count": session.message_count
            })
        else:
            # 为新请求创建临时会话
            session = await session_manager.create_session(
                SessionCreateRequest(
                    claude_working_dir=str(config.claude_working_path) if config.claude_working_path is not None else None
                )
            )
            session_id = session.session_id
            logger.debug(f"Created temporary session", extra={
                "session_id": session_id
            })

        # 添加用户消息到会话
        await session_manager.add_message_to_session(
            session_id=session_id,
            message=last_user_message
        )

        # 创建Claude进程
        # 对于新会话，不传递session_id，让Claude创建新的会话ID
        # 对于现有会话，传递Claude返回的session_id
        claude_session_id = session.claude_session_id if session.claude_session_id else None
        
        logger.debug(f"Creating Claude process", extra={
            "session_id": session_id,
            "claude_session_id": claude_session_id,
            "continue_session": bool(claude_session_id)
        })

        # 使用get_or_create_process支持进程重用
        claude_process = await claude_service.get_or_create_process(
            session_id=claude_session_id,
            working_dir=str(config.claude_working_path) if config.claude_working_path is not None else None,
            continue_session=bool(claude_session_id)
        )

        # 转换消息为Claude格式
        claude_prompt = request.to_claude_prompt()
        logger.debug(f"Converted to Claude prompt", extra={
            "response_id": response_id,
            "prompt_length": len(claude_prompt)
        })

        if request.stream:
            # 流式响应
            response = await _handle_streaming_response(
                response_id,
                claude_process,
                claude_prompt,
                request.model
            )
        else:
            # 非流式响应
            response = await _handle_non_streaming_response(
                response_id,
                claude_process,
                claude_prompt,
                request.model
            )

        # 更新会话信息，保存Claude返回的session ID
        claude_session_id = claude_process.get_claude_session_id()
        if claude_session_id and claude_session_id != session.claude_session_id:
            update_request = SessionUpdateRequest(claude_session_id=claude_session_id)
            await session_manager.update_session(
                session_id=session_id,
                request=update_request
            )
            logger.info(f"Updated session with Claude session ID", extra={
                "session_id": session_id,
                "claude_session_id": claude_session_id
            })

        return response

    except ValidationError as e:
        logger.warning(f"Validation error in chat completion: {e}")
        raise HTTPException(status_code=400, detail=ErrorResponse.create(
            message=str(e),
            error_type="invalid_request_error",
            param=e.field if hasattr(e, 'field') else None
        ).model_dump())

    except ClaudeAPIError as e:
        logger.error(f"Claude API error in chat completion: {e}")
        raise HTTPException(status_code=500, detail=ErrorResponse.create(
            message=str(e),
            error_type=e.error_code or "internal_server_error"
        ).model_dump())

    except Exception as e:
        logger.error(f"Unexpected error in chat completion: {e}")
        raise HTTPException(status_code=500, detail=ErrorResponse.create(
            message="Internal server error",
            error_type="internal_server_error"
        ).model_dump())


async def _handle_streaming_response(
    response_id: str,
    claude_process: ClaudeProcess,
    claude_prompt: str,
    model: str
) -> StreamingResponse:
    """处理流式响应"""
    try:
        stream_service = get_stream_service()

        async def generate():
            """生成流式响应"""
            try:
                # 发送消息到Claude并获取流式输出
                claude_output = claude_process.send_message(claude_prompt)

                # 转换为OpenAI格式的SSE流
                async for sse_data in stream_service.create_claude_stream(
                    response_id=response_id,
                    claude_output=claude_output,
                    model=model
                ):
                    yield sse_data

            except Exception as e:
                logger.error(f"Error in streaming response generation: {e}", extra={
                    "response_id": response_id
                })
                # 发送错误响应
                yield stream_service._format_sse_data(ErrorResponse.create(
                    message=str(e),
                    error_type="streaming_error"
                ).dict())

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用nginx缓冲
            }
        )

    except Exception as e:
        logger.error(f"Error setting up streaming response: {e}", extra={
            "response_id": response_id
        })
        raise ClaudeAPIError(f"Failed to setup streaming response: {e}")


async def _handle_non_streaming_response(
    response_id: str,
    claude_process: ClaudeProcess,
    claude_prompt: str,
    model: str
) -> ChatCompletionResponse:
    """处理非流式响应"""
    try:
        stream_service = get_stream_service()

        # 发送消息到Claude并收集完整响应
        response_json = await stream_service.create_non_streaming_response(
            response_id=response_id,
            claude_output=claude_process.send_message(claude_prompt),
            model=model
        )

        # 解析JSON并返回响应对象
        response_dict = json.loads(response_json)
        return ChatCompletionResponse(**response_dict)

    except Exception as e:
        logger.error(f"Error in non-streaming response generation: {e}", extra={
            "response_id": response_id
        })
        raise ClaudeAPIError(f"Failed to generate response: {e}")


@router.get("/models")
async def list_models() -> ModelsResponse:
    """
    列出可用模型

    返回支持的模型列表。
    """
    try:
        logger.info("Models list requested")

        # 返回支持的Claude模型
        return ModelsResponse.create_default()

    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=ErrorResponse.create(
            message="Failed to list models",
            error_type="internal_server_error"
        ).model_dump())


# 导出路由器
__all__ = ["router"]