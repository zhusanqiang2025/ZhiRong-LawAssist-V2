// frontend/src/pages/SmartChatPage.tsx
import React, { useState, useEffect, useRef } from 'react';
import { Button, Input, Layout, message, Typography, Card, Space, Badge } from 'antd';
import { SendOutlined, RobotOutlined, UserOutlined, MenuOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../api';
import { logger } from '../utils/logger';
import './SmartChatPage.css';

const { Header, Content } = Layout;
const { TextArea } = Input;
const { Title, Text } = Typography;

interface ActionButton {
  id?: string;
  title?: string;
  text?: string; // API response format
  type?: 'template_query' | 'contract_generation' | 'legal_analysis' | 'case_analysis' | 'contract_review' | 'document_drafting' | 'legal_research';
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
}

const SmartChatPage: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showQuickActions, setShowQuickActions] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { logout } = useAuth();

  // 快捷操作
  const quickActions: QuickAction[] = [
    {
      id: 'contract-generation',
      title: '合同生成',
      icon: <RobotOutlined />,
      category: 'contract',
      route: '/contract',
      hasBackend: true
    },
    {
      id: 'legal-analysis',
      title: '法律分析',
      icon: <RobotOutlined />,
      category: 'legal-consultation',
      route: '/analysis',
      hasBackend: true
    },
    {
      id: 'contract-review',
      title: '合同审查',
      icon: <RobotOutlined />,
      category: 'contract',
      route: '/review',
      hasBackend: false
    },
    {
      id: 'case-analysis',
      title: '案件分析',
      icon: <RobotOutlined />,
      category: 'case',
      route: '/case-analysis',
      hasBackend: false
    }
  ];

  // 常见建议
  const commonSuggestions = [
    '帮我起草一份劳动合同',
    '分析这份合同的风险点',
    '生成一份租赁合同模板',
    '帮我审查这份保密协议',
    '起草一份律师函',
    '计算诉讼费用',
    '查询相关法律规定',
    '分析案件胜诉可能性'
  ];

  useEffect(() => {
    // 自动滚动到消息底部
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // 添加欢迎消息
    if (messages.length === 0) {
      const welcomeMessage: Message = {
        id: 'welcome',
        content: '您好！我是智融法助2.0，您的多模型融合智能法律助手。请告诉我您遇到的法律问题或需求，我会通过对话方式帮助您明确具体需求，并推荐最合适的处理方案。',
        role: 'assistant',
        timestamp: new Date(),
        suggestions: commonSuggestions
      };
      setMessages([welcomeMessage]);
    }
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSend = async () => {
    if (!inputValue.trim()) {
      message.warning('请输入您的问题或需求');
      return;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue.trim(),
      role: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsTyping(true);
    setShowQuickActions(false);

    try {
      // 转换对话历史格式（排除欢迎消息）
      const conversationHistory = messages
        .filter(msg => msg.id !== 'welcome')
        .map(msg => ({
          role: msg.role,
          content: msg.content,
          timestamp: msg.timestamp.toISOString()
        }));

      // 调用真实的Deepseek API
      const response = await api.smartChat(userMessage.content, conversationHistory);
      const responseData = response.data;

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        content: responseData.response,
        role: 'assistant',
        timestamp: new Date(),
        suggestions: responseData.suggestions || [],
        actionButtons: responseData.action_buttons || []
      };

      setMessages(prev => [...prev, assistantMessage]);
      setSuggestions(responseData.suggestions || []);
      setIsTyping(false);

      // 记录交互日志
      logger.debug('AI对话完成', {
        userInput: userMessage.content.substring(0, 50),
        aiResponseLength: responseData.response.length,
        confidence: responseData.confidence
      });

    } catch (error: any) {
      logger.error('AI对话失败:', error);

      // 根据错误类型显示不同的错误消息
      let errorMessage = '抱歉，AI助手暂时无法处理您的请求。请稍后再试。';

      if (error.response?.status === 401) {
        errorMessage = '您的登录已过期，请重新登录。';
      } else if (error.response?.status === 500) {
        errorMessage = 'AI服务暂时不可用，请稍后再试。';
      } else if (error.code === 'ECONNABORTED') {
        errorMessage = '请求超时，请检查网络连接后重试。';
      }

      const errorResponse: Message = {
        id: (Date.now() + 1).toString(),
        content: errorMessage,
        role: 'assistant',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, errorResponse]);
      setIsTyping(false);

      // 显示错误提示
      if (error.response?.status !== 401) {
        message.error('AI对话服务暂时不可用，请稍后重试');
      }
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    setInputValue(suggestion);
    // 自动发送
    setTimeout(() => {
      handleSend();
    }, 100);
  };

  const handleQuickAction = (action: QuickAction) => {
    if (action.hasBackend) {
      navigate(action.route);
    } else {
      message.info('该功能正在开发中，敬请期待！');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleActionButtonClick = (button: ActionButton) => {
    if (button.route) {
      // 导航到相应页面，可以携带参数
      if (button.params) {
        // 将参数编码到URL中或者通过状态管理传递
        navigate(button.route, { state: button.params });
      } else {
        navigate(button.route);
      }
    } else {
      message.info('该功能正在开发中，敬请期待！');
    }
  };

  const renderMessage = (message: Message) => (
    <div
      key={message.id}
      className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}
    >
      <div className="message-avatar">
        {message.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
      </div>
      <div className="message-content">
        <div className="message-text">{message.content}</div>
        <div className="message-time">
          {message.timestamp.toLocaleTimeString()}
        </div>

        {/* 功能按钮 - 优先显示 */}
        {message.actionButtons && message.actionButtons.length > 0 && (
          <div className="message-action-buttons" style={{ marginTop: '12px' }}>
            <Text type="secondary" style={{ fontSize: '12px', marginBottom: '8px', display: 'block' }}>
              推荐操作：
            </Text>
            <Space wrap>
              {message.actionButtons.map((button, index) => (
                <Button
                  key={index}
                  type="primary"
                  size="small"
                  icon={<span style={{ marginRight: '4px' }}>{button.icon || '🔗'}</span>}
                  onClick={() => handleActionButtonClick(button)}
                  style={{
                    borderRadius: '6px',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                  }}
                  title={button.description}
                >
                  {button.title}
                </Button>
              ))}
            </Space>
          </div>
        )}

        {/* 建议按钮 */}
        {message.suggestions && message.suggestions.length > 0 && (
          <div className="message-suggestions" style={{ marginTop: '12px' }}>
            <Text type="secondary" style={{ fontSize: '12px', marginBottom: '8px', display: 'block' }}>
              或者您可以这样说：
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
  );

  return (
    <Layout className="smart-chat-layout">
      <Header className="chat-header">
        <div className="header-left">
          <Button
            type="text"
            icon={<MenuOutlined />}
            onClick={() => navigate('/scenes')}
            className="back-btn"
          >
            返回
          </Button>
          <Title level={4} className="header-title">智能对话</Title>
        </div>
        <div className="header-right">
          <Badge count={messages.length - 1} offset={[-10, 0]}>
            <Button type="text" icon={<UserOutlined />} onClick={logout}>
              退出
            </Button>
          </Badge>
        </div>
      </Header>

      <Content className="chat-content">
        <div className="chat-messages" ref={messagesEndRef}>
          {messages.map(renderMessage)}

          {isTyping && (
            <div className="typing-indicator">
              <div className="typing-avatar">
                <RobotOutlined />
              </div>
              <div className="typing-content">
                <span>AI助手正在思考...</span>
                <div className="typing-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
        </div>

        {showQuickActions && (
          <div className="quick-actions">
            <Card title="快捷服务" size="small" className="quick-actions-card">
              <Space wrap>
                {quickActions.map(action => (
                  <Button
                    key={action.id}
                    icon={action.icon}
                    onClick={() => handleQuickAction(action)}
                    className="quick-action-btn"
                    type={action.hasBackend ? 'primary' : 'default'}
                  >
                    {action.title}
                    {!action.hasBackend && (
                      <span className="coming-soon">开发中</span>
                    )}
                  </Button>
                ))}
              </Space>
            </Card>
          </div>
        )}

        <div className="chat-input">
          <div className="input-container">
            <TextArea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="请描述您的法律问题或需求..."
              rows={1}
              autoSize={{ minRows: 1, maxRows: 4 }}
              className="message-input"
            />
            <Button
              type="primary"
              icon={<SendOutlined />}
              onClick={handleSend}
              disabled={!inputValue.trim() || isTyping}
              className="send-button"
            >
              发送
            </Button>
          </div>

          {suggestions.length > 0 && (
            <div className="suggestions-container">
              <Space wrap>
                <Text type="secondary" className="suggestions-label">建议：</Text>
                {suggestions.map((suggestion, index) => (
                  <Button
                    key={index}
                    size="small"
                    type="link"
                    onClick={() => handleSuggestionClick(suggestion)}
                  >
                    {suggestion}
                  </Button>
                ))}
              </Space>
            </div>
          )}
        </div>
      </Content>
    </Layout>
  );
};

export default SmartChatPage;