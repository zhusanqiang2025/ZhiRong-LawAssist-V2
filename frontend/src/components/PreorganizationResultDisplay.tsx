// frontend/src/components/PreorganizationResultDisplay.tsx
/**
 * 预整理结果展示组件
 *
 * 用于展示文档预整理的结果，包括：
 * 1. 用户需求总结（可编辑）
 * 2. 资料预整理列表（可编辑）
 * 3. 事实情况总结（可编辑）
 * 4. 合同法律特征（展示）
 * 5. 合同关系（展示）
 * 6. 架构图（如有）
 * 7. 分析模式选择（单模型/多模型）
 */

import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { DiagramViewer } from '@/components/DiagramViewer';
import {
  Edit2,
  Check,
  X,
  FileText,
  Users,
  Calendar,
  DollarSign,
  Building2,
  AlertCircle,
  CheckCircle2,
} from 'lucide-react';

interface PreorganizationResultDisplayProps {
  sessionId: string;
  data: PreorganizationResultData;
  onConfirm: (modifications: UserModifications) => void;
  onStartAnalysis: (mode: 'single' | 'multi', model?: string) => void;
  loading?: boolean;
}

interface PreorganizationResultData {
  user_requirement_summary?: string;
  documents_info?: DocumentInfo[];
  fact_summary?: FactSummary;
  contract_legal_features?: ContractLegalFeatures;
  contract_relationships?: ContractRelationship[];
  architecture_diagram?: ArchitectureDiagram;
}

interface DocumentInfo {
  file_name: string;
  signing_date?: string;
  file_type?: string;
  entities?: string[];
  amount?: string;
  subject?: string;
  core_content?: string;
}

interface FactSummary {
  timeline?: string[];
  location?: string;
  entities?: string[];
  core_events?: string[];
  contract_name?: string;
  legal_relationships?: string[];
}

interface ContractLegalFeatures {
  contract_type?: string;
  legal_features?: {
    transaction_nature?: string;
    contract_object?: string;
    stance?: string;
    consideration_type?: string;
    consideration_detail?: string;
    transaction_characteristics?: string;
    usage_scenario?: string;
    legal_basis?: string[];
  };
  matched_keywords?: string[];
}

interface ContractRelationship {
  relationship_type: string;
  main_contract: string;
  related_contract: string;
  confidence?: number;
  detection_method?: string;
}

interface ArchitectureDiagram {
  diagram_type: string;
  format: string;
  code: string;
  title?: string;
  metadata?: {
    companies?: string[];
    shareholders?: string[];
    total_nodes?: number;
  };
}

interface UserModifications {
  user_requirement_summary?: {
    original_value: string;
    modified_value: string;
  };
  documents_info?: {
    original_value: DocumentInfo[];
    modified_value: DocumentInfo[];
  };
  fact_summary?: {
    original_value: FactSummary;
    modified_value: FactSummary;
  };
}

