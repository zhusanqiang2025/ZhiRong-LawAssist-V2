## 模板web服务示例：

用于展示如何使用基于openai.json Mock一些假数据 用于前后端分离

## 部署说明

### 构建流程
- 使用 `docker/Dockerfile` 进行构建
- 前端构建产物位于 `backend/static/frontend/` 目录
- 提交信息需要包含 `[vendor]` 标签才能触发 vendor 镜像构建

### 最近更新
- 修复了前端构建后的静态文件路径配置
- 更新了 simple_main.py 以支持多路径查找前端文件
