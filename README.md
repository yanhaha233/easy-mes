# Easy MES

Easy MES 是一个面向中小制造企业的精简 MES 项目。项目目标是先跑通“计划下达到工位、现场数据回收”的主流程，避免一开始就做成复杂的大型 MES。

## 技术栈

| 层 | 选择 |
| --- | --- |
| 后端 | FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | Vue3 + Vite + TypeScript |
| 管理端 UI | Element Plus |
| 缓存 | Redis，后续需要幂等缓存或队列时启用 |
| 部署 | Docker Compose |

## 目录结构

```text
easy-mes/
  backend/                 # FastAPI 后端
    app/
      api/v1/              # HTTP API
      core/                # 配置和默认值
      db/                  # 数据库会话
      models/              # ORM 模型
      schemas/             # Pydantic DTO
      services/            # 业务服务
      scripts/             # 本地运维和演示脚本
    tests/
  frontend/                # Vue3 前端
    src/
      api/
      router/
      types/
      views/
  docs/                    # 业务规格文档
```

## 本地启动

先启动 PostgreSQL 和 Redis：

```powershell
cd D:\code\easy-mes
docker compose up -d
```

PostgreSQL 暴露端口为 `15432`，Redis 暴露端口为 `16379`。

### 后端

```powershell
cd D:\code\easy-mes\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\uvicorn app.main:app --reload --port 8010
```

健康检查：

```text
GET http://127.0.0.1:8010/api/v1/health
```

### 前端

PowerShell 环境下优先使用 `npm.cmd`，避免执行策略拦截 `npm.ps1`。

```powershell
cd D:\code\easy-mes\frontend
npm.cmd install
npm.cmd run dev
```

前端默认地址：

```text
http://127.0.0.1:5180/
```

## 演示数据

数据库迁移完成后，可以写入一套默认计划员、操作员、质检员可直接使用的演示档案：

```powershell
cd D:\code\easy-mes\backend
.\.venv\Scripts\python -m app.scripts.seed_demo
```

脚本会创建：

- 演示物料、BOM、工艺路线
- CNC、去毛刺、质检工位
- A 班、默认计划员、默认操作员、默认质检员
- 划伤、尺寸超差、毛刺残留等不良原因
- `planner / planner123`、`operator / operator123`、`inspector / inspector123`、`admin / admin123` 四个演示账号
- 一张已确认并派工的演示工单

如果只想初始化基础档案，不创建演示工单：

```powershell
.\.venv\Scripts\python -m app.scripts.seed_demo --skip-work-order
```

## 自动校验

GitHub Actions 会在 `main` 分支 push 和 pull request 时执行：

- 后端依赖安装
- Alembic 数据库迁移
- `ruff check app tests`
- `pytest`
- 一条从基础档案到追溯查询的主流程集成测试
- 前端 `npm ci`
- 前端 `npm run build`

本地只跑快速单元测试：

```powershell
cd D:\code\easy-mes\backend
.\.venv\Scripts\python -m pytest
```

本地跑主流程集成测试时，需要先启动 PostgreSQL 并完成迁移：

```powershell
cd D:\code\easy-mes\backend
$env:EASY_MES_RUN_INTEGRATION="1"
.\.venv\Scripts\python -m pytest
```

## 开发原则

任何新功能先对照 `SKILL.md` 判断是否应该做，再对照 `mes-business-flows.md` 判断业务如何流转。当前阶段优先保证：

- 基础档案完整可录入
- 工单主流程能跑通
- 车间报工在手机竖屏下足够快
- 状态机、幂等键、审计日志、追溯链不被绕过
