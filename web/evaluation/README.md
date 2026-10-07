# EvalRoute Evaluation Workbench

EvalRoute 评测服务的 Vue 3 工作台。该目录迁移自 `yuyuanweb/ai-test` 的前端并适配当前 Python 评测 API；它不是从零开发的独立前端。上游当前未发现许可证，未经授权不应重新分发。详见仓库根目录的 `NOTICE` 与 `docs/PROVENANCE.md`。

## 环境要求

- Node.js 22+

## 技术栈

- Vue 3
- Vite
- TypeScript
- Ant Design Vue
- Axios
- Pinia
- Vue Router

## 开发

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码格式化
npm run format

# 代码检查
npm run lint
```

## 生成 API 代码

```bash
npm run openapi2ts
```

生成后需要审查端点命名和响应类型，避免把旧后端的控制器名称重新带入主代码。

## 目录结构

```
src/
├── api/           # API 接口定义
├── assets/        # 静态资源
├── components/    # 公共组件
├── config/        # 配置文件
├── layouts/       # 布局组件
├── pages/         # 页面组件
├── router/        # 路由配置
├── stores/        # Pinia 状态管理
└── utils/         # 工具函数
```
