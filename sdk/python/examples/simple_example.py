"""Simple SDK usage example."""

from __future__ import annotations

import os

from evalroute_sdk import EvalRouteClient


def main() -> None:
    api_key = os.getenv("EVALROUTE_API_KEY", "")
    base_url = os.getenv("EVALROUTE_BASE_URL", "http://localhost:8123/api")
    client = EvalRouteClient.builder().api_key(api_key).base_url(base_url).build()
    try:
        response = client.chat("你好，请介绍一下自己")
        print(f"响应: {response.content}")
        print("\nToken 统计:")
        print(f"输入: {response.usage.prompt_tokens}")
        print(f"输出: {response.usage.completion_tokens}")
        print(f"总计: {response.usage.total_tokens}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
