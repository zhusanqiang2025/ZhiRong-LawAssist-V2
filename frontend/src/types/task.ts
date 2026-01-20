// frontend/src/types/task.ts
/**
 * 任务相关类型定义
 */

export interface TaskProgress {
  taskId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0-100
  currentNode: string;
  nodeProgress: Record<string, NodeProgressInfo>;
  workflowSteps: WorkflowStep[];
  estimatedTimeRemaining?: number; // 秒
  errorMessage?: string;
  timestamp: string;
  result?: any; // Add result property
}

export interface NodeProgressInfo {
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0-100
  message?: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  result?: any;
}

export interface WorkflowStep {
  name: string;
  order: number;
  estimatedTime: number; // 秒
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: number; // 0-100
  startedAt?: string;
  completedAt?: string;
  error?: string;
  result?: any;
}

export interface Task {
  id: string;
  userDemand?: string;
  user_demand?: string; // Alias for userDemand
  analysisReport?: string;
  analysis_report?: string; // Alias for analysisReport
  finalDocument?: string;
  final_document?: string; // Alias for finalDocument
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancelled'; // Add 'cancelled'
  docType?: string;
  doc_type?: string; // Alias for docType
  result?: string;
  createdAt?: string;
  updatedAt?: string;
  startedAt?: string;
  completedAt?: string;
  progress?: number;
  currentNode?: string;
  nodeProgress?: Record<string, NodeProgressInfo>;
  workflowSteps?: WorkflowStep[];
  estimatedTimeRemaining?: number;
  errorMessage?: string;
  retryCount?: number;
  workflowRunId?: string;
  priority?: number;
  ownerId?: number;
  owner_id?: number; // Alias for ownerId
  conversationId?: string;
  [key: string]: any; // Allow additional properties
}

export interface TaskCreateRequest {
  userDemand: string;
  docType: 'contract' | 'letter' | 'analysis' | 'other';
  files?: File[];
}

export interface TaskCreateResponse {
  success: boolean;
  data: {
    taskId: string;
    status: string;
    message: string;
  };
}

export interface TaskStatusResponse {
  success: boolean;
  data: Task;
}

export interface TaskListResponse {
  success: boolean;
  data: {
    tasks: Task[];
    pagination: {
      total: number;
      page: number;
      pageSize: number;
      totalPages: number;
      hasNext: boolean;
      hasPrev: boolean;
    };
  };
}

// WebSocket 消息类型
export type WebSocketMessageType =
  | 'task_status'
  | 'task_progress'
  | 'task_completed'
  | 'task_error'
  | 'ping'
  | 'pong'
  | 'get_status'
  | 'error';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  data?: any;
  message?: string;
  timestamp: string;
}

// 进度可视化组件 Props
export interface ProgressTimelineProps {
  task: Task;
  className?: string;
  showTimeEstimates?: boolean;
  compact?: boolean;
}

export interface NodeProgressProps {
  node: WorkflowStep;
  isActive?: boolean;
  isCompleted?: boolean;
  hasError?: boolean;
  className?: string;
}

export interface OverallProgressProps {
  progress: number;
  status: Task['status'];
  currentNode?: string;
  estimatedTimeRemaining?: number;
  className?: string;
  showPercentage?: boolean;
  showStatus?: boolean;
}

// 文档类型配置
export interface DocumentTypeConfig {
  value: 'contract' | 'letter' | 'analysis' | 'other';
  label: string;
  description: string;
  icon?: string;
  steps: string[];
}