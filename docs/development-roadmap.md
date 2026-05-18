# 开工路线图

> 目标：先跑通“计划 → 工序任务 → 报工反馈”的最小闭环，不急着上复杂排产、SPC、设备采集。

## 第 0 步：项目准备

- [x] 放入 `lean-mes-builder` 规则：`SKILL.md`
- [x] 放入 MES 业务流程规则：`mes-business-flows.md`
- [x] 补充工单创建详细规格：`docs/work-order-creation.md`
- [x] 建立 FastAPI + Vue3 工程骨架
- [ ] 配置本机 Python 解释器
- [ ] 安装前后端依赖

## 第 1 步：数据模型

先建这些表，不扩散：

- `materials`
- `boms`
- `bom_lines`
- `routings`
- `routing_operations`
- `work_centers`
- `work_orders`
- `work_order_materials`
- `work_order_operations`
- `idempotency_keys`
- `audit_logs`

关键原则：

- 数量用 Decimal，不用 float。
- 所有业务表带 `tenant_id`。
- 业务实体软删除，流水不删除。
- 工单相关表保存物料、BOM、工艺路线、工位快照。

## 第 2 步：工单创建

参考 `docs/work-order-creation.md` 实现：

- `POST /api/v1/work-orders`
- 支持 `Idempotency-Key`
- 创建主工单
- 一层 BOM 展开到 `work_order_materials`
- 工艺路线拆分到 `work_order_operations`
- 写审计日志

## 第 3 步：工单查询

- `GET /api/v1/work-orders`
- `GET /api/v1/work-orders/{work_order_no}`

查询结果要能让计划员确认：

- 这张工单要做什么
- 需要哪些物料
- 要经过哪些工序
- 当前状态是什么

## 第 4 步：车间报工

先做最小闭环：

- 扫工序二维码进入操作页
- 开工
- 报工
- 写 `clock_records`
- 更新工序状态
- 推进下一道工序

报工接口必须幂等，前端要考虑离线重传。
