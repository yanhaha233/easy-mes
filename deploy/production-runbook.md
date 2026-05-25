# Easy MES 生产级 MVP 运维手册

目标环境：一台厂内服务器或云主机，Docker Compose 部署 PostgreSQL、Redis、后端和前端。适用于 1 个试点工厂、少量计划员和车间操作员的 MVP。

## 1. 上线前准备

1. 准备服务器，安装 Docker 和 Docker Compose。
2. 复制配置模板：

```powershell
Copy-Item deploy\.env.production.example .env.prod
```

3. 修改 `.env.prod`：

| 变量 | 要求 |
| --- | --- |
| `POSTGRES_PASSWORD` | 生产库密码，不使用模板值 |
| `AUTH_SECRET_KEY` | 长随机字符串，不能使用本地默认值 |
| `CORS_ORIGINS` | 前端访问地址，例如 `http://192.168.1.10:8080` |
| `ERP_INTEGRATION_API_KEY` | 不接 ERP 时留空；接 ERP 时设置共享密钥 |

## 2. 首次部署

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

后端容器启动时会自动执行 `alembic upgrade head`。首次部署完成后执行 smoke check：

```powershell
cd backend
python -m app.scripts.smoke_check --base-url http://127.0.0.1:8080
```

如果需要演示档案和演示账号：

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml exec backend python -m app.scripts.seed_demo
```

正式试点建议只初始化基础档案，不生成演示工单：

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml exec backend python -m app.scripts.seed_demo --skip-work-order
```

## 3. 日常检查

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs --tail 100 backend
```

健康检查：

```text
GET http://<host>:8080/api/v1/health
GET http://<host>:8080/api/v1/health/ready
```

`/health/ready` 失败时先看 PostgreSQL 容器是否健康，再查后端日志中的 `request_id` / `trace_id`。

## 4. 备份与恢复

上线后每天至少备份一次数据库。备份文件必须复制到服务器外部位置。

```powershell
New-Item -ItemType Directory -Force backups
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T postgres pg_dump -U easy_mes -d easy_mes -Fc > backups\easy_mes_$(Get-Date -Format yyyyMMdd_HHmmss).dump
```

恢复前必须停前后端，避免恢复过程中继续写入：

```powershell
docker compose --env-file .env.prod -f docker-compose.prod.yml stop frontend backend
docker compose --env-file .env.prod -f docker-compose.prod.yml cp backups\<backup-file>.dump postgres:/tmp/easy_mes_restore.dump
docker compose --env-file .env.prod -f docker-compose.prod.yml exec postgres pg_restore -U easy_mes -d easy_mes --clean --if-exists /tmp/easy_mes_restore.dump
docker compose --env-file .env.prod -f docker-compose.prod.yml exec postgres rm -f /tmp/easy_mes_restore.dump
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
```

## 5. 发布与回滚

发布前：

```powershell
git pull
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
cd backend
python -m app.scripts.smoke_check --base-url http://127.0.0.1:8080
cd ..
```

回滚原则：

1. 先确认是否有数据库迁移。只改前端或后端代码时，直接切回上一 commit 重建镜像。
2. 如果已经执行了不可逆迁移，先恢复上线前数据库备份，再切回上一 commit。
3. 回滚后必须跑 smoke check，并抽查登录、工单列表、报工、追溯。

示例：

```powershell
git log --oneline -5
git checkout <last-good-commit>
docker compose --env-file .env.prod -f docker-compose.prod.yml build
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d
cd backend
python -m app.scripts.smoke_check --base-url http://127.0.0.1:8080
```

## 6. ERP 轻量接入与回传

不接 ERP 时，计划员用页面新建或 Excel/CSV 导入工单。接 ERP 时只接两件事：

1. ERP 推送工单到 `POST /api/v1/integrations/erp/work-orders`。
2. MES 完工入库后生成本地回传记录，ERP 拉取 `GET /api/v1/integrations/erp/work-order-feedback?status=pending`，成功后调用 ack。

如果 ERP 暂时回传不了，`erp_work_order_feedbacks` 会保留待回传记录。运维人员可定期查询 pending 记录，确认外部系统恢复后再补传。

## 7. 试点验收

试点第一周只验收主流程：

1. 基础档案：物料、BOM、工艺路线、工位、人员、工序权限。
2. 计划下达：手工新建、Excel/CSV 导入、可选 ERP 工单推送。
3. 派工与报工：操作员只能看到自己能做的工序，报工后状态推进正确。
4. 质检停线：巡检不合格能暂停工单，恢复后继续报工。
5. 完工入库：工单关闭，ERP 来源工单生成本地回传记录。
6. 追溯：能按工单看到创建、派工、报工、质检、入库流水。

试点反馈按严重程度处理：阻断生产当天修；影响效率一周内修；报表和体验优化进入下一轮。
