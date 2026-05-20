# 双流不稳定性 PDE-NHF 评估脚本
# 加载训练好的模型，正向积分并与 PIC ground truth 对比

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import argparse
import random

from shared.models.hamiltonian import NeuralHamiltonianFlow


class Parser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='双流不稳定性 PDE-NHF 评估')
        self.parser.add_argument('-SEED', default=1, type=int, dest='SEED')
        self.parser.add_argument('-FOLDER_EXP', default='models/two_stream/', type=str, dest='FOLDER_EXP')
        self.parser.add_argument('-FOLDER_DATA', default='data/two_stream/', type=str, dest='FOLDER_DATA')
        self.parser.add_argument('-L', default=50, type=int, dest='L')
        self.parser.add_argument('-DT', default=0.1, type=float, dest='DT')
        self.parser.add_argument('-MODEL_FILE', default='model_final', type=str, dest='MODEL_FILE')
        self.parser.add_argument('-TEST_IDX', default=0, type=int, dest='TEST_IDX')
        self.args = self.parser.parse_args()


def set_seed(seed):
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def wasserstein_1d(u_values, v_values):
    """计算一维 Wasserstein-1 距离"""
    u_sorted = np.sort(u_values)
    v_sorted = np.sort(v_values)
    n = len(u_sorted)
    return np.sum(np.abs(u_sorted - v_sorted)) / n


if __name__ == "__main__":
    parser = Parser()
    random_seed = parser.args.SEED
    folder_exp = parser.args.FOLDER_EXP
    folder_data = parser.args.FOLDER_DATA
    L_steps = parser.args.L
    dt = parser.args.DT
    model_file = parser.args.MODEL_FILE
    test_idx = parser.args.TEST_IDX

    set_seed(random_seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 加载模型
    model = NeuralHamiltonianFlow(L_steps=L_steps, dt=-dt)
    model.load_state_dict(torch.load(folder_exp + model_file, map_location=device))
    model.to(device)
    model.double()
    model.eval()
    print(f"已加载模型: {folder_exp}{model_file}")
    print(f"蛙跳步数 L={L_steps}, dt={dt}")

    # 加载测试数据
    Q00 = np.load(folder_data + 'Q00.npy')
    P00 = np.load(folder_data + 'P00.npy')
    Q100 = np.load(folder_data + 'Q100.npy')
    P100 = np.load(folder_data + 'P100.npy')
    Cond = np.load(folder_data + 'Cond.npy')

    print(f"测试样本 {test_idx}: v_stream={Cond[test_idx,0]:.3f}, "
          f"v_spread={Cond[test_idx,1]:.4f}, A={Cond[test_idx,2]:.4f}")
    print(f"数据量: {Q00.shape[0]} 样本, {Q00.shape[1]} 粒子")

    # 从初始状态正向积分
    q0_true = torch.tensor(Q00[test_idx], dtype=torch.float64).to(device)
    p0_true = torch.tensor(P00[test_idx], dtype=torch.float64).to(device)

    q_pred, p_pred = model.sample(q0_true, p0_true, nsteps=L_steps, delta_t=dt)

    q_pred = q_pred.squeeze(0).cpu().numpy()
    p_pred = p_pred.squeeze(0).cpu().numpy()
    q_true = Q100[test_idx]
    p_true = P100[test_idx]

    # 计算 Wasserstein-1 距离
    w1_q = wasserstein_1d(q_pred, q_true)
    w1_p = wasserstein_1d(p_pred, p_true)
    print(f"Wasserstein-1 距离: q={w1_q:.4f}, p={w1_p:.4f}")

    # 可视化
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))

    # t=0: 初始状态 (真实)
    ax = axes[0, 0]
    ax.scatter(Q00[test_idx], P00[test_idx], s=1, alpha=0.4, color='blue')
    ax.set_xlabel('x (位置)')
    ax.set_ylabel('v (速度)')
    ax.set_title(f't=0 初始双流分布\nv_stream={Cond[test_idx,0]:.2f}, v_spread={Cond[test_idx,1]:.3f}')
    ax.set_xlim(0, 10)
    ax.set_ylim(-3, 3)

    # t=T: PIC ground truth
    ax = axes[0, 1]
    ax.scatter(q_true, p_true, s=1, alpha=0.4, color='red')
    ax.set_xlabel('x (位置)')
    ax.set_ylabel('v (速度)')
    ax.set_title('t=10 PIC Ground Truth')
    ax.set_xlim(0, 10)
    ax.set_ylim(-3, 3)

    # t=T: HNF 预测
    ax = axes[1, 0]
    ax.scatter(q_pred, p_pred, s=1, alpha=0.4, color='green')
    ax.set_xlabel('x (位置)')
    ax.set_ylabel('v (速度)')
    ax.set_title(f't=10 HNF 预测\nW1(q)={w1_q:.4f}, W1(p)={w1_p:.4f}')
    ax.set_xlim(0, 10)
    ax.set_ylim(-3, 3)

    # 叠加对比 (x-边缘分布)
    ax = axes[1, 1]
    bins = 50
    ax.hist(q_true, bins=bins, alpha=0.5, density=True, color='red', label='PIC')
    ax.hist(q_pred, bins=bins, alpha=0.5, density=True, color='green', label='HNF')
    ax.set_xlabel('x (位置)')
    ax.set_ylabel('概率密度')
    ax.set_title('位置分布对比')
    ax.legend()

    plt.tight_layout()
    plt.savefig(folder_exp + 'evaluation.png', dpi=150)
    print(f"评估图已保存至 {folder_exp}evaluation.png")
