# 前端全站视觉升级设计文档

> **产品**: Research Copilot
> **日期**: 2026-03-21
> **范围**: 全站 UI/UX 重设计 — 设计系统 + 所有页面 + 动效体系
> **技术方案**: 引入 Tailwind CSS + shadcn/ui + Framer Motion，替换现有 vanilla CSS

---

## 一、设计方向

- **风格**: 温暖专业（Craft / Arc Browser 路线）— 柔和渐变、圆润形状、在专业中带温度
- **色彩模式**: 暗色为主 + 浅色可选，用户可通过设置页切换
- **Accent 色**: 亮蓝色系，移除当前紫色调
- **动效**: 丰富有活力 — 入场、过渡、hover、Agent 状态动画，让界面"活"起来

---

## 二、设计系统

### 2.1 色彩 Token

| Token            | 浅色模式                | 深色模式                | 用途                        |
| ---------------- | ----------------------- | ----------------------- | --------------------------- |
| `background`     | `#F8F9FB`               | `#1A1B23`               | 页面底色                    |
| `surface`        | `#FFFFFF`               | `#22232E`               | 卡片/面板底色               |
| `surface-raised` | `#F1F3F7`               | `#2A2B38`               | 悬浮面板/下拉               |
| `border`         | `#E2E5EB`               | `#32333F`               | 分割线/边框                 |
| `border-hover`   | `#C8CDD6`               | `#45465A`               | hover 边框                  |
| `text-primary`   | `#1A1D26`               | `#EAEDF3`               | 主文本                      |
| `text-secondary` | `#6B7080`               | `#9096A6`               | 辅助文本                    |
| `text-muted`     | `#9CA1B0`               | `#737987`               | 弱化文本（WCAG AA ≥ 4.5:1） |
| `accent`         | `#2B7FFF`               | `#4D9AFF`               | 主交互色                    |
| `accent-hover`   | `#1A6FEF`               | `#6AABFF`               | accent hover                |
| `accent-subtle`  | `rgba(43,127,255,0.08)` | `rgba(77,154,255,0.12)` | accent 背景                 |
| `success`        | `#22C55E`               | `#34D399`               | 成功状态                    |
| `warning`        | `#F59E0B`               | `#FBBF24`               | 警告状态                    |
| `error`          | `#EF4444`               | `#F87171`               | 错误状态                    |

### 2.2 排版

| 属性     | 值                                                                                                      |
| -------- | ------------------------------------------------------------------------------------------------------- |
| 标题字体 | Inter, weight 600/700                                                                                   |
| 正文字体 | Inter, weight 400/500                                                                                   |
| 代码字体 | JetBrains Mono, weight 400/500                                                                          |
| 行高     | 1.5（比当前 1.6 更紧凑）                                                                                |
| 字号梯度 | xs: 0.75rem, sm: 0.8125rem, base: 0.875rem, md: 1rem, lg: 1.125rem, xl: 1.25rem, 2xl: 1.5rem, 3xl: 2rem |

### 2.3 圆角

| 层级 | 半径   | 适用         |
| ---- | ------ | ------------ |
| sm   | 8px    | 按钮、输入框 |
| md   | 12px   | 卡片、面板   |
| lg   | 16px   | 弹窗、模态   |
| full | 9999px | 头像、标签   |

### 2.4 阴影（多层缓动）

| 层级        | 浅色模式                                                   | 深色模式                        |
| ----------- | ---------------------------------------------------------- | ------------------------------- |
| `shadow-sm` | `0 1px 3px rgba(0,0,0,0.06)`                               | 用 border 代替                  |
| `shadow-md` | `0 4px 16px rgba(0,0,0,0.08)`                              | 用 border 代替                  |
| `shadow-lg` | `0 2px 8px rgba(0,0,0,0.04), 0 12px 40px rgba(0,0,0,0.10)` | 用 border + surface-raised 代替 |

### 2.5 主题切换实现

通过 `<html data-theme="dark">` 属性 + CSS 变量切换。shadcn/ui 内建的 `dark:` 类机制与此兼容。主题偏好存入 `localStorage`，首次访问跟随系统 `prefers-color-scheme`。

---

## 三、布局架构

### 3.1 导航栏 — 可折叠双栏

```
收起状态 (56px)          展开状态 (240px)
┌──────┐                ┌────────────────────────┐
│ Logo │                │ Logo  Research Copilot  │
│      │                │                        │
│  □   │  ← 工作区      │ □ 工作区                │
│      │                │   ┌──────────────────┐  │
│      │                │   │ 工作区选择器 ▾    │  │
│      │                │   └──────────────────┘  │
│      │                │                        │
│      │                │ Thread 历史列表         │
│      │                │   • Transformer 调研    │
│      │                │   • GNN 对比分析        │
│      │                │   • ...                │
│      │                │                        │
│  ⚙   │  ← 设置       │  ☀/🌙  用户头像  ⚙     │
└──────┘                └────────────────────────┘
```

