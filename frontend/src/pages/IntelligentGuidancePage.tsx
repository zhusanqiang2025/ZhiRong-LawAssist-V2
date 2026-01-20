// frontend/src/pages/IntelligentGuidancePage.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Button, Input, Layout, message, Typography, Card, Space, Steps, Progress, Modal } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, CompassOutlined, MessageOutlined, FileSearchOutlined, FileProtectOutlined, ReloadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import EnhancedModuleNavBar from '../components/ModuleNavBar/EnhancedModuleNavBar';
import { useSessionPersistence } from '../hooks/useSessionPersistence';
import './IntelligentGuidancePage.css';

const { Content } = Layout;
const { TextArea } = Input;
const { Text } = Typography;
const { Step } = Steps;

interface ActionButton {
  id?: string;
  title?: string;
  text?: string; // API response format
  type?: 'template_query' | 'contract_generation' | 'legal_analysis' | 'case_analysis' | 'contract_review' | 'document_drafting' | 'legal_research' | 'workflow_action';
  action?: string; // API response format
  route?: string;
  params?: Record<string, any>;
  icon?: string;
  description?: string;
}

interface Message {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
  suggestions?: string[];
  actionButtons?: ActionButton[];
}

interface QuickAction {
  id: string;
  title: string;
  icon: React.ReactNode;
  category: string;
  route: string;
  hasBackend?: boolean;
  description?: string;
}

// ========== 会话持久化 ==========
// 定义会话数据类型
interface GuidanceSessionData {
  currentStep: number;
  guidanceProgress: number;
  messages: Message[];
  showQuickActions: boolean;
  userInputHistory: string[]; // 用户输入历史
}

