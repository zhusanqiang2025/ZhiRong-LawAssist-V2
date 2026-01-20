# 管理员后台项目结构与代码文档

## 一、访问入口

### 前端入口

**位置**: 用户界面右上角用户名下拉菜单

**路径**: `frontend/src/pages/SceneSelectionPage.tsx:224-236`

```typescript
const userMenuItems: MenuProps['items'] = [
  {
    key: 'profile',
    label: '个人中心',
    icon: <UserOutlined />,
  },
  // 仅管理员可见的入口
  ...(user?.is_admin ? [{
    key: 'admin',
    label: '系统管理后台',
    icon: <SettingOutlined />,
    onClick: () => navigate('/admin')
  }] : []),
  {
    type: 'divider',
  },
  {
    key: 'logout',
    label: '退出登录',
  }
];
```

**权限控制**: 仅当 `user.is_admin === true` 时显示"系统管理后台"选项

---

## 二、前端项目结构

### 1. 路由配置

**文件**: [frontend/src/App.tsx:175-183](frontend/src/App.tsx#L175-L183)

```typescript
{/* 管理后台 */}
<Route
  path="/admin"
  element={
    <PrivateRoute>
      <AdminPage />
    </PrivateRoute>
  }
/>
```

### 2. 主页面组件

**文件**: [frontend/src/pages/AdminPage.tsx](frontend/src/pages/AdminPage.tsx)

**组件结构**:

```
AdminPage (主组件)
├── DashboardView (数据仪表盘)
├── CategoryManagerView (合同分类配置)
└── TemplateManagerView (模板管理)
```

#### 2.1 AdminPage 主组件

**位置**: `AdminPage.tsx:1002-1055`

**功能**:
- 权限验证（仅管理员可访问）
- 左侧导航菜单（三个功能标签）
- 内容区域渲染

```typescript
const AdminPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [selectedKey, setSelectedKey] = useState('dashboard');

  // 权限验证
  useEffect(() => {
    if (user && !user.is_admin) {
      message.error('无权访问');
      navigate('/');
    }
  }, [user, navigate]);

  // 导航菜单
  const menuItems = [
    { key: 'dashboard', icon: <DashboardOutlined />, label: '数据仪表盘' },
    { key: 'categories', icon: <AppstoreOutlined />, label: '合同分类配置' },
    { key: 'templates', icon: <FileTextOutlined />, label: '模板管理' },
  ];

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header>
        <Button onClick={() => navigate('/')}>返回前台</Button>
        <Title level={4}>系统管理后台</Title>
      </Header>
      <Layout>
        <Sider width={220}>
          <Menu
            mode="inline"
            selectedKeys={[selectedKey]}
            onClick={(e) => setSelectedKey(e.key)}
            items={menuItems}
          />
        </Sider>
        <Content>
          {renderContent()}
        </Content>
      </Layout>
    </Layout>
  );
};
```

#### 2.2 数据仪表盘 (DashboardView)

**位置**: `AdminPage.tsx:72-330`

**功能**:
- 显示系统统计信息（用户数、模板数、下载量等）
- 用户列表管理（分页显示）

**API调用**:
```typescript
// 获取系统统计
const statsRes = await api.getSystemStats();
// GET /api/v1/admin/stats

// 获取用户列表
const usersRes = await api.getUserList();
// GET /api/v1/admin/users?page=1&size=10
```

**数据字段**:
```typescript
interface SystemStats {
  total_users: number;          // 总用户数
  total_templates: number;       // 总模板数
  total_downloads: number;       // 总下载量
  total_tasks: number;           // 总任务数
  active_users_today: number;    // 今日活跃用户
  total_online_time: number;     // 总在线时间
}

interface UserStats {
  id: number;
  email: string;
  is_admin: boolean;
  template_count: number;
  task_count: number;
  download_count: number;
  last_active: string;
  created_at: string;
}
```

#### 2.3 合同分类配置 (CategoryManagerView)

**位置**: `AdminPage.tsx:790-997`

**功能**:
- 显示13种标准合同类型统计
- 显示每种类型的模板数量和V2特征完整率
- 查看每种类型的详细模板列表

**V2特征升级重点**:
```typescript
// 13种标准合同类型
const PRIMARY_CONTRACT_TYPES = [
  { value: '买卖合同', label: '买卖合同', description: '货物买卖、资产转让等' },
  { value: '建设工程合同', label: '建设工程合同', description: '工程施工、设计、监理等' },
  { value: '承揽合同', label: '承揽合同', description: '加工承揽、定制服务等' },
  // ... 共13种
];

// 统计每种类型的V2特征完整率
const typeStats = PRIMARY_CONTRACT_TYPES.map(type => {
  const templates = allTemplates.filter(t => t.primary_contract_type === type.value);
  const completeCount = templates.filter(t =>
    t.transaction_nature && t.contract_object && t.complexity && t.stance
  ).length;

  return {
    ...type,
    count: templates.length,
    completeCount,
    incompleteCount: templates.length - completeCount
  };
});
```

**表格列**:
```typescript
const columns = [
  { title: '合同类型', dataIndex: 'label' },
  {
    title: '模板统计',
    render: (_, record) => (
      <Space size="large">
        <Statistic title="总数" value={record.count} />
        <Statistic title="V2完整" value={record.completeCount} />
        <Statistic title="待补充" value={record.incompleteCount} />
      </Space>
    )
  },
  {
    title: '完整率',
    render: (_, record) => {
      const rate = record.count > 0 ? Math.round((record.completeCount / record.count) * 100) : 0;
      return <Progress percent={rate} />;
    }
  },
  {
    title: '操作',
    render: (_, record) => (
      <Button onClick={() => showDetails(record.value)}>查看详情</Button>
    )
  }
];
```

#### 2.4 模板管理 (TemplateManagerView)

**位置**: `AdminPage.tsx:335-785`

**功能**:
- 查看所有模板列表（分页）
- 上传新模板
- 编辑V2四维法律特征
- 删除模板

**V2特征编辑器**:
```typescript
// 使用 TemplateV2Editor 组件
<TemplateV2Editor
  visible={v2ModalVisible}
  template={selectedTemplate}
  onSave={handleV2Save}
  onCancel={() => setV2ModalVisible(false)}
/>
```

**模板列表表格**:
```typescript
const columns = [
  { title: '名称', dataIndex: 'name' },
  {
    title: '主合同类型',
    dataIndex: 'primary_contract_type',
    render: (t) => <Tag color="blue">{t}</Tag>
  },
  {
    title: 'V2 特征',
    key: 'v2_features',
    render: (_, record) => (
      <Space size="small" wrap>
        {record.transaction_nature && (
          <Tag color="geekblue">交易: {record.transaction_nature}</Tag>
        )}
        {record.contract_object && (
          <Tag color="purple">标的: {record.contract_object}</Tag>
        )}
        {record.complexity && (
          <Tag color="orange">复杂度: {record.complexity}</Tag>
        )}
        {record.stance && (
          <Tag color="cyan">立场: {record.stance}</Tag>
        )}
      </Space>
    )
  },
  {
    title: '风险/推荐',
    render: (_, record) => (
      <Space>
        {record.risk_level && <Tag>{record.risk_level}</Tag>}
        {record.is_recommended && <Tag color="gold">⭐ 推荐</Tag>}
      </Space>
    )
  },
  {
    title: '权限',
    dataIndex: 'is_public',
    render: (pub) => pub ? <Tag color="green">公开</Tag> : <Tag color="orange">私有</Tag>
  },
  {
    title: '操作',
    render: (_, record) => (
      <Space>
        <Button onClick={() => handleEditV2(record)}>V2特征</Button>
        <Popconfirm
          title="确定删除此模版？"
          onConfirm={() => handleDelete(record.id)}
        >
          <Button danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    )
  }
];
```

---

## 三、后端API结构

### 3.1 路由配置

**文件**: [backend/app/api/v1/router.py](backend/app/api/v1/router.py)

```python
from app.api.v1.endpoints import auth, rag_management, contract_templates, admin, categories

api_router = APIRouter()

# 认证路由
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# 管理员路由（新增）
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])

# 分类路由（新增）
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])

# RAG管理路由
api_router.include_router(rag_management.router, prefix="/rag", tags=["RAG Management"])

# 合同模板路由
api_router.include_router(contract_templates.router, prefix="/contract", tags=["Contract Templates"])
```

### 3.2 管理员API端点

**文件**: [backend/app/api/v1/endpoints/admin.py](backend/app/api/v1/endpoints/admin.py)

#### 端点1: 获取系统统计

```python
@router.get("/stats")
async def get_system_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取系统统计信息

    仅管理员可访问
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    total_users = db.query(User).count()
    total_templates = db.query(ContractTemplate).filter(
        ContractTemplate.status == "active"
    ).count()
    total_downloads = db.query(func.sum(ContractTemplate.download_count)).scalar() or 0
    total_tasks = 0
    active_users_today = total_users
    total_online_time = 0

    return {
        "total_users": total_users,
        "total_templates": total_templates,
        "total_downloads": total_downloads,
        "total_tasks": total_tasks,
        "active_users_today": active_users_today,
        "total_online_time": total_online_time
    }
```

**API路径**: `GET /api/v1/admin/stats`
**权限**: 仅管理员
**返回**: 系统统计数据

#### 端点2: 获取用户列表

```python
@router.get("/users")
async def get_user_list(
    page: int = 1,
    size: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取用户列表（分页）

    仅管理员可访问
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可访问")

    total_count = db.query(User).count()
    users = db.query(User).offset((page - 1) * size).limit(size).all()

    user_list = []
    for user in users:
        template_count = db.query(ContractTemplate).filter(
            ContractTemplate.owner_id == user.id
        ).count()

        user_list.append({
            "id": user.id,
            "email": user.email,
            "is_admin": user.is_admin,
            "template_count": template_count,
            "task_count": 0,
            "download_count": 0,
            "last_active": None,
            "created_at": None
        })

    return {
        "items": user_list,
        "total": total_count,
        "page": page,
        "size": size
    }
```

**API路径**: `GET /api/v1/admin/users?page=1&size=10`
**权限**: 仅管理员
**返回**: 分页用户列表

### 3.3 分类API端点

**文件**: [backend/app/api/v1/endpoints/categories.py](backend/app/api/v1/endpoints/categories.py)

#### 端点1: 获取分类列表

```python
@router.get("/")
async def get_categories(db: Session = Depends(get_db)):
    """
    获取13种标准合同类型列表

    用于向后兼容，新系统使用 PrimaryContractType 枚举
    """
    PRIMARY_CONTRACT_TYPES = [
        {"name": "买卖合同", "value": "买卖合同"},
        {"name": "建设工程合同", "value": "建设工程合同"},
        {"name": "承揽合同", "value": "承揽合同"},
        # ... 共13种
    ]

    return {
        "categories": PRIMARY_CONTRACT_TYPES,
        "total": len(PRIMARY_CONTRACT_TYPES)
    }
```

**API路径**: `GET /api/v1/categories/`
**权限**: 所有用户
**返回**: 13种标准合同类型

### 3.4 合同模板API端点

**文件**: [backend/app/api/v1/endpoints/contract_templates.py](backend/app/api/v1/endpoints/contract_templates.py)

#### 端点1: 上传模板

```python
@router.post("/upload")
async def upload_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    primary_contract_type: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    is_public: bool = Form(False),
    # V2特征字段
    transaction_nature: Optional[str] = Form(None),
    contract_object: Optional[str] = Form(None),
    complexity: Optional[str] = Form(None),
    stance: Optional[str] = Form(None),
    risk_level: Optional[str] = Form(None),
    is_recommended: Optional[bool] = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    上传合同模板

    权限规则：
    - 管理员可以上传公开模板 (is_public=True) 和私有模板
    - 普通用户只能上传私有模板 (is_public=False)
    """
    # 权限验证：只有管理员可以上传公开模板
    if is_public and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="只有管理员可以上传公开模板")

    # 创建模板记录
    template = ContractTemplate(
        name=name,
        primary_contract_type=primary_contract_type,
        is_public=is_public,
        owner_id=current_user.id,
        # V2特征
        transaction_nature=transaction_nature,
        contract_object=contract_object,
        complexity=complexity,
        stance=stance,
        risk_level=risk_level,
        is_recommended=is_recommended,
    )

    db.add(template)
    db.commit()

    return template
```

**API路径**: `POST /api/v1/contract/upload`
**权限**: 所有用户（公开模板仅管理员）
**返回**: 创建的模板信息

#### 端点2: 更新V2特征

```python
@router.put("/{template_id}/v2-features")
async def update_template_v2_features(
    template_id: str,
    v2_data: V2FeaturesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新模板的 V2 法律特征

    仅管理员可以编辑 V2 法律特征
    """
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="仅管理员可编辑")

    template = db.query(ContractTemplate).filter(
        ContractTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 更新V2特征
    if v2_data.transaction_nature is not None:
        template.transaction_nature = v2_data.transaction_nature
    if v2_data.contract_object is not None:
        template.contract_object = v2_data.contract_object
    if v2_data.complexity is not None:
        template.complexity = v2_data.complexity
    if v2_data.stance is not None:
        template.stance = v2_data.stance

    db.commit()

    return {"message": "V2 法律特征已更新"}
```

**API路径**: `PUT /api/v1/contract/{template_id}/v2-features`
**权限**: 仅管理员
**返回**: 更新确认

#### 端点3: 删除模板

```python
@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除模板

    权限规则：
    - 公开模板：仅管理员可删除
    - 私有模板：所有者或管理员可删除
    """
    template = db.query(ContractTemplate).filter(
        ContractTemplate.id == template_id
    ).first()

    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 权限检查
    if template.is_public:
        if not current_user.is_admin:
            raise HTTPException(status_code=403, detail="只有管理员可以删除公开模板")
    else:
        if template.owner_id != current_user.id and not current_user.is_admin:
            raise HTTPException(status_code=403, detail="无权删除此模板")

    # 删除文件和记录
    os.remove(template.file_url)
    db.delete(template)
    db.commit()

    return {"message": "模板已删除"}
```

**API路径**: `DELETE /api/v1/contract/{template_id}`
**权限**: 根据模板权限动态控制
**返回**: 删除确认

---

## 四、前端API调用层

### 4.1 主API文件

**文件**: `frontend/src/api/index.ts`

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
});

