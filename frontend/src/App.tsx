// frontend/src/App.tsx (v3.1 - 性能优化：代码分割和懒加载)
import React, { lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { ErrorBoundary } from './components/ErrorBoundary';
import { SessionProvider } from './context/SessionContext';
import { Spin, App as AntdApp } from 'antd';

// ==================== 代码分割和懒加载 ====================
// 使用 React.lazy() 进行路由级别的代码分割
// 这样可以显著减少初始 bundle 大小，提升首屏加载速度

// 核心页面（保持同步加载，因为用户登录后会立即访问）
import LoginPage from './pages/LoginPage';
import SceneSelectionPage from './pages/SceneSelectionPage';

// 懒加载其他页面组件
const HomePage = lazy(() => import('./pages/HomePage'));
const ResultPage = lazy(() => import('./pages/ResultPage'));
const SmartChatPage = lazy(() => import('./pages/SmartChatPage'));
const IntelligentGuidancePage = lazy(() => import('./pages/IntelligentGuidancePage'));
const LegalConsultationPage = lazy(() => import('./pages/LegalConsultationPage'));
const ContractPage = lazy(() => import('./pages/ContractPage'));
const AdminPage = lazy(() => import('./pages/AdminPage'));
const TemplateEditPage = lazy(() => import('./pages/TemplateEditPage'));
const ContractReview = lazy(() => import('./pages/ContractReview'));
const ContractReviewHistory = lazy(() => import('./pages/ContractReviewHistory'));
const DocumentProcessingPage = lazy(() => import('./pages/DocumentProcessingPage'));
const ContractGenerationPage = lazy(() => import('./pages/ContractGenerationPage'));
const ContractPlanningPage = lazy(() => import('./pages/ContractPlanningPage'));
const CostCalculationPage = lazy(() => import('./pages/CostCalculationPage'));
// 移除旧版 RiskAnalysisPage 引用，解决 Build 错误
const RiskAnalysisPageV2 = lazy(() => import('./pages/RiskAnalysisPageV2'));
const LitigationAnalysisPage = lazy(() => import('./pages/LitigationAnalysisPage'));
const DocumentDraftingPage = lazy(() => import('./pages/DocumentDraftingPage'));
const UserKnowledgeBasePage = lazy(() => import('./pages/UserKnowledgeBasePage'));

// ==================== 加载占位符 ====================
// 统一的加载提示组件
const LoadingFallback = () => (
  <div style={{
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'center',
    alignItems: 'center',
    height: '100vh',
    background: '#f0f2f5'
  }}>
    <Spin size="large" tip="加载中..." />
    <div style={{ marginTop: 16, color: '#999', fontSize: 14 }}>
      正在加载页面，请稍候...
    </div>
  </div>
);

// ==================== 路由守卫 ====================
const PrivateRoute: React.FC<{ children: JSX.Element }> = ({ children }) => {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) {
    return <LoadingFallback />;
  }
  return isAuthenticated ? children : <Navigate to="/login" />;
};

