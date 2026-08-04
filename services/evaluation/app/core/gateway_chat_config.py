"""Backward-compatible LangChain factory backed by the EvalRoute gateway."""

from langchain_openai import ChatOpenAI

from app.core.config import get_settings


def get_gateway_chat_client(model_name: str = "qwen-plus") -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=model_name,
        openai_api_key=settings.GATEWAY_API_KEY,
        openai_api_base=settings.gateway_openai_base_url,
        default_headers={"X-Client": "EvalRoute Evaluation"},
        temperature=0.7,
        max_tokens=2000,
        streaming=True,
    )
