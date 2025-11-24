"""
请求响应日志中间件

将HTTP请求和响应包打印到命令行，用于调试。
"""

import json
import time
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import StreamingResponse
import logging

logger = logging.getLogger(__name__)


async def log_requests_middleware(request: Request, call_next: Callable) -> Response:
    """
    记录HTTP请求和响应的中间件
    
    Args:
        request: FastAPI请求对象
        call_next: 下一个中间件或路由处理器
        
    Returns:
        Response: 响应对象
    """
    start_time = time.time()
    
    # 打印请求信息
    print("\n" + "="*80)
    print(f"🔵 HTTP请求 [{request.method}] {request.url}")
    print("="*80)
    
    # 打印请求头
    print("📋 请求头:")
    for name, value in request.headers.items():
        # 隐藏敏感信息
        if name.lower() in ['authorization', 'cookie', 'x-api-key']:
            value = "***HIDDEN***"
        print(f"  {name}: {value}")
    
    # 打印查询参数
    if request.query_params:
        print("🔍 查询参数:")
        for key, value in request.query_params.items():
            print(f"  {key}: {value}")
    
    # 读取并打印请求体（使用更安全的方式）
    request_body_logged = False
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            # 使用form()或json()方法，这些方法会正确处理请求体
            content_type = request.headers.get("content-type", "")
            
            if "application/json" in content_type:
                try:
                    json_data = await request.json()
                    print("📦 请求体 (JSON):")
                    print(json.dumps(json_data, indent=2, ensure_ascii=False))
                    request_body_logged = True
                except Exception:
                    pass
            
            if not request_body_logged:
                # 对于其他类型的请求体，尝试读取原始数据
                try:
                    body_bytes = await request.body()
                    if body_bytes:
                        body_str = body_bytes.decode('utf-8', errors='ignore')
                        print("📦 请求体:")
                        print(body_str[:1000] + ("..." if len(body_str) > 1000 else ""))
                    else:
                        print("📦 请求体: (空)")
                except Exception as e:
                    print(f"📦 请求体读取失败: {e}")
                    
        except Exception as e:
            print(f"📦 请求体处理失败: {e}")
    
    # 不再修改request对象的内部方法
    
    # 调用下一个处理器
    try:
        response = await call_next(request)
        
        # 计算处理时间
        process_time = time.time() - start_time
        
        # 打印响应信息
        print("\n" + "-"*80)
        print(f"🟢 HTTP响应 [{response.status_code}] - 耗时: {process_time:.3f}s")
        print("-"*80)
        
        # 打印响应头
        print("📋 响应头:")
        for name, value in response.headers.items():
            print(f"  {name}: {value}")
        
        # 处理响应体
        if isinstance(response, StreamingResponse):
            print("📦 响应体: (流式响应)")
            
            # 包装流式响应以记录内容
            original_body_iterator = response.body_iterator
            
            async def logged_body_iterator():
                print("🔄 流式响应内容:")
                async for chunk in original_body_iterator:
                    if isinstance(chunk, bytes):
                        chunk_str = chunk.decode('utf-8', errors='ignore')
                        print(f"  📄 数据块: {chunk_str.strip()}")
                    yield chunk
                print("✅ 流式响应结束")
            
            response.body_iterator = logged_body_iterator()
            
        else:
            # 对于普通响应，尝试读取响应体
            if hasattr(response, 'body') and response.body:
                try:
                    body_str = response.body.decode('utf-8')
                    print("📦 响应体:")
                    try:
                        # 尝试格式化JSON
                        json_data = json.loads(body_str)
                        print(json.dumps(json_data, indent=2, ensure_ascii=False))
                    except json.JSONDecodeError:
                        # 如果不是JSON，直接打印
                        print(body_str)
                except Exception as e:
                    print(f"📦 响应体读取失败: {e}")
            else:
                print("📦 响应体: (空)")
        
        print("="*80 + "\n")
        
        return response
        
    except Exception as e:
        # 处理异常
        process_time = time.time() - start_time
        print("\n" + "-"*80)
        print(f"🔴 HTTP异常 - 耗时: {process_time:.3f}s")
        print("-"*80)
        print(f"❌ 异常类型: {type(e).__name__}")
        print(f"❌ 异常信息: {str(e)}")
        
        # 记录到日志系统
        logger.error(f"请求处理异常: {request.method} {request.url} - {str(e)}", exc_info=True)
        
        print("="*80 + "\n")
        raise


def add_request_logging_middleware(app):
    """
    添加请求日志中间件到FastAPI应用
    
    Args:
        app: FastAPI应用实例
    """
    app.middleware("http")(log_requests_middleware)
    print("✅ 请求响应日志中间件已启用 - 所有HTTP请求和响应将打印到命令行")