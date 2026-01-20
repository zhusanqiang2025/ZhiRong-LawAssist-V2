// frontend/src/pages/LitigationAnalysisPage.tsx
/**
 * 案件分析页面 (重构版)
 *
 * 核心升级：
 * 1. 集成 EnhancedAnalysisDisplay 组件，展示案件全景、主体画像、时间线。
 * 2. 适配后端 Unified Preorganization 接口返回的数据结构。
 * 3. 优化预整理确认页面的布局和体验。
 */

import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Layout,
  Steps,
  Card,
  Upload,
  Input,
  Button,
  Space,
  Typography,
  message,
  Alert,
  Divider,
  Row,
  Col,
  Tag,
  Progress,
  Select,
  Statistic,
  Collapse,
  List,
  Timeline,
  Descriptions,
  Radio,
  Result
} from 'antd';
import {
  UploadOutlined,
  FileTextOutlined,
  SendOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  DownloadOutlined,
  ReloadOutlined,
  LinkOutlined,
  InboxOutlined,
  EditOutlined,
  SaveOutlined,
  RocketOutlined,
  ThunderboltOutlined,
  AppstoreOutlined,
  FolderOpenOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import ModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
import ModuleKnowledgeToggle from '../components/ModuleKnowledgeToggle';
// ✅ 引入增强展示组件 (复用风险评估的组件)
import EnhancedAnalysisDisplay from '../components/EnhancedAnalysisDisplay';
// ✅ 引入历史记录侧边栏
import LitigationAnalysisHistorySidebar from '../components/LitigationAnalysisHistorySidebar';

import { caseTypeOptions, positionOptions, getPackageIdByCaseType } from '../config/litigationConfig';
import { ANALYSIS_GOAL_OPTIONS } from '../types/litigationAnalysis';
import { caseAnalysisApi } from '../api/litigationAnalysis';
import { getWsBaseUrl, getApiBaseUrl } from '../utils/apiConfig';
import type {
  LitigationAnalysisResult,
  LitigationPreorganizationResult,
  LitigationDocumentAnalysis,
  LitigationPosition,
  AnalysisGoal,
  Stage2AnalysisResult,
  GenerateDraftsResult,
  DraftDocument
} from '../types/litigationAnalysis';
// 将 enum 从 type 导入中移除，单独作为值导入
import { AnalysisScenario, CaseType } from '../types/litigationAnalysis';
import { DOCUMENT_TYPE_LABELS, PARTY_ROLE_LABELS, DOCUMENT_TYPE_COLORS } from '../types/litigationAnalysis';
import { useSessionPersistence } from '../hooks/useSessionPersistence';

const { Content } = Layout;
const { TextArea } = Input;
const { Text, Paragraph, Title } = Typography;
const { Dragger } = Upload;
const { Panel } = Collapse;

const LitigationAnalysisPage: React.FC = () => {
  const navigate = useNavigate();
  const wsRef = useRef<WebSocket | null>(null);

  // 新增：轮询和重连机制相关的 ref
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimerRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef<number>(0);
  const MAX_RECONNECT_ATTEMPTS = 5;

  // 步骤状态
  const [currentStep, setCurrentStep] = useState<number>(0);

  // 第一步：文件上传
  const [inferredCaseType, setInferredCaseType] = useState<CaseType | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [preorganizing, setPreorganizing] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [preorganizeProgress, setPreorganizeProgress] = useState<number>(0);
  const [preorganizeStatusText, setPreorganizeStatusText] = useState<string>('');

  // 第二步：预整理结果
  const [preorganizationResult, setPreorganizationResult] = useState<LitigationPreorganizationResult | null>(null);
  // ✅ 新增：增强分析数据状态 (用于展示全景图)
  const [enhancedAnalysisData, setEnhancedAnalysisData] = useState<any>(null);
  
  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  const [editedDoc, setEditedDoc] = useState<LitigationDocumentAnalysis | null>(null);

  // 第三步：诉讼配置
  const [litigationPosition, setLitigationPosition] = useState<LitigationPosition | null>(null);
  const [customPosition, setCustomPosition] = useState<string>('');  // 新增：自定义诉讼地位
  const [analysisGoal, setAnalysisGoal] = useState<AnalysisGoal | null>(null);
  const [customGoal, setCustomGoal] = useState<string>(''); // 保留兼容
  const [backgroundInfo, setBackgroundInfo] = useState<string>('');
  const [focusPoints, setFocusPoints] = useState<string>(''); // 保留兼容
  const [customAnalysisGoal, setCustomAnalysisGoal] = useState<string>('');

  // 3阶段架构状态
  const [analysisScenario, setAnalysisScenario] = useState<AnalysisScenario | null>(null);
  const [stage2Result, setStage2Result] = useState<Stage2AnalysisResult | null>(null);
  const [draftDocuments, setDraftDocuments] = useState<GenerateDraftsResult | null>(null);
  const [generatingDrafts, setGeneratingDrafts] = useState<boolean>(false);
  const [analysisMode, setAnalysisMode] = useState<'single' | 'multi'>('multi');

  // 会话ID
  const [sessionId, setSessionId] = useState<string>('');

  // 第四步：分析状态
  const [analysisStatus, setAnalysisStatus] = useState<string>('idle');
  const [analysisProgress, setAnalysisProgress] = useState<number>(0);
  const [analysisMessage, setAnalysisMessage] = useState<string>('');
  const [analysisStage, setAnalysisStage] = useState<string>('');

  // 第五步：分析结果
  const [result, setResult] = useState<LitigationAnalysisResult | null>(null); // 保留兼容

  // 历史记录侧边栏状态
  const [historySidebarVisible, setHistorySidebarVisible] = useState<boolean>(false);

  // ========== 会话持久化 (略微简化定义) ==========
  interface LitigationSessionData {
    step: number;
    inferredCaseType: CaseType | null;
    uploadedFiles: string[];
    preorganizationResult: LitigationPreorganizationResult | null;
    enhancedAnalysisData: any; // ✅ 持久化增强数据
    litigationPosition: LitigationPosition | null;
    analysisGoal: AnalysisGoal | null;
    customGoal: string;
    backgroundInfo: string;
    focusPoints: string;
    analysisScenario: AnalysisScenario | null;
    analysisStatus: string;
    analysisProgress: number;
    stage2Result: Stage2AnalysisResult | null;
  }

  const {
    sessionId: persistedSessionId,
    sessionData: persistedSessionData,
    saveSession,
    clearSession
  } = useSessionPersistence<LitigationSessionData>('litigation_analysis_session', {
    expirationTime: 60 * 60 * 1000
  });

  const effectiveSessionId = persistedSessionId || sessionId;

  // ========== WebSocket 连接（增强版：轮询+心跳+重连）==========
  useEffect(() => {
    if (analysisStatus === 'analyzing' && effectiveSessionId) {
      connectWebSocket();
    }
    return () => {
      // 清理所有定时器和连接
      if (wsRef.current) wsRef.current.close();
      if (heartbeatTimerRef.current) clearInterval(heartbeatTimerRef.current);
      if (pollTimerRef.current) clearInterval(pollTimerRef.current);
    };
  }, [analysisStatus, effectiveSessionId]);

  // 轮询函数（WebSocket 失败时的回退方案）
  const startPolling = () => {
    if (pollTimerRef.current) {
      console.log('Polling already active');
      return; // 避免重复轮询
    }

    console.log('🔄 Starting result polling...');
    pollTimerRef.current = setInterval(async () => {
      try {
        // 使用 any 类型，因为后端返回包含 status 字段的对象
        const result: any = await caseAnalysisApi.getCaseResult(effectiveSessionId);

        if (result.status === 'completed') {
          // 任务完成，清除轮询并获取结果
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }

          setAnalysisProgress(100);
          setAnalysisMessage('分析完成');
          setAnalysisStatus('completed');

          // 获取最终结果
          await fetchFinalResult();

        } else if (result.status === 'failed') {
          // 任务失败
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }

          setAnalysisStatus('failed');
          message.error('分析失败');
        }

      } catch (error) {
        console.error('Polling error:', error);
      }
    }, 5000); // 每 5 秒轮询一次
  };

  // 重连逻辑
  const attemptReconnect = () => {
    if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttemptsRef.current++;
      const delay = Math.min(1000 * Math.pow(2, reconnectAttemptsRef.current), 30000);

      console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})...`);

      setTimeout(() => {
        if (analysisStatus === 'analyzing') {
          connectWebSocket();
        }
      }, delay);
    } else {
      console.log('❌ Max reconnection attempts reached, switching to polling');
      startPolling();
    }
  };

  const connectWebSocket = () => {
    const wsUrl = `${getWsBaseUrl()}/api/v1/litigation-analysis/ws/${effectiveSessionId}`;
    console.log(`🔌 Connecting to WebSocket: ${wsUrl}`);
    wsRef.current = new WebSocket(wsUrl);

    wsRef.current.onopen = () => {
      console.log('✅ WebSocket connected');
      reconnectAttemptsRef.current = 0; // 重置重连计数

      // 连接成功后清除轮询
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }

      // 启动心跳（每 30 秒发送一次 ping）
      heartbeatTimerRef.current = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(JSON.stringify({ type: 'ping' }));
          console.log('💓 WebSocket ping sent');
        }
      }, 30000);
    };

    wsRef.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // 处理 pong 响应
        if (data.type === 'pong') {
          console.log('💓 WebSocket pong received');
          return;
        }

        handleWebSocketMessage(data);
      } catch (e) { console.error('WS Parse Error', e); }
    };

    wsRef.current.onerror = (error) => {
      console.error('❌ WebSocket error:', error);

      // 清除心跳定时器
      if (heartbeatTimerRef.current) {
        clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }

      // 尝试重连
      attemptReconnect();
    };

    wsRef.current.onclose = () => {
      console.log('🔌 WebSocket closed');

      // 清除心跳定时器
      if (heartbeatTimerRef.current) {
        clearInterval(heartbeatTimerRef.current);
        heartbeatTimerRef.current = null;
      }

      // 如果分析还在进行中，尝试重连
      if (analysisStatus === 'analyzing') {
        attemptReconnect();
      }
    };
  };

  const handleWebSocketMessage = (data: any) => {
    // 适配新的 workflow.py 消息格式
    if (data.type === 'node_progress') {
        setAnalysisProgress(Math.round(data.progress * 100));
        setAnalysisMessage(data.message);
        setAnalysisStage(data.node); // 用 node name 作为 stage
    } else if (data.type === 'preorganization_completed') {
        // 如果是从 WS 接收预整理结果（虽然目前通过 HTTP 返回，但保留 WS 通道）
        // 处理逻辑略，目前主要靠 HTTP 响应
    } else if (data.type === 'complete') {
        // 分析完成，获取最终结果
        setAnalysisProgress(100);
        setAnalysisMessage('分析完成');
        setAnalysisStatus('completed');

        // 从后端获取最终结果
        fetchFinalResult();
    } else if (data.type === 'error') {
        setAnalysisStatus('failed');
        message.error(data.message || '分析失败');
    }
  };

  // 添加获取最终结果的函数
  const fetchFinalResult = async () => {
    try {
      const result = await caseAnalysisApi.getCaseResult(effectiveSessionId);

      // 后端返回的是简化结构，使用类型断言处理
      const resultData = result as any;

      // 构造 Stage2AnalysisResult
      const stage2Data: Stage2AnalysisResult = {
        session_id: resultData.session_id || effectiveSessionId,
        status: resultData.status || 'completed',
        case_type: resultData.case_type || inferredCaseType || 'contract_performance',
        case_position: resultData.case_position || litigationPosition || 'unknown',
        analysis_scenario: resultData.analysis_scenario || analysisScenario || AnalysisScenario.PRE_LITIGATION,
        assembled_rules: resultData.assembled_rules || [],
        timeline: resultData.timeline || { events: [] },
        evidence_analysis: resultData.evidence_analysis || {
          admissibility_assessment: '',
          analysis_points: []
        },
        model_results: resultData.model_results || {
          final_strength: 0,
          confidence: 0,
          final_summary: resultData.case_summary || '无摘要',
          final_facts: [],
          final_legal_arguments: [],
          rule_application: [],
          final_strengths: [],
          final_weaknesses: [],
          conclusion: ''
        },
        strategies: resultData.strategies || [],
        final_report: resultData.final_report || resultData.case_summary || '无报告',
        report_json: resultData.report_json || {
          meta: {
            generated_at: new Date().toISOString(),
            case_type: inferredCaseType || 'contract_performance',
            scenario: analysisScenario || AnalysisScenario.PRE_LITIGATION,
            draft_documents_available: false
          },
          dashboard: {
            win_rate: resultData.win_probability ? resultData.win_probability * 100 : 0,
            confidence: 0,
            key_facts_count: 0,
            risk_count: 0,
            strategies_count: 0
          },
          content: {
            summary: resultData.case_summary || '',
            facts: [],
            timeline: [],
            strategies: []
          }
        },
        completed_at: resultData.completed_at || new Date().toISOString()
      };

      // 持久化会话
      saveSession(effectiveSessionId, {
        step: 3,
        inferredCaseType,
        uploadedFiles: uploadedFiles.map(f => f.name),
        preorganizationResult,
        enhancedAnalysisData,
        litigationPosition,
        analysisGoal,
        customGoal,
        backgroundInfo,
        focusPoints,
        analysisScenario: analysisScenario,
        analysisStatus: 'completed',
        analysisProgress: 100,
        stage2Result: stage2Data
      });

      setStage2Result(stage2Data);
      setCurrentStep(3);  // 跳转到结果页面
      message.success('深度分析完成！');
    } catch (error) {
      console.error('获取结果失败:', error);
      message.error('获取分析结果失败');
      setAnalysisStatus('failed');
    }
  };

  // ========== 核心操作：预整理 ==========
  const handlePreorganize = async () => {
    if (uploadedFiles.length === 0) { message.warning('请至少上传一个文件'); return; }

    setPreorganizing(true);
    setUploadProgress(0);
    setPreorganizeStatusText('正在准备上传文件...');

    // 模拟上传进度
    const uploadInterval = setInterval(() => {
      setUploadProgress(prev => (prev >= 90 ? 90 : prev + 10));
    }, 200);

    const formData = new FormData();
    uploadedFiles.forEach(file => formData.append('files', file));
    formData.append('case_type', 'contract_performance'); // 默认类型

    setPreorganizeStatusText('正在上传文件...');
    setUploadProgress(100);
    clearInterval(uploadInterval);

    setPreorganizeStatusText('正在分析文档类型和内容...');
    setPreorganizeProgress(30);

    // 添加模拟进度：在 API 调用期间平滑增长进度
    const progressInterval = setInterval(() => {
      setPreorganizeProgress(prev => (prev >= 80 ? 80 : prev + 5));
    }, 2000); // 每2秒增加5%

    try {
      const response = await fetch(`${getApiBaseUrl()}/litigation-analysis/preorganize`, {
        method: 'POST',
        body: formData
      });

      clearInterval(progressInterval);

      if (!response.ok) throw new Error('预整理失败');

      const result = await response.json(); // 注意：这里返回的是包含 enhanced_analysis_compatible 的大对象

      setPreorganizeProgress(90);
      setPreorganizeStatusText('正在整理分析结果...');

      // ✅ 关键：提取并保存数据
      // 1. 基础预整理数据 (适配旧 LitigationPreorganizationResult 结构)
      // 注意：后端的 LitigationPreorganizationResult 结构可能已经包含了 list 形式的 document_analyses
      // 如果后端返回的是 dict 形式 (document_summaries)，前端需要做适配

      // 假设后端返回的是我们在 workflow.py 中定义的结构：
      // { session_id, document_summaries: {}, enhanced_analysis_compatible: {}, ... }

      // 我们需要把它转换成前端 LitigationPreorganizationResult 期望的结构
      // 或者直接存储原始数据，并在 renderStep2 中适配

      // 这里采用直接存储的方式，但在 render 时做兼容
      setPreorganizationResult(result as any);

      // 2. 增强分析数据 (用于 EnhancedAnalysisDisplay)
      if (result.enhanced_analysis_compatible) {
          setEnhancedAnalysisData(result.enhanced_analysis_compatible);
      }

      setInferredCaseType(CaseType.CONTRACT_PERFORMANCE);
      setSessionId(result.session_id);

      setPreorganizeProgress(100);
      setPreorganizeStatusText('预整理完成！');

      setTimeout(() => {
        setCurrentStep(1);
        message.success('文档预整理完成！');
      }, 500);

    } catch (error: any) {
      clearInterval(progressInterval); // 确保清理定时器
      console.error('Preorganization failed:', error);
      setPreorganizeStatusText('预整理失败');
      message.error('文档预整理失败，请重试');
    } finally {
      setPreorganizing(false);
    }
  };

  // ========== 核心操作：启动分析 (阶段2) ==========
  const handleStartAnalysis = async () => {
    if (!litigationPosition) { message.warning('请选择诉讼地位'); return; }
    if (!analysisGoal) { message.warning('请选择分析立场'); return; }

    setAnalysisStatus('analyzing');  // 改为 analyzing 状态
    setAnalysisProgress(0);
    setAnalysisMessage('正在启动分析...');
    setCurrentStep(2);  // 先跳转到分析进度页面

    try {
      const effectiveCaseType = inferredCaseType || 'contract_performance';
      let mappedScenario: AnalysisScenario;

      if (analysisGoal === 'prosecution') mappedScenario = AnalysisScenario.PRE_LITIGATION;
      else if (analysisGoal === 'defense') mappedScenario = AnalysisScenario.DEFENSE;
      else mappedScenario = AnalysisScenario.MEDIATION;

      const packageId = getPackageIdByCaseType(effectiveCaseType);

      // 获取实际的诉讼地位值（处理识别主体的情况）
      const getActualLitigationPosition = (): string => {
        if (litigationPosition === 'custom') {
          return customPosition || 'unknown';
        }

        // 如果是识别出的主体，需要从主体画像中获取其角色
        if (litigationPosition?.startsWith('identified_')) {
          const index = parseInt(litigationPosition.split('_')[1]);
          const party = enhancedAnalysisData?.parties?.[index];
          if (party) {
            // 将角色映射到标准诉讼地位
            const roleMapping: Record<string, string> = {
              '原告': 'plaintiff',
              '被告': 'defendant',
              '申请人': 'applicant',
              '被申请人': 'respondent',
              '上诉人': 'appellant',
              '被上诉人': 'appellee',
              '第三人': 'third_party'
            };
            return roleMapping[party.role] || 'unknown';
          }
        }

        return litigationPosition || 'unknown';
      };

      const actualPosition = getActualLitigationPosition();

      const finalBackgroundInfo = customAnalysisGoal
        ? `${analysisGoal === 'custom' ? '自定义目标：' : ''}${customAnalysisGoal}${backgroundInfo ? '\n\n' + backgroundInfo : ''}`
        : backgroundInfo;

      setAnalysisMessage(`正在${analysisMode === 'single' ? '单模型' : '多模型'}分析案件...`);
      setAnalysisProgress(10);

      // 发起分析请求
      const response = await caseAnalysisApi.analyzeLitigationCase({
        preorganized_data: preorganizationResult,  // 直接传递对象，不手动序列化
        case_position: actualPosition,  // 使用映射后的实际诉讼地位
        analysis_scenario: mappedScenario,
        case_package_id: packageId,
        case_type: effectiveCaseType,
        user_input: finalBackgroundInfo || focusPoints,
        analysis_mode: analysisMode
      });

      // 只保存 session_id，等待 WebSocket 推送结果
      setSessionId(response.session_id);
      setAnalysisProgress(20);
      setAnalysisMessage('分析已启动，AI 正在进行深度推演...');

      // 不要直接设置 stage2Result 和跳到 step 3
      // 等待 WebSocket 推送完成后再处理
      // WebSocket 消息处理会更新 stage2Result 并跳转

    } catch (error: any) {
      console.error('Failed to start stage2 analysis:', error);
      message.error(error.response?.data?.detail || '启动分析失败');
      setAnalysisStatus('failed');
      setCurrentStep(1);
    }
  };

  // ========== 其他 Handlers ==========
  const handleReset = () => {
    setCurrentStep(0);
    setInferredCaseType(null);
    setUploadedFiles([]);
    setPreorganizationResult(null);
    setEnhancedAnalysisData(null); // 重置
    setLitigationPosition(null);
    setAnalysisGoal(null);
    setCustomGoal('');
    setBackgroundInfo('');
    setFocusPoints('');
    setSessionId('');
    setAnalysisStatus('idle');
    setAnalysisProgress(0);
    setAnalysisMessage('');
    setStage2Result(null);
    setDraftDocuments(null);
    setGeneratingDrafts(false);
    clearSession();
  };

  // ========== 历史记录恢复处理 ==========
  const handleRestoreSession = async (sessionId: string) => {
    try {
      // 从后端获取完整数据
      const sessionData: any = await caseAnalysisApi.getCaseResult(sessionId);

      // 恢复状态
      setSessionId(sessionId);
      if (sessionData.case_type) {
        setInferredCaseType(sessionData.case_type);
      }
      if (sessionData.case_position) {
        setLitigationPosition(sessionData.case_position);
      }

      // 根据状态恢复步骤
      if (sessionData.status === 'completed') {
        // 已完成任务：恢复到结果页面
        setStage2Result(sessionData as Stage2AnalysisResult);
        setCurrentStep(3); // 结果页面
      } else if (sessionData.status === 'pending' || sessionData.status === 'processing' || sessionData.status === 'started') {
        // 进行中任务：恢复到确认页面（需要获取预整理数据）
        // 如果有预整理数据，直接恢复；否则重新开始
        setCurrentStep(1); // 确认页面
      }

      // 清除持久化数据
      clearSession();

      message.success('任务已恢复');

    } catch (error) {
      console.error('恢复任务失败:', error);
      message.error('恢复任务失败，请重试');
    }
  };

  // ========== 报告下载处理 ==========
  const handleDownloadPreorganizationReport = async (format: 'docx' | 'pdf') => {
    try {
      await caseAnalysisApi.downloadPreorganizationReport(effectiveSessionId, format);
      message.success(`${format.toUpperCase()}报告下载成功`);
    } catch (error: any) {
      console.error('下载预整理报告失败:', error);
      message.error(error.response?.data?.detail || '下载失败，请稍后重试');
    }
  };

  const handleDownloadAnalysisReport = async (format: 'docx' | 'pdf') => {
    try {
      await caseAnalysisApi.downloadAnalysisReport(effectiveSessionId, format);
      message.success(`${format.toUpperCase()}报告下载成功`);
    } catch (error: any) {
      console.error('下载分析报告失败:', error);
      message.error(error.response?.data?.detail || '下载失败，请稍后重试');
    }
  };

  const handleRemoveFile = (file: File) => {
    setUploadedFiles(prev => prev.filter(f => f !== file));
  };

  const handleFileUpload = (file: File) => {
    setUploadedFiles(prev => [...prev, file]);
    return false;
  };

  // ========== 步骤渲染：Step 1 (上传) ==========
  const renderStep1 = () => (
    <Card title="步骤1：上传案件文档">
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <ModuleKnowledgeToggle moduleName="litigation_analysis" moduleLabel="案件分析" />
        <Alert message="智能案件分析" description="系统将根据您上传的文档自动识别案件类型并进行智能分析。支持PDF、Word、图片等格式。" type="info" showIcon />
        
        <div>
          <Text strong style={{ fontSize: 16 }}>上传案件文档</Text>
          <Text type="secondary" style={{ marginLeft: 8 }}>（至少上传1个文件）</Text>
          <Divider style={{ margin: '12px 0' }} />
          <Dragger multiple fileList={[]} beforeUpload={handleFileUpload} accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg">
            <p className="ant-upload-drag-icon"><InboxOutlined style={{ fontSize: 48, color: '#1890ff' }} /></p>
            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
            <p className="ant-upload-hint">支持PDF、Word、图片等格式，可同时上传多个文件</p>
          </Dragger>
          {uploadedFiles.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <Text strong>已选择 {uploadedFiles.length} 个文件：</Text>
              <div style={{ marginTop: 8 }}>
                {uploadedFiles.map((file, index) => (
                  <Tag key={index} closable onClose={() => handleRemoveFile(file)} style={{ marginBottom: 8 }}>{file.name}</Tag>
                ))}
              </div>
            </div>
          )}
        </div>

        {preorganizing && (
          <Card>
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Text strong>{preorganizeStatusText}</Text>
                <Text type="secondary">{preorganizeProgress > 0 ? `${preorganizeProgress}%` : ''}</Text>
              </div>
              <Progress percent={preorganizeProgress} status={preorganizeProgress === 100 ? 'success' : 'active'} strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }} />
            </Space>
          </Card>
        )}

        <div style={{ textAlign: 'right' }}>
          <Button type="primary" size="large" onClick={handlePreorganize} loading={preorganizing} disabled={uploadedFiles.length === 0 || preorganizing} icon={<SendOutlined />}>
            下一步：预整理文档
          </Button>
        </div>
      </Space>
    </Card>
  );

  // ========== 步骤渲染：Step 2 (确认) - 核心修改 ==========
  const renderStep2 = () => {
    if (!preorganizationResult) return null;

    // 适配文档列表：支持 dict 或 list 结构
    let docList: any[] = [];
    if (preorganizationResult.document_summaries && typeof preorganizationResult.document_summaries === 'object') {
        // 如果是字典 (新结构)
        docList = Object.values(preorganizationResult.document_summaries);
    } else if (preorganizationResult.document_analyses && Array.isArray(preorganizationResult.document_analyses)) {
        // 如果是列表 (旧结构或适配后)
        docList = preorganizationResult.document_analyses;
    }

    // 提取关系数据
    const relationships = preorganizationResult.document_relationships || [];

    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card>
          <Button onClick={() => setCurrentStep(0)}>上一步</Button>
        </Card>

        {/* 报告导出 */}
        <Card>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Text strong>报告导出</Text>
            <Space wrap>
              <Button
                icon={<DownloadOutlined />}
                onClick={() => handleDownloadPreorganizationReport('docx')}
              >
                下载Word报告
              </Button>
              <Button
                icon={<DownloadOutlined />}
                onClick={() => handleDownloadPreorganizationReport('pdf')}
              >
                下载PDF报告
              </Button>
            </Space>
          </Space>
        </Card>

        {/* ✅ 新增：案件全景展示 (复用风险评估的高级组件) */}
        {enhancedAnalysisData ? (
          <Card
            title={<Space><FileTextOutlined /><Text strong>案件全景</Text><Tag color="purple">AI 深度洞察</Tag></Space>}
            style={{ marginBottom: 16 }}
          >
            <EnhancedAnalysisDisplay enhancedAnalysis={enhancedAnalysisData} />
          </Card>
        ) : (
          // 降级显示
          <Card title="案件全景">
             <Alert message="正在生成全景数据..." type="info" showIcon />
          </Card>
        )}

        {/* 文档列表 (保持原有逻辑，做微调) */}
        <Card title={<Space><FolderOpenOutlined /><Text strong>文档详细分析</Text></Space>}>
          <Collapse accordion>
            {docList.map((doc: any, index: number) => {
                const title = doc.document_title || doc.file_name || `文档 ${index+1}`;
                const typeLabel = DOCUMENT_TYPE_LABELS[doc.document_subtype || doc.file_type] || '其他文书';
                
                return (
                  <Panel 
                    header={<Space><Text strong>{title}</Text><Tag color="blue">{typeLabel}</Tag></Space>} 
                    key={doc.file_id || index}
                  >
                    <Descriptions column={1} size="small" bordered>
                      <Descriptions.Item label="核心摘要">{doc.summary || doc.content_summary}</Descriptions.Item>
                      {doc.risk_signals && doc.risk_signals.length > 0 && (
                        <Descriptions.Item label="风险提示">
                          {doc.risk_signals.map((s: string, i: number) => <Tag color="red" key={i}>{s}</Tag>)}
                        </Descriptions.Item>
                      )}
                      {/* 可以继续补充其他字段展示 */}
                    </Descriptions>
                  </Panel>
                );
            })}
          </Collapse>
        </Card>

        {/* 关联关系 */}
        {relationships.length > 0 && (
          <Card title={`文档关联 (${relationships.length})`}>
            <List
              dataSource={relationships}
              renderItem={(item: any) => (
                <List.Item>
                  <Space>
                    <LinkOutlined />
                    <Text>{item.doc1_name || '文档A'}</Text>
                    <Tag>{item.relationship_type}</Tag>
                    <Text>{item.doc2_name || '文档B'}</Text>
                    <Text type="secondary">({item.description || item.reasoning})</Text>
                  </Space>
                </List.Item>
              )}
            />
          </Card>
        )}

        {/* 分析配置表单 */}
        <Card title="分析配置">
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <div>
              <Text strong>您的诉讼地位</Text>
              <Divider style={{ margin: '12px 0' }} />
              <Select
                placeholder="请选择您的诉讼地位"
                size="large"
                style={{ width: '100%' }}
                value={litigationPosition}
                onChange={(value) => {
                  setLitigationPosition(value);
                  if (value !== 'custom') {
                    setCustomPosition('');
                  }
                }}
              >
                {/* 如果有主体画像数据，显示识别出的主体 */}
                {enhancedAnalysisData?.parties && enhancedAnalysisData.parties.length > 0 &&
                  enhancedAnalysisData.parties.map((party: any, index: number) => (
                    <Select.Option key={`identified_${index}`} value={`identified_${index}`}>
                      <div>
                        <div style={{ fontWeight: 500 }}>{party.name}</div>
                        <div style={{ fontSize: 12, color: '#999' }}>角色：{party.role}</div>
                      </div>
                    </Select.Option>
                  ))
                }
                {/* 分隔符 */}
                {enhancedAnalysisData?.parties && enhancedAnalysisData.parties.length > 0 && (
                  <Select.Option key="divider" disabled>
                    <Divider style={{ margin: '8px 0' }} />
                  </Select.Option>
                )}
                {/* 固定选项 */}
                {positionOptions.map(opt => (
                  <Select.Option key={opt.value} value={opt.value}>
                    {opt.label}
                  </Select.Option>
                ))}
                {/* 其他（手动输入）选项 */}
                <Select.Option key="custom" value="custom">
                  其他（手动输入）
                </Select.Option>
              </Select>
              {litigationPosition === 'custom' && (
                <Input
                  placeholder="请输入您的诉讼地位"
                  value={customPosition}
                  onChange={(e) => setCustomPosition(e.target.value)}
                  style={{ marginTop: 8 }}
                />
              )}
            </div>
            <div>
              <Text strong>分析场景</Text>
              <Divider style={{ margin: '12px 0' }} />
              <Select
                placeholder="请选择分析场景"
                size="large"
                style={{ width: '100%' }}
                value={analysisGoal}
                onChange={(value) => {
                  setAnalysisGoal(value);
                  if (value !== 'custom') {
                    setCustomGoal('');
                  }
                }}
                options={ANALYSIS_GOAL_OPTIONS}
              />
              {analysisGoal === 'custom' && (
                <Input.TextArea
                  placeholder="请具体描述您的分析场景和需求，例如：准备仲裁、申请执行、证据收集等..."
                  value={customGoal}
                  onChange={(e) => setCustomGoal(e.target.value)}
                  autoSize={{ minRows: 2, maxRows: 4 }}
                  style={{ marginTop: 8 }}
                />
              )}
            </div>
            <div>
              <Text strong>分析模式</Text>
              <Divider style={{ margin: '12px 0' }} />
              <Radio.Group value={analysisMode} onChange={e => setAnalysisMode(e.target.value)}>
                <Radio value="multi">多模型并行分析 (推荐)</Radio>
                <Radio value="single">单模型快速分析</Radio>
              </Radio.Group>
            </div>
            
            <div style={{ textAlign: 'right' }}>
              <Button
                type="primary"
                size="large"
                icon={<SendOutlined />}
                onClick={handleStartAnalysis}
                disabled={!litigationPosition || !analysisGoal}
              >
                启动深度分析
              </Button>
            </div>
          </Space>
        </Card>
      </Space>
    );
  };

  // ========== 步骤渲染：Step 3, 4, 5 (保持基本逻辑) ==========

  const renderStep3 = () => (
    <Card title="AI 分析中">
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* 新增：案件基本信息卡片 */}
        <Card
          type="inner"
          title="案件信息"
          size="small"
          style={{ backgroundColor: '#fafafa' }}
        >
          <Descriptions column={2} size="small">
            <Descriptions.Item label="案件类型">
              {inferredCaseType ? (
                <Tag color="blue">
                  {caseTypeOptions.find(opt => opt.value === inferredCaseType)?.label || inferredCaseType}
                </Tag>
              ) : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="诉讼地位">
              {litigationPosition ? (
                <Tag color="purple">
                  {positionOptions.find(opt => opt.value === litigationPosition)?.label || litigationPosition}
                </Tag>
              ) : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="分析场景">
              {analysisGoal ? (
                <Tag color="green">
                  {ANALYSIS_GOAL_OPTIONS.find(opt => opt.value === analysisGoal)?.label || analysisGoal}
                </Tag>
              ) : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="分析模式">
              <Tag color="orange">
                {analysisMode === 'multi' ? '多模型并行分析' : '单模型快速分析'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>

          {backgroundInfo && (
            <div style={{ marginTop: 12 }}>
              <Text type="secondary">补充信息：</Text>
              <Paragraph
                ellipsis={{ rows: 2, expandable: true, symbol: '展开' }}
                style={{ marginTop: 4, marginBottom: 0 }}
              >
                {backgroundInfo}
              </Paragraph>
            </div>
          )}
        </Card>

        {/* 现有进度显示 */}
        <Space>
          {analysisStatus === 'analyzing' && <LoadingOutlined spin />}
          <Text strong style={{ fontSize: 16 }}>{analysisMessage}</Text>
        </Space>
        <Progress
          percent={analysisProgress}
          status="active"
          strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }}
        />

        {analysisStage && (
          <Alert
            message={`当前阶段：${analysisStage}`}
            type="info"
            showIcon
            style={{ marginTop: 8 }}
          />
        )}
      </Space>
    </Card>
  );

  const renderStep4 = () => {
    if (!stage2Result) return null;

    // 检查是否有错误（通过 status 字段）
    if (stage2Result.status === "failed") {
      return (
        <Result
          status="error"
          title="分析失败"
          subTitle="模型分析失败，请重试"
          extra={
            <Space>
              <Button onClick={handleReset}>重新分析</Button>
            </Space>
          }
        />
      );
    }

    // 检查 model_results 是否存在
    if (!stage2Result.model_results) {
      return (
        <Result
          status="warning"
          title="数据格式错误"
          subTitle="后端返回的数据格式不正确"
          extra={
            <Space>
              <Button onClick={handleReset}>重新分析</Button>
            </Space>
          }
        />
      );
    }

    // 提供默认值，防止访问未定义属性
    const {
      final_strength = 0,
      confidence = 0,
      final_summary = "无摘要"
    } = stage2Result.model_results;

    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <Card>
          <Space direction="vertical" size="small" style={{ width: '100%' }}>
            <Space wrap>
              <Button onClick={handleReset}>重新分析</Button>
              <Button type="primary" onClick={handleGenerateDrafts} loading={generatingDrafts}>生成法律文书</Button>
            </Space>
            <Divider style={{ margin: 8 }} />
            <Text strong>报告导出</Text>
            <Space wrap>
              <Button
                type="primary"
                icon={<DownloadOutlined />}
                onClick={() => handleDownloadAnalysisReport('docx')}
              >
                下载Word报告
              </Button>
              <Button
                icon={<DownloadOutlined />}
                onClick={() => handleDownloadAnalysisReport('pdf')}
              >
                下载PDF报告
              </Button>
            </Space>
          </Space>
        </Card>

        {/* 核心结论 */}
        <Card title="核心结论">
           <Row gutter={16}>
             <Col span={12}><Statistic title="胜诉率" value={(final_strength * 100).toFixed(1)} suffix="%" precision={1} /></Col>
             <Col span={12}><Statistic title="置信度" value={(confidence * 100).toFixed(0)} suffix="%" /></Col>
           </Row>
           <Divider />
           <ReactMarkdown>{final_summary}</ReactMarkdown>
        </Card>

        {/* 完整报告 */}
        <Card title="详细分析报告">
           <ReactMarkdown>{stage2Result.final_report}</ReactMarkdown>
        </Card>
      </Space>
    );
  };

  // 生成文书页面
  const handleGenerateDrafts = async () => {
      if (!sessionId) return;
      setGeneratingDrafts(true);
      try {
          const res = await caseAnalysisApi.generateLitigationDocuments({
              session_id: sessionId,
              case_position: litigationPosition!,
              analysis_scenario: analysisScenario!,
              analysis_result: stage2Result || undefined
          });
          setDraftDocuments(res);
          message.success(`生成了 ${res.total_count} 份文书`);
          // 生成成功后跳转到文书列表页面
          setCurrentStep(4);
      } catch (e) {
          message.error('生成失败');
      }
      finally {
          setGeneratingDrafts(false);
      }
  };

  const renderStep5 = () => {
      if (!draftDocuments) {
          // 不再自动触发，等待用户手动点击生成
          return (
            <Card>
              <div style={{ textAlign: 'center', padding: '50px 0' }}>
                <p>请点击"生成法律文书"按钮开始生成文书</p>
                <Button type="primary" onClick={handleGenerateDrafts} loading={generatingDrafts}>
                  生成法律文书
                </Button>
              </div>
            </Card>
          );
      }
      return (
          <Space direction="vertical" style={{width:'100%'}}>
              <Card title="法律文书草稿">
                  <List
                      dataSource={draftDocuments.draft_documents}
                      renderItem={doc => (
                          <List.Item actions={[<Button icon={<DownloadOutlined />}>下载</Button>]}>
                              <List.Item.Meta
                                  avatar={<FileTextOutlined style={{fontSize: 24, color: '#1890ff'}}/>}
                                  title={doc.document_name}
                                  description={`生成时间: ${new Date(doc.generated_at).toLocaleString()}`}
                              />
                          </List.Item>
                      )}
                  />
              </Card>
              <Button onClick={() => setCurrentStep(3)}>返回报告</Button>
          </Space>
      );
  };

  // ========== 主渲染 ==========

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <ModuleNavBar currentModuleKey="case-analysis" />
      <Content style={{ flex: 1, padding: '24px' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto' }}>
          {/* 顶部操作栏：步骤 + 历史记录按钮 */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
            <Card style={{ flex: 1, marginRight: 16 }}>
              <Steps
                current={currentStep}
                items={[
                  { title: '上传文件' },
                  { title: '全景预整理' },
                  { title: '深度分析' },
                  { title: '分析报告' },
                  { title: '文书生成' }
                ]}
              />
            </Card>
            <Button
              icon={<AppstoreOutlined />}
              onClick={() => setHistorySidebarVisible(true)}
              style={{ height: 'auto', padding: '12px 24px' }}
            >
              历史任务
            </Button>
          </div>

          {currentStep === 0 && renderStep1()}
          {currentStep === 1 && renderStep2()}
          {currentStep === 2 && renderStep3()}
          {currentStep === 3 && renderStep4()}
          {currentStep === 4 && renderStep5()}
        </div>
      </Content>

      {/* 历史记录侧边栏 */}
      <LitigationAnalysisHistorySidebar
        visible={historySidebarVisible}
        onClose={() => setHistorySidebarVisible(false)}
        onLoadSession={handleRestoreSession}
      />
    </Layout>
  );
};

export default LitigationAnalysisPage;