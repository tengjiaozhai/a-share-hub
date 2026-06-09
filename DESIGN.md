---
name: A股/美股自动交易系统
description: 专业量化交易工作台，支持策略配置、实时监控和风险控制，提供8种主题切换
colors:
  # Trading Terminal (默认主题)
  primary: "#4dd4c6"
  primary-deep: "#3db8ab"
  bg: "#0b1117"
  panel: "#101922"
  panel-2: "#0e1520"
  surface: "#101922"
  surface2: "#162231"
  fg: "#e7edf5"
  text: "#e7edf5"
  muted: "#94a3b8"
  dim: "#64748b"
  green: "#22c55e"
  red: "#ef4444"
  yellow: "#eab308"
  warn: "#f7b955"
  danger: "#f26d6d"
  stroke: "rgba(255,255,255,0.08)"
  border: "rgba(255,255,255,0.08)"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "clamp(1.5rem, 4vw, 2.5rem)"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "normal"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
    fontSize: "10px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.5px"
  mono:
    fontFamily: "'SF Mono', 'Cascadia Code', 'Fira Code', ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  sm: "4px"
  md: "8px"
  lg: "12px"
spacing:
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.bg}"
    rounded: "{rounded.sm}"
    padding: "9px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-deep}"
  button-secondary:
    backgroundColor: "{colors.surface2}"
    textColor: "{colors.fg}"
    rounded: "{rounded.sm}"
    padding: "7px 14px"
  input:
    backgroundColor: "{colors.panel-2}"
    textColor: "{colors.fg}"
    rounded: "{rounded.sm}"
    padding: "6px 8px"
  card:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.fg}"
    rounded: "{rounded.md}"
    padding: "10px 12px"
  chip:
    backgroundColor: "rgba(77,212,198,0.15)"
    textColor: "{colors.primary}"
    rounded: "12px"
    padding: "2px 8px"
themes:
  - id: "trading-terminal"
    name: "交易终端"
    description: "默认深色主题，青色主色调"
    accent: "#4dd4c6"
  - id: "mission-control"
    name: "任务控制"
    description: "海军蓝+琥珀色遥测风格"
    accent: "#f59e0b"
  - id: "neutral-modern"
    name: "中性现代"
    description: "平衡的浅色阅读主题"
    accent: "#2563eb"
  - id: "hud-signal"
    name: "HUD信号"
    description: "高对比度操作深色主题"
    accent: "#00ff88"
  - id: "mono-grid"
    name: "单色网格"
    description: "终端风格单色主题"
    accent: "#ffffff"
  - id: "openai-editorial"
    name: "OpenAI编辑"
    description: "平静的深色编辑风格"
    accent: "#10a37f"
  - id: "nvidia-power"
    name: "NVIDIA性能"
    description: "性能绿黑主题"
    accent: "#76b900"
  - id: "coinbase-institutional"
    name: "Coinbase机构"
    description: "简洁金融白色主题"
    accent: "#0052ff"
---

# Design System: A股/美股自动交易系统

## 1. Overview

**Creative North Star: "专业交易控制台"**

这是一个为个人量化交易者设计的专业工作台，强调信息密度和操作效率。系统提供8种精心设计的主题，满足不同场景和个人偏好，从深色交易终端到浅色现代风格，从高对比度HUD到极简单色。

设计哲学：在合理范围内展示足够的信息来支持快速决策，同时保持界面的清晰和可读性。系统状态、执行状态、风险状态一目了然。主题系统允许用户根据环境光线、使用场景和个人喜好自定义界面，同时保持一致的交互逻辑和信息架构。

**Key Characteristics:**
- 8种主题切换，适应不同场景和偏好
- 信息密度优先，支持快速决策
- 状态清晰可见，操作反馈明确
- 专业可靠，体现量化交易的技术深度
- 主题间保持一致的交互逻辑和信息层次

## 2. Colors

深色调色板，以青色为主色调，营造专业交易环境。系统支持8种主题，每种主题都有完整的色彩系统。

### 主题系统

系统提供8种精心设计的主题，通过`data-theme`属性切换：

1. **Trading Terminal** (默认): 深色背景，青色主色调，专业交易环境
2. **Mission Control**: 海军蓝+琥珀色，遥测风格
3. **Neutral Modern**: 浅色背景，蓝色主色调，现代阅读体验
4. **HUD Signal**: 纯黑背景，高对比度绿色，HUD风格
5. **Mono Grid**: 深灰背景，单色设计，终端风格
6. **OpenAI Editorial**: 深紫背景，绿色主色调，编辑风格
7. **NVIDIA Power**: 纯黑背景，性能绿，高性能风格
8. **Coinbase Institutional**: 浅灰背景，蓝色主色调，机构风格

每个主题都定义了完整的色彩系统，包括背景、面板、文字、强调色、语义色等。主题切换通过CSS变量实现，确保即时生效。

