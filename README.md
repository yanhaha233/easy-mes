# Easy MES

Easy MES 是一个面向中小制造企业的精简 MES 项目。项目原则来自两份规则文档：

- `SKILL.md`：控制功能边界，避免把系统做成大型 MES。
- `mes-business-flows.md`：控制业务流程、状态机、报工、追溯等实现规则。

当前阶段先搭骨架，第一块业务从“工单创建：BOM 展开、工艺路线绑定、工序拆分”开始。

## 技术栈

| 层 | 选择 |
|----|------|
| 后端 | FastAPI + SQLAlchemy + PostgreSQL |
| 前端 | Vue3 + Vite + TypeScript |
| 管理端 UI | Element Plus |
| 缓存 | Redis（二期或需要幂等缓存时启用） |
| 部署 | Docker Compose |

## 目录结构

```text
easy-mes/
  backend/                 # FastAPI 后端
    app/
      api/v1/              # HTTP API
      core/                # 配置、基础能力
      db/                  # 数据库会话
      models/              # ORM 模型
      repositories/        # 数据访问
      schemas/             # Pydantic DTO
      services/            # 业务服务
    tests/
  frontend/                # Vue3 前端
    src/
      views/
      components/
      router/
      stores/
  docs/                    # 业务规格文档
```

## 后端启动

先确保本机安装 Python 3.12+，或在 PyCharm 中配置一个 Python 解释器。

先启动本地依赖服务：

```powershell
cd D:\code\easy-mes
docker compose up -d
```

PostgreSQL 暴露端口为 `15432`，Redis 暴露端口为 `16379`，用于避开本机常见端口占用。

```powershell
cd D:\code\easy-mes\backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\uvicorn app.main:app --reload --port 8010
```

健康检查：

```text
GET http://127.0.0.1:8010/api/v1/health
```

## 前端启动

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

## 开发顺序

1. 建核心数据表：物料、BOM、工艺路线、工单、工单物料、工单工序、幂等键、审计日志。
2. 实现工单创建接口。
3. 实现工单详情查询。
4. 实现基础档案的最小录入与列表。
5. 再进入齐套检查和报工。

任何新功能先对照 `SKILL.md` 判断是否应该做，再对照 `mes-business-flows.md` 判断业务如何流转。