// 管理员API
export const getSystemStats = () => api.get('/admin/stats');
export const getUserList = (params?: any) => api.get('/admin/users', { params });

// 分类API
export const getCategories = () => api.get('/categories/');

export default api;
```

### 4.2 合同模板API

**文件**: `frontend/src/api/contractTemplates.ts`

```typescript
import api from './index';

export interface ContractTemplate {
  id: string;
  name: string;
  category: string;
  primary_contract_type: string;
  is_public: boolean;
  // V2特征
  transaction_nature?: string;
  contract_object?: string;
  complexity?: string;
  stance?: string;
  risk_level?: string;
  is_recommended?: boolean;
}

export const contractTemplateApi = {
  // 获取模板列表
  getTemplates: (params: any) =>
    api.get('/contract', { params }),

  // 上传模板
  uploadTemplate: (data: FormData) =>
    api.post('/contract/upload', data, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),

  // 更新V2特征
  updateV2Features: (id: string, data: any) =>
    api.put(`/contract/${id}/v2-features`, data),

  // 删除模板
  deleteTemplate: (id: string) =>
    api.delete(`/contract/${id}`),
};
```

---

## 五、V2特征编辑组件

**文件**: `frontend/src/components/TemplateV2Editor.tsx`

**功能**: 提供V2四维法律特征的编辑界面

**表单字段**:
```typescript
interface V2FeaturesData {
  primary_contract_type: string;
  transaction_nature: string;
  contract_object: string;
  complexity: string;
  stance: string;
  delivery_model?: string;
  payment_model?: string;
  risk_level?: string;
  is_recommended?: boolean;
}
```

**UI组件**:
- 主合同类型选择器（13种标准类型）
- 交易性质下拉框
- 合同标的选择器
- 复杂程度选择器
- 立场选择器
- 风险等级选择器
- 推荐模板开关

---

## 六、数据流向图

```
用户操作
    ↓