- 切换方式：hover 或 toggle button，spring 动画（damping: 25, stiffness: 300）
- 展开后展示工作区选择器 + 当前工作区的 Thread 历史
- Thread 历史列表支持 `@tanstack/react-virtual` 虚拟滚动

### 3.2 工作台双栏

```
┌──────┬──────────────────┬──┬──────────────────────┐
│      │ 对话              │▎│ 📄 Editor  📑 PDF  🧪│
│ Nav  │                  │▎│                      │
│      │ [Avatar] User    │▎│ 编辑器内容区          │
│      │ 用户消息          │▎│                      │
│      │                  │▎│                      │
│      │ [Avatar] Agent   │▎│                      │
│      │ █ Agent 回复      │▎│                      │
│      │ │(左侧蓝色竖线)   │▎│                      │
│      │                  │▎│                      │
│      │ ┌──────────────┐ │▎│                      │
│      │ │ 输入框       > │ │▎│                      │
│      │ └──────────────┘ │▎│                      │
└──────┴──────────────────┴──┴──────────────────────┘
                          ▲ 可拖拽分割线
```

- 使用 `react-resizable-panels` 实现拖拽分割（shadcn 生态）
- Chat 最小宽度 320px，Canvas 最小宽度 400px
- 分割线带 resize handle + hover 高亮
- 双击分割线恢复 50/50 默认比例
- Agent 状态整合到 Chat 面板头部（状态灯 + 文字）
- **拖拽 60fps 保障**：`mousedown` 时给左右容器注入 `pointer-events: none` + `user-select: none`，上方覆盖透明遮罩防止 TipTap/PDF iframe 吞噬事件；`mouseup` 时移除

### 3.3 消息布局（通栏左对齐）

所有消息通栏左对齐，区分方式：

| 角色  | Avatar   | 背景色         | 左侧竖线           |
| ----- | -------- | -------------- | ------------------ |
| 用户  | 用户头像 | transparent    | 无                 |
| Agent | AI 图标  | surface        | accent 色 2px 竖线 |
| 系统  | 无       | warning-subtle | 无，居中小字       |

---

## 四、页面设计

### 4.1 工作区列表页 (`/workspaces`)

- **卡片**: 水平卡片，左侧学科渐变色块 + 图标，右侧名称/标签/时间/文档数
- **防溢出**: Flex 布局 + 文本 truncate，Badge 最多 3 个 + `+N` 溢出
- **新建**: 虚线边框 "+" 卡片 → 点击弹出 Dialog 模态框（shadcn/ui Dialog）
- **空状态**: 中央图标 + 引导文案 + CTA，fade-in 入场
- **卡片动效**: staggered fade-up，每张间隔 50ms
- **卡片 hover**: `translateY(-2px)` + 边框亮色 + 阴影

### 4.2 工作台页面 (`/workspace/:id`)

**Chat 面板**:
- 头部：工作区名称 + Agent 状态指示灯（idle/thinking/executing），pulse 动画
- 消息入场：slide-up + fade-in (y: 8→0, opacity: 0→1, 200ms)
- **SSE 流式安全**：`isStreaming: true` 的消息禁用 Framer Motion 形变动画，仅保留 CSS 闪烁光标；流式文本使用 `useRef` 局部管理，不触发 Zustand 全局 Store 高频更新；收到 `[DONE]` 信号后再执行平滑展开/折叠动画

**CoT 思考面板**:
- Agent 思考期间**自动展开**，带 auto-scroll
- Agent 输出最终结果时**自动折叠**
- 展开/折叠使用 `AnimatePresence` + `layout` spring 动画（仅在非 streaming 时触发）
- 内部使用 muted 色 + mono 字体

**HITL 卡片**:
- accent 色高亮边框 + attention-pulse（闪烁 2 次后停止）
- **Approve**: accent 实色按钮（主权重）
- **Reject**: ghost/outline 按钮（次权重）+ Popover 二次确认，防误触

**输入区**:
- 底部固定，大圆角输入框
- 发送按钮带 loading spinner

### 4.3 Canvas 面板

- **Tab 栏**: shadcn/ui Tabs + active 下划线 `layoutId` 滑动动画
- **Tab 溢出**: 隐藏滚动条样式 + overflow dropdown menu
- **工具栏**: 图标按钮组 + tooltip + 竖线分隔符分组
- **编辑器**: 更大内边距、行间距，聚焦阅读体验
- **PDF 渲染器**:
  - 基于 PDF.js，启用**页面级虚拟化**：仅渲染视口内 3-5 页，防止长 PDF（100+ 页）导致 OOM
  - **深色模式 PDF 反转**：暗色主题下对 PDF Canvas 容器应用 `filter: invert(0.9) hue-rotate(180deg)`，反转黑白同时保持图片色相，避免纯白 PDF 破坏暗色沉浸感

### 4.4 设置页 (`/settings`)

