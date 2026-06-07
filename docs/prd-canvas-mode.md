# AIMV Studio — 自由画布创作模式 PRD

**版本**: v0.1
**状态**: 草稿
**日期**: 2026-03-24
**作者**: Product / Claude

---

## 1. 背景与目标

### 1.1 现状问题

当前 AIMV Studio 的创作流程是**线性向导式**：

```
描述主题 → 风格选择 → 音乐上传 → AI 生成分镜 → 逐镜确认 → 合成导出
```

这种模式对初次用户友好，但对有创作意图的用户存在明显瓶颈：

- 分镜顺序固定，无法自由调度叙事结构
- 每个镜头孤立，缺乏全局视角下的节奏感知
- 无法直观感知"整首 MV 的空间构成"
- A/B 对比版本只能顺序浏览，无法并排对比
- 重新生成某一段落会破坏已完成镜头的上下文

### 1.2 参考形态

liblib.tv 的工作流（见附图）展示了**节点画布式**的视频创作范式：

- 每个视频帧/镜头是一个可自由拖拽的节点
- 节点间用有向连线表示叙事顺序
- 创作者可以自由聚类、分组、分支，像剪辑师的拼贴板一样工作
- 整个 MV 的结构一眼可见

### 1.3 目标

在 AIMV Studio 中新增 **Canvas Mode（自由画布创作模式）**，与现有线性模式并存，为创作者提供：

| 目标 | 度量指标 |
|---|---|
| 提升创作自由度 | 用户在画布模式完成创作的平均满意度 ≥ 4.2/5 |
| 加速叙事调整效率 | 镜头重排操作 < 3 次点击 |
| 全局感知 MV 结构 | 用户可在 5 秒内定位任意镜头 |
| 支持并行生成 | 单次最多同时生成 8 个镜头节点 |

---

## 2. 用户画像

### P0 — 进阶创作者
- 有完整 MV 创作概念，知道想要什么叙事结构
- 需要自由排布"前奏 / 高潮 / 尾奏"的视觉布局
- 习惯 Figma / Miro / Final Cut 等空间化工具

### P1 — AI 辅助型创作者
- 让 AI 生成初稿后，在画布上二次调整
- 需要看到全局才能做局部决策（"这段太暗了，前后要对比"）

### P2 — 协作型团队
- 需要分享画布给他人评审
- 观看者只读模式，评论者可标注

---

## 3. 整体产品形态

### 3.1 页面结构

```
┌─────────────────────────────────────────────────────────────┐
│  TopBar: 项目名 │ 撤销/重做 │ 模式切换(线性/画布) │ 导出 │ 分享  │
├──────┬──────────────────────────────────────────┬───────────┤
│      │                                          │           │
│ Left │           CANVAS WORKSPACE               │  Right    │
│ Panel│         (无限画布 + 节点图)               │  Panel    │
│      │                                          │           │
│ 资源库│  [Shot节点] ——→ [Shot节点] ——→ [Shot节点] │  镜头属性  │
│      │       ↓                                  │  Prompt   │
│ 角色库│  [Scene Group]     [A/B Compare节点]     │  模型选择  │
│      │                                          │  生成状态  │
│ 音乐  │                                          │           │
│ 分析  │  [+ 新建节点]                             │           │
├──────┴──────────────────────────────────────────┴───────────┤
│  Bottom: 音乐波形 / 节拍时间轴 / 当前播放头                       │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心隐喻

画布 = **导演的故事板（Storyboard）**

- **Shot 节点** = 一个视频片段（已生成或待生成）
- **有向边** = 镜头的叙事先后顺序
- **Scene Group** = 一组同场景的镜头（可折叠）
- **音乐时间轴** = 节拍/段落的时间锚点（底部）
- **Playhead** = 当前音乐播放位置，在画布上高亮对应节点

---

## 4. 核心功能模块

### 4.1 画布工作区

#### 4.1.1 基础交互
| 操作 | 快捷键 / 手势 |
|---|---|
| 平移画布 | Space + 拖拽 / 双指拖动 |
| 缩放 | Ctrl+滚轮 / 双指捏合 |
| 框选节点 | 拖拽空白区域 |
| 多选 | Shift + 点击 |
| 全选 | Ctrl/Cmd + A |
| 撤销/重做 | Ctrl/Cmd + Z / Y |
| 适配视口 | Ctrl/Cmd + Shift + H |
| 搜索定位 | Ctrl/Cmd + F |

#### 4.1.2 小地图（Minimap）
- 右下角常驻，可折叠
- 显示全局节点分布
- 点击小地图可快速跳转视口
- 显示当前视口范围（高亮框）

#### 4.1.3 背景网格
- 默认：细点阵网格（深色，低对比）
- 可切换：线格 / 无背景
- 不参与导出

### 4.2 Shot 节点

#### 4.2.1 节点状态与外观

```
┌──────────────────────────┐
│  [缩略图 / 生成动画]       │  ← 16:9 预览区，160×90px
│                          │
│  ● 场景描述文字（截断）     │
│  [模型标签] [时长] [状态]   │
└──────────────────────────┘
    ↑                   ↑
  左连接点            右连接点
