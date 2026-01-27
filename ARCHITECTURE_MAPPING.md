# 智融法助2.0 - 架构映射文档

> **文档目的**: 确保在调试和测试中能准确找到每个功能模块对应的代码文件

---

## 📋 功能模块总览

应用共包含 **10 个主功能模块** + **管理后台** + **辅助功能页面**，分为 3 大类：

### 🎯 咨询类 (3个模块)
- 智能咨询
- 风险评估
- 案件分析

### 📄 合同类 (3个模块)
- 合同生成
- 合同审查
- 模板查询

### 🛠️ 工具类 (3个模块)
- 文档处理
- 文书起草
- 费用测算

### 🤖 智能引导 (1个模块)
- 智能引导 (首页Banner入口)

---

## 1️⃣ 智能咨询

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/consultation` |
| **分类** | 咨询类 |
| **功能描述** | 资深律师为您提供专业的法律咨询服务 |

### 前端文件
```
frontend/src/pages/LegalConsultationPage.tsx
frontend/src/pages/LegalConsultationPage.css
```

### 后端API
```
API路由文件:
├── backend/app/api/consultation_router.py
└── backend/app/api/v1/endpoints/smart_chat.py (expert-consultation)

服务文件:
├── backend/app/services/consultation/
└── backend/app/services/deepseek_service.py

主要端点:
├── POST /api/consultation/upload          - 上传咨询文件
├── POST /api/consultation                 - 发起咨询
└── POST /api/v1/smart-chat/expert-consultation - 专家咨询
```

### 数据模型
```
backend/app/models/consultation.py (如果存在)
```

---

## 2️⃣ 风险评估

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/risk-analysis` |
| **分类** | 咨询类 |
| **功能描述** | 深度分析法律文件，识别潜在风险点 |

### 前端文件
```
frontend/src/pages/RiskAnalysisPageV2.tsx      (当前版本)
frontend/src/pages/RiskAnalysisPage.tsx        (旧版本)
```

### 后端API
```
API路由文件:
├── backend/app/api/v1/endpoints/risk_analysis.py
└── backend/app/api/v1/endpoints/risk_analysis_v2.py

服务文件:
└── backend/app/services/risk_analysis/

主要端点:
├── POST /api/v1/risk-analysis/submit                    - 提交分析
├── POST /api/v1/risk-analysis/upload                    - 上传文档
├── POST /api/v1/risk-analysis/start/{session_id}        - 开始分析
├── GET  /api/v1/risk-analysis/result/{session_id}       - 获取结果
└── WS   /api/v1/risk-analysis/ws/{session_id}           - WebSocket进度
```

### 数据模型
```
backend/app/models/risk_analysis.py
```

---

## 3️⃣ 案件分析

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/litigation-analysis` |
| **分类** | 咨询类 |
| **功能描述** | 分析案件材料，制定诉讼策略 |

### 前端文件
```
frontend/src/pages/LitigationAnalysisPage.tsx
```

### 后端API
```
API路由文件:
└── backend/app/api/v1/endpoints/litigation_analysis.py

服务文件:
└── backend/app/services/litigation_analysis/
    └── workflow.py

主要端点:
├── POST /api/v1/litigation-analysis/start                      - 开始分析
├── GET  /api/v1/litigation-analysis/result/{session_id}        - 获取结果
├── GET  /api/v1/litigation-analysis/report/{session_id}/download - 下载报告
└── WS   /api/v1/litigation-analysis/ws/{session_id}            - WebSocket进度
```

### 数据模型
```
backend/app/models/litigation_analysis.py
```

---

## 4️⃣ 合同生成

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/contract/generate` |
| **分类** | 合同类 |
| **功能描述** | 基于需求智能生成各类合同文书 |

### 前端文件
```
frontend/src/pages/ContractGenerationPage.tsx
```

