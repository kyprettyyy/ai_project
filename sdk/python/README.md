# EvalRoute Python SDK

这是当前网关 OpenAI 兼容接口的轻量 Python 客户端。

```python
from evalroute_sdk import ChatMessage, ChatRequest, EvalRouteClient

client = EvalRouteClient(api_key="your-local-api-key")
response = client.chat(ChatRequest(messages=[ChatMessage.user("hello")]))
print(response.content)
```

该 SDK 处于原型阶段。接口稳定性、重试策略和发布流程尚未达到公共包承诺标准。
