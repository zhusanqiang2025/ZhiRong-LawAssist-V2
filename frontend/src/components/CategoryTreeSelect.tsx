// frontend/src/components/CategoryTreeSelect.tsx
import React from 'react';
import { TreeSelect, TreeSelectProps } from 'antd';
import { FolderOutlined, FolderOpenOutlined } from '@ant-design/icons';
import type { DataNode } from 'antd/es/tree';
import { CategoryNode } from '../api/categoryService';

const { TreeNode } = TreeSelect;

interface CategoryTreeSelectProps extends Omit<TreeSelectProps, 'treeData' | 'value' | 'onChange'> {
  treeData: CategoryNode[];
  value?: number[];
  onChange?: (value: number[]) => void;
  disabled?: boolean;
  showUniversalHint?: boolean;
  placeholder?: string;
}

const convertToTreeData = (categories: CategoryNode[]): DataNode[] => {
  return categories.map(category => ({
    title: category.name,
    value: category.id,
    key: category.id.toString(),
    children: category.children && category.children.length > 0
      ? convertToTreeData(category.children)
      : undefined,
    icon: category.children && category.children.length > 0
      ? <FolderOutlined />
      : <FolderOpenOutlined />
  }));
};

const CategoryTreeSelect: React.FC<CategoryTreeSelectProps> = ({
  treeData,
  value,
  onChange,
  disabled = false,
  showUniversalHint = true,
  placeholder = '请选择适用的合同分类（可多选，留空则为通用规则）',
  style,
  ...restProps
}) => {
  const treeNodes = React.useMemo(() => convertToTreeData(treeData), [treeData]);

  const displayValue = React.useMemo(() => {
    if (!value || value.length === 0) {
      return showUniversalHint ? '通用（所有分类）' : undefined;
    }
    return value;
  }, [value, showUniversalHint]);

  return (
    <TreeSelect
      treeData={treeNodes}
      value={displayValue}
      onChange={onChange as any}
      disabled={disabled}
      multiple
      treeCheckable
      showCheckedStrategy={TreeSelect.SHOW_PARENT}
      maxTagCount={3}
      maxTagPlaceholder={(omittedValues) => `+${omittedValues.length} 个分类`}
      showSearch
      treeNodeFilterProp="title"
      placeholder={placeholder}
      allowClear
      style={{ width: '100%', ...style }}
      dropdownStyle={{ maxHeight: 400, overflow: 'auto' }}
      treeDefaultExpandAll
      {...restProps}
    />
  );
};

export { convertToTreeData };
export default CategoryTreeSelect;