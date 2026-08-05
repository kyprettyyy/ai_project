# EvalRoute Gateway Service

FastAPI 网关集成原型。研究相关范围是模型目录、OpenAI 兼容调用、约束感知路由、有限回退和路由审计。计费、充值、插件、完整用户后台等历史模块不属于路由研究贡献，来源与边界见仓库根目录的 `docs/PROVENANCE.md`。

供应商适配器中的 DashScope、DeepSeek 和 Zhipu 类有意保持为薄包装：这些供应商当前都通过 OpenAI 兼容协议调用，薄类只声明供应商匹配；URL 规范化、请求构造、流式响应和用量解析集中在 `openai_adapter.py`。这不代表已经实现三套独立原生 SDK，也不应据此扩大功能宣传。

```bash
pip install -r requirements.txt
python run.py
```

运行单元测试：

```bash
python -m unittest discover -s tests -v
```

生产使用前仍需完成认证、密钥管理、限流、支付、审计日志和故障恢复的专项评审。
