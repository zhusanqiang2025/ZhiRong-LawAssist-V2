import React from 'react';
import { Card } from 'antd';
import './LoadingPlaceholder.css';

const LoadingPlaceholder: React.FC = () => {
    return (
        <Card title="AI 正在为您生成文书..." className="display-card placeholder-card">
            <div className="placeholder-content">
                <div className="placeholder-line title-line"></div>
                <div className="placeholder-line"></div>
                <div className="placeholder-line short-line"></div>
                <div className="placeholder-line"></div>
                <div className="placeholder-line"></div>
                <div className="placeholder-line medium-line"></div>
            </div>
        </Card>
    );
};

export default LoadingPlaceholder;
