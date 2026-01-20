/**
 * 合同规划相关类型定义
 */

export interface PlanningModeOption {
  id: string;
  name: string;
  description: string;
  features: string[];
  expected_quality: string;
  processing_time: string;
  available: boolean;
  recommended: boolean;
}

export interface PlanningModeOptionsResponse {
  success: boolean;
  options: {
    multi_model: PlanningModeOption;
    single_model: PlanningModeOption;
  };
  default_choice: string;
}

export interface AnalyzeAndGetFormRequest {
  user_input: string;
  uploaded_files?: string[];
  planning_mode?: 'multi_model' | 'single_model' | null;
}

export interface RequiresUserChoiceResponse {
  success: boolean;
  processing_type: 'contract_planning';
  requires_user_choice: true;
  user_choice_options: {
    multi_model: PlanningModeOption;
    single_model: PlanningModeOption;
  };
  default_choice: string;
}

export interface PlannedContract {
  id: string;
  title: string;
  contract_type: string;
  purpose: string;
  priority: number;
}

export interface ContractPlanningResult {
  success: boolean;
  processing_type: 'contract_planning';
  analysis_result: {
    contracts: PlannedContract[];
    signing_order: string[];
    relationships: Record<string, string[]>;
    risk_notes: string[];
    overall_description: string;
    total_estimated_contracts: number;
    planning_mode: 'multi_model' | 'single_model';
  };
}

export type ContractPlanningResponse = RequiresUserChoiceResponse | ContractPlanningResult;
