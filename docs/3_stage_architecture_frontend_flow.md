# 案件分析模块 - 3阶段架构前端交互流程文档

## 概述

案件分析模块已重构为**3阶段架构**，每个阶段都有明确的人工接入点，用户可以在每个阶段后确认/编辑数据，然后决定是否继续下一阶段。

---

## 架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          3阶段案件分析流程                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐        ┌─────────────────┐        ┌─────────────────┐  │
│  │   阶段1: 预整理  │   ──▶  │  阶段2: 全案分析  │   ──▶  │  阶段3: 文书生成  │  │
│  │   (用户上传)     │        │   (用户确认后)    │        │   (按需触发)      │  │
│  └─────────────────┘        └─────────────────┘        └─────────────────┘  │
│           │                           │                           │           │
│           ▼                           ▼                           ▼           │
│  • 用户上传文件              • 用户选择角色/场景        • 用户点击按钮      │
│  • 基础信息提取              • 规则组装                  • 生成文书草稿      │
│  • 用户确认/编辑             • 证据分析                  • 预览/编辑/下载    │
│  • 选择角色/场景             • 模型推演                                    │
│                              • 策略生成                                    │
│                              • 生成报告                                    │
│                                   │                                         │
│                                   ▼                                         │
│                         • 用户预览/编辑/下载报告                            │
│                         • 点击"生成法律文书"按钮                            │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 阶段1: 预整理阶段

### 用户操作流程

1. **用户上传文件**
   - 在前端页面上传案件相关文档（PDF、DOCX、图片等）
   - 可选输入案件描述（`user_context`）

2. **调用预整理API**
   ```javascript
   const formData = new FormData();
   files.forEach(file => formData.append('files', file));
   formData.append('case_type', '合同纠纷');
   formData.append('user_context', '本案系货物买卖合同纠纷...');

   const response = await fetch('/api/v1/litigation-analysis/preorganize', {
     method: 'POST',
     body: formData
   });
   ```

3. **显示预整理结果**
   - 文档分析列表（每个文档的类型、摘要、关键事实、日期、金额等）
   - 跨文档综合信息（所有当事人、时间线、争议焦点等）
   - 文档关联关系图
   - 质量评估（清晰度、完整性、证据链完整性）

4. **用户确认/编辑**
   - 允许用户编辑提取的信息
   - 添加遗漏的信息
   - 修正错误的识别结果

5. **选择角色和场景**
   - **诉讼地位**（`case_position`）：
     - 原告 (plaintiff)
     - 被告 (defendant)
     - 上诉人 (appellant)
     - 被上诉人 (appellee)
     - 申请人 (applicant)
     - 被申请人 (respondent)
     - 第三人 (third_party)
   - **分析场景**（`analysis_scenario`）：
     - 准备起诉 (pre_litigation)
     - 应诉准备 (defense)
     - 上诉 (appeal)
     - 执行 (execution)
     - 财产保全 (preservation)
     - 证据收集 (evidence_collection)
     - 调解准备 (mediation)

6. **点击"开始深度分析"按钮** → 进入阶段2

### API端点

**请求**: `POST /api/v1/litigation-analysis/preorganize`

**请求参数**:
- `files`: 文档列表（multipart/form-data）
- `case_type`: 案件类型（可选，默认"合同纠纷"）
- `user_context`: 用户描述（可选）

**响应**:
```json
{
  "session_id": "preorg_1234567890",
  "document_analyses": [
    {
      "file_id": "file_001",
      "file_name": "律师函.pdf",
      "file_type": "lawyer_letter",
      "content_summary": "某某律师事务所受原告委托...",
      "key_facts": ["双方于2023年签署了货物买卖合同"],
      "key_dates": ["2023-01-15", "2023-06-30"],
      "key_amounts": ["50万元", "违约金10%"],
      "parties": [
        {"name": "某某科技有限公司", "role": "plaintiff", "confidence": 0.95}
      ]
    }
  ],
  "cross_document_info": {
    "all_parties": [...],
    "timeline": [...],
    "dispute_points": [...],
    "disputed_amount": "50万元"
  },
  "document_relationships": [...],
  "quality_assessment": {
    "clarity_score": 0.85,
    "completeness_score": 0.75,
    "evidence_chain_score": 0.60
  },
  "processed_at": "2024-01-15T10:30:00"
}
```

---

## 阶段2: 全案分析阶段

### 用户操作流程

1. **用户点击"开始深度分析"**
   - 传递用户确认的预整理数据
   - 传递选择的诉讼地位和分析场景