```

**节点状态颜色**：
- `pending` — 边框灰色，缩略图显示"等待生成"占位符
- `generating` — 边框渐变动画（紫 → 粉循环），缩略图显示进度环
- `done` — 边框绿色（hover 时），缩略图显示视频帧
- `failed` — 边框红色，缩略图显示重试按钮
- `selected` — 边框亮紫色 + 外发光

#### 4.2.2 节点操作

| 操作 | 触发方式 |
|---|---|
| 选中 | 单击 |
| 预览视频 | 双击（全屏浮层播放） |
| 编辑属性 | 选中后右侧 Panel 更新 |
| 拖动位置 | 拖拽节点主体 |
| 连线 | 从连接点拖出（hover 时出现蓝色锚点） |
| 上下文菜单 | 右键 |
| 批量操作 | 框选后工具栏出现批量按钮 |

**右键菜单**：
```
生成此镜头
重新生成
复制节点
复制 Prompt
锁定 / 解锁位置
添加到 Scene Group
删除
```

#### 4.2.3 快速生成浮层

双击空白画布 → 弹出**快速创建节点**浮层：
```
┌────────────────────────────────┐
│  描述这个镜头...（文本输入）       │
│                                │
│  模型: [Seedance ▾]  时长: [5s]│
│           [生成]  [取消]        │
└────────────────────────────────┘
```
确认后在点击位置创建节点，立即开始生成。

### 4.3 连线（Edge）

#### 4.3.1 连线类型
| 类型 | 外观 | 语义 |
|---|---|---|
| `sequence` | 实线箭头（白色） | 镜头顺序接续 |
| `branch` | 虚线箭头（橙色） | 分支版本（A/B 对比） |
| `parallel` | 双线箭头（蓝色） | 同时进行的镜头（多机位） |

#### 4.3.2 连线交互
- 从节点右侧锚点拖出 → 拖到另一节点左侧锚点 → 松开创建连线
- 点击连线可选中（变为高亮），Delete 键删除
- 双击连线可标注备注
- 连线上显示时间差（如 "+2.5s"）

### 4.4 Scene Group（场景组）

- 框选多个节点 → 右键 → "创建场景组"
- 场景组有标题（可编辑）、颜色（可选）、圆角边框
- **折叠**：双击组标题 → 组内节点折叠为单个组节点（显示节点数量）
- **展开**：双击折叠后的组节点
- 移动组 = 批量移动组内所有节点
- 组可嵌套（最多 2 层）

```
┌─ 前奏段 [8节点] ──────────────────────────┐
│                                           │
│  [Shot1] → [Shot2] → [Shot3]              │
│       ↘                                   │
│        [Shot4-B(branch)]                  │
│                                           │
└───────────────────────────────────────────┘
```

### 4.5 音乐时间轴（底部）

```
┌──────────────────────────────────────────────────────────┐
│ ▶ 00:12.3          ━━━━━━━━━━━━━━━━━━━━━━━━━  02:48.0   │
│ |前奏|  A段  |       B段(高潮)      |   C段   | 尾奏|     │
│ ┊  ┊  ┊  ┊  ┊  ┊  ┊  ┊  ┊  ┊  ┊  ┊  ┊  ┊  ┊  ┊       │
│ ↑节拍线                              ↑播放头             │
└──────────────────────────────────────────────────────────┘
```

- 根据 `MusicAnalysis`（BPM、segments、beats）自动渲染
- 段落（前奏/A段/B段/C段）用不同颜色区块标注
- 播放头拖动时，画布中当前时间对应的节点高亮
- 节点可**锁定到时间轴**：拖拽节点到时间轴 → 节点固定在该时间点（对齐节拍）
- 支持"节拍对齐"模式：自动将节点起始点吸附到最近节拍

### 4.6 AI 辅助功能

#### 4.6.1 自动布局

工具栏 → "AI 自动编排" → 调用 DirectorAgent：
- 根据音乐结构（段落、节拍、情绪曲线）自动将节点对齐时间轴
- 根据叙事逻辑推荐连线顺序
- 推荐后用户可接受/拒绝，逐个或全部

#### 4.6.2 下一镜头建议

选中一个节点 → 右侧 Panel 底部出现 **"AI 建议下一镜头"**：
- 根据当前镜头的 prompt、情绪、运动方向推荐 3 个候选 prompt
- 点击候选 → 在当前节点右侧自动创建并连线新节点

#### 4.6.3 批量生成

框选多个 `pending` 节点 → "批量生成（N 个）" → 并发调用，逐个完成时实时更新缩略图

#### 4.6.4 一键生成全部

工具栏 → "生成所有空白镜头" → 扫描全画布 pending 节点，按拓扑顺序批量提交任务

### 4.7 右侧属性面板

选中节点时展开，无选中时收起（或显示项目信息）：

```
┌─────────────────────────┐
│  Shot #12               │
│  ─────────────────────  │
│  Prompt                 │
│  ┌───────────────────┐  │
│  │一个女孩站在樱花树下  │  │
│  │，镜头缓慢推进...   │  │
│  └───────────────────┘  │
│                         │
│  模型     [Seedance 2.0] │
│  时长     [5s ▾]         │
│  运动     [推镜头 ▾]      │
│  比例     [16:9 ▾]        │
│                         │
│  锁定时间点  [02:14.5]    │
│  场景组   [高潮段 ▾]      │
│                         │
│  [重新生成]  [复制Prompt] │
│                         │
│  ─ 质量评分 ─            │
│  ★★★★☆  4.2 / 5.0      │
│  [用此版本] [弃用]        │
└─────────────────────────┘
```

### 4.8 导出到时间线

画布创作完成后 → "导出到时间线" → 将有向图按拓扑排序转换为线性序列，进入合成 Pipeline：

1. 检查是否存在孤立节点（无连线）→ 提示用户
2. 检查是否存在循环依赖 → 报错
3. 按拓扑顺序生成 `shot_sequence`
4. 调用现有合成 Worker（FFmpeg concat）

---

## 5. 交互设计规范

### 5.1 视觉风格

| 元素 | 规范 |
|---|---|
| 画布背景 | `#0a0a10`，点阵网格 `rgba(255,255,255,0.04)` |
| 节点背景 | `#16161e`，`border: 1px solid rgba(255,255,255,0.1)` |
| 节点 hover | `border-color: rgba(141,92,255,0.6)` |
| 连线颜色 | `rgba(255,255,255,0.4)` → hover `#8d5cff` |
| 场景组边框 | 用户选色，默认 `rgba(141,92,255,0.25)` |
| 选中高亮 | `box-shadow: 0 0 0 2px #8d5cff` |
| 生成中动画 | 边框渐变 keyframe，紫→粉→紫，3s loop |

