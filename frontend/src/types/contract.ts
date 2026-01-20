// frontend/src/types/contract.ts

// ==================== 合同分类 (Category) ====================

export interface CategoryTreeItem {
  id: number;
  name: string;
  code?: string;
  description?: string;
  parent_id?: number | null;
  sort_order: number;
  is_active: boolean;
  template_count: number; // 核心：该分类下的模板数量
  children: CategoryTreeItem[];
  level?: number; // 添加层级属性，用于前端展示
  meta_info?: {
    contract_type?: string;
    industry?: string;
    usage_scene?: string;
    jurisdiction?: string;
    [key: string]: any;
  };
}

// ==================== 合同模板 (Contract Template) ====================

// 合同法律特征（知识图谱7个字段）
export interface ContractLegalFeatures {
  transaction_nature?: string;        // 交易性质
  contract_object?: string;           // 合同标的
  consideration_type?: string;        // 对价类型：有偿/无偿/混合
  consideration_detail?: string;      // 对价具体说明
  transaction_characteristics?: string; // 交易特征
  usage_scenario?: string;            // 适用场景
  legal_basis?: string[];             // 法律依据
}

export interface ContractTemplate {
  id: string;
  name: string;

  // 模板变体字段
  version_type?: string;              // 版本类型：标准版/简化版/详细版
  stance_tendency?: string;           // 立场倾向：甲方/乙方/中立
  detailed_usage_scenario?: string;   // 详细使用场景说明

  category: string;
  subcategory?: string;
  description?: string;

  // 文件信息
  file_url: string;
  file_name: string;
  file_size: number;
  file_type: string;

  // 权限与状态
  is_public: boolean;
  owner_id?: number;
  download_count: number;
  rating: number;
  status: string;
  is_featured: boolean;

  // 搜索与标签
  keywords?: string[];
  tags?: string[];

  // V1 结构锚点 (兼容旧逻辑)
  primary_contract_type?: string;
  secondary_types?: string[];
  delivery_model?: string;
  payment_model?: string;
  industry_tags?: string[];
  allowed_party_models?: string[];
  risk_level?: string;
  is_recommended?: boolean;

  // 知识图谱法律特征字段（7个核心字段）
  transaction_nature?: string;
  contract_object?: string;

  // V2+ 扩展法律特征
  transaction_consideration?: string;  // 交易对价（旧字段，兼容保留）
  transaction_characteristics?: string;  // 交易特征
  usage_scenario?: string;  // 使用场景说明

  // 扩展元数据 (包含源文件路径、知识图谱关联、提取的结构等)
  metadata_info?: {
    source_file_url?: string;
    source_file_type?: string;
    original_filename?: string;
    converted?: boolean;
    knowledge_graph_match?: {
      contract_type?: string;
      match_method?: string;
      match_score?: number;
      legal_features?: ContractLegalFeatures;
    };
    extracted_structure?: {
      sections?: Array<{ level: number; title: string }>;
      clauses?: Record<string, boolean>;
      key_terms?: Record<string, string[]>;
      structure_summary?: string;
    };
    [key: string]: any;
  };

  created_at: string;
  updated_at?: string;
}

// 模板信息（简化版，用于列表展示）
export interface TemplateInfo {
  id: string;
  name: string;
  category: string;
  subcategory?: string;
  description?: string;
  file_type: string;
  is_public: boolean;
  rating: number;
  created_at: string;
  // 智能检索相关属性
  final_score?: number;
  match_reason?: string;
}

export interface TemplateListResponse {
  templates: ContractTemplate[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
}