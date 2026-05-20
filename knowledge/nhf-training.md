---
类型: tuning
标签: [NHF, 训练, KL散度, 损失函数, 先验分布]
依赖: [PyTorch, deepset-potential, pde-nhf-overview]
---
# NHF 训练 — KL 散度损失与先验设计

## 摘要

PDE-NHF 的训练目标是最小化 KL 散度：将最终时刻的粒子分布通过反向蛙跳积分推回初始时刻，要求推回后的分布与先验分布一致。损失函数 = 负对数先验概率的期望。关键是选择与物理问题匹配的先验分布。

## 前提条件

- 已生成训练数据（Q25/P25/Cond）
- 已定义好势能网络和蛙跳积分器
- 了解所求解物理问题的初始分布

## 训练流程

```
1. 从 data loader 取一批 (q_final, p_final, cond)
2. 前向传播：反向蛙跳 L 步，dt 取负值
   q_final, p_final → leapfrog(L, -dt) → q0, p0
3. 计算先验 log 概率：
   log_prob_q0 + log_prob_p0
4. 损失 = -mean(log_prob)
5. 反向传播，更新 V_net 参数
```

## 先验分布设计（核心）

### 原始 Gauss 先验（generate_data.py）

```python
# q0 ~ N(mu_q=64, sigma_q²)
# p0 ~ N(mu_p=0, sigma_p²)
prior_q = D.Normal(loc=64.0, scale=sigma_q)
prior_p = D.Normal(loc=0.0, scale=sigma_p)
loss = -(log_pi_q0 + log_pi_p0).mean()
```

### 双流混合 Gauss 先验（train_model_two_stream.py）

```python
# p0 ~ 0.5*N(+v_stream, v_spread²) + 0.5*N(-v_stream, v_spread²)
lp1 = D.Normal(v_stream, v_spread).log_prob(p0)
lp2 = D.Normal(-v_stream, v_spread).log_prob(p0)
log_pi_p0 = logsumexp([lp1+log(0.5), lp2+log(0.5)], dim=-1).sum(dim=1)

# q0 ~ U(0, L_domain)  ← 均匀分布，常数项
log_pi_q0 = -log(L_domain) * N_particles
```

### 关键数值技巧：logsumexp

直接 `log(0.5*N1 + 0.5*N2)` 容易下溢。用 `logsumexp` 在 log 空间计算：
```
log(0.5*N1 + 0.5*N2) = logsumexp([log(N1)+log(0.5), log(N2)+log(0.5)])
```

## 超参数

| 参数 | 原始 Gauss | 双流 vspread=0.1 |
|------|-----------|-----------------|
| L (蛙跳步数) | 25 | 10 |
| dt (训练时取负) | -0.04 | -0.25 |
| N_train | 20000 | 400 |
| batch_size | 128 | 128 |
| lr | 3e-4 | 3e-4 |
| epochs | 200 | 200 |
| 理论最优 Loss | ~log(σ_q·σ_p) | 104 (= -log(L_domain)·N) |

## 梯度放大小心

v_spread 出现在 Normal 的 scale 中。`log_prob` 对 p0 的梯度 ∝ 1/v_spread²。当 v_spread 很小（如 0.02）时梯度放大 2500×，导致训练不稳定。

**缓解方法**：
- 增大 v_spread（≥0.1）
- 降低学习率
- 梯度裁剪
- 课程退火（先大 v_spread 再逐步缩小）

## 边界限制

- 均匀位置先验不提供训练信号（常数项），仅速度先验驱动训练
- 蛙跳步数和 dt 需覆盖完整的动力学时间窗口
- v_spread 太小会导致梯度爆炸

## 相邻模块

- [[deepset-potential]] — 被训练的势能网络
- [[pde-nhf-overview]] — 完整数据流
- [[two-stream]] — 双流先验的物理背景
- [[experiments/vspread-comparison]] — v_spread 对比实验
