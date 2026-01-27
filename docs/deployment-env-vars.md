# 部署环境变量配置

本文档说明了部署法律助手应用时需要配置的环境变量。

---

## 必需配置

### 管理员账户

在首次部署时，应用会自动创建管理员用户。需要配置以下环境变量：

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `DEFAULT_ADMIN_EMAIL` | 管理员邮箱地址（main.py 使用） | `admin@yourdomain.com` |
| `DEFAULT_ADMIN_PASSWORD` | 管理员密码（至少8位） | `YourSecurePassword123!` |
| `SEED_ADMIN_EMAIL` | 管理员邮箱地址（seed 脚本使用，与上面保持一致） | `admin@yourdomain.com` |
| `SEED_ADMIN_PASSWORD` | 管理员密码（seed 脚本使用，与上面保持一致） | `YourSecurePassword123!` |

> **注意**: 需要同时配置两组变量（`DEFAULT_ADMIN_*` 和 `SEED_ADMIN_*`），确保两者的邮箱和密码保持一致。

**示例**:
```bash
export DEFAULT_ADMIN_EMAIL="admin@yourdomain.com"
export DEFAULT_ADMIN_PASSWORD="YourSecurePassword123!"
export SEED_ADMIN_EMAIL="admin@yourdomain.com"
export SEED_ADMIN_PASSWORD="YourSecurePassword123!"
```

**安全建议**:
- 使用强密码（至少8位，包含大小写字母、数字和特殊字符）
- 首次登录后立即修改密码
- 不要在代码中硬编码密码

### 数据库配置

应用使用 PostgreSQL 作为数据库。

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `DATABASE_URL` | PostgreSQL 连接字符串 | `postgresql://user:pass@host:5432/dbname` |
| `POSTGRES_SERVER` | 数据库服务器地址 | `localhost` |
| `POSTGRES_PORT` | 数据库端口 | `5432` |
| `POSTGRES_USER` | 数据库用户名 | `postgres` |
| `POSTGRES_PASSWORD` | 数据库密码 | `your_password` |
| `POSTGRES_DB` | 数据库名称 | `legal_assistant_db` |

**示例**:
```bash
export DATABASE_URL="postgresql://postgres:password@localhost:5432/legal_assistant_db"
```

---

## 可选配置

### 环境标识

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ENVIRONMENT` | 环境类型 | `development` |
|  | 可选值: `production`, `staging`, `development` |  |

**示例**:
```bash
export ENVIRONMENT="production"
```

### 安全配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `SECRET_KEY` | JWT 密钥（自动生成） | - |
| `ALLOWED_HOSTS` | 允许的主机列表 | `localhost,127.0.0.1` |
| `FRONTEND_PUBLIC_URL` | 前端访问地址（用于飞书通知跳转） | `http://localhost:5173` |
| `ALLOWED_ORIGINS` | 额外的 CORS 允许源（逗号分隔） | - |

> **FRONTEND_PUBLIC_URL 说明**: 此地址用于飞书通知中的"查看审查结果"链接跳转。如果配置了飞书集成，需要设置为实际的前端访问地址。

**示例**:
```bash
export SECRET_KEY="your_generated_secret_key"
export FRONTEND_PUBLIC_URL="https://your-frontend-domain.com"
export ALLOWED_ORIGINS="https://app1.example.com,https://app2.example.com"
```

**生成 JWT 密钥**:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### LLM 配置

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-...` |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI 密钥 | `your_key` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI 端点 | `https://...` |

### Redis 配置（Celery 异步任务）

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `REDIS_URL` | Redis 连接字符串 | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery Broker URL | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery 结果后端 | `redis://localhost:6379/0` |
| `CELERY_ENABLED` | 启用 Celery | `true` |

### 飞书集成（可选）

| 环境变量 | 说明 | 示例 |
|---------|------|------|
| `FEISHU_APP_ID` | 飞书应用 ID | `cli_...` |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | `your_secret` |
| `FEISHU_VERIFY_TOKEN` | 飞书验证令牌 | `your_token` |
| `FEISHU_ENCRYPT_KEY` | 飞书加密密钥 | `your_key` |

---

## Docker Compose 配置示例

