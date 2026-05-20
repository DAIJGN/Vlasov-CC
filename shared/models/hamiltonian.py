"""Neural Hamiltonian Flow — 带有可学习势能的 Hamiltonian 动力学

通过蛙跳积分器反向推演，用 KL 散度训练势能网络。
支持两种先验：
- GaussPrior: q~N(mu,σ²), p~N(mu,σ²)
- TwoStreamPrior: q~U(0,L), p~0.5N(+vs,vsp²)+0.5N(-vs,vsp²)
"""

import torch
import torch.nn as nn
import torch.distributions as D
from torch.autograd import grad
import numpy as np

from shared.models.potential import Potential


class NeuralHamiltonianFlow(nn.Module):
    """可学习 Hamiltonian 动力学的 Normalizing Flow

    Args:
        L_steps: 蛙跳积分步数
        dt: 时间步长（训练时取负值，表示反向动力学）
        potential: Potential 网络实例（可选，默认 hidden_dim=256）
    """

    def __init__(self, L_steps, dt, potential=None):
        super().__init__()
        self.L = L_steps
        self.dt = dt
        self.V_net = potential if potential is not None else Potential()
        self.register_parameter(
            name='a', param=nn.Parameter(torch.ones(1))
        )  # M⁻¹ = a² I — 可学习质量矩阵

    def potential_energy(self, q):
        return self.V_net(q)

    def leapfrog_integrator(self, q, p, L_steps, dt, create_graph=True):
        """蛙跳积分器（PyTorch 版，保留计算图用于反向传播）

        模板：半加速 → 全漂移 → 半加速

        Args:
            q, p: 位置和动量 (B, N)
            L_steps: 步数
            dt: 时间步长
            create_graph: 是否保留计算图（训练时 True，推理时 False）

        Returns:
            q, p: 积分后的位置和动量
        """
        V = self.potential_energy(q)
        gq, = grad(V.sum(), q, create_graph=create_graph)

        for _ in range(L_steps):
            p = p - 0.5 * dt * gq
            q = q + self.a ** 2 * p * dt
            V = self.potential_energy(q)
            gq, = grad(V.sum(), q, create_graph=create_graph)
            p = p - 0.5 * dt * gq

        return q, p

    def forward(self, q, p, cond):
        """反向演化：从最终状态回到初始状态

        Args:
            q, p: 最终时刻的位置和动量 (B, N)
            cond: 条件参数 (B, C)，内容取决于先验类型

        Returns:
            q0, p0: 反向积分后的初始状态
            cond unpacked: 解包后的条件张量
        """
        cond = self._unpack_cond(cond)
        q.requires_grad, p.requires_grad = True, True
        q, p = self.leapfrog_integrator(q, p, self.L, self.dt, create_graph=True)
        return q, p, *cond

    def _unpack_cond(self, cond):
        """子类重写此方法以解包条件参数"""
        raise NotImplementedError("子类需实现 _unpack_cond")

    def compute_log_prior(self, q0, p0, *cond):
        """子类重写此方法以计算先验对数概率"""
        raise NotImplementedError("子类需实现 compute_log_prior")

    def loss(self, q, p, cond):
        """KL 散度损失 = -E[log π(q0) + log π(p0)]"""
        result = self.forward(q, p, cond)
        q0, p0 = result[0], result[1]
        cond_rest = result[2:]
        log_prior = self.compute_log_prior(q0, p0, *cond_rest)
        return -log_prior.mean()

    def sample(self, q0, p0, nsteps, delta_t):
        """正向演化：从初始状态积分到最终状态（推理用）

        Args:
            q0, p0: 初始状态 (N,) — 不带 batch 维度
            nsteps: 正向步数
            delta_t: 正向时间步长（正值）

        Returns:
            q, p: 最终状态 (1, N)
        """
        q0, p0 = q0.unsqueeze(0), p0.unsqueeze(0)
        q0.requires_grad, p0.requires_grad = True, True
        q, p = self.leapfrog_integrator(q0, p0, nsteps, -delta_t, create_graph=False)
        return q.detach(), p.detach()


# ===== 先验分布工厂 =====

class GaussPriorNHF(NeuralHamiltonianFlow):
    """原始 Gauss 先验：q~N(64,σ_q²), p~N(0,σ_p²)

    Cond 格式: (B, 2) = [sigma_q, sigma_p]
    """

    def _unpack_cond(self, cond):
        sigma_q = cond[:, 0].unsqueeze(1)
        sigma_p = cond[:, 1].unsqueeze(1)
        return sigma_q, sigma_p

    def compute_log_prior(self, q0, p0, sigma_q, sigma_p):
        prior_q = D.Normal(loc=64.0, scale=sigma_q)
        prior_p = D.Normal(loc=0.0, scale=sigma_p)
        log_q = prior_q.log_prob(q0).sum(dim=1)
        log_p = prior_p.log_prob(p0).sum(dim=1)
        return log_q + log_p


class TwoStreamPriorNHF(NeuralHamiltonianFlow):
    """双流混合 Gauss 先验：q~U(0,L), p~0.5N(+v_stream,v_spread²)+0.5N(-v_stream,v_spread²)

    Cond 格式: (B, 3) = [v_stream, v_spread, A_perturb]
    A_perturb 在训练中不使用（仅数据生成时使用）
    """

    def __init__(self, L_steps, dt, L_domain=10.0, potential=None):
        super().__init__(L_steps, dt, potential)
        self.L_domain = L_domain

    def _unpack_cond(self, cond):
        v_stream = cond[:, 0].unsqueeze(1)
        v_spread = cond[:, 1].unsqueeze(1)
        return v_stream, v_spread

    def compute_log_prior(self, q0, p0, v_stream, v_spread):
        # 位置先验：均匀分布 U(0, L_domain)，常数项
        log_q = -np.log(self.L_domain) * q0.shape[1]

        # 速度先验：混合高斯 0.5*N(+v_stream, v_spread²) + 0.5*N(-v_stream, v_spread²)
        lp1 = D.Normal(v_stream, v_spread).log_prob(p0)
        lp2 = D.Normal(-v_stream, v_spread).log_prob(p0)
        log_p = torch.logsumexp(
            torch.stack([lp1 + np.log(0.5), lp2 + np.log(0.5)], dim=-1),
            dim=-1
        ).sum(dim=1)

        return log_q + log_p