### 后端API
```
API路由文件:
├── backend/app/api/contract_generation_router.py
└── backend/app/api/v1/endpoints/contract_templates.py

服务文件:
└── backend/app/services/contract_generation/
    ├── workflow.py
    ├── agents/
    ├── rag/
    ├── structural/
    └── tools/

主要端点:
├── POST /api/contract-generation/analyze          - 分析需求
├── POST /api/contract-generation/generate         - 生成合同
├── POST /api/contract-generation/process-document - 处理文档
└── POST /api/v1/contract                          - 模板管理
```

### 数据模型
```
backend/app/models/contract_template.py
```

---

## 5️⃣ 合同审查

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/contract/review` |
| **分类** | 合同类 |
| **功能描述** | 专业审查合同条款，识别潜在风险 |

### 前端文件
```
frontend/src/pages/ContractReview.tsx             (新版本)
```

### 后端API
```
API路由文件:
└── backend/app/api/contract_router.py

服务文件:
├── backend/app/services/contract_review_service.py
├── backend/app/services/contract_review/
└── backend/app/services/langgraph_review_service.py

主要端点:
├── POST /api/contract/upload                      - 上传合同
├── POST /api/contract/{contract_id}/deep-review   - 开始深度审查
└── POST /api/contract/{contract_id}/apply-revisions - 应用修订
```

### 数据模型
```
backend/app/models/contract.py
```

---

## 6️⃣ 模板查询

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/contract` |
| **分类** | 合同类 |
| **功能描述** | 查找合适的法律文书模板 |

### 前端文件
```
frontend/src/pages/ContractPage.tsx
```

### 后端API
```
API路由文件:
└── backend/app/api/v1/endpoints/contract_templates.py

服务文件:
├── backend/app/services/template_feature_extractor.py
└── backend/app/services/common/contract_knowledge_db_service.py

主要端点:
├── GET  /api/v1/contract/                       - 获取模板列表
├── GET  /api/v1/contract/{template_id}/content  - 获取模板内容
└── POST /api/v1/contract/upload                 - 上传模板
```

### 数据模型
```
backend/app/models/contract_template.py
backend/app/models/category.py
```

---

## 7️⃣ 文档处理

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/document-processing` |
| **分类** | 工具类 |
| **功能描述** | 文档预处理、智能编辑、文件比对 |

### 前端文件
```
frontend/src/pages/DocumentProcessingPage.tsx
```

### 后端API
```
API路由文件:
├── backend/app/api/document_router.py
└── backend/app/api/v1/preprocessor_router.py

服务文件:
├── backend/app/services/document_preprocessor.py
└── backend/app/services/unified_document_service.py

主要端点:
├── POST /api/document/generate-from-content       - 从AI内容生成
├── POST /api/document/process-file-to-standard    - 标准化文件
├── POST /api/preprocessor/convert                 - 格式转换
└── POST /api/preprocessor/convert-async           - 异步转换
```

---

## 8️⃣ 文书起草

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/document-drafting` |
| **分类** | 工具类 |
| **功能描述** | 起草各类司法文书和函件 |

### 前端文件
```
frontend/src/pages/DocumentDraftingPage.tsx
```

### 后端API
```
API路由文件:
└── backend/app/api/v1/endpoints/document_drafting.py

服务文件:
└── backend/app/services/document_drafting/
    └── workflow.py

主要端点:
├── GET  /api/v1/document-drafting/templates   - 获取文书模板
├── POST /api/v1/document-drafting/analyze     - 分析需求
└── POST /api/v1/document-drafting/generate    - 生成文书
```

### 数据模型
```
backend/app/models/document_drafting.py (如果存在)
```

---

## 9️⃣ 费用测算

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/cost-calculation` |
| **分类** | 工具类 |
| **功能描述** | 计算诉讼费用、律师费等 |

### 前端文件
```
frontend/src/pages/CostCalculationPage.tsx
```

### 后端API
```
API路由文件:
└── backend/app/api/cost_calculation_router.py

服务文件:
└── backend/app/services/unified_document_service.py

