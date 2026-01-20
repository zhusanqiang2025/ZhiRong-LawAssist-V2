// frontend/src/config/litigationConfig.ts
/**
 * 案件分析配置
 */

export const caseTypeOptions = [
  {
    value: 'contract_performance',
    label: '合同履约分析',
    icon: '📄',
    description: '分析合同履约情况，制定诉讼方案'
  },
  {
    value: 'complaint_defense',
    label: '起诉状分析',
    icon: '⚖️',
    description: '分析起诉状，制定应诉策略'
  },
  {
    value: 'judgment_appeal',
    label: '判决分析',
    icon: '📜',
    description: '分析判决书，制定上诉策略'
  },
  {
    value: 'evidence_preservation',
    label: '保全申请',
    icon: '🔒',
    description: '财产保全、证据保全申请策略'
  },
  {
    value: 'enforcement',
    label: '强制执行',
    icon: '⚖️',
    description: '判决执行策略、财产线索分析'
  },
  {
    value: 'arbitration',
    label: '仲裁程序',
    icon: '⚖️',
    description: '仲裁申请、答辩、证据策略'
  }
];

/**
 * 案件类型到规则包ID的映射
 * 用于前端调用后端API时传递正确的 package_id
 */
export const CASE_TYPE_TO_PACKAGE_ID: Record<string, string> = {
  'contract_performance': 'contract_performance_v1',
  'complaint_defense': 'complaint_defense_v1',
  'judgment_appeal': 'judgment_appeal_v1',
  'evidence_preservation': 'evidence_preservation_v1',
  'enforcement': 'enforcement_v1',
  'arbitration': 'arbitration_v1'
};

/**
 * 根据案件类型获取对应的规则包ID
 * @param caseType 案件类型
 * @returns 规则包ID，如果未找到则返回通用规则包ID
 */
export const getPackageIdByCaseType = (caseType: string): string => {
  return CASE_TYPE_TO_PACKAGE_ID[caseType] || 'contract_performance_v1';
};

export const positionOptions = [
  { value: 'plaintiff', label: '原告', icon: '👤' },
  { value: 'defendant', label: '被告', icon: '👥' },
  { value: 'appellant', label: '上诉人', icon: '📝' },
  { value: 'appellee', label: '被上诉人', icon: '📄' },
  { value: 'applicant', label: '申请人', icon: '📋' },
  { value: 'respondent', label: '被申请人', icon: '📋' },
  { value: 'third_party', label: '第三人', icon: '👥' }
];

/**
 * 分析场景选项（3阶段架构：阶段2需要）
 */
export const analysisScenarioOptions = [
  { value: 'pre_litigation', label: '准备起诉', icon: '📋', description: '评估起诉可行性，制定诉讼策略' },
  { value: 'defense', label: '应诉准备', icon: '🛡️', description: '分析对方起诉，制定抗辩策略' },
  { value: 'appeal', label: '上诉分析', icon: '📝', description: '分析一审判决，制定上诉策略' },
  { value: 'execution', label: '执行阶段', icon: '⚖️', description: '判决执行策略、财产线索分析' },
  { value: 'preservation', label: '财产保全', icon: '🔒', description: '财产保全、证据保全申请策略' },
  { value: 'evidence_collection', label: '证据收集', icon: '🔍', description: '证据收集计划和策略' },
  { value: 'mediation', label: '调解准备', icon: '🤝', description: '调解谈判策略和准备' }
];
