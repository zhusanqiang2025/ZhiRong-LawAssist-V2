// frontend/src/pages/ContractReview.tsx
import React, { useState, useRef, useEffect } from 'react';
import { flushSync } from 'react-dom';
import { DocumentEditor } from "@onlyoffice/document-editor-react";
import { useNavigate, useParams } from 'react-router-dom';
import api from '../api';
import { logger } from '../utils/logger';
import { Button, Spin, Select, Input, Tag, Alert, Card, Modal, Checkbox, Dropdown, Space, Form, Table, Popconfirm, Collapse, Badge, Tabs, Progress, Row, Col, Statistic, App } from 'antd';
import {
  EditOutlined,
  CheckOutlined,
  EyeOutlined,
  DownloadOutlined,
  DiffOutlined,
  FileProtectOutlined,
  FileTextOutlined,
  FileSearchOutlined,
  UserOutlined,
  AppstoreOutlined,
  CalculatorOutlined,
  SearchOutlined,
  ArrowLeftOutlined,
  PlusOutlined,
  DeleteOutlined,
  CloseCircleOutlined,
  HistoryOutlined,
  WarningOutlined,
  SafetyCertificateOutlined,
  HeartOutlined,
  CheckCircleOutlined,
  FlagOutlined,
  FileExclamationOutlined
} from '@ant-design/icons';
import type { MenuProps } from 'antd';
import EnhancedModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
import ModuleKnowledgeToggle from '../components/ModuleKnowledgeToggle';
import ContractHealthAssessment from '../components/ContractHealthAssessment';
import './ContractReview.css';

const { TextArea } = Input;
const { Panel } = Collapse;

interface Metadata {
  contract_name?: string;
  parties?: string | string[];
  amount?: string;
  contract_type?: string;
  core_terms?: string;
  legal_features?: {
    transaction_structures?: string[];
  };
  entity_risks?: Record<string, EntityRiskInfo>;
}

interface EntityRiskInfo {
  entity_name: string;
  entity_type: string;
  risk_level: 'High' | 'Medium' | 'Low' | 'None';
  risk_items: Array<{
    type: string;
    description: string;
    detail: string;
  }>;
}

interface ReviewItem {
  id: number;
  issue_type: string;
  quote: string;
  explanation: string;
  suggestion: string;
  legal_basis?: string; // 审查依据
  severity: string; // Low/Medium/High/Critical
  action_type: string; // Revision 或 Alert
  item_status: string;
  entity_risk?: EntityRiskInfo; // 关联的主体风险信息
  related_entities?: string[]; // 关联的主体名称列表
}

// ⭐ 工具函数：解析当事人字符串为数组
const parsePartiesString = (parties: string | string[] | undefined): string[] => {
  // 如果已经是数组，直接返回
  if (Array.isArray(parties)) {
    return parties;
  }

  // 如果是空值，返回空数组
  if (!parties) {
    return [];
  }

  // 如果是字符串，解析为多个当事人
  // 格式："甲方：雇主；乙方：贵州省秦佳琪家政服务有限公司"
  const partyArray: string[] = [];
  const parts = parties.split(/[；;]/);

  for (const part of parts) {
    const trimmed = part.trim();
    if (trimmed) {
      partyArray.push(trimmed);
    }
  }

  return partyArray.length > 0 ? partyArray : [parties];
};