### 5.2 性能要求

- 画布节点 ≤ 200 个时流畅渲染（60fps）
- 缩略图懒加载（仅渲染视口内节点的图片）
- 节点位置变更 debounce 500ms 后存库
- 画布状态自动保存（localStorage + 后端同步）

### 5.3 快捷键全表

| 快捷键 | 功能 |
|---|---|
| G | 生成选中节点 |
| R | 重新生成选中节点 |
| N | 新建节点（在鼠标位置） |
| Del / Backspace | 删除选中 |
| Ctrl+G | 选中节点创建场景组 |
| Ctrl+Shift+G | 解散场景组 |
| Ctrl+L | AI 自动布局 |
| Ctrl+P | 播放预览 |
| F | 聚焦选中节点（适配到视口） |
| Escape | 取消选中 / 关闭浮层 |
| 1/2/3 | 缩放到 25% / 50% / 100% |

---

## 6. 数据模型

### 6.1 新增 Canvas 表

```sql
CREATE TABLE canvases (
  id          SERIAL PRIMARY KEY,
  project_id  INTEGER REFERENCES projects(id) ON DELETE CASCADE,
  viewport_x  FLOAT DEFAULT 0,
  viewport_y  FLOAT DEFAULT 0,
  viewport_zoom FLOAT DEFAULT 1.0,
  created_at  TIMESTAMP DEFAULT now(),
  updated_at  TIMESTAMP DEFAULT now()
);
```

