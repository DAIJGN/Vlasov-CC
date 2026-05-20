---
类型: primitive
标签: [双流不稳定性, Vlasov, 等离子体, Penrose判据, 相空间]
依赖: [numpy, pic-solver]
---
# 双流不稳定性 — 物理背景与参数空间

## 摘要

双流不稳定性（Two-Stream Instability）是等离子体物理中最经典的不稳定性之一。两束相向运动的电子束在速度空间中形成两个峰，通过波-粒子相互作用不稳定性增长，在相空间中形成涡旋结构（filamentation）。

## 物理设定

- 两束电子：速度分别为 +v_stream 和 -v_stream
- 热速度展宽：v_spread（高斯分布的 σ）
- 空间上：均匀背景，加上小幅余弦扰动 A·cos(2πx/L)
- 离子背景：均匀正电荷，密度 = 1

## 参数与稳定性

### Penrose 判据

对于双流分布函数，稳定性取决于 α = v_stream / v_spread：

- **α > 1.307**：不稳定（两峰分离足够远，可激发不稳定性）
- **α ≤ 1.307**：稳定（热展宽抑制不稳定性）

1.307 是双流色散关系的数值解，来自超越方程：
```
1 + (1/α²) - (√π/α)·e^(-α²)·Im[erf(iα)] = 0
```

### 关键参数

| 参数 | 取值范围 | 物理含义 |
|------|---------|---------|
| v_stream | 0.8–1.5 | 束流漂移速度 |
| v_spread | 0.01–0.5 | 热速度展宽（高斯σ） |
| α=v_stream/v_spread | >1.307 | 不稳定判据 |
| A_perturb | 0.001–0.01 | 空间扰动幅度 |
| L | 10 | 域长度 (λ_D) |

## 代码实现

### 速度初始化（双流分布）

```python
half = N // 2
v[:half] = v_stream + randn(half) * v_spread
v[half:] = -v_stream + randn(N-half) * v_spread
```

### 位置初始化（带扰动）

```python
# f(x) ∝ 1 + A*cos(2πx/L)
# 用 rejection sampling 从该分布采样
```

## PDE-NHF vs PINN 对比

| 特性 | PINN 双流 | PDE-NHF 双流 |
|------|----------|-------------|
| v_stream | 固定 ±1.0 | 随机 0.8–1.5 |
| v_spread | 固定 0.02 | 随机 0.01–0.05（原始）/ 可控 |
| 求解方式 | 直接拟合 f(t,x,v) | 学习相空间变换 |
| 时间窗口 | 0–62.5 | 0–2.5 (可扩展) |

## 相空间演化特征

1. **t=0**：两条水平带（±v_stream 处）
2. **t=2.5**：开始形成波状扰动
3. **t=5.0**：涡旋结构出现
4. **t=7.5–10**：涡旋合并，filamentation

## 边界限制

- 仅支持 1D + 周期性
- 粒子数太少（<500）时涡旋结构不明显
- v_spread 太小（<0.01）时粒子速度几乎单色，统计噪声大

## 相邻模块

- [[pinn-overview]] — PINN 处理双流
- [[pde-nhf-overview]] — PDE-NHF 处理双流
- [[pic-solver]] — PIC 底层实现
- [[nhf-training]] — 双流混合 Gauss 先验的损失函数设计
- [[experiments/vspread-comparison]] — v_spread 对比实验
