// frontend/src/pages/LegalConsultationPage.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Button, Input, Layout, message, Typography, Card, Space, Avatar, Divider, Tag, Alert, Checkbox, Tooltip, List } from 'antd';
import { 
  SendOutlined, UserOutlined, CrownOutlined, BankOutlined, SecurityScanOutlined, 
  CheckCircleOutlined, CloseCircleOutlined, PaperClipOutlined, DeleteOutlined, 
  BookOutlined, FileOutlined, PlusCircleOutlined, AppstoreOutlined, SafetyOutlined, 
  FileProtectOutlined, DiffOutlined, EditOutlined, FileTextOutlined, CalculatorOutlined,
  HistoryOutlined, RobotOutlined, ClearOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api, { uploadConsultationFile, deleteConsultationFile, consultLaw, resetConsultationSession } from '../api';
import type { UploadFile } from 'antd/es/upload/interface';
import EnhancedModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
import ModuleKnowledgeToggle from '../components/ModuleKnowledgeToggle';
import ConsultationHistorySidebar from '../components/ConsultationHistorySidebar';
import SessionHistoryButton from '../components/SessionHistoryButton';
import { useConsultationSession } from '../hooks/useConsultationSession';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './LegalConsultationPage.css';

const { Content, Sider } = Layout;
const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

// ================= 类型定义 =================

interface ActionButton {
  id?: string;
  title?: string;
  text?: string;
  type?: 'case_analysis' | 'contract_review' | 'risk_assessment' | 'legal_research' | 'document_review' | 'follow_up_action' | 'comprehensive_analysis' | 'litigation_strategy';
  action?: string;
  route?: string;
  params?: Record<string, any>;
  icon?: string;
  description?: string;
}

interface UploadedFile {
  file_id: string;
  filename: string;
  file_type: string;
  content_preview: string;
  status: 'uploading' | 'done' | 'error';
}

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant' | 'assistant_specialist';
  timestamp: Date;
  suggestions?: string[];
  actionButtons?: ActionButton[];
  confidence?: number;
  isConfirmation?: boolean;
  onConfirm?: (selectedQuestions?: string[]) => void;
  onReject?: () => void;
  suggestedQuestions?: string[];
  directQuestions?: string[];
}

interface ExpertProfile {
  name: string;
  title: string;
  experience: string;
  specializations: string[];
  cases: number;
  success_rate: string;
  avatar: string;
}

// ================= 主组件 =================