const IntelligentGuidancePage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showQuickActions, setShowQuickActions] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [guidanceProgress, setGuidanceProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState(0);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // 会话持久化配置
  const {
    hasSession,
    saveSession,
    clearSession,
    restoreSession,
    isLoading: isRestoringSession
  } = useSessionPersistence<GuidanceSessionData>('intelligent_guidance_session', {
    expirationTime: 60 * 60 * 1000, // 1小时过期
    autoRestore: false, // 不自动恢复，需要用户确认
    onRestore: (sessionId, data) => {
      console.log('[智能引导] 恢复会话:', sessionId, data);
      setCurrentStep(data.currentStep);
      setGuidanceProgress(data.guidanceProgress);
      setMessages(data.messages);
      setShowQuickActions(data.showQuickActions);
      message.success('已恢复之前的智能引导会话');
    }
  });

  // 智能引导专用快捷操作（选项A：功能类别平衡）
  const quickActions: QuickAction[] = [
    {
      id: 'consultation',
      title: '智能咨询',
      icon: <MessageOutlined />,
      category: 'consultation',
      route: '/consultation',
      hasBackend: true,
      description: '资深律师专业法律咨询服务'
    },
    {
      id: 'risk-analysis',
      title: '风险评估',
      icon: <FileSearchOutlined />,
      category: 'analysis',
      route: '/risk-analysis',
      hasBackend: true,
      description: '深度分析法律文件，识别潜在风险点'
    },
    {
      id: 'contract-generation',
      title: '合同生成',
      icon: <FileProtectOutlined />,
      category: 'contract',
      route: '/contract/generate',
      hasBackend: true,
      description: '基于需求智能生成各类合同文书'
    },
    {
      id: 'case-analysis',
      title: '案件分析',
      icon: <FileSearchOutlined />,
      category: 'case',
      route: '/litigation-analysis',
      hasBackend: true,
      description: '分析案件材料，制定诉讼策略'
    }
  ];

  // 智能引导专用建议（覆盖所有9个模块）
  const guidanceSuggestions = [
    '我需要法律咨询服务',
    '帮我分析这份合同的风险',
    '分析一下这个案件的胜诉可能性',
    '我需要生成一份技术服务合同',
    '帮我审查这份租赁合同',
    '查找劳动合同模板',
    '处理这个PDF文档',
    '帮我起草一份律师函',
    '计算诉讼费用大概多少钱'
  ];

  // 引导步骤配置
  const guidanceSteps = [
    {
      title: '需求探索',
      description: '了解您的具体需求'
    },
    {
      title: '场景识别',
      description: '确定适用的法律场景'
    },
    {
      title: '方案推荐',
      description: '推荐最适合的解决方案'
    },
    {
      title: '行动引导',
      description: '引导您开始使用'
    }
  ];

  useEffect(() => {
    // 添加欢迎消息
    const welcomeMessage: Message = {
      id: 'welcome',
      content: `您好！我是您的智能法律引导助手 👋

🎯 **我可以帮您做什么？**
• 通过对话快速了解您的法律需求
• 推荐最适合的法律工作流
• 提供直达功能页面的便捷通道

🔧 **支持的法律服务：**
1. **智能咨询** - 资深律师提供专业法律建议
2. **风险评估** - 深度分析法律文件,识别潜在风险
3. **合同生成** - 智能起草各类合同文书
4. **案件分析** - 分析案件材料,制定诉讼策略

💡 **使用方法：**
请告诉我您需要什么帮助,或者直接点击下方的快速开始按钮。

示例：
• "我需要法律咨询服务"
• "帮我分析这份合同的风险"
• "我需要生成一份技术服务合同"`,
      role: 'assistant',
      timestamp: new Date(),
      suggestions: guidanceSuggestions.slice(0, 4)
    };
    setMessages([welcomeMessage]);
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // 根据对话进展更新引导进度
    if (messages.length > 1) {
      const userMessages = messages.filter(m => m.role === 'user').length;
      setCurrentStep(Math.min(userMessages, 3));
      setGuidanceProgress(Math.min(userMessages * 25, 100));
    }
  }, [messages]);

  // 自动保存会话状态
  useEffect(() => {
    if (messages.length > 1) {
      // 只在有实际对话内容时保存
      saveSession(Date.now().toString(), {
        currentStep,
        guidanceProgress,
        messages,
        showQuickActions,
        userInputHistory: messages.filter(m => m.role === 'user').map(m => m.content)
      });
    }
  }, [currentStep, guidanceProgress, messages, showQuickActions, saveSession]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      content: inputValue,
      role: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setShowQuickActions(false);
    setIsTyping(true);

    try {
      const response = await api.intelligentGuidance({
        message: inputValue,
        conversation_history: messages.map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      });

      const assistantMessage: Message = {
        id: `assistant-${Date.now()}`,
        content: response.data.response,
        role: 'assistant',
        timestamp: new Date(),
        suggestions: response.data.suggestions,
        actionButtons: response.data.action_buttons
      };

      setMessages(prev => [...prev, assistantMessage]);
      setSuggestions(response.data.suggestions);

    } catch (error) {
      console.error('发送消息失败:', error);
      message.error('发送消息失败，请重试');

      const errorMessage: Message = {
        id: `error-${Date.now()}`,
        content: '抱歉，我现在无法处理您的请求。请稍后再试或尝试重新表述您的问题。',
        role: 'assistant',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleQuickAction = (action: QuickAction) => {
    // 根据动作类型处理
    if (action.hasBackend) {
      // 如果有后端支持，发送引导消息
      const guidanceMessage = `我想${action.title.toLowerCase()}`;
      setInputValue(guidanceMessage);
      setShowQuickActions(false);
    } else {
      // 直接跳转页面
      navigate(action.route);
      message.info(`${action.title}功能正在开发中`);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputValue(suggestion);
    setShowQuickActions(false);
  };

  const handleActionButtonClick = (button: ActionButton) => {
    if (button.route) {
      navigate(button.route, { state: button.params });
    } else {
      message.info('该功能正在开发中，敬请期待！');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <Layout className="intelligent-guidance-layout">
      <EnhancedModuleNavBar
        currentModuleKey="guidance"
        title="智能引导"
        icon={<CompassOutlined />}
      />

      <Content className="guidance-content">
        <div className="guidance-container">
          {/* 会话恢复提示 */}
          {hasSession && (
            <Card
              className="session-restore-card"
              size="small"
              style={{
                marginBottom: '16px',
                backgroundColor: '#e6f7ff',
                borderColor: '#91d5ff'
              }}
            >
              <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>
                检测到之前的会话
              </div>
              <div style={{ fontSize: '14px', color: '#666', marginBottom: '12px' }}>
                系统检测到您之前有一个未完成的智能引导会话。您可以继续之前的对话，或者重新开始。
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <Button
                  type="primary"
                  icon={<CompassOutlined />}
                  onClick={() => {
                    clearSession();
                    message.info('已清除之前的会话，重新开始');
                  }}
                >
                  重新开始
                </Button>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => {
                    restoreSession();
                  }}
                >
                  继续之前会话
                </Button>
              </div>
            </Card>
          )}

          {/* 引导进度 */}
          <Card className="progress-card" size="small">
            <Steps current={currentStep} size="small" items={guidanceSteps} />
            <Progress
              percent={guidanceProgress}
              size="small"
              style={{ marginTop: 12 }}
              strokeColor={{
                '0%': '#108ee9',
                '100%': '#52c41a',
              }}
            />
          </Card>

          {/* 消息列表 */}
          <div className="messages-container">
            {messages.map((message) => (
              <div key={message.id} className={`message ${message.role}`}>
                <div className="message-avatar">
                  {message.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
                </div>
                <div className="message-content">
                  <div className="message-bubble">
                    <Text style={{ whiteSpace: 'pre-wrap' }}>{message.content}</Text>
                  </div>

                  {/* 显示操作按钮 */}
                  {message.actionButtons && message.actionButtons.length > 0 && (
                    <div className="message-action-buttons">
                      <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>
                        推荐操作：
                      </Text>
                      <Space wrap>
                        {message.actionButtons.map((button, index) => (
                          <Button
                            key={index}
                            type="primary"
                            size="small"
                            onClick={() => handleActionButtonClick(button)}
                            title={button.description}
                          >
                            {button.title}
                          </Button>
                        ))}
                      </Space>
                    </div>
                  )}

                  {/* 显示建议 */}
                  {message.suggestions && message.suggestions.length > 0 && (
                    <div className="message-suggestions">
                      <Text type="secondary" style={{ marginBottom: 8, display: 'block' }}>
                        您可能想问：
                      </Text>
                      <Space wrap>
                        {message.suggestions.map((suggestion, index) => (
                          <Button
                            key={index}
                            size="small"
                            type="dashed"
                            onClick={() => handleSuggestionClick(suggestion)}
                          >
                            {suggestion}
                          </Button>
                        ))}
                      </Space>
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* 输入状态提示 */}
            {isTyping && (
              <div className="message assistant">
                <div className="message-avatar">
                  <RobotOutlined />
                </div>
                <div className="message-content">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* 输入区域 */}
          <div className="input-area">
            <div className="input-container">
              <TextArea
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="请描述您需要什么帮助，例如：我需要一份技术服务合同..."
                autoSize={{ minRows: 2, maxRows: 6 }}
                className="message-input"
              />
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSendMessage}
                loading={isTyping}
                disabled={!inputValue.trim()}
                className="send-button"
              >
                发送
              </Button>
            </div>
          </div>

          {/* 快速操作 */}
          {showQuickActions && (
            <Card className="quick-actions-card" title="快速开始" style={{ marginTop: '16px' }}>
              <div className="quick-actions-horizontal">
                {quickActions.map((action) => (
                  <Button
                    key={action.id}
                    size="large"
                    className="quick-action-button-horizontal"
                    onClick={() => handleQuickAction(action)}
                  >
                    {action.icon}
                    {action.title}
                  </Button>
                ))}
              </div>
            </Card>
          )}
        </div>
      </Content>
    </Layout>
  );
};

export default IntelligentGuidancePage;