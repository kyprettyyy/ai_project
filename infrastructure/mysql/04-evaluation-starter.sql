USE evalroute_evaluation;

INSERT INTO scene
  (id, userId, name, description, category, isPreset, isActive, isDelete)
VALUES
  ('7c4ef4d2-93c1-4b80-8078-1a7f24e77ac1', 1, 'EvalRoute 基础能力集',
   '覆盖摘要、分类、抽取、数学、代码和问答，用于验证评测链路。', '综合', 1, 1, 0)
ON DUPLICATE KEY UPDATE name=VALUES(name), description=VALUES(description), isActive=1, isDelete=0;

INSERT INTO scene_prompt
  (id, sceneId, userId, promptIndex, title, content, difficulty, tags, expectedOutput, isDelete)
VALUES
  ('ae107d82-5d6e-4546-ad65-1fd00be07871', '7c4ef4d2-93c1-4b80-8078-1a7f24e77ac1', 1, 0,
   '客服行动项摘要', '将以下客服记录压缩为三条行动项：客户无法登录，重置密码邮件未收到，账号绑定了旧手机号。', 'easy', '["summarization"]', '检查邮件投递；验证身份；更新手机号并重置密码。', 0),
  ('5da76214-8131-4d69-8c88-607dc84c1af9', '7c4ef4d2-93c1-4b80-8078-1a7f24e77ac1', 1, 1,
   '工单分类', '将工单分类为 billing、technical 或 account：扣款成功但余额未到账。', 'easy', '["classification"]', 'billing', 0),
  ('af954ced-fc90-4653-9c41-1be639130b20', '7c4ef4d2-93c1-4b80-8078-1a7f24e77ac1', 1, 2,
   '结构化抽取', '从文本提取公司、金额和日期：北辰科技于2026年3月12日支付人民币18,500元。', 'easy', '["extraction"]', '{"company":"北辰科技","amount":18500,"currency":"CNY","date":"2026-03-12"}', 0),
  ('f6dc9c89-b308-40b6-917b-1acb0b52bf87', '7c4ef4d2-93c1-4b80-8078-1a7f24e77ac1', 1, 3,
   'Token 成本计算', '每百万输入 Token 2 元、输出 Token 8 元。本次输入25万、输出5万 Token，成本多少元？', 'easy', '["math"]', '0.9 元', 0),
  ('ce4eff80-d91f-4e0c-84e8-f0458c134b85', '7c4ef4d2-93c1-4b80-8078-1a7f24e77ac1', 1, 4,
   'Python 顺序去重', '写一个 Python 函数，将列表按元素首次出现顺序去重，并说明时间复杂度。', 'easy', '["code"]', '使用 set 记录已见元素，单次遍历，平均 O(n)。', 0),
  ('d7ff438b-af0d-4d49-9eb1-1dbbd03791c4', '7c4ef4d2-93c1-4b80-8078-1a7f24e77ac1', 1, 5,
   '评测可复现性', '为什么模型评测请求应显式指定模型，而在线请求可以使用自动路由？', 'medium', '["qa"]', '评测需要控制变量和可复现；在线请求优化综合目标。', 0)
ON DUPLICATE KEY UPDATE title=VALUES(title), content=VALUES(content), expectedOutput=VALUES(expectedOutput), isDelete=0;

INSERT INTO prompt_template
  (id, userId, name, description, strategy, content, variables, category, isPreset, usageCount, isActive, isDelete)
VALUES
  ('evalroute-rubric-v1', NULL, '结构化评分 Rubric', '要求评分器返回维度分和可审计理由。', 'direct',
   '依据给定参考答案，从 correctness、relevance、clarity 三个维度对候选答案评分，并返回 JSON。\n问题：{question}\n参考：{reference}\n候选：{answer}',
   '["question","reference","answer"]', 'evaluation', 1, 0, 1, 0)
ON DUPLICATE KEY UPDATE content=VALUES(content), description=VALUES(description), isActive=1, isDelete=0;
