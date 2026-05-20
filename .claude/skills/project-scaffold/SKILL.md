---
name: project-scaffold
description: Initialize a well-structured project folder architecture for new or existing projects. Use when the user starts a new project, wants to reorganize an existing project, asks "how should I organize this project", or discusses project structure. Follows the 4-layer Agent-Native architecture: Skill layer (routing docs) → Knowledge layer (structured cards) → Primitive layer (reusable components) → Verification layer (testing). Adapts depth to project scale — never over-engineer a single-script project.
---

# Project Scaffold

Initialize or reorganize a project with an agent-friendly folder architecture.

## Core Principle: Understand First, Then Build

**Do NOT skip ahead. Follow the phases in order.** Creating architecture without understanding the project is worse than no architecture.

### Phase 0: Understand the Project (MANDATORY)

Before any architecture decisions, complete these steps:

**0a. Read papers first**

If there's a `论文/` (papers) directory or the user mentions related papers:
1. List all PDFs in 论文/
2. Read each paper (use the paper-tutor agent if available, or read directly)
3. Extract: the governing equations, the numerical method, the physical parameters, the expected outputs
4. Summarize your understanding to the user and confirm it's correct before proceeding

**0b. Read all code**

1. List every `.py` file in the project
2. Read each file in full (not just scan)
3. For each file note: what it does, what it imports, what it outputs
4. Identify duplicated code across files

**0c. Map paper to code**

For each mathematical concept in the paper, identify which code file/function implements it. If there's a mismatch, flag it.

**0d. Report findings to the user**

Before creating anything, summarize:
- What problem the project solves
- What methods it uses
- What the code structure looks like (current)
- What duplicated code was found
- What architecture tier you recommend and why

**User must approve before you create anything.**

### Assessment Checklist（Phase 0 后才能做）

Ask the user (or infer from code):

1. Is this a multi-module project or a single script?
2. Will there be shared code across modules? (shared primitives)
3. Will the project be worked on iteratively over weeks/months?
4. Will multiple agents be used? (code-writer, explainer, paper-tutor, etc.)
5. Is there existing code to analyze or is this from scratch?

### Three Tiers

| Tier | When to use | What gets created |
|------|------------|-------------------|
| **Lightweight** | Single script, one-off analysis | CLAUDE.md only (routing + commands) |
| **Standard** | Multi-module, shared code, multi-agent | CLAUDE.md + knowledge/ + shared/ |
| **Full** | Long-term research, experiments, benchmarks | Standard + tests/ + scripts/ + experiment tracking |

**Default to the simplest tier that fits.** You can always upgrade later.

---

## Tier 1: Lightweight (CLAUDE.md only)

For single-script projects, a Jupyter notebook analysis, or one-off data processing.

### What to create

A `CLAUDE.md` (~40 lines) containing:

```markdown
# CLAUDE.md

## 语言要求
所有对话、代码注释、文档编写必须使用中文。

## 项目概述
[一句话描述项目做什么]

## 常用命令
[启动、运行、测试的命令]

## 文件说明
[关键文件的用途，每文件一行]
```

### What NOT to create
- No `knowledge/` directory
- No `shared/` directory
- No `tests/` directory
- No agent definitions (unless the user specifically wants them)

---

## Tier 2: Standard (Multi-module project)

For projects with 2+ sub-modules sharing code, multi-agent usage, or iterative development over weeks.

### Step 1: Analyze existing code (if any)

Before creating anything, read existing code to find:
- Duplicated class/function definitions across files
- Shared numerical/computation components
- Distinct module boundaries
- Current pain points (user feedback)

Report findings to the user before proceeding.

### Step 2: Create directory structure

```
project/
├── CLAUDE.md              # Routing index (~60 lines)
├── knowledge/              # Structured knowledge cards
│   ├── <module1>-overview.md
│   ├── <module2>-overview.md
│   └── experiments/
│       └── .gitkeep
├── shared/                 # Reusable primitives
│   ├── __init__.py
│   ├── <domain1>/
│   │   ├── __init__.py
│   │   └── <component>.py
│   └── <domain2>/
│       ├── __init__.py
│       └── <component>.py
├── <module1>/              # Existing module directories
├── <module2>/
└── .gitignore
```