2. **调用全案分析API**
   ```javascript
   const formData = new FormData();
   formData.append('preorganized_data', JSON.stringify(confirmedPreorganizationData));
   formData.append('case_position', 'plaintiff');
   formData.append('analysis_scenario', 'pre_litigation');
   formData.append('case_package_id', 'contract_disputes_001');
   formData.append('case_type', '合同纠纷');

   const response = await fetch('/api/v1/litigation-analysis/analyze', {
     method: 'POST',
     body: formData
   });
   ```

3. **显示分析进度**
   - WebSocket 实时推送进度
   - 规则组装 → 证据分析 → 模型推演 → 策略生成 → 报告生成

4. **显示分析结果**
   - **核心结论**: 胜诉率/成功率、案情综述、最终意见
   - **事实认定**: 经认定的关键法律事实、时间线
   - **法律分析**: 核心主张/抗辩、规则适用、优劣势分析
   - **证据审查**: 证据能力评估、证据缺口/质证策略
   - **行动策略**: 多个策略方案（激进/稳健/保守）

5. **用户预览/编辑/下载报告**
   - 在线预览 Markdown 报告
   - 可编辑报告内容
   - 下载为 MD/PDF/DOCX 格式

6. **显示"生成法律文书"按钮**
   - 提示用户可以按需生成文书草稿
   - 点击后进入阶段3

### API端点

**请求**: `POST /api/v1/litigation-analysis/analyze`

**请求参数**:
- `preorganized_data`: 用户确认的预整理数据（JSON字符串）
- `case_position`: 诉讼地位（plaintiff/defendant/...）
- `analysis_scenario`: 分析场景（pre_litigation/defense/...）
- `case_package_id`: 案件包ID
- `case_type`: 案件类型（可选）
- `user_input`: 用户输入（可选）
- `analysis_mode`: 分析模式（single/multi，默认multi）
- `selected_model`: 单模型选择（可选）

**响应**:
```json
{
  "session_id": "stage2_analysis_1234567890",
  "status": "completed",
  "case_type": "合同纠纷",
  "case_position": "plaintiff",
  "analysis_scenario": "pre_litigation",
  "assembled_rules": ["规则1", "规则2"],
  "timeline": {
    "events": [
      {"date": "2023-01-15", "description": "合同签署", "source": "contract.pdf"}
    ]
  },
  "evidence_analysis": {
    "admissibility_assessment": "证据链基本完整",
    "analysis_points": [...],
    "missing_evidence": ["补充履行证明"]
  },
  "model_results": {
    "final_strength": 0.755,
    "confidence": 0.85,
    "final_summary": "原告XX公司与被告买卖合同纠纷...",
    "final_facts": ["2023年1月15日签署买卖合同"],
    "final_legal_arguments": "依据《民法典》第509条...",
    "rule_application": [...],
    "final_strengths": ["合同关系明确"],
    "final_weaknesses": ["需证明实际损失"],
    "conclusion": "建议起诉，有较高胜算"
  },
  "strategies": [
    {
      "title": "快速保全施压策略",
      "type": "aggressive",
      "description": "利用我方优势，立即起诉并申请财产保全",
      "steps": [
        {"step_name": "立案准备", "description": "准备起诉状、证据清单"},
        {"step_name": "财产保全", "description": "申请诉前财产保全"}
      ],
      "recommendation_score": 5
    }
  ],
  "final_report": "# 诉讼可行性评估报告\n\n...",
  "report_json": {
    "meta": {...},
    "dashboard": {...},
    "content": {...}
  },
  "completed_at": "2024-01-15T10:35:00"
}
```

---

## 阶段3: 文书生成阶段（按需）

### 用户操作流程

1. **用户点击"生成法律文书"按钮**
   - 基于阶段2的分析结果生成配套文书
   - 不是自动触发的，需要用户主动点击

2. **调用文书生成API**
   ```javascript
   const formData = new FormData();
   formData.append('session_id', stage2SessionId);
   formData.append('case_position', 'plaintiff');
   formData.append('analysis_scenario', 'pre_litigation');
   formData.append('analysis_result', JSON.stringify(stage2AnalysisResult));

   const response = await fetch('/api/v1/litigation-analysis/generate-drafts', {
     method: 'POST',
     body: formData
   });
   ```

3. **显示生成的文书列表**
   - 根据角色和场景自动确定文书类型
     - 原告+准备起诉 → 起诉状 + 证据清单
     - 被告+应诉 → 答辩状 + 证据清单
     - 上诉人+上诉 → 上诉状 + 新证据清单
   - 每个文书显示：
     - 文书名称
     - 需要填写的占位符
     - 预览按钮

4. **用户预览/编辑/下载文书**
   - 点击预览查看完整内容
   - 编辑占位符和其他内容
   - 下载为 MD/PDF/DOCX 格式