const LegalConsultationPage: React.FC = () => {
  // 路由与导航
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();

  // 会话管理 Hook
  const {
    currentSession,
    historySessions,
    isHistorySidebarOpen,
    createNewSession,
    continueSession,
    saveCurrentSession,
    deleteSession,
    toggleHistorySidebar,
    initializeSession,
  } = useConsultationSession();

  // 本地状态
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [consultationStarted, setConsultationStarted] = useState(false);
  const [currentExpertType, setCurrentExpertType] = useState<'assistant' | 'specialist'>('assistant');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  
  // 建议与问题选择状态
  const [selectedSuggestedQuestions, setSelectedSuggestedQuestions] = useState<Record<string, string[]>>({});
  const [customQuestions, setCustomQuestions] = useState<Record<string, string>>({});

  // 动态专家信息（从后端响应中提取）
  const [dynamicSpecialistInfo, setDynamicSpecialistInfo] = useState<{
    role?: string;      // specialist_role
    domain?: string;    // primary_type
  }>({});

  // 会话状态跟踪
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(() => sessionStorage.getItem('consultation_session_id'));
  const [consultationSession, setConsultationSession] = useState<{
    sessionId: string;
    specialistOutput: any;
    isInSpecialistMode: boolean;
  } | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // 保存用户最后一次输入的问题（用于第二阶段调用）
  const lastUserQuestionRef = useRef<string>('');

  // ================= 副作用处理 =================

  // 初始化会话
  useEffect(() => {
    initializeSession();
  }, [initializeSession]);

  // 页面卸载前保存会话
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (messages.length > 0 && currentSession) {
        const data = JSON.stringify({
          session_id: currentSession.sessionId,
          messages: messages,
          title: messages.find(m => m.role === 'user')?.content?.substring(0, 50) + '...' || '对话记录',
          specialist_type: currentExpertType === 'specialist' ? '律师' : undefined
        });
        navigator.sendBeacon('/consultation/save-history', data);
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [messages, currentSession, currentExpertType]);

  // 处理智能引导跳转带来的参数
  useEffect(() => {
    const state = location.state as { initial_input?: string } | null;
    if (state?.initial_input) {
      setInputValue(state.initial_input);
      setConsultationStarted(true);
      // 延迟自动发送，提升体验
      setTimeout(() => handleSendMessage(state.initial_input), 500);
      message.success('已自动带入您的咨询需求');
      // 清除 state 防止刷新重复触发 (React Router 默认保留 state)
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  // 消息列表自动滚动
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // 初始欢迎语
  useEffect(() => {
    if (messages.length === 0) {
      const welcomeMessage: Message = {
        id: 'welcome',
        content: `您好！我是您的智能律师助理。\n\n我可以帮您分析法律问题，识别专业领域，并为您匹配最合适的专业律师进行深度解答。\n\n请描述您遇到的法律困扰，或者上传相关文件（支持 PDF/Word）。`,
        role: 'assistant',
        timestamp: new Date(),
        confidence: 1.0
      };
      setMessages([welcomeMessage]);
    }
  }, []);

  // ================= 逻辑处理函数 =================

  // 专家档案数据
  const expertProfiles = {
    assistant: {
      name: "律师助理",
      title: "智能初诊",
      experience: "AI",
      specializations: ["问题分析", "领域识别"],
      cases: 0,
      success_rate: "-",
      avatar: "assistant"
    },
    specialist: {
      name: "专业律师团队",
      title: "深度咨询",
      experience: "15年+",
      specializations: ["合同", "劳动", "公司", "民商事"],
      cases: 500,
      success_rate: "92%",
      avatar: "expert"
    }
  };
  const currentExpertProfile = expertProfiles[currentExpertType];

  // 开启新会话
  const handleNewChat = async () => {
    if (messages.length > 1) { // 只有欢迎语时不保存
      await saveCurrentSession(messages);
    }
    setMessages([]); // 这里会触发 useEffect 重新加载欢迎语
    setConsultationStarted(false);
    setCurrentExpertType('assistant');
    setUploadedFiles([]);
    setSelectedSuggestedQuestions({});
    setCustomQuestions({});
    setConsultationSession(null);
    setDynamicSpecialistInfo({}); // 清空动态专家信息
    sessionStorage.removeItem('consultation_session_id');
    setCurrentSessionId(null);

    // 【关键】调用后端 API 重置会话
    if (currentSession?.sessionId) {
      try {
        await resetConsultationSession(currentSession.sessionId);
      } catch (error) {
        console.error('重置会话失败:', error);
      }
    }
    await createNewSession();
    message.success('已开启新咨询');
  };

  // 加载历史会话
  const handleLoadHistory = async (sessionId: string) => {
    const session = await continueSession(sessionId);
    if (!session) {
      message.error('加载历史记录失败');
      return;
    }
    setMessages(JSON.parse(JSON.stringify(session.messages)));
    setConsultationStarted(true);
    const hasSpecialist = session.messages.some((m: any) => m.role === 'assistant_specialist');
    setCurrentExpertType(hasSpecialist ? 'specialist' : 'assistant');
    setSelectedSuggestedQuestions({});
    setCustomQuestions({});
    setUploadedFiles([]);
    
    // 更新当前 Session ID
    sessionStorage.setItem('consultation_session_id', sessionId);
    setCurrentSessionId(sessionId);
    
    message.success('历史记录已加载');
  };

  // 发送消息核心逻辑
  const handleSendMessage = async (manualInput?: string) => {
    const contentToSend = manualInput || inputValue;
    if (!contentToSend.trim() && uploadedFiles.length === 0) return;

    // 【关键修复】保存用户原始问题，用于第二阶段调用
    lastUserQuestionRef.current = contentToSend;

    if (!consultationStarted) setConsultationStarted(true);

    // 构建用户消息
    let displayContent = contentToSend;
    if (uploadedFiles.length > 0) {
      const fileNames = uploadedFiles.map(f => f.filename).join('、');
      displayContent = contentToSend
        ? `${contentToSend}\n\n📎 已上传：${fileNames}`
        : `请分析以下文件：${fileNames}`;
    }

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      content: displayContent,
      role: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsTyping(true);

    try {
      const uploadedFileIds = uploadedFiles.filter(f => f.status === 'done').map(f => f.file_id);
      const sessionIdFromStorage = sessionStorage.getItem('consultation_session_id');

      // 【关键】判断是否为新对话的第一条消息
      const isFirstMessageOfNewChat = messages.length <= 1; // 只有欢迎语

      const requestParams: any = {
        question: contentToSend || '请分析我上传的文件',
        uploaded_files: uploadedFileIds.length > 0 ? uploadedFileIds : undefined,
        session_id: sessionIdFromStorage || null,
        // 【关键】如果是新对话的第一条消息，请求后端重置会话
        reset_session: isFirstMessageOfNewChat
      };

      const response = await consultLaw(requestParams);

      // 更新 Session ID
      if (response.session_id) {
        sessionStorage.setItem('consultation_session_id', response.session_id);
        setCurrentSessionId(response.session_id);
      }

      setUploadedFiles([]); // 发送后清空上传列表

      // 处理响应
      if (response.need_confirmation) {
        handleConfirmationResponse(response);
      } else {
        handleNormalResponse(response);
      }

    } catch (error) {
      console.error('发送失败:', error);
      message.error('服务暂时不可用，请稍后再试');
      setMessages(prev => [...prev, {
        id: `error-${Date.now()}`,
        content: '抱歉，连接出现问题。请检查网络或稍后重试。',
        role: 'assistant',
        timestamp: new Date()
      }]);
    } finally {
      setIsTyping(false);
    }
  };

  // 处理普通响应
  const handleNormalResponse = (response: any) => {
    const assistantMessage: Message = {
      id: `assistant-${Date.now()}`,
      content: response.response || response.answer,
      role: response.final_report ? 'assistant_specialist' : 'assistant',
      timestamp: new Date(),
      suggestions: response.suggestions,
      actionButtons: response.action_buttons?.map((btn: any) => ({
        id: btn.key,
        title: btn.label,
        action: btn.key,
        // 根据后端 key 映射到前端 route (简单示例)
        route: btn.key === 'risk_analysis' ? '/risk-analysis' : undefined 
      })),
      confidence: response.confidence
    };
    setMessages(prev => [...prev, assistantMessage]);
    
    if (response.final_report) {
      setConsultationSession(prev => ({
        sessionId: response.session_id,
        specialistOutput: response,
        isInSpecialistMode: true
      }));
    }
  };

  // 处理需要确认的响应（两阶段）
  const handleConfirmationResponse = (response: any) => {
    // 保存专家信息到状态
    if (response.specialist_role || response.primary_type) {
      setDynamicSpecialistInfo({
        role: response.specialist_role,
        domain: response.primary_type
      });
    }

    // 构建确认卡片内容
    const confirmId = `confirm-${Date.now()}`;
    const confirmationMessage: Message = {
      id: confirmId,
      content: `初步分析完成。您的问题属于【${response.primary_type}】领域。\n\n建议转交专业律师进行深度分析。`,
      role: 'assistant',
      timestamp: new Date(),
      isConfirmation: true,
      suggestedQuestions: response.suggested_questions || [],
      directQuestions: response.direct_questions || [],
      onConfirm: async () => {
        // 用户点击确认
        const selected = selectedSuggestedQuestions[confirmId] || [];
        const custom = customQuestions[confirmId];
        const allQuestions = [...selected, ...(custom ? [custom] : [])];

        // 【调试增强】详细的调试日志
        console.log('[DEBUG Frontend] ===== 用户确认时的调试信息 =====');
        console.log('[DEBUG Frontend] confirmId:', confirmId);
        console.log('[DEBUG Frontend] selectedSuggestedQuestions:', selectedSuggestedQuestions);
        console.log('[DEBUG Frontend] selected (用户选择的补充问题):', selected);
        console.log('[DEBUG Frontend] custom (用户自定义问题):', custom);
        console.log('[DEBUG Frontend] allQuestions (最终问题列表):', allQuestions);
        console.log('[DEBUG Frontend] allQuestions.length:', allQuestions.length);
        console.log('[DEBUG Frontend] lastUserQuestionRef.current:', lastUserQuestionRef.current);
        console.log('[DEBUG Frontend] response.direct_questions:', response.direct_questions);
        console.log('[DEBUG Frontend] response.suggested_questions:', response.suggested_questions);
        console.log('[DEBUG Frontend] 将发送的 selected_suggested_questions:', allQuestions.length > 0 ? allQuestions : undefined);
        console.log('[DEBUG Frontend] ===== 调试信息结束 =====');

        // 添加"正在转交"提示
        const loadingId = `proc-${Date.now()}`;
        setMessages(prev => [...prev, {
          id: loadingId,
          content: `已转交【${response.primary_type}】专家律师，正在进行深度思考与分析...`,
          role: 'assistant_specialist',
          timestamp: new Date()
        }]);
        setCurrentExpertType('specialist');

        try {
          const secondResponse = await consultLaw({
            // 【关键修复】使用用户原始问题，而非占位符
            question: lastUserQuestionRef.current,
            user_confirmed: true,
            selected_suggested_questions: allQuestions.length > 0 ? allQuestions : undefined,
            session_id: sessionStorage.getItem('consultation_session_id')
          });

          // 移除 loading 消息，添加结果
          setMessages(prev => {
            const filtered = prev.filter(m => m.id !== loadingId);
            return [...filtered, {
              id: `specialist-${Date.now()}`,
              content: secondResponse.response || secondResponse.answer,
              role: 'assistant_specialist',
              timestamp: new Date(),
              suggestions: secondResponse.suggestions,
              actionButtons: secondResponse.action_buttons
            }];
          });
        } catch (e) {
          message.error('专业分析请求失败');
          setMessages(prev => prev.filter(m => m.id !== loadingId));
        }
      },
      onReject: () => {
        setMessages(prev => [...prev, {
          id: `sys-${Date.now()}`,
          content: '已取消转交。您可以继续向我提问，或重新描述问题。',
          role: 'assistant',
          timestamp: new Date()
        }]);
      }
    };
    setMessages(prev => [...prev, confirmationMessage]);
  };

  // 文件上传
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    const file = e.target.files[0];
    if (file.size > 50 * 1024 * 1024) {
      message.error('文件大小不能超过 50MB');
      return;
    }

    const tempId = `temp-${Date.now()}`;
    setUploadedFiles(prev => [...prev, {
      file_id: tempId, filename: file.name, file_type: file.name.split('.').pop() || '', 
      content_preview: '', status: 'uploading'
    }]);
    setIsUploading(true);

    try {
      const res = await uploadConsultationFile(file);
      setUploadedFiles(prev => prev.map(f => f.file_id === tempId ? {
        ...f, file_id: res.file_id, status: 'done', content_preview: res.content_preview
      } : f));
      message.success('上传成功');
    } catch (e) {
      message.error('上传失败');
      setUploadedFiles(prev => prev.filter(f => f.file_id !== tempId));
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // ================= 渲染辅助函数 =================

  const getFileIcon = (type: string) => {
    const t = type.toLowerCase();
    if (t.includes('pdf')) return <FileTextOutlined style={{ color: '#ff4d4f' }} />;
    if (t.includes('doc')) return <FileTextOutlined style={{ color: '#1890ff' }} />;
    return <FileOutlined />;
  };

  // ================= 页面渲染 =================

  return (
    <Layout className="legal-consultation-layout" style={{ height: '100vh', background: '#f0f2f5' }}>
      <EnhancedModuleNavBar
        currentModuleKey="consultation"
        title="智能咨询"
        icon={<BankOutlined />}
        showQuickNav={false}
        extra={
          <Button 
            type="text" 
            icon={<HistoryOutlined />} 
            onClick={toggleHistorySidebar}
          >
            历史记录
          </Button>
        }
      />

      <Layout style={{ overflow: 'hidden' }}>
        {/* 历史记录侧边栏 */}
        <ConsultationHistorySidebar
          visible={isHistorySidebarOpen}
          onClose={() => toggleHistorySidebar()}
          onLoadHistory={handleLoadHistory}
          onNewChat={handleNewChat}
        />

        {/* 主聊天区域 */}
        <Content style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 0 }}>
          {/* 消息流区域 */}
          <div className="messages-container" style={{ flex: 1, overflowY: 'auto', padding: '20px 10%' }}>
            {messages.map((msg) => (
              <div key={msg.id} className={`message-row ${msg.role === 'user' ? 'user-row' : 'bot-row'}`}>
                <div className="message-avatar">
                  <Avatar 
                    icon={msg.role === 'user' ? <UserOutlined /> : (msg.role === 'assistant_specialist' ? <CrownOutlined /> : <RobotOutlined />)} 
                    style={{ backgroundColor: msg.role === 'user' ? '#1890ff' : (msg.role === 'assistant_specialist' ? '#722ed1' : '#52c41a') }}
                  />
                </div>
                
                <div className="message-bubble-container">
                  {/* 发言人名字 */}
                  {msg.role !== 'user' && (
                    <div className="message-sender-name">
                      {msg.role === 'assistant_specialist' ? '专业律师' : '律师助理'}
                      {msg.confidence && <Tag color="green" style={{ marginLeft: 8, fontSize: 10 }}>置信度 {Math.round(msg.confidence * 100)}%</Tag>}
                    </div>
                  )}

                  {/* 消息气泡 */}
                  <div className={`message-bubble ${msg.role}`}>
                    {msg.isConfirmation ? (
                      // 确认卡片 UI
                      <div className="confirmation-card">
                        <Text strong style={{ fontSize: 16 }}>🔎 初步诊断完成</Text>
                        <Paragraph style={{ margin: '12px 0' }}>{msg.content.split('\n\n')[0]}</Paragraph>
                        
                        {msg.suggestedQuestions && msg.suggestedQuestions.length > 0 && (
                          <div className="suggestion-selection">
                            <Divider plain style={{ margin: '12px 0' }}>您可以勾选补充问题</Divider>
                            <Space direction="vertical" style={{ width: '100%' }}>
                              {msg.suggestedQuestions.map((q, idx) => (
                                <Checkbox 
                                  key={idx}
                                  onChange={(e) => {
                                    const current = selectedSuggestedQuestions[msg.id] || [];
                                    const next = e.target.checked ? [...current, q] : current.filter(x => x !== q);
                                    setSelectedSuggestedQuestions(prev => ({...prev, [msg.id]: next}));
                                  }}
                                >
                                  {q}
                                </Checkbox>
                              ))}
                              <Checkbox
                                onChange={(e) => {
                                  if (!e.target.checked) {
                                    const newCustom = {...customQuestions};
                                    delete newCustom[msg.id];
                                    setCustomQuestions(newCustom);
                                  } else {
                                    setCustomQuestions(prev => ({...prev, [msg.id]: ''}));
                                  }
                                }}
                              >
                                其他问题
                              </Checkbox>
                              {customQuestions[msg.id] !== undefined && (
                                <Input 
                                  placeholder="请输入您的具体问题" 
                                  value={customQuestions[msg.id]}
                                  onChange={(e) => setCustomQuestions(prev => ({...prev, [msg.id]: e.target.value}))}
                                  style={{ marginLeft: 24, width: '90%' }}
                                />
                              )}
                            </Space>
                          </div>
                        )}

                        <div className="confirmation-actions" style={{ marginTop: 16, display: 'flex', gap: 12 }}>
                          <Button 
                            type="primary" 
                            icon={<CheckCircleOutlined />} 
                            onClick={() => msg.onConfirm && msg.onConfirm()}
                          >
                            转交专家律师
                          </Button>
                          <Button onClick={msg.onReject}>取消</Button>
                        </div>
                      </div>
                    ) : (
                      // 普通 Markdown 消息
                      <div className="markdown-body">
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            h1: ({...props}) => <Title level={3 as const} {...props} />,
                            h2: ({...props}) => <Title level={4 as const} {...props} />,
                            h3: ({...props}) => <Title level={5 as const} {...props} />,
                            li: ({...props}) => <li style={{ marginLeft: 20 }} {...props} />
                          }}
                        >
                          {msg.content}
                        </ReactMarkdown>
                      </div>
                    )}
                  </div>

                  {/* 消息底部操作区（建议/按钮） */}
                  {msg.actionButtons && (
                    <div className="message-footer-actions">
                      <Space wrap size={[8, 8]}>
                        {msg.actionButtons.map(btn => (
                          <Button 
                            key={btn.id} 
                            size="small" 
                            type="dashed" 
                            onClick={() => btn.route ? navigate(btn.route) : message.info('功能开发中')}
                          >
                            {btn.title}
                          </Button>
                        ))}
                      </Space>
                    </div>
                  )}
                </div>
              </div>
            ))}
            
            {isTyping && (
              <div className="message-row bot-row">
                <Avatar icon={<RobotOutlined />} style={{ backgroundColor: '#ccc' }} />
                <div className="message-bubble assistant typing">
                  <span>●</span><span>●</span><span>●</span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* 底部输入区域 */}
          <div className="input-area-wrapper" style={{ padding: '16px 10%', background: '#fff', borderTop: '1px solid #e8e8e8' }}>
            {/* 上传文件预览 */}
            {uploadedFiles.length > 0 && (
              <div className="upload-preview-bar">
                <Space>
                  {uploadedFiles.map(f => (
                    <Tag 
                      key={f.file_id} 
                      closable 
                      onClose={() => deleteConsultationFile(f.file_id).then(() => setUploadedFiles(prev => prev.filter(x => x.file_id !== f.file_id)))}
                      icon={getFileIcon(f.file_type)}
                      color={f.status === 'error' ? 'red' : 'blue'}
                    >
                      {f.filename} {f.status === 'uploading' && '(上传中)'}
                    </Tag>
                  ))}
                </Space>
              </div>
            )}

            <div className="input-box-container" style={{ display: 'flex', gap: 12 }}>
              <div style={{ flex: 1, position: 'relative' }}>
                <TextArea
                  value={inputValue}
                  onChange={e => setInputValue(e.target.value)}
                  onKeyPress={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } }}
                  placeholder="请输入您的法律问题，或上传合同/文书..."
                  autoSize={{ minRows: 2, maxRows: 6 }}
                  style={{ borderRadius: 8, paddingRight: 40 }}
                />
                <Tooltip title="上传文件 (PDF/Word)">
                  <Button 
                    type="text" 
                    icon={<PaperClipOutlined />} 
                    style={{ position: 'absolute', right: 8, bottom: 8, color: '#666' }}
                    onClick={() => fileInputRef.current?.click()}
                  />
                </Tooltip>
                <input ref={fileInputRef} type="file" style={{ display: 'none' }} onChange={handleFileSelect} accept=".pdf,.doc,.docx,.txt" />
              </div>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <Button type="primary" icon={<SendOutlined />} onClick={() => handleSendMessage()} loading={isTyping} style={{ height: '100%' }}>
                  发送
                </Button>
                {currentSessionId && (
                  <Tooltip title="结束当前对话，开启新话题">
                    <Button icon={<ClearOutlined />} size="small" onClick={handleNewChat} />
                  </Tooltip>
                )}
              </div>
            </div>
            <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block', textAlign: 'center' }}>
              AI 建议仅供参考，重大法律事务请咨询线下律师。
            </Text>
          </div>
        </Content>

        {/* 右侧辅助面板 */}
        <Sider width={280} theme="light" style={{ borderLeft: '1px solid #f0f0f0', padding: 16 }}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            
            {/* 当前专家卡片 */}
            <Card size="small" bordered={false} className="expert-card-right">
              <div style={{ textAlign: 'center' }}>
                <Avatar size={64} src={currentExpertProfile.avatar} icon={<UserOutlined />} style={{ marginBottom: 12, backgroundColor: currentExpertType === 'assistant' ? '#52c41a' : '#722ed1' }} />
                <Title level={5} style={{ margin: 0 }}>
                  {currentExpertType === 'specialist' && dynamicSpecialistInfo.role
                    ? dynamicSpecialistInfo.role
                    : currentExpertProfile.name}
                </Title>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {currentExpertType === 'specialist' && dynamicSpecialistInfo.domain
                    ? `专业领域：${dynamicSpecialistInfo.domain}`
                    : currentExpertProfile.title}
                </Text>

                <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-around', background: '#f9f9f9', padding: 8, borderRadius: 4 }}>
                  <div><div style={{ fontWeight: 'bold' }}>{currentExpertProfile.cases}</div><div style={{ fontSize: 10, color: '#999' }}>服务案例</div></div>
                  <div><div style={{ fontWeight: 'bold' }}>{currentExpertProfile.success_rate}</div><div style={{ fontSize: 10, color: '#999' }}>好评率</div></div>
                </div>
              </div>
            </Card>

            {/* 知识库开关 */}
            <ModuleKnowledgeToggle moduleName="consultation" moduleLabel="智能咨询" />

            {/* 快捷工具 - 更新版 */}
            <div className="quick-tools">
              <Divider orientation="left" style={{ margin: '12px 0' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>快捷工具</Text>
              </Divider>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {/* 第一排：核心分析 */}
                <Button block size="small" icon={<SafetyOutlined />} onClick={() => navigate('/risk-analysis')}>风险评估</Button>
                <Button block size="small" icon={<BankOutlined />} onClick={() => navigate('/litigation-analysis')}>案件分析</Button>
                
                {/* 第二排：合同业务 */}
                <Button block size="small" icon={<FileProtectOutlined />} onClick={() => navigate('/contract/generate')}>合同生成</Button>
                <Button block size="small" icon={<DiffOutlined />} onClick={() => navigate('/contract/review')}>合同审查</Button>
                
                {/* 第三排：查询与处理 (新增) */}
                <Button block size="small" icon={<AppstoreOutlined />} onClick={() => navigate('/contract')}>模板查询</Button>
                <Button block size="small" icon={<EditOutlined />} onClick={() => navigate('/document-processing')}>文档处理</Button>
                
                {/* 第四排：工具箱 (新增) */}
                <Button block size="small" icon={<FileTextOutlined />} onClick={() => navigate('/document-drafting')}>文书起草</Button>
                <Button block size="small" icon={<CalculatorOutlined />} onClick={() => navigate('/cost-calculation')}>费用测算</Button>
              </div>
            </div>

          </Space>
        </Sider>
      </Layout>
    </Layout>
  );
};

export default LegalConsultationPage;
