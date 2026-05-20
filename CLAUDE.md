# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言要求

所有对话、代码注释、文档编写必须使用中文。

## 项目概述

Vlasov-Poisson 方程数值求解研究项目，包含两种互补方法：
- **PINN/** — 物理信息神经网络（Zhang et al. 2023）
- **PDE-NHF/** — Hamiltonian Normalizing Flows（Souveton & Terrana）

## 知识路由（先读卡片，再改代码）

| 你要做什么 | 先读这张卡片 |
|-----------|-------------|
| 理解/修改 PINN 代码 | `knowledge/pinn-overview.md` |
| 理解/修改 PDE-NHF 代码 | `knowledge/pde-nhf-overview.md` |
| 处理双流不稳定性算例 | `knowledge/two-stream.md` |
| 了解 PIC 求解器实现 | `knowledge/pic-solver.md` |
| 了解 Deep Set 网络架构 | `knowledge/deepset-potential.md` |
| 了解 NHF 训练原理 | `knowledge/nhf-training.md` |
| 查阅实验记录 | `knowledge/experiments/` 目录 |

## 共享代码 (shared/)

写新脚本时优先从 `shared/` 导入，不要复制粘贴类定义：

| 模块 | 提供 |
|------|------|
| `shared.models.potential` | `Potential` — Deep Set 势能网络（唯一正确定义） |
| `shared.models.hamiltonian` | `NeuralHamiltonianFlow`, `TwoStreamPriorNHF`, `GaussPriorNHF` |
| `shared.pic.deposition` | `deposit_cic_vectorized`, `deposit_cic_loop`, `interp_field_cic` |
| `shared.pic.poisson` | `solve_poisson_pinn`, `solve_poisson_nhf` |
| `shared.pic.integrator` | `leapfrog_step`, `leapfrog_multi_step` |
| `shared.pic.particles` | `init_uniform_positions`, `init_two_stream_velocities`, `init_perturbed_positions` |

**导入方式**（在 PDE-NHF/ 脚本中）：
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.models.hamiltonian import TwoStreamPriorNHF
```

## 常用命令

```bash
# PINN：生成数据 → 训练
cd PINN && python main.py && python data.py

# PDE-NHF（原始 Gauss 先验）：生成数据 → 训练
cd PDE-NHF
python generate_data.py -SEED=1 -N_EXAMPLES=32768 -N_PARTICLES=256 -MIN_STD_Q=0.5 -MAX_STD_Q=1.5 -MIN_STD_P=0.5 -MAX_STD_P=1.5
python train_model.py -SEED=1 -FOLDER_EXP='models/model/' -FOLDER_DATA='data/' -N_TRAINING=20000 -N_VALIDATION=6384 -L=25 -DT=0.04 -N_EPOCHS=200 -BATCH_SIZE=128 -LR=0.0003

# PDE-NHF（双流）：生成数据 → 训练 → 评估
python generate_data_two_stream.py
python train_model_two_stream.py
python evaluate_two_stream.py
```

## Agent 与 Skill

| Agent/Skill | 触发场景 |
|-------------|---------|
| `pinn-code-writer` | 编写/修改/调试 PINN 或 PDE-NHF Python 代码 |
| `code-explainer` | 解释代码逻辑、解读训练结果、代码与公式对照 |
| `paper-tutor` | 阅读 `论文/` 中 PDF 论文，中文解释核心思想 |
| `meeting-slide-generator` | 制作组会汇报 PPT（输出到 `ppt/`） |
| `weekly-report-assistant` | 生成周报（输出到 `周报/`） |
| `pptx` skill | 创建/编辑/读取 .pptx 文件 |
| `pdf` skill | 处理 PDF：合并、拆分、提取文本/表格、OCR |

使用方式：直接描述需求，系统自动匹配。也可明确指定 "让 xxx agent 帮我..."。

## 文件路径约定

- 出图优先保存到 `ppt/`，便于 PPT 脚本引用
- 训练输出（.npz/.pth/.npy）保存在各自项目子目录
- 周报：`周报/周报_YYYY_WW周.md`
- PPT 脚本：`ppt/generate_ppt_YYYYMMDD.py`
- 实验记录：`knowledge/experiments/`
