---
类型: primitive
标签: [PDE-NHF, Normalizing Flow, Hamiltonian, Vlasov, 相空间]
依赖: [PyTorch, numpy, shared/pic]
---
# PDE-NHF — Hamiltonian Normalizing Flows 方法

## 摘要

用 Normalizing Flow 学习 Hamiltonian 系统的相空间变换。网络学习一个标量势能 V(q)，通过蛙跳积分器进行反向/正向动力学演化。训练目标是最小化初始先验分布与反向推演的负对数似然（KL 散度）。与 PINN 不同，PDE-NHF 是一个替代模型，需要大量随机初始条件的数据集。

## 前提条件

- 必须有 PIC 模拟生成的训练数据（`generate_data.py` 或 `generate_data_two_stream.py`）
- 数据格式：Q25.npy, P25.npy, Cond.npy（最终时刻位置、动量、条件参数）
- 训练需要 GPU 内存（Deep Set 架构 ~26 万参数）
- Python 环境需 PyTorch + numpy + matplotlib

## 代码入口

| 文件 | 功能 |
|------|------|
| `PDE-NHF/generate_data.py` | 原始 Gauss 先验数据生成（mu_q=64, sigma_q/p 变化） |
| `PDE-NHF/generate_data_two_stream.py` | 双流不稳定性数据生成（v_stream, v_spread, A 变化） |
| `PDE-NHF/train_model.py` | 原始 Gauss 先验 NHF 训练 |
| `PDE-NHF/train_model_two_stream.py` | 双流 NHF 训练（混合 Gauss 先验 + 均匀位置先验） |
| `PDE-NHF/evaluate_two_stream.py` | 加载模型正向积分，计算 W1 距离，可视化 |
| `PDE-NHF/post_process.ipynb` | Jupyter 后处理评估 notebook |
| `PDE-NHF/compare_v_spread.py` | v_spread 三组对比评估脚本 |

## 数据流（三阶段）

```
阶段1 生成数据:
  随机初始条件(q0~N(μ_q,σ_q²), p0~N(μ_p,σ_p²))
  → PIC模拟 25 Leapfrog步 → 保存 Q/P 轨迹
  → 输出: data/Q*.npy, P*.npy, Cond.npy

阶段2 训练:
  加载 Q25/P25/Cond → NeuralHamiltonianFlow
  → 反向蛙跳积分(25步) → 计算KL损失
  → 保存: models/model_final, *_loss_final.npy

阶段3 评估:
  加载模型 → 正向积分 → 对比初始先验 → W1距离
```

## 核心架构

- **势能网络**：Deep Set 置换不变架构
- **蛙跳积分器**：半加速→全漂移→半加速，可学习质量参数 a
- **训练方向**：反向（从 t=T 回到 t=0），dt 取负值
- **损失**：KL 散度 = -(log_prior_q + log_prior_p)
- **参数量**：约 26 万

## 关键差异（vs PINN）

| 特性 | PDE-NHF | PINN |
|------|---------|------|
| Poisson 求解 | φ_k = ρ_k/k² → E_k = -ikφ_k | E_hat = rho_hat/(1j*kx) |
| 训练目标 | KL 散度（负对数似然） | MSE + PDE 残差 |
| 数据需求 | 大量随机初始条件 | 单次 PIC 模拟的连续 f(t,x,v) |
| 时间推进 | 蛙跳积分器 | 无（网络内蕴时间） |

## 边界限制

- 仅支持 1D Vlasov-Poisson 方程
- 周期性边界条件（x 方向）
- 蛙跳积分器步数和步长需匹配合适的时间窗口
- 训练需要 domain_length 参与 loss 计算（均匀位置先验）

## 相邻模块

- [[pinn-overview]] — PINN 方法概述
- [[deepset-potential]] — Deep Set 网络架构细节
- [[nhf-training]] — NHF 训练原理与损失函数
- [[pic-solver]] — 底层 PIC 求解器
- [[two-stream]] — 双流不稳定性算例
