"""Deep Set 势能网络 — 置换不变的标量势能 V(q)

架构：per-particle embedding(φ) → sum-pooling → global MLP(ρ)
交换任意两个粒子的位置，输出势能不变。

被 PINN（如果需要）和 PDE-NHF 共用。
"""

import torch
import torch.nn as nn


class Potential(nn.Module):
    """置换不变的标量势能网络

    Args:
        hidden_dim: 隐藏层维度，默认 256

    Input:  q (B, N) — 批次中每个粒子的位置
    Output: V (B,)  — 每批次的标量势能
    """

    def __init__(self, hidden_dim=256):
        super().__init__()
        self.phi = nn.Sequential(
            nn.Linear(1, hidden_dim),
            nn.Softplus(),
            nn.Linear(hidden_dim, hidden_dim),
        )
        self.rho = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.Softplus(),
            nn.Linear(hidden_dim, 1),
        )

    def forward(self, q):
        """q: (B, N) → V: (B,)"""
        q_centered = q - q.mean(dim=1, keepdim=True)  # 平移不变性
        phi_q = self.phi(q_centered.unsqueeze(-1))     # (B, N, hidden_dim)
        pooled = phi_q.sum(dim=1)                      # (B, hidden_dim) — 置换不变
        return self.rho(pooled).squeeze(-1)             # (B,)
