---
类型: primitive
标签: [PINN, Vlasov, 神经网络, 前向问题]
依赖: [PyTorch, numpy, PINN/main.py]
---
# PINN — 物理信息神经网络方法

## 摘要

用 PIC 粒子模拟生成 ground truth 分布函数 f(t,x,v)，再用全连接神经网络直接拟合 Vlasov 方程的解。网络同时输出 f 和电场 E，损失函数包含初始条件、边界条件、PDE 残差与数据锚点。

## 前提条件

- 必须先运行 `PINN/main.py` 生成 `pinn_vlasov_data.npz`
- 数据包含 500 个时间步的 f(t,x,v) 在 256×256 网格上的值
- Python 环境需 PyTorch + numpy + matplotlib

## 代码入口

| 文件 | 功能 |
|------|------|
| `PINN/main.py` | PIC 粒子模拟：双流不稳定性 → 生成 f(t,x,v) 训练数据 |
| `PINN/data.py` | 加载数据 → 重要性采样 → PINN_Vlasov 网络训练 → 推理对比 |
| `PINN/PIC_figure.py` | 独立生成高清 PIC 基准图 |

## 数据流

```
main.py: 粒子初始化(双流) → CIC 沉积 → FFT Poisson → Leapfrog 推进
  → 500步直方图 → f_data.npz

data.py: 加载 f_data.npz → 重要性采样(IC/BC/PDE点) → PINN_Vlasov网络
  → 组合损失训练(20k轮) → 推理评估 → 可视化
```

## 核心架构

- **网络**：8 层全连接 (3→100→100→...→2)，Tanh 激活
- **输入归一化**：t 映射到 [-1,1], x 映射到 [-1,1], v 映射到 [-1,1]
- **输出**：f_pred (分布函数) + E_pred (电场)
- **Poisson 求解**：FFT 谱方法，`E_hat = rho_hat / (1j * kx)`（直接一步求电场）
- **损失权重**：data=0.7, ic=0.1, bc=0.1, eq=0.1

## 物理参数

| 参数 | 值 | 含义 |
|------|-----|------|
| L | 10.0 | 计算域长度 (λ_D) |
| Nx | 256 | 空间网格数 |
| Np | 100000 | 宏粒子数 |
| dt | 0.125 | 时间步长 (ω_p⁻¹) |
| tEnd | 62.5 | 终止时间 |
| v_stream | ±1.0 | 双流漂移速度 |
| v_spread | 0.02 | 热速度展宽 |

## 边界限制

- 仅支持周期性边界条件（x 方向）
- 仅支持 1D Vlasov-Poisson 方程
- 不能用于逆问题（需要不同的网络输出和损失函数）

## 相邻模块

- [[pic-solver]] — PIC 求解器底层实现对比
- [[pde-nhf-overview]] — 另一种求解方法的概述
- [[two-stream]] — 双流不稳定性物理背景