主要端点:
├── POST /api/cost-calculation/upload      - 上传案件文档
├── POST /api/cost-calculation/extract     - 提取案件信息
└── POST /api/cost-calculation/calculate-v2 - 计算费用
```

---

## 🔟 智能引导

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/guidance` |
| **分类** | 智能引导 |
| **功能描述** | AI对话引导用户选择合适的功能模块 |
| **入口** | 首页Banner"开始智能引导"按钮 |

### 前端文件
```
frontend/src/pages/IntelligentGuidancePage.tsx
frontend/src/pages/IntelligentGuidancePage.css
frontend/src/components/ModuleNavBar/EnhancedModuleNavBar.tsx
```

### 后端API
```
API路由文件:
├── backend/app/api/v1/endpoints/smart_chat.py (guidance)
└── backend/app/api/v1/endpoints/search.py

服务文件:
└── backend/app/services/deepseek_service.py

主要端点:
├── POST /api/v1/smart-chat/guidance   - 智能引导对话
└── GET  /api/v1/search/global         - 全局搜索
```

### 引导流程 (4步骤)
```
1. 需求探索 - 了解用户的具体需求
2. 场景识别 - 确定适用的法律场景
3. 方案推荐 - 推荐最适合的解决方案
4. 行动引导 - 引导用户开始使用对应功能
```

### 快速入口支持
- 智能咨询
- 风险评估
- 合同生成
- 案件分析

---

## 1️⃣1️⃣ 场景选择

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/scene-selection` |
| **分类** | 辅助功能 |
| **功能描述** | 选择法律场景后跳转到对应功能模块 |

### 前端文件
```
frontend/src/pages/SceneSelectionPage.tsx
```

---

## 1️⃣2️⃣ 智能对话

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/smart-chat` |
| **分类** | 辅助功能 |
| **功能描述** | 通用智能对话界面 |

### 前端文件
```
frontend/src/pages/SmartChatPage.tsx
```

### 后端API
```
API路由文件:
└── backend/app/api/v1/endpoints/smart_chat.py

主要端点:
├── POST /api/v1/smart-chat/guidance       - 智能引导
├── POST /api/v1/smart-chat/expert-consultation - 专家咨询
└── POST /api/v1/smart-chat/general        - 通用对话
```

---

## 1️⃣3️⃣ 合同规划

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/contract/planning` |
| **分类** | 合同类辅助功能 |
| **功能描述** | 合同规划与策略生成 |

### 前端文件
```
frontend/src/pages/ContractPlanningPage.tsx
```

---

## 1️⃣4️⃣ 合同审查历史

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/contract/review-history` |
| **分类** | 合同类辅助功能 |
| **功能描述** | 查看历史合同审查记录 |

### 前端文件
```
frontend/src/pages/ContractReviewHistory.tsx
```

---

