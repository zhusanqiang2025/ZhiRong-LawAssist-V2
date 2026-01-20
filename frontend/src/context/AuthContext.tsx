// frontend/src/context/AuthContext.tsx (最终决定版 v4.0 - 中央集权登录逻辑)
import React, { createContext, useContext, useState, useEffect } from 'react';
import api, { axiosInstance } from '../api';
import { User, LoginCredentials, AuthState } from '../types';
import { logger } from '../utils/logger';
import { resetSessionGlobal, clearSessionGlobal } from './SessionContext';

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const checkToken = async () => {
      const token = localStorage.getItem('accessToken');
      if (token) {
        axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        try {
          const response = await api.getCurrentUser();
          setUser(response.data);
          setIsAuthenticated(true);
        } catch (error) {
          logger.error("Token validation failed on app load", error);
          logout();
        }
      }
      setIsLoading(false);
    };
    checkToken();
  }, []);

  const login = async (email: string, password: string) => {
    // <<< 核心修正点 2: 整个登录流程在这里原子化地完成 >>>
    try {
      // 步骤 1: 获取 Token
      const response = await api.loginUser({ username: email, password: password });
      const token = response.data.access_token;

      // 步骤 2: 立即设置 Token
      localStorage.setItem('accessToken', token);
      axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;

      // 步骤 3: 成功设置 Token 后，获取用户信息
      const userResponse = await api.getCurrentUser();
      setUser(userResponse.data);
      setIsAuthenticated(true);

      // 步骤 4: 初始化会话时间（工作时长计时）
      resetSessionGlobal();

    } catch (error) {
      logger.error("Full login flow failed", error);
      logout(); // 任何一步失败，都执行完整的登出清理
      throw error; // 抛出错误，让 LoginPage 可以捕获并显示
    }
  };

  const logout = () => {
    localStorage.removeItem('accessToken');
    delete axiosInstance.defaults.headers.common['Authorization'];
    setUser(null);
    setIsAuthenticated(false);

    // 清除会话时间
    clearSessionGlobal();
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};