前端组件 (AdminPage.tsx)
    ↓
API调用层 (api/index.ts)
    ↓
后端路由 (router.py)
    ↓
端点处理器 (admin.py / contract_templates.py)
    ↓
数据库操作 (PostgreSQL)
    ↓
返回结果
    ↓
前端更新UI
```

---

## 七、关键文件清单

### 前端文件

| 文件路径 | 功能描述 |
|---------|---------|
| `frontend/src/pages/AdminPage.tsx` | 管理员后台主页面 |
| `frontend/src/components/TemplateV2Editor.tsx` | V2特征编辑器 |
| `frontend/src/api/index.ts` | 主API调用文件 |
| `frontend/src/api/contractTemplates.ts` | 合同模板API |
| `frontend/src/App.tsx` | 路由配置 |
| `frontend/src/pages/SceneSelectionPage.tsx` | 用户菜单入口 |

### 后端文件

| 文件路径 | 功能描述 |
|---------|---------|
| `backend/app/api/v1/router.py` | API路由配置 |
| `backend/app/api/v1/endpoints/admin.py` | 管理员API端点 |
| `backend/app/api/v1/endpoints/categories.py` | 分类API端点 |
| `backend/app/api/v1/endpoints/contract_templates.py` | 合同模板API端点 |
| `backend/app/models/user.py` | 用户模型 |
| `backend/app/models/contract_template.py` | 合同模板模型 |

---

## 八、使用流程

### 1. 访问管理员后台

```
1. 用户登录系统
2. 点击右上角用户名
3. 在下拉菜单中选择"系统管理后台"（仅管理员可见）
4. 跳转到 /admin 页面
5. AdminPage 组件渲染
```

### 2. 数据仪表盘

```
1. 默认显示"数据仪表盘"标签
2. 调用 GET /api/v1/admin/stats 获取系统统计
3. 调用 GET /api/v1/admin/users 获取用户列表
4. 显示统计卡片和用户表格
```

### 3. 合同分类配置

```
1. 点击左侧"合同分类配置"标签
2. 显示13种标准合同类型统计
3. 计算每种类型的V2特征完整率
4. 点击"查看详情"查看该类型的所有模板
```

### 4. 模板管理

```
1. 点击左侧"模板管理"标签
2. 显示所有模板列表
3. 可以上传新模板、编辑V2特征、删除模板
4. 点击"V2特征"按钮打开编辑器
5. 保存后调用 PUT /api/v1/contract/{id}/v2-features
```

---

## 九、权限控制

### 前端权限

```typescript
// 仅管理员显示入口
{(user?.is_admin) && (
  <Menu.Item key="admin">系统管理后台</Menu.Item>
)}