### docker-compose.production.yml

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      # 管理员账户（必需 - 需要同时配置两组）
      - DEFAULT_ADMIN_EMAIL=${DEFAULT_ADMIN_EMAIL}
      - DEFAULT_ADMIN_PASSWORD=${DEFAULT_ADMIN_PASSWORD}
      - SEED_ADMIN_EMAIL=${SEED_ADMIN_EMAIL}
      - SEED_ADMIN_PASSWORD=${SEED_ADMIN_PASSWORD}

      # 数据库
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - POSTGRES_SERVER=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}

      # 环境标识
      - ENVIRONMENT=production

      # LLM 配置
      - OPENAI_API_KEY=${OPENAI_API_KEY}

      # 安全
      - SECRET_KEY=${SECRET_KEY}
      - ALLOWED_HOSTS=${ALLOWED_HOSTS}

    depends_on:
      - postgres
      - redis
```

### .env 文件

```bash
# 管理员账户（两组变量，保持一致）
DEFAULT_ADMIN_EMAIL=admin@yourdomain.com
DEFAULT_ADMIN_PASSWORD=YourSecurePassword123!
SEED_ADMIN_EMAIL=admin@yourdomain.com
SEED_ADMIN_PASSWORD=YourSecurePassword123!

# 数据库
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DB=legal_assistant_db

# 安全
SECRET_KEY=your_generated_secret_key_here
ALLOWED_HOSTS=yourdomain.com,localhost

# LLM（可选）
OPENAI_API_KEY=sk-your-api-key-here
```

---

## 部署验证

部署后，通过以下方式验证配置是否正确：

### 1. 检查健康状态

```bash
curl http://your-server/health
```

### 2. 检查数据初始化日志

```bash
docker-compose logs backend | grep -E "(seed|init)"
```

应该看到类似输出：
```
[Seed] Starting production data seeding...
[Seed] Step 1/5: Checking admin user...
[Seed] ✓ Admin user created: admin@yourdomain.com
[Seed] Step 2/5: Initializing review rules...
...
[Seed] Production data seeding completed!
```

### 3. 尝试登录管理员账户

- 访问: `http://your-server/`
- 邮箱: `<SEED_ADMIN_EMAIL>`
- 密码: `<SEED_ADMIN_PASSWORD>`

### 4. 验证数据已导入

管理员登录后，检查：
- 审查规则应有48条（系统规则）
- 风险评估规则应有若干条
- 案件分析包应有6个
- 知识图谱应有127种合同类型

---

## 故障排查

### 管理员未创建

**症状**: 无法使用配置的管理员账户登录

**检查**:
```bash
# 查看日志
docker-compose logs backend | grep "seed\|admin"

# 检查环境变量
docker-compose exec backend env | grep -E "(DEFAULT_ADMIN|SEED_ADMIN)"
```

**解决**: 确保同时设置了 `DEFAULT_ADMIN_EMAIL/PASSWORD` 和 `SEED_ADMIN_EMAIL/PASSWORD`，且两者的值保持一致。

### 规则未导入

**症状**: 审查功能显示"规则为0"

**检查**:
```bash
# 检查数据库
docker-compose exec backend python -c "
from app.database import SessionLocal
from app.models.rule import ReviewRule
db = SessionLocal()
print(f'规则数: {db.query(ReviewRule).count()}')
"
```

**解决**: 手动运行初始化脚本
```bash
docker exec -it <backend_container> python scripts/seed_production_data.py
```

### 数据库连接失败

**症状**: 应用启动时提示数据库连接错误

**检查**:
```bash
# 检查数据库是否运行
docker-compose ps postgres

# 检查数据库连接字符串
docker-compose exec backend env | grep DATABASE_URL
```

**解决**: 确保 PostgreSQL 容器正在运行，且连接字符串正确

---

## 安全建议

1. **使用强密码**: 管理员密码至少8位，包含大小写字母、数字和特殊字符
2. **首次登录修改密码**: 首次登录后立即修改默认密码
3. **使用密钥管理**: 考虑使用 AWS Secrets Manager、Azure Key Vault 等服务
4. **限制文件权限**: 确保 .env 文件权限为 600
5. **定期更新密码**: 定期更新管理员密码和数据库密码
6. **启用 HTTPS**: 生产环境必须启用 HTTPS
7. **配置防火墙**: 限制数据库端口的访问

---

## 相关文档

- [本地配置修改说明](./本地配置修改说明.md)
- [本地测试方法](./本地测试方法.md)
- [飞书集成代码说明](./飞书集成代码说明.md)
