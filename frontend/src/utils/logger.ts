// Logger utility to replace console.log statements
const isDevelopment = process.env.NODE_ENV === 'development';

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  level: LogLevel;
  message: string;
  data?: any;
  timestamp: Date;
}

class Logger {
  private shouldLog(level: LogLevel): boolean {
    // In production, only log errors and warnings
    if (!isDevelopment && !['error', 'warn'].includes(level)) {
      return false;
    }
    return true;
  }

  private formatLog(level: LogLevel, message: string, data?: any): LogEntry {
    return {
      level,
      message,
      data,
      timestamp: new Date()
    };
  }

  debug(message: string, data?: any): void {
    if (this.shouldLog('debug')) {
      const log = this.formatLog('debug', message, data);
      if (isDevelopment) {
        console.debug(`[DEBUG] ${message}`, data);
      }
    }
  }

  info(message: string, data?: any): void {
    if (this.shouldLog('info')) {
      const log = this.formatLog('info', message, data);
      if (isDevelopment) {
        console.info(`[INFO] ${message}`, data);
      }
    }
  }

  warn(message: string, data?: any): void {
    if (this.shouldLog('warn')) {
      const log = this.formatLog('warn', message, data);
      console.warn(`[WARN] ${message}`, data);
    }
  }

  error(message: string, error?: any): void {
    if (this.shouldLog('error')) {
      const log = this.formatLog('error', message, error);
      console.error(`[ERROR] ${message}`, error);
    }
  }

  // WebSocket specific logging
  websocket(message: string, data?: any): void {
    if (this.shouldLog('debug')) {
      this.debug(`[WebSocket] ${message}`, data);
    }
  }

  // API specific logging
  api(message: string, data?: any): void {
    if (this.shouldLog('debug')) {
      this.debug(`[API] ${message}`, data);
    }
  }

  // Task progress logging
  task(message: string, data?: any): void {
    if (this.shouldLog('info')) {
      this.info(`[Task] ${message}`, data);
    }
  }

  // OnlyOFFICE specific logging
  office(message: string, data?: any): void {
    if (this.shouldLog('info')) {
      this.info(`[Office] ${message}`, data);
    }
  }
}

const loggerInstance = new Logger();

export const logger = loggerInstance;
export const debug = (message: string, data?: any) => loggerInstance.debug(message, data);
export const info = (message: string, data?: any) => loggerInstance.info(message, data);
export const warn = (message: string, data?: any) => loggerInstance.warn(message, data);
export const error = (message: string, err?: any) => loggerInstance.error(message, err);
export const websocket = (message: string, data?: any) => loggerInstance.websocket(message, data);
export const api = (message: string, data?: any) => loggerInstance.api(message, data);
export const task = (message: string, data?: any) => loggerInstance.task(message, data);
export const office = (message: string, data?: any) => loggerInstance.office(message, data);