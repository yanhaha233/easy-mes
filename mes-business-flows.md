---
name: mes-business-flows
description: 中小型 MES 系统的核心业务流程定义。当用户要求实现具体 MES 功能——工单管理、齐套检查、排产派工、车间报工、领发料、质量检验、完工入库、追溯查询、OEE 计算时使用本技能。本技能与 lean-mes-builder 配套：lean-mes-builder 管"做不做、怎么不做"，本技能管"做的时候业务怎么转"。任何涉及"工单状态机"、"报工接口"、"齐套算法"、"BOM 反冲"、"线边库"、"工艺路线"、"工序流转"、"质量三检"、"追溯链"的实现请求都应主动触发本技能。
---

# MES 核心业务流程定义

> 本技能配合 lean-mes-builder 使用。lean-mes-builder 决定"做什么、不做什么"，本技能决定"做的事情业务上怎么转"。AI 编码代理在生成具体业务代码前必须读本技能。

---

## 一、概念词典（先统一术语）

写代码前确认你理解了下面这些词。中小厂客户的口语化表达和系统术语经常有出入，但内部命名必须统一：

| 系统术语 | 客户口语 | 含义 |
|---------|---------|------|
| 工单 / 生产订单 | 派工单、生产单、工作单 | 一个生产任务的凭证，对应 ERP 的销售订单或主生产计划 |
| 工序 (operation) | 工步、道序、工艺步 | 工单的子任务，对应工艺路线中的一个步骤 |
| 工艺路线 (routing) | 工艺、流程、路线 | 物料的生产路径定义，包含工序序列、工位、标准工时 |
| 工位 (work center) | 工位、岗位、机台 | 物理作业地点，可能是单台设备也可能是一组设备 |
| 标准工时 (std time) | 节拍、标工 | 完成一道工序的标准时间，分准备工时+加工工时 |
| 报工 (clock-in/out) | 报产、打卡、记产 | 工人完成一道工序后录入产量和质量数据 |
| 转序 (move to next op) | 转下道、流转 | 把半成品从当前工位移交到下一个工位 |
| WIP (work in progress) | 在制品、半成品 | 工序之间流转的未完成产品 |
| 齐套 (kitting) | 配料、齐料、备料 | 工单所需所有物料是否库存齐全 |
| BOM 反冲 (backflush) | 倒冲、自动扣料 | 报工时自动按 BOM 扣减原材料库存 |
| 换型 (changeover) | 换模、换线、切型 | 设备从生产 A 切换到 B 的调整 |
| 首件 (first article) | 首件、头件 | 批量生产的第一件，需单独检验 |
| OEE | 综合效率、稼动率 | 设备综合效率 = 时间稼动 × 性能 × 良率 |

**术语锁定原则**：代码里、数据库字段里、API 命名里都用系统术语（左列）。客户口语在 UI 文案和文档里翻译适配，不污染代码层。

---

## 二、工单状态机

工单是 MES 最重要的实体，状态机必须严格定义。任何不合法的状态转换都要拒绝。

### 工单主表状态机

```
            ┌─────────┐
            │  draft  │  草稿 (手工创建未确认)
            └────┬────┘
                 │ confirm
                 ↓
            ┌─────────┐
            │ pending │  待排产 (已确认未排产)
            └────┬────┘
                 │ schedule
                 ↓
            ┌─────────┐
            │scheduled│  已排产 (有派工记录未开工)
            └────┬────┘
                 │ start (任一工序开工)
                 ↓
            ┌─────────┐
   ┌────────┤in_progress├────────┐  进行中
   │ pause  └────┬────┘  resume  │
   │             │               │
   ↓             │               ↑
┌──────┐         │ all_done   ┌──────┐
│paused│         ↓            │paused│
└──┬───┘    ┌─────────┐       └──────┘
   │ resume │completed│  全部工序完成
   └────────┘ └────┬───┘
                   │ close
                   ↓
              ┌─────────┐
              │ closed  │  关单 (入库+财务确认)
              └─────────┘

特殊路径:
  任何状态 -- cancel --> cancelled  (取消, 需权限)
```

**实现要点**：
- 状态转换接口要做严格校验，非法转换返回 400 并说明当前状态
- 状态变更必须留审计日志（who, when, from, to, reason）
- `cancel` 操作需要权限控制，并且要级联取消所有未完成的工序任务