const ContractReview: React.FC = () => {
  const navigate = useNavigate();
  const { contractId: urlContractId } = useParams<{ contractId?: string }>();
  const { message: messageApi } = App.useApp(); // 【修复】使用 App.useApp() 替代静态 message
  const [editorConfig, setEditorConfig] = useState<any>(null);
  const [contractId, setContractId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState<'upload' | 'metadata' | 'reviewing' | 'results'>('upload');

  const [editedMetadata, setEditedMetadata] = useState<Metadata>({});
  const [stance, setStance] = useState<'甲方' | '乙方'>('甲方');
  const [reviews, setReviews] = useState<ReviewItem[]>([]);

  // ⭐ 新增：元数据提取状态
  const [metadataExtracting, setMetadataExtracting] = useState(false);
  const [metadataExtracted, setMetadataExtracted] = useState(false);

  // ⭐ 新增：文件上传状态（独立于 editorConfig）
  const [fileUploaded, setFileUploaded] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<string>('');
  const [showUploadProgress, setShowUploadProgress] = useState(false);

  // ⭐ 新增：会话恢复状态
  const [hasPendingSession, setHasPendingSession] = useState(false);
  const [pendingSessionInfo, setPendingSessionInfo] = useState<any>(null);

  // ⭐ 新增：监控 showUploadProgress 状态变化
  useEffect(() => {
    console.log('📊 showUploadProgress 状态变化:', showUploadProgress, 'uploadProgressRef.current:', uploadProgressRef.current);
  }, [showUploadProgress]);

  // 自定义审查规则状态
  const [useCustomRules, setUseCustomRules] = useState(false);
  const [customRulesCount, setCustomRulesCount] = useState(0);
  const [customRulesModalVisible, setCustomRulesModalVisible] = useState(false);
  const [customRuleCreateModalVisible, setCustomRuleCreateModalVisible] = useState(false);
  const [customRules, setCustomRules] = useState<any[]>([]);
  const [customRuleForm] = Form.useForm();

  // 交易结构选择状态
  const [selectedTransactionStructures, setSelectedTransactionStructures] = useState<string[]>([]);

  // 编辑模态框状态
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingItem, setEditingItem] = useState<ReviewItem | null>(null);
  const [editExplanation, setEditExplanation] = useState('');
  const [editSuggestion, setEditSuggestion] = useState('');

  // 选中状态
  const [selectedItemIds, setSelectedItemIds] = useState<number[]>([]);

  const [applyingRevisions, setApplyingRevisions] = useState(false);

  // ⭐ 新增：结果页签状态
  const [activeResultTab, setActiveResultTab] = useState<string>('suggestions'); // 默认显示"修改意见"

  // ⭐ 新增：审查进度状态
  const [reviewProgress, setReviewProgress] = useState<string>('');

  const connectorRef = useRef<any>(null);

  // ⭐ 新增：使用 ref 跟踪上传状态，确保立即响应
  const uploadProgressRef = useRef(false);

  // ⭐ 新增：记录上传开始时间，用于最小显示时间控制
  const uploadStartTimeRef = useRef<number>(0);

  // 获取自定义规则列表
  const fetchCustomRules = async () => {
    try {
      const res = await api.get('/admin/rules', { params: { category: 'custom' } });
      const rules = res.data.filter((r: any) => !r.is_system); // 只显示非系统规则
      setCustomRules(rules);
      setCustomRulesCount(rules.length);
    } catch (error) {
      console.error('获取自定义规则失败', error);
    }
  };

  // ⭐ 新增：清除会话，开始新任务
  const startNewTask = () => {
    // 清除 localStorage 中的会话数据
    localStorage.removeItem('contractReview_contractId');
    localStorage.removeItem('contractReview_step');

    // 重置所有状态
    setContractId(null);
    setStep('upload');
    setEditorConfig(null);
    setEditedMetadata({});
    setStance('甲方');
    setReviews([]);
    setMetadataExtracting(false);
    setMetadataExtracted(false);
    setFileUploaded(false);
    setProcessingStatus('');
    setShowUploadProgress(false);
    setSelectedTransactionStructures([]);
    setActiveResultTab('suggestions');
    setReviewProgress('');

    // 清除会话提示
    setHasPendingSession(false);
    setPendingSessionInfo(null);

    messageApi.success('已开始新任务');
  };

  // ⭐ 新增：恢复旧会话
  const restorePendingSession = async () => {
    if (!pendingSessionInfo) return;

    const { savedContractId, status, metadata, canLoadEditor } = pendingSessionInfo;

    try {
      setContractId(parseInt(savedContractId));

      // 恢复编辑器配置
      if (canLoadEditor) {
        const cfgRes = await api.get(`/contract-review/${savedContractId}/onlyoffice-config`);
        const cfg = cfgRes.data.config;
        const tkn = cfgRes.data.token;
        setEditorConfig({ ...cfg, token: tkn });
      }

      // 恢复元数据
      if (metadata) {
        setEditedMetadata(prev => ({
          ...prev,
          contract_name: metadata.contract_name || prev.contract_name || '',
          parties: parsePartiesString(metadata.parties),
          amount: metadata.amount || prev.amount || '',
          contract_type: metadata.contract_type || prev.contract_type || '',
          core_terms: metadata.core_terms || prev.core_terms || '',
          legal_features: metadata.legal_features || prev.legal_features,
        }));
        setMetadataExtracting(false);
        setMetadataExtracted(true);
      }

      // 恢复步骤
      const savedStep = localStorage.getItem('contractReview_step');
      if (savedStep) {
        setStep(savedStep as any);
      }

      setHasPendingSession(false);
      setPendingSessionInfo(null);
      messageApi.success('已恢复上次的会话');
    } catch (error) {
      console.error('恢复会话失败', error);
      messageApi.error('恢复会话失败，请开始新任务');
      startNewTask();
    }
  };

  // 组件挂载时获取自定义规则
  useEffect(() => {
    const checkPendingSession = async () => {
      try {
        // 从 localStorage 读取上次保存的 contractId
        const savedContractId = localStorage.getItem('contractReview_contractId');
        if (!savedContractId) return;

        console.log('🔍 检测到上次的会话，contractId:', savedContractId);

        // 查询合同处理状态
        const statusRes = await api.get(`/contract-review/${savedContractId}/processing-status`);
        const { processing_status, can_load_editor, has_metadata, metadata } = statusRes.data;

        console.log('🔍 上次会话状态:', processing_status, 'can_load_editor:', can_load_editor, 'has_metadata:', has_metadata);

        // ⭐ 修改：不自动恢复，而是设置待恢复会话信息，让用户选择
        setPendingSessionInfo({
          savedContractId,
          status: processing_status,
          canLoadEditor: can_load_editor,
          hasMetadata: has_metadata,
          metadata
        });
        setHasPendingSession(true);

        messageApi.info('检测到上次的未完成任务，可在下方选择继续或开始新任务');
      } catch (error) {
        console.error('检查会话失败', error);
        // 清除无效的会话数据
        localStorage.removeItem('contractReview_contractId');
        localStorage.removeItem('contractReview_step');
      }
    };

    checkPendingSession();
  }, []);

  // ⭐ 新增：保存关键状态到 localStorage
  useEffect(() => {
    if (contractId) {
      localStorage.setItem('contractReview_contractId', contractId.toString());
    }
  }, [contractId]);

  // ⭐ 新增：处理 URL 参数中的 contractId（用于飞书通知跳转）
  useEffect(() => {
    const loadContractFromUrl = async () => {
      if (!urlContractId) return;

      const parsedContractId = parseInt(urlContractId);
      if (isNaN(parsedContractId)) {
        messageApi.error('无效的合同 ID');
        navigate('/contract/review');
        return;
      }

      console.log('📌 从 URL 加载合同:', parsedContractId);
      setLoading(true);

      try {
        // 设置合同 ID
        setContractId(parsedContractId);

        // 获取处理状态
        const statusRes = await api.get(`/contract-review/${parsedContractId}/processing-status`);
        const { processing_status, can_load_editor, has_metadata, metadata } = statusRes.data;

        console.log('📌 URL 加载合同状态:', processing_status, 'can_load_editor:', can_load_editor);

        // 获取编辑器配置（如果可用）
        if (can_load_editor) {
          const cfgRes = await api.get(`/contract-review/${parsedContractId}/onlyoffice-config`);
          const cfg = cfgRes.data.config;
          const tkn = cfgRes.data.token;
          setEditorConfig({ ...cfg, token: tkn });
        }

        // 设置元数据（如果有）
        if (has_metadata && metadata) {
          setEditedMetadata(prev => ({
            ...prev,
            contract_name: metadata.contract_name || prev.contract_name || '',
            parties: parsePartiesString(metadata.parties),
            amount: metadata.amount || prev.amount || '',
            contract_type: metadata.contract_type || prev.contract_type || '',
            core_terms: metadata.core_terms || prev.core_terms || '',
            legal_features: metadata.legal_features || prev.legal_features,
          }));
          setMetadataExtracting(false);
          setMetadataExtracted(true);
        }

        // 检查审查状态
        const reviewRes = await api.get(`/contract-review/${parsedContractId}/review-results`);
        const { status, review_items } = reviewRes.data;

        if (status === 'waiting_human' || status === 'approved') {
          // 审查完成，显示结果
          setReviews(review_items || []);
          setStance(reviewRes.data.stance || '甲方');
          setStep('results');
          messageApi.success(`审查已完成，发现 ${review_items?.length || 0} 个风险点`);
        } else if (status === 'reviewing' || status === 'processing') {
          // 审查中
          setStep('reviewing');
          setReviewProgress('正在审查中...');
          // 开始轮询结果
          pollReviewResults();
        } else {
          // 未开始审查，显示元数据确认步骤
          setStep('metadata');
        }

      } catch (error: any) {
        console.error('加载合同失败', error);
        messageApi.error(error.response?.data?.detail || '加载合同失败');
        // 失败后跳转到普通上传页面
        navigate('/contract/review');
      } finally {
        setLoading(false);
      }
    };

    loadContractFromUrl();
  }, [urlContractId]);

  useEffect(() => {
    localStorage.setItem('contractReview_step', step);
  }, [step]);

  // 创建自定义规则
  const handleCreateCustomRule = async (values: any) => {
    try {
      await api.post('/admin/rules', {
        ...values,
        rule_category: 'custom',
        is_system: false
      });
      messageApi.success('自定义规则创建成功');
      fetchCustomRules();
      setCustomRuleCreateModalVisible(false);
    } catch (error: any) {
      messageApi.error(error.response?.data?.detail || '创建失败');
    }
  };

  // 删除自定义规则
  const handleDeleteCustomRule = async (id: number) => {
    try {
      await api.delete(`/admin/rules/${id}`);
      messageApi.success('删除成功');
      fetchCustomRules();
    } catch (error: any) {
      messageApi.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 切换自定义规则启用状态
  const handleToggleCustomRule = async (id: number) => {
    try {
      await api.put(`/admin/rules/${id}/toggle`);
      messageApi.success('状态更新成功');
      fetchCustomRules();
    } catch (error: any) {
      messageApi.error(error.response?.data?.detail || '更新失败');
    }
  };

  // 1. 文件上传
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const fileName = file.name.toLowerCase();
    // 支持更多格式：.doc, .docx, .pdf, .txt, .rtf, .odt
    // 支持图片格式：.jpg, .jpeg, .png, .bmp, .tiff, .gif
    const supportedFormats = [
      '.doc', '.docx', '.pdf', '.txt', '.rtf', '.odt',
      '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif'
    ];
    const isSupported = supportedFormats.some(ext => fileName.endsWith(ext));

    if (!isSupported) {
      messageApi.error('支持的格式：文档 (.doc/.docx/.pdf/.txt/.rtf/.odt) 或图片 (.jpg/.png/.bmp)');
      return;
    }

    // 检查是否为图片格式
    const isImage = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.gif'].some(ext => fileName.endsWith(ext));

    // 提示用户
    if (isImage) {
      messageApi.info('正在上传图片文件，系统将使用 OCR 识别文字内容...');
    } else if (fileName.endsWith('.doc') || fileName.endsWith('.pdf') ||
        fileName.endsWith('.txt') || fileName.endsWith('.rtf') ||
        fileName.endsWith('.odt')) {
      messageApi.info(`正在上传 ${fileName.split('.').pop()} 文件，系统将自动转换为 .docx 格式...`);
    }

    setLoading(true);

    try {
      // ⭐ 立即显示上传进度界面（使用 flushSync 强制同步更新）
      console.log('🔵 开始上传文件，设置上传进度状态');
      uploadStartTimeRef.current = Date.now(); // ⭐ 记录上传开始时间

      // ⭐ 先设置 ref（立即生效）
      uploadProgressRef.current = true;

      // ⭐ 使用 flushSync 强制同步更新状态，确保立即渲染
      flushSync(() => {
        setShowUploadProgress(true);
        setFileUploaded(true);
      });

      console.log('🔵 上传进度状态已同步设置，showUploadProgress:', showUploadProgress, 'uploadProgressRef.current:', uploadProgressRef.current);

      const res = await api.uploadContract(file); // 新接口：/api/contract-review/upload
      const contract_id = res.data.contract_id;

      console.log('上传成功，contract_id:', contract_id, '响应数据:', res.data);

      setContractId(contract_id);

      // 显示预处理信息
      if (res.data.preprocess_info) {
        const { original_format } = res.data.preprocess_info;
        if (original_format && original_format !== 'docx') {
          messageApi.success(`文件上传成功！正在转换 ${original_format.toUpperCase()} 格式...`);
        } else {
          messageApi.success('文件上传成功！正在后台处理...');
        }
      } else {
        messageApi.success('文件上传成功！正在后台处理...');
      }

      // 上传接口已经返回了 config 和 token，直接使用
      if (res.data.config && res.data.token) {
        setEditorConfig({
          ...res.data.config,
          token: res.data.token
        });
        console.log('OnlyOffice 配置已设置 (来自上传响应)');

        // ⭐ 修复：即使上传响应包含 config，也要遵守最小显示时间
        const minDisplayTime = 3000; // 3秒
        const elapsedTime = Date.now() - uploadStartTimeRef.current;

        if (elapsedTime < minDisplayTime) {
          const remainingTime = minDisplayTime - elapsedTime;
          console.log(`⏳ 上传响应包含 config，但等待 ${remainingTime}ms 后隐藏上传进度界面`);
          setTimeout(() => {
            // ⭐ 使用 flushSync 强制同步隐藏
            uploadProgressRef.current = false;
            flushSync(() => {
              setShowUploadProgress(false);
            });
            console.log('✅ 上传进度界面已隐藏（最小显示时间已过）');
          }, remainingTime);
        } else {
          // ⭐ 配置设置后，立即隐藏上传进度（使用 flushSync）
          uploadProgressRef.current = false;
          flushSync(() => {
            setShowUploadProgress(false);
          });
        }
      }
      // 如果上传响应没有配置，异步等待处理完成后再获取
      else {
        // ⭐ 优化：立即显示文件信息，后台异步获取编辑器配置
        // 不阻塞界面显示，用户可以立即看到文件已上传
        messageApi.info('文件上传成功，正在后台处理格式和预览...');

        // 后台异步轮询获取配置，不阻塞界面
        const pollProcessingComplete = async (retries = 0) => {
          const MAX_RETRIES = 30; // 最多等待60秒

          if (retries >= MAX_RETRIES) {
            console.warn('后台处理轮询超时，尝试获取配置');
            try {
              const cfgRes = await api.get(`/contract-review/${contract_id}/onlyoffice-config`);
              const cfg = cfgRes.data.config;
              const tkn = cfgRes.data.token;
              setEditorConfig({ ...cfg, token: tkn });
              console.log('OnlyOffice 配置已设置 (超时后获取)');
            } catch (err) {
              console.warn('超时后仍无法获取 OnlyOffice 配置', err);
            }
            return;
          }

          try {
            // 查询处理状态
            const statusRes = await api.get(`/contract-review/${contract_id}/processing-status`);
            const { processing_status, can_load_editor } = statusRes.data;

            // ⭐ 更新处理状态，用于显示不同提示
            setProcessingStatus(processing_status);

            console.log(`后台处理状态 (第${retries + 1}次):`, processing_status, 'can_load_editor:', can_load_editor);

            // ⭐ 关键优化：只要 docx 格式转换完成就可以加载编辑器（不需要等PDF和元数据）
            if (can_load_editor) {
              const cfgRes = await api.get(`/contract-review/${contract_id}/onlyoffice-config`);
              const cfg = cfgRes.data.config;
              const tkn = cfgRes.data.token;
              setEditorConfig({ ...cfg, token: tkn });

              // ⭐ 修复：遵守最小显示时间规则
              const minDisplayTime = 3000; // 3秒
              const elapsedTime = Date.now() - uploadStartTimeRef.current;

              if (elapsedTime < minDisplayTime) {
                const remainingTime = minDisplayTime - elapsedTime;
                console.log(`⏳ pollProcessingComplete: 等待 ${remainingTime}ms 后隐藏上传进度界面`);
                setTimeout(() => {
                  // ⭐ 使用 flushSync 强制同步隐藏
                  uploadProgressRef.current = false;
                  flushSync(() => {
                    setShowUploadProgress(false);
                  });
                  console.log('✅ 上传进度界面已隐藏（pollProcessingComplete 最小显示时间已过）');
                }, remainingTime);
              } else {
                // ⭐ 配置设置后，隐藏上传进度（使用 flushSync）
                uploadProgressRef.current = false;
                flushSync(() => {
                  setShowUploadProgress(false);
                });
              }

              console.log('OnlyOffice 配置已设置 (docx转换完成即可加载)');

              // 根据处理状态显示不同的提示
              if (processing_status === 'completed') {
                messageApi.success('文件处理完成，可以开始编辑');
              } else if (processing_status === 'metadata_extraction') {
                messageApi.info('编辑器已就绪，正在提取合同元数据...');
              } else if (processing_status === 'pdf_generation') {
                messageApi.info('编辑器已就绪，正在生成PDF预览...');
              }
              return; // ✅ 配置已设置，退出轮询
            } else {
              // 继续等待
              setTimeout(() => pollProcessingComplete(retries + 1), 2000);
            }
          } catch (err) {
            console.warn('查询处理状态失败，2秒后重试', err);
            setTimeout(() => pollProcessingComplete(retries + 1), 2000);
          }
        };

        // 异步轮询，不阻塞界面
        pollProcessingComplete();
      }

      setStep('metadata');

      // ⭐ 初始化元数据提取状态
      setMetadataExtracting(true);
      setMetadataExtracted(false);

      // ⭐ 优化：使用新的处理状态端点轮询
      if (contract_id) {
        const pollProcessingStatus = async (retries = 0) => {
          const MAX_RETRIES = 45; // 最多等待90秒

          // 随着重试次数增加，显示更友好的提示
          const getProgressMessage = (status: string, retryCount: number) => {
            if (retryCount < 5) return '文件上传成功，正在处理...';
            if (status === 'format_conversion') return '正在转换文件格式（.doc → .docx）...';
            if (status === 'pdf_generation') return '正在生成PDF预览...';
            if (status === 'metadata_extraction') return '正在提取合同元数据...';
            if (retryCount < 15) return '合同信息提取中，请稍候...';
            if (retryCount < 30) return '正在分析合同条款（可能需要较长时间）...';
            return '仍在处理中，感谢您的耐心等待...';
          };

          if (retries > MAX_RETRIES) {
            console.warn('处理状态轮询超时');
            setMetadataExtracting(false);
            // ⭐ 超时时也隐藏上传进度（使用 flushSync）
            uploadProgressRef.current = false;
            flushSync(() => {
              setShowUploadProgress(false);
            });
            messageApi.warning({
              content: '文件处理耗时较长，可能是文件格式较复杂。您可以稍后刷新页面或继续填写合同信息。',
              duration: 6,
            });
            return;
          }

          try {
            // ⭐ 使用新的处理状态端点
            const statusRes = await api.get(`/contract-review/${contract_id}/processing-status`);
            console.log(`轮询处理状态 (第${retries + 1}次):`, statusRes.data);

            const { processing_status, can_load_editor, has_metadata, metadata, error_message } = statusRes.data;

            // ⭐ 关键修复：在上传后的前3秒内，不允许隐藏上传进度界面
            // 这样用户至少能看到3秒的"文件已上传"提示
            if (can_load_editor && !editorConfig) {
              console.log('✅ 检测到可以加载编辑器');

              // ⭐ 立即获取并设置 editorConfig，确保隐藏上传进度前 editorConfig 已设置
              const cfgRes = await api.get(`/contract-review/${contract_id}/onlyoffice-config`);
              const cfg = cfgRes.data.config;
              const tkn = cfgRes.data.token;
              setEditorConfig({ ...cfg, token: tkn });
              console.log('✅ OnlyOffice 配置已设置，editorConfig:', { ...cfg, token: tkn });

              // ⭐ 至少显示3秒的上传进度界面，确保用户能看到文件已上传的提示
              const minDisplayTime = 3000; // 3秒
              const elapsedTime = Date.now() - uploadStartTimeRef.current;

              console.log(`⏱️ 已显示 ${elapsedTime}ms，最小显示时间 ${minDisplayTime}ms`);

              if (elapsedTime < minDisplayTime) {
                const remainingTime = minDisplayTime - elapsedTime;
                console.log(`⏳ 等待 ${remainingTime}ms 后隐藏上传进度界面`);

                // ⭐ 延迟隐藏上传进度（使用 flushSync）
                setTimeout(() => {
                  uploadProgressRef.current = false;
                  flushSync(() => {
                    setShowUploadProgress(false);
                  });
                  console.log('✅ 上传进度界面已隐藏（最小显示时间已过）');
                }, remainingTime);
              } else {
                console.log('✅ 已超过最小显示时间，立即隐藏上传进度界面');
                uploadProgressRef.current = false;
                flushSync(() => {
                  setShowUploadProgress(false);
                });
              }

              // 根据处理状态显示不同的提示
              if (processing_status === 'completed') {
                messageApi.success('文件处理完成，可以开始编辑');
              } else if (processing_status === 'metadata_extraction') {
                messageApi.info('编辑器已就绪，正在提取合同元数据...');
              } else if (processing_status === 'pdf_generation') {
                messageApi.info('编辑器已就绪，正在生成PDF预览...');
              }
            }

            // 显示进度提示（每10次显示一次）
            if (retries > 0 && retries % 10 === 0) {
              messageApi.info(getProgressMessage(processing_status, retries), 2);
            }

            // 检查是否有错误
            if (processing_status === 'error') {
              console.error('后台处理失败:', error_message);
              setMetadataExtracting(false);
              // ⭐ 出错时也隐藏上传进度（使用 flushSync）
              uploadProgressRef.current = false;
              flushSync(() => {
                setShowUploadProgress(false);
              });
              messageApi.error(`文件处理失败: ${error_message}`);
              return;
            }

            // 检查元数据是否已提取完成
            if (has_metadata && metadata) {
              console.log('✅ 元数据已就绪:', metadata);

              // ⭐ 更新元数据状态，解析当事人字符串为数组
              setEditedMetadata(prev => {
                const newState = {
                  ...prev,
                  contract_name: metadata.contract_name || prev.contract_name || '',
                  parties: parsePartiesString(metadata.parties), // ⭐ 解析为数组
                  amount: metadata.amount || prev.amount || '',
                  contract_type: metadata.contract_type || prev.contract_type || '',
                  core_terms: metadata.core_terms || prev.core_terms || '',
                  legal_features: metadata.legal_features || prev.legal_features,
                };
                return newState;
              });

              // ⭐ 更新提取状态
              setMetadataExtracting(false);
              setMetadataExtracted(true);

              messageApi.success('合同信息提取成功，可修改后确认');
              return; // ✅ 元数据提取完成，停止轮询
            } else {
              // 继续轮询
              console.log(`⏳ 处理中 (${processing_status})，2秒后重试...`);
              setTimeout(() => pollProcessingStatus(retries + 1), 2000);
            }
          } catch (err) {
            console.error('检查处理状态失败', err);
            // 即使出错也继续重试
            setTimeout(() => pollProcessingStatus(retries + 1), 2000);
          }
        };

        // 立即开始第一次轮询
        pollProcessingStatus();
      }
    } catch (error: any) {
      console.error("上传失败", error);
      messageApi.error(error.response?.data?.detail || "文件上传失败");
    } finally {
      setLoading(false);
    }
  };

  // 3. 开始深度审查
  const startDeepReview = async () => {
    if (!contractId) return;

    setLoading(true);
    setStep('reviewing');
    setReviewProgress('📋 正在启动审查任务...'); // ⭐ 初始化进度提示

    // ⭐ 显示审查开始提示
    messageApi.info({
      content: '正在启动合同深度审查...',
      duration: 3
    });

    try {
      // ⭐ 处理当事人数据：将数组转换为字符串
      const processedMetadata = { ...editedMetadata };
      if (Array.isArray(editedMetadata.parties)) {
        processedMetadata.parties = editedMetadata.parties.join('; ');
      }

      // ⭐ 调用新的审查API，传递交易结构参数
      const formData = new FormData();
      formData.append('stance', stance);
      formData.append('enable_custom_rules', useCustomRules.toString());
      formData.append('use_langgraph', 'true');
      formData.append('use_celery', 'true'); // ⭐ 改为异步模式

      // ⭐ 修复：使用JSON字符串格式传递交易结构列表
      if (selectedTransactionStructures.length > 0) {
        formData.append('transaction_structures', JSON.stringify(selectedTransactionStructures));
        console.log('📤 发送交易结构:', JSON.stringify(selectedTransactionStructures));
      }

      // ⭐ 修复：将元数据作为JSON字符串发送（后端会解析）
      formData.append('updated_metadata', JSON.stringify(processedMetadata));
      console.log('📤 发送元数据:', processedMetadata);

      const response = await api.post(`/contract-review/${contractId}/deep-review`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      // ⭐ 显示任务已提交提示
      if (response.data.success) {
        messageApi.success('深度审查任务已提交，正在后台加载审查规则并分析合同...');
      }

      // 轮询结果
      pollReviewResults();
    } catch (error: any) {
      console.error("审查启动失败", error);
      console.error("错误详情:", error.response?.data);
      setReviewProgress(''); // ⭐ 清除进度提示
      messageApi.error(error.response?.data?.detail || "审查启动失败");
      setStep('metadata');
    } finally {
      setLoading(false);
    }
  };

  // 4. 轮询审查结果
  const pollReviewResults = async () => {
    if (!contractId) return;

    let pollCount = 0;
    const maxPolls = 150; // 最多轮询150次（7.5分钟）

    // ⭐ 进度提示状态
    let currentProgressStep = 0;
    const progressSteps = [
      { message: '📋 正在加载审查规则...', threshold: 0 },
      { message: '🔍 正在分析合同条款...', threshold: 10 },
      { message: '⚠️ 正在识别风险点...', threshold: 30 },
      { message: '📝 正在生成审查报告...', threshold: 60 },
      { message: '🎯 正在优化审查结果...', threshold: 90 }
    ];

    const poll = async () => {
      try {
        pollCount++;

        // ⭐ 更新进度提示（每5秒更新一次）
        const currentStep = progressSteps.find((step, index) => {
          return pollCount >= step.threshold &&
                 (index === progressSteps.length - 1 || pollCount < progressSteps[index + 1].threshold);
        });

        if (currentStep && currentProgressStep !== progressSteps.indexOf(currentStep)) {
          currentProgressStep = progressSteps.indexOf(currentStep);
          // ⭐ 更新状态以便在UI中显示
          setReviewProgress(currentStep.message);
          messageApi.loading({
            content: currentStep.message,
            duration: 4,
            key: 'review-progress'
          });
          console.log(`[审查进度] ${currentStep.message} (第${pollCount}次轮询)`);
        }

        const res = await api.getReviewResults(contractId);
        const { status, review_items } = res.data;

        console.log(`[审查轮询] 第${pollCount}次: status=${status}, items=${review_items?.length || 0}`);

        if (status === 'waiting_human' || status === 'approved') {
          setReviews(review_items);
          setStep('results');
          setReviewProgress(''); // ⭐ 清除进度提示
          messageApi.success({
            content: `✅ 审查完成！发现 ${review_items.length} 个风险点`,
            duration: 5
          });
          return; // ✅ 结束轮询
        } else if (status === 'processing' || status === 'pending' || status === 'reviewing' || status === 'draft') {
          // 继续轮询
          if (pollCount < maxPolls) {
            setTimeout(poll, 3000);
          } else {
            setReviewProgress(''); // ⭐ 清除进度提示
            messageApi.error('审查超时，请稍后刷新查看结果');
          }
        } else {
          // 未知状态，停止轮询
          setReviewProgress('');
          messageApi.warning(`未知状态: ${status}，请刷新页面重试`);
        }
      } catch (error) {
        console.error("获取结果失败", error);

        if (pollCount < maxPolls) {
          setTimeout(poll, 5000);
        } else {
          setReviewProgress(''); // ⭐ 清除进度提示
          messageApi.error('获取审查结果超时');
        }
      }
    };

    poll();
  };

  // 5. 打开编辑模态框
  const openEditModal = (item: ReviewItem) => {
    setEditingItem(item);
    setEditExplanation(item.explanation);
    setEditSuggestion(item.suggestion);
    setEditModalVisible(true);
  };

  // 6. 保存编辑的审查意见
  const saveEditItem = async () => {
    if (!editingItem) return;

    try {
      await api.updateReviewItem(editingItem.id, {
        explanation: editExplanation,
        suggestion: editSuggestion
      });

      // 更新本地状态
      setReviews(reviews.map(item =>
        item.id === editingItem.id
          ? { ...item, explanation: editExplanation, suggestion: editSuggestion }
          : item
      ));

      messageApi.success('审查意见已更新');
      setEditModalVisible(false);
    } catch (error: any) {
      console.error('更新审查意见失败', error);
      messageApi.error(error.response?.data?.detail || '更新失败');
    }
  };

  // 7. 应用修订到文档
  const applyRevisions = async (itemIds?: number[]) => {
    if (!contractId) return;

    const idsToApply = itemIds || selectedItemIds;
    if (idsToApply.length === 0) {
      messageApi.warning('请先选择要应用的修改意见');
      return;
    }

    setApplyingRevisions(true);
    try {
      const res = await api.applyRevisions(contractId, idsToApply, false);

      if (res.data.config && res.data.token) {
        // 直接替换主编辑器的配置，显示修订版文档
        setEditorConfig({
          ...res.data.config,
          token: res.data.token
        });

        // 根据文件格式显示不同消息
        const formatMsg = res.data.converted
          ? ` (原文件格式: ${res.data.original_format?.toUpperCase() || 'PDF'}，已自动转换为 Word 格式)`
          : '';

        messageApi.success(`已应用 ${res.data.applied_count} 条修订建议${formatMsg}` +
          (res.data.not_found_count > 0 ? `，${res.data.not_found_count} 条未找到原文` : ''));

        // 显示修订样式说明
        messageApi.info('修订样式：红色删除线 = 原文，黄色高亮下划线 = 修订内容');
      } else {
        messageApi.error('生成修订文档失败');
      }
    } catch (error: any) {
      console.error('应用修订失败', error);
      messageApi.error(error.response?.data?.detail || '应用修订失败');
    } finally {
      setApplyingRevisions(false);
    }
  };

  // 8. 全选/取消全选
  const toggleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedItemIds(reviews.map(r => r.id));
    } else {
      setSelectedItemIds([]);
    }
  };

  // 9. 切换单个选中状态
  const toggleSelectItem = (itemId: number, checked: boolean) => {
    if (checked) {
      setSelectedItemIds([...selectedItemIds, itemId]);
    } else {
      setSelectedItemIds(selectedItemIds.filter(id => id !== itemId));
    }
  };

  // 10. 点击高亮定位到原文
  const highlightInOriginal = (quote: string) => {
    console.log('[高亮定位] 尝试定位:', quote);

    const trimmedQuote = quote.trim();

    if (!trimmedQuote) {
      messageApi.warning("审查意见原文为空");
      return;
    }

    // ⭐ 优化：提取关键词用于模糊匹配
    const keywords = trimmedQuote
      .replace(/[，。；：！？、""''（）【】《》\s]/g, ' ')  // 移除标点符号
      .split(' ')
      .filter(word => word.length > 1)  // 过滤单字
      .slice(0, 3);  // 取前3个关键词

    const searchQuery = keywords.length > 0 ? keywords[0] : trimmedQuote;

    // 方法1: 尝试使用 connector (如果可用)
    if (connectorRef.current && typeof connectorRef.current.executeMethod === 'function') {
      console.log('[高亮定位] 使用 executeMethod 方法');
      try {
        // OnlyOffice 的 executeMethod 可以调用内置方法
        connectorRef.current.executeMethod("SearchAndReplace", {
          "searchString": searchQuery,
          "replaceString": searchQuery,
          "matchCase": false
        }).then(() => {
          messageApi.success(`已定位到关键词: "${searchQuery}"${keywords.length > 1 ? ` (其他: ${keywords.slice(1).join(', ')})` : ''}`);
        }).catch((err: any) => {
          console.warn('[高亮定位] executeMethod 失败:', err);
          // 降级到方法2
          fallbackToCallCommand();
        });
        return;
      } catch (err) {
        console.warn('[高亮定位] executeMethod 异常:', err);
        // 继续尝试方法2
      }
    }

    // 方法2: 尝试使用 callCommand (Builder API)
    const fallbackToCallCommand = () => {
      if (connectorRef.current && typeof connectorRef.current.callCommand === 'function') {
        console.log('[高亮定位] 使用 callCommand 方法');
        try {
          connectorRef.current.callCommand(function() {
            // 在文档编辑器上下文中执行
            // @ts-ignore - OnlyOffice Builder API 全局对象
            if (typeof Api === 'undefined' || !Api.GetDocument) {
              console.warn('[高亮定位] Builder API 不可用');
              return -1;
            }

            // @ts-ignore
            const oDocument = Api.GetDocument();

            // ⭐ 优化：尝试多个关键词搜索
            let nFoundCount = 0;
            const nParagraphsCount = oDocument.GetElementsCount();
            const searchTerms = keywords.length > 0 ? keywords : [trimmedQuote];

            // 先尝试精确匹配
            for (let nPara = 0; nPara < nParagraphsCount; nPara++) {
              const oParagraph = oDocument.GetElement(nPara);
              const sParaText = oParagraph.GetText ? oParagraph.GetText() : "";

              if (sParaText) {
                // 检查是否包含搜索词
                for (const term of searchTerms) {
                  if (sParaText.indexOf(term) !== -1) {
                    // 找到匹配，尝试高亮
                    const nStartPos = sParaText.indexOf(term);
                    const nEndPos = nStartPos + term.length;

                    if (oParagraph.GetRange) {
                      const oRange = oParagraph.GetRange(nStartPos, nEndPos);

                      // 定位到第一个匹配项
                      if (nFoundCount === 0) {
                        // @ts-ignore
                        if (oDocument.SetCurrentRange) {
                          oDocument.SetCurrentRange(oRange);
                        }
                      }

                      nFoundCount++;
                      break;  // 每个段落只计数一次
                    }
                  }
                }
              }
            }

            return nFoundCount;
          }, (result: any) => {
            const nFoundCount = typeof result === 'number' ? result : 0;
            if (nFoundCount > 0) {
              messageApi.success(`已定位到 ${nFoundCount} 处相关内容，关键词: ${keywords.join(', ')}`);
            } else {
              messageApi.info(`未在文档中找到精确匹配，建议关键词: ${keywords.join(', ')}`);
            }
          });
          return;
        } catch (err) {
          console.error('[高亮定位] callCommand 异常:', err);
        }
      }
    };

    fallbackToCallCommand();

    // 方法3: 最终降级 - 提示用户手动搜索
    setTimeout(() => {
      messageApi.info(`💡 提示：请按 Ctrl+F 在文档中搜索，建议关键词: ${keywords.join(', ')}`);
    }, 800);
  };

  // 11. 下载文件
  const handleDownload = async (docType: 'original' | 'revised') => {
    if (!contractId) return;

    try {
      const blob = await api.downloadContract(contractId, docType);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = docType === 'revised' ? '修订版合同.docx' : '原始合同.docx';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      messageApi.success(docType === 'revised' ? '修订版文件下载成功' : '原始文件下载成功');
    } catch (error: any) {
      console.error('下载失败', error);
      messageApi.error(error.response?.data?.detail || '下载失败');
    }
  };

  // 下载菜单项
  const downloadMenuItems: MenuProps['items'] = [
    {
      key: 'original',
      label: '下载原始文件',
      icon: <DownloadOutlined />,
      onClick: () => handleDownload('original'),
    },
    {
      key: 'revised',
      label: '下载修订版文件',
      icon: <DownloadOutlined />,
      onClick: () => handleDownload('revised'),
    },
  ];

  const onDocumentReady = (event: any) => {
    logger.office?.("ONLYOFFICE Ready!");
    try {
      const connector = event?.docEditor?.createConnector?.();
      connectorRef.current = connector ?? null;
    } catch (err) {
      console.error('创建 connector 失败', err);
      connectorRef.current = null;
    }
  };

  // ⭐ 新增：结果页签辅助函数
  // 获取带主体风险的审查项
  const getItemsWithEntityRisks = () => {
    return reviews.filter(r => r.entity_risk);
  };

  // 按严重程度分组统计
  const getSeverityStats = () => {
    return {
      Critical: reviews.filter(r => r.severity === 'Critical').length,
      High: reviews.filter(r => r.severity === 'High').length,
      Medium: reviews.filter(r => r.severity === 'Medium').length,
      Low: reviews.filter(r => r.severity === 'Low').length
    };
  };

  // 按问题类型分组统计
  const getIssueTypeStats = () => {
    const stats: Record<string, number> = {};
    reviews.forEach(r => {
      const type = r.issue_type;
      stats[type] = (stats[type] || 0) + 1;
    });
    return Object.entries(stats).sort((a, b) => b[1] - a[1]);
  };

  // 获取争议焦点（严重程度为 Critical 或 High 的项）
  const getControversyPoints = () => {
    return reviews.filter(r => r.severity === 'Critical' || r.severity === 'High');
  };

  // 获取缺失条款（action_type 为 'Alert' 的项）
  const getMissingClauses = () => {
    return reviews.filter(r => r.action_type === 'Alert');
  };

  // 当事人列表操作
  const addParty = () => {
    const current = parsePartiesString(editedMetadata.parties);
    current.push('');
    setEditedMetadata({ ...editedMetadata, parties: current });
  };

  const updateParty = (index: number, value: string) => {
    const current = parsePartiesString(editedMetadata.parties);
    current[index] = value;
    setEditedMetadata({ ...editedMetadata, parties: current });
  };

  const removeParty = (index: number) => {
    const current = parsePartiesString(editedMetadata.parties);
    current.splice(index, 1);
    setEditedMetadata({ ...editedMetadata, parties: current });
  };

  // 顶部导航栏 - 功能模块快捷入口
  const quickNavItems: MenuProps['items'] = [
    { key: 'divider1', type: 'divider' },
    {
      key: 'consultation',
      label: '智能咨询',
      icon: <UserOutlined />,
      onClick: () => navigate('/consultation')
    },
    {
      key: 'legal-analysis',
      label: '法律分析',
      icon: <FileSearchOutlined />,
      onClick: () => navigate('/analysis')
    },
    {
      key: 'legal-search',
      label: '法律检索',
      icon: <SearchOutlined />,
      onClick: () => messageApi.info('法律检索功能开发中')
    },
    { key: 'divider2', type: 'divider' },
    {
      key: 'template-search',
      label: '模板查询',
      icon: <AppstoreOutlined />,
      onClick: () => navigate('/contract')
    },
    {
      key: 'contract-generation',
      label: '合同生成',
      icon: <FileProtectOutlined />,
      onClick: () => navigate('/contract/generate')
    },
    {
      key: 'contract-review',
      label: '合同审查',
      icon: <DiffOutlined />,
      disabled: true,
      onClick: () => navigate('/contract/review')
    },
    { key: 'divider3', type: 'divider' },
    {
      key: 'case-analysis',
      label: '案件分析',
      icon: <FileSearchOutlined />,
      onClick: () => messageApi.info('案件分析功能开发中')
    },
    {
      key: 'document-drafting',
      label: '司法文书',
      icon: <FileTextOutlined />,
      onClick: () => messageApi.info('司法文书功能开发中')
    },
    { key: 'divider4', type: 'divider' },
    {
      key: 'document-processing',
      label: '文档处理',
      icon: <FileTextOutlined />,
      onClick: () => navigate('/document-processing')
    },
    {
      key: 'cost-calculation',
      label: '费用测算',
      icon: <CalculatorOutlined />,
      onClick: () => navigate('/cost-calculation')  // 导航到费用测算页面
    },
  ];

  // ⭐ 新增：标签页渲染函数
  // 渲染综合评估标签页
  const renderOverviewTab = () => {
    const severityStats = getSeverityStats();
    const issueTypeStats = getIssueTypeStats();

    return (
      <div style={{ padding: '16px 0' }}>
        {/* 风险分布统计 */}
        <Row gutter={24} style={{ marginBottom: 24 }}>
          <Col span={12}>
            <Card title="风险等级分布" bordered={false}>
              <div style={{ display: 'flex', justifyContent: 'space-around', marginTop: 16 }}>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 32, fontWeight: 'bold', color: '#ff4d4f' }}>{severityStats.Critical}</div>
                  <div style={{ color: '#666' }}>极严重</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 32, fontWeight: 'bold', color: '#faad14' }}>{severityStats.High}</div>
                  <div style={{ color: '#666' }}>高风险</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 32, fontWeight: 'bold', color: '#1890ff' }}>{severityStats.Medium}</div>
                  <div style={{ color: '#666' }}>中等</div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 32, fontWeight: 'bold', color: '#52c41a' }}>{severityStats.Low}</div>
                  <div style={{ color: '#666' }}>轻微</div>
                </div>
              </div>
            </Card>
          </Col>
          <Col span={12}>
            <Card title="问题类型分布" bordered={false}>
              <div style={{ marginTop: 16 }}>
                {issueTypeStats.slice(0, 5).map(([type, count]) => (
                  <div key={type} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, padding: '8px 12px', background: '#f5f5f5', borderRadius: '4px' }}>
                    <span>{type}</span>
                    <Tag color="blue">{count}</Tag>
                  </div>
                ))}
              </div>
            </Card>
          </Col>
        </Row>

        {/* 操作建议 */}
        <Alert
          message="操作建议"
          description={
            <div>
              <p>1. 优先处理极严重和高风险问题</p>
              <p>2. 查看"修改意见"标签页应用具体修订建议</p>
              <p>3. 关注"主体风险"标签页中的交易方风险信息</p>
              <p>4. 对于缺失条款，考虑与对方协商补充</p>
            </div>
          }
          type="info"
          showIcon
        />
      </div>
    );
  };

  // 渲染修改意见标签页（默认显示）
  const renderSuggestionsTab = () => {
    return (
      <div>
        <Alert
          message={`共发现 ${reviews.length} 个风险点，已选 ${selectedItemIds.length} 条`}
          type={reviews.some(r => r.action_type === 'Alert') ? 'warning' : 'info'}
          style={{ marginBottom: 16 }}
        />

        {/* 批量操作栏 */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <Checkbox
            checked={selectedItemIds.length === reviews.length && reviews.length > 0}
            indeterminate={selectedItemIds.length > 0 && selectedItemIds.length < reviews.length}
            onChange={(e) => toggleSelectAll(e.target.checked)}
          >
            全选
          </Checkbox>
          <Button
            type="primary"
            onClick={() => applyRevisions()}
            disabled={selectedItemIds.length === 0 || applyingRevisions}
            loading={applyingRevisions}
            icon={<CheckOutlined />}
          >
            应用选定修订 ({selectedItemIds.length})
          </Button>
          <Button
            onClick={() => applyRevisions(reviews.map(r => r.id))}
            disabled={applyingRevisions}
            loading={applyingRevisions}
          >
            全部应用
          </Button>
          <Dropdown menu={{ items: downloadMenuItems }} trigger={['click']}>
            <Button icon={<DownloadOutlined />}>
              下载文件
            </Button>
          </Dropdown>
        </div>

        {/* 审查项列表 */}
        {reviews.map((item) => (
          <Card
            key={item.id}
            style={{ marginBottom: 12, border: selectedItemIds.includes(item.id) ? '2px solid #1890ff' : undefined }}
            className="risk-card"
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Checkbox
                checked={selectedItemIds.includes(item.id)}
                onChange={(e) => toggleSelectItem(item.id, e.target.checked)}
              />
              <div style={{ flex: 1, marginLeft: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <strong>{item.issue_type}</strong>
                  <Tag color={item.severity === 'Critical' ? 'red' : item.severity === 'High' ? 'orange' : 'blue'}>
                    {item.severity}
                  </Tag>
                  {item.action_type === 'Alert' && <Tag color="red">严重警告</Tag>}
                  {item.entity_risk && (
                    <Tag
                      color={item.entity_risk.risk_level === 'High' ? 'red' : item.entity_risk.risk_level === 'Medium' ? 'orange' : 'default'}
                      icon={<WarningOutlined />}
                    >
                      主体风险: {item.entity_risk.risk_level}
                    </Tag>
                  )}
                  {item.related_entities && item.related_entities.length > 0 && (
                    <Tag color="cyan" icon={<SafetyCertificateOutlined />}>
                      涉及: {item.related_entities.join(', ')}
                    </Tag>
                  )}
                </div>

                <div
                  style={{
                    background: '#f5f5f5',
                    padding: '8px',
                    borderRadius: '4px',
                    margin: '8px 0',
                    cursor: 'pointer',
                    fontSize: '13px',
                    border: '1px dashed #d9d9d9'
                  }}
                  onClick={() => highlightInOriginal(item.quote)}
                  title="点击在原文中定位"
                >
                  <EyeOutlined style={{ marginRight: 4 }} />
                  <strong>原文：</strong>{item.quote}
                </div>

                <div style={{ fontSize: '13px', marginBottom: 4 }}>
                  <strong>风险说明：</strong>{item.explanation}
                </div>
                <div style={{ fontSize: '13px', marginBottom: 8 }}>
                  <strong>修改建议：</strong>{item.suggestion}
                </div>
                {item.legal_basis && (
                  <div style={{ fontSize: '13px', marginBottom: 8, background: '#f0f5ff', padding: '6px 8px', borderRadius: '4px' }}>
                    <strong style={{ color: '#1890ff' }}>审查依据：</strong>
                    <span style={{ color: '#666' }}>{item.legal_basis}</span>
                  </div>
                )}

                {/* 主体风险详情折叠面板 */}
                {item.entity_risk && (
                  <Collapse ghost style={{ marginBottom: 8 }}>
                    <Panel
                      header={
                        <span style={{ color: '#ff4d4f', fontWeight: 'bold' }}>
                          <WarningOutlined style={{ marginRight: 4 }} />
                          主体风险详情 ({item.entity_risk.entity_name})
                        </span>
                      } key="entity-risk"
                    >
                      <div style={{ padding: '8px 0', fontSize: '13px' }}>
                        <div style={{ marginBottom: 8 }}>
                          <strong>风险等级：</strong>
                          <Badge
                            status={item.entity_risk.risk_level === 'High' ? 'error' : item.entity_risk.risk_level === 'Medium' ? 'warning' : 'default'}
                            text={item.entity_risk.risk_level}
                          />
                        </div>
                        <div style={{ marginBottom: 8 }}>
                          <strong>主体类型：</strong>
                          <span>{item.entity_risk.entity_type}</span>
                        </div>
                        {item.entity_risk.risk_items && item.entity_risk.risk_items.length > 0 && (
                          <div>
                            <strong>风险详情：</strong>
                            <ul style={{ margin: '8px 0', paddingLeft: 20 }}>
                              {item.entity_risk.risk_items.map((risk, idx) => (
                                <li key={idx}>
                                  <Tag color="red" style={{ marginBottom: 4 }}>{risk.type}</Tag>
                                  <div>{risk.description}</div>
                                  <div style={{ color: '#999', fontSize: '12px' }}>{risk.detail}</div>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </Panel>
                  </Collapse>
                )}

                <div style={{ display: 'flex', gap: 8 }}>
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => applyRevisions([item.id])}
                    disabled={applyingRevisions}
                  >
                    采纳并应用
                  </Button>
                  <Button
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => openEditModal(item)}
                  >
                    编辑
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    );
  };

  // 渲染争议焦点标签页
  const renderControversyTab = () => {
    const controversyPoints = getControversyPoints();

    if (controversyPoints.length === 0) {
      return (
        <Alert
          message="暂无争议焦点"
          description="未发现极严重或高风险的争议点"
          type="success"
          showIcon
        />
      );
    }

    return (
      <div>
        <Alert
          message={`发现 ${controversyPoints.length} 处争议焦点（极严重或高风险）`}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
        {controversyPoints.map((item) => (
          <Card
            key={item.id}
            style={{ marginBottom: 12, borderLeft: '4px solid #ff4d4f' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Tag color={item.severity === 'Critical' ? 'red' : 'orange'}>{item.severity}</Tag>
              <strong>{item.issue_type}</strong>
            </div>
            <div style={{ background: '#fff1f0', padding: '8px', borderRadius: '4px', marginBottom: 8 }}>
              <div style={{ fontSize: '13px' }}>
                <strong>原文：</strong>{item.quote}
              </div>
            </div>
            <div style={{ fontSize: '13px', marginBottom: 4 }}>
              <strong>风险说明：</strong>{item.explanation}
            </div>
            <div style={{ fontSize: '13px', color: '#666' }}>
              <strong>修改建议：</strong>{item.suggestion}
            </div>
          </Card>
        ))}
      </div>
    );
  };

  // 渲染缺失条款标签页
  const renderMissingClausesTab = () => {
    const missingClauses = getMissingClauses();

    if (missingClauses.length === 0) {
      return (
        <Alert
          message="合同条款完备"
          description="未发现缺失的重要条款"
          type="success"
          showIcon
        />
      );
    }

    return (
      <div>
        <Alert
          message={`发现 ${missingClauses.length} 处缺失或需要补充的条款`}
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
        {missingClauses.map((item) => (
          <Card
            key={item.id}
            style={{ marginBottom: 12, borderLeft: '4px solid #faad14' }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <Tag color="orange">缺失条款</Tag>
              <strong>{item.issue_type}</strong>
            </div>
            <div style={{ fontSize: '13px', marginBottom: 8 }}>
              <strong>风险说明：</strong>{item.explanation}
            </div>
            <div style={{ fontSize: '13px', color: '#666' }}>
              <strong>建议补充：</strong>{item.suggestion}
            </div>
          </Card>
        ))}
      </div>
    );
  };

  // 渲染主体风险标签页
  const renderEntityRiskTab = () => {
    const itemsWithRisks = getItemsWithEntityRisks();

    if (itemsWithRisks.length === 0) {
      return (
        <Alert
          message="未发现主体风险"
          description="审查结果中未涉及主体风险信息"
          type="success"
          showIcon
        />
      );
    }

    // 按主体分组
    const entityGroups: Record<string, typeof itemsWithRisks> = {};
    itemsWithRisks.forEach(item => {
      if (item.entity_risk) {
        const entityName = item.entity_risk.entity_name;
        if (!entityGroups[entityName]) {
          entityGroups[entityName] = [];
        }
        entityGroups[entityName].push(item);
      }
    });

    return (
      <div>
        <Alert
          message={`发现 ${Object.keys(entityGroups).length} 个主体存在风险`}
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
        {Object.entries(entityGroups).map(([entityName, items]) => (
          <Card
            key={entityName}
            style={{ marginBottom: 16 }}
            title={
              <span style={{ color: '#ff4d4f' }}>
                <SafetyCertificateOutlined style={{ marginRight: 8 }} />
                {entityName}
              </span>
            }
          >
            {items[0].entity_risk && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8 }}>
                  <strong>主体类型：</strong>
                  <Tag>{items[0].entity_risk.entity_type}</Tag>
                </div>
                <div>
                  <strong>风险等级：</strong>
                  <Badge
                    status={items[0].entity_risk.risk_level === 'High' ? 'error' : 'warning'}
                    text={items[0].entity_risk.risk_level}
                  />
                </div>
              </div>
            )}
            <div style={{ fontWeight: 'bold', marginBottom: 8 }}>相关风险点：</div>
            {items.map(item => (
              <div
                key={item.id}
                style={{
                  padding: '8px 12px',
                  background: '#f5f5f5',
                  borderRadius: '4px',
                  marginBottom: 8,
                  cursor: 'pointer'
                }}
                onClick={() => {
                  setActiveResultTab('suggestions');
                  setTimeout(() => highlightInOriginal(item.quote), 100);
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Tag color={item.severity === 'Critical' ? 'red' : item.severity === 'High' ? 'orange' : 'blue'}>
                    {item.severity}
                  </Tag>
                  <span>{item.issue_type}</span>
                </div>
                <div style={{ fontSize: '12px', color: '#666', marginTop: 4 }}>
                  {item.explanation}
                </div>
              </div>
            ))}
          </Card>
        ))}
      </div>
    );
  };

  // 渲染重审标签页
  const renderReReviewTab = () => {
    return (
      <div style={{ textAlign: 'center', padding: '40px' }}>
        <div style={{ fontSize: '48px', marginBottom: '16px' }}>🔄</div>
        <h3>重新审查</h3>
        <p style={{ color: '#666', marginBottom: '24px' }}>
          如果修改了合同内容或调整了审查参数，可以重新启动审查
        </p>
        <Space>
          <Button type="primary" onClick={startDeepReview}>
            重新审查
          </Button>
          <Button onClick={() => {
            setStep('metadata');
          }}>
            调整审查参数
          </Button>
        </Space>
      </div>
    );
  };

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* 统一导航栏 */}
      <EnhancedModuleNavBar currentModuleKey="contract-review" />

      {/* ⭐ 新增：会话恢复提示 */}
      {hasPendingSession && (
        <div style={{
          background: '#fff7e6',
          borderBottom: '1px solid #ffd591',
          padding: '12px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <WarningOutlined style={{ fontSize: '18px', color: '#fa8c16' }} />
            <div>
              <div style={{ fontWeight: 500, color: '#d46b08' }}>检测到上次的未完成任务</div>
              <div style={{ fontSize: '12px', color: '#8c8c8c' }}>
                {pendingSessionInfo?.metadata?.contract_name || `合同 #${pendingSessionInfo?.savedContractId}`} -
                状态: {pendingSessionInfo?.status === 'completed' ? '已完成' : '进行中'}
              </div>
            </div>
          </div>
          <Space>
            <Button size="small" onClick={startNewTask}>
              开始新任务
            </Button>
            <Button type="primary" size="small" onClick={restorePendingSession}>
              继续上次任务
            </Button>
          </Space>
        </div>
      )}

      {/* 原有内容区域 */}
      <div className="review-container">
      {/* 左侧：编辑器 */}
      <div className="editor-area">
        {/* ⭐ 优先级1: 显示上传进度（文件已上传，正在处理）- 使用 ref 确保立即响应 */}
        {(function() {
          // ⭐ 调试：在渲染时输出状态值
          console.log('🔍 渲染检查 - showUploadProgress:', showUploadProgress, 'uploadProgressRef.current:', uploadProgressRef.current, 'editorConfig:', !!editorConfig, 'metadataExtracted:', metadataExtracted);
          return showUploadProgress || uploadProgressRef.current;
        })() ? (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            padding: '40px',
            textAlign: 'center',
            background: '#f5f5f5'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '20px' }}>📤</div>
            <h3 style={{ marginBottom: '16px' }}>文件已上传！</h3>
            <p style={{ color: '#666', marginBottom: '24px' }}>
              正在进行格式转换，请稍候...
            </p>
            <div style={{
              padding: '16px 24px',
              background: '#fff3cd',
              border: '1px solid #ffc107',
              borderRadius: '8px',
              maxWidth: '400px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                <div className="ant-spin ant-spin-spinning" style={{ display: 'inline-block' }}>
                  <span className="ant-spin-dot ant-spin-dot-spin">
                    <i></i><i></i><i></i><i></i>
                  </span>
                </div>
                <strong>正在后台处理：</strong>
              </div>
              <div style={{ textAlign: 'left', fontSize: '14px', marginLeft: '24px' }}>
                <div>✓ 文件已上传</div>
                <div style={{ opacity: 0.7 }}>⟳ 格式转换中...</div>
                <div style={{ opacity: 0.5 }}>○ 生成预览...</div>
              </div>
            </div>
            <div style={{ marginTop: '20px', fontSize: '12px', color: '#999' }}>
              预计处理时间：10-30秒（根据文件大小）
            </div>
          </div>
        ) : editorConfig && metadataExtracted ? (
          // ⭐ 优先级2: 显示文档编辑器（元数据已提取）
          <DocumentEditor
            id="docxEditor"
            documentServerUrl={import.meta.env.VITE_ONLYOFFICE_URL || (import.meta.env.PROD ? '/onlyoffice' : 'http://localhost:8082')}
            config={editorConfig}
            events_onDocumentReady={onDocumentReady}
            height="100%"
            width="100%"
          />
        ) : editorConfig ? (
          // ⭐ 优先级3: 文件已转换但元数据未提取完成时显示处理进度
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            padding: '40px',
            textAlign: 'center'
          }}>
            <div style={{ fontSize: '48px', marginBottom: '20px' }}>📄</div>
            <h3 style={{ marginBottom: '16px' }}>文件上传成功！</h3>
            <p style={{ color: '#666', marginBottom: '24px' }}>
              正在提取合同元数据，请稍候...
            </p>
            <div style={{
              padding: '16px 24px',
              background: '#e6f7ff',
              border: '1px solid #91d5ff',
              borderRadius: '4px',
              color: '#1890ff',
              maxWidth: '400px'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <div className="ant-spin ant-spin-spinning" style={{ display: 'inline-block' }}>
                  <span className="ant-spin-dot ant-spin-dot-spin">
                    <i></i><i></i><i></i><i></i>
                  </span>
                </div>
                <strong>正在后台处理：</strong>
              </div>
              <div style={{ textAlign: 'left', fontSize: '14px', marginLeft: '24px' }}>
                <div>✓ 文件已上传</div>
                <div style={{ opacity: 0.7 }}>⟳ 格式转换中...</div>
                <div style={{ opacity: 0.5 }}>○ 生成预览...</div>
              </div>
            </div>
            <p style={{ fontSize: '12px', color: '#999', marginTop: '16px' }}>
              预计需要 10-30 秒，处理完成后将自动显示编辑器
            </p>
          </div>
        ) : (
          // ⭐ 优先级4: 默认上传按钮
          <div className="upload-placeholder">
            <label style={{ cursor: 'pointer', color: '#1890ff', fontSize: '18px' }}>
              点击上传合同文件
              <br />
              <span style={{ fontSize: '14px', color: '#999' }}>
                支持格式：文档 (.doc/.docx/.pdf/.txt/.rtf/.odt)
                <br />
                支持格式：图片 (.jpg/.png/.bmp/.tiff/.gif) - OCR 识别
                <br />
                非 .docx 格式将自动转换为 Word 格式
              </span>
              <input
                type="file"
                accept=".doc,.docx,.pdf,.txt,.rtf,.odt,.jpg,.jpeg,.png,.bmp,.tiff,.gif"
                onChange={handleFileUpload}
                style={{ display: 'none' }}
              />
            </label>
            {loading && <div className="spin">上传处理中...</div>}
          </div>
        )}
      </div>

      {/* 右侧：AI 控制面板 */}
      <div className="ai-sidebar">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 style={{ margin: 0 }}>⚖️ 智能合同审查（升级版）</h3>
          <Button
            type="link"
            icon={<HistoryOutlined />}
            onClick={() => navigate('/contract/review-history')}
            style={{ padding: 0 }}
          >
            历史任务
          </Button>
        </div>

        {/* 知识库增强开关 */}
        <ModuleKnowledgeToggle
          moduleName="contract_review"
          moduleLabel="合同审查"
        />

        {/* 自定义规则管理区域 - 所有步骤都显示 */}
        <Card
          title={
            <span>
              <FileProtectOutlined style={{ marginRight: 8 }} />
              自定义审查规则
            </span>
          }
          size="small"
          style={{ marginBottom: 16 }}
          extra={
            <Button
              size="small"
              icon={<AppstoreOutlined />}
              onClick={() => setCustomRulesModalVisible(true)}
            >
              管理规则
            </Button>
          }
        >
          <div style={{ fontSize: '12px', color: '#666' }}>
            <div>已创建 {customRulesCount} 条自定义规则</div>
            {customRulesCount > 0 && (
              <div style={{ marginTop: 4 }}>
                <Checkbox
                  checked={useCustomRules}
                  onChange={(e) => setUseCustomRules(e.target.checked)}
                >
                  本次审查启用
                </Checkbox>
              </div>
            )}
          </div>
        </Card>

        {/* 步骤1：元数据确认 */}
        {step === 'metadata' && (
          <Card title="请确认合同基本信息" style={{ marginBottom: 16 }}>
            <div style={{ marginBottom: 12 }}>
              <strong>审查立场：</strong>
              <Select value={stance} onChange={(value) => setStance(value as '甲方' | '乙方')} style={{ width: 120 }}>
                <Select.Option value="甲方">甲方</Select.Option>
                <Select.Option value="乙方">乙方</Select.Option>
              </Select>
            </div>

            <div style={{ marginBottom: 12 }}>
              <strong>合同类型：</strong>
              <Input
                value={editedMetadata.contract_type || ''}
                onChange={(e) => setEditedMetadata({ ...editedMetadata, contract_type: e.target.value })}
                placeholder="如：服务合同"
                disabled
              />
            </div>

            <div style={{ marginBottom: 12 }}>
              <strong>合同名称：</strong>
              <Input
                value={editedMetadata.contract_name || ''}
                onChange={(e) => setEditedMetadata({ ...editedMetadata, contract_name: e.target.value })}
                placeholder="如：技术服务合同"
              />
            </div>
            <div style={{ margin: '8px 0' }}>
              <strong>当事人：</strong>
              {/* ⭐ 始终解析为数组显示 */}
              {parsePartiesString(editedMetadata.parties).map((p, idx) => (
                <div key={idx} className="party-row" style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <Input
                    value={p}
                    onChange={(e) => updateParty(idx, e.target.value)}
                    placeholder={`当事人 ${idx + 1}`}
                    style={{ flex: 1 }}
                  />
                  {parsePartiesString(editedMetadata.parties).length > 1 && (
                    <Button danger type="text" onClick={() => removeParty(idx)} icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  )}
                </div>
              ))}
              <div style={{ marginTop: 8 }}>
                <Button type="dashed" onClick={addParty} icon={<PlusOutlined />}>
                  添加当事人
                </Button>
              </div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>合同金额：</strong>
              <Input
                value={editedMetadata.amount || ''}
                onChange={(e) => setEditedMetadata({ ...editedMetadata, amount: e.target.value })}
              />
            </div>

            {/* ⭐ 交易结构选择 */}
            {editedMetadata.legal_features?.transaction_structures &&
              editedMetadata.legal_features.transaction_structures.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <strong>
                    <AppstoreOutlined style={{ marginRight: 4 }} />
                    确认本次交易结构 (可多选)
                  </strong>
                  <Tag color="blue">AI建议</Tag>
                </div>
                <Checkbox.Group
                  style={{ width: '100%' }}
                  value={selectedTransactionStructures}
                  onChange={(values) => setSelectedTransactionStructures(values as string[])}
                >
                  <Space direction="vertical" style={{ width: '100%' }}>
                    {editedMetadata.legal_features.transaction_structures.map((ts) => (
                      <Checkbox key={ts} value={ts}>
                        {ts}
                      </Checkbox>
                    ))}
                  </Space>
                </Checkbox.Group>
                <div style={{ marginTop: 8, fontSize: '12px', color: '#999' }}>
                  💡 提示：选择交易结构后，系统将加载对应的专项审查规则
                </div>
              </div>
            )}

            {/* ⭐ 元数据提取进度提示 */}
            {metadataExtracting && (
              <Alert
                message="正在提取合同信息..."
                description="AI 正在分析合同内容，提取当事人、金额、类型等关键信息，请稍候..."
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}

            <Button
              type="primary"
              onClick={startDeepReview}
              loading={loading}
              disabled={metadataExtracting || !metadataExtracted}
              style={{ width: '100%' }}
            >
              {metadataExtracting ? '正在提取合同信息...' : !metadataExtracted ? '等待合同信息提取...' : '开始深度审查'}
            </Button>
          </Card>
        )}

        {/* 步骤2：审查中 */}
        {step === 'reviewing' && (
          <Card>
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <Spin size="large" />
              <div style={{ marginTop: '24px' }}>
                <h3 style={{ marginBottom: '16px' }}>AI 正在深度分析合同...</h3>
                {reviewProgress ? (
                  <div style={{
                    padding: '16px 24px',
                    background: '#e6f7ff',
                    border: '1px solid #91d5ff',
                    borderRadius: '8px',
                    color: '#1890ff',
                    fontSize: '16px',
                    fontWeight: 500,
                    maxWidth: '500px',
                    margin: '0 auto'
                  }}>
                    {reviewProgress}
                  </div>
                ) : (
                  <p style={{ color: '#666' }}>请耐心等待（通常需要 10-30 秒）</p>
                )}
              </div>
              <div style={{ marginTop: '24px', fontSize: '14px', color: '#999' }}>
                正在执行：规则加载 → 条款分析 → 风险识别 → 报告生成
              </div>
            </div>
          </Card>
        )}

        {/* 步骤3：审查结果 */}
        {step === 'results' && (
          <div className="review-results-container">
            {/* ⭐ 合同健康度综合评估 - 置于顶部 */}
            <ContractHealthAssessment contractId={contractId} />

            {/* ⭐ 标签页布局 */}
            <Card style={{ marginTop: 16 }}>
              <Tabs
                activeKey={activeResultTab}
                onChange={setActiveResultTab}
                type="card"
                size="large"
                items={[
                  {
                    key: 'overview',
                    label: (
                      <span>
                        <FileSearchOutlined />
                        综合评估
                      </span>
                    ),
                    children: renderOverviewTab()
                  },
                  {
                    key: 'suggestions',
                    label: (
                      <span>
                        <EditOutlined />
                        修改意见
                        <Tag color="blue" style={{ marginLeft: 4 }}>{reviews.length}</Tag>
                      </span>
                    ),
                    children: renderSuggestionsTab()
                  },
                  {
                    key: 'controversy',
                    label: (
                      <span>
                        <FlagOutlined />
                        争议焦点
                        <Tag color="red" style={{ marginLeft: 4 }}>{getControversyPoints().length}</Tag>
                      </span>
                    ),
                    children: renderControversyTab()
                  },
                  {
                    key: 'missing',
                    label: (
                      <span>
                        <FileExclamationOutlined />
                        缺失条款
                        <Tag color="orange" style={{ marginLeft: 4 }}>{getMissingClauses().length}</Tag>
                      </span>
                    ),
                    children: renderMissingClausesTab()
                  },
                  {
                    key: 'entity',
                    label: (
                      <span>
                        <SafetyCertificateOutlined />
                        主体风险
                        <Tag color="cyan" style={{ marginLeft: 4 }}>{getItemsWithEntityRisks().length}</Tag>
                      </span>
                    ),
                    children: renderEntityRiskTab()
                  },
                  {
                    key: 're-review',
                    label: (
                      <span>
                        <HistoryOutlined />
                        重审
                      </span>
                    ),
                    children: renderReReviewTab()
                  }
                ]}
              />
            </Card>
          </div>
        )}
      </div>

      {/* 编辑模态框 */}
      <Modal
        title="编辑审查意见"
        open={editModalVisible}
        onOk={saveEditItem}
        onCancel={() => setEditModalVisible(false)}
        width={600}
        okText="保存"
        cancelText="取消"
      >
        {editingItem && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <strong>问题类型：</strong>
              <Tag color={editingItem.severity === 'Critical' ? 'red' : editingItem.severity === 'High' ? 'orange' : 'blue'}>
                {editingItem.issue_type}
              </Tag>
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>原文：</strong>
              <div style={{ background: '#f5f5f5', padding: '8px', borderRadius: '4px', marginTop: 4 }}>
                {editingItem.quote}
              </div>
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>风险说明：</strong>
              <TextArea
                value={editExplanation}
                onChange={(e) => setEditExplanation(e.target.value)}
                rows={3}
                placeholder="请输入风险说明"
              />
            </div>
            <div style={{ marginBottom: 16 }}>
              <strong>修改建议：</strong>
              <TextArea
                value={editSuggestion}
                onChange={(e) => setEditSuggestion(e.target.value)}
                rows={3}
                placeholder="请输入修改建议"
              />
            </div>
          </div>
        )}
      </Modal>

      {/* 自定义规则管理模态框 */}
      <Modal
        title="自定义审查规则管理"
        open={customRulesModalVisible}
        onCancel={() => setCustomRulesModalVisible(false)}
        footer={null}
        width={800}
      >
        <div style={{ marginBottom: 16 }}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              customRuleForm.resetFields();
              customRuleForm.setFieldsValue({ is_active: true, priority: 0 });
              setCustomRuleCreateModalVisible(true);
            }}
            style={{ marginRight: 8 }}
          >
            新建规则
          </Button>
          <Button onClick={fetchCustomRules}>刷新</Button>
        </div>

        <Table
          dataSource={customRules}
          rowKey="id"
          pagination={false}
          size="small"
          columns={[
            {
              title: '名称',
              dataIndex: 'name',
              key: 'name',
              ellipsis: true,
            },
            {
              title: '描述',
              dataIndex: 'description',
              key: 'description',
              ellipsis: true,
            },
            {
              title: '优先级',
              dataIndex: 'priority',
              key: 'priority',
              width: 70,
            },
            {
              title: '状态',
              dataIndex: 'is_active',
              key: 'is_active',
              width: 70,
              render: (active: boolean) => (
                active ?
                  <Tag color="success" icon={<CheckOutlined />}>启用</Tag> :
                  <Tag color="default" icon={<CloseCircleOutlined />}>禁用</Tag>
              ),
            },
            {
              title: '操作',
              key: 'actions',
              width: 150,
              render: (_: any, record: any) => (
                <Space size="small">
                  <Button
                    type="text"
                    size="small"
                    onClick={() => handleToggleCustomRule(record.id)}
                  >
                    {record.is_active ? '禁用' : '启用'}
                  </Button>
                  <Popconfirm
                    title="确定删除此规则吗？"
                    onConfirm={() => handleDeleteCustomRule(record.id)}
                    okText="确定"
                    cancelText="取消"
                  >
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                    >
                      删除
                    </Button>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
      </Modal>

      {/* 创建自定义规则弹窗 */}
      <Modal
        title="创建自定义规则"
        open={customRuleCreateModalVisible}
        onCancel={() => setCustomRuleCreateModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form
          form={customRuleForm}
          layout="vertical"
          onFinish={handleCreateCustomRule}
        >
          <Form.Item
            label="规则名称"
            name="name"
            rules={[{ required: true, message: '请输入规则名称' }]}
          >
            <Input placeholder="如：价格合理性审查" />
          </Form.Item>
          <Form.Item
            label="规则描述"
            name="description"
          >
            <Input placeholder="简要描述此规则的用途" />
          </Form.Item>
          <Form.Item
            label="规则内容"
            name="content"
            rules={[{ required: true, message: '请输入规则内容' }]}
            tooltip="详细的审查规则说明，将用于 AI 审查提示"
          >
            <TextArea
              rows={6}
              placeholder="请输入详细的审查规则内容，包括审查要点、判断标准等..."
            />
          </Form.Item>
          <Form.Item
            label="优先级"
            name="priority"
            tooltip="数字越小越优先"
          >
            <Input type="number" min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" block>
              创建规则
            </Button>
          </Form.Item>
        </Form>
      </Modal>
      </div>
    </div>
  );
};

export default ContractReview;