export const PreorganizationResultDisplay: React.FC<PreorganizationResultDisplayProps> = ({
  sessionId,
  data,
  onConfirm,
  onStartAnalysis,
  loading = false,
}) => {
  // 编辑状态管理
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editedData, setEditedData] = useState<PreorganizationResultData>(data);
  const [analysisMode, setAnalysisMode] = useState<'single' | 'multi'>('multi');
  const [selectedModel, setSelectedModel] = useState<string>('gpt-4');

  // 当外部数据更新时，同步到本地状态
  useEffect(() => {
    setEditedData(data);
  }, [data]);

  // 开始编辑
  const handleStartEdit = (field: string) => {
    setEditingField(field);
  };

  // 取消编辑
  const handleCancelEdit = () => {
    setEditingField(null);
    setEditedData(data);
  };

  // 保存编辑
  const handleSaveEdit = (field: string) => {
    setEditingField(null);
    // 构建修改记录
    const modifications: UserModifications = {};
    if (field === 'user_requirement_summary') {
      modifications.user_requirement_summary = {
        original_value: data.user_requirement_summary || '',
        modified_value: editedData.user_requirement_summary || '',
      };
    } else if (field === 'documents_info') {
      modifications.documents_info = {
        original_value: data.documents_info || [],
        modified_value: editedData.documents_info || [],
      };
    } else if (field === 'fact_summary') {
      modifications.fact_summary = {
        original_value: data.fact_summary || {},
        modified_value: editedData.fact_summary || {},
      };
    }
    onConfirm(modifications);
  };

  // 处理确认并开始分析
  const handleConfirmAndStart = () => {
    // 先确认（如果有修改）
    const modifications: UserModifications = {};
    if (JSON.stringify(editedData) !== JSON.stringify(data)) {
      if (editedData.user_requirement_summary !== data.user_requirement_summary) {
        modifications.user_requirement_summary = {
          original_value: data.user_requirement_summary || '',
          modified_value: editedData.user_requirement_summary || '',
        };
      }
      if (JSON.stringify(editedData.documents_info) !== JSON.stringify(data.documents_info)) {
        modifications.documents_info = {
          original_value: data.documents_info || [],
          modified_value: editedData.documents_info || [],
        };
      }
      if (JSON.stringify(editedData.fact_summary) !== JSON.stringify(data.fact_summary)) {
        modifications.fact_summary = {
          original_value: data.fact_summary || {},
          modified_value: editedData.fact_summary || {},
        };
      }
      onConfirm(modifications);
    }

    // 开始分析
    onStartAnalysis(analysisMode, analysisMode === 'single' ? selectedModel : undefined);
  };

  // 获取关系类型的中文名称
  const getRelationshipTypeName = (type: string): string => {
    const typeMap: Record<string, string> = {
      'master_supplement': '主合同-补充协议',
      'master_termination': '主合同-解除通知',
      'amendment': '修订协议',
      'related': '相关文档',
    };
    return typeMap[type] || type;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto p-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-bold">文档预整理结果</h2>
          <p className="text-muted-foreground mt-1">
            请确认以下信息是否准确，可以选择修改后开始风险分析
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCancelEdit} disabled={loading}>
            <X className="mr-2 h-4 w-4" />
            重置
          </Button>
          <Button onClick={handleConfirmAndStart} disabled={loading}>
            <Check className="mr-2 h-4 w-4" />
            确认并开始分析
          </Button>
        </div>
      </div>

      {/* 主要内容区域 */}
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="overview">概览</TabsTrigger>
          <TabsTrigger value="documents">资料详情</TabsTrigger>
          <TabsTrigger value="facts">事实情况</TabsTrigger>
          <TabsTrigger value="relationships">关系分析</TabsTrigger>
        </TabsList>

        {/* 概览标签页 */}
        <TabsContent value="overview" className="space-y-4">
          {/* 用户需求总结 */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  用户需求总结
                </CardTitle>
                {editingField !== 'user_requirement_summary' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleStartEdit('user_requirement_summary')}
                  >
                    <Edit2 className="h-4 w-4" />
                  </Button>
                )}
                {editingField === 'user_requirement_summary' && (
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm" onClick={handleCancelEdit}>
                      <X className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleSaveEdit('user_requirement_summary')}
                    >
                      <Check className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {editingField === 'user_requirement_summary' ? (
                <Textarea
                  value={editedData.user_requirement_summary || ''}
                  onChange={(e) =>
                    setEditedData({ ...editedData, user_requirement_summary: e.target.value })
                  }
                  rows={4}
                  className="w-full"
                />
              ) : (
                <p className="text-sm leading-relaxed">
                  {editedData.user_requirement_summary || '暂无用户需求描述'}
                </p>
              )}
            </CardContent>
          </Card>

          {/* 合同法律特征 */}
          {data.contract_legal_features && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Building2 className="h-5 w-5" />
                  合同法律特征
                </CardTitle>
                {data.contract_legal_features.contract_type && (
                  <CardDescription>
                    识别为：{data.contract_legal_features.contract_type}
                  </CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4">
                  {data.contract_legal_features.legal_features && (
                    <>
                      {data.contract_legal_features.legal_features.transaction_nature && (
                        <div>
                          <Label className="text-muted-foreground">交易性质</Label>
                          <p className="text-sm font-medium">
                            {data.contract_legal_features.legal_features.transaction_nature}
                          </p>
                        </div>
                      )}
                      {data.contract_legal_features.legal_features.contract_object && (
                        <div>
                          <Label className="text-muted-foreground">合同标的</Label>
                          <p className="text-sm font-medium">
                            {data.contract_legal_features.legal_features.contract_object}
                          </p>
                        </div>
                      )}
                      {data.contract_legal_features.legal_features.stance && (
                        <div>
                          <Label className="text-muted-foreground">立场</Label>
                          <p className="text-sm font-medium">
                            {data.contract_legal_features.legal_features.stance}
                          </p>
                        </div>
                      )}
                      {data.contract_legal_features.legal_features.consideration_type && (
                        <div>
                          <Label className="text-muted-foreground">对价类型</Label>
                          <p className="text-sm font-medium">
                            {data.contract_legal_features.legal_features.consideration_type}
                          </p>
                        </div>
                      )}
                    </>
                  )}
                </div>
                {data.contract_legal_features.matched_keywords && (
                  <div className="mt-4">
                    <Label className="text-muted-foreground">匹配关键词</Label>
                    <div className="flex flex-wrap gap-2 mt-2">
                      {data.contract_legal_features.matched_keywords.map((kw, idx) => (
                        <Badge key={idx} variant="secondary">
                          {kw}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* 架构图 */}
          {data.architecture_diagram && (
            <Card>
              <CardHeader>
                <CardTitle>股权/投资架构图</CardTitle>
                {data.architecture_diagram.title && (
                  <CardDescription>{data.architecture_diagram.title}</CardDescription>
                )}
              </CardHeader>
              <CardContent>
                <DiagramViewer
                  diagramType={data.architecture_diagram.diagram_type}
                  format={data.architecture_diagram.format}
                  sourceCode={data.architecture_diagram.code}
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* 资料详情标签页 */}
        <TabsContent value="documents" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>资料预整理详情</CardTitle>
                {editingField !== 'documents_info' && data.documents_info && data.documents_info.length > 0 && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleStartEdit('documents_info')}
                  >
                    <Edit2 className="h-4 w-4" />
                  </Button>
                )}
                {editingField === 'documents_info' && (
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm" onClick={handleCancelEdit}>
                      <X className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleSaveEdit('documents_info')}>
                      <Check className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {!data.documents_info || data.documents_info.length === 0 ? (
                <p className="text-center text-muted-foreground py-8">暂无资料信息</p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>文件名</TableHead>
                      <TableHead>签署时间</TableHead>
                      <TableHead>类型</TableHead>
                      <TableHead>主体</TableHead>
                      <TableHead>金额</TableHead>
                      <TableHead>标的</TableHead>
                      <TableHead>核心内容</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {editedData.documents_info?.map((doc, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-medium">{doc.file_name}</TableCell>
                        <TableCell>{doc.signing_date || '-'}</TableCell>
                        <TableCell>{doc.file_type || '-'}</TableCell>
                        <TableCell>
                          {doc.entities && doc.entities.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {doc.entities.map((entity, i) => (
                                <Badge key={i} variant="outline" className="text-xs">
                                  {entity}
                                </Badge>
                              ))}
                            </div>
                          ) : (
                            '-'
                          )}
                        </TableCell>
                        <TableCell>{doc.amount || '-'}</TableCell>
                        <TableCell>{doc.subject || '-'}</TableCell>
                        <TableCell className="max-w-xs truncate">
                          {doc.core_content || '-'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 事实情况标签页 */}
        <TabsContent value="facts" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>事实情况总结</CardTitle>
                {editingField !== 'fact_summary' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleStartEdit('fact_summary')}
                  >
                    <Edit2 className="h-4 w-4" />
                  </Button>
                )}
                {editingField === 'fact_summary' && (
                  <div className="flex gap-2">
                    <Button variant="ghost" size="sm" onClick={handleCancelEdit}>
                      <X className="h-4 w-4" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => handleSaveEdit('fact_summary')}>
                      <Check className="h-4 w-4" />
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {editedData.fact_summary ? (
                <>
                  {editedData.fact_summary.timeline && editedData.fact_summary.timeline.length > 0 && (
                    <div>
                      <Label className="text-muted-foreground flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        时间线
                      </Label>
                      <ul className="mt-2 space-y-1">
                        {editedData.fact_summary.timeline.map((event, idx) => (
                          <li key={idx} className="text-sm">
                            • {event}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {editedData.fact_summary.location && (
                    <div>
                      <Label className="text-muted-foreground">地点</Label>
                      <p className="text-sm font-medium mt-1">{editedData.fact_summary.location}</p>
                    </div>
                  )}
                  {editedData.fact_summary.entities && editedData.fact_summary.entities.length > 0 && (
                    <div>
                      <Label className="text-muted-foreground flex items-center gap-2">
                        <Users className="h-4 w-4" />
                        相关主体
                      </Label>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {editedData.fact_summary.entities.map((entity, idx) => (
                          <Badge key={idx} variant="secondary">
                            {entity}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                  {editedData.fact_summary.core_events && editedData.fact_summary.core_events.length > 0 && (
                    <div>
                      <Label className="text-muted-foreground">核心事件</Label>
                      <ul className="mt-2 space-y-1">
                        {editedData.fact_summary.core_events.map((event, idx) => (
                          <li key={idx} className="text-sm">
                            • {event}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {editedData.fact_summary.contract_name && (
                    <div>
                      <Label className="text-muted-foreground">合同名称</Label>
                      <p className="text-sm font-medium mt-1">{editedData.fact_summary.contract_name}</p>
                    </div>
                  )}
                  {editedData.fact_summary.legal_relationships && editedData.fact_summary.legal_relationships.length > 0 && (
                    <div>
                      <Label className="text-muted-foreground">法律关系</Label>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {editedData.fact_summary.legal_relationships.map((rel, idx) => (
                          <Badge key={idx} variant="outline">
                            {rel}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-center text-muted-foreground py-8">暂无事实情况总结</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 关系分析标签页 */}
        <TabsContent value="relationships" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>合同关系分析</CardTitle>
              <CardDescription>
                基于文件名模式和LLM分析识别的合同间关系
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!data.contract_relationships || data.contract_relationships.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <CheckCircle2 className="h-12 w-12 text-muted-foreground mb-2" />
                  <p className="text-muted-foreground">未检测到合同间关系</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {data.contract_relationships.map((rel, idx) => (
                    <div key={idx} className="border rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <Badge variant="secondary">{getRelationshipTypeName(rel.relationship_type)}</Badge>
                        {rel.confidence !== undefined && (
                          <Badge variant="outline">置信度: {(rel.confidence * 100).toFixed(0)}%</Badge>
                        )}
                      </div>
                      <div className="space-y-1 text-sm">
                        <p>
                          <span className="font-medium">主合同：</span>
                          {rel.main_contract}
                        </p>
                        <p>
                          <span className="font-medium">相关合同：</span>
                          {rel.related_contract}
                        </p>
                        {rel.detection_method && (
                          <p className="text-muted-foreground">
                            检测方法：{rel.detection_method === 'filename_pattern' ? '文件名模式匹配' : 'LLM内容分析'}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* 底部固定的分析模式选择区域 */}
      <Card className="sticky bottom-0 z-10 shadow-lg">
        <CardContent className="pt-6">
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold mb-2">选择分析模式</h3>
              <p className="text-sm text-muted-foreground">
                选择使用单个模型或多个模型进行风险分析
              </p>
            </div>

            <RadioGroup value={analysisMode} onValueChange={(v) => setAnalysisMode(v as 'single' | 'multi')}>
              <div className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-accent">
                <RadioGroupItem value="multi" id="multi" />
                <Label htmlFor="multi" className="flex-1 cursor-pointer">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">多模型并行分析</p>
                      <p className="text-sm text-muted-foreground">
                        使用多个模型同时分析，提供更全面的风险评估
                      </p>
                    </div>
                    <CheckCircle2 className="h-5 w-5 text-primary" />
                  </div>
                </Label>
              </div>

              <div className="flex items-center space-x-2 p-3 border rounded-lg hover:bg-accent">
                <RadioGroupItem value="single" id="single" />
                <Label htmlFor="single" className="flex-1 cursor-pointer">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <p className="font-medium">单模型分析</p>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      使用指定的模型进行快速分析
                    </p>
                    {analysisMode === 'single' && (
                      <Select value={selectedModel} onValueChange={setSelectedModel}>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="选择模型" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="gpt-4">GPT-4</SelectItem>
                          <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
                          <SelectItem value="claude-3-opus">Claude 3 Opus</SelectItem>
                          <SelectItem value="claude-3-sonnet">Claude 3 Sonnet</SelectItem>
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                </Label>
              </div>
            </RadioGroup>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