### Primary (Trading Terminal 默认主题)
- **青色主色调** (#4dd4c6): 主要强调色，用于按钮、选中状态、关键指标。在深色背景上提供良好的对比度。
- **深青色** (#3db8ab): 主色调的深色变体，用于悬停状态。

### Neutral
- **深黑背景** (#0b1117): 主背景色，提供沉浸式交易环境。
- **面板背景** (#101922): 卡片和面板背景，与主背景形成层次。
- **深色面板** (#0e1520): 输入框和次级面板背景。
- **表面色** (#162231): 悬停和激活状态的背景。
- **前景色** (#e7edf5): 主要文本颜色，在深色背景上提供良好的可读性。
- **静音色** (#94a3b8): 次要文本和标签。
- **暗灰色** (#64748b): 占位符和禁用状态。

### Semantic
- **绿色** (#22c55e): 正面状态，如盈利、买入信号。
- **红色** (#ef4444): 负面状态，如亏损、卖出信号。
- **黄色** (#eab308): 警告状态，如待处理、运行中。
- **警告色** (#f7b955): 警告指示器。
- **危险色** (#f26d6d): 危险状态和错误。

### Named Rules
**The Information Density Rule.** 在合理范围内展示足够的信息来支持快速决策，但避免信息过载。每个数据点都应该有明确的用途。

## 3. Typography

**Display Font:** 系统字体栈（-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif）
**Body Font:** 系统字体栈
**Mono Font:** SF Mono, Cascadia Code, Fira Code

**Character:** 专业、清晰、易读。使用系统字体栈确保跨平台的一致性，等宽字体用于数值和代码显示。

### Hierarchy
- **Display** (700, clamp(1.5rem, 4vw, 2.5rem), 1.2): 主要标题和关键指标。
- **Body** (400, 12px, 1.5): 正文内容和描述文本。
- **Label** (600, 10px, 1.4, 0.5px): 标签和分类文本，使用大写和字母间距增强可读性。
- **Mono** (400, 12px, 1.4): 数值、代码和等宽显示。

### Named Rules
**The Tabular Numbers Rule.** 所有数值显示使用等宽字体和tabular-nums特性，确保数字对齐，便于快速比较。

## 4. Elevation

采用扁平化设计，通过背景色和边框创建层次感，而不是阴影。

### Layering Strategy
- **主背景** (#0b1117): 最底层
- **面板背景** (#101922): 卡片和容器
- **深色面板** (#0e1520): 输入框和次级元素
- **表面色** (#162231): 悬停和激活状态

### Named Rules
**The Flat-By-Default Rule.** 元素默认扁平，通过背景色变化和边框创建层次，而不是阴影。这保持了界面的清晰和专业感。

## 5. Components

### Buttons
- **Shape:** 圆角矩形（4px）
- **Primary:** 青色背景 (#4dd4c6)，深色文字 (#0b1117)，padding: 9px 16px
- **Hover:** 深青色背景 (#3db8ab)
- **Secondary:** 表面色背景 (#162231)，前景色文字 (#e7edf5)，边框: 1px solid rgba(255,255,255,0.08)

### Inputs / Fields
- **Style:** 深色面板背景 (#0e1520)，边框: 1px solid rgba(255,255,255,0.08)
- **Focus:** 边框变为青色 (#4dd4c6)
- **Padding:** 6px 8px
- **Font:** 12px 系统字体

### Cards / Containers
- **Corner Style:** 圆角 (8px)
- **Background:** 面板背景 (#101922)
- **Border:** 1px solid rgba(255,255,255,0.08)
- **Internal Padding:** 10px 12px

### Chips / Tags
- **Style:** 青色背景 (rgba(77,212,198,0.15))，青色文字 (#4dd4c6)
- **Corner Style:** 圆角 (12px)
- **Padding:** 2px 8px
- **Font:** 11px, 600 weight

### Navigation
- **Style:** 深色背景，青色活动状态
- **Typography:** 11px, 600 weight
- **States:** 活动状态使用青色背景，悬停状态使用前景色文字

## 6. Do's and Don'ts

### Do:
- **Do** 使用深色主题，减少长时间使用的视觉疲劳
- **Do** 保持信息密度，支持快速决策
- **Do** 使用等宽字体显示数值，确保对齐
- **Do** 使用语义化颜色（绿色=正面，红色=负面，黄色=警告）
- **Do** 保持状态清晰可见，操作反馈明确
- **Do** 保留8种主题切换功能，满足不同场景需求
- **Do** 确保所有主题都保持一致的交互逻辑和信息层次
- **Do** 为每个主题提供完整的色彩系统，包括背景、面板、文字、强调色、语义色

### Don't:
- **Don't** 使用极简主义，牺牲功能完整性
- **Don't** 使用过多动画，分散注意力
- **Don't** 使用浅色主题，不适合长时间交易
- **Don't** 使用过于花哨的装饰，保持专业感
- **Don't** 使用阴影，保持扁平化设计
- **Don't** 移除主题切换功能，这是用户个性化的重要特性
- **Don't** 在不同主题间改变交互逻辑或信息架构
- **Don't** 为主题添加不一致的色彩角色或命名