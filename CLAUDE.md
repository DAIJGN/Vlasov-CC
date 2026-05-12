# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言要求

所有对话、代码注释、文档编写必须使用中文。

## 项目概述

这是一个 Vlasov-Poisson 方程数值求解的研究项目，包含两种互补的求解方法：

- **PINN/** — 物理信息神经网络方法（Zhang et al. 2023），用 PIC 粒子模拟生成 ground truth，再用神经网络学习分布函数 f(t,x,v)
- **PDE-NHF/** — Hamiltonian Normalizing Flows 方法（Souveton & Terrana），用 Normalizing Flow 学习 Hamiltonian 系统的相空间演化

两个方法解决的是同一个 1D Vlasov-Poisson 方程，但走的是完全不同的技术路线。

## 数据流架构

### PINN 数据流（两阶段）

```
PIC 模拟 (main.py)                    PINN 训练 (data.py)
─────────────────                    ──────────────────
粒子初始化 → 电荷沉积(CIC)          加载 f_data.npz
  → FFT 求解 Poisson → 电场插值       → 采样 IC/BC/PDE 点
  → Leapfrog 推进粒子                 → PINN_Vlasov 网络
  → 生成 f_data.npz                   → 组合损失训练
  → 保存 + 可视化                     → 推理评估 vs PIC 真值
```

**关键依赖**：`data.py` 依赖 `main.py` 生成的 `pinn_vlasov_data.npz`。修改 `main.py` 的模拟参数后，必须重新生成数据再训练。

### PDE-NHF 数据流（三阶段）

```
生成数据 (generate_data.py)    训练 (train_model.py)      评估 (post_process.ipynb)
────────────────────────────    ─────────────────────      ──────────────────────────
256 个随机初始条件              加载 Q25/P25/Cond.npy       加载训练好的模型
  → PIC 模拟 25 Leapfrog 步       → NeuralHamiltonianFlow    → 反向积分回初始条件
  → 保存 Q/P 轨迹                 → 训练 V_net 势能网络       → 对比初始分布
  → 输出到 data/                  → 保存到 models/
```

**关键依赖**：`train_model.py` 依赖 `generate_data.py` 生成的 `.npy` 文件。模型权重保存在 `models/model/` 下。

## 常用命令

### PINN 项目运行

```bash
# 第一步：生成 PIC 训练数据
cd PINN && python main.py
# 输出：pinn_vlasov_data.npz（训练数据）+ 相空间分布图

# 第二步：训练 PINN 模型
cd PINN && python data.py
# 输出：pinn_vlasov_weights.pth（模型权重）+ Loss 曲线 + 预测 vs 真值对比图

# 单独生成高清 PIC 基准图
cd PINN && python PIC_figure.py
# 输出：PIC_GroundTruth_HighRes.png
```

### PDE-NHF 项目运行

```bash
# 第一步：生成训练数据集
cd PDE-NHF
python generate_data.py -SEED=1 -N_EXAMPLES=32768 -N_PARTICLES=256 \
    -MIN_STD_Q=0.5 -MAX_STD_Q=1.5 -MIN_STD_P=0.5 -MAX_STD_P=1.5
# 输出：data/Q25.npy, data/P25.npy, data/Cond.npy 等

# 第二步：训练模型
python train_model.py -SEED=1 -FOLDER_EXP='models/model/' -FOLDER_DATA='data/' \
    -N_TRAINING=20000 -N_VALIDATION=6384 -L=25 -DT=0.04 \
    -N_EPOCHS=200 -BATCH_SIZE=128 -LR=0.0003
# 输出：models/model/model_final, training_loss_final.npy 等

# 第三步：后处理评估
# 用 Jupyter 打开 post_process.ipynb 运行
```

### Python 环境依赖

两个项目都需要：`torch`, `numpy`, `matplotlib`。PDE-NHF 额外需要 `argparse`（标准库）。

## 核心架构差异需注意

| 特性 | PINN | PDE-NHF |
|------|------|---------|
| 求解方式 | 神经网络直接拟合 f(t,x,v) | Normalizing Flow 学习相空间变换 |
| Poisson 求解 | FFT (1j*k 谱方法) | FFT (k² 谱方法, 先求 φ 再求 E) |
| 时间推进 | 无（网络内蕴时间） | Leapfrog 积分器 (L=25步) |
| 训练目标 | MSE(f_pred, f_true) + PDE 残差 | KL 散度 (负对数似然) |
| 数据需求 | 单次 PIC 模拟的连续 f(t,x,v) | 大量随机初始条件的粒子轨迹 |

**注意两个项目 Poisson 求解器的差异**：
- PINN 用 `E_hat = rho_hat / (1j * kx)`（直接一步求电场）
- PDE-NHF 用 `φ_k = ρ_k / k²`, `E_k = -ik φ_k`（先求电势再求电场）

## 自定义 Agent

本项目配置了 5 个专用 Agent（定义在 `.claude/agents/`），通过 `/agents` 命令创建：

| Agent | 触发场景 |
|-------|---------|
| `pinn-code-writer` | 编写/修改/调试 PINN 或 PDE-NHF 的 Python 代码 |
| `code-explainer` | 解释代码逻辑、解读训练结果、代码与公式对照 |
| `paper-tutor` | 阅读 `论文/` 中的 PDF 论文，用中文解释核心思想 |
| `meeting-slide-generator` | 制作组会汇报 PPT（输出到 `ppt/`） |
| `weekly-report-assistant` | 生成周报（输出到 `周报/`） |

使用方式：直接描述需求，系统会自动匹配对应 Agent 执行。也可以明确指定 "让 xxx agent 帮我..."。

## 文件路径约定

- 出图时优先保存到 `ppt/` 目录，便于 PPT 脚本引用
- 训练输出（.npz, .pth, .npy）保存在各自项目的根目录
- 周报按 `周报/周报_YYYY_WW周.md` 命名
- PPT 生成脚本按 `ppt/generate_ppt_YYYYMMDD.py` 命名
