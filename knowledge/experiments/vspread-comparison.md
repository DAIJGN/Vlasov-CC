---
类型: experiment
标签: [实验, v_spread, 对比, benchmark, 训练]
依赖: [two-stream, nhf-training, pde-nhf-overview]
---
# v_spread 受控对比实验

## 摘要

通过固定 v_spread=0.05/0.1/0.2 三组实验，量化热速度展宽对 PDE-NHF 双流训练效果的影响。核心发现：v_spread=0.1 是最优平衡点（Loss 750，W1(v)=0.028）。

## 实验设计

### 动机

原始双流参数 v_spread∈[0.01,0.05] 导致的梯度放大 ∝1/v_spread² 造成训练困难（Loss≈4500）。需要找到既有物理不稳定性又训练可行的 v_spread。

### 三组配置

| 组 | v_spread | α 范围 | Penrose | 梯度放大 | 样本数 |
|----|---------|--------|---------|---------|--------|
| A | 0.05 | 16–30 | ✓ | 400× | 500 |
| B | 0.10 | 8–15 | ✓ | 100× | 500 |
| C | 0.20 | 4–7.5 | ✓ | 25× | 500 |

### 固定参数

- N_PARTICLES=256, L=10, Nx=128
- T=2.5 (25步, dt=0.1)
- v_stream∈[0.8,1.5] 变化
- 训练：N_TRAIN=400, N_VAL=100, L=10, dt=0.25, batch=64, lr=3e-4, epochs=200

## 结果（2026-05-13）

| v_spread | α(test) | Train Loss (min) | W1(v) | W1(x) |
|----------|---------|-----------------|-------|-------|
| 0.05 | 16.8 | 1246 | 0.079 | 1.39 |
| **0.10** | 11.1 | **750** | **0.028** | 3.44 |
| 0.20 | 5.7 | 760 | 0.035 | 3.67 |

## 关键发现

1. **v_spread=0.1 是最优平衡点**：Loss 最低（750），W1(v) 最小（0.028，接近原始论文水准）
2. **Loss 改善 6×**：从 4500（v_spread=0.02）→ 750（v_spread=0.1）
3. **W1(x) 仍偏高**（3–4）：位置先验是均匀分布，无训练信号驱动收敛
4. **v_spread=0.05 更难**（Loss 1246）：梯度放大效应已开始显现
5. **v_spread=0.2 未继续改善**：α 接近临界值，不稳定性减弱，动力学信号变弱

## 输出文件

| 文件 | 说明 |
|------|------|
| `models/two_stream/v_spread_comparison_results.png` | 3×3 对比图（Loss+PIC+HNF） |
| `models/two_stream/vspread_*/model_final` | 三组训练模型权重 |
| `models/two_stream/vspread_*/*_loss_final.npy` | 训练/验证 loss 记录 |
| `data/two_stream/vspread_*/` | 三组原始 PIC 数据 |
| `compare_v_spread.py` | 对比评估脚本 |

## 后续方向

- **阶段 2**：v_spread=0.1 全规模训练（5000+ 样本，epochs=300–500）
- **阶段 3**（可选）：课程退火 v_spread 0.2→0.1→0.05→0.02
- **阶段 4**（可选）：扩展时间窗口 T=2.5→5.0→7.5→10.0

## 相邻模块

- [[two-stream]] — 双流物理背景
- [[nhf-training]] — 训练原理与梯度放大的理论分析
- [[pde-nhf-overview]] — 完整数据流
