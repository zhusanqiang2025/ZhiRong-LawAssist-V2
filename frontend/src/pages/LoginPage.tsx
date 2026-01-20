import React, { useState } from 'react';
import { Form, Input, Button, Card, Tabs, message, Typography, theme, ConfigProvider } from 'antd';
import {
  UserOutlined,
  LockOutlined,
  SafetyCertificateOutlined,
  RocketOutlined,
  FileProtectOutlined,
  ArrowRightOutlined,
  MobileOutlined
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import api from '../api';

const { Title, Text, Paragraph } = Typography;
const { useToken } = theme;

// --- 组件：左侧科技感 SVG 插画 ---
// 这是一个抽象的"文档+神经网络+盾牌"的结合体
const AiLegalGraphic = () => (
  <svg viewBox="0 0 400 400" xmlns="http://www.w3.org/2000/svg" className="graphic-float">
    <defs>
      <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" style={{ stopColor: '#60a5fa', stopOpacity: 1 }} />
        <stop offset="100%" style={{ stopColor: '#3b82f6', stopOpacity: 0.6 }} />
      </linearGradient>
      <filter id="glow">
        <feGaussianBlur stdDeviation="4.5" result="coloredBlur"/>
        <feMerge>
          <feMergeNode in="coloredBlur"/>
          <feMergeNode in="SourceGraphic"/>
        </feMerge>
      </filter>
    </defs>
    {/* 背景网格 */}
    <g stroke="rgba(255,255,255,0.1)" strokeWidth="1">
      <line x1="50" y1="0" x2="50" y2="400" />
      <line x1="150" y1="0" x2="150" y2="400" />
      <line x1="250" y1="0" x2="250" y2="400" />
      <line x1="350" y1="0" x2="350" y2="400" />
      <line x1="0" y1="50" x2="400" y2="50" />
      <line x1="0" y1="150" x2="400" y2="150" />
      <line x1="0" y1="250" x2="400" y2="250" />
      <line x1="0" y1="350" x2="400" y2="350" />
    </g>
    
    {/* 核心图形：抽象盾牌/文件 */}
    <path 
      d="M200,80 L320,130 L320,220 C320,290 270,350 200,380 C130,350 80,290 80,220 L80,130 L200,80 Z" 
      fill="url(#grad1)" 
      opacity="0.1" 
    />
    <path 
      d="M200,90 L310,135 L310,220 C310,280 265,335 200,360 C135,335 90,280 90,220 L90,135 L200,90 Z" 
      fill="none" 
      stroke="#60a5fa" 
      strokeWidth="2"
      filter="url(#glow)"
    />

    {/* 动态节点连接线 */}
    <g stroke="#93c5fd" strokeWidth="1.5" opacity="0.8">
       <line x1="200" y1="150" x2="260" y2="200" />
       <line x1="200" y1="150" x2="140" y2="200" />
       <line x1="140" y1="200" x2="140" y2="280" />
       <line x1="260" y1="200" x2="260" y2="280" />
       <line x1="140" y1="280" x2="200" y2="320" />
       <line x1="260" y1="280" x2="200" y2="320" />
       <line x1="200" y1="150" x2="200" y2="240" />
    </g>

    {/* 节点圆点 */}
    <g fill="#fff">
      <circle cx="200" cy="150" r="4" />
      <circle cx="260" cy="200" r="3" />
      <circle cx="140" cy="200" r="3" />
      <circle cx="140" cy="280" r="3" />
      <circle cx="260" cy="280" r="3" />
      <circle cx="200" cy="320" r="4" />
      <circle cx="200" cy="240" r="5" fill="#60a5fa" filter="url(#glow)"/>
    </g>
  </svg>
);

// --- 组件：特性列表项 ---
const FeatureItem = ({ icon, title, text }: { icon: React.ReactNode, title: string, text: string }) => (
  <div style={{ display: 'flex', gap: '16px', marginBottom: '24px', alignItems: 'flex-start' }}>
    <div style={{ 
      background: 'rgba(255,255,255,0.1)', 
      padding: '10px', 
      borderRadius: '12px', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      backdropFilter: 'blur(10px)'
    }}>
      {React.cloneElement(icon as React.ReactElement, { style: { fontSize: '20px', color: '#93c5fd' } })}
    </div>
    <div>
      <Text strong style={{ color: '#fff', fontSize: '15px', display: 'block', marginBottom: '4px' }}>{title}</Text>
      <Text style={{ color: 'rgba(255,255,255,0.65)', fontSize: '13px', lineHeight: '1.4' }}>{text}</Text>
    </div>
  </div>
);

const LoginPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const auth = useAuth();
  const { token } = useToken();

  const handleRegister = async (values: any) => {
    setLoading(true);
    try {
      await api.registerUser({ email: values.email, password: values.password });
      message.success({ content: '注册成功！正在自动登录...', icon: <RocketOutlined /> });
      // 注册后直接尝试登录体验更好
      await auth.login(values.email, values.password);
      navigate('/');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '注册失败，请稍后重试。');
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = async (values: any) => {
    setLoading(true);
    try {
      await auth.login(values.email, values.password);
      message.success('欢迎回来，律师。');
      navigate('/');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '登录失败，请检查您的凭据。');
    } finally {
      setLoading(false);
    }
  };

  const renderForm = (isLogin: boolean) => (
    <Form
      layout="vertical"
      onFinish={isLogin ? handleLogin : handleRegister}
      size="large"
      style={{ marginTop: '20px' }}
    >
      <Form.Item
        name="email"
        label={<span style={{ color: '#64748b', fontSize: '13px' }}>工作邮箱</span>}
        rules={[{ required: true, type: 'email', message: '请输入有效的邮箱地址' }]}
      >
        <Input
          prefix={<UserOutlined style={{ color: '#94a3b8' }} />}
          placeholder="name@lawfirm.com"
          style={{ borderRadius: '8px', padding: '10px 16px' }}
        />
      </Form.Item>

      {/* 注册时显示手机号输入框 */}
      {!isLogin && (
        <Form.Item
          name="phone"
          label={<span style={{ color: '#64748b', fontSize: '13px' }}>手机号（可选）</span>}
          rules={[
            {
              pattern: /^(\+?\d{10,15})?$/,
              message: '请输入有效的手机号'
            }
          ]}
        >
          <Input
            prefix={<MobileOutlined style={{ color: '#94a3b8' }} />}
            placeholder="+86 13800000000"
            style={{ borderRadius: '8px', padding: '10px 16px' }}
          />
        </Form.Item>
      )}

      <Form.Item
        name="password"
        label={<span style={{ color: '#64748b', fontSize: '13px' }}>密码</span>}
        rules={[{ required: true, message: '请输入密码' }]}
      >
        <Input.Password
          prefix={<LockOutlined style={{ color: '#94a3b8' }} />}
          placeholder="••••••••"
          style={{ borderRadius: '8px', padding: '10px 16px' }}
        />
      </Form.Item>

      <Form.Item style={{ marginTop: '32px' }}>
        <Button
          type="primary"
          htmlType="submit"
          loading={loading}
          block
          style={{
            height: '48px',
            borderRadius: '8px',
            fontSize: '16px',
            fontWeight: 500,
            background: 'linear-gradient(90deg, #2563eb 0%, #1d4ed8 100%)',
            border: 'none',
            boxShadow: '0 4px 12px rgba(37, 99, 235, 0.2)'
          }}
        >
          {isLogin ? '登录工作台' : '创建新账户'} <ArrowRightOutlined style={{ fontSize: '12px' }} />
        </Button>
      </Form.Item>
    </Form>
  );

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#2563eb',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
        },
      }}
    >
      <div className="login-container" style={{
        display: 'flex',
        minHeight: '100vh',
        background: '#f8fafc', // 浅灰背景
        overflow: 'hidden'
      }}>
        {/* CSS 动画注入 */}
        <style>{`
          @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-15px); }
            100% { transform: translateY(0px); }
          }
          .graphic-float {
            animation: float 6s ease-in-out infinite;
          }
          @media (max-width: 768px) {
            .login-left-panel { display: none !important; }
            .login-right-panel { width: 100% !important; padding: 20px !important; }
          }
        `}</style>

        {/* 左侧：品牌与视觉冲击区 */}
        <div className="login-left-panel" style={{
          width: '45%',
          background: '#0f172a', // 深海蓝
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '60px 80px',
          overflow: 'hidden',
          color: '#fff'
        }}>
          {/* 背景装饰光 */}
          <div style={{
            position: 'absolute',
            top: '-20%',
            left: '-20%',
            width: '600px',
            height: '600px',
            background: 'radial-gradient(circle, rgba(37,99,235,0.2) 0%, rgba(15,23,42,0) 70%)',
            borderRadius: '50%',
          }} />

          <div style={{ position: 'relative', zIndex: 10 }}>
            {/* Logo 区 */}
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: '60px' }}>
              <div style={{ 
                width: '40px', height: '40px', 
                background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', 
                borderRadius: '8px', marginRight: '12px',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                <span style={{ fontWeight: 'bold', fontSize: '20px' }}>⚖️</span>
              </div>
              <Title level={3} style={{ color: '#fff', margin: 0, fontWeight: 600, letterSpacing: '0.5px' }}>
                智融法助 2.0
              </Title>
            </div>

            {/* Slogan */}
            <Title level={1} style={{ 
              color: '#fff', 
              fontSize: '48px', 
              lineHeight: '1.2', 
              marginBottom: '30px',
              fontWeight: 700 
            }}>
              智能驱动<br/>
              <span style={{ 
                background: 'linear-gradient(90deg, #60a5fa 0%, #a5b4fc 100%)', 
                WebkitBackgroundClip: 'text', 
                WebkitTextFillColor: 'transparent' 
              }}>
                法律未来
              </span>
            </Title>
            
            <Paragraph style={{ color: '#94a3b8', fontSize: '18px', marginBottom: '60px', maxWidth: '400px' }}>
              专为法律专业人士打造的 AI 协作平台。集成深度推理引擎，让风险无处遁形，文书一键生成。
            </Paragraph>

            {/* 功能特性列表 */}
            <div>
              <FeatureItem 
                icon={<RocketOutlined />} 
                title="深度咨询 & 案件分析" 
                text="基于全库案例检索，提供专家级诉讼策略建议。" 
              />
              <FeatureItem 
                icon={<SafetyCertificateOutlined />} 
                title="智能风险审查" 
                text="毫秒级识别合同漏洞，精准定位法律风险点。" 
              />
              <FeatureItem 
                icon={<FileProtectOutlined />} 
                title="自动化文书生成" 
                text="支持复杂逻辑的合同与法律函件一键起草。" 
              />
            </div>
          </div>

          {/* 右下角插图 */}
          <div style={{ position: 'absolute', right: '-80px', bottom: '-40px', width: '400px', opacity: 0.9 }}>
            <AiLegalGraphic />
          </div>
        </div>

        {/* 右侧：登录表单 */}
        <div className="login-right-panel" style={{
          width: '55%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          padding: '40px',
          background: '#ffffff'
        }}>
          <div style={{ width: '100%', maxWidth: '420px' }}>
            {/* 移动端 Logo (仅在左侧隐藏时显示) - 通过 CSS 控制显示逻辑这里省略，但在移动端布局下会很有用 */}
            <div style={{ marginBottom: '32px', textAlign: 'center' }}>
              <Title level={2} style={{ color: '#1e293b', marginBottom: '8px' }}>欢迎使用</Title>
              <Text style={{ color: '#64748b' }}>请输入您的凭据以访问工作台</Text>
            </div>

            <Card 
              bordered={false} 
              style={{ boxShadow: 'none' }}
              bodyStyle={{ padding: 0 }}
            >
              <Tabs
                defaultActiveKey="login"
                centered
                items={[
                  { key: 'login', label: '账户登录', children: renderForm(true) },
                  { key: 'register', label: '申请试用', children: renderForm(false) }
                ]}
                tabBarStyle={{ marginBottom: '24px' }}
              />
            </Card>

            {/* 底部版权 */}
            <div style={{ textAlign: 'center', marginTop: '40px' }}>
              <Text style={{ color: '#94a3b8', fontSize: '12px' }}>
                © 2024 Smart Legal Assistant Inc. <br/>
                Enterprise Grade Security · ISO 27001 Certified
              </Text>
            </div>
          </div>
        </div>
      </div>
    </ConfigProvider>
  );
};

export default LoginPage;