### 工序任务状态机（工单的子级）

```
pending → ready → in_progress → reporting → done
                       ↓
                    paused → resume
                       ↓
                    cancelled
```

- `ready`：物料已齐套，可以扫码开工
- `in_progress`：已扫码开工，未报工
- `reporting`：报工中（界面打开但未提交，可选）
- `done`：完工报工已确认

**关键约束**：
- 工序 N+1 只有在工序 N 状态为 `done` 时才能进入 `ready`（除非工艺路线允许并行）
- 工单整体的 `completed` 状态由所有工序任务都 `done` 触发

---

## 三、核心流程详解

### 3.1 工单创建流程

**触发**：ERP 同步 / 计划员手工创建

**步骤**：

```
1. 接收输入: {物料编码, 数量, 交期, 客户?, 优先级?, 关联销售订单号?}
2. 校验:
   - 物料档案是否存在
   - 物料是否有激活的工艺路线
   - 数量 > 0
3. 工单主表写入 (status=draft 或 pending)
4. 展开 BOM:
   - 按物料的当前激活 BOM 计算所需子件数量
   - 写入 work_order_materials 表
5. 展开工艺路线:
   - 按物料的当前激活 routing 拆分工序
   - 每道工序写入 work_order_ops 表 (含工位、标准工时、序号)
6. 若来自 ERP: 状态直接到 pending
   若手工创建: 留在 draft, 等待确认
```

**接口契约示例**：

```http
POST /api/v1/work-orders
{
  "material_code": "P-001",
  "quantity": 100,
  "due_date": "2026-06-01",
  "priority": "normal",
  "source": "manual",
  "external_ref": "SO-2026-0001",
  "remark": ""
}

Response 201:
{
  "work_order_no": "WO-202605-0001",
  "status": "draft",
  "operations": [
    {"seq": 10, "work_center": "WC-CNC-01", "std_time_sec": 1800, "status": "pending"},
    {"seq": 20, "work_center": "WC-DEBURR-01", "std_time_sec": 600, "status": "pending"},
    {"seq": 30, "work_center": "WC-QC-01", "std_time_sec": 300, "status": "pending"}
  ],
  "materials_required": [...]
}
```

**注意事项**：
- 工单号生成规则：`WO-YYYYMM-NNNN`，月内序号递增
- 工艺路线可能有多个版本，要明确取"当前激活版本"
- BOM 展开只做一层，多层在领料阶段递归（避免一次性数据爆炸）

### 3.2 齐套检查流程

齐套是 MES 调用 WMS 的关键交互。

**逻辑**：

```
输入: work_order_no

1. 查询 work_order_materials, 得到所需物料清单
2. 对每个物料:
   - 调用 WMS 接口查询当前可用库存 (扣除已锁定)
   - 计算: 缺口 = 需求量 - 可用量
3. 汇总:
   - 全部缺口为 0 → 齐套, 状态可转 scheduled
   - 有任意缺口 > 0 → 不齐套, 返回缺料清单
4. 可选: 调用 WMS 进行预锁定 (将所需量从"可用"转为"已分配")
```

**模式 A vs 模式 B 影响**：

- 模式 A（线边库归 WMS）：齐套检查只查主仓 + 线边库（如果允许跨库取料）
- 模式 B（线边库归 MES）：齐套检查只查 WMS 主仓（线边库 MES 自己管，不参与齐套）

**接口契约示例**：

```http
POST /api/v1/work-orders/{wo_no}/kitting-check
Response 200:
{
  "work_order_no": "WO-202605-0001",
  "is_complete": false,
  "shortage": [
    {
      "material_code": "M-A001",
      "required_qty": 100,
      "available_qty": 60,
      "shortage_qty": 40,
      "expected_arrival": "2026-05-20"
    }
  ],
  "checked_at": "2026-05-17T10:23:45Z"
}
```

**异常路径**：
- WMS 接口超时 → 不自动判齐套, 标记为"齐套检查失败"
- 部分齐套是否允许下产线：业务策略, 默认不允许, 但留 override 开关

### 3.3 排产派工流程

中小厂不要做复杂 APS，规则越简单越好。

