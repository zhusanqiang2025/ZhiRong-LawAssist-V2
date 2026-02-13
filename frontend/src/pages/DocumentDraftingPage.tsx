// frontend/src/pages/DocumentDraftingPage.tsx
import React, { useState, useEffect, useRef } from 'react';
import {
  Card,
  Steps,
  Form,
  Input,
  Upload,
  Button,
  Select,
  Spin,
  message,
  Row,
  Col,
  Typography,
  Space,
  Divider,
  Alert
} from 'antd';
import {
  UploadOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  LoadingOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import ModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
import api from '../api';
import { useSessionPersistence } from '../hooks/useSessionPersistence';
import './DocumentDraftingPage.css';

const { Step } = Steps;
const { TextArea } = Input;
const { Option } = Select;
const { Title, Text, Paragraph } = Typography;

interface DocumentType {
  id: string;
  name: string;
  description: string;
  category: string;
}

interface GeneratedDocument {
  document_type: string;
  document_name: string;
  content: string;
  format: string;
  strategy: string;
}

const DocumentDraftingPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [currentStep, setCurrentStep] = useState(0);
  const [selectedType, setSelectedType] = useState<string>('');
  const [userInput, setUserInput] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [generatedContent, setGeneratedContent] = useState('');
  const [documentTypes, setDocumentTypes] = useState<DocumentType[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(true);

  // ========== 会话持久化 ==========
  interface DocumentDraftingSessionData {
    step: number;
    selectedType: string;
    userInput: string;
    uploadedFiles: string[]; // 文件名列表
    generatedContent: string;
  }

  // 使用 ref 来追踪是否已经恢复过会话，避免重复恢复
  const hasRestoredRef = useRef(false);
  const isRestoringRef = useRef(false);

  const {
    hasSession,
    saveSession,
    clearSession,
    isLoading: isRestoringSession
  } = useSessionPersistence<DocumentDraftingSessionData>('document_drafting_session', {
    expirationTime: 2 * 60 * 60 * 1000, // 2小时
    autoRestore: false, // 禁用自动恢复，手动控制恢复时机
    onRestore: (sessionId, data) => {
      console.log('[文书起草] 恢复会话:', data);
      isRestoringRef.current = true;

      setCurrentStep(data.step);
      setSelectedType(data.selectedType || '');
      setUserInput(data.userInput || '');
      setGeneratedContent(data.generatedContent || '');

      // 标记恢复完成（延迟到下一个事件循环，避免在状态更新期间触发）
      setTimeout(() => {
        hasRestoredRef.current = true;
        isRestoringRef.current = false;
      }, 0);
    }
  });

  // 保存会话状态
  const saveCurrentState = () => {
    // 如果正在恢复会话，则不保存
    if (isRestoringRef.current) {
      console.log('[文书起草] 正在恢复会话，跳过保存');
      return;
    }

    saveSession(Date.now().toString(), {
      step: currentStep,
      selectedType,
      userInput,
      uploadedFiles: uploadedFiles.map(f => f.name || f.uid),
      generatedContent
    });
  };

  // 手动控制会话恢复（仅在组件首次挂载时执行一次）
  useEffect(() => {
    // 如果已经恢复过，或者正在恢复，则跳过
    if (hasRestoredRef.current || isRestoringRef.current) {
      return;
    }

    // 检查是否有可恢复的会话
    if (hasSession) {
      console.log('[文书起草] 检测到会话，准备恢复');
      isRestoringRef.current = true;

      // 获取存储的会话数据
      const storedData = localStorage.getItem('document_drafting_session');
      if (storedData) {
        try {
          const session = JSON.parse(storedData);
          if (session.data) {
            // 直接恢复状态
            setCurrentStep(session.data.step || 0);
            setSelectedType(session.data.selectedType || '');
            setUserInput(session.data.userInput || '');
            setGeneratedContent(session.data.generatedContent || '');

            // 显示恢复消息（只显示一次）
            message.success('已恢复之前的文书起草会话');

            // 标记恢复完成
            setTimeout(() => {
              hasRestoredRef.current = true;
              isRestoringRef.current = false;
            }, 100);
          }
        } catch (error) {
          console.error('[文书起草] 恢复会话失败:', error);
          hasRestoredRef.current = true;
          isRestoringRef.current = false;
        }
      } else {
        hasRestoredRef.current = true;
      }
    } else {
      // 没有会话，直接标记完成
      hasRestoredRef.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // 只在组件挂载时执行一次

  // 监听状态变化，自动保存
  useEffect(() => {
    // 只在恢复完成后才保存会话
    if (hasRestoredRef.current && !isRestoringRef.current && !isRestoringSession) {
      if (currentStep > 0 || selectedType || userInput) {
        saveCurrentState();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, selectedType, userInput, generatedContent]);
  // ========== 会话持久化结束 ==========

  // ========== 智能引导和上下文复用穿透 ==========
  useEffect(() => {
    // 从智能引导页面传递过来的参数
    const state = location.state as {
      requirement?: string;
      consultationContext?: {
        target_module: string;
        data: any;
        summary: string;
      };
    } | null;

    if (state?.requirement) {
      setUserInput(state.requirement);
      message.success('已根据您的需求自动填充内容');
    }

    // 【新增】处理从咨询复用的上下文
    if (state?.consultationContext) {
      const { summary } = state.consultationContext;
      console.log('[DocumentDrafting] 接收到复用上下文:', state.consultationContext);

      // 填充用户输入
      if (summary) {
        setUserInput(prev => {
          return prev ? `${prev}\n\n【案情摘要】\n${summary}` : `【案情摘要】\n${summary}`;
        });
        message.success('已自动导入咨询案情信息');
        // 可选：如果 consultationContext.data 中包含 doctype，也可以在这里自动 setSelectedType
        // if (state.consultationContext.data?.document_type) {
        //   setSelectedType(state.consultationContext.data.document_type);
        // }
      }
    }
  }, [location.state]);

  // 加载文书类型列表
  useEffect(() => {
    const fetchTemplates = async () => {
      try {
        setTemplatesLoading(true);
        // 这里应该调用 API 获取文书类型
        // 暂时使用静态数据
        const types: DocumentType[] = [
          { id: 'lawyer_letter', name: '律师函', description: '律师事务所函件，用于催告、通知等', category: 'letter' },
          { id: 'demand_letter', name: '催告函', description: '催告履行义务的函件', category: 'letter' },
          { id: 'notification_letter', name: '通知函', description: '各类通知告知函件', category: 'letter' },
          { id: 'civil_complaint', name: '民事起诉状', description: '民事诉讼起诉状', category: 'judicial' },
          { id: 'defense_statement', name: '答辩状', description: '被告答辩状', category: 'judicial' },
          { id: 'evidence_list', name: '证据清单', description: '诉讼证据清单', category: 'judicial' },
          { id: 'application', name: '申请书', description: '各类申请书（财产保全、先予执行等）', category: 'judicial' },
          { id: 'power_of_attorney', name: '授权委托书', description: '诉讼授权委托书', category: 'judicial' }
        ];
        setDocumentTypes(types);
      } catch (error) {
        console.error('获取文书类型失败:', error);
        message.error('获取文书类型失败');
      } finally {
        setTemplatesLoading(false);
      }
    };

    fetchTemplates();
  }, []);

  const handleGenerate = async () => {
    if (!selectedType) {
      message.warning('请选择文书类型');
      return;
    }

    if (!userInput.trim()) {
      message.warning('请描述您的需求');
      return;
    }

    setLoading(true);
    try {
      const response = await api.post('/document-drafting/generate', {
        user_input: userInput,
        uploaded_files: uploadedFiles.map(f => f.response?.file_path || f.url),
        document_type: selectedType
      });

      if (response.data.status === 'success' && response.data.generated_documents.length > 0) {
        const doc: GeneratedDocument = response.data.generated_documents[0];
        setGeneratedContent(doc.content);
        setCurrentStep(3);
        message.success('文书生成成功！');
      } else {
        message.error(response.data.message || '文书生成失败');
      }
    } catch (error: any) {
      console.error('生成失败:', error);
      message.error(error.response?.data?.detail || '生成失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleBack = () => {
    navigate('/');
  };

  const renderStepContent = () => {
    if (templatesLoading) {
      return (
        <Card style={{ textAlign: 'center', padding: '48px' }}>
          <Spin tip="加载中..." />
        </Card>
      );
    }

    switch (currentStep) {
      case 0:
        return (
          <Card title="选择文书类型" className="step-card">
            <Paragraph type="secondary">
              请选择您需要起草的文书类型，系统将根据您的选择使用相应的专业模板。
            </Paragraph>
            <Select
              style={{ width: '100%', marginBottom: 24 }}
              placeholder="请选择文书类型"
              value={selectedType || undefined}
              onChange={setSelectedType}
              size="large"
            >
              <Option key="letter" disabled style={{ fontWeight: 'bold', background: '#f5f5f5' }}>
                ── 函件类 ──
              </Option>
              {documentTypes.filter(d => d.category === 'letter').map(doc => (
                <Option key={doc.id} value={doc.id}>
                  {doc.name} - {doc.description}
                </Option>
              ))}
              <Option key="judicial" disabled style={{ fontWeight: 'bold', background: '#f5f5f5' }}>
                ── 司法文书类 ──
              </Option>
              {documentTypes.filter(d => d.category === 'judicial').map(doc => (
                <Option key={doc.id} value={doc.id}>
                  {doc.name} - {doc.description}
                </Option>
              ))}
            </Select>
            <div style={{ textAlign: 'right' }}>
              <Button onClick={handleBack} style={{ marginRight: 8 }}>
                返回
              </Button>
              <Button
                type="primary"
                size="large"
                onClick={() => setCurrentStep(1)}
                disabled={!selectedType}
              >
                下一步
              </Button>
            </div>
          </Card>
        );

      case 1:
        return (
          <Card title="描述您的需求" className="step-card">
            <Paragraph type="secondary">
              请详细描述您要起草的文书内容，包括当事人信息、事实经过、具体要求等。
            </Paragraph>
            <Form layout="vertical">
              <Form.Item label="需求描述" required>
                <TextArea
                  rows={8}
                  placeholder="请详细描述您要起草的文书内容...&#10;&#10;例如：&#10;1. 当事人信息（原告/被告、收件人等）&#10;2. 事实经过&#10;3. 具体请求或要求&#10;4. 其他需要说明的情况"
                  value={userInput}
                  onChange={e => setUserInput(e.target.value)}
                />
              </Form.Item>
            </Form>
            <div style={{ textAlign: 'right' }}>
              <Button onClick={() => setCurrentStep(0)} style={{ marginRight: 8 }}>
                上一步
              </Button>
              <Button
                type="primary"
                size="large"
                onClick={() => setCurrentStep(2)}
                disabled={!userInput.trim()}
              >
                下一步
              </Button>
            </div>
          </Card>
        );

      case 2:
        return (
          <Card title="上传相关资料（可选）" className="step-card">
            <Paragraph type="secondary">
              您可以上传相关文件（如合同、证据材料等），系统将提取其中的信息作为参考。此步骤可选。
            </Paragraph>
            <Upload
              fileList={uploadedFiles}
              onChange={({ fileList }) => setUploadedFiles(fileList)}
              beforeUpload={() => false}  // 阻止自动上传
              multiple
            >
              <Button icon={<UploadOutlined />} size="large">
                点击上传文件
              </Button>
            </Upload>
            <Paragraph type="secondary" style={{ marginTop: 16, marginBottom: 24 }}>
              支持的文件格式：PDF、Word、图片等
            </Paragraph>
            <Divider />
            <div style={{ textAlign: 'right' }}>
              <Button onClick={() => setCurrentStep(1)} style={{ marginRight: 8 }}>
                上一步
              </Button>
              <Button
                type="primary"
                size="large"
                onClick={handleGenerate}
                loading={loading}
                icon={loading ? <LoadingOutlined /> : <FileTextOutlined />}
              >
                {loading ? '生成中...' : '生成文书'}
              </Button>
            </div>
          </Card>
        );

      case 3:
        return (
          <Card
            title="生成的文书"
            className="step-card"
            extra={
              <Button onClick={() => setCurrentStep(0)}>
                重新生成
              </Button>
            }
          >
            <div style={{ textAlign: 'center', marginBottom: 24 }}>
              <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
              <Title level={3} style={{ marginTop: 16, marginBottom: 8 }}>
                文书生成成功！
              </Title>
              <Paragraph type="secondary">
                系统已根据您的需求和专业模板生成了以下文书
              </Paragraph>
            </div>

            <div
              className="document-content"
              style={{
                background: '#f5f5f5',
                padding: 24,
                borderRadius: 8,
                marginBottom: 24,
                maxHeight: 600,
                overflow: 'auto',
                whiteSpace: 'pre-wrap',
                lineHeight: 1.8
              }}
            >
              {generatedContent}
            </div>

            <div style={{ textAlign: 'center' }}>
              <Space>
                <Button size="large" onClick={() => setCurrentStep(0)}>
                  重新生成
                </Button>
                <Button type="primary" size="large" onClick={handleBack}>
                  返回工作台
                </Button>
              </Space>
            </div>
          </Card>
        );

      default:
        return null;
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#f0f2f5' }}>
      {/* 统一导航栏 */}
      <ModuleNavBar currentModuleKey="document-drafting" />

      {/* 原有内容区域 */}
      <div style={{ flex: 1, padding: '24px' }}>
        {/* 会话恢复提示 */}
        {hasSession && currentStep === 0 && (
          <Alert
            message="检测到之前的会话"
            description={
              <Space direction="vertical" size="small">
                <Text>系统检测到您之前有一个未完成的文书起草会话。您可以：</Text>
                <Space>
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => {
                      // 触发自动恢复（useSessionPersistence 会自动处理）
                      window.location.reload();
                    }}
                  >
                    继续之前的起草
                  </Button>
                  <Button
                    size="small"
                    onClick={() => {
                      clearSession();
                      message.info('已清除之前的会话，可以开始新的起草');
                    }}
                  >
                    开始新起草
                  </Button>
                </Space>
              </Space>
            }
            type="info"
            showIcon
            closable
            style={{ marginBottom: 16 }}
          />
        )}

        <Card style={{ marginBottom: 24 }}>
          <Row gutter={24} align="middle">
            <Col flex="1">
              <Title level={2} style={{ marginBottom: 8 }}>
                <FileTextOutlined /> 文书起草
              </Title>
              <Paragraph type="secondary" style={{ marginBottom: 0 }}>
                使用专业法律模板，智能起草各类司法文书和函件
              </Paragraph>
            </Col>
          </Row>
        </Card>

        <Card style={{ marginBottom: 24 }}>
          <Steps
            current={currentStep}
            items={[
              { title: '选择类型', description: '选择文书类型' },
              { title: '描述需求', description: '填写文书信息' },
              { title: '上传资料', description: '上传参考文件（可选）' },
              { title: '生成文书', description: '查看生成结果' }
            ]}
          />
        </Card>

        {renderStepContent()}
      </div>
    </div>
  );
};

export default DocumentDraftingPage;
