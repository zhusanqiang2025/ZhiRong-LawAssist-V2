// frontend/src/pages/ResultPage.tsx (v3.0 - 支持WebSocket实时进度显示)
import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Layout, message, Row, Col, Card, Typography, Button, Space, Modal, Input, Spin, Alert, Divider, Tag } from 'antd';
import { logger } from '../utils/logger';
import { DownloadOutlined, MailOutlined, WechatOutlined, FilePdfOutlined, FileWordOutlined,
    CopyOutlined, RobotOutlined, MessageOutlined, CheckOutlined, CloseOutlined, EyeOutlined
} from '@ant-design/icons';
import api from '../api';
import FileDisplay from '../components/FileDisplay';
import ChatWindow from '../components/ChatWindow';
import LoadingPlaceholder from '../components/LoadingPlaceholder';
import {
    OverallProgress,
    ProgressTimeline,
    NodeProgress
} from '../components/Progress';
import { taskWebSocketService, WebSocketCallbacks } from '../services/websocketService';
import { TaskProgress, Task } from '../types/task';
import './ResultPage.css';

const { Content, Header } = Layout;
const { Paragraph } = Typography;
const { TextArea } = Input;

const cleanAndFormatForMarkdown = (rawText: string): string => {
    if (!rawText || rawText === 'None') return "";
    let cleanedText = String(rawText)
        .replace(/<think>[\s\S]*?<\/think>/gs, '')
        .replace(/<execute>[\s\S]*$/g, '');
    cleanedText = cleanedText
        .replace(/\r\n/g, '\n')
        .replace(/\n{3,}/g, '\n\n')
        .trim();
    return cleanedText;
};

const extractFinalContract = (cleanedText: string): string => {
    if (!cleanedText) return "";
    const startMarker = "【审查通过稿】";
    const endMarker = "【主要修改说明】";
    const startIndex = cleanedText.indexOf(startMarker);
    if (startIndex === -1) return cleanedText;
    const endIndex = cleanedText.indexOf(endMarker, startIndex);
    let contractText = (endIndex !== -1)
        ? cleanedText.substring(startIndex + startMarker.length, endIndex)
        : cleanedText.substring(startIndex + startMarker.length);
    return contractText.trim();
};

