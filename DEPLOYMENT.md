# 法律文档助手 - 部署指南

## 快速部署步骤

### 准备工作

1. **修改配置文件** - 打开 `.env` 文件，修改以下密码：
   ```bash
   POSTGRES_PASSWORD=your_secure_password
   SECRET_KEY=your_secret_key
   ONLYOFFICE_JWT_SECRET=your_jwt_secret
   ```

2. **修改上传脚本** - 编辑 `upload.bat` 或 `upload.sh`，填入服务器信息：
   ```bash
   SERVER_HOST=您的服务器IP
   SERVER_USER=root  # 或其他用户名
   ```

3. **修改部署脚本** - 编辑 `deploy.sh`，填入服务器 IP：
   ```bash
   SERVER_IP="您的服务器IP"
   ```

### 方式一：使用脚本上传并部署

#### Windows 用户（推荐）

1. **上传文件**
   - 双击运行 `upload.bat`
   - 或在 Git Bash 中运行 `bash upload.sh`

2. **连接服务器**
   - 打开 Termius
   - 连接到您的服务器

3. **执行部署**
   ```bash
   cd ~/legal-assistant
   bash deploy.sh
   ```

#### Termius SFTP 方式

1. 在 Termius 中右键连接 → "SFTP"
2. 上传以下文件/目录：
   - `backend/` (整个目录)
   - `frontend/` (整个目录)
   - `docker-compose.yml`
   - `.env`
   - `deploy.sh`

3. 在 Termius SSH 终端中：
   ```bash
   cd ~/legal-assistant
   chmod +x deploy.sh
   nano .env  # 修改密码配置
   bash deploy.sh
   ```

### 方式二：手动上传（使用 Termius）

1. 在 Termius 中建立 SFTP 连接
2. 拖拽以下文件夹到服务器：
   - `backend/`
   - `frontend/`
3. 上传文件：
   - `docker-compose.yml`
   - `.env`
   - `deploy.sh`

4. SSH 连接到服务器，执行：
   ```bash
   cd ~/legal-assistant
   chmod +x deploy.sh
   bash deploy.sh
   ```

---

## 部署后访问

部署成功后，可通过以下地址访问：

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端界面** | `http://服务器IP:3000` | 主应用入口 |
| **后端 API** | `http://服务器IP:8000` | API 接口 |
| **API 文档** | `http://服务器IP:8000/docs` | Swagger 文档 |
| **Celery 监控** | `http://服务器IP:5555` | 任务监控面板 |
| **ONLYOFFICE** | `http://服务器IP:8082` | 文档编辑器 |

---

## 常用管理命令

```bash
cd ~/legal-assistant

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 重启服务
docker-compose restart

# 重启特定服务
docker-compose restart backend

# 停止所有服务
docker-compose down

# 停止并删除数据卷
docker-compose down -v

# 进入后端容器
docker-compose exec backend bash

# 进入数据库
docker-compose exec db psql -U admin -d legal_assistant_db

# 查看资源使用
docker stats
```

---

## 故障排查

### 问题 1: 容器启动失败

```bash
# 查看详细日志
docker-compose logs backend
docker-compose logs frontend

# 重建并重启
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### 问题 2: 数据库连接失败

```bash
# 检查数据库容器
docker-compose ps db

# 查看数据库日志
docker-compose logs db

# 手动连接测试
docker-compose exec db psql -U admin -d legal_assistant_db
```

### 问题 3: 无法访问前端

```bash
# 检查前端容器
docker-compose ps frontend

# 查看前端日志
docker-compose logs frontend

# 检查 Nginx 配置
docker-compose exec frontend cat /etc/nginx/conf.d/default.conf
```

### 问题 4: AI 模型调用失败

```bash
# 进入后端容器测试
docker-compose exec backend bash

# 测试 API 连通性
curl -v https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1/models

# 检查环境变量
docker-compose exec backend env | grep API
```

---

## 数据备份

```bash
# 创建备份脚本
cat > ~/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR=~/backups
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR

# 备份数据库
docker-compose exec -T db pg_dump -U admin legal_assistant_db > $BACKUP_DIR/db_$DATE.sql

# 压缩备份
gzip $BACKUP_DIR/db_$DATE.sql

# 删除 30 天前的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete
EOF

chmod +x ~/backup.sh

# 手动备份
~/backup.sh

# 添加定时任务（每天凌晨 2 点备份）
crontab -e
0 2 * * * ~/backup.sh
```

---

## 更新部署

当代码有更新时：

```bash
cd ~/legal-assistant

# 1. 上传更新的文件
# 使用 upload.bat 或 Termius SFTP

# 2. 重建镜像
docker-compose build

# 3. 重启服务
docker-compose up -d

# 4. 运行数据库迁移（如有更新）
docker-compose exec backend alembic upgrade head
```

---

## 文件清单

部署所需的核心文件：

```
legal_document_assistant v3/
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/          # 应用代码
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/          # 前端代码
├── docker-compose.yml
├── .env
├── deploy.sh         # 部署脚本
├── upload.sh         # Linux/Mac 上传脚本
└── upload.bat        # Windows 上传脚本
```
