---
类型: primitive
标签: [DeepSet, 神经网络, 置换不变性, 势能, PyTorch]
依赖: [PyTorch]
---
# Deep Set 势能网络

## 摘要

基于 Deep Set 架构的标量势能网络。核心特性是**置换不变性**——交换任意两个粒子的位置，输出的势能不变。这通过 "per-particle embedding → sum-pooling → global MLP" 的结构实现。

## 前提条件

- PyTorch
- 输入形状：(B, N) — B 个 batch，每个 N 个粒子
- 粒子在 x 空间的一维坐标

## 代码入口

| 文件 | 行号 | 说明 |
|------|------|------|
| `PDE-NHF/train_model.py:117-135` | 原始 Gauss 先验版 | hidden_dim=256 |
| `PDE-NHF/train_model_two_stream.py:111-130` | 双流版 | hidden_dim=256 |
| `PDE-NHF/train_quick_test.py:33-40` | 快速测试版 | hidden_dim=256 |

## 架构

```
输入 q: (B, N)
  ↓
q_centered = q - mean(q, dim=1)  ← 去均值保证平移不变性
  ↓
q_centered.unsqueeze(-1): (B, N, 1)
  ↓
φ: Linear(1,256) → Softplus → Linear(256,256)  ← 每个粒子独立嵌入
  ↓
sum(dim=1): (B, 256)  ← 加和池化（置换不变的关键）
  ↓
ρ: Linear(256,256) → Softplus → Linear(256,1) → squeeze: (B,)
  ↓
输出: 标量势能 V(q)
```

## 为什么用 Deep Set

Vlasov 方程的粒子是全同的，交换任意两个粒子物理上不可区分。Deep Set 的 sum-pooling 天然保证这个对称性，避免了普通 MLP 需要强加置换不变性的问题。

## 参数量

- hidden_dim=256 时约 26 万参数
- φ 层：1×256 + 256 + 256×256 + 256 = 66,048
- ρ 层：256×256 + 256 + 256×1 + 1 = 65,793
- 总计约 131,841（不含可学习质量参数 a）

## 边界限制

- 对粒子数量 N 不敏感（sum-pooling 可处理任意 N），但训练和推理时 N 应一致
- q_centered 操作意味着网络隐式要求粒子分布在有界域中
- 去均值可能掩盖长程有序结构（对某些物理问题）

## 相邻模块

- [[pde-nhf-overview]] — 此网络在 NHF 中的使用方式
- [[nhf-training]] — 如何训练该网络
- [[two-stream]] — 双流算例下的网络输入输出