- 分组 surface 卡片：Profile | 学科偏好 | API Keys | 用量统计 | 主题切换
- 每组卡片：标题 + 描述 + 表单项
- 主题切换独立卡片，切换后全页平滑过渡（300ms CSS transition）

### 4.5 认证页面 (`/login`, `/register`)

- 居中 surface 卡片 + shadow-lg
- shadcn/ui Input + Label 组件
- 提交按钮带 loading spinner
- 卡片入场 scale-up + fade-in

---

## 五、动效系统

### 5.1 全局过渡

| 场景     | 进入               | 退出               | 缓动                           |
| -------- | ------------------ | ------------------ | ------------------------------ |
| 路由切换 | 200ms fade + slide | 150ms fade + slide | enter: ease-out, exit: ease-in |
| 主题切换 | 300ms              | —                  | ease                           |

### 5.2 组件级动效（Framer Motion）

| 组件         | 动效                         | 参数                                               |
| ------------ | ---------------------------- | -------------------------------------------------- |
| 卡片列表     | staggered fade-up            | `staggerChildren: 0.05`, `y: 12→0`, `opacity: 0→1` |
| Dialog       | scale + fade + backdrop blur | `scale: 0.95→1`, backdrop `opacity: 0→1`           |
| 侧边栏       | width spring                 | `type: "spring"`, `damping: 25`, `stiffness: 300`  |
| CoT 面板     | height + content fade        | `AnimatePresence` + `layout`                       |
| 消息入场     | slide-up + fade              | `y: 8→0`, `opacity: 0→1`, 200ms                    |
| 按钮 hover   | scale up                     | `scale: 1.02`, 120ms                               |
| 按钮 press   | scale down                   | `scale: 0.98`, 80ms                                |
| Agent 状态灯 | pulse                        | `box-shadow` 呼吸扩散                              |
| HITL 卡片    | attention pulse              | border-color 闪烁 2 次                             |
| Tab 下划线   | slide                        | Framer `layoutId` 共享动画                         |
| 分割线拖拽   | spring settle                | 拖拽无动画，释放 spring                            |

### 5.3 性能约束

- 所有动画仅使用 `transform` + `opacity`（GPU 合成层）
- `will-change` 仅动画激活时添加
- 列表 > 50 项时禁用 stagger，改为 instant 渲染
- 长列表（Thread 历史等）使用 `@tanstack/react-virtual` 虚拟化
- 尊重 `prefers-reduced-motion` 系统设置，降级为 instant

### 5.4 SSE 流式与动画隔离策略

**问题**：SSE 打字机每秒推送几十个 Token → React 高频重渲染 + Framer Motion 实时计算弹簧高度 → 主线程阻塞、掉帧甚至页面卡死。

**方案**：
1. `isStreaming: true` 状态的消息气泡**完全禁用** Framer Motion 形变动画
2. 流式文本通过 `useRef` + 局部独立 State 管理，**不触发** Zustand 全局 Store 更新
3. 仅保留轻量 CSS 闪烁光标动画（`@keyframes blink`）
4. 收到 SSE `[DONE]` 信号后，将最终文本写入 Store，并执行一次平滑过渡动画
5. CoT 面板的 `AnimatePresence` + `layout` 动画仅在 streaming 结束后触发

---

## 六、技术方案

### 6.1 新增依赖

| 包                                  | 用途                                                                        |
| ----------------------------------- | --------------------------------------------------------------------------- |
| `tailwindcss` + `@tailwindcss/vite` | 工具类 CSS                                                                  |
| `shadcn/ui` 组件（按需）            | Button, Dialog, Tabs, Input, Label, Select, Popover, Avatar, Badge, Tooltip |
| `react-resizable-panels`            | 可拖拽双栏分割面板                                                          |
| `framer-motion`                     | 组件级动画                                                                  |
| `@tanstack/react-virtual`           | 长列表虚拟化                                                                |

### 6.2 迁移策略

1. 安装 Tailwind + shadcn/ui 初始化
2. 将现有 CSS 变量迁移为 Tailwind + shadcn 主题变量
3. 逐组件替换：先替换基础组件（Button, Input），再替换页面
4. 现有 `.css` 文件逐步移除，最终只保留 `index.css`（全局 reset + Tailwind directives + 自定义 token）

---

## 七、验证计划

### 自动化测试
- `npm run build` 确保 TypeScript 编译无错误
- `npm run lint` 确保无 lint 错误

### 浏览器验证
- 逐页面截图对比新旧 UI
- 验证 light/dark 主题切换流畅
- 检查所有交互状态（hover/active/disabled/focus）
- 检查 WCAG 对比度 ≥ 4.5:1（text-muted 在两个主题下）
- 验证 `prefers-reduced-motion` 降级行为

### 用户手动验证
- 登录 → 工作区列表 → 创建工作区 → 进入工作台 → 发送消息 → 设置页切换主题，全流程顺畅
