# pgvector 集成测试指南

## 测试结果总结

根据当前测试运行情况,发现以下问题需要解决:

### 1. 数据库连接问题

**错误**: `could not translate host name "db" to address`

**原因**: `.env` 文件中的 `POSTGRES_SERVER=db` 使用的是 Docker 容器名称,本地测试时无法解析。

**解决方案**:

修改 `.env` 文件中的数据库配置:

```bash
# Docker 环境 (当前)
POSTGRES_SERVER=db
DATABASE_URL=postgresql://admin:01689101Abc@db:5432/legal_assistant_db

# 本地测试环境 (修改为)
POSTGRES_SERVER=localhost
# 或者
POSTGRES_SERVER=127.0.0.1

DATABASE_URL=postgresql://admin:01689101Abc@localhost:5432/legal_assistant_db
```

### 2. BGE 服务连接问题

**错误**: `[WinError 10060] 连接超时`

**原因**: BGE 嵌入服务 `115.190.43.141:11434` 无法访问。

**解决方案**:

#### 选项 1: 检查网络连接
```bash
# 测试 BGE 服务是否可达
curl http://115.190.43.141:11434/api/embed

# 如果在公司内网,确保 VPN 已连接
# 如果服务需要认证,检查 API 配置
```

#### 选项 2: 使用本地 BGE 服务

如果公司 BGE 服务不可用,可以搭建本地 BGE 服务:

```bash
# 使用 Docker 运行 BGE-M3 服务
docker pull qdrant/bge-m3:latest
docker run -p 11434:11434 qdrant/bge-m3
```

然后修改 `.env`:
```bash
BGE_EMBEDDING_API_URL=http://localhost:11434/api/embed
```

#### 选项 3: 跳过 BGE 测试

如果暂时无法访问 BGE 服务,可以修改测试脚本跳过相关测试:

```python
# 在 test_pgvector_integration.py 中注释掉
# self.test_bge_service()
# self.test_vector_search()
# self.test_template_retriever()
```

### 3. 执行数据库迁移

在测试之前,需要先执行数据库迁移:

```bash
cd backend

# 1. 确认 pgvector 扩展已安装
psql -U admin -d legal_assistant_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

# 2. 运行 Alembic 迁移
alembic upgrade head
```

### 4. 完整测试步骤

#### 步骤 1: 配置环境变量

修改 `.env`:
```bash
# 本地测试使用 localhost
POSTGRES_SERVER=localhost
DATABASE_URL=postgresql://admin:password@localhost:5432/legal_assistant_db

# 确认 BGE 服务配置
BGE_EMBEDDING_API_URL=http://115.190.43.141:11434/api/embed
```

#### 步骤 2: 安装 pgvector 扩展

```bash
# 连接到 PostgreSQL
psql -U admin -d legal_assistant_db

# 安装 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

# 验证安装
\dx
# 应该看到 vector 扩展
```

#### 步骤 3: 运行数据库迁移

```bash
cd backend
alembic upgrade head
```

预期输出:
```
Running upgrade 20260118_add_case_overview -> 20260119_add_pgvector_support
```

#### 步骤 4: 运行集成测试

```bash
cd backend
python test_pgvector_integration.py
```

### 5. 预期测试结果

所有测试通过时的输出:

```
============================================================
测试摘要
============================================================
总测试数: 7
通过: 7
失败: 0
通过率: 100.0%
============================================================

详细结果:
  [PASS] pgvector 扩展检查: pgvector 扩展已安装
  [PASS] embedding 字段检查: 所有字段存在
  [PASS] HNSW 索引检查: HNSW 索引已创建
  [PASS] BGE 嵌入服务: BGE 服务正常, 嵌入维度: 1024
  [PASS] PgVectorStore 初始化: 总模板: 0, 已索引: 0, 覆盖率: N/A
  [PASS] 向量相似度搜索: 搜索返回 0 个结果
  [PASS] TemplateRetriever 检索: 检索返回 0 个结果
============================================================

所有测试通过! pgvector 集成正常工作。

下一步:
  1. 在 router.py 中启用 RAG 路由
  2. 运行数据迁移脚本为现有模板生成向量
  3. 测试前端智能搜索功能
```

### 6. 故障排除

#### 问题 1: pgvector 扩展未安装

```bash
# 错误: 缺少字段: embedding
# 解决: 安装 pgvector 扩展
psql -U admin -d legal_assistant_db -c "CREATE EXTENSION vector;"
```

#### 问题 2: 字段缺失

```bash
# 错误: 缺少字段: embedding, embedding_updated_at, embedding_text_hash
# 解决: 运行数据库迁移
cd backend
alembic upgrade head
```

#### 问题 3: BGE 服务超时

```bash
# 错误: BGE 服务异常: [WinError 10060] 连接超时
# 解决: 检查网络连接或使用本地 BGE 服务
curl http://115.190.43.141:11434/api/embed

# 或者修改配置使用其他嵌入服务
```

#### 问题 4: Docker 环境问题

如果在 Docker 环境中测试,确保:

1. PostgreSQL 容器正在运行
2. 已安装 pgvector 扩展到容器中
3. 网络配置正确

```bash
# 在 PostgreSQL 容器中安装 pgvector
docker exec -it <postgres_container> bash
apt-get update && apt-get install -y postgresql-14-pgvector
psql -U admin -d legal_assistant_db -c "CREATE EXTENSION vector;"
```

### 7. 下一步操作

测试通过后,按以下顺序执行:

1. **启用 RAG 路由** (在 `router.py` 中取消注释)
2. **修改上传接口** (添加向量生成逻辑)
3. **创建数据迁移脚本** (为现有模板生成向量)
4. **运行数据迁移** (批量为模板生成向量)
5. **前端测试** (验证智能搜索功能)

## 相关文件

- 测试脚本: `backend/test_pgvector_integration.py`
- 配置文件: `backend/.env`
- 迁移脚本: `backend/alembic/versions/20260119_add_pgvector_support.py`
- pgvector 服务: `backend/app/services/contract_generation/rag/pgvector_store.py`
