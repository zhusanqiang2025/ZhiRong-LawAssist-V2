# 智融法助 v2.0 - 完整应用架构文档

## 📋 目录

1. [项目概述](#项目概述)
2. [技术栈](#技术栈)
3. [项目结构](#项目结构)
4. [前端架构](#前端架构)
5. [后端架构](#后端架构)
6. [核心功能模块](#核心功能模块)
7. [数据库设计](#数据库设计)
8. [API 路由设计](# API路由设计)
9. [部署架构](#部署架构)
10. [开发指南](#开发指南)

---

## 项目概述

**项目名称**: 智融法助 v2.0 (Legal Document Assistant)

**项目描述**: 基于大语言模型的法律文书生成和分析平台，为法律从业者提供智能化的合同管理、案件分析、风险评估等服务。

**版本**: v2.0 (重构版 v4.0)

**架构模式**: 前后端分离 + 微服务化

**开发状态**: 生产就绪

---

## 技术栈

### 前端技术栈
```json
{
  "framework": "React 18.2.0",
  "language": "TypeScript 5.6.2",
  "build_tool": "Vite 7.2.7",
  "ui_library": "Ant Design 5.28.0",
  "router": "React Router 7.10.1",
  "http_client": "Axios 1.13.2",
  "charts": "Recharts 2.15.4 + Mermaid 11.12.2"
}
```

### 后端技术栈
```json
{
  "framework": "FastAPI 0.104.1",
  "python_version": "3.11+",
  "orm": "SQLAlchemy 2.0+",
  "database": "PostgreSQL 15 + pgvector",
  "vector_db": "ChromaDB 0.6.0",
  "task_queue": "Celery 5.3.4 (Redis已移除，使用内存缓存)",
  "ai_framework": "LangChain 0.3.x"
}
```

### DevOps 技术栈
```json
{
  "containerization": "Docker + Docker Compose",
  "orchestration": "Kubernetes (GitLab CI/CD)",
  "reverse_proxy": "Nginx",
  "document_editor": "OnlyOffice Document Server",
  "monitoring": "Prometheus + Grafana"
}
```

---

## 项目结构

### 整体目录结构

```
智融法助 v2.0/
├── frontend/                 # 前端项目
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── backend/                  # 后端项目
│   ├── app/
│   ├── alembic/               # 数据库迁移
│   ├── scripts/               # 工具脚本（已整理）
│   ├── main.py                # ✅ 应用主入口
│   └── requirements.txt
├── docs/                     # 📄 文档目录
├── docker/                    # Docker 配置
├── .gitlab-ci.yml             # CI/CD 配置
└── docker-compose.yml         # 本地开发配置
```

### 前端详细结构
```
frontend/src/
├── api/                      # API 接口封装
│   ├── consultation.ts        # 咨询服务 API
│   ├── litigationAnalysis.ts  # 诉讼分析 API
│   ├── knowledgeBase.ts       # 知识库 API
│   └── ...
├── components/               # 公共组件
│   ├── ChatWindow.tsx        # 聊天窗口
│   ├── FileDisplay.tsx       # 文件展示
│   ├── ModuleNavBar/          # 模块导航栏
│   └── ...
├── context/                  # React Context
│   ├── AuthContext.tsx       # 认证状态管理
│   └── SessionContext.tsx    # 会话状态管理
├── hooks/                    # 自定义 Hooks
│   ├── useConsultationSession.ts
│   └── useRiskAnalysisTasks.ts
├── pages/                    # 页面组件
│   ├── HomePage.tsx            # 首页
│   ├── LegalConsultationPage.tsx # 法律咨询
│   ├── ContractGenerationPage.tsx # 合同生成
│   ├── RiskAnalysisPageV2.tsx    # 风险分析
│   ├── LitigationAnalysisPage.tsx # 诉讼分析
│   ├── CostCalculationPage.tsx   # 费用计算
│   ├── DocumentDraftingPage.tsx  # 文档起草
│   └── ...
├── types/                    # TypeScript 类型定义
└── utils/                    # 工具函数
```

### 后端详细结构
```
backend/app/
├── main.py                   # ✅ 应用主入口 (v4.0)
├── api/                      # API 路由层
│   ├── v1/router.py          # V1 统一路由
│   ├── websocket.py          # WebSocket 支持
│   └── ...
├── core/                     # 核心配置
│   ├── config.py             # 应用配置
│   ├── llm_config.py         # LLM 配置
│   ├── security.py           # 安全配置
│   └── exceptions.py         # 异常处理
├── models/                   # 数据模型
│   ├── user.py
│   ├── task.py
│   ├── contract.py
│   └── ...
├── services/                 # 业务服务层
│   ├── common/               # 通用服务
│   │   ├── file_service.py
│   │   ├── document_preprocessor.py
│   │   ├── cache_service.py
│   │   └── ...
│   ├── consultation/         # 咨询服务
│   ├── contract_generation/  # 合同生成
│   ├── contract_review/      # 合同审查
│   ├── cost_calculation/    # 费用计算 (新建)
│   ├── document_drafting/   # 文档起草
│   ├── knowledge_base/       # 知识库
│   ├── litigation_analysis/  # 诉讼分析
│   ├── legal_search/         # 法律检索 (新建)
│   └── risk_analysis/        # 风险分析
└── utils/                    # 工具类
    ├── office_utils.py       # OnlyOffice 集成
    ├── crypto_utils.py       # 加密工具
    └── file_security.py      # 文件安全
```

---

## 前端架构

### 技术架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         前端架构 (React + TypeScript)                │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌───────────────────┴───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   路由层     │   │   组件层     │   │   状态管理     │
│              │   │              │   │                │
│React Router │   │  Ant Design  │   │  Context API    │
│              │   │              │   │                │
│懒加载        │   │  定制组件    │   │  Redux        │
│              │   │              │   │  (可选)        │
└──────────────┘   └──────────────┘   └──────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                              │
        ┌──────────────────────────────────────────┐
        │           API 服务层                      │
        │  (Axios + API 封装)                   │
        └──────────────────────────────────────────┘
```

### 核心页面组件

| 页面 | 路由 | 说明 |
|------|------|------|
| 首页 | `/` | 智能引导 Banner + 功能入口 |
| 法律咨询 | `/consultation` | 实时对话 + 历史管理 |
| 合同生成 | `/contract/generate` | 需求分析 + 智能生成 |
| 合同审查 | `/contract/review` | AI审查 + 在线编辑 |
| 风险分析 | `/risk-analysis` | 多任务并行 + 可视化 |
| 诉讼分析 | `/litigation-analysis` | 案件分析 + 策略制定 |
| 文档起草 | `/document-drafting` | 文书生成 + 格式转换 |
| 费用计算 | `/cost-calculation` | 费用估算 + 报告生成 |

---

## 后端架构

### 技术架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    后端架构 (FastAPI + Python)                    │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌───────────────────┴───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   API 层      │   │   服务层      │   │   数据层      │
│              │   │              │   │                │
│ /api/v1/      │   │ services/     │   │   models/       │
│ router.py     │   │              │   │                │
│              │   │  通用服务    │   │   database.py    │
│ endpoints/    │   │  common/       │   │                │
└──────────────┘   └───────────────┘   └───────────────┘
        │                   │                   │
        └───────────────────┴───────────────────┘
                              │
        ┌──────────────────────────────────────────┐
        │           中间件层                          │
        │  (CORS, Security, WebSocket)           │
        └──────────────────────────────────────────┘
```

### 服务模块架构

```
backend/app/services/
├── common/                   # 通用服务
│   ├── file_service.py          # 文件管理
│   ├── document_preprocessor.py  # 文档预处理
│   ├── document_renderer.py     # 文档渲染
│   └── cache_service.py         # 缓存服务
├── consultation/              # 咨询服务
│   ├── graph.py                 # 对话流程图
│   ├── session_service.py       # 会话管理
│   ├── history_service.py       # 历史记录
│   └── dynamic_persona_generator.py  # 动态人物生成
├── contract_generation/       # 合同生成
│   ├── agents/                  # 生成代理
│   ├── workflow.py              # 工作流程
│   └── rag/                     # 检索增强
├── contract_review/           # 合同审查
│   ├── graph.py                 # 审查流程图
│   ├── nodes/                   # 审查节点
│   └── rule_assembler.py        # 规则组装器
├── cost_calculation/         # 费用计算 (新建)
│   └── cost_service.py         # 费用计算逻辑
├── document_drafting/        # 文档起草
│   └── workflow.py              # 起草工作流
├── knowledge_base/            # 知识库
│   ├── local_legal_kb.py       # 本地知识库
│   ├── database_kb.py          # 数据库知识库
│   └── unified_service.py     # 统一服务
├── litigation_analysis/      # 诉讼分析
│   └── workflow.py              # 分析工作流
├── legal_search/             # 法律检索 (新建)
│   └── rag_system.py          # RAG 检索系统
└── risk_analysis/           # 风险分析
    ├── workflow.py              # 分析工作流
    └── preorganization/       # 预组织服务
```

---

## 核心功能模块

### 1. 智能咨询 (Legal Consultation)

**功能描述**: 基于多轮对话的智能法律咨询服务，采用两阶段处理模式（律师助理→专业律师）

**技术实现**:
- **两阶段处理**: 律师助理节点进行初步分类，专业律师节点提供深度分析
- **动态人物生成**: 根据案情自动生成专业法律角色（persona_definition）
- **战略分析**: 自动生成案件分析策略和风险重点（strategic_focus）
- **会话管理**: 支持多会话并行、历史记录管理
- **上下文保持**: 长对话中的上下文信息保持
- **异步任务**: 使用 Celery 后台处理，前端通过轮询获取结果
- **状态机管理**: 使用 current_phase 和 user_decision 精确控制流程状态

**关键文件**:
- `backend/app/api/consultation_router.py` - 咨询 API 路由
- `backend/app/services/consultation/graph.py` - LangGraph 工作流
- `backend/app/services/consultation/session_service.py` - 会话状态管理
- `backend/app/tasks/consultation_tasks.py` - Celery 异步任务
- `frontend/src/pages/LegalConsultationPage.tsx` - 咨询页面

**数据流**:
```
用户输入问题
    ↓
前端: startConsultation()
    ↓
POST /api/v1/consultation/start
    ↓
后端: consultation_router.py - start_consultation()
    ↓
Celery: task_run_consultation() [异步]
    ↓
LangGraph: run_legal_consultation()
    ├→ assistant_node (律师助理)
    │   └→ 生成分类: primary_type, specialist_role, persona_definition, strategic_focus
    │   └→ 保存到: classification + session_state
    ├→ [用户确认] → confirm_decision()
    └→ specialist_node (专业律师)
        └→ 深度分析: analysis, advice, risk_warning, action_steps
        └→ 保存到: specialist_output + session_state
    ↓
数据库: ConsultationHistory 表
    └─ session_state: {current_phase, classification, specialist_output}
    └─ current_phase: initial/waiting_confirmation/specialist/completed
    └─ user_decision: pending/confirmed/cancelled
    └─ status: active/archived/cancelled
    ↓
前端: pollTaskStatus() 轮询
    ↓
GET /api/v1/consultation/task-status/{session_id}
    ↓
后端: get_task_status()
    ↓
返回: {status, current_phase, classification, specialist_output}
```

**状态机**:
```
                    ┌─────────────┐
                    │   initial   │ (任务启动)
                    └──────┬──────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   running   │ (Celery 处理中)
                    └──────┬──────┘
                           │
                   ┌───────┴───────┐
                   │               │
                   ▼               ▼
        ┌──────────────────┐  ┌──────────────────┐
        │ waiting_confirmation│  │    completed     │
        │  (助理完成，等待确认)│  │   (直接完成)      │
        └────────┬─────────┘  └──────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
   确认(Confirm)     取消(Cancel)
        │                 │
        ▼                 ▼
 ┌─────────────┐   ┌───────────┐
 │  specialist │   │  cancelled │
 │ (专家律师处理)│  └───────────┘
 └──────┬──────┘
        │
        ▼
 ┌─────────────┐
 │  completed  │
 └─────────────┘
```

**API 端点**:
```
POST /api/v1/consultation/start                    # 启动咨询任务
GET  /api/v1/consultation/task-status/{session_id}  # 获取任务状态（轮询）
POST /api/v1/consultation/confirm                 # 确认转交专家律师
```

**API 端点详情**:

| 端点 | 方法 | 描述 | 请求参数 | 响应结构 |
|------|------|------|----------|----------|
| `/api/v1/consultation/start` | POST | 启动咨询任务 | `{question, session_id?, context?}` | `{session_id, task_id, ui_action}` |
| `/api/v1/consultation/task-status/{session_id}` | GET | 获取任务状态 | - | `{status, current_phase, classification?, specialist_output?}` |
| `/api/v1/consultation/confirm` | POST | 确认转交专家 | `{session_id, user_confirmed: true}` | `{session_id, task_id}` |

**任务状态响应示例** (waiting_confirmation 阶段):
```json
{
  "status": "waiting_confirmation",
  "current_phase": "waiting_confirmation",
  "session_id": "session-abc123",
  "primary_type": "公司治理与合规",
  "specialist_role": "股权代持与高管激励律师",
  "suggested_questions": [],
  "direct_questions": [],
  "basic_summary": "初步分析...",
  "recommended_approach": "建议...",
  "persona_definition": {
    "role_title": "高级公司治理顾问",
    "professional_background": "法学硕士，专注于公司治理...",
    "years_of_experience": "12年",
    "expertise_area": "股权代持协议、高管报酬...",
    "approach_style": "严谨、务实..."
  },
  "strategic_focus": {
    "analysis_angle": "从法律风险、税务合规角度",
    "key_points": [
      "代持协议的合法性及有效性审查",
      "报酬计算方式的公平性",
      "税务筹划的合规性"
    ],
    "risk_alerts": [
      "潜在税务稽查风险",
      "股权代持引发的所有权纠纷"
    ],
    "attention_matters": [
      "注意实际控制权与名义股东的约定",
      "关注协议解除时的股权返还机制"
    ]
  }
}
```

### 2. 合同生成 (Contract Generation)

**功能描述**: 基于用户需求智能生成各类法律合同

**技术实现**:
- **多Agent协作**: 需求分析器 + 条款生成器
- **模板系统**: 可配置的合同模板库
- **知识图谱**: 合同条款智能推荐
- **合同规划**: 支持复杂合同的场景规划

**关键文件**:
- `backend/app/services/contract_generation/workflow.py` - 生成工作流
- `frontend/src/pages/ContractGenerationPage.tsx` - 生成页面

**API 端点**:
```
POST /api/contract-generation/analyze           # 分析需求
POST /api/contract-generation/generate          # 生成合同
POST /api/contract-generation/planning          # 合同规划
```

### 3. 合同审查 (Contract Review)

**功能描述**: AI辅助的专业合同审查服务

**技术实现**:
- **规则引擎**: 基于法律规则库的智能审查
- **AI增强**: LLM 辅助深度分析
- **OnlyOffice**: 集成在线文档编辑器
- **修订建议**: 具体的修改意见和风险提示

**关键文件**:
- `backend/app/services/contract_review/graph.py` - 审查流程图
- `backend/app/services/contract_review/nodes/` - 审查节点
- `frontend/src/pages/ContractReview.tsx` - 审查页面

**API 端点**:
```
POST /api/contract/{contract_id}/deep-review     # 深度审查
GET  /api/contract/{contract_id}/onlyoffice-config  # 编辑配置
```

### 4. 风险分析 (Risk Analysis)

**功能描述**: 法律文档风险评估与可视化分析

**技术实现**:
- **多任务支持**: 并行处理多个风险分析任务
- **规则引擎**: 可配置的风险规则包
- **可视化展示**: 风险热力图、趋势图
- **预组织**: 风险事项的结构化组织

**关键文件**:
- `backend/app/services/risk_analysis/workflow.py` - 分析工作流
- `frontend/src/pages/RiskAnalysisPageV2.tsx` - 分析页面

**API 端点**:
```
POST /api/v1/risk-analysis/submit        # 提交分析
POST /api/v1/risk-analysis/upload        # 上传文档
WS   /api/v1/risk-analysis/ws/{id}        # WebSocket进度
```

### 5. 诉讼分析 (Litigation Analysis)

**功能描述**: 案件材料分析与诉讼策略制定

**技术实现**:
- **要素提取**: 自动提取案件关键信息
- **策略制定**: 基于案例库的策略推荐
- **报告生成**: 自动生成分析报告

**关键文件**:
- `backend/app/services/litigation_analysis/workflow.py` - 分析工作流
- `frontend/src/pages/LitigationAnalysisPage.tsx` - 分析页面

### 6. 文档起草 (Document Drafting)

**功能描述**: 智能生成各类司法文书

**技术实现**:
- **模板引擎**: 基于模板的智能生成
- **格式转换**: 支持多种格式互转

**关键文件**:
- `backend/app/services/document_drafting/workflow.py` - 起草工作流

**API 端点**:
```
POST /api/v1/document-drafting/generate    # 生成文书
GET  /api/v1/document-drafting/templates   # 获取模板
```

### 7. 费用计算 (Cost Calculation)

**功能描述**: 诉讼费用智能计算

**技术实现**:
- **多种费用类型**: 诉讼费、保全费、执行费、律师费等
- **法规依据**: 基于最新收费标准
- **可视化展示**: 费用明细和汇总

**关键文件**:
- `backend/app/services/cost_calculation/cost_service.py` - 费用计算逻辑
- `frontend/src/pages/CostCalculationPage.tsx` - 计算页面

### 8. 法律检索 (Legal Search)

**功能描述**: 法律法规语义检索

**技术实现**:
- **向量检索**: 基于语义的智能搜索
- **全文检索**: 支持关键词搜索
- **多源数据**: 法规库、案例库、知识图谱

**关键文件**:
- `backend/app/services/legal_search/rag_system.py` - RAG 检索系统

---

## 数据库设计

### 主要数据表

#### 用户表 (users)
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    full_name VARCHAR,
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 任务表 (tasks)
```sql
CREATE TABLE tasks (
    id VARCHAR PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    type VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    input_data JSONB,
    result_data JSONB,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 咨询历史表 (consultation_histories)
```sql
CREATE TABLE consultation_histories (
    id VARCHAR PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id VARCHAR UNIQUE NOT NULL,
    title VARCHAR,
    messages JSONB,              -- 对话消息列表
    message_count INTEGER DEFAULT 0,
    specialist_type VARCHAR,     -- 专业律师类型
    classification JSONB,        -- 分类结果 (包含 persona_definition, strategic_focus)
    session_state JSONB,         -- 会话状态 (完整状态对象)
    -- v4.0 新增字段
    current_phase VARCHAR DEFAULT 'initial',  -- initial/waiting_confirmation/specialist/completed
    user_decision VARCHAR DEFAULT 'pending',  -- pending/confirmed/cancelled
    current_task_id VARCHAR,     -- Celery 任务 ID
    -- 枚举字段 (status 仅用于会话生命周期管理，不用于业务流程)
    status VARCHAR DEFAULT 'active' CHECK (status IN ('active', 'archived', 'cancelled')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 关键索引
CREATE INDEX idx_consultation_session_id ON consultation_histories(session_id);
CREATE INDEX idx_consultation_user_id ON consultation_histories(user_id);
CREATE INDEX idx_consultation_status ON consultation_histories(status);
CREATE INDEX idx_consultation_current_phase ON consultation_histories(current_phase);

-- 字段说明
-- session_id: 唯一会话标识，前后端通过此 ID 进行通信
-- current_phase: 业务流程阶段 (initial -> running -> waiting_confirmation -> specialist -> completed)
-- user_decision: 用户决策状态 (pending -> confirmed/cancelled)
-- status: 会话生命周期状态 (active -> archived/cancelled)
-- classification: 律师助理节点的分类结果，包含:
--   - primary_type: 专业领域 (如 "公司治理与合规")
--   - specialist_role: 专业律师角色 (如 "股权代持与高管激励律师")
--   - persona_definition: 专家人设信息
--   - strategic_focus: 战略分析重点
--   - suggested_questions: 建议的补充问题
--   - direct_questions: 直接询问的问题
-- session_state: 完整的会话状态对象，包含:
--   - is_in_specialist_mode: 是否已进入专家模式
--   - specialist_output: 专业律师节点的输出 (analysis, advice, risk_warning, action_steps)
--   - classification: 分类结果 (与 classification 字段同步)
--   - current_phase: 当前阶段 (与 current_phase 字段同步)
--   - user_decision: 用户决策 (与 user_decision 字段同步)
```

#### 合同模板表 (contract_templates)
```sql
CREATE TABLE contract_templates (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    category_id VARCHAR REFERENCES categories(id),
    content TEXT,
    variables JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### 风险分析表 (risk_analyses)
```sql
CREATE TABLE risk_analyses (
    id VARCHAR PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id VARCHAR,
    documents JSONB,
    risk_items JSONB,
    analysis_result JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## API 路由设计

### API 版本管理
采用 v1 版本统一路由架构：

```
/api/v1/
├── auth/                    # 认证相关
├── consultation/            # 咨询服务
├── contract/                # 合同管理
├── risk-analysis/           # 风险分析
├── litigation-analysis/     # 诉讼分析
├── document-drafting/       # 文档起草
├── knowledge-base/           # 知识库
├── smart-chat/               # 智能对话
└── admin/                   # 管理后台
```

### 核心 API 端点

| 功能 | 方法 | 端点 | 描述 |
|------|------|------|------|
| 认证 | POST | `/api/v1/auth/login` | 用户登录 |
| 咨询 | POST | `/api/v1/smart-chat/expert-consultation` | 专家咨询 |
| 咨询历史 | GET | `/api/v1/consultation-history/sessions` | 会话列表 |
| 合同生成 | POST | `/api/contract-generation/generate` | 生成合同 |
| 合同审查 | POST | `/api/contract/{id}/deep-review` | 深度审查 |
| 风险分析 | POST | `/api/v1/risk-analysis/submit` | 提交分析 |
| 费用计算 | POST | `/api/cost-calculation/calculate-v2` | 计算费用 |
| 文档起草 | POST | `/api/v1/document-drafting/generate` | 生成文书 |
| 诉讼分析 | POST | `/api/v1/litigation-analysis/start` | 开始分析 |
| 知识库查询 | POST | `/api/v1/rag/query` | RAG 查询 |

---

## 部署架构

### 本地开发环境

```yaml
架构: 前后端分离
Frontend: React (Vite dev server) :3001
Backend: FastAPI (Uvicorn) :9000
Database: PostgreSQL :5433
```

### 生产环境 (K8s)

```yaml
架构: 容器化部署
Ingress: Nginx 反向代理
Services:
  - Frontend: Nginx + React 静态文件
  - Backend: FastAPI 应用
  - Database: PostgreSQL + pgvector
  - OnlyOffice: 文档编辑器服务
```

### Docker Compose 配置

```yaml
services:
  frontend:
    image: legal_assistant_v3_frontend
    ports: ["3001:80"]
  backend:
    image: legal_assistant_v3_backend
    ports: ["9000:8000"]
    depends_on:
      - db
  db:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: legal_assistant_db
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  onlyoffice:
    image: onlyoffice/documentserver:latest
    ports: ["8083:80"]
```

---

## 开发指南

### 环境配置

#### 1. 本地开发环境设置

```bash
# 克隆项目
git clone <repository-url>
cd 智融法助 v2.0

# 安装前端依赖
cd frontend
npm install

# 安装后端依赖
cd backend
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
```

#### 2. 启动开发服务器

```bash
# 启动后端 (终端1)
cd backend
uvicorn app.main:app --reload --port 9000

# 启动前端 (终端2)
cd frontend
npm run dev
```

#### 3. 访问应用

- 前端: http://localhost:3001
- 后端 API: http://localhost:9000
- API 文档: http://localhost:9000/docs
- 管理后台: http://localhost:3001/admin

### 代码规范

#### Python 代码风格

- 遵循 PEP 8 规范
- 使用类型提示
- 编写详细的 docstring
- 单元测试覆盖率 > 80%

#### 前端代码风格

- 使用 TypeScript 编写
- 遵循 ESLint 规则
- 组件使用函数式组件
- 使用自定义 Hooks 组织逻辑

### 调试技巧

#### 后端调试

```python
# 使用日志记录
import logging
logger = logging.getLogger(__name__)

# 使用断点调试
import pdb; pdb.set_trace()
```

#### 前端调试

```javascript
// 使用 console.log 或 debugger
console.log('Debug:', data);

// 或使用 React DevTools
debugger;
```

---

## 常见问题

### 1. 导入错误
**问题**: ModuleNotFoundError

**解决方案**:
```bash
# 清理 Python 缓存
find . -type d -name "__pycache__" -exec rm -rf {} +

# 重新安装依赖
pip install -r requirements.txt
```

### 2. 数据库连接错误
**问题**: could not translate host name

**解决方案**:
```bash
# 检查数据库服务状态
docker-compose ps

# 查看数据库日志
docker-compose logs db
```

### 3. 前端构建错误
**问题**: Module not found

**解决方案**:
```bash
# 清理缓存重新构建
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

---

## 智能咨询模块 - 已发现的架构问题

本文档记录智能咨询模块在开发调试过程中发现的架构问题及解决方案，供其他 AI 编程工具参考。

### 问题 1: API 路径重复

**症状**: `GET /api/v1/v1/consultation/task-status/...` 返回 404 Not Found

**原因**: 前端 API client 已配置 `/api/v1` 前缀，但在调用时又加上了 `/v1`，导致路径重复

**解决**:
- 修改前端调用：将 `/v1/consultation/task-status/` 改为 `/consultation/task-status/`
- 文件: `frontend/src/pages`/LegalConsultationPage.tsx:311`

**参考代码**:
```typescript
// ❌ 错误 - 路径重复
const response = await api.get(`/v1/consultation/task-status/${sessionId}`);

// ✅ 正确 - API client 已有前缀
const response = await api.get(`/consultation/task-status/${sessionId}`);
```

---

### 问题 2: 数据库枚举值不匹配

**症状**: `SQLAlchemy` 异常: `'waiting_confirmation' is not among the defined enum values. Enum name: consultation_status. Possible values: active, archived, cancelled`

**原因**:
- `status` 字段定义的枚举值为 `active/archived/cancelled`
- 但代码尝试将 `waiting_confirmation` 写入 `status` 字段
- `waiting_confirmation` 是业务流程阶段，不应存入 `status` 字段

**解决**:
- 使用 `current_phase` 字段存储业务流程阶段（`initial/waiting_confirmation/specialist/completed`）
- `status` 字段仅用于会话生命周期管理（`active/archived/cancelled`）
- 文件: `backend/app/tasks/consultation_tasks.py:106-107`

**参考代码**:
```python
# ❌ 错误 - waiting_confirmation 不是 status 的有效值
asyncio.run(session_service.update_session(
    session_id=session_id,
    status="waiting_confirmation",  # 会抛出枚举错误
    current_phase="waiting_confirmation"
))

# ✅ 正确 - 使用 current_phase 字段
asyncio.run(session_service.update_session(
    session_id=session_id,
    status="active",  # 使用正确的枚举值
    current_phase="waiting_confirmation"
))
```

---

### 问题 3: session_state 同步不一致

**症状**: `get_session` 返回的数据缺少 `current_phase`、`user_decision` 等关键字段

**原因**:
- `update_session` 更新了数据库列（`current_phase`, `user_decision` 等）
- 但未同步到 `session_state` JSONB 字段
- `get_session` 只返回 `session_state`，导致缺失数据

**解决**:
- 在 `update_session` 方法中，更新数据库列后同步到 `session_state`
- 在 `get_session` 方法中，从数据库列补充缺失的值到返回对象
- 文件: `backend/app/services/consultation/session_service.py:239-262`

**参考代码**:
```python
# update_session 方法中添加同步逻辑
if hasattr(history, 'current_phase') and history.current_phase:
    session_state['current_phase'] = history.current_phase
if hasattr(history, 'user_decision') and history.user_decision:
    session_state['user_decision'] = history.user_decision
if hasattr(history, 'status') and history.status:
    session_state['status'] = history.status
history.session_state = session_state
```

---

### 问题 4: 前端 Message 接口不完整

**症状**: 前端确认卡片不显示专家人设（`persona_definition`）和战略分析（`strategic_focus`）信息

**原因**:
- 后端 API 正确返回了 `persona_definition` 和 `strategic_focus` 数据
- 但前端 TypeScript `Message` 接口缺少这些字段的类型定义
- 导致前端构建消息对象时无法正确存储这些数据

**解决**:
- 扩展 `Message` 接口，添加缺失的字段定义
- 更新确认卡片构建逻辑，从 API 响应捕获完整数据
- 更新确认卡片渲染逻辑，显示专家人设和战略分析卡片
- 文件: `frontend/src/pages/LegalConsultationPage.tsx:50-63, 337-357, 775-811`

**参考代码**:
```typescript
// Message 接口扩展
export interface Message {
  // ... 现有字段
  // 新增字段
  persona_definition?: {
    role_title?: string;
    professional_background?: string;
    years_of_experience?: string;
    expertise_area?: string;
    approach_style?: string;
  };
  strategic_focus?: {
    analysis_angle?: string;
    key_points?: string[];
    risk_alerts?: string[];
    attention_matters?: string[];
  };
}

// 确认卡片构建
const confirmationMessage: Message = {
  // ... 现有字段
  persona_definition: response.data.persona_definition,
  strategic_focus: response.data.strategic_focus,
};
```

---

### 问题 5: save_session 方法参数不匹配

**症状**: `TypeError` - `save_session` 收到意外的关键字参数

**原因**:
- `save_session` 方法定义不接受 `status` 参数
- 但调用时传入了 `status="active"`

**解决**:
- 移除错误的 `status` 参数调用
- 文件: `backend/app/tasks/consultation_tasks.py:117-132`

---

## 智能咨询模块调试指南

本指南提供系统的调试步骤，帮助 AI 编程工具排查智能咨询模块的问题。

### 调试步骤 1: 检查后端日志

查看后端日志中的关键输出，确认数据是否正确生成和传递：

```bash
# 关键日志输出示例
[API] 任务状态查询: session_id=session-abc123
[API] - current_phase=waiting_confirmation, user_decision=pending, status=active
[API] - classification存在=True
[API] - primary_type=公司治理与合规
[API] - specialist_role=股权代持与高管激励律师
[API] - persona_definition存在=True
[API] - strategic_focus存在=True
```

**预期结果**:
- `current_phase` 应为 `waiting_confirmation`（助理完成，等待确认）
- `user_decision` 应为 `pending`（等待用户决策）
- `classification` 对象存在且包含 `persona_definition` 和 `strategic_focus`

**如果日志缺失**:
- 检查 LangGraph 工作流中的助理节点是否正确返回
- 检查 consultation_tasks.py 中的状态判断逻辑

---

### 调试步骤 2: 检查数据库状态

直接查询数据库，验证数据是否正确存储：

```sql
-- 查询会话的完整状态
SELECT
    session_id,
    status,
    current_phase,
    user_decision,
    classification->>'primary_type' as primary_type,
    classification->>'specialist_role' as specialist_role,
    jsonb_exists(classification, 'persona_definition') as has_persona,
    jsonb_exists(classification, 'strategic_focus') as has_strategic_focus
FROM consultation_histories
WHERE session_id = 'your-session-id';

-- 查看完整的 classification JSONB 内容
SELECT
    session_id,
    current_phase,
    classification
FROM consultation_histories
WHERE session_id = 'your-session-id';

-- 检查 session_state JSONB 是否同步
SELECT
    session_id,
    session_state->>'current_phase' as session_state_current_phase,
    session_state->>'user_decision' as session_state_user_decision,
    current_phase as db_current_phase,
    user_decision as db_user_decision
FROM consultation_histories
WHERE session_id = 'your-session-id';
```

**预期结果**:
- `status` = `active`
- `current_phase` = `waiting_confirmation`
- `user_decision` = `pending`
- `primary_type` 和 `specialist_role` 有值
- `has_persona` 和 `has_strategic_focus` 为 `true`
- `session_state` 中的 `current_phase` 和 `user_decision` 与数据库列同步

---

### 调试步骤 3: 检查前端网络请求

在浏览器控制台检查 API 响应，验证后端返回的完整数据：

```javascript
// 在 LegalConsultationPage.tsx 的轮询函数中添加调试代码
const response = await api.get(`/consultation/task-status/${sessionId}`);

// 添加调试日志
console.log('[DEBUG Frontend] 收到 waiting_confirmation 响应:', response.data);
console.log('[DEBUG Frontend] status:', response.data.status);
console.log('[DEBUG Frontend] current_phase:', response.data.current_phase);
console.log('[DEBUG Frontend] primary_type:', response.data.primary_type);
console.log('[DEBUG Frontend] specialist_role:', response.data.specialist_role);
console.log('[DEBUG Frontend] persona_definition:', response.data.persona_definition);
console.log('[DEBUG Frontend] strategic_focus:', response.data.strategic_focus);
```

**预期结果**:
- `response.data.status` = `"waiting_confirmation"`
- `response.data.current_phase` = `"waiting_confirmation"`
- `response.data.primary_type` 有值（如 "公司治理与合规"）
- `response.data.specialist_role` 有值（如 "股权代持与高管激励律师"）
- `response.data.persona_definition` 是一个对象（包含 role_title, professional_background 等）
- `response.data.strategic_focus` 是一个对象（包含 analysis_angle, key_points 等）

**如果数据缺失**:
- 检查后端 `get_task_status` 函数是否正确返回所有字段
- 检查数据库中的 `classification` JSONB 是否包含这些字段

---

### 调试步骤 4: 检查前端 Message 对象

验证前端构建的 Message 对象是否包含专家信息：

```javascript
// 在构建 confirmationMessage 后添加调试代码
const confirmationMessage: Message = {
  id: `confirm-${Date.now()}`,
  content: `初步分析完成...`,
  role: 'assistant',
  timestamp: new Date(),
  isConfirmation: true,
  suggestedQuestions: response.data.suggested_questions || [],
  directQuestions: response.data.direct_questions || [],
  persona_definition: response.data.persona_definition,
  strategic_focus: response.data.strategic_focus,
  specialist_role: response.data.specialist_role,
  primary_type: response.data.primary_type,
};

// 添加调试日志
console.log('[DEBUG Frontend] confirmationMessage 对象:', confirmationMessage);
console.log('[DEBUG Frontend] persona_definition 存在:', !!confirmationMessage.persona_definition);
console.log('[DEBUG Frontend] strategic_focus 存在:', !!confirmationMessage.strategic_focus);
```

**预期结果**:
- `confirmationMessage.persona_definition` 存在且包含专家人设信息
- `confirmationMessage.strategic_focus` 存在且包含战略分析信息

**如果数据缺失**:
- 检查 TypeScript `Message` 接口是否定义了这些字段
- 检查赋值是否正确（注意拼写错误，如 `persona_definiton`）

---

### 调试步骤 5: 检查前端渲染逻辑

验证前端确认卡片是否正确渲染专家信息卡片：

```javascript
// 在确认卡片的 JSX 中添加调试代码
{msg.isConfirmation ? (
  <div className="confirmation-card">
    {/* 调试日志 */}
    {(() => {
      console.log('[DEBUG Render] msg.isConfirmation:', msg.isConfirmation);
      console.log('[DEBUG Render] msg.persona_definition:', msg.persona_definition);
      console.log('[DEBUG Render] msg.strategic_focus:', msg.strategic_focus);
      return null;
    })()}

    <Text strong style={{ fontSize: 16 }}>🔎 初步诊断完成</Text>
    {/* ... 现有代码 */}

    {/* 专家人设卡片 */}
    {msg.persona_definition && (
      <Card size="small" style={{ margin: '12px 0', background: '#f0f5ff' }}>
        {/* ... 专家人设渲染代码 */}
      </Card>
    )}

    {/* 战略分析卡片 */}
    {msg.strategic_focus && (
      <Card size="small" style={{ margin: '12px 0', background: '#fff7e6' }}>
        {/* ... 战略分析渲染代码 */}
      </Card>
    )}
  </div>
) : (
  // ...
)}
```

**预期结果**:
- `msg.persona_definition` 有值时，专家人设卡片渲染
- `msg.strategic_focus` 有值时，战略分析卡片渲染

**如果卡片不显示**:
- 检查条件判断是否正确（`msg.persona_definition && ...`）
- 检查样式是否导致卡片被隐藏
- 检查是否有其他代码错误中断了渲染

---

### 调试步骤 6: 强制刷新浏览器

浏览器缓存可能导致旧的 JavaScript 代码仍在运行：

```bash
# 强制刷新（清除缓存）
Windows/Linux: Ctrl + Shift + R
Mac: Cmd + Shift + R

# 或在开发者工具中清除缓存
F12 → Application → Storage → Clear site data
```

---

### 调试步骤 7: 检查 API 路径配置

验证前端 API 客户端配置：

```javascript
// 检查 api 实例的 baseURL 配置
console.log('[DEBUG] API baseURL:', api.defaults.baseURL);

// 预期输出: 'http://localhost:9000/api/v1' 或类似值
```

**如果路径配置错误**:
- 检查 `frontend/src/api` 目录下的 API 配置文件
- 确认 `baseURL` 设置正确

---

### 调试步骤 8: 检查 TypeScript 编译错误

有时 TypeScript 编译错误会导致代码没有正确更新：

```bash
# 在前端项目目录中
cd frontend
npm run build

# 查看是否有编译错误
```

**如果存在编译错误**:
- 检查 `Message` 接口定义是否完整
- 检查类型使用是否正确

---

## 智能咨询模块关键文件映射

| 功能 | 文件路径 | 关键内容 |
|------|----------|----------|
| 咨询 API 路由 | `backend/app/api/consultation_router.py` | start_consultation, get_task_status, confirm_decision |
| 会话管理服务 | `backend/app/services/consultation/session_service.py` | get_session, save_session, update_session, initialize_session |
| Celery 任务 | `backend/app/tasks/consultation_tasks.py` | task_run_consultation - 后台异步任务 |
| 咨询工作流 | `backend/app/services/consultation/graph.py` | run_legal_consultation, assistant_node, specialist_node |
| 咨询页面 | `frontend/src/pages/LegalConsultationPage.tsx` | startConsultation, pollTaskStatus, 确认卡片渲染 |
| 数据模型 | `backend/app/models/consultation_history.py` | ConsultationHistory ORM 模型 |
| 数据库迁移 | `backend/migrations/fix_status_enum_data_raw_sql.py` | 修复枚举数据错误的脚本 |

---

## 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v2.0 | 2026-02 | 架构重构版本，服务模块化 |
| v1.0 | 2025-12 | 初始版本 |

---

## 联系方式

**项目仓库**: [Git Repository]

**文档更新**: 2026-02-06

**维护团队**: 智融法助开发团队

---

*本文档随项目演进持续更新。*
