"""CIC（Cloud-in-Cell）电荷沉积与电场插值

提供两个版本：
- vectorized: 向量化实现，适合大规模粒子（Np >= 10000），PINN 使用
- loop: for 循环实现，适合小规模粒子（Np ~ 256），PDE-NHF 数据生成使用
"""

import numpy as np


def deposit_cic_vectorized(xp, w, dx, Nx):
    """向量化 CIC 电荷沉积（使用 np.add.at 消除 for 循环）

    Args:
        xp: 粒子位置数组，shape (Np,)
        w: 每个粒子的电荷权重，标量或 shape (Np,)
        dx: 网格间距
        Nx: 网格点数

    Returns:
        rho: 电荷密度数组，shape (Nx,)
    """
    rho = np.zeros(Nx)
    x_idx = xp / dx
    i = np.floor(x_idx).astype(int) % Nx
    ip = (i + 1) % Nx
    xi = x_idx - np.floor(x_idx)

    np.add.at(rho, i, w * (1 - xi))
    np.add.at(rho, ip, w * xi)

    return rho


def deposit_cic_loop(xp, w, dx, Nx):
    """for 循环版 CIC 电荷沉积（小粒子数时足够快，代码更易读）

    Args:
        xp: 粒子位置数组，shape (Np,)
        w: 每个粒子的电荷权重，标量
        dx: 网格间距
        Nx: 网格点数

    Returns:
        rho: 电荷密度数组，shape (Nx,)
    """
    rho = np.zeros(Nx)
    for xi in xp:
        i = int(xi / dx)
        frac = (xi - i * dx) / dx
        iL = i % Nx
        iR = (i + 1) % Nx
        rho[iL] += (1 - frac) * w
        rho[iR] += frac * w
    rho /= dx
    rho -= np.mean(rho)  # 强制全局电中性
    return rho


def interp_field_cic(xp, E_grid, dx, Nx):
    """CIC 电场插值（向量化版，适合所有规模）

    Args:
        xp: 粒子位置数组，shape (Np,)
        E_grid: 网格电场，shape (Nx,)
        dx: 网格间距
        Nx: 网格点数

    Returns:
        Ep: 粒子位置上的电场，shape (Np,)
    """
    x_idx = xp / dx
    i = np.floor(x_idx).astype(int) % Nx
    ip = (i + 1) % Nx
    xi = x_idx - np.floor(x_idx)

    Ep = E_grid[i] * (1 - xi) + E_grid[ip] * xi
    return Ep


def interp_field_cic_loop(xp, E_grid, dx, Nx):
    """CIC 电场插值（for 循环版，小粒子数时使用）

    Args:
        xp: 粒子位置数组，shape (Np,)
        E_grid: 网格电场，shape (Nx,)
        dx: 网格间距
        Nx: 网格点数

    Returns:
        Ep: 粒子位置上的电场，shape (Np,)
    """
    Ep = np.zeros_like(xp)
    for idx, xi in enumerate(xp):
        left = int(xi / dx) % Nx
        right = (left + 1) % Nx
        frac = (xi - left * dx) / dx
        Ep[idx] = (1 - frac) * E_grid[left] + frac * E_grid[right]
    return Ep
