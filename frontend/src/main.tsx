// src/main.tsx (清洁版 v1.3 - 已集成AntD样式)
// 变更说明：
// 1. 新增导入 Ant Design 的全局CSS文件。
// 2. 添加 ErrorBoundary 来捕获整个应用中的错误。

import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';
import 'antd/dist/reset.css'; // <-- 核心修改：导入Ant Design的样式重置文件

import { AuthProvider } from './context/AuthContext';
import { ErrorBoundary } from './components/ErrorBoundary';

const container = document.getElementById('root');
if (!container) throw new Error('Failed to find the root element');

const root = createRoot(container);
root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <AuthProvider>
        <App />
      </AuthProvider>
    </ErrorBoundary>
  </React.StrictMode>
);