const ResultPage: React.FC = () => {
    const { taskId } = useParams<{ taskId: string }>();
    const navigate = useNavigate();

    const [task, setTask] = useState<Task | null>(null);
    const [finalContent, setFinalContent] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [isChatting, setIsChatting] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [downloadUrl, setDownloadUrl] = useState('');
    const [showConfirmation, setShowConfirmation] = useState(false);
    const [analysisResult, setAnalysisResult] = useState('');

    // WebSocket 相关状态
    const [isWebSocketConnected, setIsWebSocketConnected] = useState(false);
    const [showProgressDetails, setShowProgressDetails] = useState(false);
    const [currentProgress, setCurrentProgress] = useState<TaskProgress | null>(null);

    const pollingIntervalRef = useRef<number | null>(null);
    const wsCallbacksRef = useRef<WebSocketCallbacks | null>(null);

    // 解析分析结果并生成确认消息
    const getConfirmationMessage = (analysisReport: string): string => {
        try {
            // 尝试解析JSON格式的分析报告
            const reportData = JSON.parse(analysisReport);
            const intent = reportData.intent;
            
            // 根据意图生成相应的确认消息
            switch (intent) {
                case "analyze_risk":
                    return "系统已完成背景情况分析，基于你的资料和信息，你是否需要我进行风险分析？如果你确认，我将启动风险分析报告工作流，为你输出专业的风险分析报告。";
                case "legal_consultation":
                    return "系统已完成背景情况分析，基于你的资料和信息，你是否需要我生成合同？如果你确认，我将启动合同生成工作流，为你输出专业的合同文本。";
                case "draft_letter":
                    return "系统已完成背景情况分析，基于你的资料和信息，你是否需要我草拟函件？如果你确认，我将启动函件起草工作流，为你输出专业的函件文本。";
                case "judicial_document":
                    return "系统已完成背景情况分析，基于你的资料和信息，你是否需要我拟订司法文书？如果你确认，我将启动司法文书拟订工作流，为你输出专业的司法文书。";
                default:
                    return "系统已完成背景情况分析，基于你的资料和信息，你是否需要我进行风险分析？如果你确认，我将启动风险分析报告工作流，为你输出专业的风险分析报告。";
            }
        } catch (e) {
            // 如果解析失败，返回默认消息
            return "系统已完成背景情况分析，基于你的资料和信息，你是否需要我进行风险分析？如果你确认，我将启动风险分析报告工作流，为你输出专业的风险分析报告。";
        }
    };

    // WebSocket 回调函数
    const createWebSocketCallbacks = useCallback((): WebSocketCallbacks => {
        return {
            onProgress: (progress: TaskProgress) => {
                logger.task('收到进度更新:', progress);
                setCurrentProgress(progress);

                // 更新任务状态
                setTask(prev => {
                    if (!prev) return null;

                    const updatedTask = {
                        ...prev,
                        status: progress.status,
                        progress: progress.progress,
                        currentNode: progress.currentNode,
                        nodeProgress: progress.nodeProgress,
                        workflowSteps: progress.workflowSteps,
                        estimatedTimeRemaining: progress.estimatedTimeRemaining,
                        errorMessage: progress.errorMessage
                    };

                    // 处理完成状态
                    if (progress.status === 'completed' && progress.result) {
                        const rawResult = progress.result || '';
                        const cleanedText = cleanAndFormatForMarkdown(rawResult);
                        const contractText = extractFinalContract(cleanedText);
                        setFinalContent(contractText || cleanedText);
                        setShowConfirmation(false);
                        setIsLoading(false);
                        setIsChatting(false);
                    } else if (progress.status === 'failed') {
                        setIsLoading(false);
                        setIsChatting(false);
                        message.error(`任务处理失败: ${progress.errorMessage || '未知错误'}`);
                    }

                    return updatedTask;
                });
            },
            onCompleted: (result: any) => {
                logger.task('任务完成:', result);
                setIsLoading(false);
                setIsChatting(false);
                message.success('任务处理完成！');
            },
            onError: (error: string) => {
                logger.error('任务错误:', error);
                setIsLoading(false);
                setIsChatting(false);
                message.error(`任务处理失败: ${error}`);
            },
            onConnected: () => {
                logger.websocket('WebSocket连接成功');
                setIsWebSocketConnected(true);
            },
            onDisconnected: () => {
                logger.websocket('WebSocket连接断开');
                setIsWebSocketConnected(false);
            }
        };
    }, []);

    // 连接WebSocket
    const connectWebSocket = useCallback(async () => {
        if (!taskId) return;

        try {
            // 获取当前用户的token
            const token = localStorage.getItem('token');
            if (!token) {
                console.warn('未找到认证token，无法连接WebSocket');
                return;
            }

            const callbacks = createWebSocketCallbacks();
            wsCallbacksRef.current = callbacks;

            await taskWebSocketService.connect(taskId, token, callbacks);
        } catch (error) {
            console.error('WebSocket连接失败:', error);
            // WebSocket连接失败，回退到轮询模式
            startPolling();
        }
    }, [taskId, createWebSocketCallbacks]);

    // 启动轮询（WebSocket失败时的回退方案）
    const startPolling = useCallback(() => {
        if (pollingIntervalRef.current) return;

        const intervalId = window.setInterval(async () => {
            if (!taskId) return;
            try {
                const response = await api.getTaskStatus(taskId);
                const newTask = response.data;
                setTask(newTask);

                if (newTask.status === 'completed' || newTask.status === 'failed') {
                    stopPolling();
                    setIsLoading(false);
                    setIsChatting(false);
                    if (newTask.status === 'completed') {
                        if (newTask.analysis_report && !newTask.final_document) {
                            setAnalysisResult(newTask.analysis_report);
                            setShowConfirmation(true);
                            setFinalContent('');
                        } else if (newTask.result) {
                            const rawResult = newTask.result || '';
                            const cleanedText = cleanAndFormatForMarkdown(rawResult);
                            const contractText = extractFinalContract(cleanedText);
                            setFinalContent(contractText || cleanedText);
                            setShowConfirmation(false);
                        }
                    } else {
                        message.error(`任务处理失败: ${cleanAndFormatForMarkdown(newTask.result) || '未知错误'}`);
                    }
                } else {
                    setIsLoading(true);
                }
            } catch (error) {
                console.error('轮询任务状态失败:', error);
                message.error('轮询任务状态失败');
                stopPolling();
                setIsLoading(false);
                setIsChatting(false);
            }
        }, 3000);

        pollingIntervalRef.current = intervalId;
    }, [taskId]);

    const stopPolling = useCallback(() => {
        if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
        }

        // 断开WebSocket连接
        taskWebSocketService.disconnect();
        setIsWebSocketConnected(false);
    }, []);

    // 初始化：尝试WebSocket，失败则回退到轮询
    useEffect(() => {
        if (!taskId) {
            message.error('无效的任务ID，正在返回首页...');
            navigate('/');
            return;
        }

        // 优先尝试WebSocket连接
        connectWebSocket();

        // 清理函数
        return () => {
            stopPolling();
        };
    }, [taskId, navigate, connectWebSocket, stopPolling]);

    // 获取任务初始状态（WebSocket连接前的数据）
    useEffect(() => {
        const fetchInitialTask = async () => {
            if (!taskId) return;

            try {
                const response = await api.getTaskStatus(taskId);
                const initialTask = response.data;
                setTask(initialTask);

                // 如果任务已经完成或失败，不需要连接WebSocket
                if (initialTask.status === 'completed' || initialTask.status === 'failed') {
                    stopPolling();
                    setIsLoading(false);
                    setIsChatting(false);

                    if (initialTask.status === 'completed') {
                        if (initialTask.analysis_report && !initialTask.final_document) {
                            setAnalysisResult(initialTask.analysis_report);
                            setShowConfirmation(true);
                        } else if (initialTask.result) {
                            const rawResult = initialTask.result || '';
                            const cleanedText = cleanAndFormatForMarkdown(rawResult);
                            const contractText = extractFinalContract(cleanedText);
                            setFinalContent(contractText || cleanedText);
                            setShowConfirmation(false);
                        }
                    }
                }
            } catch (error) {
                console.error('获取任务状态失败:', error);
            }
        };

        fetchInitialTask();
    }, [taskId]);

    const handleConfirmGeneration = async () => {
        if (!taskId || !task) return;
        
        try {
            // 发送确认请求，触发文档生成
            const formData = new FormData();
            formData.append('task_id', taskId);
            formData.append('action', 'generate');
            // 添加必须的 demand 参数
            formData.append('demand', task.user_demand || '');
            
            await api.createAnalysisTask(formData);
            
            // 重置状态并重新开始轮询
            setTask({ ...task, status: 'processing', result: '' });
            setShowConfirmation(false);
            setIsLoading(true);
            setFinalContent('');
            
            // 显示提示信息，表示正在分析中
            message.success('已确认，AI正在进行分析，请您耐心等待……');
            
            // 重新开始轮询
            startPolling();
        } catch (error: any) {
            const errorMsg = error.response?.data?.detail || '确认失败。';
            message.error(errorMsg);
            console.error("Confirm generation error:", error);
        }
    };

    const handleCancelGeneration = () => {
        // 用户取消生成，返回主页并保留之前的信息
        navigate('/', { state: { taskId: taskId, demand: task?.user_demand } });
    };
    
    const handleChatSubmit = async (modificationSuggestion: string) => {
        if (!taskId || !task) return;
        if (!finalContent.trim()) {
            message.error('当前没有可供修改的文稿内容。');
            return;
        }
        const docType = task.doc_type;
        if (!docType) {
            message.error('无法确定当前文档类型，无法提交修改。');
            return;
        }

        setIsChatting(true);
        setIsLoading(true);
        stopPolling();
        try {
            // <-- 核心修复：使用 api.
            await api.sendModificationRequest(taskId, {
                original_content: finalContent,
                modification_suggestion: modificationSuggestion,
                type: docType,
            });
            setTask({ ...task, status: 'processing', result: '' });
            startPolling();
        } catch (error: any) {
            const errorMsg = error.response?.data?.detail || '发送修改意见失败。';
            message.error(errorMsg);
            console.error("Send modification error:", error);
            setIsChatting(false);
            setIsLoading(false);
        }
    };
    
    const handleGenerateFile = async (format: 'word' | 'pdf') => {
        if (!finalContent.trim() || !taskId || !task) {
            message.warning("没有可供生成的合同正文内容。");
            return;
        }
        const docType = task.doc_type;
        if (format === 'word' && !docType) {
            message.error('无法确定文档类型，无法生成Word文件。');
            return;
        }
        setIsGenerating(true);
        setDownloadUrl('');
        try {
            // <-- 核心修复：使用 api.
            const response = await api.generateFile(taskId, {
                content: finalContent,
                format: format,
                doc_type: docType,
            });
            const url = response.data.file_url;
            setDownloadUrl(url); 
            const fullUrl = `${window.location.origin}${url}`;
            Modal.success({
              title: '文件生成成功！',
              content: (
                <div>
                  <p>您的文件已准备就绪，可以下载或分享。</p>
                  <Input readOnly value={fullUrl} addonAfter={<CopyOutlined onClick={() => { navigator.clipboard.writeText(fullUrl); message.success('链接已复制！'); }}/>}/>
                </div>
              ),
              okText: "知道了"
            });
        } catch (error: any) {
            const errorMsg = error.response?.data?.detail || '文件生成失败。';
            message.error(errorMsg);
            console.error("Generate file error:", error);
        } finally {
            setIsGenerating(false);
        }
    };
    
    const handleShare = (platform: 'feishu' | 'wechat') => {
        if (!downloadUrl) {
            message.warning('请先生成文件以获取分享链接。');
            return;
        }
        const fullUrl = `${window.location.origin}${downloadUrl}`;
        navigator.clipboard.writeText(fullUrl);
        message.success(`下载链接已复制，请在${platform === 'feishu' ? '飞书' : '微信'}中粘贴发送。`);
    };

    const handleEmailShare = () => {
        if (!downloadUrl) {
            message.warning('请先生成文件以获取分享链接。');
            return;
        }
        const fullUrl = `${window.location.origin}${downloadUrl}`;
        const subject = "分享法律文书文件";
        const body = `您好，

这是为您生成的法律文书文件，请通过以下链接下载：
${fullUrl}

祝好！`;
        window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    };

    // 渲染进度显示组件
    const renderProgressSection = () => {
        if (!isLoading && !task?.status) return null;

        // 如果任务已经完成，不显示进度
        if (task?.status === 'completed' && finalContent) return null;

        return (
            <div className="progress-section">
                {/* 总体进度 */}
                {currentProgress && (
                    <OverallProgress
                        progress={currentProgress.progress}
                        status={currentProgress.status}
                        currentNode={currentProgress.currentNode}
                        estimatedTimeRemaining={currentProgress.estimatedTimeRemaining}
                    />
                )}

                {/* 连接状态指示器 */}
                <div className="connection-status">
                    <Space>
                        <span className={`status-indicator ${isWebSocketConnected ? 'connected' : 'disconnected'}`}>
                            {isWebSocketConnected ? (
                                <><CheckOutlined /> WebSocket连接正常</>
                            ) : (
                                <><CloseOutlined /> {pollingIntervalRef.current ? '轮询模式' : '连接断开'}</>
                            )}
                        </span>
                        {task && (
                            <Tag color={task.status === 'processing' ? 'blue' :
                                      task.status === 'completed' ? 'green' :
                                      task.status === 'failed' ? 'red' : 'default'}>
                                {task.status === 'processing' ? '处理中' :
                                 task.status === 'completed' ? '已完成' :
                                 task.status === 'failed' ? '失败' : '等待中'}
                            </Tag>
                        )}
                    </Space>
                </div>

                {/* 进度详情切换按钮 */}
                {(currentProgress?.workflowSteps || task?.workflowSteps) && (
                    <div className="progress-details-toggle">
                        <Button
                            type="text"
                            icon={<EyeOutlined />}
                            onClick={() => setShowProgressDetails(!showProgressDetails)}
                        >
                            {showProgressDetails ? '隐藏进度详情' : '显示进度详情'}
                        </Button>
                    </div>
                )}

                {/* 详细进度时间线 */}
                {showProgressDetails && (
                    <ProgressTimeline
                        task={task || currentProgress || {}}
                        showTimeEstimates={true}
                        compact={false}
                    />
                )}
            </div>
        );
    };

    if (isLoading && !task) {
        return (
            <div className="loading-page">
                <LoadingPlaceholder />
            </div>
        );
    }

    return (
        <Layout className="result-layout">
            <Header className="result-header">
                <div className="logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
                    <RobotOutlined /> <span>法律文书生成助手</span>
                </div>
                <div>
                    <Button onClick={() => navigate('/')}>创建新任务</Button>
                </div>
            </Header>
            <Content className="result-content">
                {/* 进度显示区域 */}
                {renderProgressSection()}

                <div className="content-grid">
                    <div className="file-display-pane">
                        {isLoading || task?.status === 'processing' ? (
                            <div className="processing-content">
                                {showConfirmation ? (
                                    <Card title="案情分析完成" className="display-card">
                                        <div className="markdown-body">
                                            <Alert
                                                message="确认您的需求"
                                                description={getConfirmationMessage(analysisResult)}
                                                type="info"
                                                showIcon
                                            />
                                            <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
                                                <Button
                                                    type="primary"
                                                    icon={<CheckOutlined />}
                                                    onClick={handleConfirmGeneration}
                                                >
                                                    确认
                                                </Button>
                                                <Button
                                                    icon={<CloseOutlined />}
                                                    onClick={handleCancelGeneration}
                                                >
                                                    返回修改
                                                </Button>
                                            </div>
                                        </div>
                                    </Card>
                                ) : (
                                    <>
                                        <FileDisplay content={finalContent} />
                                        {/* 处理中的占位提示 */}
                                        {!finalContent && (
                                            <div className="processing-placeholder">
                                                <Spin size="large" tip="AI正在分析您的需求，请稍候..." />
                                                <div className="processing-tips">
                                                    <p>• 系统正在分析您的文档内容</p>
                                                    <p>• 提取关键法律要素</p>
                                                    <p>• 生成专业的法律文书</p>
                                                </div>
                                            </div>
                                        )}
                                    </>
                                )}
                            </div>
                        ) : (
                            <FileDisplay content={finalContent} />
                        )}
                    </div>

                    <div className="control-pane">
                        <div className="control-pane-scrollable">
                            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                                {/* 实时进度信息 */}
                                {currentProgress && (
                                    <Card title="实时处理状态" size="small" className="progress-info-card">
                                        <div className="progress-info">
                                            <p><strong>当前节点:</strong> {currentProgress.currentNode || '等待中'}</p>
                                            <p><strong>总体进度:</strong> {Math.round(currentProgress.progress)}%</p>
                                            {currentProgress.estimatedTimeRemaining && (
                                                <p><strong>预计剩余时间:</strong> {Math.round(currentProgress.estimatedTimeRemaining / 60)}分钟</p>
                                            )}
                                        </div>
                                    </Card>
                                )}

                                <ChatWindow isSending={isChatting} onSendMessage={handleChatSubmit} />
                                <Card title="确认与生成文件" size="small">
                                    <Paragraph type="secondary" style={{ marginBottom: 16 }}>
                                        请确认或编辑以下合同正文，然后生成文件。
                                    </Paragraph>
                                    <TextArea
                                        rows={8}
                                        value={finalContent}
                                        onChange={(e) => setFinalContent(e.target.value)}
                                        placeholder="AI生成的最终文稿将在此处显示，您可直接编辑。"
                                        disabled={task?.status !== 'completed' || showConfirmation}
                                    />
                                    <Spin spinning={isGenerating} tip="文件生成中...">
                                        <Row gutter={16} style={{ marginTop: 16 }}>
                                            <Col span={12}>
                                                <Button
                                                    icon={<FileWordOutlined />}
                                                    block
                                                    onClick={() => handleGenerateFile('word')}
                                                    disabled={task?.status !== 'completed' || showConfirmation}
                                                >
                                                    生成 Word
                                                </Button>
                                            </Col>
                                            <Col span={12}>
                                                <Button
                                                    icon={<FilePdfOutlined />}
                                                    block
                                                    onClick={() => handleGenerateFile('pdf')}
                                                    disabled={task?.status !== 'completed' || showConfirmation}
                                                >
                                                    生成 PDF
                                                </Button>
                                            </Col>
                                        </Row>
                                    </Spin>
                                </Card>
                                <Card title="文件交付" size="small">
                                    <Button
                                        type="primary"
                                        icon={<DownloadOutlined />}
                                        disabled={!downloadUrl}
                                        block
                                        href={downloadUrl}
                                        download
                                    >
                                        直接下载
                                    </Button>
                                    <Paragraph style={{ textAlign: 'center', margin: '16px 0', color: '#999' }}>
                                        或分享至
                                    </Paragraph>
                                    <Row gutter={16}>
                                        <Col span={8}>
                                            <Button
                                                icon={<MessageOutlined />}
                                                block
                                                onClick={() => handleShare('feishu')}
                                                disabled={!downloadUrl}
                                            >
                                                飞书
                                            </Button>
                                        </Col>
                                        <Col span={8}>
                                            <Button
                                                icon={<WechatOutlined />}
                                                block
                                                onClick={() => handleShare('wechat')}
                                                disabled={!downloadUrl}
                                            >
                                                微信
                                            </Button>
                                        </Col>
                                        <Col span={8}>
                                            <Button
                                                icon={<MailOutlined />}
                                                block
                                                onClick={handleEmailShare}
                                                disabled={!downloadUrl}
                                            >
                                                邮件
                                            </Button>
                                        </Col>
                                    </Row>
                                </Card>
                            </Space>
                        </div>
                    </div>
                </div>
            </Content>
        </Layout>
    );
};

export default ResultPage;