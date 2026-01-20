// frontend/src/components/DiagramViewer.tsx
import React, { useEffect, useRef, useState } from 'react';
import { Card, Alert, Spin, Button, Space, Typography, Tag } from 'antd';
import {
  DownloadOutlined,
  ReloadOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  FullscreenOutlined
} from '@ant-design/icons';

const { Text } = Typography;

// 图表格式
export type DiagramFormat = 'mermaid' | 'svg' | 'png' | 'dot';

// 图表类型
export type DiagramType =
  | 'equity_structure'
  | 'equity_penetration'
  | 'investment_flow'
  | 'risk_mindmap'
  | 'relationship_graph'
  | 'timeline';

interface DiagramViewerProps {
  diagramType?: DiagramType;
  sourceCode?: string;
  format: DiagramFormat;
  title?: string;
  renderedData?: string; // base64 编码的渲染数据（SVG/PNG）
  loading?: boolean;
  error?: string;
  onRetry?: () => void;
  onDownload?: () => void;
}

const DiagramViewer: React.FC<DiagramViewerProps> = ({
  diagramType,
  sourceCode,
  format,
  title,
  renderedData,
  loading = false,
  error,
  onRetry,
  onDownload
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [zoom, setZoom] = useState(1);
  const [mermaidLoaded, setMermaidLoaded] = useState(false);
  const [mermaidError, setMermaidError] = useState<string | null>(null);

  // 加载 Mermaid.js
  useEffect(() => {
    if (format === 'mermaid' && sourceCode && !mermaidLoaded) {
      loadMermaid();
    }
  }, [format, sourceCode]);

  const loadMermaid = async () => {
    try {
      // 动态加载 mermaid
      const mermaid = await import('mermaid');
      await mermaid.default.initialize({
        startOnLoad: true,
        theme: 'default',
        securityLevel: 'loose'
      });
      setMermaidLoaded(true);
      setMermaidError(null);

      // 渲染图表
      if (containerRef.current) {
        await mermaid.default.contentLoaded();
      }
    } catch (err) {
      console.error('Failed to load Mermaid:', err);
      setMermaidError('Mermaid 加载失败');
    }
  };

  // 处理缩放
  const handleZoomIn = () => {
    setZoom(prev => Math.min(prev + 0.1, 3));
  };

  const handleZoomOut = () => {
    setZoom(prev => Math.max(prev - 0.1, 0.3));
  };

  const handleResetZoom = () => {
    setZoom(1);
  };

  // 处理全屏
  const handleFullscreen = () => {
    if (containerRef.current) {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        containerRef.current.requestFullscreen();
      }
    }
  };

  // 获取图表类型标签
  const getDiagramTypeLabel = () => {
    const labels: Record<DiagramType, string> = {
      equity_structure: '股权结构图',
      equity_penetration: '股权穿透图',
      investment_flow: '投资流程图',
      risk_mindmap: '风险思维导图',
      relationship_graph: '关系图',
      timeline: '时间线'
    };
    return labels[diagramType || 'equity_structure'];
  };

  // 渲染 Mermaid 图表
  const renderMermaid = () => {
    if (mermaidError) {
      return (
        <Alert
          message="Mermaid 加载失败"
          description="请检查网络连接或稍后重试"
          type="error"
          showIcon
          action={
            onRetry && (
              <Button size="small" onClick={onRetry}>
                重试
              </Button>
            )
          }
        />
      );
    }

    return (
      <div
        ref={containerRef}
        className="mermaid"
        style={{
          transform: `scale(${zoom})`,
          transformOrigin: 'top left',
          transition: 'transform 0.3s',
          overflow: 'auto'
        }}
      >
        {sourceCode}
      </div>
    );
  };

  // 渲染 SVG
  const renderSVG = () => {
    if (renderedData) {
      return (
        <div
          dangerouslySetInnerHTML={{ __html: renderedData }}
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: 'top left',
            transition: 'transform 0.3s'
          }}
        />
      );
    }

    // 如果没有渲染数据，尝试直接渲染源代码（假设它是 SVG）
    if (sourceCode && sourceCode.startsWith('<svg')) {
      return (
        <div
          dangerouslySetInnerHTML={{ __html: sourceCode }}
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: 'top left',
            transition: 'transform 0.3s'
          }}
        />
      );
    }

    return <Alert message="无 SVG 数据" type="warning" />;
  };

  // 渲染 PNG
  const renderPNG = () => {
    if (renderedData) {
      return (
        <img
          src={`data:image/png;base64,${renderedData}`}
          alt="Diagram"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: 'top left',
            transition: 'transform 0.3s',
            maxWidth: '100%'
          }}
        />
      );
    }

    return <Alert message="无 PNG 数据" type="warning" />;
  };

  // 渲染 DOT 源代码
  const renderDOT = () => {
    return (
      <pre
        style={{
          background: '#f5f5f5',
          padding: 16,
          borderRadius: 4,
          overflow: 'auto',
          transform: `scale(${zoom})`,
          transformOrigin: 'top left',
          transition: 'transform 0.3s'
        }}
      >
        {sourceCode}
      </pre>
    );
  };

  // 渲染图表内容
  const renderContent = () => {
    if (loading) {
      return (
        <div style={{ textAlign: 'center', padding: 40 }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text type="secondary">正在生成图表...</Text>
          </div>
        </div>
      );
    }

    if (error) {
      return (
        <Alert
          message="图表生成失败"
          description={error}
          type="error"
          showIcon
          action={
            onRetry && (
              <Button size="small" icon={<ReloadOutlined />} onClick={onRetry}>
                重试
              </Button>
            )
          }
        />
      );
    }

    if (!sourceCode && !renderedData) {
      return <Alert message="暂无图表数据" type="info" />;
    }

    switch (format) {
      case 'mermaid':
        return renderMermaid();
      case 'svg':
        return renderSVG();
      case 'png':
        return renderPNG();
      case 'dot':
        return renderDOT();
      default:
        return <Alert message={`不支持的格式: ${format}`} type="error" />;
    }
  };

  return (
    <Card
      title={
        <Space>
          <Text strong>{title || getDiagramTypeLabel()}</Text>
          {diagramType && <Tag color="blue">{diagramType}</Tag>}
          <Tag>{format.toUpperCase()}</Tag>
        </Space>
      }
      extra={
        <Space>
          {format !== 'dot' && (
            <>
              <Button
                size="small"
                icon={<ZoomOutOutlined />}
                onClick={handleZoomOut}
                disabled={loading || !!error}
              >
                缩小
              </Button>
              <Button
                size="small"
                onClick={handleResetZoom}
                disabled={loading || !!error}
              >
                {Math.round(zoom * 100)}%
              </Button>
              <Button
                size="small"
                icon={<ZoomInOutlined />}
                onClick={handleZoomIn}
                disabled={loading || !!error}
              >
                放大
              </Button>
              <Button
                size="small"
                icon={<FullscreenOutlined />}
                onClick={handleFullscreen}
                disabled={loading || !!error}
              >
                全屏
              </Button>
            </>
          )}
          {onDownload && (
            <Button
              type="primary"
              size="small"
              icon={<DownloadOutlined />}
              onClick={onDownload}
              disabled={loading || !!error}
            >
              下载
            </Button>
          )}
        </Space>
      }
      bodyStyle={{
        overflow: 'auto',
        maxHeight: 600,
        minHeight: 300
      }}
    >
      {renderContent()}
    </Card>
  );
};

export default DiagramViewer;
