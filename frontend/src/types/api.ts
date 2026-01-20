// API response type definitions
export interface ApiResponse<T = any> {
  data: T;
  success: boolean;
  message?: string;
  status_code?: number;
}

export interface PaginatedResponse<T = any> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface Task {
  id: number;
  user_id: number;
  type: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  input_data: Record<string, any>;
  output_data?: Record<string, any>;
  error_message?: string;
  created_at: string;
  updated_at: string;
  started_at?: string;
  completed_at?: string;
}

export interface Scene {
  id: string;
  name: string;
  description: string;
  icon: string;
  path: string;
  category?: string;
  order?: number;
}