// 页面级权限验证
useEffect(() => {
  if (user && !user.is_admin) {
    message.error('无权访问');
    navigate('/');
  }
}, [user, navigate]);
```

### 后端权限

```python
# 每个端点都验证管理员权限
if not current_user.is_admin:
    raise HTTPException(status_code=403, detail="仅管理员可访问")
```

---

## 十、V2特征管理核心功能

### 1. V2特征完整性统计

```typescript
// 检查V2特征是否完整
const isV2Complete = (template: ContractTemplate) => {
  return !!(
    template.transaction_nature &&
    template.contract_object &&
    template.complexity &&
    template.stance
  );
};

// 计算完整率
const completeCount = templates.filter(isV2Complete).length;
const incompleteCount = templates.length - completeCount;
const completionRate = (completeCount / templates.length) * 100;
```

### 2. V2特征可视化

```typescript
// 使用Tag显示V2特征
<Space size="small" wrap>
  <Tag color="geekblue">交易: {transaction_nature}</Tag>
  <Tag color="purple">标的: {contract_object}</Tag>
  <Tag color="orange">复杂度: {complexity}</Tag>
  <Tag color="cyan">立场: {stance}</Tag>
</Space>
```

### 3. V2特征编辑流程

```
1. 点击"V2特征"按钮
2. 打开 TemplateV2Editor 模态框
3. 加载当前模板的V2特征
4. 用户修改特征值
5. 点击"保存"
6. 调用API更新数据库
7. 刷新模板列表
```

---

## 总结

管理员后台系统由以下核心部分组成：

1. **入口**: 用户下拉菜单（仅管理员可见）
2. **路由**: `/admin` 路径
3. **主组件**: `AdminPage.tsx`
4. **三个功能标签**:
   - 数据仪表盘 (DashboardView)
   - 合同分类配置 (CategoryManagerView)
   - 模板管理 (TemplateManagerView)
5. **后端API**: `/api/v1/admin/*` 和 `/api/v1/contract/*`
6. **V2特征管理**: TemplateV2Editor 组件
7. **权限控制**: 前后端双重验证
