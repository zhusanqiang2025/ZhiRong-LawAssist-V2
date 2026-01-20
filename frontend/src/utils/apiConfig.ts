// 统一的 API baseURL 配置
// 逻辑：生产环境使用相对路径，开发环境回退到 localhost

/**
 * 获取 API 基础 URL
 * - 优先使用环境变量 VITE_API_BASE_URL
 * - 生产环境无环境变量时返回空字符串（相对路径）
 * - 开发环境回退到 localhost:8000
 */
export const getApiBaseUrl = (): string => {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  // 生产环境：空字符串（相对路径，自动适配当前域名）
  if (import.meta.env.PROD) {
    return '';
  }
  // 开发环境：localhost
  return 'http://localhost:8000';
};

/**
 * 获取 WebSocket 基础 URL
 * - 生产环境使用当前域名的 ws/wss 协议
 * - 开发环境使用 localhost:8000
 */
export const getWsBaseUrl = (): string => {
  const apiBase = getApiBaseUrl();
  if (!apiBase) {
    // 生产环境：使用当前域名
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}`;
  }
  // 开发环境或显式配置：转换协议
  const wsProtocol = apiBase.startsWith('https') ? 'wss:' : 'ws:';
  return apiBase.replace(/^https?:/, wsProtocol);
};
