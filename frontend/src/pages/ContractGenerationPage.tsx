// frontend/src/pages/ContractGenerationPage.tsx
/**
 * 合同生成页面
 *
 * 功能：
 * 1. 用户输入需求描述
 * 2. 上传相关文件（可选）
 * 3. AI 分析需求并确定处理类型
 * 4. 生成合同文档
 * 5. 预览和下载生成的文档
 */
import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Button,
  Card,
  Typography,
  Input,
  Upload,
  message,
  Space,
  Steps,
  Tag,
  Modal,
  Form,
  Select,
  Divider,
  Alert,
  Spin,
  Radio,
  Checkbox,
  Descriptions,
  Table,
  Tabs,
  List,
  Tooltip
} from 'antd';
import {
  SendOutlined,
  UploadOutlined,
  FileTextOutlined,
  DownloadOutlined,
  EyeOutlined,
  CheckCircleOutlined,
  PlusOutlined,
  InfoCircleOutlined,
  FileOutlined,
  EditOutlined,
  SyncOutlined,
  HistoryOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
  CloseCircleOutlined
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import ReactMarkdown from 'react-markdown'; // 新增：引入 Markdown 渲染
import remarkGfm from 'remark-gfm'; // 新增：支持表格等 GFM 语法
import { DocumentEditor } from "@onlyoffice/document-editor-react"; // 新增：OnlyOffice 文档预览
import ModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar'; // 新增：统一导航栏组件
import api from '../api';
import { useSessionPersistence } from '../hooks/useSessionPersistence';
import { taskWebSocketService, getWebSocketStatus } from '../services/websocketService'; // 新增：WebSocket 服务
import type {
  ContractGenerationAnalyzeResponse,
  GeneratedContract,
  ClarificationFormResponse,
  ClarificationFormField,
  ContractGenerationTaskResponse, // 新增：联合类型
  ContractGenerationCeleryResponse, // 新增：Celery 响应
  ContractGenerationSyncResponse // 新增：Sync 响应
} from '../types';
import type { TaskProgress } from '../types/task'; // 新增：任务进度类型
import { Progress } from 'antd'; // 新增：进度条组件
import './ContractGenerationPage.css';

const { Title, Text, Paragraph } = Typography;
const { Step } = Steps;
const { TextArea } = Input;
const { Dragger } = Upload;
const { Option } = Select;

// 处理类型标签映射
const PROCESSING_TYPE_LABELS: Record<string, { label: string; color: string; description: string }> = {
  'contract_modification': {
    label: '合同变更',
    color: 'blue',
    description: '基于原合同生成变更协议'
  },
  'contract_termination': {
    label: '合同解除',
    color: 'orange',
    description: '基于原合同生成解除协议'
  },
  'single_contract': {
    label: '单一合同',
    color: 'green',
    description: '生成一份新合同'
  },
  'contract_planning': {
    label: '合同规划',
    color: 'purple',
    description: '复杂交易需要多份合同'
  }
};

const ContractGenerationPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [form] = Form.useForm();

  // ========== 会话持久化 ==========
  // 定义会话数据类型
  interface ContractGenerationSessionData {
    step: number;
    userInput: string;
    uploadedFiles: string[]; // 文件名列表
    clarificationFormResponse: ClarificationFormResponse | null;
    clarificationFormData: Record<string, any>;
    planningModeSelectionVisible: boolean;
    planningModeOptions: any;
    selectedPlanningMode: 'multi_model' | 'single_model' | null;
    generatedContracts: GeneratedContract[];
    editableContent: string;
    selectedContractFilename: string | null;
  }

  // 使用 ref 来追踪是否已经恢复过会话，避免重复恢复
  const hasRestoredRef = useRef(false);
  const isRestoringRef = useRef(false);
  // 【新增】追踪 Step 2 是否已经开始提取（避免重复提取）
  const step2ExtractionStartedRef = useRef(false);

  const {
    hasSession,
    saveSession,
    clearSession,
    isLoading: isRestoringSession
  } = useSessionPersistence<ContractGenerationSessionData>('contract_generation_session', {
    expirationTime: 2 * 60 * 60 * 1000, // 2小时
    autoRestore: false, // 禁用自动恢复，手动控制恢复时机
    onRestore: (sessionId, data) => {
      console.log('[合同生成] 恢复会话:', data);
      isRestoringRef.current = true;

      setCurrentStep(data.step);
      setUserInput(data.userInput || '');
      setClarificationFormResponse(data.clarificationFormResponse);
      setClarificationFormData(data.clarificationFormData || {});
      setPlanningModeSelectionVisible(data.planningModeSelectionVisible || false);
      setPlanningModeOptions(data.planningModeOptions);
      setSelectedPlanningMode(data.selectedPlanningMode);
      setGeneratedContracts(data.generatedContracts || []);
      setEditableContent(data.editableContent || '');

      // 恢复选中的合同
      if (data.selectedContractFilename && data.generatedContracts && data.generatedContracts.length > 0) {
        const contract = data.generatedContracts.find((c: GeneratedContract) => c.filename === data.selectedContractFilename);
        if (contract) {
          setSelectedContract(contract);
        }
      }

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
      console.log('[合同生成] 正在恢复会话，跳过保存');
      return;
    }

    saveSession(Date.now().toString(), {
      step: currentStep,
      userInput,
      uploadedFiles: uploadedFiles.map(f => {
        if (typeof f === 'string') return f;
        if (f.name) return f.name;
        if (f.originFileObj?.name) return f.originFileObj.name;
        return f.uid || String(f);
      }),
      clarificationFormResponse,
      clarificationFormData,
      planningModeSelectionVisible,
      planningModeOptions,
      selectedPlanningMode,
      generatedContracts,
      editableContent,
      selectedContractFilename: selectedContract?.filename || null
    });
  };
  // ========== 会话持久化结束 ==========

  // 状态管理
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [userInput, setUserInput] = useState<string>('');
  const [uploadedFiles, setUploadedFiles] = useState<any[]>([]);
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [analyzingResult, setAnalyzingResult] = useState<ContractGenerationAnalyzeResponse | null>(null);
  const [generating, setGenerating] = useState<boolean>(false);
  const [generatedContracts, setGeneratedContracts] = useState<GeneratedContract[]>([]);
  const [sessionId, setSessionId] = useState<string>('');
  const [outputFormat, setOutputFormat] = useState<'docx' | 'pdf'>('docx');

  // 【新增状态】需求澄清表单相关
  const [clarificationFormResponse, setClarificationFormResponse] = useState<ClarificationFormResponse | null>(null);
  const [clarificationFormData, setClarificationFormData] = useState<Record<string, any>>({});
  const [useTemplate, setUseTemplate] = useState<boolean>(true); // 是否使用模板
  const [templatePreviewVisible, setTemplatePreviewVisible] = useState<boolean>(false);
  const [templatePreviewContent, setTemplatePreviewContent] = useState<any>(null);
  const [loadingTemplatePreview, setLoadingTemplatePreview] = useState<boolean>(false);

  // 【新增状态】：合同规划模式选择相关
  const [planningModeSelectionVisible, setPlanningModeSelectionVisible] = useState<boolean>(false);
  const [planningModeOptions, setPlanningModeOptions] = useState<any>(null);
  const [selectedPlanningMode, setSelectedPlanningMode] = useState<'multi_model' | 'single_model' | null>(null);

  // 澄清问题 Modal (已弃用，保留以避免错误)
  const [clarificationModalVisible, setClarificationModalVisible] = useState<boolean>(false);
  const [clarificationAnswers, setClarificationAnswers] = useState<Record<string, string>>({});
  const [clarificationForm] = Form.useForm();

  // 确认并生成文件 loading 状态
  const [generatingFiles, setGeneratingFiles] = useState<Record<number, boolean>>({});

  // 【新增状态】：用于存储当前正在编辑的文本内容，实现双向绑定
  const [editableContent, setEditableContent] = useState<string>('');
  const [selectedContract, setSelectedContract] = useState<GeneratedContract | null>(null);

  // 【新增状态】：OnlyOffice 文档预览配置
  const [onlyOfficeConfig, setOnlyOfficeConfig] = useState<any>(null);
  const [loadingOnlyOfficeConfig, setLoadingOnlyOfficeConfig] = useState<boolean>(false);

  // 【新增状态】：Celery 任务追踪相关
  const [taskId, setTaskId] = useState<string | null>(null);
  const [taskProgress, setTaskProgress] = useState<TaskProgress | null>(null);
  const [taskStatus, setTaskStatus] = useState<'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'>('pending');
  const [isWebSocketConnected, setIsWebSocketConnected] = useState<boolean>(false);

  // 【新增状态】：合同规划流程相关
  const [contractPlanResult, setContractPlanResult] = useState<any | null>(null); // 存储规划结果
  const [planGenerationLoading, setPlanGenerationLoading] = useState<boolean>(false); // 规划生成中

  // 【新增状态】：Step 2 LLM 提取变更/解除信息相关
  const [extractingModificationTerminationInfo, setExtractingModificationTerminationInfo] = useState<boolean>(false); // 提取中
  const [extractedInfo, setExtractedInfo] = useState<any | null>(null); // 存储提取的信息

  // 【新增状态】：历史任务记录相关
  const [activeTab, setActiveTab] = useState<string>('new'); // 当前激活的标签页
  const [historyTasks, setHistoryTasks] = useState<any[]>([]); // 历史任务列表
  const [loadingHistory, setLoadingHistory] = useState<boolean>(false); // 加载历史任务中
  const [historyTotal, setHistoryTotal] = useState<number>(0); // 历史任务总数

  // ✅ 修复：将 useMemo 移至组件顶层，遵守 React Hook 规则
  // 数据适配：将 questions 格式转换为 sections 格式
  const normalizedClarificationForm = useMemo(() => {
    if (!clarificationFormResponse?.clarification_form) {
      return null;
    }

    const form = clarificationFormResponse.clarification_form;

    // 如果已经有 sections，直接返回（旧格式或已处理）
    if (form.sections && form.sections.length > 0) {
      return form;
    }

    // 如果有 questions，转换为 sections（新格式适配）
    if (form.questions && form.questions.length > 0) {
      return {
        ...form,
        sections: [{
          section_id: 'main',
          section_title: '需求澄清',
          fields: form.questions.map(q => ({
            field_id: q.id,
            field_type: q.type,
            label: q.question,
            required: q.required,
            placeholder: q.placeholder || `请输入${q.question}`,
            default_value: q.default,
            options: q.options,
            validation_rules: {}
          }))
        }]
      };
    }

    return form;
  }, [clarificationFormResponse]);

  // 【新增 Effect】：当生成的合同列表变化时，自动选中第一个并初始化编辑内容
  useEffect(() => {
    if (generatedContracts.length > 0 && !selectedContract) {
      const firstContract = generatedContracts[0];
      setSelectedContract(firstContract);
      setEditableContent(firstContract.content || '');
    }
  }, [generatedContracts]);

  // 手动控制会话恢复（仅在组件首次挂载时执行一次）
  useEffect(() => {
    // 如果已经恢复过，或者正在恢复，则跳过
    if (hasRestoredRef.current || isRestoringRef.current) {
      return;
    }

    // 检查是否有可恢复的会话
    if (hasSession) {
      console.log('[合同生成] 检测到会话，准备恢复');
      isRestoringRef.current = true;

      // 获取存储的会话数据
      const storedData = localStorage.getItem('contract_generation_session');
      if (storedData) {
        try {
          const session = JSON.parse(storedData);
          if (session.data) {
            // 直接恢复状态
            setCurrentStep(session.data.step || 0);
            setUserInput(session.data.userInput || '');
            setClarificationFormResponse(session.data.clarificationFormResponse);
            setClarificationFormData(session.data.clarificationFormData || {});
            setPlanningModeSelectionVisible(session.data.planningModeSelectionVisible || false);
            setPlanningModeOptions(session.data.planningModeOptions);
            setSelectedPlanningMode(session.data.selectedPlanningMode);
            setGeneratedContracts(session.data.generatedContracts || []);
            setEditableContent(session.data.editableContent || '');

            // 恢复选中的合同
            if (session.data.selectedContractFilename && session.data.generatedContracts && session.data.generatedContracts.length > 0) {
              const contract = session.data.generatedContracts.find((c: GeneratedContract) => c.filename === session.data.selectedContractFilename);
              if (contract) {
                setSelectedContract(contract);
              }
            }

            // 显示恢复消息（只显示一次）
            message.success('已恢复之前的合同生成会话');

            // 标记恢复完成
            setTimeout(() => {
              hasRestoredRef.current = true;
              isRestoringRef.current = false;
            }, 100);
          }
        } catch (error) {
          console.error('[合同生成] 恢复会话失败:', error);
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

  // ========== 智能引导上下文穿透 ==========
  useEffect(() => {
    // 从智能引导页面传递过来的参数
    const state = location.state as { user_requirement?: string } | null;
    if (state?.user_requirement) {
      setUserInput(state.user_requirement);
      message.success('已根据您的需求自动填充内容');
    }
  }, [location.state]);

  // 【新增 Effect】：Step 2 自动提取变更/解除信息
  useEffect(() => {
    const processingType = clarificationFormResponse?.processing_type;

    console.log('[Step 2 Extraction Effect] 触发检查:', {
      currentStep,
      hasClarificationFormResponse: !!clarificationFormResponse,
      processingType: processingType,
      hasExtractedInfo: !!extractedInfo,
      extractionStarted: step2ExtractionStartedRef.current
    });

    // 只在 Step 2 (确认阶段) 时触发
    if (currentStep !== 1 || !clarificationFormResponse) {
      console.log('[Step 2 Extraction Effect] 跳过：不满足触发条件');
      // 重置提取标记（返回 Step 1 时）
      if (currentStep !== 1) {
        step2ExtractionStartedRef.current = false;
      }
      return;
    }

    // 只处理合同变更/解除场景
    if (processingType !== 'contract_modification' && processingType !== 'contract_termination') {
      console.log('[Step 2 Extraction Effect] 跳过：不是变更/解除场景');
      return;
    }

    // 【新增】防止重复提取：如果已经提取过且有结果，跳过
    if (step2ExtractionStartedRef.current && extractedInfo) {
      console.log('[Step 2 Extraction Effect] 跳过：已经提取过');
      return;
    }

    // 【修改】始终在 Step 2 调用 LLM 提取（即使用户之前可能已经提取过）
    // 因为用户的需求是："第二步应该需要一个LLM节点，从用户输入信息中提取核心内容"
    // 这样可以确保 Step 2 是一个独立的 LLM 节点，让用户看到提取过程

    // 开始提取信息
    const extractInfo = async () => {
      console.log('[Step 2] 检测到合同变更/解除场景，开始 LLM 提取信息');
      step2ExtractionStartedRef.current = true; // 标记开始提取
      setExtractingModificationTerminationInfo(true);

      try {
        const response = await api.extractModificationTerminationInfo({
          user_input: userInput,
          analysis_result: clarificationFormResponse // 使用 clarificationFormResponse
        });

        if (response.data && response.data.success) {
          console.log('[Step 2] LLM 提取成功:', response.data.extracted_info);
          setExtractedInfo(response.data.extracted_info);

          // 将提取的信息附加到 clarificationFormResponse 中
          setClarificationFormResponse({
            ...clarificationFormResponse,
            extracted_modification_termination_info: response.data.extracted_info
          });

          message.success('AI 已提取相关信息，请确认');
        } else {
          console.error('[Step 2] LLM 提取失败:', response.data);
          message.error('信息提取失败，请刷新重试');
          step2ExtractionStartedRef.current = false; // 失败时重置，允许重试
        }
      } catch (error) {
        console.error('[Step 2] LLM 提取异常:', error);
        message.error('信息提取异常，请刷新重试');
        step2ExtractionStartedRef.current = false; // 失败时重置，允许重试
      } finally {
        setExtractingModificationTerminationInfo(false);
      }
    };

    extractInfo();
  }, [currentStep, clarificationFormResponse, userInput]); // 移除 analyzingResult 依赖

  // 【修改】监听关键状态变化，自动保存会话
  useEffect(() => {
    // 只在恢复完成后才保存会话
    if (hasRestoredRef.current && !isRestoringRef.current && !isRestoringSession) {
      if (currentStep > 0 || userInput.trim() || clarificationFormResponse || generatedContracts.length > 0) {
        saveCurrentState();
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, userInput, clarificationFormResponse, clarificationFormData, generatedContracts, editableContent, selectedContract]);
  // 【会话持久化结束】

  // 【新增 Effect】：保存 Celery 任务状态到 sessionStorage
  useEffect(() => {
    if (taskId && taskStatus !== 'pending') {
      const sessionData = {
        taskId,
        taskStatus,
        taskProgress,
        generatedContracts,
        clarificationFormResponse,
        userInput,
        timestamp: Date.now()
      };
      sessionStorage.setItem('contract_gen_task', JSON.stringify(sessionData));
    }
  }, [taskId, taskStatus, taskProgress, generatedContracts]);

  // 【新增 Effect】：组件挂载时恢复 Celery 任务状态
  useEffect(() => {
    const saved = sessionStorage.getItem('contract_gen_task');
    if (saved && !hasRestoredRef.current) {
      try {
        const data = JSON.parse(saved);
        // 检查是否在 2 小时内
        const TWO_HOURS = 2 * 60 * 60 * 1000;
        if (Date.now() - data.timestamp < TWO_HOURS) {
          // 【修复】根据任务状态决定是否恢复
          if (data.taskStatus === 'processing') {
            // ✅ 处理中的任务 → 恢复并继续监听
            setTaskId(data.taskId);
            setTaskStatus(data.taskStatus);
            setTaskProgress(data.taskProgress);
            setClarificationFormResponse(data.clarificationFormResponse);
            setUserInput(data.userInput);

            // 重新连接 WebSocket 继续监听
            setCurrentStep(1); // 回到确认步骤，显示进度
            startTaskMonitoring(data.taskId);
            message.info('检测到进行中的任务，正在恢复...');
            hasRestoredRef.current = true;

          } else if (data.taskStatus === 'completed') {
            // ⏸️ 已完成的任务 → 保留在 sessionStorage 作为历史记录，清除当前状态
            // 这样可以让用户从空白开始创建新任务，同时保留历史记录
            console.log('[SessionRestore] 检测到已完成的任务，保留作为历史记录:', data.taskId);
            hasRestoredRef.current = true;
            // ⚠️ 清除旧状态，避免影响新任务
            setTaskId(null);
            setTaskStatus('pending');
            setTaskProgress(undefined);
            setGeneratedContracts([]);
            setClarificationFormResponse(null);
            setSelectedContract(null);
            setEditableContent('');

          } else {
            // ❌ 失败/取消的任务 → 清除缓存
            console.log('[SessionRestore] 清除失败/取消的任务缓存:', data.taskStatus);
            sessionStorage.removeItem('contract_gen_task');
          }
        } else {
          // 过期的会话数据，清除
          sessionStorage.removeItem('contract_gen_task');
        }
      } catch (error) {
        console.error('恢复 Celery 任务会话失败:', error);
        sessionStorage.removeItem('contract_gen_task');
      }
    }
  }, []); // 只在挂载时执行一次

  // 【新增 Effect】：任务失败后清除 sessionStorage（已完成的任务保留作为历史记录）
  useEffect(() => {
    if (taskStatus === 'failed' || taskStatus === 'cancelled') {
      // 失败或取消的任务清除缓存
      const timer = setTimeout(() => {
        sessionStorage.removeItem('contract_gen_task');
        console.log('[SessionRestore] 已清除失败/取消任务的缓存');
      }, 5000);
      return () => clearTimeout(timer);
    }
    // ✅ 已完成的任务保留在 sessionStorage 中，作为历史记录
  }, [taskStatus]);

  // 【新增 Effect】：当切换到历史记录标签时，获取历史任务列表
  useEffect(() => {
    if (activeTab === 'history') {
      fetchHistoryTasks();
    }
  }, [activeTab]);

  // 【新增方法】：处理合同切换
  const handleContractChange = (filename: string) => {
    const contract = generatedContracts.find(c => c.filename === filename);
    if (contract) {
      setSelectedContract(contract);
      setEditableContent(contract.content || '');
      // 重置 OnlyOffice 配置，稍后重新加载
      setOnlyOfficeConfig(null);
      // 如果文件已生成，加载 OnlyOffice 配置
      if (contract.file_generated) {
        loadOnlyOfficeConfig(contract.filename);
      }
    }
  };

  // 【新增方法】：加载 OnlyOffice 配置
  const loadOnlyOfficeConfig = async (filename: string) => {
    setLoadingOnlyOfficeConfig(true);
    try {
      // 提取不含扩展名的文件名
      const baseFilename = filename.replace(/\.(docx|pdf)$/i, '');
      const docxFilename = `${baseFilename}.docx`;

      const response = await api.getDocumentPreviewConfig(docxFilename);
      const result = response.data;

      if (result.config && result.token) {
        setOnlyOfficeConfig({
          ...result.config,
          token: result.token
        });
      } else {
        message.warning('无法加载文档预览配置');
      }
    } catch (error: any) {
      console.error('加载 OnlyOffice 配置失败:', error);
      message.error('加载文档预览失败');
    } finally {
      setLoadingOnlyOfficeConfig(false);
    }
  };

  // 文件上传配置
  const fileUploadProps = {
    name: 'files',
    multiple: true,
    fileList: uploadedFiles,
    accept: '.docx,.doc,.pdf,.png,.jpg,.jpeg',
    beforeUpload: (file: File) => {
      const isValidType = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'image/png',
        'image/jpeg'
      ].includes(file.type);

      if (!isValidType) {
        message.error('只支持上传 Word、PDF、图片文件');
        return Upload.LIST_IGNORE;
      }

      const isValidSize = file.size <= 50 * 1024 * 1024; // 50MB
      if (!isValidSize) {
        message.error('文件大小不能超过 50MB');
        return Upload.LIST_IGNORE;
      }

      return false; // 阻止自动上传
    },
    onChange: (info: any) => {
      setUploadedFiles(info.fileList);
    },
    onRemove: (file: any) => {
      const index = uploadedFiles.indexOf(file);
      const newFileList = uploadedFiles.slice();
      newFileList.splice(index, 1);
      setUploadedFiles(newFileList);
    }
  };

  // 【新增】：获取历史任务列表
  const fetchHistoryTasks = async () => {
    setLoadingHistory(true);
    try {
      const response = await api.getContractGenerationTasks({
        skip: 0,
        limit: 20
      });
      setHistoryTasks(response.data.tasks || []);
      setHistoryTotal(response.data.total || 0);
    } catch (error) {
      console.error('获取历史任务失败:', error);
      message.error('获取历史任务失败');
    } finally {
      setLoadingHistory(false);
    }
  };

  // 第一步：分析需求并获取澄清表单
  const handleAnalyzeRequirement = async (planningMode?: 'multi_model' | 'single_model') => {
    if (!userInput.trim()) {
      message.warning('请输入您的需求描述');
      return;
    }

    setAnalyzing(true);
    try {
      // 构建请求数据，只包含有值的字段
      // 安全地提取文件名列表，避免循环引用问题
      const uploadedFileNames: string[] = [];

      if (uploadedFiles && Array.isArray(uploadedFiles)) {
        for (const f of uploadedFiles) {
          if (!f) continue;

          // Ant Design Upload 组件的文件对象结构
          // 尝试多种可能的文件名字段
          let fileName: string | null = null;

          if (typeof f === 'string') {
            fileName = f;
          } else if (typeof f === 'object') {
            // 尝试从不同字段获取文件名
            if (f.name && typeof f.name === 'string') {
              fileName = f.name;
            } else if (f.originFileObj && f.originFileObj.name && typeof f.originFileObj.name === 'string') {
              fileName = f.originFileObj.name;
            } else if (f.response && f.response.filename && typeof f.response.filename === 'string') {
              fileName = f.response.filename;
            }
          }

          // 只添加有效的文件名
          if (fileName && fileName !== 'undefined' && fileName !== '[object Object]') {
            uploadedFileNames.push(fileName);
          }
        }
      }

      const requestData: any = {
        user_input: userInput
      };

      // 只有当有上传文件时才添加 uploaded_files
      if (uploadedFileNames.length > 0) {
        requestData.uploaded_files = uploadedFileNames;
      }

      // 只有当 planning_mode 有值时才添加
      if (planningMode) {
        requestData.planning_mode = planningMode;
      }

      // 调用新的 API：分析并获取澄清表单
      const response = await api.analyzeAndGetClarificationForm(requestData);

      const result = response.data;

      if (result.success) {
        // 检查是否需要用户选择规划模式
        if (result.requires_user_choice && result.user_choice_options) {
          // 显示规划模式选择界面
          setClarificationFormResponse(result);
          setPlanningModeOptions(result.user_choice_options);
          setPlanningModeSelectionVisible(true);
          setCurrentStep(1); // 进入第二步，但显示模式选择
          message.info('检测到您的需求属于合同规划场景，请选择生成模式');
        } else {
          // 正常的单一合同生成流程
          setClarificationFormResponse(result);
          setPlanningModeSelectionVisible(false);
          setCurrentStep(1); // 进入第二步：显示匹配情况和澄清表单
          message.success('需求分析完成');
        }
      } else {
        message.error(result.error || '需求分析失败');
      }
    } catch (error: any) {
      console.error('需求分析失败:', error);
      message.error(error.response?.data?.detail || '需求分析失败，请重试');
    } finally {
      setAnalyzing(false);
    }
  };

  // 第二步：回答澄清问题后继续
  const handleClarificationSubmit = async () => {
    try {
      // 不再验证必填，直接获取已填写的值
      const values = clarificationForm.getFieldsValue();
      setClarificationAnswers(values);
      setClarificationModalVisible(false);
      // 保持在确认步骤（Step 1），让用户点击"确认并生成"按钮
    } catch (error) {
      console.error('处理失败:', error);
    }
  };

  // 【新增函数】：启动任务监听（WebSocket 连接）
  const startTaskMonitoring = async (taskId: string) => {
    // 修复：始终使用用户的 JWT token（accessToken），而不是后端返回的随机 UUID task_token
    const token = localStorage.getItem('accessToken') || localStorage.getItem('token') || '';

    if (!token) {
      console.error('[WebSocket] 未找到用户 token');
      message.error('未找到登录凭证，请重新登录');
      return;
    }

    // 【修复】检查是否已经连接到相同的任务
    const currentStatus = getWebSocketStatus();
    if (currentStatus.isConnected && currentStatus.taskId === taskId) {
      console.log('[WebSocket] 已连接到任务，无需重连:', taskId);
      return;
    }

    // 【修复】断开旧连接
    if (currentStatus.isConnected) {
      console.log('[WebSocket] 断开旧连接，连接到新任务:', taskId);
      taskWebSocketService.disconnect();
    }

    // 【新增】统一的状态更新函数，避免竞态条件
    const updateTaskState = (progress: TaskProgress) => {
      console.log('[WebSocket] 进度更新:', progress.progress, '%');
      // 原子性更新所有相关状态
      setTaskProgress(progress);
      setTaskStatus(progress.status);

      // 根据状态更新连接状态
      const isActive = progress.status !== 'completed' &&
                       progress.status !== 'failed' &&
                       progress.status !== 'cancelled';
      setIsWebSocketConnected(isActive);
    };

    try {
      await taskWebSocketService.connect(taskId, token, {
        onConnected: () => {
          console.log('[WebSocket] 连接成功');
          setIsWebSocketConnected(true);
          setTaskStatus('processing');
        },
        onProgress: updateTaskState,
        onCompleted: (result: any) => {
          console.log('[WebSocket] ===== onCompleted 回调被调用 =====');
          console.log('[WebSocket] result 参数:', result);
          console.log('[WebSocket] result.contracts:', result?.contracts);
          console.log('[WebSocket] result.contracts 是数组?:', Array.isArray(result?.contracts));

          setIsWebSocketConnected(false);
          setTaskStatus('completed');

          // 解析结果
          if (result?.contracts && Array.isArray(result.contracts)) {
            console.log('[WebSocket] ✅ contracts 存在且是数组，长度:', result.contracts.length);
            console.log('[WebSocket] 第一个合同:', result.contracts[0]);

            setGeneratedContracts(result.contracts);
            if (result.contracts.length > 0) {
              const firstContract = result.contracts[0];
              setSelectedContract(firstContract);
              setEditableContent(firstContract.content || '');
              console.log('[WebSocket] 已设置 editableContent:', firstContract.content?.substring(0, 100));
            }
            setCurrentStep(2);
            console.log('[WebSocket] 已设置 currentStep = 2');
            message.success(`成功生成 ${result.contracts.length} 份合同`);
          } else {
            console.error('[WebSocket] ❌ result.contracts 不存在或不是数组');
            message.error('任务完成但未返回有效结果');
          }
        },
        onError: (error: string) => {
          console.error('[WebSocket] 错误:', error);
          setIsWebSocketConnected(false);
          setTaskStatus('failed');
          message.error(error || '任务执行失败');
        },
        onDisconnected: () => {
          setIsWebSocketConnected(false);
          console.log('[WebSocket] 连接已断开');
        }
      });
    } catch (error) {
      console.error('[WebSocket] 连接失败:', error);
      setTaskStatus('failed');
      message.error('WebSocket 连接失败，请刷新页面重试');
    }
  };

  // 第二步：使用表单数据生成合同（支持模板/非模板两种路径，支持 Celery/Sync 双模式）
  const handleGenerateContract = async (useTemplateMode: boolean = true) => {
    if (!clarificationFormResponse) {
      message.error('缺少分析结果');
      return;
    }

    // 【修复】清除旧的 sessionStorage，避免使用旧任务 ID
    sessionStorage.removeItem('contract_gen_task');

    setGenerating(true);
    try {
      let response: any;

      if (useTemplateMode) {
        // 使用模板生成：调用新 API
        response = await api.generateContractWithFormData({
          user_input: userInput,
          form_data: clarificationFormData,
          analysis_result: clarificationFormResponse.analysis_result,
          template_match_result: clarificationFormResponse.template_match_result,
          knowledge_graph_features: clarificationFormResponse.knowledge_graph_features,
          planning_mode: 'single_model'  // 【修复】使用模板时使用 single_model
        });
      } else {
        // 不使用模板：调用新 API，使用 multi_model（两阶段生成）
        response = await api.generateContractWithFormData({
          user_input: userInput,
          form_data: clarificationFormData,
          analysis_result: clarificationFormResponse.analysis_result,
          template_match_result: clarificationFormResponse.template_match_result,
          knowledge_graph_features: clarificationFormResponse.knowledge_graph_features,
          planning_mode: 'multi_model',  // 【修复】不用模板时使用 multi_model（两阶段生成）
          skip_template: true  // 【新增】明确跳过模板匹配
        });

        // 【旧代码已删除】之前调用的 api.generateContract(formData) 不支持 planning_mode 参数
      }

      const result = response.data as ContractGenerationTaskResponse;

      // ✨ 新增：判断响应类型（Celery 模式 vs Sync 模式）
      if (result.task_system === 'celery' && (result as ContractGenerationCeleryResponse).task_id) {
        // Celery 模式：进入任务监听流程
        const celeryResult = result as ContractGenerationCeleryResponse;
        setTaskId(celeryResult.task_id!);
        setTaskStatus('processing'); // ✅ 修复：设置为 processing 以触发进度显示
        message.info(celeryResult.message || '合同生成任务已提交后台处理，请稍候...');

        // 启动 WebSocket 监听
        await startTaskMonitoring(celeryResult.task_id!);
      } else if (result.task_system === 'sync' || !result.task_system) {
        // Sync 模式或旧版本兼容：直接显示结果（原有逻辑）
        const syncResult = result as any; // 兼容旧格式
        if (syncResult.success) {
          setGeneratedContracts(syncResult.contracts || []);

          if (syncResult.contracts && syncResult.contracts.length > 0) {
            const firstContract = syncResult.contracts[0];
            setSelectedContract(firstContract);
            setEditableContent(firstContract.content || '');
          }

          setCurrentStep(2);
          message.success(`成功生成 ${syncResult.contracts?.length || 0} 份合同`);
        } else {
          message.error(syncResult.error || '生成失败');
        }
      }
    } catch (error: any) {
      console.error('生成合同失败:', error);
      message.error(error.response?.data?.detail || '生成合同失败，请重试');
    } finally {
      setGenerating(false);
    }
  };

  // 【新增函数】：处理规划模式确认并生成规划
  const handlePlanningModeConfirm = async (mode: 'multi_model' | 'single_model') => {
    setSelectedPlanningMode(mode);
    setPlanningModeSelectionVisible(false);

    setPlanGenerationLoading(true);
    try {
      // 准备文件列表
      const file_list = uploadedFiles
        .filter(f => f.originFileObj)
        .map(f => f.originFileObj);

      // 调用 /generate-plan-only API
      const response = await api.generateContractPlanOnly({
        user_input: userInput,
        planning_mode: mode,
        uploaded_files: file_list.length > 0 ? file_list : undefined,
        session_id: sessionId || undefined
      });

      const result = response.data;

      if (result.success) {
        setContractPlanResult(result);
        setCurrentStep(1); // 进入确认步骤，显示规划结果
        message.success('合同规划生成成功');
      } else {
        message.error(result.error || '规划生成失败');
      }
    } catch (error: any) {
      console.error('规划生成失败:', error);
      message.error(error.response?.data?.detail || '规划生成失败，请重试');
    } finally {
      setPlanGenerationLoading(false);
    }
  };

  // 【新增函数】：基于规划生成合同
  const handleGenerateFromPlan = async () => {
    if (!contractPlanResult) {
      message.error('缺少规划结果');
      return;
    }

    setGenerating(true);
    try {
      // 生成临时 plan_id（实际应该从后端返回）
      const planId = `plan_${Date.now()}`;

      // 调用 /generate-from-plan API
      const response = await api.generateContractsFromPlan({
        plan_id: planId,
        session_id: sessionId || undefined
      });

      const result = response.data;

      if (result.success) {
        // 处理生成的合同
        if (result.contracts && Array.isArray(result.contracts)) {
          setGeneratedContracts(result.contracts);
          if (result.contracts.length > 0) {
            const firstContract = result.contracts[0];
            setSelectedContract(firstContract);
            setEditableContent(firstContract.content || '');
          }
          setCurrentStep(2);
          message.success(`成功生成 ${result.contracts.length} 份合同`);
        } else if (result.task_id) {
          // Celery 任务模式
          setTaskId(result.task_id);
          setTaskStatus('pending');
          message.info('合同生成任务已提交后台处理，请稍候...');
          await startTaskMonitoring(result.task_id);
        }
      } else {
        message.error(result.error || '基于规划生成合同失败');
      }
    } catch (error: any) {
      console.error('基于规划生成合同失败:', error);
      message.error(error.response?.data?.detail || '基于规划生成合同失败，请重试');
    } finally {
      setGenerating(false);
    }
  };

  // 【新增函数】：处理合同变更/解除生成
  const handleGenerateModificationTermination = async () => {
    if (!extractedInfo) {
      message.error('缺少确认信息，请等待信息提取完成');
      return;
    }

    // 【修复】清除旧的 sessionStorage，避免使用旧任务 ID
    sessionStorage.removeItem('contract_gen_task');

    setGenerating(true);
    try {
      const response = await api.generateContractWithFormData({
        user_input: userInput,
        form_data: {},  // 不使用表单数据，使用确认信息
        analysis_result: clarificationFormResponse.analysis_result,
        template_match_result: clarificationFormResponse.template_match_result,
        knowledge_graph_features: clarificationFormResponse.knowledge_graph_features,
        planning_mode: 'single_model',
        skip_template: true,  // 跳过模板，直接使用简化流程
        // 【修改】使用独立的 extractedInfo state 而不是 clarificationFormResponse
        confirmed_modification_termination_info: extractedInfo
      });

      const result = response.data as ContractGenerationTaskResponse;

      // 判断响应类型（Celery 模式 vs Sync 模式）
      if (result.task_system === 'celery' && (result as ContractGenerationCeleryResponse).task_id) {
        const celeryResult = result as ContractGenerationCeleryResponse;
        setTaskId(celeryResult.task_id);
        setTaskStatus('pending');
        message.info('变更/解除协议生成任务已提交后台处理，请稍候...');
        await startTaskMonitoring(celeryResult.task_id!);
      } else {
        // 同步模式
        const syncResult = result as ContractGenerationSyncResponse;
        if (syncResult.contracts && Array.isArray(syncResult.contracts)) {
          setGeneratedContracts(syncResult.contracts);
          if (syncResult.contracts.length > 0) {
            const firstContract = syncResult.contracts[0];
            setSelectedContract(firstContract);
            setEditableContent(firstContract.content || '');
          }
          setCurrentStep(2);
          message.success('变更/解除协议生成成功');
        }
      }
    } catch (error: any) {
      console.error('生成变更/解除协议失败:', error);
      message.error(error.response?.data?.detail || '生成失败，请重试');
    } finally {
      setGenerating(false);
    }
  };

  // 辅助函数：格式化表单数据为文本输入
  const _formatFormDataForInput = (formData: Record<string, any>): string => {
    const sections: string[] = [];
    sections.push('## 补充信息');

    for (const [key, value] of Object.entries(formData)) {
      if (value !== null && value !== undefined && value !== '') {
        // 将 field_id 转换为可读标签
        const label = _getFieldLabel(key);
        sections.push(`- ${label}: ${value}`);
      }
    }

    return sections.join('\n');
  };

  // 辅助函数：从表单中获取字段标签
  const _getFieldLabel = (fieldId: string): string => {
    if (!clarificationFormResponse?.clarification_form) return fieldId;

    for (const section of clarificationFormResponse.clarification_form.sections) {
      const field = section.fields.find(f => f.field_id === fieldId);
      if (field) return field.label;
    }

    return fieldId;
  };

  // 加载模板预览内容
  const handleLoadTemplatePreview = async (templateId: string) => {
    setLoadingTemplatePreview(true);
    try {
      const response = await api.getTemplatePreview(templateId);
      const result = response.data;

      if (result.success) {
        setTemplatePreviewContent(result.template);
        setTemplatePreviewVisible(true);
      } else {
        message.error(result.message || '加载模板失败');
      }
    } catch (error: any) {
      console.error('加载模板预览失败:', error);
      message.error(error.response?.data?.detail || '加载模板预览失败，请重试');
    } finally {
      setLoadingTemplatePreview(false);
    }
  };

  // 预览文档文本内容（新窗口打开预览页面）
  const handlePreview = (contract: GeneratedContract) => {
    const baseUrl = window.location.protocol + '//' + window.location.hostname + ':9000';
    const previewUrl = baseUrl + contract.preview_url;
    window.open(previewUrl, '_blank');
  };

  // 确认并生成文件
  const handleGenerateFiles = async (contract: GeneratedContract, index: number) => {
    // 【修改】：使用用户编辑后的内容 (editableContent) 而不是原始 contract.content
    // 注意：如果是当前选中的合同，用 editableContent；如果是列表里的其他合同，用它自己的 content
    const contentToUse = (selectedContract?.filename === contract.filename) 
        ? editableContent 
        : contract.content;

    if (!contentToUse) {
      message.error('没有可用的文本内容');
      return;
    }

    setGeneratingFiles({ ...generatingFiles, [index]: true });

    try {
      const formData = new FormData();
      formData.append('content', contentToUse);
      formData.append('filename', contract.filename);
      formData.append('doc_type', 'contract');
      formData.append('output_format', outputFormat);

      const response = await api.generateContractFiles(formData);
      const result = response.data;

      if (result.success) {
        // 更新合同信息，添加文件路径
        const updatedContracts = [...generatedContracts];
        updatedContracts[index] = {
          ...contract,
          content: contentToUse, // 更新保存的内容
          docx_path: result.docx_path,
          pdf_path: result.pdf_path,
          preview_url: result.preview_url,
          download_docx_url: result.download_docx_url,
          download_pdf_url: result.download_pdf_url,
          file_generated: true
        };
        setGeneratedContracts(updatedContracts);
        
        // 如果当前正在编辑的是这个合同，也更新 selectedContract
        if (selectedContract?.filename === contract.filename) {
          setSelectedContract(updatedContracts[index]);
        }

        message.success('文件生成成功');

        // 加载 OnlyOffice 配置用于预览
        await loadOnlyOfficeConfig(contract.filename);
      } else {
        message.error(result.message || '文件生成失败');
      }
    } catch (error: any) {
      console.error('文件生成失败:', error);
      message.error(error.response?.data?.detail || '文件生成失败，请重试');
    } finally {
      setGeneratingFiles({ ...generatingFiles, [index]: false });
    }
  };

  // 下载文档
  const handleDownload = async (contract: GeneratedContract) => {
    try {
      // 构造下载 URL
      const baseUrl = window.location.protocol + '//' + window.location.hostname + ':9000';
      const downloadUrl = baseUrl + contract.download_docx_url;
      window.open(downloadUrl, '_blank');
      message.success('开始下载');
    } catch (error) {
      message.error('下载失败');
    }
  };

  // 重置流程
  const handleReset = () => {
    setCurrentStep(0);
    setUserInput('');
    setUploadedFiles([]);
    setAnalyzingResult(null);
    setGeneratedContracts([]);
    setClarificationFormResponse(null);
    setClarificationFormData({});
    setUseTemplate(true);
    setEditableContent('');
    setSelectedContract(null);
    // 重置规划模式选择状态
    setPlanningModeSelectionVisible(false);
    setPlanningModeOptions(null);
    setSelectedPlanningMode(null);
    // 【新增】重置合同规划流程状态
    setContractPlanResult(null);
    setPlanGenerationLoading(false);
    clarificationForm.resetFields();
    form.resetFields();
    // 清除会话数据
    clearSession();
  };

  // 获取处理类型配置
  const getProcessingTypeConfig = () => {
    if (!analyzingResult) return null;
    return PROCESSING_TYPE_LABELS[analyzingResult.processing_type] || {
      label: analyzingResult.processing_type,
      color: 'default',
      description: ''
    };
  };

  // 渲染第一步：输入需求
  const renderStepInput = () => (
    <Card className="step-card">
      <Title level={4}>1. 描述您的需求</Title>
      <Paragraph type="secondary">
        请详细描述您需要生成的合同内容，AI 将根据您的需求智能生成合同文档。
      </Paragraph>

      {analyzing && (
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <Spin tip="AI 正在分析您的需求，请稍候..." size="large" />
          <div style={{ marginTop: 16, color: '#999' }}>
            这可能需要几秒钟时间
          </div>
        </div>
      )}

      <Form layout="vertical" style={{ display: analyzing ? 'none' : 'block' }}>
        <Form.Item label="需求描述" required>
          <TextArea
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            placeholder="例如：我与另一自然人合资设立一家公司，双方合计出资100万元，我出资75万元持有75%股权，对方出资25万元持有25%股权，请帮我草拟一份股权投资合作协议。"
            rows={6}
            showCount
            maxLength={2000}
          />
        </Form.Item>

        <Form.Item label="上传相关文件（可选）">
          <Dragger {...fileUploadProps}>
            <p className="ant-upload-drag-icon">
              <UploadOutlined />
            </p>
            <p className="ant-upload-text">点击或拖拽文件到此处</p>
            <p className="ant-upload-hint">
              支持上传 Word、PDF、图片文件，用于合同变更、解除等场景
            </p>
          </Dragger>
        </Form.Item>

        <Form.Item>
          <Button
            type="primary"
            size="large"
            icon={<SendOutlined />}
            onClick={() => handleAnalyzeRequirement()}
            loading={analyzing}
            block
          >
            分析需求
          </Button>
        </Form.Item>
      </Form>
    </Card>
  );

  // 渲染第二步：匹配情况 + 澄清表单（支持进度覆盖层）
  const renderStepConfirm = () => {
    if (!clarificationFormResponse) return null;

    // 【新增】Step 2 LLM 提取中的加载状态
    if (extractingModificationTerminationInfo) {
      return (
        <Card className="step-card">
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <Spin tip="AI 正在从您的输入中提取关键信息..." size="large" />
            <div style={{ marginTop: 24, color: '#666' }}>
              <p>正在分析原合同内容和变更/解除需求</p>
              <p style={{ fontSize: 12, color: '#999' }}>这可能需要几秒钟时间</p>
            </div>
          </div>
        </Card>
      );
    }

    // 【修复】简化条件判断，只依赖 taskId 和 taskStatus
    // 移除对 isWebSocketConnected 的依赖，因为它可能与实际状态不同步
    // 显示进度覆盖层的条件：
    // 1. 有 taskId 并且任务状态是 processing（正在处理）
    // 2. 或者有 taskId 但还没有生成的合同（任务刚完成但结果还没显示）
    const shouldShowProgress = taskId &&
      (taskStatus === 'processing' ||
       (taskStatus === 'completed' && generatedContracts.length === 0));

    // ✨ Celery 任务进行中时，显示进度覆盖层
    if (shouldShowProgress) {
      return (
        <div style={{ position: 'relative', minHeight: 400 }}>
          {/* 原有确认方案内容（模糊背景） */}
          <div style={{ filter: 'blur(2px)', pointerEvents: 'none', opacity: 0.6 }}>
            {renderOriginalConfirmContent()}
          </div>

          {/* 进度覆盖层 */}
          <div className="progress-overlay">
            {renderStepProgress()}
          </div>
        </div>
      );
    }

    // 正常显示确认方案内容
    return renderOriginalConfirmContent();
  };

  // 【新增】渲染合同变更/解除确认界面
  const renderModificationTerminationConfirm = () => {
    if (!extractedInfo) return null;

    const info = extractedInfo;
    const { processing_type, original_contract_info, confidence } = info;
    const isTermination = processing_type === 'contract_termination';

    return (
      <div className="step-card" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <Title level={4}>
          {isTermination ? '2. 确认解除信息' : '2. 确认变更信息'}
        </Title>

        {/* 置信度提示 */}
        {confidence !== undefined && (
          <Alert
            message={confidence >= 0.8 ? '信息提取准确度高' : '请仔细核对以下信息'}
            description={
              confidence >= 0.8
                ? `系统已从您提供的信息中提取出关键内容，准确度 ${(confidence * 100).toFixed(0)}%。请确认无误后点击生成。`
                : `系统提取的信息准确度 ${(confidence * 100).toFixed(0)}%，建议您仔细核对并修正以下信息。`
            }
            type={confidence >= 0.8 ? 'success' : 'warning'}
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        {/* 原合同信息卡片 */}
        <Card
          title={<><FileTextOutlined /> 原合同信息</>}
          bordered
          style={{ background: '#f6ffed' }}
        >
          <Descriptions bordered size="small" column={1}>
            <Descriptions.Item label="合同名称">
              {original_contract_info.contract_name || '未识别'}
            </Descriptions.Item>
            <Descriptions.Item label="签订日期">
              {original_contract_info.signing_date || '未识别'}
            </Descriptions.Item>
            <Descriptions.Item label="合同期限">
              {original_contract_info.contract_term || '未识别'}
            </Descriptions.Item>
            <Descriptions.Item label="当事人">
              {original_contract_info.parties?.length > 0
                ? original_contract_info.parties.join('、')
                : '未识别'}
            </Descriptions.Item>
          </Descriptions>
        </Card>

        {/* 解除/变更信息卡片 */}
        {isTermination ? (
          <Card
            title={<><EditOutlined /> 解除详情</>}
            bordered
            style={{ background: '#fff7e6' }}
          >
            <Form layout="vertical">
              <Form.Item label="解除原因">
                <Input.TextArea
                  defaultValue={info.termination_reason || ''}
                  onChange={(e) => {
                    // 【修改】更新 extractedInfo state 而不是 clarificationFormResponse
                    setExtractedInfo({
                      ...extractedInfo,
                      termination_reason: e.target.value
                    });
                  }}
                  placeholder="请输入或修改解除原因"
                  rows={3}
                />
              </Form.Item>

              <Form.Item label={<Text strong>解除后安排</Text>}>
                <Table
                  dataSource={
                    info.post_termination_arrangements && Object.keys(info.post_termination_arrangements).length > 0
                      ? Object.entries(info.post_termination_arrangements).map(([key, value]) => ({
                          key: key,
                          item: key,
                          detail: value as string
                        }))
                      : [{ key: 'empty', item: '', detail: '' }]
                  }
                  columns={[
                    {
                      title: '项目',
                      dataIndex: 'item',
                      key: 'item',
                      width: '30%',
                      render: (text: string, record: any, index: number) => (
                        <Input
                          defaultValue={text}
                          placeholder="例如：费用结算"
                          onChange={(e) => {
                            const arrangements = { ...(info.post_termination_arrangements || {}) };
                            if (record.key === 'empty' && e.target.value) {
                              // 如果是空行且用户输入了内容，创建新条目
                              arrangements[`项目${Object.keys(arrangements).length + 1}`] = e.target.value;
                              setExtractedInfo({
                                ...extractedInfo,
                                post_termination_arrangements: arrangements
                              });
                            } else if (record.key !== 'empty') {
                              // 更新现有条目的键名
                              const oldKey = record.key;
                              const entries = Object.entries(arrangements);
                              const newEntries = entries.map(([k, v]) => k === oldKey ? [e.target.value || k, v] : [k, v]);
                              setExtractedInfo({
                                ...extractedInfo,
                                post_termination_arrangements: Object.fromEntries(newEntries)
                              });
                            }
                          }}
                        />
                      )
                    },
                    {
                      title: '详情',
                      dataIndex: 'detail',
                      key: 'detail',
                      render: (text: string, record: any) => (
                        <Input.TextArea
                          defaultValue={text}
                          placeholder="请输入详情"
                          rows={2}
                          onChange={(e) => {
                            const arrangements = { ...(info.post_termination_arrangements || {}) };
                            if (record.key === 'empty' && e.target.value) {
                              arrangements[`项目${Object.keys(arrangements).length + 1}`] = e.target.value;
                              setExtractedInfo({
                                ...extractedInfo,
                                post_termination_arrangements: arrangements
                              });
                            } else if (record.key !== 'empty') {
                              arrangements[record.key] = e.target.value;
                              setExtractedInfo({
                                ...extractedInfo,
                                post_termination_arrangements: arrangements
                              });
                            }
                          }}
                        />
                      )
                    }
                  ]}
                  pagination={false}
                  size="small"
                  bordered
                />
              </Form.Item>
            </Form>
          </Card>
        ) : (
          <Card
            title={<><EditOutlined /> 变更详情</>}
            bordered
            style={{ background: '#e6f7ff' }}
          >
            {info.modification_points && info.modification_points.length > 0 ? (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                {info.modification_points.map((point: any, index: number) => (
                  <Card key={index} size="small" hoverable>
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <div>
                        <Tag color="blue">变更点 {index + 1}</Tag>
                        {point.clause_number && (
                          <Tag color="geekblue">条款 {point.clause_number}</Tag>
                        )}
                      </div>
                      <div>
                        <Text type="secondary">原条款：</Text>
                        <div style={{
                          padding: 8,
                          background: '#f5f5f5',
                          borderRadius: 4,
                          marginTop: 4,
                          fontFamily: 'monospace'
                        }}>
                          {point.original_content}
                        </div>
                      </div>
                      <div>
                        <Text type="secondary">变更为：</Text>
                        <Input.TextArea
                          defaultValue={point.modified_content}
                          onChange={(e) => {
                            // 【修改】更新 extractedInfo 中的变更点
                            const updatedPoints = [...extractedInfo.modification_points];
                            updatedPoints[index].modified_content = e.target.value;
                            setExtractedInfo({
                              ...extractedInfo,
                              modification_points: updatedPoints
                            });
                          }}
                          style={{ marginTop: 4 }}
                          rows={3}
                        />
                      </div>
                      {point.reason && (
                        <div>
                          <Text type="secondary">变更原因：{point.reason}</Text>
                        </div>
                      )}
                    </Space>
                  </Card>
                ))}
              </Space>
            ) : (
              <Alert
                message="未检测到具体变更点"
                description="系统未能在您的需求中识别出明确的变更条款。您可以继续生成，系统将根据您的整体需求进行推断。"
                type="info"
                showIcon
              />
            )}
          </Card>
        )}

        {/* 操作按钮 */}
        <Card bordered={false} style={{ background: '#fafafa' }}>
          <Space>
            <Button onClick={() => setCurrentStep(0)}>
              返回修改需求
            </Button>
            <Button
              type="primary"
              size="large"
              icon={<CheckCircleOutlined />}
              onClick={() => handleGenerateModificationTermination()}
              loading={generating}
            >
              确认并生成{isTermination ? '解除协议' : '变更协议'}
            </Button>
          </Space>
        </Card>
      </div>
    );
  };

  // 辅助函数：渲染原有的确认方案内容（提取为独立函数以便复用）
  const renderOriginalConfirmContent = () => {
    if (!clarificationFormResponse) return null;

    const processingType = clarificationFormResponse.processing_type;

    // 【调试】打印当前场景
    console.log('[renderOriginalConfirmContent] 当前场景:', processingType, {
      hasExtractedInfo: !!extractedInfo,
      hasPlanningModeSelection: planningModeSelectionVisible,
      hasClarificationForm: !!clarificationFormResponse.clarification_form
    });

    // 【修改】处理合同变更/解除场景 - 使用独立的 extractedInfo state
    if (extractedInfo) {
      console.log('[renderOriginalConfirmContent] 检测到变更/解除信息，使用专用确认界面');
      return renderModificationTerminationConfirm();
    }

    // ✨ 新增：处理合同规划模式选择
    if (planningModeSelectionVisible && planningModeOptions) {
      const { multi_model, single_model } = planningModeOptions;

      return (
        <div className="step-card" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <Title level={4}>2. 选择合同规划生成模式</Title>

          <Alert
            message="检测到合同规划场景"
            description="系统检测到您的需求属于复杂的合同规划场景，可能需要多份合同协同。请选择生成模式："
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
          />

          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {/* 多模型综合融合模式 */}
            <Card
              hoverable
              style={{
                border: multi_model.recommended ? '2px solid #1890ff' : '1px solid #d9d9d9',
                background: multi_model.recommended ? '#f0f5ff' : '#fff'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div style={{ flex: 1 }}>
                  <Space style={{ marginBottom: 12 }}>
                    <Title level={5} style={{ margin: 0 }}>{multi_model.name}</Title>
                    {multi_model.recommended && <Tag color="blue">推荐</Tag>}
                    {!multi_model.available && <Tag color="red">不可用</Tag>}
                  </Space>

                  <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                    {multi_model.description}
                  </Paragraph>

                  <div style={{ marginBottom: 16 }}>
                    <Text strong>特点：</Text>
                    <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                      {multi_model.features?.map((feature: string, idx: number) => (
                        <li key={idx}>{feature}</li>
                      ))}
                    </ul>
                  </div>

                  <Space>
                    <Tag color="green">预期质量：{multi_model.expected_quality}</Tag>
                    <Tag color="orange">处理时间：{multi_model.processing_time}</Tag>
                  </Space>
                </div>

                <Button
                  type={multi_model.recommended ? 'primary' : 'default'}
                  size="large"
                  disabled={!multi_model.available}
                  onClick={() => handlePlanningModeConfirm('multi_model')}
                  loading={planGenerationLoading}
                >
                  选择此模式
                </Button>
              </div>
            </Card>

            {/* 单模型快速生成模式 */}
            <Card
              hoverable
              style={{
                border: single_model.recommended ? '2px solid #1890ff' : '1px solid #d9d9d9',
                background: single_model.recommended ? '#f0f5ff' : '#fff'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <div style={{ flex: 1 }}>
                  <Space style={{ marginBottom: 12 }}>
                    <Title level={5} style={{ margin: 0 }}>{single_model.name}</Title>
                    {single_model.recommended && <Tag color="blue">推荐</Tag>}
                  </Space>

                  <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                    {single_model.description}
                  </Paragraph>

                  <div style={{ marginBottom: 16 }}>
                    <Text strong>特点：</Text>
                    <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                      {single_model.features?.map((feature: string, idx: number) => (
                        <li key={idx}>{feature}</li>
                      ))}
                    </ul>
                  </div>

                  <Space>
                    <Tag color="green">预期质量：{single_model.expected_quality}</Tag>
                    <Tag color="orange">处理时间：{single_model.processing_time}</Tag>
                  </Space>
                </div>

                <Button
                  type={single_model.recommended ? 'primary' : 'default'}
                  size="large"
                  onClick={() => handlePlanningModeConfirm('single_model')}
                  loading={planGenerationLoading}
                >
                  选择此模式
                </Button>
              </div>
            </Card>
          </Space>

          {/* 操作按钮 */}
          <Card bordered={false} style={{ background: '#fafafa' }}>
            <Button onClick={() => setCurrentStep(0)}>
              返回修改需求
            </Button>
          </Card>
        </div>
      );
    }

    // 【新增】处理合同规划结果显示
    if (contractPlanResult && clarificationFormResponse?.processing_type === 'contract_planning') {
      return (
        <div className="step-card" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          <Title level={4}>2. 查看规划结果</Title>

          <Alert
            message="规划生成成功"
            description="系统已根据您的需求生成合同规划，请查看以下结果。确认后可开始生成具体合同。"
            type="success"
            showIcon
            style={{ marginBottom: 24 }}
          />

          {/* 规划结果展示 */}
          <Card
            title="合同规划清单"
            extra={
              <Tag color={contractPlanResult.planning_mode === 'multi_model' ? 'gold' : 'blue'}>
                {contractPlanResult.planning_mode === 'multi_model' ? '多模型融合' : '单模型生成'}
              </Tag>
            }
          >
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {contractPlanResult.contract_plan?.map((contract: any, index: number) => (
                <Card key={contract.id || index} size="small" hoverable>
                  <Space direction="vertical" size="small" style={{ width: '100%' }}>
                    <Space>
                      <Tag color="blue">{index + 1}</Tag>
                      <Text strong>{contract.title}</Text>
                      {contract.contract_type && <Tag>{contract.contract_type}</Tag>}
                      {contract.priority && <Tag color="geekblue">优先级：{contract.priority}</Tag>}
                    </Space>
                    {contract.purpose && (
                      <Paragraph type="secondary" style={{ margin: 0 }}>
                        {contract.purpose}
                      </Paragraph>
                    )}
                    {contract.parties && contract.parties.length > 0 && (
                      <div>
                        <Text type="secondary">当事人：</Text>
                        <Text>{contract.parties.join('、')}</Text>
                      </div>
                    )}
                  </Space>
                </Card>
              ))}
            </Space>
          </Card>

          {/* 多模型融合报告 */}
          {contractPlanResult.synthesis_report && (
            <Card title="多模型融合分析" bordered={false} style={{ background: '#f6ffed' }}>
              <Paragraph type="secondary">
                {contractPlanResult.synthesis_report.fusion_summary}
              </Paragraph>
              {contractPlanResult.synthesis_report.extracted_strengths?.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <Text strong>优势：</Text>
                  <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                    {contractPlanResult.synthesis_report.extracted_strengths.map((strength: string, idx: number) => (
                      <li key={idx}>{strength}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}

          {/* 操作按钮 */}
          <Card bordered={false} style={{ background: '#fafafa' }}>
            <Space>
              <Button onClick={() => setCurrentStep(0)}>
                返回修改需求
              </Button>
              <Button
                type="primary"
                size="large"
                icon={<CheckCircleOutlined />}
                onClick={handleGenerateFromPlan}
                loading={generating}
              >
                确认并开始生成合同
              </Button>
            </Space>
          </Card>
        </div>
      );
    }

    // 原有的单一合同生成流程
    const { template_match_result } = clarificationFormResponse;

    return (
      <div className="step-card" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <Title level={4}>2. 确认处理方案并补充信息</Title>

        {/* 模板匹配卡片 */}
        {template_match_result && (
          <Card
            className="template-match-card"
            bordered
            style={{
              background: template_match_result.match_level === 'HIGH' ? '#f6ffed' : '#fffbe6',
              borderColor: template_match_result.match_level === 'HIGH' ? '#b7eb8f' : '#ffe58f'
            }}
          >
            <div className="match-card-header">
              <Space>
                <FileTextOutlined style={{ fontSize: 20, color: template_match_result.match_level === 'HIGH' ? '#52c41a' : '#faad14' }} />
                <div>
                  <Text strong style={{ fontSize: 16 }}>模板匹配结果</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 13 }}>
                    {template_match_result.match_level === 'HIGH' ? '高度匹配' :
                     template_match_result.match_level === 'STRUCTURAL' ? '结构参考' : '未找到匹配模板'}
                  </Text>
                </div>
              </Space>
              <Space>
                <Tag color={template_match_result.match_level === 'HIGH' ? 'success' : 'warning'}>
                  {template_match_result.match_level}
                </Tag>
                {template_match_result.template_id && (
                  <Button
                    size="small"
                    icon={<EyeOutlined />}
                    onClick={() => handleLoadTemplatePreview(template_match_result.template_id)}
                    loading={loadingTemplatePreview}
                  >
                    预览模板
                  </Button>
                )}
              </Space>
            </div>

            {template_match_result.template_name && (
              <div style={{ marginTop: 16 }}>
                <Text strong>匹配模板：</Text>
                <Text style={{ marginLeft: 8 }}>{template_match_result.template_name}</Text>
                {template_match_result.match_score !== undefined && (
                  <Tag color="blue" style={{ marginLeft: 8 }}>
                    相似度: {(template_match_result.match_score * 100).toFixed(1)}%
                  </Tag>
                )}
              </div>
            )}

            {template_match_result.match_reason && (
              <div style={{ marginTop: 12 }}>
                <Text type="secondary" style={{ fontSize: 13 }}>
                  匹配原因：{template_match_result.match_reason}
                </Text>
              </div>
            )}
          </Card>
        )}

        {/* 需求澄清表单 */}
        {(() => {
          console.log('[renderOriginalConfirmContent] 渲染澄清表单，场景:', processingType);
          return null;
        })()}
        <Card className="clarification-form-card" bordered title="需求澄清表单">
          <Alert
            message="请补充以下信息以生成更准确的合同"
            description="标记为红色的字段为必填项，其他为选填项。填写完整信息后，选择是否使用模板生成合同。"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />

          {/* 防御性检查：确保有数据可以渲染 */}
          {!normalizedClarificationForm?.sections ? (
            <Alert
              message="表单数据加载中"
              description="正在分析您的需求，请稍候..."
              type="info"
            />
          ) : !Array.isArray(normalizedClarificationForm.sections) ? (
            <Alert
              message="数据格式错误"
              description="表单数据格式异常，请重新尝试"
              type="error"
            />
          ) : (
          <Form
            form={form}
            layout="vertical"
            onValuesChange={(changedValues) => {
              setClarificationFormData({ ...clarificationFormData, ...changedValues });
            }}
          >
            {normalizedClarificationForm?.sections?.map((section) => (
              <div key={section.section_id} style={{ marginBottom: 24 }}>
                <Title level={5} style={{ marginBottom: 16 }}>
                  {section.section_title}
                </Title>

                <Space direction="vertical" style={{ width: '100%' }} size="middle">
                  {section.fields.map((field) => (
                    <Form.Item
                      key={field.field_id}
                      name={field.field_id}
                      label={
                        <Space>
                          <Text>{field.label}</Text>
                          {field.required && <Text type="danger"> *</Text>}
                          {normalizedClarificationForm?.summary?.missing_info?.includes(field.label) && (
                            <Tag color="red">缺失</Tag>
                          )}
                        </Space>
                      }
                      initialValue={field.default_value}
                      rules={field.required ? [{ required: true, message: `请填写${field.label}` }] : []}
                    >
                      {renderFormField(field)}
                    </Form.Item>
                  ))}
                </Space>
              </div>
            ))}
          </Form>
          )}
        </Card>

        {/* 操作按钮 */}
        <Card className="action-buttons-card" bordered={false} style={{ background: '#fafafa' }}>
          <Space style={{ width: '100%', justifyContent: 'space-between' }}>
            <Button onClick={() => setCurrentStep(0)}>
              返回修改
            </Button>

            <Space>
              {clarificationFormResponse.processing_type === 'contract_planning' ? (
                // 合同规划场景：显示单一按钮（不涉及模板）
                <Button
                  type="primary"
                  size="large"
                  icon={<CheckCircleOutlined />}
                  onClick={() => handleGenerateContract(false)}
                  loading={generating}
                >
                  开始生成合同规划
                </Button>
              ) : clarificationFormResponse.processing_type === 'contract_modification' ||
                        clarificationFormResponse.processing_type === 'contract_termination' ? (
                // 合同变更/解除场景：显示单一按钮（不涉及模板）
                <Button
                  type="primary"
                  size="large"
                  icon={<CheckCircleOutlined />}
                  onClick={() => handleGenerateContract(false)}
                  loading={generating}
                >
                  {clarificationFormResponse.processing_type === 'contract_modification' ? '开始生成变更协议' : '开始生成解除协议'}
                </Button>
              ) : (
                // 单一合同场景：显示模板选择按钮
                <>
                  <Button
                    size="large"
                    onClick={() => handleGenerateContract(false)}
                    loading={generating}
                  >
                    不采用模板生成
                  </Button>
                  <Button
                    type="primary"
                    size="large"
                    icon={<CheckCircleOutlined />}
                    onClick={() => handleGenerateContract(true)}
                    loading={generating}
                    disabled={template_match_result?.match_level === 'NONE'}
                  >
                    采用模板生成
                  </Button>
                </>
              )}
            </Space>
          </Space>
        </Card>
      </div>
    );
  };

  // 渲染表单字段
  const renderFormField = (field: ClarificationFormField) => {
    switch (field.field_type) {
      case 'text':
        return (
          <Input
            placeholder={field.placeholder}
            maxLength={200}
          />
        );

      case 'textarea':
        return (
          <TextArea
            placeholder={field.placeholder}
            rows={4}
            showCount
            maxLength={2000}
          />
        );

      case 'number':
        return (
          <Input
            type="number"
            placeholder={field.placeholder}
          />
        );

      case 'date':
        return (
          <Input
            type="date"
          />
        );

      case 'money':
        return (
          <Input
            type="number"
            placeholder={field.placeholder || '请输入金额'}
            prefix="¥"
            addonAfter="元"
          />
        );

      case 'select':
        return (
          <Select placeholder={field.placeholder}>
            {field.options?.map((option, index) => (
              <Option key={option.value ?? `option-${index}`} value={option.value}>
                {option.label}
              </Option>
            ))}
          </Select>
        );

      case 'radio':
        return (
          <Radio.Group>
            {field.options?.map((option) => (
              <Radio key={option.value} value={option.value}>
                {option.label}
              </Radio>
            ))}
          </Radio.Group>
        );

      case 'checkbox':
        return (
          <Checkbox.Group
            options={field.options?.map(opt => ({ label: opt.label, value: opt.value }))}
          />
        );

      default:
        return <Input placeholder={field.placeholder} />;
    }
  };

  // 【新增函数】：渲染任务进度展示组件
  const renderStepProgress = () => {
    return (
      <Card className="step-card progress-card">
        <div className="progress-container">
          <Title level={4}>AI 正在生成合同</Title>

          {/* 连接状态指示 */}
          <div className="connection-status">
            <span className={`status-indicator ${isWebSocketConnected ? 'connected' : 'disconnected'}`}>
              {isWebSocketConnected ? (
                <><CheckCircleOutlined /> WebSocket 连接正常</>
              ) : (
                <><SyncOutlined spin /> 连接中...</>
              )}
            </span>
          </div>

          {/* 进度条 */}
          <Progress
            percent={Math.round(taskProgress?.progress || 0)}
            status={taskStatus === 'failed' ? 'exception' : taskStatus === 'completed' ? 'success' : 'active'}
            size={12}
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
          />

          {/* 当前节点信息 */}
          {taskProgress?.currentNode && (
            <Alert
              message={taskProgress.currentNode}
              description={taskProgress.nodeProgress?.[taskProgress.currentNode]?.message}
              type="info"
              showIcon
              style={{ marginTop: 16, textAlign: 'left' }}
            />
          )}

          {/* 预计剩余时间 */}
          {taskProgress?.estimatedTimeRemaining && (
            <Text type="secondary" style={{ marginTop: 16, display: 'block' }}>
              预计剩余时间: {Math.ceil(taskProgress.estimatedTimeRemaining / 60)} 分钟
            </Text>
          )}

          {/* 处理中提示 */}
          {taskStatus === 'processing' && (
            <Paragraph type="secondary" style={{ marginTop: 16 }}>
              AI 正在深度分析您的需求并起草合同，这可能需要 1-3 分钟，请耐心等待...
            </Paragraph>
          )}
        </div>
      </Card>
    );
  };

  // 【重构】：渲染第三步：生成结果
  const renderStepResult = () => {
    // 获取当前展示的合同（优先 Selected，否则取第一个）
    const primaryContract = selectedContract || (generatedContracts.length > 0 ? generatedContracts[0] : null);

    return (
      <div className="step-card result-container">
        
        {/* === 上半部分：左右分屏显示区 === */}
        <div className="result-split-view">
          
          {/* 左侧：可编辑区域 (Source) */}
          <div className="split-pane edit-pane-container">
            <div className="pane-header">
              <Space>
                <EditOutlined />
                <span>编辑原始内容</span>
              </Space>
              <Tag color="default">Markdown</Tag>
            </div>
            <div className="pane-scroll-content">
              <TextArea
                className="contract-editor-textarea"
                value={editableContent}
                onChange={(e) => {
                  setEditableContent(e.target.value);
                  // 同步更新数据源，防止切换丢失
                  if (primaryContract) {
                    primaryContract.content = e.target.value;
                  }
                }}
                placeholder="在此处编辑合同内容，右侧将实时预览..."
                spellCheck={false}
              />
            </div>
          </div>

          {/* 右侧：预览区域 (Preview) - 仅显示 Markdown 预览 */}
          <div className="split-pane preview-pane-container">
            <div className="pane-header">
              <Space>
                <EyeOutlined />
                <span>格式预览</span>
              </Space>
              <Tag color="blue">Markdown 预览</Tag>
            </div>
            <div className="pane-scroll-content">
              {primaryContract ? (
                <div className="markdown-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {editableContent || primaryContract.content || ''}
                  </ReactMarkdown>
                </div>
              ) : (
                <div className="pane-placeholder">
                  <FileTextOutlined style={{ fontSize: 48, marginBottom: 16 }} />
                  <Text type="secondary">暂无预览内容</Text>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* === 下半部分：底部操作工具栏 === */}
        <div className="result-toolbar">
          
          {/* 左侧：状态信息 */}
          <div className="toolbar-left">
            <div className="status-capsule">
              <CheckCircleOutlined style={{ marginRight: 6 }} />
              <span>已生成 {generatedContracts.length} 份文档</span>
            </div>

            {/* 输出格式选择 */}
            <Space>
              <Text strong style={{ fontSize: 13 }}>输出格式：</Text>
              <Select
                value={outputFormat}
                onChange={setOutputFormat}
                style={{ width: 140 }}
                size="middle"
              >
                <Option value="docx">Word 文档</Option>
                <Option value="pdf">PDF 文档</Option>
              </Select>
            </Space>

            {/* 如果有多份合同，显示切换器 */}
            {generatedContracts.length > 1 && (
              <Space>
                <Text strong style={{ fontSize: 13 }}>当前文档：</Text>
                <Select
                  value={primaryContract?.filename}
                  onChange={handleContractChange}
                  style={{ width: 240 }}
                  size="middle"
                >
                  {generatedContracts.map((contract, index) => (
                    <Option key={index} value={contract.filename}>
                      {contract.filename}
                    </Option>
                  ))}
                </Select>
              </Space>
            )}

            {/* 模板来源显示 */}
            {primaryContract?.template_info && (
              <div className="template-info-text">
                基于模板：<Tag>{primaryContract.template_info.name}</Tag>
              </div>
            )}
          </div>

          {/* 右侧：核心操作按钮 */}
          <div className="toolbar-right">
            <Button onClick={handleReset}>
              放弃并重新开始
            </Button>
            
            {/* 下载按钮 (仅当文件已生成时显示) */}
            {primaryContract?.file_generated && (
              <Button 
                icon={<DownloadOutlined />} 
                onClick={() => handleDownload(primaryContract)}
              >
                下载 {outputFormat === 'pdf' ? 'PDF' : 'Word'}
              </Button>
            )}

            {/* 生成文件按钮 (主操作) */}
            <Button
              type="primary"
              icon={primaryContract?.file_generated ? <CheckCircleOutlined /> : <FileOutlined />}
              onClick={() => {
                if (primaryContract) {
                  const updatedContract = { ...primaryContract, content: editableContent };
                  const index = generatedContracts.findIndex(c => c.filename === primaryContract.filename);
                  handleGenerateFiles(updatedContract, index);
                }
              }}
              loading={primaryContract ? generatingFiles[generatedContracts.findIndex(c => c.filename === primaryContract.filename)] : false}
              style={{ minWidth: 120 }}
            >
              {primaryContract?.file_generated ? '重新生成文件' : '确认并生成文件'}
            </Button>
          </div>
        </div>

      </div>
    );
  };

  // 渲染模板预览 Modal
  const renderTemplatePreviewModal = () => {
    return (
      <Modal
        title="模板预览"
        open={templatePreviewVisible}
        onCancel={() => setTemplatePreviewVisible(false)}
        footer={[
          <Button key="close" onClick={() => setTemplatePreviewVisible(false)}>
            关闭
          </Button>
        ]}
        width={900}
      >
        <div style={{ padding: '16px 0' }}>
          {loadingTemplatePreview ? (
            <div style={{ textAlign: 'center', padding: '40px 0' }}>
              <Spin size="large" />
              <div style={{ marginTop: 16 }}>
                <Text type="secondary">正在加载模板内容...</Text>
              </div>
            </div>
          ) : templatePreviewContent ? (
            <>
              <Title level={4}>{templatePreviewContent.name}</Title>

              <Space style={{ marginBottom: 16 }}>
                {templatePreviewContent.category && (
                  <Tag color="blue">{templatePreviewContent.category}</Tag>
                )}
                {templatePreviewContent.subcategory && (
                  <Tag color="cyan">{templatePreviewContent.subcategory}</Tag>
                )}
              </Space>

              {templatePreviewContent.description && (
                <Paragraph style={{ marginBottom: 16 }}>
                  {templatePreviewContent.description}
                </Paragraph>
              )}

              {templatePreviewContent.preview_content && (
                <>
                  <Divider>模板内容预览</Divider>
                  <div
                    style={{
                      background: '#f5f5f5',
                      padding: 16,
                      borderRadius: 8,
                      maxHeight: 400,
                      overflow: 'auto',
                      fontFamily: 'monospace',
                      fontSize: 13,
                      lineHeight: 1.6,
                      whiteSpace: 'pre-wrap'
                    }}
                  >
                    {templatePreviewContent.preview_content}
                  </div>
                  <Text type="secondary" style={{ fontSize: 12, marginTop: 8, display: 'block' }}>
                    注：此为模板内容预览（前 2000 字符），生成时将根据您的需求进行调整。
                  </Text>
                </>
              )}
            </>
          ) : (
            <div style={{ background: '#f5f5f5', padding: 16, borderRadius: 8, textAlign: 'center' }}>
              <Text type="secondary">无法加载模板内容</Text>
            </div>
          )}
        </div>
      </Modal>
    );
  };

  // 渲染澄清问题 Modal (已弃用，保留以避免错误)
  const renderClarificationModal = () => (
    <Modal
      title="补充信息（可选）"
      open={clarificationModalVisible}
      onOk={handleClarificationSubmit}
      onCancel={() => {
        setClarificationModalVisible(false);
        // 不返回上一步，而是继续到确认步骤
        setCurrentStep(1);
      }}
      width={600}
      okText="确认继续"
      cancelText="跳过"
    >
      <Alert
        message="补充如下信息，生成的合同更准确"
        description="如您不补充，AI也可基于当前信息生成合同，但需要您进一步完善合同。以下问题均为选填项。"
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
      />

      <Form form={clarificationForm} layout="vertical">
        {analyzingResult?.clarification_questions.map((question, index) => (
          <Form.Item
            key={index}
            name={`answer_${index}`}
            label={
              <Space>
                <Text>{question}</Text>
                <Tag color="blue">选填</Tag>
              </Space>
            }
            tooltip="此问题为选填，如不填写系统将使用默认处理"
          >
            <TextArea
              rows={3}
              placeholder="选填，如不填写将使用默认处理..."
              style={{ backgroundColor: '#fafafa' }}
            />
          </Form.Item>
        ))}
      </Form>

      <Divider />
      <Space direction="vertical" style={{ width: '100%' }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          <InfoCircleOutlined style={{ marginRight: 4 }} />
          提示：您可以选择性填写以上问题。未填写的信息将在生成的合同中以占位符或默认条款形式呈现，您可以根据实际情况进行后续修改和完善。
        </Text>
      </Space>
    </Modal>
  );

  // 【新增】：渲染历史任务列表
  const renderHistoryTasks = () => {
    // 状态显示配置
    const statusConfig = {
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
      processing: { color: 'processing', icon: <LoadingOutlined />, text: '处理中' },
      pending: { color: 'default', icon: <ClockCircleOutlined />, text: '待处理' },
      failed: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
      cancelled: { color: 'warning', icon: <CloseCircleOutlined />, text: '已取消' }
    };

    // 格式化时间
    const formatTime = (timeStr: string) => {
      if (!timeStr) return '-';
      const date = new Date(timeStr);
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    };

    const columns = [
      {
        title: '任务ID',
        dataIndex: 'id',
        key: 'id',
        width: 100,
        ellipsis: true,
        render: (id: string) => (
          <Tooltip title={id}>
            <Text copyable={{ text: id }} style={{ fontSize: 12 }}>
              {id.slice(0, 8)}...
            </Text>
          </Tooltip>
        )
      },
      {
        title: '状态',
        dataIndex: 'status',
        key: 'status',
        width: 100,
        render: (status: string) => {
          const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.pending;
          return (
            <Tag color={config.color} icon={config.icon}>
              {config.text}
            </Tag>
          );
        }
      },
      {
        title: '进度',
        dataIndex: 'progress',
        key: 'progress',
        width: 120,
        render: (progress: number) => (
          <Progress percent={Math.round(progress)} size="small" status={progress === 100 ? 'success' : 'active'} />
        )
      },
      {
        title: '用户需求',
        dataIndex: 'user_input',
        key: 'user_input',
        ellipsis: true,
        render: (userInput: string) => (
          <Tooltip title={userInput}>
            <Text ellipsis style={{ maxWidth: 300 }}>
              {userInput}
            </Text>
          </Tooltip>
        )
      },
      {
        title: '规划模式',
        dataIndex: 'planning_mode',
        key: 'planning_mode',
        width: 120,
        render: (mode: string) => {
          if (!mode) return '-';
          const modeConfig = {
            single_model: { text: '单模型', color: 'blue' },
            multi_model: { text: '多模型', color: 'gold' }
          };
          const config = modeConfig[mode as keyof typeof modeConfig];
          return config ? <Tag color={config.color}>{config.text}</Tag> : mode;
        }
      },
      {
        title: '创建时间',
        dataIndex: 'created_at',
        key: 'created_at',
        width: 160,
        render: (time: string) => formatTime(time)
      },
      {
        title: '完成时间',
        dataIndex: 'completed_at',
        key: 'completed_at',
        width: 160,
        render: (time: string) => formatTime(time)
      },
      {
        title: '操作',
        key: 'action',
        width: 120,
        fixed: 'right' as const,
        render: (_: any, record: any) => (
          <Space size="small">
            {record.status === 'completed' && (
              <Tooltip title="查看详情">
                <Button
                  type="link"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => {
                    // TODO: 实现查看详情功能
                    message.info('详情查看功能开发中');
                  }}
                />
              </Tooltip>
            )}
            {record.status === 'failed' && record.error_message && (
              <Tooltip title={record.error_message}>
                <Button
                  type="link"
                  size="small"
                  danger
                  icon={<InfoCircleOutlined />}
                />
              </Tooltip>
            )}
          </Space>
        )
      }
    ];

    return (
      <div className="history-tasks-container">
        <Card
          title={
            <Space>
              <HistoryOutlined />
              <span>历史任务记录</span>
            </Space>
          }
          extra={
            <Space>
              <Text type="secondary">共 {historyTotal} 条记录</Text>
              <Button
                icon={<SyncOutlined />}
                onClick={fetchHistoryTasks}
                loading={loadingHistory}
              >
                刷新
              </Button>
            </Space>
          }
        >
          {loadingHistory ? (
            <div style={{ textAlign: 'center', padding: '60px 0' }}>
              <Spin tip="加载中..." size="large" />
            </div>
          ) : historyTasks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px' }}>
              <FileTextOutlined style={{ fontSize: 64, color: '#d9d9d9', marginBottom: 16 }} />
              <Text type="secondary" style={{ fontSize: 16 }}>
                暂无历史任务记录
              </Text>
              <div style={{ marginTop: 16 }}>
                <Button type="primary" onClick={() => setActiveTab('new')}>
                  开始创建合同
                </Button>
              </div>
            </div>
          ) : (
            <Table
              columns={columns}
              dataSource={historyTasks}
              rowKey="id"
              pagination={{
                pageSize: 10,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条记录`
              }}
              scroll={{ x: 1200 }}
            />
          )}
        </Card>
      </div>
    );
  };

  // 【新增 Effect】：WebSocket 清理逻辑
  useEffect(() => {
    return () => {
      // 组件卸载时断开 WebSocket 连接
      taskWebSocketService.disconnect();
      console.log('[WebSocket] 组件卸载，已断开连接');
    };
  }, []);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#f0f2f5' }}>
      {/* 统一导航栏 */}
      <ModuleNavBar currentModuleKey="contract-generation" />

      {/* 原有内容区域 */}
      <div style={{ flex: 1, padding: '24px', maxWidth: 1400, margin: '0 auto', width: '100%' }}>
        {/* 【会话持久化】会话恢复提示 - 仅在新建标签页显示 */}
        {activeTab === 'new' && hasSession && !hasRestoredRef.current && (
          <Alert
            message="检测到之前的会话"
            description="系统检测到您之前有一个未完成的合同生成任务。您可以继续之前的工作，或者点击下方按钮重新开始。"
            type="info"
            showIcon
            closable
            style={{ marginBottom: 24 }}
            action={
              <Space>
                <Button
                  size="small"
                  onClick={() => {
                    clearSession();
                    hasRestoredRef.current = true;
                  }}
                >
                  重新开始
                </Button>
                <Button
                  type="primary"
                  size="small"
                  onClick={() => {
                    // 手动触发恢复（通过重新执行恢复 effect）
                    hasRestoredRef.current = false;
                    // 这将触发上面的 effect 执行恢复逻辑
                  }}
                >
                  恢复会话
                </Button>
              </Space>
            }
          />
        )}

        {/* 【新增】标签页切换 */}
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          style={{ marginBottom: 24 }}
          items={[
            {
              key: 'new',
              label: (
                <span>
                  <PlusOutlined />
                  新建合同
                </span>
              ),
              children: (
                <>
                  <Steps current={currentStep} style={{ marginBottom: 32, maxWidth: 800, margin: '0 auto 32px' }}>
                    <Step title="输入需求" description="描述您的合同需求" />
                    <Step title="确认方案" description="查看匹配并补充信息" />
                    <Step title="生成完成" description="获取合同文档" />
                  </Steps>

                  {currentStep === 0 && renderStepInput()}
                  {currentStep === 1 && renderStepConfirm()}
                  {currentStep === 2 && renderStepResult()}
                </>
              )
            },
            {
              key: 'history',
              label: (
                <span>
                  <HistoryOutlined />
                  历史记录
                </span>
              ),
              children: renderHistoryTasks()
            }
          ]}
        />

        {renderTemplatePreviewModal()}
        {renderClarificationModal()}
      </div>
    </div>
  );
};

export default ContractGenerationPage;