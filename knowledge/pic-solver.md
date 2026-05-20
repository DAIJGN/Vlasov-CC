---
类型: primitive
标签: [PIC, CIC, FFT, Poisson, Leapfrog, 粒子模拟]
依赖: [numpy]
---
# PIC 求解器 — 粒子云网格方法

## 摘要

Particle-in-Cell (PIC) 方法用宏粒子代表等离子体分布，通过 CIC 电荷沉积 → FFT Poisson 求解 → 电场插值 → Leapfrog 推进的循环进行模拟。两个项目（PINN 和 PDE-NHF）各自实现了 PIC 求解器，实现细节有差异。

## 前提条件

- numpy
- 1D 周期性边界条件
- 粒子数足够大以保证统计精度（通常 Np ≥ 10000）

## 代码入口

| 文件 | PIC 实现 | 特点 |
|------|---------|------|
| `PINN/main.py:26-65` | CIC 向量化版 | `np.add.at` 消除 for 循环，Np=100000 |
| `PDE-NHF/generate_data.py:68-122` | CIC for 循环版 | 逐个粒子沉积，Np=256 |
| `PDE-NHF/generate_data_two_stream.py:67-108` | CIC for 循环版 | 同上，双流初始化 |

## PIC 循环四步

```
1. CIC 电荷沉积: 粒子位置 → 网格电荷密度 ρ(x)
2. FFT Poisson: ρ(x) → FFT → ρ_k → E_k → IFFT → E(x)
3. CIC 电场插值: E(x) → 粒子位置上的 E_p
4. Leapfrog 推进: v ← v - E·dt, x ← x + v·dt
```

## Poisson 求解器差异（重要！）

| 项目 | 方法 | 公式 |
|------|------|------|
| **PINN** | 直接一步求电场 | `E_hat = rho_hat / (1j * kx)` |
| **PDE-NHF** | 先求电势再求电场 | `φ_k = ρ_k / k²` → `E_k = -ik φ_k` |

两种方法数学等价（对 1D），但实现路径不同。修改代码时不要混用。

## 蛙跳积分器 (Leapfrog)

```
半步加速: v(t+dt/2) = v(t) - 0.5*dt*E(t)
全步漂移: x(t+dt) = x(t) + dt*v(t+dt/2)
重算电场: E(t+dt) from x(t+dt)
半步加速: v(t+dt) = v(t+dt/2) - 0.5*dt*E(t+dt)
```

## 关键参数约定

| 参数 | PINN | PDE-NHF (原始) | PDE-NHF (双流) |
|------|------|--------------|--------------|
| L (域长) | 10 | 128 | 10 |
| Nx (网格) | 256 | 128 | 128 |
| Np (粒子) | 100000 | 256 | 1000 |
| dt | 0.125 | 0.04 | 0.1 |
| T (总时间) | 62.5 | 1.0 | 10.0 |
| 总步数 | 500 | 25 | 100 |

## 边界限制

- 仅支持 1D + 周期性边界
- 粒子数太少（<100）会导致统计噪声过大
- CIC 插值假设粒子在单个网格单元内，极端非均匀分布可能失准

## 相邻模块

- [[pinn-overview]] — PINN 如何使用 PIC
- [[pde-nhf-overview]] — PDE-NHF 如何使用 PIC
- [[two-stream]] — 双流初始化的 PIC 实现
