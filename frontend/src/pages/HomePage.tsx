// frontend/src/pages/HomePage.tsx (最小化修复版本)
import React, { useState, useEffect } from 'react';
import { Button, Input, Upload, message, Spin, Alert, Card, Typography, Tag } from 'antd';
import type { UploadFile, UploadProps } from 'antd';
import { useLocation, useNavigate } from 'react-router-dom';
import { InboxOutlined, SendOutlined, RobotOutlined, FileTextOutlined } from '@ant-design/icons';
import api from '../api';
import { useAuth } from '../context/AuthContext';
import { logger } from '../utils/logger';
import TemplateSelector from '../components/TemplateSelector';
import { ContractTemplate } from '../api/contractTemplates';

const { TextArea } = Input;
const { Dragger } = Upload;

const HomePage: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { logout } = useAuth();

    // 复制原始状态和函数
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string>('');
    const [fileList, setFileList] = useState<UploadFile[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<ContractTemplate | null>(null);
    const [documentType, setDocumentType] = useState<string>('文书生成');
    const [userInput, setUserInput] = useState('');

    useEffect(() => {
        const params = new URLSearchParams(location.search);
        const type = params.get('type');
        if (type === 'judicial_document' || type === 'contract_drafting') {
            setDocumentType(type);
        }
    }, [location.search]);

    const draggerProps: UploadProps = {
        name: 'file',
        multiple: true,
        fileList,
        beforeUpload: () => false,
        onChange: ({ fileList: newFileList }) => {
            setFileList(newFileList.slice(-5));
        },
        onDrop: (e) => {
            logger.debug('Dropped files', e.dataTransfer.files);
        },
    };

    const handleSubmit = async () => {
        if (!userInput.trim()) {
            message.error('请输入您的需求描述');
            return;
        }

        setLoading(true);
        setError('');

        try {
            const formData = new FormData();
            formData.append('query', userInput);
            formData.append('demand_categories', documentType);

            fileList.forEach((file) => {
                if (file.originFileObj) {
                    formData.append('files', file.originFileObj, file.name);
                }
            });

            if (selectedTemplate && selectedTemplate.id) {
                formData.append('template_id', selectedTemplate.id);
            }

            const response = await api.post('/workflow/start', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                }
            });

            if (response.data.task_id) {
                const docType = documentType === 'judicial_document' ? '司法文书' : selectedTemplate?.category || '文书生成';
                navigate(`/result?task_id=${response.data.task_id}&doc_type=${encodeURIComponent(docType)}`);
            } else {
                throw new Error('No task ID received');
            }
        } catch (error: any) {
            console.error('Submit error:', error);
            const errorMsg = error.response?.data?.detail || error.message || '提交失败，请重试';
            setError(errorMsg);
            message.error(errorMsg);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="home-layout">
            <div className="home-header">
                <div className="logo">
                    <RobotOutlined />
                    <span>法律文书生成助手</span>
                </div>
                <Button type="link" onClick={logout}>退出登录</Button>
            </div>
            <div className="home-content">
                <Spin spinning={loading} tip="正在提交分析任务..." size="large">
                    <Card className="form-card" bordered={false}>
                        <div className="form-header">
                            <Typography.Title level={2}>
                                {documentType === 'judicial_document' ? '司法文书生成' : '智能案情分析'}
                            </Typography.Title>
                            <Typography.Paragraph type="secondary">
                                {documentType === 'judicial_document'
                                    ? '请详细说明您的司法文书需求，并上传相关证据材料，AI将基于您提供的信息为您生成专业的司法文书。'
                                    : '选择合适的合同模版，说明您的需求，并上传相关材料，AI Agent 将基于您选择的模版进行分析，并生成最适合的法律文书。'
                                }
                            </Typography.Paragraph>
                            {documentType === 'judicial_document' && (
                                <Tag color="blue" style={{ marginTop: 8 }}>司法文书工作流已启动</Tag>
                            )}
                        </div>

                        {documentType !== 'judicial_document' && (
                            <div className="form-section">
                                <Typography.Title level={5} className="section-title">
                                    1. 选择合同模版
                                </Typography.Title>
                                <TemplateSelector
                                    onSelectTemplate={setSelectedTemplate}
                                    selectedTemplateId={selectedTemplate?.id}
                                />
                            </div>
                        )}

                        {selectedTemplate && documentType !== 'judicial_document' && (
                            <Card size="small" style={{ marginTop: 12, backgroundColor: '#f6ffed' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div>
                                        <Typography.Text strong>已选择模版: {selectedTemplate.name}</Typography.Text>
                                        <div style={{ marginTop: 4 }}>
                                            <Tag color="blue">{selectedTemplate.category}</Tag>
                                            <Tag color={selectedTemplate.is_public ? 'green' : 'orange'}>
                                                {selectedTemplate.is_public ? '公有' : '私有'}
                                            </Tag>
                                            {selectedTemplate.rating > 0 && (
                                                <Tag color="gold">⭐ {selectedTemplate.rating.toFixed(1)}</Tag>
                                            )}
                                        </div>
                                        {selectedTemplate.description && (
                                            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                                                {selectedTemplate.description}
                                            </Typography.Text>
                                        )}
                                    </div>
                                    <Button
                                        icon={<FileTextOutlined />}
                                        size="small"
                                    >
                                        下载模版
                                    </Button>
                                </div>
                            </Card>
                        )}

                        <div className="form-section">
                            <Typography.Title level={5} className="section-title">
                                <InboxOutlined /> {documentType === 'judicial_document' ? '2. 上传证据材料' : '2. 上传相关材料'} (可选)
                            </Typography.Title>
                            <Dragger {...draggerProps} className="upload-dragger">
                                <p className="ant-upload-drag-icon"><InboxOutlined /></p>
                                <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                                <p className="ant-upload-hint">
                                    {documentType === 'judicial_document'
                                        ? '支持单个或多个文件，如证据材料、起诉状、答辩状、判决书等'
                                        : '支持单个或多个文件，如合同、聊天记录、起诉状等'
                                    }
                                </p>
                            </Dragger>
                        </div>

                        <div className="form-section">
                            <Typography.Title level={5} className="section-title">
                                <SendOutlined /> 3. 描述您的需求
                            </Typography.Title>
                            <TextArea
                                rows={4}
                                value={userInput}
                                onChange={(e) => setUserInput(e.target.value)}
                                placeholder={
                                    documentType === 'judicial_document'
                                        ? '请详细描述您的司法文书需求，例如：起草答辩状、修改合同条款、生成起诉状等...'
                                        : selectedTemplate
                                            ? `请描述您对《${selectedTemplate.name}》的具体需求和修改要求...`
                                            : '请描述您的案情和法律需求...'
                                }
                                maxLength={2000}
                                showCount
                            />
                        </div>

                        <Button
                            type="primary"
                            size="large"
                            block
                            className="submit-button"
                            onClick={handleSubmit}
                            disabled={loading}
                        >
                            开始智能分析
                        </Button>

                        {error && <Alert message="操作失败" description={error} type="error" showIcon style={{marginTop: 16}} />}
                    </Card>
                </Spin>
            </div>
            <div style={{ textAlign: 'center', padding: '20px' }}>法律文书生成助手 ©2025 Created by YourTeam</div>
        </div>
    );
};

export default HomePage;