**简单规则排产逻辑**：

```
1. 取所有 status=pending 或 scheduled 且 is_kitted=true 的工单
2. 按优先级 (urgent > high > normal) + 交期 (升序) 排序
3. 遍历工单, 对每道工序:
   - 找到该工序的 work_center 当前最早可用时间
   - 按 std_time × 数量 计算占用时长
   - 占用该时段, 写入 schedule_slots
4. 计划员可在甘特图上拖拽调整顺序, 系统重新计算后续时间
```

**派工**：排产完成后, 当前时段对应的工序任务状态从 `pending` 改为 `ready`, 等待工位扫码。

**约束检查**（拖拽时必须满足）：
- 同一工位同一时间只能有一个工序占用
- 工序 N+1 的开始时间必须 >= 工序 N 的结束时间（同一工单）
- 不能排到已停机的设备

**禁止做的事**：
- 不要做遗传算法、模拟退火等高级排程
- 不要尝试自动优化"换型成本"——靠计划员的经验
- 不要做实时滚动重排——每次拖拽只重算受影响的工序

### 3.4 工序执行与报工流程

这是 MES 最高频的操作，必须 10 秒内完成。

**完整微循环**：

```
A. 工人到达工位
   ↓
B. 扫工单二维码 (或工序卡条码)
   - 系统检查: 这道工序是 ready 状态吗?
   - 系统检查: 这个工人有这个工位的权限吗?
   ↓
C. 显示工序信息: 物料、数量、工艺要求、上道工序产出
   ↓
D. (可选) 领料确认
   - 模式 A: 调用 WMS 出库接口, 从线边库扣减
   - 模式 B: 仅在 MES 内记录用料
   ↓
E. (可选) 首件检验
   - 第一件做完后, 由 QC 确认合格才能继续批量
   ↓
F. 点击"开工" → 工序状态转 in_progress
   ↓
G. 加工过程 (MES 不介入, 除非有传感器自动采集)
   ↓
H. 点击"报工"
   - 录入: 合格数, 不良数, 不良原因 (多选)
   - 录入: 实际用料数量 (如果与 BOM 不一致)
   - 自动: 用时计算 = 报工时间 - 开工时间
   ↓
I. 系统写入 clock_record (报工流水)
   ↓
J. 系统更新:
   - work_order_ops.status = done
   - work_order.actual_qty += 合格数
   - 若有 BOM 反冲: 更新物料库存 (模式 A 调 WMS, 模式 B 内部)
   - 若所有工序 done: work_order.status = completed
   - 否则: 下一道工序 status = ready
```

**报工接口契约**：

```http
POST /api/v1/operations/{op_id}/clock
Idempotency-Key: <uuid-from-client>
{
  "good_qty": 95,
  "bad_qty": 5,
  "defects": [
    {"reason_code": "D-SCRATCH", "qty": 3},
    {"reason_code": "D-DIMENSION", "qty": 2}
  ],
  "actual_materials": [
    {"material_code": "M-A001", "qty": 100, "lot_no": "LOT-2026051701"}
  ],
  "operator_id": "W-0102",
  "remark": ""
}
```

**关键约束**：
- `good_qty + bad_qty` 必须 > 0
- `defects` 总数必须 = `bad_qty`
- `Idempotency-Key` 是必须的，幂等键服务端缓存 24 小时
- 接口响应时间 SLA: < 500ms (因为车间网络可能慢)

**离线场景**：
- 工位平板支持离线缓存报工数据
- 网络恢复后按时间戳顺序上送
- 服务端用 idempotency-key + (op_id, operator_id, client_timestamp) 复合去重

### 3.5 质量三检流程

三检 = 首件 + 巡检 + 终检。每一种触发时机和流程都不同。

**首件检验**：

```
触发: 每批工单的第一件加工完成
流程: 工人扫码"首件送检" → QC 检验 → 合格才能继续批量
失败处理: 调机、再做一件、再检, 直到合格
数据: 写 quality_records (type=first_article)
```

**过程巡检**：

```
触发: 按工艺路线定义的频次 (例: 每 30 分钟 / 每 50 件)
流程: 系统提醒 QC 巡检 → QC 抽样检验 → 记录结果
失败处理: 不合格立即停线, 工序状态 → paused
数据: 写 quality_records (type=patrol_inspection)
```

