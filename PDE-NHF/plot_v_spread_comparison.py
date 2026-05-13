"""
独立脚本：不同速度展宽 v_spread 的两流不稳定性 PIC 模拟对比图
使用 generate_data_two_stream.py 中的 PIC 核心代码
生成 5 行 x 3 列的大图 (5个 v_spread 值 x 3个时间点)
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


# =============================================================================
# PIC 模拟核心函数（从 generate_data_two_stream.py 复制）
# =============================================================================

def compute_charge_density(x, Nx, dx, L, N_particles):
    """CIC 电荷沉积，返回归一化的电荷密度"""
    rho = np.zeros(Nx)
    q_p = L / N_particles  # 粒子电荷权重，使平均密度 = 1（匹配离子背景）

    for xi in x:
        i = int(xi / dx)
        frac = (xi - i * dx) / dx
        iL = i % Nx
        iR = (i + 1) % Nx
        rho[iL] += (1 - frac) * q_p
        rho[iR] += frac * q_p

    rho /= dx
    rho -= np.mean(rho)  # 强制全局电中性
    return rho


def compute_electric_field(rho, Nx, dx):
    """FFT 谱方法求解 Poisson 方程，返回电场 E(x)"""
    k = np.fft.fftfreq(Nx, d=dx) * 2 * np.pi
    rho_k = np.fft.fft(rho)
    rho_k[0] = 0.0  # k=0 模式设为零

    with np.errstate(divide='ignore', invalid='ignore'):
        phi_k = np.zeros_like(rho_k, dtype=complex)
        nonzero_k = k != 0
        phi_k[nonzero_k] = rho_k[nonzero_k] / (k[nonzero_k] ** 2)

    E_k = -1j * k * phi_k
    E_k[0] = 0.0
    E = np.real(np.fft.ifft(E_k))
    return E


def interpolate_field(x, E_grid, Nx, dx):
    """CIC 插值，将网格电场插值到粒子位置"""
    E_interp = np.zeros_like(x)
    for idx, xi in enumerate(x):
        left = int(xi / dx) % Nx
        right = (left + 1) % Nx
        frac = (xi - left * dx) / dx
        E_interp[idx] = (1 - frac) * E_grid[left] + frac * E_grid[right]
    return E_interp


def sample_two_stream_positions(N, L, A, seed=None):
    """
    从 f(x) ∝ 1 + A*cos(2π*x/L) 分布采样粒子位置
    使用 rejection sampling（对小 A 高效）
    """
    if seed is not None:
        np.random.seed(seed)
    x_candidates = np.random.uniform(0, L, int(N * (1 + A) * 2))
    fx = 1.0 + A * np.cos(2 * np.pi * x_candidates / L)
    accept = np.random.rand(len(x_candidates)) < (fx / (1.0 + A))
    x_accepted = x_candidates[accept]
    if len(x_accepted) < N:
        extra = np.random.uniform(0, L, N - len(x_accepted))
        x_accepted = np.concatenate([x_accepted, extra])
    return x_accepted[:N]


def run_pic_simulation(v_spread, v_stream=1.0, A_perturb=0.005,
                       L=10.0, Nx=128, N_particles=1000, T=10.0, dt=0.1,
                       seed=42):
    """
    运行一次两流不稳定性 PIC 模拟
    返回 dict: {time_label: (x_array, v_array)} 快照
    """
    dx = L / Nx
    total_steps = int(T / dt)

    np.random.seed(seed)

    # 初始化粒子位置：均匀分布 + 空间扰动
    x = sample_two_stream_positions(N_particles, L, A_perturb)

    # 初始化粒子速度：双流分布
    half = N_particles // 2
    v = np.zeros(N_particles)
    v[:half] = v_stream + np.random.randn(half) * v_spread
    v[half:] = -v_stream + np.random.randn(N_particles - half) * v_spread

    snapshots = {}
    snapshots[0] = (x.copy(), v.copy())

    # 初始电场
    rho = compute_charge_density(x, Nx, dx, L, N_particles)
    E_grid = compute_electric_field(rho, Nx, dx)
    E = interpolate_field(x, E_grid, Nx, dx)

    # 第一次半加速（与 generate_data_two_stream.py 一致的蛙跳格式）
    v += 0.5 * dt * E

    # 主循环：漂移 -> 算场 -> 加速
    for step in range(1, total_steps + 1):
        # 漂移步
        x = (x + dt * v) % L

        # 计算新电场
        rho = compute_charge_density(x, Nx, dx, L, N_particles)
        E_grid = compute_electric_field(rho, Nx, dx)
        E = interpolate_field(x, E_grid, Nx, dx)

        # 半加速
        v += 0.5 * dt * E

        # 保存 t=5 (step 50) 和 t=10 (step 100) 的快照
        if step == 50:
            snapshots[5] = (x.copy(), v.copy())
        if step == 100:
            snapshots[10] = (x.copy(), v.copy())

    return snapshots


# =============================================================================
# 主程序
# =============================================================================

if __name__ == "__main__":
    # 固定参数
    V_STREAM = 1.0
    A_PERTURB = 0.005
    L = 10.0
    Nx = 128
    N_PARTICLES = 1000
    T = 10.0
    DT = 0.1
    SEED = 42

    # 要对比的 v_spread 值
    v_spread_list = [0.02, 0.05, 0.1, 0.3, 0.5]
    time_points = [0, 5, 10]  # 单位: omega_p^{-1}

    n_rows = len(v_spread_list)
    n_cols = len(time_points)

    # 创建大图：5 行 3 列，共享坐标轴范围
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 20),
                             sharex=True, sharey=True)

    # 全局标题
    fig.suptitle(f'Two-Stream Instability: Phase Space vs. Velocity Spread\n'
                 f'v_stream = {V_STREAM}, A_perturb = {A_PERTURB}, '
                 f'L = {L}, Nx = {Nx}, N_p = {N_PARTICLES}, T = {T}, dt = {DT}',
                 fontsize=14, fontweight='bold', y=0.99)

    print("=" * 70)
    print("Two-Stream Instability: v_spread Comparison")
    print(f"  Fixed params: v_stream={V_STREAM}, A_perturb={A_PERTURB}")
    print(f"  L={L}, Nx={Nx}, N_particles={N_PARTICLES}, T={T}, dt={DT}")
    print("=" * 70)

    # 预计算所有模拟结果（方便调试和重用）
    all_snapshots = {}
    for row_idx, v_spread in enumerate(v_spread_list):
        alpha = V_STREAM / v_spread
        print(f"\n[v_spread={v_spread:.3f}, alpha={alpha:.1f}] Running PIC simulation...")

        snapshots = run_pic_simulation(
            v_spread=v_spread,
            v_stream=V_STREAM,
            A_perturb=A_PERTURB,
            L=L, Nx=Nx, N_particles=N_PARTICLES,
            T=T, dt=DT, seed=SEED
        )
        all_snapshots[v_spread] = snapshots

        for col_idx, t in enumerate(time_points):
            ax = axes[row_idx, col_idx]
            x_snap, v_snap = snapshots[t]

            # 绘制相空间散点图
            ax.scatter(x_snap, v_snap, s=1.5, c='navy', alpha=0.5, edgecolors='none',
                       rasterized=True)
            ax.set_xlim(0, L)
            ax.set_ylim(-2.5, 2.5)
            ax.grid(True, alpha=0.3, linestyle='--')

            # ---- 列标题：第一行标注时间 ----
            if row_idx == 0:
                ax.set_title(f't = {t}', fontsize=13, fontweight='bold', pad=8)

            # ---- 行标签：第一列标注 v_spread 和 alpha ----
            if col_idx == 0:
                # 用 text 在右上角内部标注参数，美观且不占用轴外空间
                ax.text(0.97, 0.96,
                        f'v_spread = {v_spread:.2f}\nalpha = {alpha:.1f}',
                        transform=ax.transAxes, fontsize=9,
                        verticalalignment='top', horizontalalignment='right',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                                  alpha=0.85, edgecolor='gray', linewidth=0.5))

            # ---- 坐标轴标签：只在外围显示 ----
            if row_idx == n_rows - 1:
                ax.set_xlabel('x', fontsize=11)
            if col_idx == 0:
                ax.set_ylabel('v', fontsize=11)

        print(f"  -> Done (t=0 particles={len(snapshots[0][0])}, "
              f"t=10 v_std={np.std(snapshots[10][1]):.3f})")

    plt.tight_layout(pad=1.2, rect=[0, 0, 1, 0.97])  # 给 suptitle 留空间

    # 保存图片
    output_path = 'data/two_stream/v_spread_comparison.png'
    fig.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n图片已保存到: {output_path}")
    print("完成！")
