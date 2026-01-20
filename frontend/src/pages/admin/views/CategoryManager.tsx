import React, { useState, useEffect } from 'react';
import {
  Card, Tree, Button, Space, Tag, Modal, Form, Input, Switch,
  message, Popconfirm, TreeSelect, Typography, Row, Col, Divider, Descriptions
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ReloadOutlined,
  FolderOutlined, FolderOpenOutlined
} from '@ant-design/icons';
import { contractTemplateApi } from '../../../api/contractTemplates';
import type { CategoryTreeItem } from '../../../types/contract';

const { Text, Paragraph } = Typography;

const CategoryManager: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [treeData, setTreeData] = useState<CategoryTreeItem[]>([]);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<CategoryTreeItem | null>(null);
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([]);
  const [form] = Form.useForm();

  // 获取分类树
  const fetchTree = async () => {
    setLoading(true);
    try {
      const data = await contractTemplateApi.getCategoryTree(true);
      setTreeData(data);

      // 自动展开所有节点的 key
      const getAllKeys = (items: CategoryTreeItem[]): React.Key[] => {
        let keys: React.Key[] = [];
        items.forEach(item => {
          keys.push(item.id);
          if (item.children && item.children.length > 0) {
            keys = keys.concat(getAllKeys(item.children));
          }
        });
        return keys;
      };
      setExpandedKeys(getAllKeys(data));
    } catch (error) {
      message.error('加载分类失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTree();
  }, []);

  // 提交表单（新增/修改）
  const handleSubmit = async (values: any) => {
    try {
      if (editingId) {
        await contractTemplateApi.updateCategory(editingId, values);
        message.success('更新成功');
      } else {
        await contractTemplateApi.createCategory(values);
        message.success('创建成功');
      }
      setModalVisible(false);
      form.resetFields();
      fetchTree();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  // 删除分类
  const handleDelete = async (id: number) => {
    try {
      await contractTemplateApi.deleteCategory(id);
      message.success('删除成功');
      if (selectedCategory?.id === id) {
        setSelectedCategory(null);
      }
      fetchTree();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 查找分类节点
  const findCategory = (items: CategoryTreeItem[], id: number): CategoryTreeItem | null => {
    for (const item of items) {
      if (item.id === id) return item;
      if (item.children) {
        const found = findCategory(item.children, id);
        if (found) return found;
      }
    }
    return null;
  };

  // 渲染分类树节点
  const renderTreeNodes = (data: CategoryTreeItem[]): any[] => {
    return data.map(item => ({
      title: (
        <Space>
          <FolderOutlined style={{ color: '#1890ff' }} />
          <span>{item.name}</span>
          {item.code && <Tag style={{ margin: 0 }}>{item.code}</Tag>}
          <Tag style={{ margin: 0 }}>{item.template_count || 0}</Tag>
        </Space>
      ),
      key: item.id,
      selectable: true,
      children: item.children && item.children.length > 0 ? renderTreeNodes(item.children) : undefined
    }));
  };

  // 递归转换 TreeSelect 数据
  const renderTreeSelect = (data: CategoryTreeItem[]): any[] => {
    return data.map(item => ({
      title: item.name,
      value: item.id,
      children: item.children ? renderTreeSelect(item.children) : []
    }));
  };

  // 统计子分类数量
  const countChildren = (item: CategoryTreeItem): { level2: number; level3: number } => {
    let level2 = 0;
    let level3 = 0;

    if (item.children && item.children.length > 0) {
      level2 = item.children.length;
      item.children.forEach(child => {
        if (child.children && child.children.length > 0) {
          level3 += child.children.length;
        }
      });
    }

    return { level2, level3 };
  };

  // 打开编辑框
  const handleEdit = (record: CategoryTreeItem) => {
    setEditingId(record.id);
    form.setFieldsValue({
      name: record.name,
      code: record.code,
      description: record.description,
      parent_id: record.parent_id,
      is_active: record.is_active
    });
    setModalVisible(true);
  };

  // 打开新增框
  const handleAdd = (parentId?: number) => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      parent_id: parentId,
      is_active: true
    });
    setModalVisible(true);
  };

  // 获取分类层级名称
  const getLevelName = (item: CategoryTreeItem): string => {
    if (!item.parent_id) return '一级分类';
    // 检查父节点是否也有父节点
    const hasGrandparent = treeData.some(cat =>
      cat.children?.some(child => child.id === item.parent_id)
    );
    return hasGrandparent ? '三级分类' : '二级分类';
  };

  return (
    <>
      <Card
        title="合同分类配置"
        extra={
          <Space>
            <Button
              icon={<ReloadOutlined />}
              onClick={fetchTree}
            >
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => handleAdd()}
            >
              新增一级分类
            </Button>
          </Space>
        }
      >
        <Paragraph type="secondary" style={{ marginBottom: 16 }}>
          管理合同分类标准，维护三级分类体系。分类与合同模板的绑定在模板管理页面进行。
        </Paragraph>

        <Row gutter={16}>
          {/* 左侧：分类树 */}
          <Col span={10}>
            <Card
              title="分类树"
              size="small"
              style={{ height: 'calc(100vh - 240px)', overflow: 'auto' }}
            >
              <Tree
                treeData={renderTreeNodes(treeData)}
                onSelect={(keys) => {
                  if (keys[0]) {
                    const category = findCategory(treeData, Number(keys[0]));
                    setSelectedCategory(category || null);
                  } else {
                    setSelectedCategory(null);
                  }
                }}
                selectedKeys={selectedCategory ? [selectedCategory.id] : []}
                expandedKeys={expandedKeys}
                onExpand={setExpandedKeys}
                showIcon
                defaultExpandAll
                style={{ fontSize: 14 }}
              />
            </Card>
          </Col>

          {/* 右侧：分类详情和操作 */}
          <Col span={14}>
            <Card
              title={selectedCategory ? (
                <Space>
                  <span>分类详情</span>
                  <Tag color="blue">{getLevelName(selectedCategory)}</Tag>
                </Space>
              ) : "分类详情"}
              size="small"
              style={{ height: 'calc(100vh - 240px)', overflow: 'auto' }}
            >
              {selectedCategory ? (
                <>
                  <Descriptions column={1} bordered size="small">
                    <Descriptions.Item label="分类名称">
                      <Space>
                        {selectedCategory.name}
                        {selectedCategory.code && <Tag>{selectedCategory.code}</Tag>}
                      </Space>
                    </Descriptions.Item>
                    <Descriptions.Item label="分类层级">
                      <Tag color={selectedCategory.parent_id ? 'green' : 'blue'}>
                        {getLevelName(selectedCategory)}
                      </Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="模板数量">
                      <Tag color="purple">{selectedCategory.template_count || 0}</Tag>
                    </Descriptions.Item>
                    <Descriptions.Item label="状态">
                      <Tag color={selectedCategory.is_active ? 'success' : 'default'}>
                        {selectedCategory.is_active ? '启用' : '禁用'}
                      </Tag>
                    </Descriptions.Item>
                    {selectedCategory.description && (
                      <Descriptions.Item label="描述">
                        {selectedCategory.description}
                      </Descriptions.Item>
                    )}
                    {!selectedCategory.parent_id && (
                      <Descriptions.Item label="子分类统计">
                        <Space size="large">
                          <div>
                            <Text type="secondary">二级分类：</Text>
                            <Tag color="cyan">{selectedCategory.children?.length || 0}</Tag>
                          </div>
                          <div>
                            <Text type="secondary">三级分类：</Text>
                            <Tag color="purple">
                              {selectedCategory.children?.reduce((sum, child) =>
                                sum + (child.children?.length || 0), 0
                              ) || 0}
                            </Tag>
                          </div>
                        </Space>
                      </Descriptions.Item>
                    )}
                  </Descriptions>

                  <Divider />

                  <Space>
                    <Button
                      type="primary"
                      icon={<PlusOutlined />}
                      onClick={() => handleAdd(selectedCategory.id)}
                    >
                      新增子分类
                    </Button>
                    <Button
                      icon={<EditOutlined />}
                      onClick={() => handleEdit(selectedCategory)}
                    >
                      编辑
                    </Button>
                    <Popconfirm
                      title="确定删除此分类？"
                      description="删除后不可恢复"
                      onConfirm={() => handleDelete(selectedCategory.id)}
                      okText="确定"
                      cancelText="取消"
                    >
                      <Button danger icon={<DeleteOutlined />}>
                        删除
                      </Button>
                    </Popconfirm>
                  </Space>
                </>
              ) : (
                <div style={{ textAlign: 'center', padding: '40px 0' }}>
                  <Text type="secondary">请从左侧选择一个分类查看详情</Text>
                </div>
              )}
            </Card>
          </Col>
        </Row>
      </Card>

      {/* 新增/编辑分类 Modal */}
      <Modal
        title={editingId ? "编辑分类" : "新增分类"}
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        onOk={form.submit}
        width={600}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item name="parent_id" label="上级分类">
            <TreeSelect
              treeData={renderTreeSelect(treeData)}
              placeholder="无（作为一级分类）"
              allowClear
              treeDefaultExpandAll
              showSearch
            />
          </Form.Item>

          <Form.Item
            name="name"
            label="分类名称"
            rules={[{ required: true, message: '请输入分类名称' }]}
          >
            <Input placeholder="例如：民法典典型合同" />
          </Form.Item>

          <Form.Item name="code" label="分类编码">
            <Input placeholder="例如：1-1（可选，用于排序和识别）" />
          </Form.Item>

          <Form.Item name="description" label="分类描述">
            <Input.TextArea
              rows={3}
              placeholder="描述此分类的用途和适用范围"
            />
          </Form.Item>

          <Space style={{ width: '100%' }}>
            <Form.Item name="is_active" label="启用状态" valuePropName="checked" tooltip="禁用后，此分类不会在前端显示">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </>
  );
};

export default CategoryManager;