**终检**：

```
触发: 工序全部完成
流程: QC 按抽检标准抽样 → 检验 → 判合格/不合格/让步接收
失败处理:
  - 全检不合格: 走返修流程 (新建返修工单, 引用原工单)
  - 部分不合格: 拆分入库 (合格品入主仓, 不合格品入隔离仓)
数据: 写 quality_records (type=final_inspection)
```

**不良处置**：

```
不良品的去向有 4 种, 必须明确:
1. 返修 (rework): 走返修工单, 修复后重新检验
2. 让步接收 (concession): 经客户/工程师批准, 标记降级品入库
3. 报废 (scrap): 直接报废, 记录原因
4. 退料 (return-to-vendor): 若是来料不良, 退给供应商 (走 WMS 退货)
```

### 3.6 追溯链构建

追溯的核心是"事件流水关联实体快照"。

**追溯数据模型**：

```
clock_record (每次报工的核心流水)
├── work_order_no       (工单)
├── operation_seq       (工序号)
├── work_center_id      (工位)
├── equipment_id        (设备, 可为空)
├── operator_id         (操作员)
├── shift_team_id       (班组, 可为空)
├── started_at          (开工时间)
├── ended_at            (报工时间)
├── good_qty            (合格数)
├── bad_qty             (不良数)
├── defects[]           (不良明细)
└── material_consumed[] (用料明细, 含批次号 lot_no)

quality_records (质量检验流水)
├── work_order_no
├── operation_seq
├── inspector_id
├── inspect_type        (first_article | patrol | final)
├── sample_qty
├── pass_qty
├── fail_qty
└── result              (pass | fail | concession)

equipment_events (设备状态流水, 可选)
├── equipment_id
├── event_type          (run | idle | down | setup)
├── started_at
└── ended_at
```

**追溯查询**：

```
正向追溯 (从工单查所有事件):
  GET /api/v1/work-orders/{wo_no}/traceability
  → 返回所有相关 clock_records, quality_records, equipment_events
  按时间排序

反向追溯 (从批次查问题工单):
  GET /api/v1/materials/lots/{lot_no}/traceability
  → 返回使用了该批次的所有 clock_records, 进而关联工单

横向追溯 (同一设备/操作员/批次出过的所有问题):
  GET /api/v1/traceability/cross-cut?dimension=equipment&id=EQ-001&from=...&to=...
```

**实现要点**：
- 流水表只追加不更新, 写入后不可修改
- 关联实体如果可能变更 (如工位重命名), 流水里冗余存储当时的快照名称
- 流水表数据量大, 按月分表或用时序数据库

### 3.7 OEE 计算

OEE 是设备综合效率, 但中小厂用简化口径即可。

**简化 OEE 计算公式**：

```
计算口径 (按设备, 按班次):

实际运行时间 = sum(clock_record.ended_at - clock_record.started_at)
计划运行时间 = 班次时长 - 计划停机 (保养/会议等)
实际产出 = sum(clock_record.good_qty + clock_record.bad_qty)
标准产出 = 计划运行时间 / 标准节拍
合格产出 = sum(clock_record.good_qty)

时间稼动率 = 实际运行时间 / 计划运行时间
性能稼动率 = 实际产出 / 标准产出
良品率   = 合格产出 / 实际产出

OEE = 时间稼动率 × 性能稼动率 × 良品率
```

**简化版（一期推荐）**：

```
简化 OEE = 实际运行时间 / 计划运行时间
```

只算时间稼动, 其他两个维度后期再加。客户主动问"为什么我家 OEE 这么高"时, 再上详细版。

**计算周期**：
- 实时: 当前班次正在进行的 OEE (不那么准确)
- 班结: 每个班次结束后冻结一次
- 日结: 按日聚合
- 月结: 按月聚合

---

## 四、典型 API 接口清单

下面这些接口是 MES MVP 必须暴露的, 按业务分组:

### 工单类

