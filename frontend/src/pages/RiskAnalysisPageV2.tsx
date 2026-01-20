// frontend/src/pages/RiskAnalysisPageV2.tsx
// (终极完整版：包含所有历史任务、心跳逻辑及UI细节)

import React, { useState, useEffect, useRef } from 'react';
import {
  Layout,
  Card,
  Steps,
  Button,
  Upload,
  Input,
  Space,
  Typography,
  message,
  Alert,
  Divider,
  Tag,
  Progress,
  Radio,
  Descriptions,
  Row,
  Col
} from 'antd';
import {
  UploadOutlined,
  SendOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  DownloadOutlined,
  DragOutlined,
  FileTextOutlined,
  SafetyOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';

import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

import RiskPackageSelector from '../components/RiskPackageSelector';
import MultiModelComparison, { MultiModelComparisonResult } from '../components/MultiModelComparison';
import ReportResultsDisplay, { RiskAnalysisReport } from '../components/ReportResultsDisplay';
import DiagramViewer from '../components/DiagramViewer';
import EnhancedModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
// ✅ 引入新组件
import EnhancedAnalysisDisplay from '../components/EnhancedAnalysisDisplay';
import ModuleKnowledgeToggle from '../components/ModuleKnowledgeToggle';
import RiskAnalysisHistorySidebar from '../components/RiskAnalysisHistorySidebar';
import RiskAnalysisHistoryButton from '../components/RiskAnalysisHistoryButton';

import api from '../api';
import type { RiskRulePackage } from '../types/riskAnalysis';
import { riskAnalysisHistoryManager } from '../utils/riskAnalysisHistoryManager';
import { getWsBaseUrl } from '../utils/apiConfig';

const { Content } = Layout;
const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

// --- 类型定义 ---
type SessionStatus = 'idle' | 'uploading' | 'analyzing' | 'completed' | 'failed';
type NodeStatus = 'pending' | 'processing' | 'completed' | 'failed';

interface NodeProgress {
  documentPreorganization: NodeStatus;
  multiModelAnalysis: NodeStatus;
  reportGeneration: NodeStatus;
}

interface AnalysisState {
  status: SessionStatus;
  sessionId: string;
  progress: number;
  message: string;
  nodeProgress?: NodeProgress;
  comparison?: MultiModelComparisonResult;
  report?: RiskAnalysisReport;
  diagrams?: Array<{
    id: string;
    type: string;
    title: string;
    format: string;
    sourceCode: string;
  }>;
  analysisMode?: 'single' | 'multi';
}

// 可排序组件
interface SortableItemProps {
  id: string;
  pkg: RiskRulePackage;
  index: number;
}

const SortableItem: React.FC<SortableItemProps> = ({ id, pkg, index }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1, cursor: 'grab' };
  const categoryInfo = getCategoryInfo(pkg.package_category);

  return (
    <div ref={setNodeRef} style={style} {...attributes}>
      <Card size="small" style={{ marginBottom: 8, borderLeft: `3px solid ${getTagColor(categoryInfo.color)}`, backgroundColor: isDragging ? '#e6f7ff' : '#f9f9f9', cursor: 'grab' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Tag color="blue" style={{ margin: 0, fontSize: 11 }}>#{index + 1}</Tag>
            <Text style={{ fontSize: 13 }}>{categoryInfo.icon} {pkg.package_name}</Text>
          </Space>
          <span {...listeners} style={{ cursor: 'grab', padding: '4px' }}><DragOutlined style={{ fontSize: 14 }} /></span>
        </div>
      </Card>
    </div>
  );
};

// 辅助函数
const CATEGORY_MAP: Record<string, { label: string; color: string; icon: string }> = {
  'equity_risk': { label: '股权风险', color: 'blue', icon: '🏢' },
  'investment_risk': { label: '投资风险', color: 'gold', icon: '💼' },
  'governance_risk': { label: '治理风险', color: 'purple', icon: '⚖️' },
  'contract_risk': { label: '合同风险', color: 'orange', icon: '📄' },
  'tax_risk': { label: '税务风险', color: 'green', icon: '🧾' },
  'litigation_risk': { label: '诉讼风险', color: 'red', icon: '⚖️' }
};

function getCategoryInfo(category: string) {
  return CATEGORY_MAP[category] || { label: category, color: 'default', icon: '📦' };
}

function getTagColor(color: string): string {
  const colorMap: Record<string, string> = { 'blue': '#1890ff', 'gold': '#faad14', 'purple': '#722ed1', 'orange': '#fa8c16', 'green': '#52c41a', 'red': '#ff4d4f', 'default': '#d9d9d9' };
  return colorMap[color] || color;
}

const RiskAnalysisPageV2: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const wsRef = useRef<WebSocket | null>(null);

  // 状态管理
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [selectedPackageIds, setSelectedPackageIds] = useState<string[]>([]);
  const [allPackages, setAllPackages] = useState<RiskRulePackage[]>([]);
  const [userInput, setUserInput] = useState<string>('');
  const [uploadedFileIds, setUploadedFileIds] = useState<string[]>([]);
  const [uploadIds, setUploadIds] = useState<string[]>([]);
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ uid: string; name: string; status: string; response?: any }>>([]);

  const [analysisState, setAnalysisState] = useState<AnalysisState>({
    status: 'idle',
    sessionId: '',
    progress: 0,
    message: '',
    nodeProgress: {
      documentPreorganization: 'pending',
      multiModelAnalysis: 'pending',
      reportGeneration: 'pending',
    },
  });

  const [preorganizationData, setPreorganizationData] = useState<any>(null);
  const [enhancedAnalysis, setEnhancedAnalysis] = useState<any>(null);
  const [isRestoringSession, setIsRestoringSession] = useState<boolean>(false);
  const [selectedAnalysisMode, setSelectedAnalysisMode] = useState<'single' | 'multi' | null>(null);
  const [evaluationStance, setEvaluationStance] = useState<string>('');
  const [historyVisible, setHistoryVisible] = useState<boolean>(false);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [isCreatingNewSession, setIsCreatingNewSession] = useState<boolean>(false);
  const [hasRestoredOnce, setHasRestoredOnce] = useState<boolean>(false);

  const sensors = useSensors(useSensor(PointerSensor), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));
  
  const selectedPackages = selectedPackageIds.map(id => allPackages.find(pkg => pkg.package_id === id)).filter(Boolean) as RiskRulePackage[];

  // 声明函数，防止 hoisting 问题
  const fetchFinalResult = async (retryCount = 0, specificSessionId?: string) => {
    const sid = specificSessionId || analysisState.sessionId;
    try {
      const response = await api.get(`/risk-analysis-v2/result/${sid}`);
      const backendData = response.data;

      const dist = backendData.risk_distribution || { high: 0, medium: 0, low: 0, critical: 0 };
      const transformedDistribution = {
        high: (dist.high || 0) + (dist.critical || 0),
        medium: dist.medium || 0,
        low: dist.low || 0
      };

      const transformedRiskItems = (backendData.risk_items || []).map((item: any) => {
        let riskLevel = item.risk_level?.toLowerCase();
        if (riskLevel === 'critical') riskLevel = 'high';
        if (!['high', 'medium', 'low'].includes(riskLevel)) riskLevel = 'low';
        
        return {
          risk_id: item.id.toString(),
          risk_title: item.title,
          risk_level: riskLevel,
          description: item.description,
          confidence: item.confidence,
          details: item.reasons ? item.reasons.join('\n') : '',
          suggestions: Array.isArray(item.suggestions) ? item.suggestions.join('\n') : item.suggestions
        };
      });

      const transformedReport: RiskAnalysisReport = {
        executive_summary: backendData.summary || '',
        risk_items: transformedRiskItems,
        risk_distribution: transformedDistribution,
        strategies: [],
        recommendations: [],
        analysis_metadata: {
          analysis_duration: backendData.completed_at && backendData.created_at
            ? new Date(backendData.completed_at).getTime() - new Date(backendData.created_at).getTime()
            : undefined
        }
      };

      setAnalysisState(prev => ({
        ...prev,
        status: 'completed',
        report: transformedReport,
        comparison: backendData.comparison,
        diagrams: backendData.diagrams,
        nodeProgress: { ...prev.nodeProgress!, multiModelAnalysis: 'completed', reportGeneration: 'completed' }
      }));
      setCurrentStep(4);
      message.success('风险评估完成！');

    } catch (error: any) {
      if (error.response?.status === 400 && retryCount < 3) {
        setTimeout(() => fetchFinalResult(retryCount + 1, sid), 1000 * (retryCount + 1));
      } else {
        message.error(`获取结果失败: ${error.message}`);
      }
    }
  };

  // 提前定义 handleWebSocketMessage 以便 useEffect 使用
  const handleWebSocketMessage = (data: any) => {
    if ((data.type === 'node_progress' || data.type === 'progress') && Math.round(data.progress * 100) === 100) {
      console.log('Progress 100%, waiting for complete signal');
    }

    switch (data.type) {
      case 'node_progress':
        setAnalysisState(prev => ({
          ...prev,
          progress: Math.round(data.progress * 100),
          message: data.message,
          nodeProgress: { ...prev.nodeProgress!, [data.node]: data.status }
        }));
        break;

      case 'preorganization_completed':
        console.log('[WS] 预整理完成');
        setPreorganizationData({
          basic: data.preorganized_data || {},
          enhanced: data.enhanced_data || {}
        });
        setEnhancedAnalysis(data.enhanced_analysis || null);
        setCurrentStep(2);
        setAnalysisState(prev => ({
          ...prev, progress: 100, message: '文档预整理完成',
          nodeProgress: { ...prev.nodeProgress!, documentPreorganization: 'completed' }
        }));
        break;

      case 'complete':
        fetchFinalResult();
        break;

      case 'error':
        setAnalysisState(prev => ({ ...prev, status: 'failed', message: data.message }));
        message.error(data.message);
        break;
        
      case 'comparison':
        setAnalysisState(prev => ({ ...prev, comparison: data.comparison }));
        break;
        
      case 'diagram':
        setAnalysisState(prev => ({ ...prev, diagrams: [...(prev.diagrams || []), data.diagram] }));
        break;
    }
  };

  // ========== 会话恢复逻辑 ==========
  const fetchFinalResultForSession = async (sessionId: string) => {
    setAnalysisState(prev => ({ ...prev, sessionId }));
    await fetchFinalResult(0, sessionId);
  };

  useEffect(() => {
    const restoreSession = async () => {
      const urlSessionId = searchParams.get('session_id');
      if (!urlSessionId || isCreatingNewSession || hasRestoredOnce) return;
      
      if (analysisState.sessionId === urlSessionId && ['analyzing', 'processing', 'uploading'].includes(analysisState.status)) return;

      try {
        setIsRestoringSession(true);
        const response = await api.get(`/risk-analysis-v2/${urlSessionId}/restore-state`);
        const restoreData = response.data;

        switch (restoreData.current_stage) {
          case 'input':
            setAnalysisState(prev => ({ ...prev, sessionId: urlSessionId, status: 'idle' }));
            setCurrentStep(0);
            break;
          case 'preorganization_in_progress':
            setAnalysisState({
              status: 'analyzing', sessionId: urlSessionId, progress: 30, message: '正在继续文档预整理...',
              nodeProgress: { documentPreorganization: 'processing', multiModelAnalysis: 'pending', reportGeneration: 'pending' }
            });
            setCurrentStep(1);
            break;
          case 'preorganization_completed':
            const preorgData = restoreData.data.preorganization;
            setPreorganizationData({ basic: preorgData, enhanced: preorgData.enhanced_analysis || {} });
            setEnhancedAnalysis(preorgData.enhanced_analysis || null);
            setAnalysisState(prev => ({
              ...prev, sessionId: urlSessionId, status: 'idle', progress: 100, message: '文档预整理完成',
              nodeProgress: { documentPreorganization: 'completed', multiModelAnalysis: 'pending', reportGeneration: 'pending' }
            }));
            setCurrentStep(2);
            if (preorgData.analysis_mode) setSelectedAnalysisMode(preorgData.analysis_mode);
            break;
          case 'analysis_in_progress':
            setAnalysisState({
              status: 'analyzing', sessionId: urlSessionId, progress: 60, message: '正在继续分析...',
              nodeProgress: { documentPreorganization: 'completed', multiModelAnalysis: 'processing', reportGeneration: 'pending' }
            });
            setCurrentStep(3);
            break;
          case 'analysis_completed':
            setAnalysisState({
              status: 'completed', sessionId: urlSessionId, progress: 100, message: '分析已完成',
              nodeProgress: { documentPreorganization: 'completed', multiModelAnalysis: 'completed', reportGeneration: 'completed' }
            });
            setCurrentStep(4);
            await fetchFinalResultForSession(urlSessionId);
            break;
        }
        setHasRestoredOnce(true);
        message.success('已恢复之前的分析状态');
      } catch (error: any) {
        if (error.response?.status === 404) {
          const newSearchParams = new URLSearchParams(searchParams);
          newSearchParams.delete('session_id');
          window.history.replaceState({}, '', `${window.location.pathname}?${newSearchParams.toString()}`);
        }
      } finally {
        setIsRestoringSession(false);
      }
    };
    restoreSession();
  }, [searchParams, isCreatingNewSession, analysisState.sessionId, hasRestoredOnce]);

  // ========== 历史任务管理 (补全) ==========
  useEffect(() => {
    const syncUnreadCount = async () => {
      try {
        await riskAnalysisHistoryManager.syncHistoryList();
        setUnreadCount(riskAnalysisHistoryManager.getIncompleteCount());
      } catch (error) { console.error('同步失败', error); }
    };
    syncUnreadCount();
    const interval = setInterval(syncUnreadCount, 30000);
    return () => clearInterval(interval);
  }, []);

  // ========== 智能引导上下文穿透 ==========
  useEffect(() => {
    // 从智能引导页面传递过来的参数
    const state = location.state as { description?: string } | null;
    if (state?.description) {
      setUserInput(state.description);
      message.success('已根据您的描述自动填充内容');
    }
  }, [location.state]);

  useEffect(() => {
    if (!analysisState.sessionId || analysisState.status === 'idle') return;
    const sendHeartbeat = async () => {
      try { await api.post(`/risk-analysis-v2/${analysisState.sessionId}/heartbeat`, { ws_connected: true }); }
      catch (e) { console.error('心跳失败', e); }
    };
    sendHeartbeat();
    const interval = setInterval(sendHeartbeat, 30000);
    return () => clearInterval(interval);
  }, [analysisState.sessionId, analysisState.status]);

  useEffect(() => {
    const handleBeforeUnload = async () => {
      if (analysisState.sessionId && ['analyzing', 'uploading'].includes(analysisState.status)) {
        await api.post(`/risk-analysis-v2/${analysisState.sessionId}/heartbeat`, { ws_connected: false });
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [analysisState.sessionId, analysisState.status]);

  // ========== WebSocket 连接 ==========
  useEffect(() => {
    if (isRestoringSession || !analysisState.sessionId) return;

    const wsUrl = `${getWsBaseUrl()}/risk-analysis-v2/ws/${analysisState.sessionId}`;

    if (wsRef.current && wsRef.current.url === wsUrl && wsRef.current.readyState === WebSocket.OPEN) return;
    if (wsRef.current) wsRef.current.close();

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    let heartbeatInterval: NodeJS.Timeout;

    ws.onopen = () => {
      console.log('WS Connected');
      heartbeatInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send('ping');
      }, 10000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleWebSocketMessage(data);
      } catch (error) {
        console.error('WS Parse Error', error);
      }
    };

    ws.onclose = () => { if (heartbeatInterval) clearInterval(heartbeatInterval); };
    return () => { if (heartbeatInterval) clearInterval(heartbeatInterval); ws.close(); };
  }, [analysisState.sessionId, isRestoringSession]);

  const handleLoadHistorySession = async (sessionId: string) => {
    try {
      setHasRestoredOnce(false);
      setIsCreatingNewSession(false);
      window.location.href = `/risk-analysis?session_id=${sessionId}`;
    } catch (error) {
      console.error('加载历史任务失败:', error);
      message.error('加载历史任务失败');
    }
  };

  // ========== 用户操作 Handlers ==========
  const handleStartAnalysis = async () => {
    setIsCreatingNewSession(true);
    if (!userInput.trim() && uploadedFileIds.length === 0) {
      message.warning('请输入描述或上传文件');
      setIsCreatingNewSession(false);
      return;
    }

    setAnalysisState(prev => ({ ...prev, status: 'uploading' }));

    try {
      const createResponse = await api.post('/risk-analysis-v2/create-session', {
        upload_ids: uploadIds.length > 0 ? uploadIds : undefined,
        package_id: undefined,
        user_input: userInput
      });
      const session_id = createResponse.data.session_id;

      setAnalysisState(prev => ({
        ...prev, status: 'analyzing', sessionId: session_id, progress: 0, message: '正在进行文档预整理...',
        nodeProgress: { documentPreorganization: 'processing', multiModelAnalysis: 'pending', reportGeneration: 'pending' }
      }));
      setCurrentStep(1);

      await new Promise(resolve => setTimeout(resolve, 500));
      await api.post(`/risk-analysis-v2/start/${session_id}`, { stop_after_preorganization: true });
      message.success('开始文档预整理...');
    } catch (error: any) {
      message.error('启动失败');
      setAnalysisState(prev => ({ ...prev, status: 'idle' }));
    } finally {
      setTimeout(() => setIsCreatingNewSession(false), 1000);
    }
  };

  const handleSelectAnalysisMode = async (mode: 'single' | 'multi') => {
    try {
      setSelectedAnalysisMode(mode);
      setCurrentStep(3);
      setAnalysisState(prev => ({
        ...prev, status: 'analyzing', analysisMode: mode, message: mode === 'multi' ? '多模型分析中...' : '单模型分析中...',
        nodeProgress: { ...prev.nodeProgress!, multiModelAnalysis: 'processing' }
      }));

      await api.post(`/risk-analysis-v2/continue/${analysisState.sessionId}`, {
        analysis_mode: mode,
        selected_model: mode === 'single' ? 'Qwen3-235B-A22B-Thinking-2507' : undefined,
        package_id: selectedPackageIds[0],
        evaluation_stance: evaluationStance || undefined
      });
      message.success('已启动分析');
    } catch (error) {
      setCurrentStep(2);
      message.error('启动分析失败');
    }
  };

  const handleFileUpload = async (file: File) => {
    const uid = `${Date.now()}-${Math.random()}`;
    setUploadedFiles(prev => [...prev, { uid, name: file.name, status: 'uploading' }]);
    try {
      const fd = new FormData(); fd.append('files', file);
      const res = await api.post('/risk-analysis-v2/upload', fd);
      setUploadedFiles(prev => prev.map(f => f.uid === uid ? { ...f, status: 'done', response: res.data } : f));
      if (res.data.upload_id) setUploadIds(p => [...p, res.data.upload_id]);
      if (res.data.file_paths) setUploadedFileIds(p => [...p, ...res.data.file_paths]);
      return false;
    } catch (e) {
      setUploadedFiles(prev => prev.map(f => f.uid === uid ? { ...f, status: 'error' } : f));
      return false;
    }
  };

  const handleFileRemove = (file: any) => {
    setUploadedFiles(prev => prev.filter(f => f.uid !== file.uid));
    if (file.response?.upload_id) setUploadIds(p => p.filter(id => id !== file.response.upload_id));
    if (file.response?.file_paths) setUploadedFileIds(p => p.filter(path => !file.response.file_paths.includes(path)));
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (over && active.id !== over.id) {
      setSelectedPackageIds((items) => {
        const oldIndex = items.findIndex((id) => id === active.id);
        const newIndex = items.findIndex((id) => id === over.id);
        return arrayMove(items, oldIndex, newIndex);
      });
    }
  };

  const handleDownloadPreorganizationReport = async () => {
    try {
      const response = await api.get(`/risk-analysis-v2/preorganization-report/${analysisState.sessionId}`, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = `预整理报告.docx`;
      document.body.appendChild(link); link.click(); document.body.removeChild(link);
    } catch (e) { message.error('下载失败'); }
  };

  const handleDownloadRiskAnalysisReport = async () => {
    try {
      const response = await api.get(`/risk-analysis-v2/report/${analysisState.sessionId}`, { responseType: 'blob' });
      const blob = new Blob([response.data], { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a'); link.href = url; link.download = `风险分析报告.docx`;
      document.body.appendChild(link); link.click(); document.body.removeChild(link);
    } catch (e) { message.error('下载失败'); }
  };

  const renderNodeProgress = () => {
    const nodeProgress = analysisState.nodeProgress;
    const getNodeIcon = (status: NodeStatus) => {
      switch (status) {
        case 'pending': return <CloseCircleOutlined style={{ color: '#d9d9d9' }} />;
        case 'processing': return <LoadingOutlined style={{ color: '#1890ff' }} />;
        case 'completed': return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
        case 'failed': return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
      }
    };
    const nodes = [
      { key: 'documentPreorganization' as const, label: '文档预整理', description: '分类、质量评估、摘要生成' },
      { key: 'multiModelAnalysis' as const, label: '多模型分析', description: '并行分析 + 综合整合' },
      { key: 'reportGeneration' as const, label: '输出风险报告', description: '生成最终评估报告' }
    ];
    return (
      <Card title="分析进度" style={{ marginTop: 16 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {nodes.map(node => (
            <div key={node.key}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                {getNodeIcon(nodeProgress![node.key])}
                <Text strong style={{ marginLeft: 8 }}>{node.label}</Text>
              </div>
              <Text type="secondary" style={{ marginLeft: 32, fontSize: 12 }}>{node.description}</Text>
            </div>
          ))}
          <Divider />
          <Progress percent={Math.round(analysisState.progress)} status={analysisState.status === 'failed' ? 'exception' : 'active'} />
          <Text type="secondary">{analysisState.message}</Text>
        </Space>
      </Card>
    );
  };

  const renderInputPage = () => (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <Space direction="vertical" style={{ width: '100%' }} size="large">
        <ModuleKnowledgeToggle moduleName="risk_analysis" moduleLabel="风险评估" />
        <Card title="评估要求/背景情况说明">
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <TextArea
              rows={6}
              placeholder="请描述评估的具体要求、相关背景情况说明或需要特别关注的风险点..."
              value={userInput}
              onChange={(e) => setUserInput(e.target.value)}
            />
            <div>
              <Upload
                multiple
                fileList={uploadedFiles as any[]}
                beforeUpload={handleFileUpload}
                onRemove={handleFileRemove}
                disabled={analysisState.status === 'uploading'}
              >
                <Button icon={<UploadOutlined />} disabled={analysisState.status === 'uploading'}>
                  点击上传文件（支持拖拽）
                </Button>
              </Upload>
              {uploadedFiles.length > 0 && (
                <Alert
                  message={<Space><CheckCircleOutlined style={{ color: '#52c41a' }} /><span>已上传 {uploadedFiles.filter(f => f.status === 'done').length} / {uploadedFiles.length} 个文件</span></Space>}
                  type="success"
                  style={{ marginTop: 12 }}
                />
              )}
            </div>
          </Space>
        </Card>
        <Card style={{ textAlign: 'center', background: '#fafafa' }}>
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Button
              type="primary"
              size="large"
              icon={<SendOutlined />}
              onClick={handleStartAnalysis}
              loading={analysisState.status === 'uploading'}
              disabled={!userInput.trim() && uploadedFileIds.length === 0}
              style={{ width: '100%', height: 50, fontSize: 16 }}
            >
              开始资料预整理
            </Button>
            <Alert message="预整理说明" description="系统将对您上传的文档进行智能预整理，包括分类、摘要生成、关键信息提取等。" type="info" showIcon style={{ fontSize: 12 }} />
          </Space>
        </Card>
      </Space>
    </div>
  );

  const renderPreorganizationProgressPage = () => (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Card title="文档预整理中">
        <Space direction="vertical" size="large" style={{ width: '100%' }}>
          <div><Space>{analysisState.status === 'analyzing' && <LoadingOutlined spin />}<Text strong style={{ fontSize: 16 }}>{analysisState.message || '正在预整理文档...'}</Text></Space></div>
          <Progress percent={analysisState.progress} status={analysisState.status === 'analyzing' ? 'active' : 'success'} strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }} />
          <Alert message="预整理内容" description={<ul style={{ margin: 0, paddingLeft: 20 }}><li>分类与质量评估</li><li>关键信息提取</li><li>跨文档整合</li></ul>} type="info" showIcon />
        </Space>
      </Card>
    </div>
  );

  const renderPreorganizationConfirmPage = () => (
    <div style={{ maxWidth: 1200, margin: '0 auto' }}>
      <Space direction="vertical" style={{ width: '100%', marginBottom: 16 }}>
        <Alert message="文档预整理完成" description="请确认以下信息是否准确，可以选择修改后选择分析模式继续" type="info" showIcon />
        <div style={{ textAlign: 'right' }}><Button type="primary" icon={<DownloadOutlined />} onClick={handleDownloadPreorganizationReport}>下载预整理报告</Button></div>
      </Space>

      {enhancedAnalysis && (
        <Card title={<Space><FileTextOutlined /><span>增强分析结果</span><Tag color="purple">交易全景图</Tag></Space>} style={{ marginBottom: 16 }}>
          <EnhancedAnalysisDisplay enhancedAnalysis={enhancedAnalysis} />
        </Card>
      )}

      {preorganizationData?.basic && (
        <Card title="文档信息整理" style={{ marginBottom: 16 }}>
          {preorganizationData.basic.document_summaries && Object.keys(preorganizationData.basic.document_summaries).length > 0 ? (
            <div>
              {Object.entries(preorganizationData.basic.document_summaries).map(([path, summary]: [string, any], index: number) => (
                <Card key={path} type="inner" size="small" style={{ marginBottom: 16 }} title={<Space><Text strong style={{ fontSize: 14 }}>文档 {index + 1}：{summary.document_title || (summary.file_name || path.split('/').pop())}</Text>{summary.document_subtype && <Tag color="purple">{summary.document_subtype}</Tag>}</Space>}>
                  <Descriptions column={1} size="small">
                    {summary.document_purpose && <Descriptions.Item label="文档目的">{summary.document_purpose}</Descriptions.Item>}
                    <Descriptions.Item label="核心内容">{summary.summary}</Descriptions.Item>
                  </Descriptions>
                  
                  {/* 恢复：详细要素展示 (原版功能) */}
                  <div style={{ marginTop: 12 }}>
                    {summary.key_parties && summary.key_parties.length > 0 && <div style={{ marginBottom: 4 }}><Text type="secondary">主体：</Text><Text>{summary.key_parties.join('、')}</Text></div>}
                    {summary.key_dates && summary.key_dates.length > 0 && <div style={{ marginBottom: 4 }}><Text type="secondary">日期：</Text><Text>{summary.key_dates.join('； ')}</Text></div>}
                    {summary.key_amounts && summary.key_amounts.length > 0 && <div style={{ marginBottom: 4 }}><Text type="secondary">金额：</Text><Text>{summary.key_amounts.join('； ')}</Text></div>}
                  </div>

                  {summary.risk_signals && summary.risk_signals.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Text type="secondary" strong>风险信号：</Text>
                      <div style={{ marginTop: 4 }}>
                        {summary.risk_signals.map((signal: string, i: number) => (
                          <Tag key={i} color="orange" style={{ marginBottom: 4 }}>{signal}</Tag>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ) : (<div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>暂无详细文档摘要</div>)}
        </Card>
      )}

      <Card title="选择规则包（可选）" style={{ marginBottom: 16 }}>
        <RiskPackageSelector value={selectedPackageIds} onChange={setSelectedPackageIds} onPackagesLoad={setAllPackages} />
        {selectedPackages.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <div style={{ marginBottom: 12 }}><Text strong>已选规则包排序</Text></div>
            <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
              <SortableContext items={selectedPackageIds} strategy={verticalListSortingStrategy}>
                {selectedPackages.map((pkg, index) => <SortableItem key={pkg.package_id} id={pkg.package_id} pkg={pkg} index={index} />)}
              </SortableContext>
            </DndContext>
          </div>
        )}
      </Card>

      <Card title="选择分析模式">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Radio.Group
            value={selectedAnalysisMode}
            onChange={e => setSelectedAnalysisMode(e.target.value)}
            defaultValue="multi"
          >
            <Radio value="multi">多模型并行分析 (推荐)</Radio>
            <Radio value="single">单模型快速分析</Radio>
          </Radio.Group>

          <Alert
            message={
              selectedAnalysisMode === 'multi'
                ? "DeepSeek + GPT + Qwen 多视角联合评估"
                : "快速响应，适合简单合规检查"
            }
            type="info"
            showIcon
            style={{ marginTop: 8 }}
          />

          <div>
            <label style={{ display: 'block', marginBottom: '8px', fontWeight: 500 }}>风险评估立场（可选）</label>
            <Input.TextArea placeholder="请输入您的立场..." value={evaluationStance} onChange={(e) => setEvaluationStance(e.target.value)} rows={2} />
          </div>

          <div style={{ textAlign: 'right', marginTop: 16 }}>
            <Button
              type="primary"
              size="large"
              icon={<SendOutlined />}
              onClick={() => handleSelectAnalysisMode(selectedAnalysisMode || 'multi')}
              disabled={!selectedAnalysisMode}
            >
              启动分析
            </Button>
          </div>
        </Space>
      </Card>
    </div>
  );

  const renderAnalysisProgressPage = () => {
    const isMultiModel = (analysisState.analysisMode || selectedAnalysisMode) === 'multi';
    return (
      <div style={{ maxWidth: 800, margin: '0 auto' }}>
        <Card title={isMultiModel ? '多模型并行分析中' : '单模型分析中'}>
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <div><Space>{analysisState.status === 'analyzing' && <LoadingOutlined spin />}<Text strong style={{ fontSize: 16 }}>{analysisState.message}</Text></Space></div>
            <Progress percent={analysisState.progress} status="active" strokeColor={{ '0%': '#108ee9', '100%': '#87d068' }} />
            {renderNodeProgress()}
            {analysisState.comparison && isMultiModel && (
              <Card title="多模型实时对比" style={{ marginTop: 16 }}><MultiModelComparison data={analysisState.comparison} /></Card>
            )}
          </Space>
        </Card>
      </div>
    );
  };

  const renderResultsPage = () => (
    <div>
      <Card title="风险评估报告" extra={<Space><Button type="primary" icon={<DownloadOutlined />} onClick={handleDownloadRiskAnalysisReport}>下载报告</Button><Button onClick={() => navigate('/')}>返回首页</Button></Space>}>
        {analysisState.report && <ReportResultsDisplay report={analysisState.report} />}
      </Card>
      {analysisState.diagrams && analysisState.diagrams.length > 0 && (
        <Card title="相关图表" style={{ marginTop: 16 }}>
          <DiagramViewer diagrams={analysisState.diagrams as any} />
        </Card>
      )}
      {analysisState.comparison && (
        <Card title="多模型分析对比" style={{ marginTop: 16 }}><MultiModelComparison data={analysisState.comparison} /></Card>
      )}
    </div>
  );

  return (
    <Layout style={{ minHeight: '100vh', background: '#f0f2f5' }}>
      <EnhancedModuleNavBar currentModuleKey="risk-analysis" title="风险评估" icon={<SafetyOutlined />} extra={<RiskAnalysisHistoryButton count={unreadCount} onClick={() => setHistoryVisible(true)} />} />
      <Content style={{ padding: '24px' }}>
        <div style={{ maxWidth: 1400, margin: '0 auto' }}>
          <Card style={{ marginBottom: 16 }}>
            <Steps current={currentStep} items={[{ title: '输入信息' }, { title: '文档预整理' }, { title: '确认信息' }, { title: 'AI 分析' }, { title: '查看结果' }]} />
          </Card>
          <div style={{ background: '#fff', padding: 24, borderRadius: 8, minHeight: 600 }}>
            {isRestoringSession ? (
              <div style={{ textAlign: 'center', padding: '100px 0' }}><LoadingOutlined style={{ fontSize: 48, color: '#1890ff', marginBottom: 16 }} /><Title level={3}>正在恢复会话...</Title></div>
            ) : (
              <>
                {currentStep === 0 && renderInputPage()}
                {currentStep === 1 && renderPreorganizationProgressPage()}
                {currentStep === 2 && renderPreorganizationConfirmPage()}
                {currentStep === 3 && renderAnalysisProgressPage()}
                {currentStep === 4 && renderResultsPage()}
              </>
            )}
          </div>
        </div>
      </Content>
      <RiskAnalysisHistorySidebar visible={historyVisible} onClose={() => setHistoryVisible(false)} onLoadSession={handleLoadHistorySession} />
    </Layout>
  );
};

export default RiskAnalysisPageV2;