// frontend/src/context/SessionContext.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';

interface SessionContextType {
  sessionStartTime: number | null;
  resetSession: () => void;
  clearSession: () => void;
}

const SessionContext = createContext<SessionContextType | undefined>(undefined);

// 导出非hook的会话管理函数，用于在AuthContext中使用
let globalResetSession: (() => void) | null = null;
let globalClearSession: (() => void) | null = null;

export const resetSessionGlobal = () => {
  if (globalResetSession) globalResetSession();
};

export const clearSessionGlobal = () => {
  if (globalClearSession) globalClearSession();
};

export const SessionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sessionStartTime, setSessionStartTime] = useState<number | null>(null);

  useEffect(() => {
    // 从localStorage读取会话开始时间
    const stored = localStorage.getItem('legal_assistant_session_start');
    if (stored) {
      setSessionStartTime(parseInt(stored));
    }
  }, []);

  const resetSession = () => {
    const now = Date.now();
    localStorage.setItem('legal_assistant_session_start', now.toString());
    setSessionStartTime(now);
  };

  const clearSession = () => {
    localStorage.removeItem('legal_assistant_session_start');
    setSessionStartTime(null);
  };

  // 将函数赋值给全局变量
  useEffect(() => {
    globalResetSession = resetSession;
    globalClearSession = clearSession;

    return () => {
      globalResetSession = null;
      globalClearSession = null;
    };
  }, [resetSession, clearSession]);

  return (
    <SessionContext.Provider value={{ sessionStartTime, resetSession, clearSession }}>
      {children}
    </SessionContext.Provider>
  );
};

export const useSession = () => {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error('useSession must be used within SessionProvider');
  }
  return context;
};