### Step 3: Write CLAUDE.md as routing index

The CLAUDE.md must be thin. It should tell an agent **where to find information**, not contain all the information itself.

```markdown
# CLAUDE.md

## 项目概述
[1-2 sentence description]

## 知识路由（先读卡片，再改代码）
| 你要做什么 | 先读这张卡片 |
|-----------|-------------|
| 理解/修改 X | knowledge/x-overview.md |
| 了解 Y 实现 | knowledge/y-detail.md |

## 共享代码 (shared/)
| 模块 | 提供 |
|------|------|
| shared.x.component | [what it provides] |

## 常用命令
[Quick start commands]

## 文件路径约定
[Where outputs go]
```

Key rules for CLAUDE.md:
- Keep under 80 lines
- Move detailed architecture to knowledge cards
- The routing table is the most important part
- Include shared/ import instructions

### Step 4: Extract shared primitives

For each duplicated component found in Step 1:

1. Identify the canonical version (which implementation is the most correct/complete)
2. Create `shared/<domain>/<component>.py` with the canonical version
3. Add both vectorized and loop versions if both are needed for different scales
4. Add `__init__.py` files
5. Refactor existing files to import from shared
6. Verify: load an old model checkpoint / run a quick test to confirm compatibility

Template for shared module files:

```python
"""<Component> — <one-line description>

[Brief explanation of what this provides]
"""

# [Clean implementation with type hints in docstrings]
```

### Step 5: Write knowledge cards

Create one card per module or concept. Use the structured format:

```markdown
---
类型: primitive | tuning | experiment
标签: [relevant tags]
依赖: [dependencies]
---
# <Title>

## 摘要
[One sentence]

## 前提条件
[When to use / not use]

## 代码入口
| 文件 | 功能 |
|------|------|
| path/to/file | what it does |

## 核心架构 / 关键参数
[Tables preferred over prose]

## 边界限制
[What agents must NOT do]

## 相邻模块
- [[other-card]] — relationship
```

**Card naming**: Use kebab-case, descriptive names. Place experiment records under `knowledge/experiments/`.

**Which cards to write first**: Start with one overview card per major module. Add detail cards (solver internals, training configs) as the project grows.

### Step 6: Update agent definitions (if agents exist)

If `.claude/agents/` already has agent definitions, add to each:

```markdown
## 知识路由（开始工作前先读卡片）
| 任务场景 | 先读卡片 |
|---------|---------|
| ... | knowledge/... |

## 触发边界
- **使用我**：[when to trigger]
- **不要用我**：[when to use another agent instead]
- **相邻 agent**：[related agents and their roles]
```

---

## Tier 3: Full (Long-term research project)

Everything in Tier 2, plus:

### Additional directories

```
project/
├── scripts/                # 工具脚本（数据生成、批量评估等）
│   ├── benchmark_<task>.py
│   └── compare_<topic>.py
└── knowledge/experiments/   # 变更报告和实验记录
    └── <YYYYMMDD>-<slug>.md
```

### Verification 层 — 输出文档供人工检验

探索性研究项目**没有已知 baseline**（正确答案不存在），因此不做 agent 自动验证。验证方式是：agent 每次生成/修改代码并运行实验后，**输出详细的变更文档**，由人来判断方向是否正确。

#### 流程：先提计划，批准后再执行

agent 在开始任何验证操作（跑实验、生成数据、修改代码）之前，必须先向用户提交一份简短的**验证计划**：

```
## 验证计划

### 要做什么
[一句话描述]

### 步骤
1. [步骤1] → 预计耗时 [X分钟]
2. [步骤2] → 预计耗时 [X分钟]

### 需要确认
- [关键决策点或风险]
```

用户批准后才能执行。执行完毕后输出变更报告。

#### 触发条件

以下任一情况发生，必须先输出验证计划，批准后再执行：
- 修改了代码并准备运行实验
- 生成新的训练数据
- 跑一轮超参数搜索
- 进行对比实验

#### 变更报告模板

