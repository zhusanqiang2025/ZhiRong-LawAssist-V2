# 案件分析前端3阶段架构优化方案

## 目录
- [当前架构分析](#当前架构分析)
- [问题诊断](#问题诊断)
- [优化方案](#优化方案)
- [实施计划](#实施计划)
- [代码示例](#代码示例)

---

## 当前架构分析

### 现有流程（不符合3阶段架构）

```
┌─────────────────────────────────────────────────────────────────┐
│                    当前前端流程 (LitigationAnalysisPage.tsx)      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  步骤1: 上传文件 → 预整理API                                    │
│    ↓                                                            │
│  步骤2: 显示预整理结果 → 用户编辑/确认                          │
│    ↓                                                            │
│  步骤3: 选择诉讼地位和分析目标 → 调用 /start 分析               │
│    ↓                                                            │
│  步骤4: 显示分析进度 (WebSocket)                                │
│    ↓                                                            │
│  步骤5: 显示分析结果（包含策略）                                 │
│                                                                 │
│  问题：                                                         │
│  ❌ 步骤3直接调用 /start，跳过了新的阶段2 /analyze 接口          │
│  ❌ 步骤5的分析结果中没有"生成法律文书"按钮                      │
│  ❌ 没有阶段3的文书生成界面                                      │
│  ❌ 缺少新的 API 调用函数                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 现有 API 调用对比

| 功能 | 当前前端调用 | 后端新端点 | 状态 |
|------|-------------|-----------|------|
| 预整理 | `POST /preorganize` | `POST /preorganize` | ✅ 兼容 |
| 全案分析 | `POST /start` | `POST /analyze` | ❌ 需要更新 |
| 文书生成 | 无（自动生成） | `POST /generate-drafts` | ❌ 需要添加 |
| 获取结果 | `GET /result/:id` | `GET /result/:id` | ✅ 兼容 |

### 现有数据流对比

```
当前流程：
用户上传 → 预整理 → 选择角色/目标 → /start → WebSocket → 结果显示

新流程（3阶段）：
阶段1: 用户上传 → 预整理 → 显示结果 + 角色场景选择
阶段2: 点击"开始深度分析" → /analyze → WebSocket → 显示报告 + "生成文书"按钮
阶段3: 点击"生成法律文书" → /generate-drafts → 显示文书列表
```

---

## 问题诊断

### 🔴 P0 - 严重问题（阻塞功能）

1. **API 端点未更新**
   - 步骤3 (`handleStartAnalysis`) 调用的是旧的 `startCaseAnalysis`
   - 应该调用新的 `/analyze` 端点（阶段2）
   - 缺少 `analysis_scenario` 参数传递

2. **缺少阶段2/阶段3的步骤**
   - 当前只有 5 个步骤 (0-4)
   - 需要增加：
     - 步骤 5: 阶段2分析结果展示（带"生成文书"按钮）
     - 步骤 6: 阶段3文书生成展示

3. **缺少 API 函数**
   - `litigationAnalysis.ts` 中没有：
     - `analyzeLitigationCase()` - 阶段2分析
     - `generateLitigationDocuments()` - 阶段3文书生成

4. **类型定义缺失**
   - `litigationAnalysis.ts` 中没有：
     - `DraftDocument` - 文书草稿类型
     - `GenerateDraftsResult` - 文书生成结果类型
     - `AnalysisScenario` - 分析场景枚举

### 🟡 P1 - 中等问题（影响用户体验）

1. **角色和场景选项不完整**
   - `litigationConfig.ts` 中只有 6 个角色选项
   - 后端支持 7 个角色（缺少 `third_party`）
   - 场景选项完全缺失（应包含 7 个场景）

2. **步骤指示器需要更新**
   - 当前只有 5 个步骤的描述
   - 需要增加到 7 个步骤（包含阶段2和阶段3）

3. **WebSocket 进度阶段需要更新**
   - 当前监听的进度阶段与后端不一致
   - 需要监听新的进度阶段：
     - `assemble_rules` - 规则组装
     - `analyze_evidence` - 证据分析
     - `multi_model_analyze` - 模型推演
     - `generate_strategies` - 策略生成
     - `generate_report` - 报告生成
     - `generate_drafts` - 文书生成（阶段3）

### 🟢 P2 - 轻微问题（可后续优化）

1. **错误处理不完整**
   - 缺少阶段2/阶段3的特定错误处理

2. **会话持久化需要扩展**
   - 需要保存新增的状态：
     - `analysisScenario`
     - `stage2Result`
     - `draftDocuments`

---

## 优化方案

### 方案 A：最小改动方案（推荐快速上线）

**目标**：1-2天内完成，实现基本的3阶段流程

**改动范围**：
- 修改 `LitigationAnalysisPage.tsx` 的步骤3调用
- 添加步骤5（阶段2结果展示）
- 添加步骤6（阶段3文书展示）
- 添加必要的 API 函数和类型定义

**优点**：
- 快速实现核心功能
- 改动最小，风险可控
- 向后兼容

**缺点**：
- 用户交互体验不是最优
- 需要后续优化

### 方案 B：完整重构方案（推荐长期维护）

**目标**：1周内完成，实现最佳用户体验

**改动范围**：
- 创建独立的组件：
  - `<RoleScenarioSelector />` - 角色场景选择组件
  - `<Stage2ResultDisplay />` - 阶段2结果展示组件
  - `<DraftDocumentList />` - 文书列表组件
- 重构状态管理
- 优化 WebSocket 进度显示
- 添加动画和过渡效果

**优点**：
- 代码更清晰，易维护
- 用户体验最佳
- 可复用组件

**缺点**：
- 开发时间长
- 测试工作量大

---

## 实施计划

### 阶段 1: 核心功能修复（P0）- 预计 4-6 小时

#### 1.1 更新类型定义
**文件**: `frontend/src/types/litigationAnalysis.ts`

**新增内容**:
```typescript
// ==================== 分析场景枚举 ====================
export enum AnalysisScenario {
  PRE_LITIGATION = 'pre_litigation',     // 准备起诉
  DEFENSE = 'defense',                   // 应诉准备
  APPEAL = 'appeal',                     // 上诉
  EXECUTION = 'execution',               // 执行阶段
  PRESERVATION = 'preservation',         // 财产保全
  EVIDENCE_COLLECTION = 'evidence_collection',  // 证据收集
  MEDIATION = 'mediation'                // 调解准备
}

// ==================== 文书草稿类型 ====================
export interface DraftDocument {
  document_type: string;
  document_name: string;
  content: string;
  template_info: {
    template_file: string;
    template_version: string;
  };
  placeholders: string[];
  generated_at: string;
}

// ==================== 文书生成结果 ====================
export interface GenerateDraftsResult {
  session_id: string;
  draft_documents: DraftDocument[];
  total_count: number;
  completed_at: string;
}

// ==================== 阶段2分析结果 ====================
export interface Stage2AnalysisResult {
  session_id: string;
  status: string;
  case_type: string;
  case_position: string;
  analysis_scenario: string;
  assembled_rules: string[];
  timeline: {
    events: Array<{
      date: string;
      description: string;
      source: string;
    }>;
  };
  evidence_analysis: {
    admissibility_assessment: string;
    analysis_points: Array<{
      issue: string;
      evidence_ref: string;
    }>;
    missing_evidence?: string[];
    impeachment_strategy?: string[];
  };
  model_results: {
    final_strength: number;
    confidence: number;
    final_summary: string;
    final_facts: string[];
    final_legal_arguments: string[];
    rule_application: string[];
    final_strengths: string[];
    final_weaknesses: string[];
    conclusion: string;
  };
  strategies: Array<{
    title: string;
    type: string;
    description: string;
    steps: Array<{
      step_name: string;
      description: string;
    }>;
    recommendation_score: number;
  }>;
  final_report: string;
  report_json: {
    meta: {
      generated_at: string;
      case_type: string;
      scenario: string;
      draft_documents_available: boolean;
    };
    dashboard: {
      win_rate: number;
      confidence: number;
      key_facts_count: number;
      risk_count: number;
      strategies_count: number;
    };
    content: {
      summary: string;
      facts: string[];
      timeline: any;
      strategies: any[];
    };
  };
  completed_at: string;
}
```

#### 1.2 更新配置文件
**文件**: `frontend/src/config/litigationConfig.ts`

**新增内容**:
```typescript
export const analysisScenarioOptions = [
  { value: 'pre_litigation', label: '准备起诉', icon: '📋', description: '评估起诉可行性，制定诉讼策略' },
  { value: 'defense', label: '应诉准备', icon: '🛡️', description: '分析对方起诉，制定抗辩策略' },
  { value: 'appeal', label: '上诉分析', icon: '📝', description: '分析一审判决，制定上诉策略' },
  { value: 'execution', label: '执行阶段', icon: '⚖️', description: '判决执行策略、财产线索分析' },
  { value: 'preservation', label: '财产保全', icon: '🔒', description: '财产保全、证据保全申请策略' },
  { value: 'evidence_collection', label: '证据收集', icon: '🔍', description: '证据收集计划和策略' },
  { value: 'mediation', label: '调解准备', icon: '🤝', description: '调解谈判策略和准备' }
];

export const positionOptions = [
  { value: 'plaintiff', label: '原告', icon: '👤' },
  { value: 'defendant', label: '被告', icon: '👥' },
  { value: 'appellant', label: '上诉人', icon: '📝' },
  { value: 'appellee', label: '被上诉人', icon: '📄' },
  { value: 'applicant', label: '申请人', icon: '📋' },
  { value: 'respondent', label: '被申请人', icon: '📋' },
  { value: 'third_party', label: '第三人', icon: '👥' }
];
```

#### 1.3 更新 API 函数
**文件**: `frontend/src/api/litigationAnalysis.ts`

**新增函数**:
```typescript
// ==================== 阶段2：全案分析 ====================

/**
 * 阶段2：全案分析（不包含文书生成）
 */
export const analyzeLitigationCase = async (params: {
  preorganized_data: LitigationPreorganizationResult;
  case_position: string;
  analysis_scenario: string;
  case_package_id: string;
  case_type?: string;
  user_input?: string;
  analysis_mode?: string;
  selected_model?: string;
}) => {
  const formData = new FormData();
  formData.append('preorganized_data', JSON.stringify(params.preorganized_data));
  formData.append('case_position', params.case_position);
  formData.append('analysis_scenario', params.analysis_scenario);
  formData.append('case_package_id', params.case_package_id);

  if (params.case_type) formData.append('case_type', params.case_type);
  if (params.user_input) formData.append('user_input', params.user_input);
  if (params.analysis_mode) formData.append('analysis_mode', params.analysis_mode);
  if (params.selected_model) formData.append('selected_model', params.selected_model);

  const response = await axiosInstance.post(`${BASE_URL}/analyze`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });

  return response.data;
};

// ==================== 阶段3：文书生成 ====================

/**
 * 阶段3：按需生成法律文书
 */
export const generateLitigationDocuments = async (params: {
  session_id: string;
  case_position: string;
  analysis_scenario: string;
  analysis_result?: Stage2AnalysisResult;
}) => {
  const formData = new FormData();
  formData.append('session_id', params.session_id);
  formData.append('case_position', params.case_position);
  formData.append('analysis_scenario', params.analysis_scenario);

  if (params.analysis_result) {
    formData.append('analysis_result', JSON.stringify(params.analysis_result));
  }

  const response = await axiosInstance.post(`${BASE_URL}/generate-drafts`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  });

  return response.data;
};

// ==================== 导出更新 ====================

export const caseAnalysisApi = {
  // ... 现有方法 ...

  // 阶段2：全案分析
  analyzeLitigationCase,

  // 阶段3：文书生成
  generateLitigationDocuments,
};
```

### 阶段 2: 页面组件修改（P0）- 预计 6-8 小时

#### 2.1 修改 LitigationAnalysisPage.tsx

**主要改动点**:

1. **新增状态变量**（约第100行后）:
```typescript
// 新增：分析场景（阶段2需要）
const [analysisScenario, setAnalysisScenario] = useState<AnalysisScenario | null>(null);

// 新增：阶段2分析结果
const [stage2Result, setStage2Result] = useState<Stage2AnalysisResult | null>(null);

// 新增：阶段3文书生成结果
const [draftDocuments, setDraftDocuments] = useState<GenerateDraftsResult | null>(null);

// 新增：文书生成中状态
const [generatingDrafts, setGeneratingDrafts] = useState<boolean>(false);
```

2. **修改会话持久化接口**（约第120行）:
```typescript
interface LitigationSessionData {
  step: number;
  inferredCaseType: CaseType | null;
  uploadedFiles: string[];
  preorganizationResult: LitigationPreorganizationResult | null;
  litigationPosition: LitigationPosition | null;
  analysisGoal: AnalysisGoal | null;
  customGoal: string;
  backgroundInfo: string;
  focusPoints: string;
  analysisScenario: AnalysisScenario | null; // 新增
  analysisStatus: string;
  analysisProgress: number;
  stage2Result: Stage2AnalysisResult | null; // 新增
}
```

3. **修改 handleStartAnalysis 函数**（约第293行）:
```typescript
const handleStartStage2Analysis = async () => {
  if (!litigationPosition) {
    message.warning('请选择诉讼地位');
    return;
  }

  if (!analysisScenario) {  // 改为检查 analysisScenario
    message.warning('请选择分析场景');
    return;
  }

  setAnalysisStatus('uploading');
  setCurrentStep(3); // 分析进度步骤

  try {
    const effectiveCaseType = inferredCaseType || 'contract_performance';

    // 调用阶段2 API
    const response = await caseAnalysisApi.analyzeLitigationCase({
      preorganized_data: preorganizationResult!,
      case_position: litigationPosition,
      analysis_scenario: analysisScenario,
      case_package_id: `${effectiveCaseType}_v1`,
      case_type: effectiveCaseType,
      user_input: backgroundInfo || focusPoints,
      analysis_mode: 'multi'
    });

    setSessionId(response.session_id);
    setAnalysisStatus('analyzing');

    // 保存会话状态
    saveSession(response.session_id, {
      step: 3,
      inferredCaseType,
      uploadedFiles: uploadedFiles.map(f => f.name),
      preorganizationResult,
      litigationPosition,
      analysisGoal,
      customGoal,
      backgroundInfo,
      focusPoints,
      analysisScenario, // 新增
      analysisStatus: 'analyzing',
      analysisProgress: 0
    });

  } catch (error: any) {
    console.error('Failed to start stage2 analysis:', error);
    message.error(error.response?.data?.detail || '启动分析失败');
    setAnalysisStatus('idle');
    setCurrentStep(2); // 回到上一步
  }
};
```

4. **修改步骤3渲染函数**（约第868行）:
```typescript
const renderStep3 = () => (
  <Card title="步骤3：选择分析场景">
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Alert
        message="已识别案件类型"
        description={
          <Space>
            <Tag color="blue">
              {caseTypeOptions.find(o => o.value === inferredCaseType)?.label}
            </Tag>
          </Space>
        }
        type="info"
        showIcon
      />

      {/* 诉讼地位选择 */}
      <div>
        <Text strong>诉讼地位</Text>
        <Divider style={{ margin: '12px 0' }} />
        <Row gutter={[16, 16]}>
          {positionOptions.map(pos => (
            <Col span={6} key={pos.value}>
              <Card
                hoverable
                style={{
                  border: litigationPosition === pos.value ? '2px solid #52c41a' : undefined,
                  cursor: 'pointer'
                }}
                onClick={() => setLitigationPosition(pos.value as any)}
              >
                <div style={{ textAlign: 'center' }}>
                  <Text style={{ fontSize: 24 }}>{pos.icon}</Text>
                  <div style={{ marginTop: 8 }}>
                    <Text strong>{pos.label}</Text>
                  </div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {/* 分析场景选择 - 新增 */}
      <div>
        <Text strong>分析场景</Text>
        <Text type="secondary" style={{ marginLeft: 8 }}>（必填）</Text>
        <Divider style={{ margin: '12px 0' }} />
        <Row gutter={[16, 16]}>
          {analysisScenarioOptions.map(scenario => (
            <Col span={8} key={scenario.value}>
              <Card
                hoverable
                style={{
                  border: analysisScenario === scenario.value ? '2px solid #1890ff' : undefined,
                  cursor: 'pointer',
                  height: '100%'
                }}
                onClick={() => setAnalysisScenario(scenario.value as any)}
              >
                <div style={{ textAlign: 'center' }}>
                  <Text style={{ fontSize: 32 }}>{scenario.icon}</Text>
                  <div style={{ marginTop: 8 }}>
                    <Text strong style={{ fontSize: 14 }}>{scenario.label}</Text>
                  </div>
                  <div style={{ marginTop: 4 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {scenario.description}
                    </Text>
                  </div>
                </div>
              </Card>
            </Col>
          ))}
        </Row>
      </div>

      {/* 背景信息（可选） */}
      <div>
        <Text strong>背景情况说明</Text>
        <Text type="secondary" style={{ marginLeft: 8 }}>（可选）</Text>
        <TextArea
          value={backgroundInfo}
          onChange={e => setBackgroundInfo(e.target.value)}
          rows={4}
          placeholder="补充说明案件背景情况..."
        />
      </div>

      {/* 操作按钮 */}
      <div style={{ textAlign: 'right' }}>
        <Space>
          <Button onClick={() => setCurrentStep(1)}>上一步</Button>
          <Button
            type="primary"
            size="large"
            icon={<SendOutlined />}
            onClick={handleStartStage2Analysis}
            disabled={!litigationPosition || !analysisScenario}
            loading={analysisStatus === 'uploading'}
          >
            开始深度分析
          </Button>
        </Space>
      </div>
    </Space>
  </Card>
);
```

5. **修改 WebSocket 消息处理**（约第197行）:
```typescript
const handleWebSocketMessage = (data: any) => {
  console.log('WebSocket message:', data);

  switch (data.type) {
    case 'node_progress':
      setAnalysisProgress((data.progress || 0) * 100);
      setAnalysisMessage(data.message || '');
      setAnalysisStage(data.stage || '');
      break;

    case 'complete':
      setAnalysisProgress(100);
      setAnalysisMessage('分析完成');
      // 获取阶段2结果
      fetchStage2Result();
      break;

    case 'error':
      setAnalysisStatus('failed');
      message.error(data.message || '分析失败');
      break;

    // 可以添加更多中间结果的实时展示
    case 'evidence_analysis':
      // 实时展示证据分析结果
      break;
    case 'strategies_generated':
      // 实时展示策略
      break;
  }
};

const fetchStage2Result = async () => {
  try {
    const response = await caseAnalysisApi.getCaseResult(sessionId);
    setStage2Result(response);
    setAnalysisStatus('completed');
    setCurrentStep(4); // 进入步骤5：阶段2结果展示
    message.success('深度分析完成！');
  } catch (error: any) {
    console.error('Failed to fetch stage2 result:', error);
    message.error('获取结果失败');
  }
};
```

6. **新增步骤5：阶段2结果展示**（插入到 renderStep5 之前）:
```typescript
const renderStep5 = () => {
  if (!stage2Result) return null;

  const { model_results, evidence_analysis, strategies, final_report } = stage2Result;

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* 操作按钮 */}
      <Card>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重新分析
          </Button>
          <Button onClick={() => navigate('/')}>返回首页</Button>
          <Button
            type="primary"
            icon={<FileTextOutlined />}
            onClick={handleGenerateDrafts}
            loading={generatingDrafts}
          >
            生成法律文书
          </Button>
        </Space>
      </Card>

      {/* 核心结论 */}
      <Card title="核心结论">
        <Row gutter={16}>
          <Col span={8}>
            <Statistic
              title="胜诉率/成功率"
              value={(model_results.final_strength * 100).toFixed(1)}
              suffix="%"
              precision={1}
              valueStyle={{
                color: model_results.final_strength > 0.7 ? '#3f8600' :
                       model_results.final_strength < 0.4 ? '#cf1322' : '#faad14'
              }}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="模型置信度"
              value={(model_results.confidence * 100).toFixed(0)}
              suffix="%"
              precision={0}
            />
          </Col>
          <Col span={8}>
            <Statistic
              title="策略数量"
              value={strategies.length}
              suffix="个"
            />
          </Col>
        </Row>
        <Divider />
        <ReactMarkdown>{model_results.final_summary}</ReactMarkdown>
        <Alert
          style={{ marginTop: 16 }}
          message="最终意见"
          description={model_results.conclusion}
          type="info"
          showIcon
        />
      </Card>

      {/* 事实认定与时间线 */}
      <Card title="事实认定与时间线">
        <Collapse>
          <Panel header="关键法律事实" key="facts">
            <List
              dataSource={model_results.final_facts}
              renderItem={(fact, idx) => (
                <List.Item>
                  <Text>{idx + 1}. {fact}</Text>
                </List.Item>
              )}
            />
          </Panel>
          <Panel header="时间线" key="timeline">
            <Timeline>
              {stage2Result.timeline.events.map((event, idx) => (
                <Timeline.Item key={idx}>
                  <Tag color="blue">{event.date}</Tag>
                  <Text>{event.description}</Text>
                  <Text type="secondary" style={{ marginLeft: 8 }}>
                    来源: {event.source}
                  </Text>
                </Timeline.Item>
              ))}
            </Timeline>
          </Panel>
        </Collapse>
      </Card>

      {/* 法律分析 */}
      <Card title="法律分析">
        <Tabs>
          <Tabs.TabPane tab="核心主张" key="arguments">
            <Space direction="vertical" style={{ width: '100%' }}>
              {model_results.final_legal_arguments.map((arg, idx) => (
                <Alert key={idx} message={`主张 ${idx + 1}`} description={arg} type="info" />
              ))}
            </Space>
          </Tabs.TabPane>
          <Tabs.TabPane tab="规则适用" key="rules">
            <List
              dataSource={model_results.rule_application}
              renderItem={(rule, idx) => (
                <List.Item>
                  <Text>{idx + 1}. {rule}</Text>
                </List.Item>
              )}
            />
          </Tabs.TabPane>
          <Tabs.TabPane tab="优劣势分析" key="swot">
            <Row gutter={16}>
              <Col span={12}>
                <Card type="inner" title="有利因素" size="small">
                  <List
                    dataSource={model_results.final_strengths}
                    renderItem={(strength) => (
                      <List.Item>
                        <Text>✅ {strength}</Text>
                      </List.Item>
                    )}
                  />
                </Card>
              </Col>
              <Col span={12}>
                <Card type="inner" title="风险因素" size="small">
                  <List
                    dataSource={model_results.final_weaknesses}
                    renderItem={(weakness) => (
                      <List.Item>
                        <Text>⚠️ {weakness}</Text>
                      </List.Item>
                    )}
                  />
                </Card>
              </Col>
            </Row>
          </Tabs.TabPane>
        </Tabs>
      </Card>

      {/* 证据审查 */}
      {evidence_analysis && (
        <Card title="证据审查">
          <Alert
            message="整体评价"
            description={evidence_analysis.admissibility_assessment}
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
          <Collapse>
            <Panel header="具体审查意见" key="points">
              <List
                dataSource={evidence_analysis.analysis_points}
                renderItem={(point, idx) => (
                  <List.Item>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Text strong>问题 {idx + 1}</Text>
                      <Text>{point.issue}</Text>
                      {point.evidence_ref && (
                        <Text type="secondary">证据: {point.evidence_ref}</Text>
                      )}
                    </Space>
                  </List.Item>
                )}
              />
            </Panel>
            {evidence_analysis.missing_evidence && evidence_analysis.missing_evidence.length > 0 && (
              <Panel header="证据缺口" key="missing">
                <Alert
                  message="需要补充的证据"
                  description={
                    <List
                      dataSource={evidence_analysis.missing_evidence}
                      renderItem={(item) => (
                        <List.Item>
                          <Text>- [ ] {item}</Text>
                        </List.Item>
                      )}
                    />
                  }
                  type="warning"
                  showIcon
                />
              </Panel>
            )}
            {evidence_analysis.impeachment_strategy && evidence_analysis.impeachment_strategy.length > 0 && (
              <Panel header="质证策略" key="impeachment">
                <List
                  dataSource={evidence_analysis.impeachment_strategy}
                  renderItem={(strategy) => (
                    <List.Item>
                      <Text>🛡️ {strategy}</Text>
                    </List.Item>
                  )}
                />
              </Panel>
            )}
          </Collapse>
        </Card>
      )}

      {/* 行动策略 */}
      <Card title="行动策略方案">
        <Row gutter={16}>
          {strategies.map((strategy, idx) => (
            <Col span={8} key={idx}>
              <Card
                type="inner"
                title={
                  <Space>
                    <Text>方案 {idx + 1}</Text>
                    <Tag color={
                      strategy.type === 'aggressive' ? 'red' :
                      strategy.type === 'moderate' ? 'orange' : 'blue'
                    }>
                      {strategy.type === 'aggressive' ? '激进' :
                       strategy.type === 'moderate' ? '稳健' : '保守'}
                    </Tag>
                    <Text type="secondary">
                      {'⭐'.repeat(strategy.recommendation_score || 0)}
                    </Text>
                  </Space>
                }
                style={{ height: '100%' }}
              >
                <Paragraph>{strategy.description}</Paragraph>
                <Divider />
                <Text strong>执行步骤：</Text>
                <List
                  size="small"
                  dataSource={strategy.steps}
                  renderItem={(step) => (
                    <List.Item>
                      <Text strong>{step.step_name}</Text>
                      <Paragraph style={{ margin: 0, marginTop: 4 }}>
                        {step.description}
                      </Paragraph>
                    </List.Item>
                  )}
                />
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      {/* 完整报告 */}
      <Card
        title="完整分析报告"
        extra={
          <Space>
            <Button
              size="small"
              onClick={() => {
                navigator.clipboard.writeText(final_report);
                message.success('报告已复制到剪贴板');
              }}
            >
              复制
            </Button>
            <Button
              size="small"
              type="primary"
              icon={<DownloadOutlined />}
              onClick={handleDownloadReport}
            >
              下载
            </Button>
          </Space>
        }
      >
        <div style={{ maxHeight: 600, overflow: 'auto' }}>
          <ReactMarkdown>{final_report}</ReactMarkdown>
        </div>
      </Card>

      {/* 免责声明 */}
      <Alert
        message="免责声明"
        description="本报告由人工智能系统辅助生成，仅供法律专业人士参考，不构成正式的法律意见或担保。法律结果受多种不可控因素影响，请务必咨询专业律师以获得针对性指导。"
        type="warning"
        showIcon
      />
    </Space>
  );
};
```

7. **新增文书生成处理函数**:
```typescript
const handleGenerateDrafts = async () => {
  if (!sessionId || !litigationPosition || !analysisScenario) {
    message.error('缺少必要信息');
    return;
  }

  setGeneratingDrafts(true);

  try {
    const response = await caseAnalysisApi.generateLitigationDocuments({
      session_id: sessionId,
      case_position: litigationPosition,
      analysis_scenario: analysisScenario,
      analysis_result: stage2Result || undefined
    });

    setDraftDocuments(response);
    setCurrentStep(5); // 进入步骤6：文书展示
    message.success(`成功生成 ${response.total_count} 个法律文书`);
  } catch (error: any) {
    console.error('Failed to generate drafts:', error);
    message.error(error.response?.data?.detail || '文书生成失败');
  } finally {
    setGeneratingDrafts(false);
  }
};
```

8. **新增步骤6：文书展示**:
```typescript
const renderStep6 = () => {
  if (!draftDocuments) return null;

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* 操作按钮 */}
      <Card>
        <Space>
          <Button onClick={() => setCurrentStep(4)}>返回分析报告</Button>
          <Button icon={<ReloadOutlined />} onClick={handleReset}>
            重新分析
          </Button>
        </Space>
      </Card>

      {/* 文书列表 */}
      <Card title={`生成的法律文书（${draftDocuments.total_count}个）`}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {draftDocuments.draft_documents.map((doc, idx) => (
            <Card
              key={idx}
              type="inner"
              title={
                <Space>
                  <FileTextOutlined />
                  <Text strong>{doc.document_name}</Text>
                  <Tag color="blue">{doc.document_type}</Tag>
                </Space>
              }
              extra={
                <Space>
                  <Button size="small">编辑</Button>
                  <Button
                    size="small"
                    type="primary"
                    icon={<DownloadOutlined />}
                    onClick={() => handleDownloadDocument(doc)}
                  >
                    下载
                  </Button>
                </Space>
              }
            >
              {doc.placeholders && doc.placeholders.length > 0 && (
                <Alert
                  message="需要填写的信息"
                  description={
                    <Space wrap>
                      {doc.placeholders.map((p, i) => (
                        <Tag key={i} color="warning">{p}</Tag>
                      ))}
                    </Space>
                  }
                  type="warning"
                  showIcon
                  style={{ marginBottom: 16 }}
                />
              )}

              <Collapse>
                <Panel header="查看完整内容" key="content">
                  <div style={{ maxHeight: 400, overflow: 'auto' }}>
                    <ReactMarkdown>{doc.content}</ReactMarkdown>
                  </div>
                </Panel>
              </Collapse>

              <div style={{ marginTop: 8 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  生成时间: {new Date(doc.generated_at).toLocaleString('zh-CN')}
                </Text>
              </div>
            </Card>
          ))}
        </Space>
      </Card>

      {/* 批量操作 */}
      <Card title="批量操作">
        <Space>
          <Button
            type="primary"
            icon={<DownloadOutlined />}
            onClick={() => handleDownloadAllDocuments(draftDocuments.draft_documents)}
          >
            下载全部文书
          </Button>
          <Button onClick={() => navigate('/document-drafting')}>
            在文书起草模块中编辑
          </Button>
        </Space>
      </Card>
    </Space>
  );
};

const handleDownloadDocument = (doc: DraftDocument) => {
  const blob = new Blob([doc.content], { type: 'text/markdown' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${doc.document_name}.md`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

const handleDownloadAllDocuments = (docs: DraftDocument[]) => {
  docs.forEach((doc, idx) => {
    setTimeout(() => {
      handleDownloadDocument(doc);
    }, idx * 500); // 延迟下载避免浏览器阻止
  });
};
```

9. **更新步骤指示器**（约第1304行）:
```typescript
<Steps
  current={currentStep}
  items={[
    { title: '上传文件', description: '上传案件文档，系统自动识别类型' },
    { title: '预整理结果', description: '确认文件识别结果和关键信息' },
    { title: '选择场景', description: '选择诉讼地位和分析场景' },
    { title: '深度分析', description: '多模型并行分析' },
    { title: '分析报告', description: '查看完整的分析报告' },
    { title: '法律文书', description: '生成和下载法律文书草稿' }
  ]}
/>
```

10. **更新渲染路由**（约第1318行）:
```typescript
{currentStep === 0 && renderStep1()}
{currentStep === 1 && renderStep2()}
{currentStep === 2 && renderStep3()}
{currentStep === 3 && renderStep4()}
{currentStep === 4 && renderStep5()}
{currentStep === 5 && renderStep6()}
```

### 阶段 3: UI 优化（P1-P2）- 预计 4-6 小时

1. **添加加载动画和过渡效果**
2. **优化移动端适配**
3. **添加错误提示和重试机制**
4. **优化文书预览体验**

---

## 验证测试计划

### 功能测试

1. **阶段1测试**:
   - 上传文件 → 预整理成功
   - 编辑预整理结果 → 保存成功
   - 选择诉讼地位和分析场景 → 进入阶段2

2. **阶段2测试**:
   - 点击"开始深度分析" → 调用 `/analyze` API
   - WebSocket 进度更新正常
   - 显示分析报告，包含"生成法律文书"按钮

3. **阶段3测试**:
   - 点击"生成法律文书" → 调用 `/generate-drafts` API
   - 显示文书列表
   - 预览/编辑/下载功能正常

### 兼容性测试

- Chrome/Edge (最新版)
- Firefox (最新版)
- Safari (最新版)
- 移动端浏览器

### 性能测试

- 大文件上传性能
- WebSocket 连接稳定性
- 长报告渲染性能

---

## 总结

### 关键改动点

| 文件 | 改动内容 | 优先级 |
|------|---------|--------|
| `types/litigationAnalysis.ts` | 新增类型定义 | P0 |
| `config/litigationConfig.ts` | 新增场景选项 | P0 |
| `api/litigationAnalysis.ts` | 新增 API 函数 | P0 |
| `LitigationAnalysisPage.tsx` | 修改页面逻辑 | P0 |

### 预计工作量

- **P0 核心功能**: 10-14 小时
- **P1 UI 优化**: 4-6 小时
- **P2 可选优化**: 2-4 小时

**总计**: 约 16-24 小时（2-3个工作日）

### 风险评估

- **低风险**: 类型定义、配置文件更新
- **中风险**: 页面组件修改、API 调用逻辑
- **高风险**: WebSocket 逻辑修改、状态管理

**缓解措施**:
- 保留旧代码注释，方便回滚
- 分阶段测试，确保每阶段功能正常
- 添加错误边界和降级处理

---

**文档版本**: 1.0
**创建日期**: 2026-01-18
**维护者**: Frontend Team