## 1️⃣5️⃣ 知识库管理

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/knowledge-base/*` |
| **分类** | 辅助功能 |
| **功能描述** | 知识库配置、测试、用户知识库管理 |

### 前端文件
```
frontend/src/pages/KnowledgeBaseConfigPage.tsx      # 知识库配置
frontend/src/pages/KnowledgeBaseTestPage.tsx        # 知识库测试
frontend/src/pages/UserKnowledgeBasePage.tsx        # 用户知识库
```

### 后端API
```
API路由文件:
├── backend/app/api/v1/endpoints/knowledge_base.py
└── backend/app/api/v1/endpoints/rag_management.py

主要端点:
├── POST /api/v1/knowledge-base/create              - 创建知识库
├── GET  /api/v1/knowledge-base/list                - 获取知识库列表
├── POST /api/v1/knowledge-base/upload              - 上传文档
├── POST /api/v1/rag/query                          - RAG查询
└── DELETE /api/v1/knowledge-base/{kb_id}           - 删除知识库
```

### 数据模型
```
backend/app/models/knowledge_base.py
```

---

## 1️⃣6️⃣ 模板编辑

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/template/edit` |
| **分类** | 辅助功能 |
| **功能描述** | 编辑合同模板 |

### 前端文件
```
frontend/src/pages/TemplateEditPage.tsx
```

---

## 🔧 管理后台

### 基本信息
| 项目 | 值 |
|------|------|
| **路由** | `/admin` |
| **权限** | 管理员 only |
| **功能描述** | 模板、分类、用户、统计管理 |

### 前端文件
```
frontend/src/pages/AdminPage.tsx

子模块组件 (位于 views/ 目录):
├── frontend/src/pages/admin/views/DashboardView.tsx
├── frontend/src/pages/admin/views/CategoryManager.tsx
├── frontend/src/pages/admin/views/KnowledgeGraphManager.tsx
├── frontend/src/pages/admin/views/TemplateManager.tsx
├── frontend/src/pages/admin/views/ReviewRulesManager.tsx
├── frontend/src/pages/admin/views/RiskRulePackagesManager.tsx
├── frontend/src/pages/admin/views/LitigationRulePackagesManager.tsx
└── frontend/src/pages/admin/views/CeleryMonitor.tsx
```

### 后端API
```
API路由文件:
└── backend/app/api/v1/endpoints/admin.py

主要端点:
├── GET  /api/v1/admin/stats          - 系统统计
├── GET  /api/v1/admin/users          - 用户管理
└── (各子模块的CRUD端点)
```

---

## 📁 核心架构文件

### 前端核心文件
```
frontend/src/
├── App.tsx                              # 主路由配置
├── api/index.ts                         # API客户端
├── context/AuthContext.tsx              # 认证上下文
├── context/SessionContext.tsx           # 会话管理
├── components/ErrorBoundary.tsx         # 错误边界
└── components/ModuleNavBar/             # 导航组件
```

### 后端核心文件
```
backend/app/
├── main.py                              # FastAPI应用入口
├── api/v1/router.py                     # 主路由聚合
├── api/deps.py                          # 依赖注入
├── models/                              # 数据模型目录
├── services/                            # 业务逻辑目录
└── core/config.py                       # 配置管理
```

### 后端 API 端点文件
```
backend/app/api/v1/endpoints/
├── admin.py                             # 管理后台
├── auth.py                              # 用户认证
├── categories.py                        # 分类管理
├── celery_monitor.py                    # Celery监控
├── consultation_history.py              # 咨询历史
├── contract_knowledge_graph_db.py       # 合同知识图谱
├── contract_templates.py                # 合同模板
├── document_drafting.py                 # 文档起草
├── health.py                            # 健康检查
├── knowledge_base.py                    # 知识库管理
├── legal_features_management.py         # 法律功能管理
├── litigation_analysis.py               # 案件分析
├── rag_management.py                    # RAG管理
├── risk_analysis.py                     # 风险评估
├── search.py                            # 全局搜索
├── smart_chat.py                        # 智能对话
└── tasks.py                             # 任务管理
```

### 通用服务
```
backend/app/services/
├── unified_document_service.py          # 统一文档服务
├── document_renderer.py                 # 文档渲染
└── file_service.py                      # 文件管理
```

---

## 🗄️ 数据库模型

```
backend/app/models/
├── base.py                              # Base模型
├── user.py                              # 用户模型
├── contract.py                          # 合同模型
├── contract_template.py                 # 合同模板
├── contract_knowledge.py                # 合同知识
├── contract_review_task.py              # 合同审查任务
├── risk_analysis.py                     # 风险分析
├── risk_analysis_preorganization.py     # 风险分析预组织
├── litigation_analysis.py               # 诉讼分析
├── consultation_history.py              # 咨询历史
├── knowledge_base.py                    # 知识库模型
├── rule.py                              # 规则模型
├── task.py                              # 任务模型
├── task_view.py                         # 任务视图
└── category.py                          # 分类模型
```

---

## 🔄 任务管理

### 异步任务
```
路由: /result/:taskId
前端: frontend/src/pages/ResultPage.tsx
后端: backend/app/api/v1/endpoints/tasks.py
队列: Celery + Redis
```

---

## 🌐 全局搜索

### 搜索功能
```
端点: GET /api/v1/search/global
组件: frontend/src/components/SearchResults.tsx
覆盖: 功能模块、任务、法条
```

---

## 📝 调试索引

| 当用户说... | 对应模块 |
|------------|----------|
| "智能咨询" | `/consultation` → LegalConsultationPage.tsx |
| "风险评估" | `/risk-analysis` → RiskAnalysisPageV2.tsx |
| "案件分析" | `/litigation-analysis` → LitigationAnalysisPage.tsx |
| "合同生成" | `/contract/generate` → ContractGenerationPage.tsx |
| "合同审查" | `/contract/review` → ContractReview.tsx |
| "模板查询" | `/contract` → ContractPage.tsx |
| "文档处理" | `/document-processing` → DocumentProcessingPage.tsx |
| "文书起草" | `/document-drafting` → DocumentDraftingPage.tsx |
| "费用测算" | `/cost-calculation` → CostCalculationPage.tsx |
| "智能引导" | `/guidance` → IntelligentGuidancePage.tsx |
| "场景选择" | `/scene-selection` → SceneSelectionPage.tsx |
| "智能对话" | `/smart-chat` → SmartChatPage.tsx |
| "合同规划" | `/contract/planning` → ContractPlanningPage.tsx |
| "知识库" | `/knowledge-base/*` → KnowledgeBaseConfigPage.tsx |
| "管理后台" | `/admin` → AdminPage.tsx |

---

## 📞 快速定位

当你听到问题时，按以下步骤定位：

1. **确定模块名称** - 使用上面的调试索引
2. **前端定位** - 查看 `frontend/src/pages/[模块名].tsx`
3. **后端定位** - 查看 `backend/app/api/*router.py` 或 `endpoints/*.py`
4. **服务定位** - 查看 `backend/app/services/[模块名]/`
5. **模型定位** - 查看 `backend/app/models/[模块名].py`

---

## 🐳 Docker 部署环境

### 部署架构

应用采用 **Docker Compose** 多容器部署架构，包含以下服务：

```
┌─────────────────────────────────────────────────────────────────┐
│                         Docker 网络层                            │
│                      (app-network bridge)                        │
└─────────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Frontend   │   │   Backend    │   │  PostgreSQL  │
│   (Nginx)    │◄──│  (FastAPI)   │◄──│   Database   │
│   Port:3000  │   │   Port:8000  │   │   Port:5432  │
└──────────────┘   └──────────────┘   └──────────────┘
        │                   │                   │
        │                   ▼                   ▼
        │          ┌──────────────┐   ┌──────────────┐
        │          │  ONLYOFFICE  │   │    Redis     │
        │          │   DocServer  │   │   (Celery)   │
        │          │   Port:8082  │   │   Port:6379  │
        │          └──────────────┘   └──────────────┘
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Celery     │   │   Celery     │   │    Flower    │
│   Workers    │   │    Beat      │   │  (Monitor)   │
│  (Priority)  │   │  (Scheduler) │   │   Port:5555  │
└──────────────┘   └──────────────┘   └──────────────┘
```

### 服务清单

| 服务名 | 容器名 | 镜像/构建 | 端口映射 | 说明 |
|--------|--------|-----------|----------|------|
| **frontend** | legal_assistant_v3_frontend | ./frontend/Dockerfile | 3000:80 | React + Nginx |
| **backend** | legal_assistant_v3_backend | ./backend/Dockerfile | 8000:8000 | FastAPI + Uvicorn |
| **db** | legal_assistant_v3_db | postgres:15-alpine | - | PostgreSQL 数据库 |
| **redis** | legal_assistant_v3_redis | redis:7-alpine | - | Celery 消息队列 |
| **onlyoffice** | legal_assistant_v3_onlyoffice | onlyoffice/documentserver | 8082:80 | 在线文档编辑器 |
| **celery-worker-medium** | legal_assistant_v3_celery_worker_medium | legal_document_assistantv3-backend:latest | - | 中优先级任务队列 |
| **celery-flower** | legal_assistant_v3_celery_flower | legal_document_assistantv3-backend:latest | 5555:5555 | Celery 监控面板 |

### Docker 配置文件

| 文件 | 用途 |
|------|------|
| `docker-compose.yml` | 生产环境部署配置 |
| `docker-compose.local.yml` | 本地开发轻量配置 (SQLite) |
| `docker-compose.dev.yml` | 开发环境配置 |
| `docker-compose.build.yml` | 构建环境配置 |
| `backend/Dockerfile` | 后端容器构建文件 |
| `backend/Dockerfile.local` | 后端本地开发构建文件 |
| `backend/Dockerfile.alpine` | 后端 Alpine 轻量版本 |
| `docker/Dockerfile` | Docker 通用构建文件 |
| `docker/Dockerfile.vendor` | Vendor 构建文件 |
| `frontend/Dockerfile` | 前端容器构建文件 |

### 环境变量配置

| 配置文件 | 说明 |
|----------|------|
| `.env` | 生产环境变量 (根目录) |
| `.env.example` | 环境变量模板 |
| `backend/.env` | 后端专用环境变量 |

### 数据持久化 (Volumes)

```yaml
volumes:
  pgdata:                    # PostgreSQL 数据
  redis_data:                # Redis 持久化
  onlyoffice_data:           # ONLYOFFICE 数据
  onlyoffice_log:            # ONLYOFFICE 日志
  onlyoffice_cache:          # ONLYOFFICE 缓存
  onlyoffice_fonts_cache:    # ONLYOFFICE 字体缓存
```

### 目录挂载

```yaml
# 后端开发挂载
./backend:/app:rw           # 代码热重载
./storage:/app/storage:rw   # 文件存储

# 前端构建挂载 (build阶段)
./frontend → /app (构建时)
```

---

## 🚀 部署命令

### 启动服务

```bash
# 生产环境 (完整服务)
docker-compose up -d

# 本地开发 (轻量服务)
docker-compose -f docker-compose.local.yml up -d

# 开发环境
docker-compose -f docker-compose.dev.yml up -d
```

### 构建镜像

```bash
# 构建后端镜像
docker-compose build backend

# 构建前端镜像
docker-compose build frontend

# 强制重建 (不带缓存)
docker-compose build --no-cache
```

### 服务管理

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 重启服务
docker-compose restart backend

# 停止所有服务
docker-compose down

# 停止并删除数据卷 (谨慎使用)
docker-compose down -v
```

### 进入容器调试

```bash
# 进入后端容器
docker-compose exec backend bash

# 进入数据库容器
docker-compose exec db psql -U admin -d legal_assistant_db

# 进入 Redis 容器
docker-compose exec redis redis-cli
```

---

## 🔌 端口映射

| 服务 | 容器内端口 | 宿主机端口 | 访问地址 |
|------|-----------|-----------|----------|
| **Frontend** | 80 | 3000 | http://localhost:3000 |
| **Backend API** | 8000 | 8000 | http://localhost:8000 |
| **API Docs** | 8000 | 8000 | http://localhost:8000/docs |
| **ONLYOFFICE** | 80 | 8082 | http://localhost:8082 |
| **Flower** | 5555 | 5555 | http://localhost:5555 |
| **PostgreSQL** | 5432 | - | 容器内访问 |
| **Redis** | 6379 | - | 容器内访问 |

---

## 🌐 网络架构

```
网络名称: app-network (bridge driver)

服务互联:
- frontend → backend (API调用)
- backend → db (数据库)
- backend → redis (Celery)
- backend → onlyoffice (文档编辑)
- celery-workers → redis (任务队列)
- celery-flower → redis (监控)
```

---

## 🔧 外部服务配置

### AI 服务 (环境变量)

| 服务 | 环境变量 | 配置值 |
|------|----------|--------|
| **LangChain API** | `LANGCHAIN_API_KEY` | `7adb34bf-3cb3-4dea-af41-b79de8c08ca3` |
| **LangChain Base URL** | `LANGCHAIN_API_BASE_URL` | `https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1` |
| **Model Name** | `MODEL_NAME` | `Qwen3-235B-A22B-Thinking-2507` |
| **OpenAI API Key** | `OPENAI_API_KEY` | `7adb34bf-3cb3-4dea-af41-b79de8c08ca3` |
| **OpenAI Base URL** | `OPENAI_API_BASE` | `https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1` |

### 文档处理服务

| 服务 | 环境变量 | 配置值 |
|------|----------|--------|
| **MinerU API** | `MINERU_API_URL` | `http://115.190.40.198:7231/v2/parse/file` |
| **MinerU Timeout** | `MINERU_API_TIMEOUT` | 120 |
| **OCR API** | `OCR_API_URL` | `http://115.190.43.141:8002/ocr/v1/recognize-text` |
| **OCR Timeout** | `OCR_API_TIMEOUT` | 60 |

### 数据库配置

| 配置项 | 值 |
|--------|-----|
| **数据库类型** | PostgreSQL 15 |
| **数据库名** | `legal_assistant_db` |
| **用户名** | `admin` |
| **密码** | `01689101Abc` |
| **连接地址** | `db:5432` (容器内) |

---

## 📦 镜像加速配置

### 后端 (Dockerfile)

```dockerfile
# 使用中国科技大学镜像源
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources

# 使用清华大学 PyPI 镜像
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 前端 (Dockerfile)

```dockerfile
# 使用阿里云 Alpine 镜像源
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories

# 使用 npmmirror 镜像
RUN npm install --registry=https://registry.npmmirror.com
```

---

## 🛠️ 故障排查

### 常见问题

| 问题 | 解决方案 |
|------|----------|
| **容器无法启动** | `docker-compose logs <service>` 查看日志 |
| **端口冲突** | 修改 `docker-compose.yml` 中的端口映射 |
| **数据库连接失败** | 检查 `db` 服务是否健康: `docker-compose ps` |
| **前端无法访问后端** | 检查 `VITE_API_BASE_URL` 环境变量 |
| **Celery 任务不执行** | 检查 `redis` 服务和 worker 状态 |
| **文件上传失败** | 检查 `./storage` 目录权限 |

### 健康检查

```bash
# 检查所有服务状态
docker-compose ps

# 检查数据库健康
docker-compose exec db pg_isready -U admin

# 检查 Redis 连接
docker-compose exec redis redis-cli ping

# 查看 Celery 任务
docker-compose exec celery-flower celery -A app.tasks.celery_app inspect active
```

### 日志查看

```bash
# 实时查看后端日志
docker-compose logs -f backend

# 查看最近100行
docker-compose logs --tail=100 backend

# 查看所有服务日志
docker-compose logs
```

---

## 🔄 CI/CD 部署流程

```mermaid
graph LR
    A[代码提交] --> B[Docker 构建]
    B --> C[推送镜像]
    C --> D[拉取镜像]
    D --> E[停止旧容器]
    E --> F[启动新容器]
    F --> G[健康检查]
```

### 生产部署步骤

1. **准备环境**
   ```bash
   cp .env.example .env
   # 编辑 .env 配置生产环境变量
   ```

2. **构建镜像**
   ```bash
   docker-compose build
   ```

3. **启动服务**
   ```bash
   docker-compose up -d
   ```

4. **数据库迁移**
   ```bash
   docker-compose exec backend alembic upgrade head
   ```

5. **验证部署**
   ```bash
   curl http://localhost:3000  # 前端
   curl http://localhost:8000/docs  # API文档
   ```

---

## 📞 快速定位

当你听到问题时，按以下步骤定位：

1. **确定模块名称** - 使用上面的调试索引
2. **前端定位** - 查看 `frontend/src/pages/[模块名].tsx`
3. **后端定位** - 查看 `backend/app/api/*router.py` 或 `endpoints/*.py`
4. **服务定位** - 查看 `backend/app/services/[模块名]/`
5. **模型定位** - 查看 `backend/app/models/[模块名].py`
6. **容器问题** - 使用 `docker-compose logs` 查看日志

---

*最后更新: 2026-01-26*
