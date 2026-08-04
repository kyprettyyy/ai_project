"""
对话服务层
"""
from typing import AsyncIterator
from langchain_core.messages import HumanMessage
from app.core.gateway_chat_config import get_gateway_chat_client


class ChatService:
    """
    对话服务类
    """
    
    @staticmethod
    async def stream_chat(
        message: str,
        model_name: str = "deepseek/deepseek-chat"
    ) -> AsyncIterator[str]:
        """
        流式对话
        
        Args:
            message: 用户消息
            model_name: 模型名称
            
        Yields:
            流式返回的文本块
        """
        client = get_gateway_chat_client(model_name)
        
        messages = [HumanMessage(content=message)]
        
        async for chunk in client.astream(messages):
            if chunk.content:
                yield chunk.content
    
    @staticmethod
    async def simple_chat(
        message: str,
        model_name: str = "deepseek/deepseek-chat"
    ) -> str:
        """
        简单对话(非流式)
        
        Args:
            message: 用户消息
            model_name: 模型名称
            
        Returns:
            模型回复
        """
        client = get_gateway_chat_client(model_name)
        
        messages = [HumanMessage(content=message)]
        
        response = await client.ainvoke(messages)
        
        return response.content
