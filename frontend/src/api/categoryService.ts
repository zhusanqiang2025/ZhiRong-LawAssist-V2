import { axiosInstance } from './index';

/**
 * 分类节点接口
 */
export interface CategoryNode {
  id: number;
  name: string;
  code?: string | null;
  description?: string | null;
  parent_id: number | null;
  sort_order: number;
  is_active: boolean;
  meta_info?: Record<string, any>;
  template_count?: number;
  children?: CategoryNode[];
}

/**
 * 分类服务 API
 */
export const categoryService = {
  /**
   * 获取分类树
   * @param includeInactive - 是否包含已禁用的分类
   * @returns 分类树数据
   */
  fetchCategoryTree: async (includeInactive = false): Promise<CategoryNode[]> => {
    const response = await axiosInstance.get<CategoryNode[]>('/categories/tree', {
      params: { include_inactive: includeInactive }
    });
    return response.data;
  },

  /**
   * 创建分类
   * @param data - 分类数据
   * @returns 创建的分类
   */
  createCategory: async (data: Partial<CategoryNode>): Promise<CategoryNode> => {
    const response = await axiosInstance.post<CategoryNode>('/categories/', data);
    return response.data;
  },

  /**
   * 更新分类
   * @param categoryId - 分类ID
   * @param data - 更新数据
   * @returns 更新后的分类
   */
  updateCategory: async (categoryId: number, data: Partial<CategoryNode>): Promise<CategoryNode> => {
    const response = await axiosInstance.put<CategoryNode>(`/categories/${categoryId}`, data);
    return response.data;
  },

  /**
   * 删除分类
   * @param categoryId - 分类ID
   */
  deleteCategory: async (categoryId: number): Promise<void> => {
    await axiosInstance.delete(`/categories/${categoryId}`);
  },

  /**
   * 获取所有分类（扁平列表）
   * @returns 分类列表
   */
  fetchCategories: async (): Promise<CategoryNode[]> => {
    const response = await axiosInstance.get<CategoryNode[]>('/categories/');
    return response.data;
  }
};

/**
 * 辅助函数：根据分类ID列表获取分类名称
 */
export const getCategoryNamesByIds = (
  categories: CategoryNode[],
  categoryIds?: number[]
): string[] => {
  if (!categoryIds || categoryIds.length === 0) {
    return [];
  }

  const names: string[] = [];
  const findById = (nodes: CategoryNode[], targetId: number): string | null => {
    for (const node of nodes) {
      if (node.id === targetId) {
        return node.name;
      }
      if (node.children && node.children.length > 0) {
        const found = findById(node.children, targetId);
        if (found) {
          return found;
        }
      }
    }
    return null;
  };

  for (const id of categoryIds) {
    const name = findById(categories, id);
    if (name) {
      names.push(name);
    }
  }

  return names;
};

/**
 * 辅助函数：扁平化分类树
 */
export const flattenCategories = (nodes: CategoryNode[]): CategoryNode[] => {
  const result: CategoryNode[] = [];

  const traverse = (node: CategoryNode) => {
    result.push(node);
    if (node.children && node.children.length > 0) {
      for (const child of node.children) {
        traverse(child);
      }
    }
  };

  for (const node of nodes) {
    traverse(node);
  }

  return result;
};

export type { CategoryNode };
