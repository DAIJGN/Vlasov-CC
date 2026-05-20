"""粒子初始化 — 各种物理场景的初始相空间分布"""

import numpy as np


def init_uniform_positions(N, L, seed=None):
    """均匀空间分布

    Args:
        N: 粒子数
        L: 域长度

    Returns:
        x: shape (N,)，均匀分布在 [0, L)
    """
    rng = np.random if seed is None else np.random.RandomState(seed)
    return rng.rand(N) * L if seed is None else rng.uniform(0, L, N)


def init_perturbed_positions(N, L, A, seed=None):
    """从 f(x) ∝ 1 + A*cos(2πx/L) 分布采样（双流空间扰动）

    使用 rejection sampling。对小扰动幅度 A 效率高。

    Args:
        N: 粒子数
        L: 域长度
        A: 扰动幅度（如 0.001~0.01）
        seed: 随机种子

    Returns:
        x: shape (N,)
    """
    rng = np.random if seed is None else np.random.RandomState(seed)
    # 过采样因子：1 + A 保证足够候选
    n_candidates = int(N * (1 + A) * 2)
    x_candidates = rng.uniform(0, L, n_candidates) if seed is None else rng.uniform(0, L, n_candidates)
    fx = 1.0 + A * np.cos(2 * np.pi * x_candidates / L)
    accept = rng.rand(n_candidates) < (fx / (1.0 + A))
    x_accepted = x_candidates[accept]

    if len(x_accepted) < N:
        extra = rng.uniform(0, L, N - len(x_accepted)) if seed is None else rng.uniform(0, L, N - len(x_accepted))
        x_accepted = np.concatenate([x_accepted, extra])

    return x_accepted[:N]


def init_gaussian_velocities(N, mu, sigma, seed=None):
    """高斯速度分布

    Args:
        N: 粒子数
        mu: 平均速度
        sigma: 速度标准差

    Returns:
        v: shape (N,)
    """
    rng = np.random if seed is None else np.random.RandomState(seed)
    return mu + rng.randn(N) * sigma if seed is None else mu + rng.randn(N) * sigma


def init_two_stream_velocities(N, v_stream, v_spread, seed=None):
    """双流速度分布：一半粒子 +v_stream，一半 -v_stream

    v[:half] ~ N(+v_stream, v_spread²)
    v[half:] ~ N(-v_stream, v_spread²)

    Args:
        N: 总粒子数
        v_stream: 束流漂移速度
        v_spread: 热速度展宽

    Returns:
        v: shape (N,)
    """
    rng = np.random if seed is None else np.random.RandomState(seed)
    half = N // 2
    v = np.zeros(N)
    v[:half] = v_stream + rng.randn(half) * v_spread if seed is None else v_stream + rng.randn(half) * v_spread
    v[half:] = -v_stream + rng.randn(N - half) * v_spread if seed is None else -v_stream + rng.randn(N - half) * v_spread
    return v
