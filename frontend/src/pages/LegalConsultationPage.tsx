// frontend/src/pages/LegalConsultationPage.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Button, Input, Layout, message, Typography, Card, Space, Avatar, Divider, Tag, Checkbox, Tooltip, List } from 'antd';
import { 
  SendOutlined, UserOutlined, CrownOutlined, BankOutlined, 
  CheckCircleOutlined, PaperClipOutlined, 
  AppstoreOutlined, SafetyOutlined, 
  FileProtectOutlined, DiffOutlined, EditOutlined, FileTextOutlined, CalculatorOutlined,
  HistoryOutlined, RobotOutlined, ClearOutlined, FileOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api, { uploadConsultationFile, deleteConsultationFile, consultLaw, resetConsultationSession } from '../api';
import type { UploadFile } from 'antd/es/upload/interface';
import EnhancedModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
import ModuleKnowledgeToggle from '../components/ModuleKnowledgeToggle';
import ConsultationHistorySidebar from '../components/ConsultationHistorySidebar';
import { useConsultationSession } from '../hooks/useConsultationSession';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './LegalConsultationPage.css';

const { Content, Sider } = Layout;
const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

// ================= 类型定义 =================

export interface ActionButton {
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

export interface UploadedFile {
  file_id: string;
  filename: string;
  file_type: string;
  content_preview: string;
  status: 'uploading' | 'done' | 'error';
}

export interface Message {
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
  // 【新增】专家信息字段
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
  specialist_role?: string;
  primary_type?: string;
  // 【关键】专家分析相关字段 - 用于前端渲染
  analysis?: string;
  advice?: string;
  actionSteps?: string[];
  riskWarning?: string;
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
    isHistorySidebarOpen,
    createNewSession,
    continueSession,
    saveCurrentSession,
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

  // 用于轮询异步任务的定时器ID
  const pollingTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // 保存用户最后一次输入的问题（用于第二阶段调用）
  const lastUserQuestionRef = useRef<string>('');
  // 【修复闭包陷阱】使用 Ref 穿透闭包，始终获取最新的问题选择状态
  const selectedQuestionsRef = useRef<Record<string, string[]>>({});
  const customQuestionsRef = useRef<Record<string, string>>({});
  // 【修复闭包陷阱】使用 Ref 穿透闭包，始终获取最新的上传文件状态
  const uploadedFilesRef = useRef<UploadedFile[]>([]);

  // ================= 副作用处理 =================

  // 清理定时器
  useEffect(() => {
    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
      }
    };
  }, []);

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
      setTimeout(() => handleSendMessage(state.initial_input), 500);
      message.success('已自动带入您的咨询需求');
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

  // 同步 Refs
  useEffect(() => {
    selectedQuestionsRef.current = selectedSuggestedQuestions;
  }, [selectedSuggestedQuestions]);
  useEffect(() => {
    customQuestionsRef.current = customQuestions;
  }, [customQuestions]);
  useEffect(() => {
    uploadedFilesRef.current = uploadedFiles;
  }, [uploadedFiles]);

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
    if (messages.length > 1) { 
      await saveCurrentSession(messages);
    }
    setMessages([]); 
    setConsultationStarted(false);
    setCurrentExpertType('assistant');
    setUploadedFiles([]);
    setSelectedSuggestedQuestions({});
    setCustomQuestions({});
    setConsultationSession(null);
    setDynamicSpecialistInfo({}); 
    sessionStorage.removeItem('consultation_session_id');
    setCurrentSessionId(null);

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
    
    sessionStorage.setItem('consultation_session_id', sessionId);
    setCurrentSessionId(sessionId);
    
    message.success('历史记录已加载');
  };

  // 轮询获取任务状态 - 【本次修复核心】
  const pollTaskStatus = async (sessionId: string, options?: { excludeConfirmationId?: string; skipInitialMessage?: boolean }) => {
    const { excludeConfirmationId, skipInitialMessage = false } = options || {};

    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
    }

    // 【修复】如果已经在轮询中，避免重复轮询
    if (isTyping) {
      console.log('[DEBUG] 已在处理中，跳过重复轮询');
      return;
    }

    setIsTyping(true);

    // 【修复】只有在不跳过初始消息时才添加"正在处理"消息
    if (!skipInitialMessage) {
      const processingMessage: Message = {
        id: `processing-${Date.now()}`,
        content: '正在处理您的咨询请求，请稍候...',
        role: 'assistant',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, processingMessage]);
    }

    pollingTimerRef.current = setInterval(async () => {
      try {
        const response = await api.get(`/consultation/task-status/${sessionId}`);

        if (response.data.status === 'completed' || response.data.status === 'waiting_confirmation') {
          if (pollingTimerRef.current) {
            clearInterval(pollingTimerRef.current);
            pollingTimerRef.current = null;
          }

          setIsTyping(false);
          // 移除处理中消息
          setMessages(prev => prev.filter(m => !m.content.includes('正在处理您的咨询请求')));

          if (response.data.status === 'waiting_confirmation') {
            // 【修复】检查是否已存在确认卡片（排除正在被处理的确认卡片）
            setMessages(prev => {
              const hasExistingConfirmation = prev.some(m =>
                m.isConfirmation &&
                m.id !== excludeConfirmationId
              );
              if (hasExistingConfirmation) {
                console.log('[DEBUG] 已存在确认卡片，跳过重复创建');
                return prev;
              }
              return prev;
            });

            // 【修复】移除旧的确认卡片（如果有）
            setMessages(prev => prev.filter(m => !m.isConfirmation || m.id === excludeConfirmationId));

            // 【修复】提前捕获数据到常量，避免闭包陷阱
            const primaryType = response.data.primary_type || '未知';
            const specialistRole = response.data.specialist_role;
            const personaDefinition = response.data.persona_definition;
            const strategicFocus = response.data.strategic_focus;
            const suggestedQuestions = response.data.suggested_questions || [];
            const directQuestions = response.data.direct_questions || [];

            // 【修复】先定义 confirmId，避免闭包陷阱
            const confirmId = `confirm-${Date.now()}`;
            console.log('[DEBUG] 创建确认卡片, confirmId:', confirmId, 'primaryType:', primaryType);

            const confirmationMessage: Message = {
              id: confirmId,
              content: `初步分析完成。您的问题属于【${primaryType}】领域。\n\n建议转交专业律师进行深度分析。`,
              role: 'assistant',
              timestamp: new Date(),
              isConfirmation: true,
              suggestedQuestions: suggestedQuestions,
              directQuestions: directQuestions,
              persona_definition: personaDefinition,
              strategic_focus: strategicFocus,
              specialist_role: specialistRole,
              primary_type: primaryType,
              onConfirm: async () => {
                console.log('[DEBUG] onConfirm 被调用, confirmId:', confirmId, 'primaryType:', primaryType);

                // 【修复】使用 uploadedFilesRef.current 避免闭包陷阱
                const uploadedFileIds = uploadedFilesRef.current.filter(f => f.status === 'done').map(f => f.file_id);
                const selected = selectedQuestionsRef.current[confirmId] || [];
                const custom = customQuestionsRef.current[confirmId];
                const allQuestions = [...selected, ...(custom ? [custom] : [])];

                const loadingId = `proc-${Date.now()}`;
                console.log('[DEBUG] 移除确认卡片, 添加 loading 消息, loadingId:', loadingId);

                // 【修复】使用捕获的常量 primaryType 而不是 response.data.primary_type
                setMessages(prev => [...prev.filter(m => m.id !== confirmId), {
                  id: loadingId,
                  content: `已转交【${primaryType}】专家律师，正在进行深度思考与分析...`,
                  role: 'assistant_specialist',
                  timestamp: new Date()
                }]);
                setCurrentExpertType('specialist');

                try {
                  console.log('[DEBUG] 调用 consultLaw API, session_id:', sessionId);
                  const secondResponse = await consultLaw({
                    question: lastUserQuestionRef.current,
                    user_confirmed: true,
                    selected_suggested_questions: allQuestions.length > 0 ? allQuestions : undefined,
                    uploaded_files: uploadedFileIds.length > 0 ? uploadedFileIds : undefined,
                    session_id: sessionId
                  });

                  console.log('[DEBUG] consultLaw 响应:', secondResponse.ui_action);

                  if (secondResponse.ui_action === 'async_processing') {
                    // 【修复】传递对象参数，跳过初始消息并排除确认卡片ID
                    pollTaskStatus(sessionId, { excludeConfirmationId: confirmId, skipInitialMessage: true });
                  } else {
                    // 如果直接返回结果
                     handleNormalResponse(secondResponse);
                  }

                  // 移除 loading 消息
                  setMessages(prev => prev.filter(m => m.id !== loadingId));

                } catch (e) {
                  console.error('[DEBUG] consultLaw 请求失败:', e);
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
          } 
          else if (response.data.result) {
            // 处理完成状态 (专家节点完成)
            const result = response.data.result;
            console.log('[DEBUG] Task Result (Raw):', result); 
            
            // 1. 尝试从 specialist_output 对象中提取数据
            // 2. 如果 specialist_output 为空，尝试从 result 顶层提取 (兼容性)
            let specialistData = result.specialist_output || {};
            if (!specialistData.analysis && !specialistData.advice) {
                console.log('[DEBUG] specialist_output empty, falling back to top-level');
                specialistData = result;
            }

            // 3. 提取核心字段 (处理下划线 vs 驼峰)
            const analysis = specialistData.analysis;
            const advice = specialistData.advice;
            // 处理 action_steps: 可能是 action_steps (Python) 或 actionSteps (JS)
            const actionSteps = specialistData.action_steps || specialistData.actionSteps || [];
            const riskWarning = specialistData.risk_warning || specialistData.riskWarning || '';
            
            // 4. 判断是否有专家内容
            const hasSpecialistContent = !!(analysis || advice || (actionSteps && actionSteps.length > 0) || riskWarning);
            
            console.log('[DEBUG] Extracted Fields:', { analysis, advice, actionSteps, riskWarning, hasSpecialistContent });

            const assistantMessage: Message = {
              id: `assistant-${Date.now()}`,
              // 如果有结构化字段，content 仅作为后备；否则显示普通回答
              content: hasSpecialistContent 
                ? (analysis || result.response || result.answer || '分析完成') 
                : (result.response || result.answer || '暂无内容'),
              role: result.final_report || hasSpecialistContent ? 'assistant_specialist' : 'assistant',
              timestamp: new Date(),
              suggestions: result.suggestions,
              actionButtons: result.action_buttons?.map((btn: any) => ({
                id: btn.key,
                title: btn.label,
                action: btn.key,
                route: btn.key === 'risk_analysis' ? '/risk-analysis' : undefined 
              })),
              // 【关键】映射提取到的字段到消息对象
              analysis: analysis,
              advice: advice,
              actionSteps: actionSteps,
              riskWarning: riskWarning,
              confidence: result.confidence
            };
            
            setMessages(prev => [...prev, assistantMessage]);
            
            // 更新会话状态为专家模式
            if (result.final_report || hasSpecialistContent) {
              setConsultationSession(prev => ({
                sessionId: result.session_id || sessionId,
                specialistOutput: result,
                isInSpecialistMode: true
              }));
            }
          }
        } else if (response.data.status === 'failed') {
          if (pollingTimerRef.current) {
            clearInterval(pollingTimerRef.current);
            pollingTimerRef.current = null;
          }
          setMessages(prev => prev.filter(m => !m.content.includes('正在处理您的咨询请求')));
          setMessages(prev => [...prev, {
            id: `error-${Date.now()}`,
            content: '咨询处理失败，请稍后重试',
            role: 'assistant',
            timestamp: new Date()
          }]);
        }
      } catch (error) {
        console.error('轮询任务状态失败:', error);
        if (pollingTimerRef.current) {
          clearInterval(pollingTimerRef.current);
          pollingTimerRef.current = null;
        }
      }
    }, 2000); 
  };
// 发送消息核心逻辑
  const handleSendMessage = async (manualInput?: string) => {
    const contentToSend = manualInput || inputValue;
    if (!contentToSend.trim() && uploadedFiles.length === 0) return;

    lastUserQuestionRef.current = contentToSend;

    if (!consultationStarted) setConsultationStarted(true);

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
      // 【修复】只有在没有当前会话时才重置会话
      // 如果存在 currentSessionId，说明会话仍在进行中（包括专家模式），不应该重置
      const isFirstMessageOfNewChat = !sessionIdFromStorage && messages.length <= 1;

      const requestParams: any = {
        question: contentToSend || '请分析我上传的文件',
        uploaded_files: uploadedFileIds.length > 0 ? uploadedFileIds : undefined,
        session_id: sessionIdFromStorage || null,
        reset_session: isFirstMessageOfNewChat
      };

      const response = await consultLaw(requestParams);

      if (response.session_id) {
        sessionStorage.setItem('consultation_session_id', response.session_id);
        setCurrentSessionId(response.session_id);
      }

      setUploadedFiles([]); 

      if (response.ui_action === 'async_processing') {
        await pollTaskStatus(response.session_id, {});
      } else if (response.need_confirmation) {
        handleConfirmationResponse(response, uploadedFileIds);
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

  // 处理普通响应 (同步返回)
  const handleNormalResponse = (response: any) => {
    // 同样应用数据提取逻辑，以防同步返回也包含专家结构
    let specialistData = response.specialist_output || {};
    if (!specialistData.analysis && !specialistData.advice) {
        specialistData = response; 
    }
    const analysis = specialistData.analysis;
    const advice = specialistData.advice;
    const actionSteps = specialistData.action_steps || specialistData.actionSteps || [];
    const riskWarning = specialistData.risk_warning || specialistData.riskWarning || '';
    const hasSpecialistContent = !!(analysis || advice || (actionSteps && actionSteps.length > 0) || riskWarning);

    const assistantMessage: Message = {
      id: `assistant-${Date.now()}`,
      content: hasSpecialistContent 
        ? (analysis || response.response || response.answer || '分析完成') 
        : (response.response || response.answer),
      role: response.final_report || hasSpecialistContent ? 'assistant_specialist' : 'assistant',
      timestamp: new Date(),
      suggestions: response.suggestions,
      actionButtons: response.action_buttons?.map((btn: any) => ({
        id: btn.key,
        title: btn.label,
        action: btn.key,
        route: btn.key === 'risk_analysis' ? '/risk-analysis' : undefined 
      })),
      confidence: response.confidence,
      // 映射字段
      analysis: analysis,
      advice: advice,
      actionSteps: actionSteps,
      riskWarning: riskWarning
    };
    setMessages(prev => [...prev, assistantMessage]);
    
    if (response.final_report || hasSpecialistContent) {
      setConsultationSession(prev => ({
        sessionId: response.session_id,
        specialistOutput: response,
        isInSpecialistMode: true
      }));
    }
  };

  // 处理需要确认的响应
  const handleConfirmationResponse = (response: any, fileIds: string[] = []) => {
    if (response.specialist_role || response.primary_type) {
      setDynamicSpecialistInfo({
        role: response.specialist_role,
        domain: response.primary_type
      });
    }

    // 【修复】提前捕获数据到常量，避免闭包陷阱
    const primaryType = response.primary_type || '未知';
    const suggestedQuestions = response.suggested_questions || [];
    const directQuestions = response.direct_questions || [];

    const confirmId = `confirm-${Date.now()}`;
    console.log('[DEBUG] handleConfirmationResponse 创建确认卡片, confirmId:', confirmId, 'primaryType:', primaryType);

    const confirmationMessage: Message = {
      id: confirmId,
      content: `初步分析完成。您的问题属于【${primaryType}】领域。\n\n建议转交专业律师进行深度分析。`,
      role: 'assistant',
      timestamp: new Date(),
      isConfirmation: true,
      suggestedQuestions: suggestedQuestions,
      directQuestions: directQuestions,
      onConfirm: async () => {
        console.log('[DEBUG] handle onConfirm 被调用, confirmId:', confirmId, 'primaryType:', primaryType);

        const uploadedFileIds = fileIds;
        const selected = selectedQuestionsRef.current[confirmId] || [];
        const custom = customQuestionsRef.current[confirmId];
        const allQuestions = [...selected, ...(custom ? [custom] : [])];

        const loadingId = `proc-${Date.now()}`;
        console.log('[DEBUG] 移除确认卡片, 添加 loading 消息, loadingId:', loadingId);

        // 【修复】使用捕获的常量 primaryType 而不是 response.primary_type
        setMessages(prev => [...prev.filter(m => m.id !== confirmId), {
          id: loadingId,
          content: `已转交【${primaryType}】专家律师，正在进行深度思考与分析...`,
          role: 'assistant_specialist',
          timestamp: new Date()
        }]);
        setCurrentExpertType('specialist');

        try {
          const sessionId = sessionStorage.getItem('consultation_session_id');
          console.log('[DEBUG] 调用 consultLaw API, session_id:', sessionId);
          const secondResponse = await consultLaw({
            question: lastUserQuestionRef.current,
            user_confirmed: true,
            selected_suggested_questions: allQuestions.length > 0 ? allQuestions : undefined,
            uploaded_files: uploadedFileIds.length > 0 ? uploadedFileIds : undefined,
            session_id: sessionId
          });

          console.log('[DEBUG] consultLaw 响应:', secondResponse.ui_action);

          // 如果是异步处理
          if (secondResponse.ui_action === 'async_processing') {
             // 【修复】传递对象参数，跳过初始消息并排除确认卡片ID
             pollTaskStatus(secondResponse.session_id, { excludeConfirmationId: confirmId, skipInitialMessage: true });
             setMessages(prev => prev.filter(m => m.id !== loadingId)); // 移除"转交中"，pollTaskStatus会添加"处理中"
          } else {
             // 同步返回
             handleNormalResponse(secondResponse);
             setMessages(prev => prev.filter(m => m.id !== loadingId));
          }
        } catch (e) {
          console.error('[DEBUG] consultLaw 请求失败:', e);
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
        <ConsultationHistorySidebar
          visible={isHistorySidebarOpen}
          onClose={() => toggleHistorySidebar()}
          onLoadHistory={handleLoadHistory}
          onNewChat={handleNewChat}
        />

        <Content style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: 0 }}>
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
                  {msg.role !== 'user' && (
                    <div className="message-sender-name">
                      {msg.role === 'assistant_specialist' ? '专业律师' : '律师助理'}
                      {msg.confidence && <Tag color="green" style={{ marginLeft: 8, fontSize: 10 }}>置信度 {Math.round(msg.confidence * 100)}%</Tag>}
                    </div>
                  )}

                  <div className={`message-bubble ${msg.role}`}>
                    {msg.isConfirmation ? (
                      <div className="confirmation-card">
                        <Text strong style={{ fontSize: 16 }}>🔎 初步诊断完成</Text>
                        <Paragraph style={{ margin: '12px 0' }}>
                          您的问题属于【{msg.primary_type || '未知'}】领域
                          {msg.specialist_role && `，建议由【${msg.specialist_role}】处理`}
                        </Paragraph>

                        {msg.persona_definition && (
                          <Card size="small" style={{ margin: '12px 0', background: '#f0f5ff' }}>
                            <Text strong>👨‍⚖️ 专家律师</Text>
                            <Paragraph style={{ margin: '8px 0' }}>
                              <Text>{msg.persona_definition.professional_background}</Text>
                            </Paragraph>
                            <div style={{ marginTop: 8 }}>
                              <Text type="secondary">执业年限：{msg.persona_definition.years_of_experience}</Text>
                            </div>
                            {msg.persona_definition.expertise_area && (
                              <div style={{ marginTop: 8 }}>
                                <Text strong>专业领域：</Text>
                                <Tag color="blue">{msg.persona_definition.expertise_area}</Tag>
                              </div>
                            )}
                          </Card>
                        )}

                        {msg.strategic_focus && (
                          <Card size="small" style={{ margin: '12px 0', background: '#fff7e6' }}>
                            <Text strong>🎯 分析策略</Text>
                            <Paragraph style={{ margin: '8px 0' }}>
                              <Text>分析角度：{msg.strategic_focus.analysis_angle}</Text>
                            </Paragraph>
                            {msg.strategic_focus.key_points && msg.strategic_focus.key_points.length > 0 && (
                              <div style={{ marginTop: 8 }}>
                                <Text strong>关键关注点：</Text>
                                <ul style={{ marginTop: 4, paddingLeft: 16 }}>
                                  {msg.strategic_focus.key_points.map((point, idx) => (
                                    <li key={idx}>{point}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {msg.strategic_focus.risk_alerts && msg.strategic_focus.risk_alerts.length > 0 && (
                              <div style={{ marginTop: 8 }}>
                                <Text strong style={{ color: '#ff4d4f' }}>⚠️ 风险提示：</Text>
                                <ul style={{ marginTop: 4, paddingLeft: 16 }}>
                                  {msg.strategic_focus.risk_alerts.map((alert, idx) => (
                                    <li key={idx} style={{ color: '#ff4d4f' }}>{alert}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </Card>
                        )}

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
                      // 普通 Markdown 或 专家分析结构化展示
                      <div className="message-bubble">
                        {msg.role === 'assistant_specialist' && (msg.analysis || msg.advice || msg.riskWarning || (msg.actionSteps && msg.actionSteps.length > 0)) ? (
                          <div>
                            {msg.analysis && (
                              <div style={{ marginBottom: 16 }}>
                                <h3>📋 问题解答</h3>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.analysis}</ReactMarkdown>
                              </div>
                            )}
                            
                            {msg.advice && (
                              <div style={{ marginBottom: 16 }}>
                                <h3>💡 专业建议</h3>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.advice}</ReactMarkdown>
                              </div>
                            )}
                            
                            {msg.actionSteps && msg.actionSteps.length > 0 && (
                              <div style={{ marginBottom: 16 }}>
                                <h3>✅ 行动步骤</h3>
                                <List
                                  size="small"
                                  dataSource={msg.actionSteps}
                                  renderItem={(item, index) => (
                                    <List.Item key={index}>
                                      <Text>{item}</Text>
                                    </List.Item>
                                  )}
                                />
                              </div>
                            )}
                            
                            {msg.riskWarning && (
                              <div style={{ marginBottom: 16 }}>
                                <h3>⚠️ 风险提示</h3>
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.riskWarning}</ReactMarkdown>
                              </div>
                            )}
                          </div>
                        ) : (
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                        )}
                      </div>
                    )}
                  </div>

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

          <div className="input-area-wrapper" style={{ padding: '16px 10%', background: '#fff', borderTop: '1px solid #e8e8e8' }}>
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
                    <Button
                      type="primary"
                      danger
                      size="small"
                      icon={<ClearOutlined />}
                      onClick={handleNewChat}
                      style={{ fontWeight: 'bold' }}
                    >
                      开启新对话
                    </Button>
                  </Tooltip>
                )}
              </div>
            </div>
            <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block', textAlign: 'center' }}>
              AI 建议仅供参考，重大法律事务请咨询线下律师。
            </Text>
          </div>
        </Content>

        <Sider width={280} theme="light" style={{ borderLeft: '1px solid #f0f0f0', padding: 16 }}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
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

            <ModuleKnowledgeToggle moduleName="consultation" moduleLabel="智能咨询" />

            <div className="quick-tools">
              <Divider orientation="left" style={{ margin: '12px 0' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>快捷工具</Text>
              </Divider>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                <Button block size="small" icon={<SafetyOutlined />} onClick={() => navigate('/risk-analysis')}>风险评估</Button>
                <Button block size="small" icon={<BankOutlined />} onClick={() => navigate('/litigation-analysis')}>案件分析</Button>
                <Button block size="small" icon={<FileProtectOutlined />} onClick={() => navigate('/contract/generate')}>合同生成</Button>
                <Button block size="small" icon={<DiffOutlined />} onClick={() => navigate('/contract/review')}>合同审查</Button>
                <Button block size="small" icon={<AppstoreOutlined />} onClick={() => navigate('/contract')}>模板查询</Button>
                <Button block size="small" icon={<EditOutlined />} onClick={() => navigate('/document-processing')}>文档处理</Button>
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