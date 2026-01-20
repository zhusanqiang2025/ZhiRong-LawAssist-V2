/**
 * 合同规划页面
 *
 * 功能：
 * 1. 用户输入需求
 * 2. 系统识别为"合同规划"场景
 * 3. 显示规划模式选择界面（多模型/单模型）
 * 4. 用户选择后执行规划
 * 5. 展示规划结果
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  Input,
  Button,
  Upload,
  message,
  Spin,
  Alert,
  Typography,
  Space,
} from 'antd';
import type { UploadFile, UploadProps } from 'antd';
import {
  SendOutlined,
  InboxOutlined,
  ArrowLeftOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import PlanningModeSelector from '../components/PlanningModeSelector';
import PlanningResultDisplay from '../components/PlanningResultDisplay';
import { useSessionPersistence } from '../hooks/useSessionPersistence';
import type {
  AnalyzeAndGetFormRequest,
  ContractPlanningResponse,
  RequiresUserChoiceResponse,
  ContractPlanningResult
} from '../types/planning';
// import styles from './ContractPlanningPage.module.less';

const { TextArea } = Input;
const { Dragger } = Upload;
const { Title, Paragraph, Text } = Typography;

const ContractPlanningPage: React.FC = () => {
  const navigate = useNavigate();

  // 状态管理
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');
  const [userInput, setUserInput] = useState('');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [currentStep, setCurrentStep] = useState<'input' | 'select_mode' | 'result'>('input');

  // API 响应数据
  const [choiceResponse, setChoiceResponse] = useState<RequiresUserChoiceResponse | null>(null);
  const [planningResult, setPlanningResult] = useState<ContractPlanningResult | null>(null);

  // ========== 会话持久化 ==========
  interface ContractPlanningSessionData {
    step: 'input' | 'select_mode' | 'result';
    userInput: string;
    fileList: string[]; // 文件名列表
    choiceResponse: RequiresUserChoiceResponse | null;
    planningResult: ContractPlanningResult | null;
  }

  const {
    hasSession,
    saveSession,
    clearSession,
    isLoading: isRestoringSession
  } = useSessionPersistence<ContractPlanningSessionData>('contract_planning_session', {
    expirationTime: 2 * 60 * 60 * 1000, // 2小时
    onRestore: (sessionId, data) => {
      console.log('[合同规划] 恢复会话:', data);
      setCurrentStep(data.step);
      setUserInput(data.userInput || '');
      setChoiceResponse(data.choiceResponse);
      setPlanningResult(data.planningResult);
      message.success('已恢复之前的合同规划会话');
    }
  });

  // 保存会话状态
  const saveCurrentState = () => {
    saveSession(Date.now().toString(), {
      step: currentStep,
      userInput,
      fileList: fileList.map(f => f.name || f.uid),
      choiceResponse,
      planningResult
    });
  };

  // 监听状态变化，自动保存
  useEffect(() => {
    if (currentStep !== 'input' || userInput) {
      saveCurrentState();
    }
  }, [currentStep, userInput, choiceResponse, planningResult]);
  // ========== 会话持久化结束 ==========

  // 文件上传配置
  const draggerProps: UploadProps = {
    name: 'file',
    multiple: true,
    fileList,
    beforeUpload: () => false,
    onChange: ({ fileList: newFileList }) => {
      setFileList(newFileList.slice(-5));
    },
  };

  // 步骤1：提交需求分析
  const handleSubmitAnalyze = async () => {
    if (!userInput.trim()) {
      message.error('请输入您的需求描述');
      return;
    }

    setLoading(true);
    setError('');

    try {
      // 上传文件并获取路径
      const uploadedFilePaths: string[] = [];
      for (const file of fileList) {
        if (file.originFileObj) {
          const formData = new FormData();
          formData.append('file', file.originFileObj);
          // 这里假设有文件上传接口，实际需要根据后端调整
          // const response = await api.uploadFile(formData);
          // uploadedFilePaths.push(response.data.file_path);
        }
      }

      // 调用需求分析接口
      const requestData: AnalyzeAndGetFormRequest = {
        user_input: userInput,
        uploaded_files: uploadedFilePaths,
        // 不传 planning_mode，让后端判断是否需要用户选择
      };

      const response = await api.analyzeAndGetClarificationForm(requestData);
      const data = response.data as ContractPlanningResponse;

      if (data.processing_type === 'contract_planning') {
        if ('requires_user_choice' in data && data.requires_user_choice) {
          // 需要用户选择模式
          setChoiceResponse(data);
          setCurrentStep('select_mode');
        } else {
          // 直接返回了结果（可能用户之前已经选择过）
          setPlanningResult(data as ContractPlanningResult);
          setCurrentStep('result');
        }
      } else {
        throw new Error('未识别为合同规划场景');
      }
    } catch (err: any) {
      console.error('分析失败:', err);
      const errorMsg = err.response?.data?.detail || err.message || '分析失败，请重试';
      setError(errorMsg);
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // 步骤2：用户确认模式选择后，执行规划
  const handleConfirmMode = async (mode: 'multi_model' | 'single_model') => {
    setLoading(true);
    setError('');

    try {
      // 上传文件并获取路径
      const uploadedFilePaths: string[] = [];
      for (const file of fileList) {
        if (file.originFileObj) {
          const formData = new FormData();
          formData.append('file', file.originFileObj);
          // const response = await api.uploadFile(formData);
          // uploadedFilePaths.push(response.data.file_path);
        }
      }

      // 调用规划接口，传入用户选择的模式
      const requestData: AnalyzeAndGetFormRequest = {
        user_input: userInput,
        uploaded_files: uploadedFilePaths,
        planning_mode: mode
      };

      const response = await api.analyzeAndGetClarificationForm(requestData);
      const data = response.data as ContractPlanningResult;

      setPlanningResult(data);
      setCurrentStep('result');
      message.success('合同规划完成！');
    } catch (err: any) {
      console.error('规划失败:', err);
      const errorMsg = err.response?.data?.detail || err.message || '规划失败，请重试';
      setError(errorMsg);
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // 重新开始
  const handleReset = () => {
    clearSession();
    setCurrentStep('input');
    setUserInput('');
    setFileList([]);
    setChoiceResponse(null);
    setPlanningResult(null);
    setError('');
  };

  // 返回首页
  const handleBackToHome = () => {
    navigate('/');
  };

  // 清除会话并重新开始
  const handleClearSessionAndReset = () => {
    clearSession();
    setCurrentStep('input');
    setUserInput('');
    setFileList([]);
    setChoiceResponse(null);
    setPlanningResult(null);
    setError('');
  };

  return (
    <div className="contract-planning-page">
      <div className="page-header">
        <Space>
          <Button
            icon={<ArrowLeftOutlined />}
            onClick={handleBackToHome}
          >
            返回首页
          </Button>
          <Title level={2} style={{ margin: 0 }}>
            智能合同规划
          </Title>
        </Space>
      </div>

      <Spin spinning={loading || isRestoringSession} tip={isRestoringSession ? "正在恢复会话..." : "正在分析需求..."} size="large">
        <div className="page-content">
          {/* 会话恢复提示 */}
          {hasSession && currentStep === 'input' && (
            <Alert
              message="检测到之前的会话"
              description={
                <Space direction="vertical" size="small">
                  <Text>系统检测到您之前有一个未完成的合同规划会话。您可以：</Text>
                  <Space>
                    <Button
                      size="small"
                      type="primary"
                      onClick={() => {
                        window.location.reload();
                      }}
                    >
                      继续之前的规划
                    </Button>
                    <Button
                      size="small"
                      onClick={handleClearSessionAndReset}
                    >
                      开始新规划
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

          {/* 步骤1：输入需求 */}
          {currentStep === 'input' && (
            <Card className="input-card">
              <div className="card-header">
                <Title level={3}>描述您的需求</Title>
                <Paragraph type="secondary">
                  请详细描述您的复杂交易需求，系统将为您规划所需的合同清单、签署顺序和关联关系。
                </Paragraph>
              </div>

              <div className="form-section">
                <Title level={5}>1. 上传相关材料（可选）</Title>
                <Dragger {...draggerProps}>
                  <p className="ant-upload-drag-icon">
                    <InboxOutlined />
                  </p>
                  <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                  <p className="ant-upload-hint">
                    支持单个或多个文件，如现有合同、项目资料等
                  </p>
                </Dragger>
              </div>

              <div className="form-section">
                <Title level={5}>2. 描述您的需求</Title>
                <TextArea
                  rows={6}
                  value={userInput}
                  onChange={(e) => setUserInput(e.target.value)}
                  placeholder="例如：我要收购一家科技公司，需要设计完整的交易结构，包括股权转让、员工安置、知识产权转让等..."
                  maxLength={3000}
                  showCount
                />
              </div>

              <Button
                type="primary"
                size="large"
                block
                icon={<SendOutlined />}
                onClick={handleSubmitAnalyze}
                disabled={loading || !userInput.trim()}
              >
                开始分析需求
              </Button>

              {error && (
                <Alert
                  message="操作失败"
                  description={error}
                  type="error"
                  showIcon
                  closable
                  style={{ marginTop: 16 }}
                  onClose={() => setError('')}
                />
              )}
            </Card>
          )}

          {/* 步骤2：选择规划模式 */}
          {currentStep === 'select_mode' && choiceResponse && (
            <Card className="select-mode-card">
              <div className="card-header">
                <Button onClick={handleReset} style={{ marginBottom: 16 }}>
                  <ArrowLeftOutlined /> 重新输入
                </Button>
              </div>

              <PlanningModeSelector
                options={choiceResponse.user_choice_options}
                defaultChoice={choiceResponse.default_choice}
                onConfirm={handleConfirmMode}
                loading={loading}
              />

              {error && (
                <Alert
                  message="操作失败"
                  description={error}
                  type="error"
                  showIcon
                  closable
                  style={{ marginTop: 16 }}
                  onClose={() => setError('')}
                />
              )}
            </Card>
          )}

          {/* 步骤3：展示规划结果 */}
          {currentStep === 'result' && planningResult && (
            <Card className="result-card">
              <div className="card-header">
                <Space>
                  <Button onClick={handleReset}>
                    <ReloadOutlined /> 重新规划
                  </Button>
                  <Button onClick={handleBackToHome}>
                    <ArrowLeftOutlined /> 返回首页
                  </Button>
                </Space>
              </div>

              <PlanningResultDisplay result={planningResult} />
            </Card>
          )}
        </div>
      </Spin>
    </div>
  );
};

export default ContractPlanningPage;
