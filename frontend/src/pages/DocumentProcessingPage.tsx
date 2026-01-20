// frontend/src/pages/DocumentProcessingPage.tsx
/**
 * 文档处理中心
 * 包含三个子模块：
 * 1. 文档预处理 - 将非word文件转换为可编辑的word文件（支持预览）
 * 2. 文档智能编辑 - 用户输入AI输出内容，生成可直接使用的Word/PDF文件（支持预览）
 * 3. 文件比对 - 帮助用户比对两份文件的差异
 */
import React, { useState, useEffect } from 'react';
import {
  Card,
  Typography,
  Row,
  Col,
  Button,
  Upload,
  Input,
  message,
  Tabs,
  Progress,
  Tag,
  Space,
  Divider,
  Alert,
  List,
  Descriptions,
  Modal,
  Radio,
  Select,
  Spin,
} from 'antd';
import type { UploadProps, TabsProps } from 'antd';
import {
  FileTextOutlined,
  SwapOutlined,
  DiffOutlined,
  UploadOutlined,
  DownloadOutlined,
  CheckCircleOutlined,
  LoadingOutlined,
  ExperimentOutlined,
  RobotOutlined,
  FileSearchOutlined,
  DeleteOutlined,
  EyeOutlined,
  FilePdfOutlined,
  FileWordOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { DocumentEditor } from '@onlyoffice/document-editor-react';
import ModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
import { useSessionPersistence } from '../hooks/useSessionPersistence';
import { getApiBaseUrl } from '../utils/apiConfig';
import './DocumentProcessingPage.css';

const { Title, Text, Paragraph } = Typography;
const { Dragger } = Upload;
const { TextArea } = Input;
const { Option } = Select;

interface ConvertedFile {
  uid: string;
  name: string;
  originalFormat: string;
  outputFormat: string;
  status: 'uploading' | 'converting' | 'success' | 'error';
  progress: number;
  outputPath?: string;
  downloadUrl?: string;
  previewUrl?: string;
  metadata?: {
    pages?: number;
    words?: number;
    paragraphs?: number;
  };
  error?: string;
}

interface ComparisonFile {
  id: string;
  name: string;
  file?: File;
  url?: string;
}

interface GeneratedDocument {
  contractId: number;
  filename: string;
  docxPath: string;
  pdfPath: string;
  previewUrl: string;
  downloadDocxUrl: string;
  downloadPdfUrl: string;
  status: string;
  config?: any;
  token?: string;
}

type EditingMode = 'text' | 'file';

const DocumentProcessingPage: React.FC = () => {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('preprocess');

  // ========== 会话持久化 ==========
  interface DocumentProcessingSessionData {
    activeTab: string;
    convertedFiles: ConvertedFile[];
    editingMode: EditingMode;
    aiContent: string;
    documentType: 'contract' | 'letter';
    outputFormat: 'docx' | 'pdf';
    generatedDoc: GeneratedDocument | null;
    compareFile1: ComparisonFile | null;
    compareFile2: ComparisonFile | null;
  }

  const {
    hasSession,
    saveSession,
    clearSession,
    isLoading: isRestoringSession
  } = useSessionPersistence<DocumentProcessingSessionData>('document_processing_session', {
    expirationTime: 2 * 60 * 60 * 1000, // 2小时
    onRestore: (sessionId, data) => {
      console.log('[文档处理] 恢复会话:', data);
      setActiveTab(data.activeTab || 'preprocess');
      setConvertedFiles(data.convertedFiles || []);
      setEditingMode(data.editingMode || 'text');
      setAiContent(data.aiContent || '');
      setDocumentType(data.documentType || 'contract');
      setOutputFormat(data.outputFormat || 'docx');
      setGeneratedDoc(data.generatedDoc || null);
      setCompareFile1(data.compareFile1 || null);
      setCompareFile2(data.compareFile2 || null);
      message.success('已恢复之前的文档处理会话');
    }
  });

  // 保存会话状态
  const saveCurrentState = () => {
    saveSession(Date.now().toString(), {
      activeTab,
      convertedFiles,
      editingMode,
      aiContent,
      documentType,
      outputFormat,
      generatedDoc,
      compareFile1,
      compareFile2,
    });
  };

  // ========== 所有状态变量声明 ==========
  // 文档预处理状态
  const [convertedFiles, setConvertedFiles] = useState<ConvertedFile[]>([]);

  // 文档智能编辑状态
  const [editingMode, setEditingMode] = useState<EditingMode>('text'); // text 或 file
  const [aiContent, setAiContent] = useState('');
  const [editingFile, setEditingFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<'contract' | 'letter'>('contract');
  const [outputFormat, setOutputFormat] = useState<'docx' | 'pdf'>('docx');
  const [generatedDoc, setGeneratedDoc] = useState<GeneratedDocument | null>(null);
  const [generating, setGenerating] = useState(false);
  const [previewModalVisible, setPreviewModalVisible] = useState(false);
  const [previewUrl, setPreviewUrl] = useState('');
  const [previewConfig, setPreviewConfig] = useState<any>(null);

  // 文件比对状态
  const [compareFile1, setCompareFile1] = useState<ComparisonFile | null>(null);
  const [compareFile2, setCompareFile2] = useState<ComparisonFile | null>(null);
  const [compareResult, setCompareResult] = useState<any>(null);
  const [compareLoading, setCompareLoading] = useState(false);

  // 监听状态变化，自动保存
  useEffect(() => {
    if (convertedFiles.length > 0 || aiContent || generatedDoc || compareFile1 || compareFile2) {
      saveCurrentState();
    }
  }, [activeTab, convertedFiles, editingMode, aiContent, documentType, outputFormat, generatedDoc, compareFile1, compareFile2]);
  // ========== 会话持久化结束 ==========

  // ========== 文档预处理函数 ==========
  const handlePreprocessUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    const formData = new FormData();
    formData.append('file', file as File);

    const fileItem: ConvertedFile = {
      uid: (file as File).name + Date.now(),
      name: (file as File).name,
      originalFormat: (file as File).name.split('.').pop() || '',
      outputFormat: 'docx',
      status: 'uploading',
      progress: 0,
    };

    setConvertedFiles((prev) => [...prev, fileItem]);

    try {
      const response = await fetch(`${getApiBaseUrl()}/api/preprocessor/convert`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('转换失败');
      }

      const result = await response.json();
      const outputFilename = result.output_filename || result.output_path?.split('/')?.pop();
      const previewUrl = `${getApiBaseUrl()}/storage/uploads/${outputFilename}`;

      setConvertedFiles((prev) =>
        prev.map((item) =>
          item.uid === fileItem.uid
            ? {
                ...item,
                status: 'success',
                progress: 100,
                outputPath: result.output_path,
                downloadUrl: result.download_url,
                previewUrl: previewUrl,
                metadata: result.metadata,
              }
            : item
        )
      );

      message.success(`${(file as File).name} 转换成功！`);
      onSuccess?.(result);
    } catch (error) {
      setConvertedFiles((prev) =>
        prev.map((item) =>
          item.uid === fileItem.uid
            ? {
                ...item,
                status: 'error',
                error: error instanceof Error ? error.message : '转换失败',
              }
            : item
        )
      );
      message.error(`${(file as File).name} 转换失败`);
      onError?.(error as Error);
    }
  };

  const handlePreviewConverted = async (file: ConvertedFile) => {
    try {
      // 获取文档ID，从文件路径中提取
      const filename = file.outputPath?.split('/').pop() || file.name;
      const response = await fetch(`${getApiBaseUrl()}/api/document/preview/by-filename/${filename}`);
      if (!response.ok) {
        // 如果专用接口不存在，使用预览URL直接预览
        if (file.previewUrl) {
          setPreviewUrl(file.previewUrl);
          setPreviewConfig(null);
          setPreviewModalVisible(true);
        } else {
          message.warning('预览不可用');
        }
        return;
      }
      const data = await response.json();
      setPreviewConfig(data);
      setPreviewModalVisible(true);
    } catch (error) {
      // 降级方案：使用预览URL直接预览
      if (file.previewUrl) {
        setPreviewUrl(file.previewUrl);
        setPreviewConfig(null);
        setPreviewModalVisible(true);
      } else {
        message.warning('预览不可用');
      }
    }
  };

  const handleDownloadConverted = (file: ConvertedFile) => {
    if (file.downloadUrl) {
      window.open(`${getApiBaseUrl()}${file.downloadUrl}`, '_blank');
    }
  };

  const handleDeleteConverted = (uid: string) => {
    setConvertedFiles((prev) => prev.filter((item) => item.uid !== uid));
  };

  // ========== 文档智能编辑函数 ==========
  const handleEditingFileUpload: UploadProps['customRequest'] = async (options) => {
    const { file } = options;
    setEditingFile(file as File);
    message.success('文件上传成功');
  };

  const handleGenerateDocument = async () => {
    // 检查是否有内容
    const hasTextContent = aiContent.trim().length > 0;
    const hasFileContent = editingFile !== null;

    if (!hasTextContent && !hasFileContent) {
      message.warning('请输入文本内容或上传文件');
      return;
    }

    setGenerating(true);

    try {
      if (editingMode === 'text' && hasTextContent) {
        // 文本模式：调用文档生成 API
        const response = await fetch(`${getApiBaseUrl()}/api/document/generate-from-content`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            content: aiContent,
            output_format: outputFormat,
            filename: `generated_${Date.now()}.${outputFormat}`,
          }),
        });

        if (!response.ok) {
          throw new Error('文档生成失败');
        }

        const result = await response.json();

        setGeneratedDoc({
          contractId: result.contract_id,
          filename: result.filename,
          docxPath: result.docx_path,
          pdfPath: result.pdf_path,
          previewUrl: result.preview_url,
          downloadDocxUrl: result.download_docx_url,
          downloadPdfUrl: result.download_pdf_url,
          status: result.status,
          config: result.config,
          token: result.token,
        });

        message.success('文档生成成功！');
      } else if (editingMode === 'file' && hasFileContent) {
        // 文件模式：上传不规范文件，AI 处理成规范合同/函件
        const formData = new FormData();
        formData.append('file', editingFile);
        formData.append('output_format', outputFormat);
        formData.append('document_type', documentType);

        const response = await fetch(`${getApiBaseUrl()}/api/document/process-file-to-standard`, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error('文件处理失败');
        }

        const result = await response.json();

        setGeneratedDoc({
          contractId: result.contract_id,
          filename: result.filename,
          docxPath: result.docx_path,
          pdfPath: result.pdf_path,
          previewUrl: result.preview_url,
          downloadDocxUrl: result.download_docx_url,
          downloadPdfUrl: result.download_pdf_url,
          status: result.status,
          config: result.config,
          token: result.token,
        });

        message.success('文件处理成功！');
      }
    } catch (error) {
      message.error(editingMode === 'text' ? '文档生成失败' : '文件处理失败');
      console.error(error);
    } finally {
      setGenerating(false);
    }
  };

  const handlePreviewGenerated = async () => {
    if (!generatedDoc) return;

    try {
      const response = await fetch(`${getApiBaseUrl()}${generatedDoc.previewUrl}`);
      if (!response.ok) {
        message.warning('获取预览配置失败');
        return;
      }
      const data = await response.json();
      setPreviewConfig(data);
      setPreviewModalVisible(true);
    } catch (error) {
      message.error('预览功能暂时不可用');
    }
  };

  const handleDownloadGenerated = (format: 'docx' | 'pdf') => {
    if (!generatedDoc) return;

    const url = format === 'docx' ? generatedDoc.downloadDocxUrl : generatedDoc.downloadPdfUrl;
    if (url) {
      window.open(`${getApiBaseUrl()}${url}`, '_blank');
    }
  };

  // ========== 文件比对函数 ==========
  const handleCompareUpload = (fileNumber: 1 | 2) => {
    return async (options: any) => {
      const { file } = options;
      const fileData: ComparisonFile = {
        id: Date.now().toString(),
        name: (file as File).name,
        file: file as File,
      };

      if (fileNumber === 1) {
        setCompareFile1(fileData);
      } else {
        setCompareFile2(fileData);
      }

      message.success(`文件 ${(file as File).name} 上传成功`);
    };
  };

  const handleStartCompare = async () => {
    if (!compareFile1?.file || !compareFile2?.file) {
      message.warning('请先上传两份文件');
      return;
    }

    setCompareLoading(true);

    try {
      const formData = new FormData();
      formData.append('file1', compareFile1.file);
      formData.append('file2', compareFile2.file);

      message.info('文件比对功能正在开发中');
    } catch (error) {
      message.error('比对失败');
    } finally {
      setCompareLoading(false);
    }
  };

  // ========== 示例内容 ==========
  const exampleContent = `# 销售合同

**合同编号：** SALE-2024-001

## 甲方（卖方）
- 名称：_____________________
- 地址：_____________________
- 联系人：___________________
- 电话：_____________________

## 乙方（买方）
- 名称：_____________________
- 地址：_____________________
- 联系人：___________________
- 电话：_____________________

## 第一条 标的物
1.1 产品名称：_________________
1.2 规格型号：_________________
1.3 数量：_____________________
1.4 单价：_____________________
1.5 总价：_____________________

## 第二条 交货
2.1 交货时间：_________________
2.2 交货地点：_________________

## 第三条 付款方式
3.1 乙方应于合同签署后___日内支付合同总额的___%作为预付款。
3.2 余款应在收到货物并验收合格后___日内付清。

## 第四条 违约责任
4.1 甲方未按期交货的，每逾期一日，应向乙方支付合同总额___%的违约金。
4.2 乙方未按期付款的，每逾期一日，应向甲方支付应付款项___%的违约金。

## 第五条 争议解决
本合同履行过程中发生的争议，双方应友好协商解决；协商不成的，提交甲方所在地人民法院诉讼解决。

## 签署
甲方（盖章）：_________________  乙方（盖章）：_________________
代表签字：___________________  代表签字：___________________
日期：____年__月__日          日期：____年__月__日`;

  // ========== Tab 配置 ==========
  const tabItems: TabsProps['items'] = [
    {
      key: 'preprocess',
      label: (
        <span>
          <SwapOutlined />
          文档预处理
        </span>
      ),
      children: (
        <div className="preprocess-tab">
          <Alert
            message="文档预处理功能"
            description="将 PDF、DOC、TXT 等非 Word 格式文件统一转换为可编辑的 Word (.docx) 格式。转换过程中会自动处理页码、空格、换行等格式问题。支持在线预览转换后的文档。"
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
          />

          <Card title="文件上传" style={{ marginBottom: 24 }}>
            <Dragger
              accept=".pdf,.doc,.docx,.txt,.rtf,.odt"
              multiple
              customRequest={handlePreprocessUpload}
              showUploadList={false}
            >
              <p className="ant-upload-drag-icon">
                <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
              </p>
              <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
              <p className="ant-upload-hint">
                支持格式：PDF、DOC、DOCX、TXT、RTF、ODT
                <br />
                支持批量上传，自动转换为 Word 格式
              </p>
            </Dragger>
          </Card>

          {convertedFiles.length > 0 && (
            <Card title="转换结果">
              <List
                dataSource={convertedFiles}
                renderItem={(file) => (
                  <List.Item
                    actions={[
                      file.status === 'success' && (
                        <Button
                          type="link"
                          icon={<EyeOutlined />}
                          onClick={() => handlePreviewConverted(file)}
                        >
                          预览
                        </Button>
                      ),
                      file.status === 'success' && (
                        <Button
                          type="link"
                          icon={<DownloadOutlined />}
                          onClick={() => handleDownloadConverted(file)}
                        >
                          下载
                        </Button>
                      ),
                      <Button
                        type="link"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleDeleteConverted(file.uid)}
                      >
                        删除
                      </Button>,
                    ]}
                  >
                    <List.Item.Meta
                      avatar={
                        file.status === 'success' ? (
                          <CheckCircleOutlined style={{ fontSize: 24, color: '#52c41a' }} />
                        ) : file.status === 'error' ? (
                          <FileSearchOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
                        ) : (
                          <LoadingOutlined style={{ fontSize: 24, color: '#1890ff' }} />
                        )
                      }
                      title={
                        <Space>
                          <Text strong>{file.name}</Text>
                          <Tag color={file.status === 'success' ? 'success' : file.status === 'error' ? 'error' : 'processing'}>
                            {file.status === 'success' ? '转换成功' : file.status === 'error' ? '转换失败' : '处理中'}
                          </Tag>
                        </Space>
                      }
                      description={
                        <Space direction="vertical" style={{ width: '100%' }}>
                          <Text type="secondary">
                            {file.originalFormat.toUpperCase()} → {file.outputFormat.toUpperCase()}
                          </Text>
                          {file.status === 'converting' && <Progress percent={file.progress} size="small" />}
                          {file.metadata && (
                            <Text type="secondary">
                              页数: {file.metadata.pages} | 字数: {file.metadata.words?.toLocaleString()} |
                              段落数: {file.metadata.paragraphs}
                            </Text>
                          )}
                          {file.error && <Text type="danger">{file.error}</Text>}
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            </Card>
          )}

          <Divider orientation="left">功能说明</Divider>
          <Descriptions bordered column={2} size="small">
            <Descriptions.Item label="AI 辅助处理" span={2}>
              <Tag color="blue">已启用</Tag> 使用 Qwen3-VL 模型智能识别页码、段落边界
            </Descriptions.Item>
            <Descriptions.Item label="页码处理">自动识别并删除页眉页脚中的页码</Descriptions.Item>
            <Descriptions.Item label="格式调整">智能处理不正常的空格和换行</Descriptions.Item>
            <Descriptions.Item label="段落合并">识别被错误分割的段落并自动合并</Descriptions.Item>
            <Descriptions.Item label="文档预览">支持在线预览转换后的 Word 文档</Descriptions.Item>
            <Descriptions.Item label="支持格式">PDF、DOC、DOCX、TXT、RTF、ODT</Descriptions.Item>
          </Descriptions>
        </div>
      ),
    },
    {
      key: 'editing',
      label: (
        <span>
          <RobotOutlined />
          文档智能编辑
        </span>
      ),
      children: (
        <div className="editing-tab">
          <Alert
            message="文档智能编辑功能"
            description="支持两种方式：1) 将 AI 生成的内容转换为可直接使用的 Word/PDF 文档；2) 将不规范的 Word 文件处理成标准的合同或函件格式。"
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
          />

          <Card title="选择编辑模式" style={{ marginBottom: 16 }}>
            <Space size="large">
              <Button
                type={editingMode === 'text' ? 'primary' : 'default'}
                icon={<FileTextOutlined />}
                onClick={() => setEditingMode('text')}
              >
                文本内容生成
              </Button>
              <Button
                type={editingMode === 'file' ? 'primary' : 'default'}
                icon={<UploadOutlined />}
                onClick={() => setEditingMode('file')}
              >
                文件规范化处理
              </Button>
            </Space>
          </Card>

          <Row gutter={24}>
            <Col span={editingMode === 'text' ? 14 : 12}>
              <Card
                title={editingMode === 'text' ? '输入内容' : '上传文件'}
                extra={
                  editingMode === 'text' && (
                    <Button
                      type="link"
                      onClick={() => setAiContent(exampleContent)}
                    >
                      填入示例
                    </Button>
                  )
                }
              >
                {editingMode === 'text' ? (
                  <Space direction="vertical" style={{ width: '100%' }} size="large">
                    <div>
                      <Text strong style={{ marginBottom: 8, display: 'block' }}>
                        AI 生成的内容（支持 Markdown 格式）：
                      </Text>
                      <TextArea
                        value={aiContent}
                        onChange={(e) => setAiContent(e.target.value)}
                        placeholder="请粘贴 AI 生成的内容，支持：
# 一级标题
## 二级标题
**粗体文字**
- 列表项
1. 有序列表

等 Markdown 格式，以及 / * 等特殊字符..."
                        rows={16}
                        style={{ fontFamily: 'monospace', fontSize: '13px' }}
                      />
                    </div>
                  </Space>
                ) : (
                  <Space direction="vertical" style={{ width: '100%' }} size="large">
                    <div>
                      <Text strong style={{ marginBottom: 8, display: 'block' }}>
                        上传不规范的 Word/PDF 文件：
                      </Text>
                      <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                        AI 将自动识别文档类型、提取关键信息、重新格式化生成标准合同或函件
                      </Text>
                      <Dragger
                        accept=".pdf,.doc,.docx,.txt"
                        maxCount={1}
                        customRequest={handleEditingFileUpload}
                        showUploadList={false}
                        onRemove={() => setEditingFile(null)}
                      >
                        {editingFile ? (
                          <div>
                            <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                            <p className="ant-upload-text">{editingFile.name}</p>
                          </div>
                        ) : (
                          <div>
                            <p className="ant-upload-drag-icon">
                              <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                            </p>
                            <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
                            <p className="ant-upload-hint">支持格式：PDF、DOC、DOCX、TXT</p>
                          </div>
                        )}
                      </Dragger>
                    </div>

                    <div>
                      <Text strong style={{ marginBottom: 8, display: 'block' }}>
                        文档类型：
                      </Text>
                      <Radio.Group
                        value={documentType}
                        onChange={(e) => setDocumentType(e.target.value)}
                        style={{ width: '100%' }}
                      >
                        <Radio value="contract" style={{ display: 'block', marginBottom: 8 }}>
                          <FileTextOutlined /> 标准合同
                        </Radio>
                        <Radio value="letter" style={{ display: 'block' }}>
                          <FileTextOutlined /> 正式函件
                        </Radio>
                      </Radio.Group>
                    </div>
                  </Space>
                )}
              </Card>
            </Col>

            <Col span={editingMode === 'text' ? 10 : 12}>
              <Card
                title="生成结果"
                extra={
                  generatedDoc && (
                    <Tag color="success">处理完成</Tag>
                  )
                }
              >
                {generating ? (
                  <div style={{ textAlign: 'center', padding: '60px 0' }}>
                    <Spin size="large" />
                    <p style={{ marginTop: 24, color: '#666' }}>
                      {editingMode === 'text' ? '正在生成文档...' : '正在处理文件...'}
                    </p>
                    <Progress percent={75} status="active" style={{ marginTop: 16 }} />
                  </div>
                ) : generatedDoc ? (
                  <div>
                    <Descriptions column={1} size="small" bordered>
                      <Descriptions.Item label="文件名">{generatedDoc.filename}</Descriptions.Item>
                      <Descriptions.Item label="状态">
                        <Tag color="success">{generatedDoc.status}</Tag>
                      </Descriptions.Item>
                      <Descriptions.Item label="格式">
                        <Tag color="blue">{outputFormat.toUpperCase()}</Tag>
                      </Descriptions.Item>
                    </Descriptions>

                    <Divider style={{ margin: '24px 0' }} />

                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Button
                        block
                        icon={<EyeOutlined />}
                        onClick={handlePreviewGenerated}
                      >
                        在线预览
                      </Button>
                      <Button
                        block
                        icon={<FileWordOutlined />}
                        onClick={() => handleDownloadGenerated('docx')}
                      >
                        下载 Word 文档
                      </Button>
                      <Button
                        block
                        icon={<FilePdfOutlined />}
                        onClick={() => handleDownloadGenerated('pdf')}
                      >
                        下载 PDF 文档
                      </Button>
                    </Space>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '60px 0', color: '#999' }}>
                    <ExperimentOutlined style={{ fontSize: 64, marginBottom: 16, color: '#d9d9d9' }} />
                    <p>
                      {editingMode === 'text'
                        ? '在左侧输入内容后点击"生成文档"'
                        : '上传文件后点击"开始处理"'}
                    </p>
                  </div>
                )}
              </Card>

              {/* 输出格式选择 - 放在右侧列 */}
              {editingMode === 'text' && (
                <Card title="输出格式" style={{ marginTop: 16 }}>
                  <Radio.Group
                    value={outputFormat}
                    onChange={(e) => setOutputFormat(e.target.value)}
                    style={{ width: '100%' }}
                  >
                    <Radio value="docx" style={{ display: 'block', marginBottom: 12 }}>
                      <FileWordOutlined /> Word 文档 (.docx)
                    </Radio>
                    <Radio value="pdf" style={{ display: 'block' }}>
                      <FilePdfOutlined /> PDF 文档 (.pdf)
                    </Radio>
                  </Radio.Group>

                  <Divider />

                  <Button
                    type="primary"
                    size="large"
                    block
                    icon={<RobotOutlined />}
                    loading={generating}
                    onClick={handleGenerateDocument}
                    disabled={!aiContent.trim()}
                  >
                    生成文档
                  </Button>
                </Card>
              )}

              {editingMode === 'file' && (
                <Card title="输出格式" style={{ marginTop: 16 }}>
                  <Radio.Group
                    value={outputFormat}
                    onChange={(e) => setOutputFormat(e.target.value)}
                    style={{ width: '100%' }}
                  >
                    <Radio value="docx" style={{ display: 'block', marginBottom: 12 }}>
                      <FileWordOutlined /> Word 文档 (.docx)
                    </Radio>
                    <Radio value="pdf" style={{ display: 'block' }}>
                      <FilePdfOutlined /> PDF 文档 (.pdf)
                    </Radio>
                  </Radio.Group>

                  <Divider />

                  <Button
                    type="primary"
                    size="large"
                    block
                    icon={<RobotOutlined />}
                    loading={generating}
                    onClick={handleGenerateDocument}
                    disabled={!editingFile}
                  >
                    开始处理
                  </Button>
                </Card>
              )}
            </Col>
          </Row>

          <Divider orientation="left">使用说明</Divider>
          <Card size="small">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text strong>文本内容生成模式：</Text>
              <Text>• 支持粘贴 AI（如 DeepSeek、ChatGPT 等）生成的合同、函件内容</Text>
              <Text>• 自动识别 Markdown 格式标记：# 标题、**粗体**、- 列表等</Text>
              <Text>• 可选择输出为 Word 或 PDF 格式</Text>
              <Text>• 生成后支持在线预览和下载</Text>
              <Divider style={{ margin: '8px 0' }} />
              <Text strong>文件规范化处理模式：</Text>
              <Text>• 上传不规范的 Word/PDF 文件</Text>
              <Text>• AI 自动识别文档类型（合同/函件）</Text>
              <Text>• 提取关键信息并重新格式化</Text>
              <Text>• 生成标准格式的合同或函件文档</Text>
            </Space>
          </Card>
        </div>
      ),
    },
    {
      key: 'compare',
      label: (
        <span>
          <DiffOutlined />
          文件比对
        </span>
      ),
      children: (
        <div className="compare-tab">
          <Alert
            message="文件比对功能"
            description="上传两份文档，AI 将自动识别它们之间的差异，包括新增、删除、修改的内容，并生成详细的比对报告。"
            type="info"
            showIcon
            style={{ marginBottom: 24 }}
          />

          <Row gutter={24}>
            <Col span={12}>
              <Card title="原始文档">
                <Dragger
                  accept=".pdf,.doc,.docx,.txt"
                  maxCount={1}
                  customRequest={handleCompareUpload(1)}
                  showUploadList={false}
                  onRemove={() => setCompareFile1(null)}
                >
                  {compareFile1 ? (
                    <div>
                      <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                      <p className="ant-upload-text">{compareFile1.name}</p>
                    </div>
                  ) : (
                    <div>
                      <p className="ant-upload-drag-icon">
                        <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                      </p>
                      <p className="ant-upload-text">上传原始文档</p>
                    </div>
                  )}
                </Dragger>
              </Card>
            </Col>

            <Col span={12}>
              <Card title="对比文档">
                <Dragger
                  accept=".pdf,.doc,.docx,.txt"
                  maxCount={1}
                  customRequest={handleCompareUpload(2)}
                  showUploadList={false}
                  onRemove={() => setCompareFile2(null)}
                >
                  {compareFile2 ? (
                    <div>
                      <CheckCircleOutlined style={{ fontSize: 48, color: '#52c41a' }} />
                      <p className="ant-upload-text">{compareFile2.name}</p>
                    </div>
                  ) : (
                    <div>
                      <p className="ant-upload-drag-icon">
                        <UploadOutlined style={{ fontSize: 48, color: '#1890ff' }} />
                      </p>
                      <p className="ant-upload-text">上传对比文档</p>
                    </div>
                  )}
                </Dragger>
              </Card>
            </Col>
          </Row>

          {compareFile1 && compareFile2 && (
            <div style={{ textAlign: 'center', marginTop: 24 }}>
              <Button
                type="primary"
                size="large"
                icon={<DiffOutlined />}
                loading={compareLoading}
                onClick={handleStartCompare}
              >
                开始比对
              </Button>
            </div>
          )}

          {compareResult && (
            <Card title="比对结果" style={{ marginTop: 24 }}>
              {/* TODO: 实现比对结果展示 */}
              <p>比对结果将在此显示</p>
            </Card>
          )}

          <Divider orientation="left">功能说明</Divider>
          <Descriptions bordered column={2} size="small">
            <Descriptions.Item label="比对模式">文本内容比对、格式差异比对</Descriptions.Item>
            <Descriptions.Item label="差异高亮">新增（绿色）、删除（红色）、修改（黄色）</Descriptions.Item>
            <Descriptions.Item label="支持格式">PDF、DOC、DOCX、TXT</Descriptions.Item>
            <Descriptions.Item label="报告导出">支持导出 Word、PDF 格式的比对报告</Descriptions.Item>
          </Descriptions>
        </div>
      ),
    },
  ];

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', background: '#f0f2f5' }}>
      {/* 统一导航栏 */}
      <ModuleNavBar currentModuleKey="document-processing" />

      {/* 原有内容区域 */}
      <div style={{ flex: 1, padding: '24px' }}>
        {/* 会话恢复提示 */}
        {hasSession && !isRestoringSession && (
          <Alert
            message="检测到之前的会话"
            description={
              <Space direction="vertical" size="small">
                <Text>系统检测到您之前有一个未完成的文档处理会话。您可以：</Text>
                <Space>
                  <Button
                    size="small"
                    type="primary"
                    onClick={() => {
                      message.info('已恢复之前的会话');
                    }}
                  >
                    继续之前的操作
                  </Button>
                  <Button
                    size="small"
                    onClick={() => {
                      clearSession();
                      setActiveTab('preprocess');
                      setConvertedFiles([]);
                      setEditingMode('text');
                      setAiContent('');
                      setDocumentType('contract');
                      setOutputFormat('docx');
                      setGeneratedDoc(null);
                      setCompareFile1(null);
                      setCompareFile2(null);
                      message.info('已清除之前的会话，可以开始新的文档处理');
                    }}
                  >
                    开始新操作
                  </Button>
                </Space>
              </Space>
            }
            type="info"
            closable
            style={{ marginBottom: 16 }}
          />
        )}

        <Card
          bordered={false}
          title={
            <Space>
              <FileTextOutlined style={{ fontSize: 24, color: '#1890ff' }} />
              <Title level={3} style={{ margin: 0 }}>
                文档处理中心
              </Title>
            </Space>
          }
        >
          <Tabs
            activeKey={activeTab}
            onChange={setActiveTab}
            items={tabItems}
            size="large"
          />
        </Card>

        {/* 文档预览弹窗 */}
        <Modal
          title="文档预览"
          open={previewModalVisible}
          onCancel={() => setPreviewModalVisible(false)}
          footer={null}
          width="90%"
          style={{ top: 20 }}
          bodyStyle={{ height: 'calc(100vh - 200px)', padding: 0 }}
        >
          {previewConfig ? (
            <DocumentEditor
              id="docPreviewEditor"
              documentServerUrl={import.meta.env.VITE_ONLYOFFICE_URL || (import.meta.env.PROD ? '/onlyoffice' : 'http://localhost:8082')}
              config={{
                ...previewConfig.config,
                token: previewConfig.token
              }}
              height="100%"
              width="100%"
            />
          ) : previewUrl ? (
            <iframe
              src={`${import.meta.env.VITE_ONLYOFFICE_URL || (import.meta.env.PROD ? '/onlyoffice' : 'http://localhost:8082')}/web-apps/apps/api/documents?src=${encodeURIComponent(previewUrl)}`}
              style={{
                width: '100%',
                height: '100%',
                border: 'none',
              }}
              title="文档预览"
            />
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
              <Spin size="large" tip="加载预览..." />
            </div>
          )}
        </Modal>
      </div>
    </div>
  );
};

export default DocumentProcessingPage;