### 6.2 CanvasNode（扩展现有 Task 表）

在 `tasks` 表新增字段（或新建 `canvas_nodes` 表）：

```sql
ALTER TABLE tasks ADD COLUMN canvas_x      FLOAT;
ALTER TABLE tasks ADD COLUMN canvas_y      FLOAT;
ALTER TABLE tasks ADD COLUMN canvas_w      FLOAT DEFAULT 200;
ALTER TABLE tasks ADD COLUMN canvas_h      FLOAT DEFAULT 130;
ALTER TABLE tasks ADD COLUMN canvas_locked BOOLEAN DEFAULT FALSE;
ALTER TABLE tasks ADD COLUMN time_anchor   FLOAT;        -- 锁定的时间轴位置(秒)
ALTER TABLE tasks ADD COLUMN scene_group   VARCHAR(64);  -- 所属场景组 ID
```

### 6.3 CanvasEdge 表

```sql
CREATE TABLE canvas_edges (
  id          SERIAL PRIMARY KEY,
  canvas_id   INTEGER REFERENCES canvases(id) ON DELETE CASCADE,
  source_id   INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
  target_id   INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
  edge_type   VARCHAR(20) DEFAULT 'sequence', -- sequence | branch | parallel
  label       VARCHAR(255),
  created_at  TIMESTAMP DEFAULT now()
);
```

### 6.4 SceneGroup 表

```sql
CREATE TABLE scene_groups (
  id          VARCHAR(64) PRIMARY KEY,  -- uuid
  canvas_id   INTEGER REFERENCES canvases(id) ON DELETE CASCADE,
  label       VARCHAR(100),
  color       VARCHAR(20) DEFAULT '#8d5cff',
  collapsed   BOOLEAN DEFAULT FALSE,
  x           FLOAT,
  y           FLOAT,
  created_at  TIMESTAMP DEFAULT now()
);
```

### 6.5 API 接口新增

```
GET    /api/v1/projects/{id}/canvas          # 获取画布状态
PUT    /api/v1/projects/{id}/canvas          # 更新视口（增量）
POST   /api/v1/projects/{id}/canvas/nodes    # 创建节点（+ 立即生成可选）
PATCH  /api/v1/projects/{id}/canvas/nodes/batch  # 批量更新位置
GET    /api/v1/projects/{id}/canvas/edges    # 获取所有边
POST   /api/v1/projects/{id}/canvas/edges    # 创建边
DELETE /api/v1/projects/{id}/canvas/edges/{eid}
POST   /api/v1/projects/{id}/canvas/groups   # 创建场景组
PUT    /api/v1/projects/{id}/canvas/groups/{gid}
DELETE /api/v1/projects/{id}/canvas/groups/{gid}
POST   /api/v1/projects/{id}/canvas/export-to-timeline  # 拓扑排序导出
POST   /api/v1/projects/{id}/canvas/auto-layout         # AI 自动布局
```

---

## 7. 技术选型

### 7.1 前端画布引擎

**推荐：`@vue-flow/core`**（Vue 3 版本的 React Flow）

| 方案 | 优点 | 缺点 |
|---|---|---|
| **@vue-flow/core** | Vue 3 原生、节点/边全组件化、响应式、维护活跃 | 200+ 节点性能需优化 |
| Fabric.js + Vue | 渲染性能好 | 节点组件化差，维护成本高 |
| 原生 Canvas/WebGL | 性能最强 | 开发周期长（3-4 个月） |
| Konva.js + vue-konva | 性能好 | 生态较小 |

**选型理由**：Vue Flow 的 API 与现有 Vue 3 + Pinia 栈完全契合，节点/边可用 Vue SFC 组件定义，与现有 UI 组件复用性强。

### 7.2 关键依赖

```json
{
  "@vue-flow/core": "^1.42.x",
  "@vue-flow/minimap": "^1.x",
  "@vue-flow/controls": "^1.x",
  "@vue-flow/background": "^1.x",
  "elkjs": "^0.9.x"   // 用于 AI 自动布局的图排版算法
}
```

