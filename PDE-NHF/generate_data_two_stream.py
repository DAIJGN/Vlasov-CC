# 双流不稳定性 PIC 数据生成脚本
# 基于 generate_data.py 改造，生成双流不稳定性训练数据

import numpy as np
import argparse


class Parser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='双流不稳定性 PIC 数据生成')
        self.parser.add_argument('-SEED', default=1, type=int, dest='SEED',
                                 help='随机种子')
        self.parser.add_argument('-FOLDER_DATA', default='data/two_stream/', type=str, dest='FOLDER_DATA',
                                 help='数据保存目录')
        self.parser.add_argument('-N_EXAMPLES', default=1000, type=int, dest='N_EXAMPLES',
                                 help='生成的样本数量')
        self.parser.add_argument('-N_PARTICLES', default=1000, type=int, dest='N_PARTICLES',
                                 help='每个样本的粒子数')
        self.parser.add_argument('-MIN_V_STREAM', default=0.8, type=float, dest='MIN_V_STREAM',
                                 help='最小束流速度')
        self.parser.add_argument('-MAX_V_STREAM', default=1.5, type=float, dest='MAX_V_STREAM',
                                 help='最大束流速度')
        self.parser.add_argument('-MIN_V_SPREAD', default=0.01, type=float, dest='MIN_V_SPREAD',
                                 help='最小热速度展宽')
        self.parser.add_argument('-MAX_V_SPREAD', default=0.05, type=float, dest='MAX_V_SPREAD',
                                 help='最大热速度展宽')
        self.parser.add_argument('-MIN_A_PERTURB', default=0.001, type=float, dest='MIN_A_PERTURB',
                                 help='最小空间扰动幅度')
        self.parser.add_argument('-MAX_A_PERTURB', default=0.01, type=float, dest='MAX_A_PERTURB',
                                 help='最大空间扰动幅度')
        self.args = self.parser.parse_args()


if __name__ == "__main__":
    parser = Parser()

    random_seed = parser.args.SEED
    folder_data = parser.args.FOLDER_DATA
    n = parser.args.N_EXAMPLES
    N = parser.args.N_PARTICLES

    # 物理参数（与 PINN 双流算例一致）
    L = 10.0        # 域长度 (λ_D)
    Nx = 128        # 空间网格点数
    dx = L / Nx     # 网格间距
    T = 10.0        # 总模拟时间 (ω_p^{-1})
    dt = 0.1        # 时间步长
    total_steps = int(T / dt)  # 总步数 = 100

    np.random.seed(random_seed)

    # 生成条件参数
    min_v_stream, max_v_stream = parser.args.MIN_V_STREAM, parser.args.MAX_V_STREAM
    v_stream = np.random.uniform(low=min_v_stream, high=max_v_stream, size=(n, 1))

    min_v_spread, max_v_spread = parser.args.MIN_V_SPREAD, parser.args.MAX_V_SPREAD
    v_spread = np.random.uniform(low=min_v_spread, high=max_v_spread, size=(n, 1))

    min_A, max_A = parser.args.MIN_A_PERTURB, parser.args.MAX_A_PERTURB
    A_perturb = np.random.uniform(low=min_A, high=max_A, size=(n, 1))

    # Cond: [v_stream, v_spread, A_perturb]  (n, 3)
    Cond = np.concatenate((v_stream, v_spread, A_perturb), axis=1)
    np.save(folder_data + 'Cond.npy', Cond)

    # PIC 模拟函数
    def compute_charge_density(x):
        """CIC 电荷沉积，返回归一化的电荷密度"""
        rho = np.zeros(Nx)
        q_p = L / N  # 粒子电荷权重，使平均密度 = 1（匹配离子背景）

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

    def compute_electric_field(rho):
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

    def interpolate_field(x, E_grid):
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
            # 不够则补充均匀采样
            extra = np.random.uniform(0, L, N - len(x_accepted))
            x_accepted = np.concatenate([x_accepted, extra])
        return x_accepted[:N]

    # 快照保存步数
    save_steps = [0, 25, 50, 75, 100]  # t = 0, 2.5, 5.0, 7.5, 10.0
    save_keys = ['00', '25', '50', '75', '100']

    # 预分配数组
    Q_snapshots = {k: np.zeros((n, N)) for k in save_keys}
    P_snapshots = {k: np.zeros((n, N)) for k in save_keys}

    print(f"开始生成 {n} 个双流不稳定性 PIC 样本...")
    print(f"  域长 L={L}, 网格 Nx={Nx}, 粒子数 N={N}")
    print(f"  总时间 T={T}, dt={dt}, 总步数={total_steps}")
    print(f"  v_stream ∈ [{min_v_stream}, {max_v_stream}]")
    print(f"  v_spread ∈ [{min_v_spread}, {max_v_spread}]")
    print(f"  A_perturb ∈ [{min_A}, {max_A}]")

    for i in range(n):
        if (i + 1) % 100 == 0:
            print(f'{i + 1}/{n}')

        vs = v_stream[i, 0]
        vsp = v_spread[i, 0]
        Ap = A_perturb[i, 0]

        # 初始化粒子位置：均匀分布 + 空间扰动
        x = sample_two_stream_positions(N, L, Ap)

        # 初始化粒子速度：双流分布
        half = N // 2
        v = np.zeros(N)
        v[:half] = vs + np.random.randn(half) * vsp
        v[half:] = -vs + np.random.randn(N - half) * vsp

        # 保存初始状态 (t=0)
        Q_snapshots['00'][i] = x.copy()
        P_snapshots['00'][i] = v.copy()

        # 初始电场
        rho = compute_charge_density(x)
        E_grid = compute_electric_field(rho)
        E = interpolate_field(x, E_grid)

        # 第一次半加速 (与 PDE-NHF 原始代码一致的蛙跳格式)
        v += 0.5 * dt * E

        # 主循环：漂移 → 算场 → 加速
        for step in range(1, total_steps + 1):
            # 漂移步
            x = (x + dt * v) % L

            # 计算新电场
            rho = compute_charge_density(x)
            E_grid = compute_electric_field(rho)
            E = interpolate_field(x, E_grid)

            # 半加速
            v += 0.5 * dt * E

            # 保存快照
            for sk, key in zip(save_steps, save_keys):
                if step == sk:
                    Q_snapshots[key][i] = x.copy()
                    P_snapshots[key][i] = v.copy()

    # 保存所有快照
    for key in save_keys:
        np.save(folder_data + f'Q{key}.npy', Q_snapshots[key])
        np.save(folder_data + f'P{key}.npy', P_snapshots[key])
        print(f'已保存 Q{key}.npy, P{key}.npy')

    print(f'数据生成完成！共 {n} 个样本，保存至 {folder_data}')