```markdown
## 变更报告 — [简短标题]

### 改动内容
- **文件**: [哪个文件，哪个函数]
- **改动**: [一行说清楚改了什么]
- **原因**: [为什么要改 — 解决什么问题、验证什么假设]

### 复现方法
- **运行命令**: [精确的命令 + 参数，确保他人可以重现]
- **随机种子**: [如果涉及]
- **硬件/环境**: [GPU型号、Python版本等如有特殊要求]

### 实验结果

| 指标 | 本轮结果 | 说明 |
|------|---------|------|
| [指标名] | [具体数值] | [含义 / 与理论预期的对比] |

### 分析
- [结果说明了什么 — 物理或数值层面的解释]
- [不确定性在哪 — 数据不足？需要更多实验？随机种子影响？]
- [如果有退化或异常，可能原因是什么]

### 输出文件
| 文件 | 内容描述 |
|------|---------|
| [路径] | [描述] |

### 待确认
- [ ] [需要人工判断的关键问题]
- [ ] [下一步方向建议]
```

#### 关键规则

- **先提计划再执行**：不跳过用户批准直接跑实验
- **必须写具体数值**：不能写"Loss 降低了"，必须写"Loss 从 4500 降到 750"
- **分析必须有解释**：不能只描述现象，必须给出物理/数值层面的原因推测
- **不确定性必须标明**：如果数据不足或需要进一步验证，明确说出来
- **报告同时保存为文件**：`knowledge/experiments/<YYYYMMDD>-<slug>.md`
- **不要假装有 baseline**：如果没有可对比的基准，就只描述本轮结果本身

#### 当 baseline 出现后

随着项目积累，之前的实验结果自然形成 baseline。此时验证报告应升级：

```markdown
### 实验结果

| 指标 | baseline | 本轮结果 | 变化 | 说明 |
|------|---------|---------|------|------|
| [指标] | [历史最优值] | [本轮值] | [+/- X%] | [分析] |

### 与 baseline 对比分析
- [为什么变好了 — 确认改进方向]
- [为什么变差了 — 可能原因，是否需要回滚]
- [如果在误差范围内 — 改动无明显影响，是否保留]
```

**baseline 的选取规则**：
- 优先选同一实验条件下的历史最优结果
- 如果换了配置（如 v_spread 不同），选相同配置下的上一次结果
- 实验记录文件（`knowledge/experiments/` 下）是找 baseline 的第一来源

### 实验记录管理

`knowledge/experiments/` 目录下的文件命名：`YYYYMMDD-<简短描述>.md`

每份报告独立成文，方便以后查阅和对比。积累多了以后，自然形成可追溯的实验历史。

---

## Behavior Rules

1. **Phase 0 is mandatory.** Read papers → read code → map paper to code → report findings → get approval. Never skip ahead.
2. **Always assess scale before creating.** Ask the user if unsure. Default to the tier below what the code suggests — you can always upgrade.
3. **Report analysis findings before creating.** The user should know what duplicated code was found, what modules were identified, and why a tier was chosen.
4. **Keep CLAUDE.md thin.** If you're tempted to write more than 80 lines, move content to knowledge cards.
5. **Don't delete existing code.** Extract to shared/ but keep original files as thin wrappers that import from shared. This preserves git blame and avoids breaking imports.
6. **Verify compatibility.** After extracting shared primitives, load an old checkpoint or run an existing test to prove nothing broke.
7. **Use the shared workflow's structured card format.** Every knowledge card needs frontmatter with 类型, 标签, and 依赖.

---

## Quick Reference: When to create what

| Situation | Action |
|-----------|--------|
| Single script, one author | Tier 1: CLAUDE.md only |
| 2+ scripts with duplicated code | Tier 2: Extract to shared/ |
| Multiple modules, multi-agent | Tier 2: Full knowledge cards + agent routing |
| Long-term research, experiments | Tier 3: Add tests + experiment tracking |
| User says "organize my project" | Assess → Report findings → Propose tier → Get approval → Create |
| User says "I want to add X feature" | Read CLAUDE.md routing table → Go to right knowledge card → Find code entry → Edit |