### API端点

**请求**: `POST /api/v1/litigation-analysis/generate-drafts`

**请求参数**:
- `session_id`: 阶段2分析的会话ID
- `case_position`: 诉讼地位
- `analysis_scenario`: 分析场景
- `analysis_result`: 阶段2的分析结果（JSON字符串）

**响应**:
```json
{
  "session_id": "stage2_analysis_1234567890",
  "draft_documents": [
    {
      "document_type": "civil_complaint",
      "document_name": "民事起诉状",
      "content": "民事起诉状\n\n原告：某某科技有限公司...\n\n诉讼请求：\n1. 判令被告支付货款...",
      "template_info": {
        "template_file": "civil_complaint.md",
        "template_version": "1.0"
      },
      "placeholders": ["原告地址", "被告地址", "法院名称"],
      "generated_at": "2024-01-15T10:40:00"
    },
    {
      "document_type": "evidence_list",
      "document_name": "证据清单",
      "content": "证据清单\n\n一、书证\n1. 买卖合同（原件）...",
      "template_info": {
        "template_file": "evidence_list.md",
        "template_version": "1.0"
      },
      "placeholders": ["提交人", "提交日期"],
      "generated_at": "2024-01-15T10:40:30"
    }
  ],
  "total_count": 2,
  "completed_at": "2024-01-15T10:40:30"
}
```

---

## 角色和场景组合的文书类型映射

| case_position | analysis_scenario | 生成的文书类型 |
|--------------|-------------------|---------------|
| plaintiff | pre_litigation | 民事起诉状 + 证据清单 |
| defendant | defense | 答辩状 + 证据清单 |
| appellant | appeal | 民事上诉状 + 新证据清单 |
| appellee | appeal | 答辩状 |
| plaintiff | preservation | 财产保全申请书 |
| plaintiff | execution | 强制执行申请书 |

---

## WebSocket 进度推送

### 连接

```javascript
const ws = new WebSocket(`ws://localhost:8000/api/v1/litigation-analysis/ws/${sessionId}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`[${data.progress}] ${data.message}`);

  if (data.type === 'node_progress') {
    updateProgressBar(data.progress, data.message);
  } else if (data.type === 'complete') {
    showCompletionMessage();
  }
};
```

### 进度阶段

- `preorganize`: 预整理（0.0 - 1.0）
- `assemble_rules`: 规则组装（0.0 - 1.0）
- `generate_timeline`: 时间线生成（0.0 - 1.0）
- `analyze_evidence`: 证据分析（0.0 - 1.0）
- `multi_model_analyze`: 模型推演（0.0 - 1.0）
- `generate_strategies`: 策略生成（0.0 - 1.0）
- `generate_report`: 报告生成（0.0 - 1.0）
- `generate_drafts`: 文书生成（阶段3，0.0 - 1.0）

---

## 前端UI建议

### 阶段1页面

- 文件上传区域（拖拽支持）
- 文档分析结果列表（卡片形式）
- 编辑确认面板
- 角色和场景选择下拉框
- "开始深度分析"按钮

### 阶段2页面

- 进度条（WebSocket实时更新）
- 分析报告展示区（Markdown渲染）
- 策略方案对比卡片
- 报告下载按钮（MD/PDF/DOCX）
- "生成法律文书"按钮（突出显示）

### 阶段3弹窗/页面

- 文书列表（卡片形式）
- 占位符提示
- 预览/编辑/下载按钮
- 批量下载功能

---

## 错误处理

### 常见错误

| 错误信息 | 原因 | 解决方案 |
|---------|------|---------|
| `至少需要上传一个文件` | 未上传文件 | 提示用户上传文件 |
| `无效的模块名称: litigation_analysis` | 模块错误 | 检查后端配置 |
| `案件包不存在或未启用` | 案件包ID错误 | 提供正确的案件包ID |
| `preorganized_data 必须是有效的 JSON 格式` | 数据格式错误 | 确保 JSON 序列化正确 |
| `请提供阶段2的分析结果` | 未传递分析结果 | 从阶段2响应中获取并传递 |

---

## 总结

3阶段架构的核心优势：

1. **用户控制**: 每个阶段后都有人工接入点，用户可以确认、编辑、决定是否继续
2. **按需生成**: 文书生成改为按需触发，避免不必要的处理
3. **角色场景**: 支持不同的诉讼地位和分析场景组合
4. **灵活性强**: 用户可以在任意阶段停止，不需要必须完成所有阶段

---

**文档版本**: 1.0
**更新日期**: 2024-01-15
**维护者**: Backend Team
