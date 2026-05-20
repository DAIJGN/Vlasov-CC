"""蛙跳（Leapfrog）积分器 — 保持辛结构的粒子推进方案

标准 Leagfrog 格式：
  半步加速: v(t+dt/2) = v(t) - 0.5*dt*E(t)
  全步漂移: x(t+dt) = x(t) + dt*v(t+dt/2)
  重算电场: E(t+dt) from x(t+dt)
  半步加速: v(t+dt) = v(t+dt/2) - 0.5*dt*E(t+dt)

特性：时间可逆，保持相空间体积（辛结构），二阶精度。
"""

import numpy as np


def leapfrog_half_kick(v, E, dt):
    """半步加速（kick）：v ← v - 0.5*dt*E"""
    return v - 0.5 * dt * E


def leapfrog_full_drift(x, v, dt, L):
    """全步漂移（drift）：x ← (x + dt*v) % L（周期性边界）"""
    return (x + dt * v) % L


def leapfrog_step(x, v, E_func, dt, L):
    """单个 Leapfrog 步（半加速 → 全漂移 → 半加速）

    Args:
        x: 粒子位置，shape (Np,)
        v: 粒子速度，shape (Np,)
        E_func: 电场函数，signature E_func(x) -> (E_grid, E_particles)
                返回网格电场和粒子位置上的电场
        dt: 时间步长
        L: 域长度（用于周期性边界）

    Returns:
        x_new, v_new: 更新后的位置和速度
    """
    # 第一步：半步加速（使用当前电场）
    E_grid, E_p = E_func(x)
    v = leapfrog_half_kick(v, E_p, dt)

    # 第二步：全步漂移
    x = leapfrog_full_drift(x, v, dt, L)

    # 第三步：重算电场并半加速
    E_grid, E_p = E_func(x)
    v = leapfrog_half_kick(v, E_p, dt)

    return x, v


def leapfrog_multi_step(x, v, E_func, dt, L, n_steps, save_steps=None):
    """多步 Leagfrog 积分，可选指定步数保存快照

    Args:
        x, v: 初始位置和速度
        E_func: 电场函数 E_func(x) -> (E_grid, E_p)
        dt: 时间步长
        L: 域长度
        n_steps: 总步数
        save_steps: 需要保存快照的步号集合（1-indexed），None 表示不保存

    Returns:
        snapshots: dict，key 为步号，value 为 (x, v) 元组
        总是包含最后一步
    """
    if save_steps is None:
        save_steps = set()
    snapshots = {}

    for step in range(1, n_steps + 1):
        x, v = leapfrog_step(x, v, E_func, dt, L)
        if step in save_steps:
            snapshots[step] = (x.copy(), v.copy())

    return x, v, snapshots