### 7.3 状态管理

画布状态使用独立的 `useCanvasStore`（Pinia）：

```ts
interface CanvasStore {
  nodes: VueFlowNode[]
  edges: VueFlowEdge[]
  groups: SceneGroup[]
  viewport: { x: number; y: number; zoom: number }
  selectedNodeIds: Set<string>
  // actions
  addNode(pos: XYPosition, prompt?: string): Promise<void>
  moveNodes(moves: { id: string; x: number; y: number }[]): void
  connectNodes(source: string, target: string, type: EdgeType): void
  generateNode(id: string): void
  generateBatch(ids: string[]): void
  exportToTimeline(): ShotSequence
  autoLayout(): Promise<void>
}
```

---

## 8. MVP 范围（v1.0）

### 必须有（P0）

- [ ] 无限画布 + 平移/缩放
- [ ] Shot 节点：创建、拖拽、连线、删除
- [ ] 节点状态显示（pending / generating / done / failed）
- [ ] 双击空白处快速创建节点并生成
- [ ] 右侧属性面板（编辑 prompt、模型、时长）
- [ ] 节点重新生成
- [ ] 场景组创建/折叠
- [ ] 导出到时间线（拓扑排序 → 合成 Pipeline）
- [ ] 画布状态自动保存
- [ ] 小地图
- [ ] 撤销/重做

### 应该有（P1）

- [ ] 音乐时间轴 + 节拍线
- [ ] 节点锁定到时间点
- [ ] 批量生成
- [ ] AI 自动布局（ELK.js 算法）
- [ ] A/B 对比节点（branch edge）
- [ ] 连线类型切换

### 可以有（P2）

- [ ] AI 建议下一镜头
- [ ] 节点评分与择优
- [ ] 画布分享（只读链接）
- [ ] 多人协作（WebSocket 光标同步）
- [ ] 移动端触控支持

---

## 9. 非功能需求

| 类别 | 指标 |
|---|---|
| 性能 | 100 节点画布，拖拽帧率 ≥ 55fps（Chrome M2） |
| 存储 | 画布状态增量更新，单次 PATCH ≤ 20KB |
| 可靠性 | 节点位置每 30s 自动持久化，刷新后恢复 |
| 兼容性 | Chrome 110+, Safari 16+, Firefox 115+ |
| 无障碍 | 键盘可操作全部核心功能（无障碍 Tab 顺序） |

---

## 10. 与现有系统集成

```
现有线性模式              Canvas Mode
─────────────             ────────────────
/create/{id}    ←──────→  /canvas/{id}
  (Step 向导)      共享     (自由画布)
                  Task/
                  Project
                  数据模型
                    ↓
               /editor/{id}
               (合成 + 导出，共用)
```

两种模式读写同一套 `Task` / `Project` 数据，入口互相跳转，合成导出共用现有 Pipeline。

---

## 11. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解方案 |
|---|---|---|---|
| Vue Flow 在 150+ 节点性能下降 | 中 | 高 | 视口裁剪（仅渲染可见节点），虚拟化缩略图 |
| 有向图存在环导致导出失败 | 低 | 中 | 导出前做拓扑检测，高亮成环的边提示用户 |
| 多人同时编辑画布冲突 | 低（MVP 不做） | 中 | MVP 阶段单用户，后续用 CRDT / OT |
| 手机端画布操作体验差 | 高 | 低 | MVP 不优化移动端，仅桌面 |

---

## 附录：界面草图说明

参考 liblib.tv 截图中的核心视觉语言：

1. **节点密度**：单屏可容纳 20-50 个节点，通过缩放探索全局
2. **连线美学**：贝塞尔曲线，不遮挡缩略图，hover 变色
3. **聚类感知**：相关镜头自然聚拢（用户手动 or AI 自动），场景组用低透明度填充框区分
4. **暗色基调**：保持与 AIMV Studio 整体设计语言一致（背景 `#0a0a10`）
5. **缩略图优先**：每个节点用视频帧缩略图作为主视觉，文字信息辅助

---

*下一步：UI 高保真原型设计 → 技术 Spike（Vue Flow 性能测试）→ 后端数据模型 Migration → 前端 Canvas 组件开发*