```
POST   /api/v1/work-orders                          创建工单
GET    /api/v1/work-orders/{wo_no}                  查工单详情
POST   /api/v1/work-orders/{wo_no}/confirm          确认 (draft → pending)
POST   /api/v1/work-orders/{wo_no}/cancel           取消
POST   /api/v1/work-orders/{wo_no}/kitting-check    齐套检查
POST   /api/v1/work-orders/{wo_no}/schedule         排产
GET    /api/v1/work-orders/{wo_no}/traceability     追溯
```

### 工序与报工类

```
GET    /api/v1/operations/by-qr?code=...            扫码进入工序 (操作主页)
POST   /api/v1/operations/{op_id}/start             开工
POST   /api/v1/operations/{op_id}/pause             暂停
POST   /api/v1/operations/{op_id}/resume            恢复
POST   /api/v1/operations/{op_id}/clock             报工 (核心高频接口)
```

### 质量类

```
POST   /api/v1/quality/first-article                首件检验
POST   /api/v1/quality/patrol                       巡检
POST   /api/v1/quality/final                        终检
GET    /api/v1/quality/defect-reasons               不良原因字典 (前端下拉)
```

### 看板与统计类

```
GET    /api/v1/dashboard/work-centers               工位实时状态
GET    /api/v1/dashboard/work-orders                工单进度
GET    /api/v1/reports/oee?wc=...&date=...          OEE 报表
GET    /api/v1/reports/output?date=...              产量报表
GET    /api/v1/reports/defects?date=...             不良统计
```

### WMS 接口适配类

```
POST   /api/v1/wms-callback/material-issued         WMS 配料完成通知 MES
POST   /api/v1/wms-callback/inventory-changed       WMS 库存变更通知 MES
GET    /api/v1/work-orders/{wo_no}/material-requests 给 WMS 拉取领料申请
```

---

## 五、给 AI 编码代理的强制约束

写任何 MES 业务代码前自检：

1. **状态机校验**：所有状态变更接口必须先校验源状态, 非法转换返回 400
2. **幂等性**：所有写入接口必须支持 `Idempotency-Key` header
3. **审计日志**：所有关键状态变更（工单状态、报工、质检结果）必须写审计表
4. **冗余快照**：流水表必须冗余存储关联实体的当时快照（名称、规格等）
5. **时区**：所有时间字段统一 UTC 存储, 前端转本地
6. **货币与数量**：数量字段用 decimal 而非 float, 精度精确到工艺要求位
7. **批次贯穿**：物料批次号必须在领料、用料、报工、入库链路中完整透传
8. **离线兼容**：高频写入接口必须考虑离线场景, 设计幂等键和重传策略
9. **接口边界**：MES 不直接读写 WMS 表, 必须通过 WMS API
10. **错误处理**：业务校验失败用 400 + 业务错误码; 系统异常用 5xx
11. **分页**：所有列表接口默认分页, 防止全表扫描
12. **删除策略**：业务实体一律软删除 (deleted_at), 流水永不删除

---

## 六、常见误区警示

写代码时如果遇到下面这些情况, 停下来想想:

- ❌ 想要让报工接口"顺便"更新库存、统计、看板缓存——拆开, 用事件驱动
- ❌ 想要让齐套检查直接读 WMS 库存表——必须通过 API, 不要跨库读取
- ❌ 想要让工序之间"自动跳过"未完成的——除非工艺路线显式标记可跳过
- ❌ 想要让不良品"自动"走某个流程——不良处置永远需要人工判定
- ❌ 想要为"未来扩展"加个抽象层——YAGNI, 等真有第二个实现再抽
- ❌ 想要 OEE 实时刷新到秒级——分钟级足够, 减少数据库压力
- ❌ 想要排产算法做得很"聪明"——简单规则 + 人工拖拽永远优于黑盒算法

---

## 七、与 lean-mes-builder 的关系

| 关注点 | lean-mes-builder | mes-business-flows (本技能) |
|-------|------------------|---------------------------|
| 视角 | 架构原则、避坑 | 业务流程、状态机 |
| 时机 | 设计阶段、需求评审 | 实现阶段、写代码 |
| 决策 | 该不该做这个功能 | 这个功能业务上怎么转 |
| 约束 | 不做什么、保持精简 | 必须遵守什么业务规则 |

两份技能联合使用：先用 lean-mes-builder 决定要不要做这个功能、做到什么程度, 再用 mes-business-flows 决定具体的业务流程和接口定义。
