# 融合决策

两个项目没有被粗暴合并为一个后端进程，而是按 PDF 的边界保留为两个 Python 服务：Gateway 负责统一模型调用与在线决策，Evaluation 负责数据集、批量实验、评分和报告。两者只通过稳定的 HTTP API 交互。

融合的核心不是目录搬运，而是数据闭环：

1. Evaluation 同步 Gateway 的模型目录。
2. 批量评测显式指定模型，保证评测可复现。
3. Gateway 返回 trace、provider、latency、cost、fallback 和 evaluation run metadata。
4. Evaluation 聚合质量、延迟、成本、可靠性，形成模型 × 任务类型画像。
5. 画像通过内部服务令牌回写 Gateway。
6. 在线请求不指定模型时，Gateway 依据画像和请求权重进行排序，并记录完整决策。

基础设施使用一个 MySQL 容器承载 `evalroute_gateway` 与 `evalroute_evaluation` 两个逻辑库，分别使用独立账号；Redis 使用 DB 0，并以 `gateway:` 与 `evaluation:` 前缀隔离。RabbitMQ、Java、Go 和非 Python SDK 均不在当前主链路中。
