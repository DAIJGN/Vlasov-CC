"""FFT 谱方法求解 Poisson 方程

提供两种风格：
- solve_poisson_pinn: PINN 风格，E_hat = rho_hat / (1j * kx)，直接一步求电场
- solve_poisson_nhf: PDE-NHF 风格，φ_k = ρ_k/k² → E_k = -ik·φ_k，先求电势再求电场

两种方法数学等价（1D），但实现路径不同。
"""

import numpy as np


def solve_poisson_pinn(rho, L, Nx):
    """PINN 风格 FFT Poisson：直接求电场（一步）

    E_hat = rho_hat / (1j * kx)
    E_hat[0] = 0  （直流分量设为零）

    Args:
        rho: 电荷密度，shape (Nx,)
        L: 域长度
        Nx: 网格点数

    Returns:
        E: 电场，shape (Nx,)
    """
    rho_hat = np.fft.fft(rho)
    kx = 2 * np.pi * np.fft.fftfreq(Nx, d=L / Nx)

    E_hat = np.zeros_like(rho_hat, dtype=complex)
    with np.errstate(divide='ignore', invalid='ignore'):
        E_hat = rho_hat / (1j * kx)
    E_hat[0] = 0.0

    return np.real(np.fft.ifft(E_hat))


def solve_poisson_nhf(rho, dx, Nx):
    """PDE-NHF 风格 FFT Poisson：先求电势再求电场（两步）

    φ_k = ρ_k / k²
    E_k = -ik · φ_k
    k=0 模式显式设为零

    Args:
        rho: 电荷密度，shape (Nx,)
        dx: 网格间距
        Nx: 网格点数

    Returns:
        E: 电场，shape (Nx,)
    """
    k = np.fft.fftfreq(Nx, d=dx) * 2 * np.pi
    rho_k = np.fft.fft(rho)
    rho_k[0] = 0.0  # k=0 模式设为零，保证全局电中性

    with np.errstate(divide='ignore', invalid='ignore'):
        phi_k = np.zeros_like(rho_k, dtype=complex)
        nonzero_k = k != 0
        phi_k[nonzero_k] = rho_k[nonzero_k] / (k[nonzero_k] ** 2)

    E_k = -1j * k * phi_k
    E_k[0] = 0.0

    return np.real(np.fft.ifft(E_k))