const App: React.FC = () => {
  return (
    <SessionProvider>
      <ErrorBoundary>
        <AntdApp>
          <Router>
            <Suspense fallback={<LoadingFallback />}>
              <Routes>
            <Route path="/login" element={<LoginPage />} />

            {/* 首页 */}
            <Route
              path="/"
              element={
                <PrivateRoute>
                  <SceneSelectionPage />
                </PrivateRoute>
              }
            />

            {/* 智能引导 */}
            <Route
              path="/guidance"
              element={
                <PrivateRoute>
                  <IntelligentGuidancePage />
                </PrivateRoute>
              }
            />

            {/* 智能咨询 */}
            <Route
              path="/consultation"
              element={
                <PrivateRoute>
                  <LegalConsultationPage />
                </PrivateRoute>
              }
            />

            {/* 费用测算 */}
            <Route
              path="/cost-calculation"
              element={
                <PrivateRoute>
                  <CostCalculationPage />
                </PrivateRoute>
              }
            />

            {/* 风险分析 (直接指向 V2) */}
            <Route
              path="/risk-analysis"
              element={
                <PrivateRoute>
                  <RiskAnalysisPageV2 />
                </PrivateRoute>
              }
            />

            {/* 案件分析 */}
            <Route
              path="/litigation-analysis"
              element={
                <PrivateRoute>
                  <LitigationAnalysisPage />
                </PrivateRoute>
              }
            />

            {/* 文书起草 */}
            <Route
              path="/document-drafting"
              element={
                <PrivateRoute>
                  <DocumentDraftingPage />
                </PrivateRoute>
              }
            />

            {/* 兼容旧路由 - 智能对话重定向到智能引导 */}
            <Route
              path="/chat"
              element={
                <PrivateRoute>
                  <SmartChatPage />
                </PrivateRoute>
              }
            />

            {/* 模板查询页面 */}
            <Route
              path="/templates"
              element={
                <PrivateRoute>
                  <ContractPage />
                </PrivateRoute>
              }
            />

            {/* 兼容旧路由 */}
            <Route
              path="/scenes"
              element={
                <PrivateRoute>
                  <SceneSelectionPage />
                </PrivateRoute>
              }
            />

            {/* 合同中心 */}
            <Route
              path="/contract"
              element={
                <PrivateRoute>
                  <ContractPage />
                </PrivateRoute>
              }
            />

            {/* 模板编辑（仅管理员） */}
            <Route
              path="/contract/:templateId/edit"
              element={
                <PrivateRoute>
                  <TemplateEditPage />
                </PrivateRoute>
              }
            />

            {/* 智能合同审查 */}
            <Route
              path="/contract/review"
              element={
                <PrivateRoute>
                  <ContractReview />
                </PrivateRoute>
              }
            />

            {/* 合同审查任务历史 */}
            <Route
              path="/contract/review-history"
              element={
                <PrivateRoute>
                  <ContractReviewHistory />
                </PrivateRoute>
              }
            />

            {/* 文档处理中心 */}
            <Route
              path="/document-processing"
              element={
                <PrivateRoute>
                  <DocumentProcessingPage />
                </PrivateRoute>
              }
            />

            {/* 合同生成 */}
            <Route
              path="/contract/generate"
              element={
                <PrivateRoute>
                  <ContractGenerationPage />
                </PrivateRoute>
              }
            />

            {/* 合同生成 - 新路由（智能生成按钮使用） */}
            <Route
              path="/contract-generation"
              element={
                <PrivateRoute>
                  <ContractGenerationPage />
                </PrivateRoute>
              }
            />

            {/* 合同规划 */}
            <Route
              path="/contract/planning"
              element={
                <PrivateRoute>
                  <ContractPlanningPage />
                </PrivateRoute>
              }
            />

            {/* 分析/审查 (保留旧路由以防报错，均指向首页) */}
            <Route
              path="/analysis"
              element={
                <PrivateRoute>
                  <HomePage />
                </PrivateRoute>
              }
            />
            <Route
              path="/review"
              element={
                <PrivateRoute>
                  <HomePage />
                </PrivateRoute>
              }
            />

            {/* 任务结果 */}
            <Route
              path="/result/:taskId"
              element={
                <PrivateRoute>
                  <ResultPage />
                </PrivateRoute>
              }
            />

            {/* 管理后台 */}
            <Route
              path="/admin"
              element={
                <PrivateRoute>
                  <AdminPage />
                </PrivateRoute>
              }
            />

            {/* 用户知识库 */}
            <Route
              path="/knowledge-base"
              element={
                <PrivateRoute>
                  <UserKnowledgeBasePage />
                </PrivateRoute>
              }
            />

          </Routes>
          </Suspense>
      </Router>
    </AntdApp>
  </ErrorBoundary>
    </SessionProvider>
  );
};

export default App;