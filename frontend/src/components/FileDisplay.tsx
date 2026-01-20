import React, { useEffect, useRef } from 'react';
import { Card } from 'antd';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './FileDisplay.css';

interface FileDisplayProps {
    content: string;
}

const FileDisplay: React.FC<FileDisplayProps> = ({ content }) => {
    const bottomRef = useRef<null | HTMLDivElement>(null);

    useEffect(() => {
        if (bottomRef.current) {
            bottomRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [content]);

    return (
        <Card title="AI 生成文书初稿" className="display-card">
            {/* ▼▼▼▼▼ [修正] 将 markdown-body 类名应用在正确的容器上 ▼▼▼▼▼ */}
            <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                <div ref={bottomRef} />
            </div>
        </Card>
    );
};

export default FileDisplay;