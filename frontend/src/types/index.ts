// Export type definitions explicitly to avoid conflicts
export type { 
  User, 
  AuthState, 
  LoginCredentials, 
  LoginResponse, 
  ApiErrorResponse 
} from './auth';
export * from './api';
export * from './contract';

// 导出 requests 中的类型，但排除与 auth 中重复的 LoginResponse
export type { 
  RegisterRequest, 
  LoginRequest, 
  TaskCreateRequest, 
  TaskModificationRequest, 
  FileGenerateRequest, 
  ChatMessage, 
  ChatRequest, 
  ChatResponse, 
  Template, 
  TemplateSearchRequest, 
  TemplateUploadRequest, 
  TemplateRatingRequest, 
  Category, 
  CategoryCreateRequest, 
  GuidanceRequest, 
  GuidanceResponse, 
  ConsultationRequest, 
  ConsultationResponse, 
  ContractReviewUploadResponse, 
  ContractReviewStartResponse,
  ContractGenerationAnalyzeRequest,
  ContractGenerationAnalyzeResponse,
  ContractGenerationResponse,
  GeneratedContract,
  TemplateInfo,
  DocumentProcessRequest,
  DocumentProcessResponse,
  ClarificationFormField,
  ClarificationFormSection,
  ClarificationFormSummary,
  ClarificationForm,
  ClarificationFormResponse,
  GenerateWithFormDataRequest,
  ContractGenerationCeleryResponse,
  ContractGenerationSyncResponse,
  ContractGenerationTaskResponse
} from './requests';