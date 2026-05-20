# 双流不稳定性 PDE-NHF 训练脚本
# 基于 train_model.py 改造，适配双流先验分布和参数

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
import numpy as np
import random
import argparse

from shared.models.potential import Potential
from shared.models.hamiltonian import TwoStreamPriorNHF


class Parser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(description='双流不稳定性 PDE-NHF 训练')
        self.parser.add_argument('-SEED', default=1, type=int, dest='SEED',
                                 help='随机种子')
        self.parser.add_argument('-FOLDER_EXP', default='models/two_stream/', type=str, dest='FOLDER_EXP',
                                 help='模型保存目录')
        self.parser.add_argument('-FOLDER_DATA', default='data/two_stream/', type=str, dest='FOLDER_DATA',
                                 help='数据加载目录')
        self.parser.add_argument('-N_TRAINING', default=400, type=int, dest='N_TRAINING',
                                 help='训练样本数')
        self.parser.add_argument('-N_VALIDATION', default=100, type=int, dest='N_VALIDATION',
                                 help='验证样本数')
        self.parser.add_argument('-L', default=10, type=int, dest='L',
                                 help='蛙跳积分器步数')
        self.parser.add_argument('-DT', default=0.25, type=float, dest='DT',
                                 help='蛙跳积分器时间步长')
        self.parser.add_argument('-N_EPOCHS', default=200, type=int, dest='N_EPOCHS',
                                 help='训练轮数')
        self.parser.add_argument('-BATCH_SIZE', default=128, type=int, dest='BATCH_SIZE',
                                 help='小批量大小')
        self.parser.add_argument('-LR', default=0.0003, type=float, dest='LR',
                                 help='Adam 优化器学习率')
        self.args = self.parser.parse_args()


def set_seed(seed):
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


if __name__ == "__main__":
    parser = Parser()

    random_seed = parser.args.SEED
    N_train = parser.args.N_TRAINING
    N_val = parser.args.N_VALIDATION
    learning_rate = parser.args.LR
    num_epochs = parser.args.N_EPOCHS
    batch_size = parser.args.BATCH_SIZE
    folder_exp = parser.args.FOLDER_EXP
    folder_data = parser.args.FOLDER_DATA

    # 域长度（与数据生成一致）
    L_domain = 10.0

    # 加载最终时刻数据 (t=10.0, step 100)
    Q = np.load(folder_data + 'Q25.npy')
    P = np.load(folder_data + 'P25.npy')
    Cond = np.load(folder_data + 'Cond.npy')  # [v_stream, v_spread, A_perturb]

    Q_train_np, P_train_np, Cond_train_np = Q[:N_train], P[:N_train], Cond[:N_train]
    Q_val_np, P_val_np, Cond_val_np = Q[N_train:N_train+N_val], P[N_train:N_train+N_val], Cond[N_train:N_train+N_val]

    Q_train = torch.tensor(Q_train_np, dtype=float)
    Q_val = torch.tensor(Q_val_np, dtype=float)
    P_train = torch.tensor(P_train_np, dtype=float)
    P_val = torch.tensor(P_val_np, dtype=float)
    Cond_train = torch.tensor(Cond_train_np, dtype=float)
    Cond_val = torch.tensor(Cond_val_np, dtype=float)

    print(f"训练数据: {Q_train.shape[0]} 样本, {Q_train.shape[1]} 粒子")
    print(f"验证数据: {Q_val.shape[0]} 样本, {Q_val.shape[1]} 粒子")
    print(f"Cond 维度: {Cond_train.shape[1]} (v_stream, v_spread, A_perturb)")

    class QPCondDataset(Dataset):
        def __init__(self, q_maps, p_maps, conds, transform=None):
            self.q_maps = q_maps
            self.p_maps = p_maps
            self.conds = conds
            self.transform = transform

        def __len__(self):
            return len(self.q_maps)

        def __getitem__(self, idx):
            q = self.q_maps[idx]
            p = self.p_maps[idx]
            cond = self.conds[idx]
            if self.transform:
                q = self.transform(q)
                p = self.transform(p)
            return q, p, cond

    training_dataset = QPCondDataset(Q_train, P_train, Cond_train)
    validation_dataset = QPCondDataset(Q_val, P_val, Cond_val)

    # 模型定义
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    set_seed(random_seed)

    L_steps = parser.args.L
    dt = -parser.args.DT  # 负值：反向哈密顿动力学
    model = TwoStreamPriorNHF(L_steps=L_steps, dt=dt, L_domain=L_domain)
    n_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"模型参数量: {n_parameters}")
    print(f"蛙跳步数 L={L_steps}, dt={dt}")
    model.to(device)
    model.double()

    # 训练
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    train_loader = DataLoader(training_dataset, batch_size=batch_size, shuffle=True)
    valid_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=True)

    training_loss = []
    validation_loss = []

    for epoch in range(num_epochs):
        total_loss = 0
        model.train()
        for q, p, cond in train_loader:
            q, p, cond = q.to(device), p.to(device), cond.to(device)
            loss = model.loss(q, p, cond)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        training_loss.append(float(total_loss / len(train_loader)))

        # 验证
        q, p, cond = next(iter(valid_loader))
        q, p, cond = q.to(device), p.to(device), cond.to(device)
        vloss = model.loss(q, p, cond)
        validation_loss.append(float(vloss))

        print(f"Epoch {epoch+1:4d} | Train Loss: {training_loss[-1]:.4f} | Val Loss: {validation_loss[-1]:.4f}")

        if (epoch + 1) % 50 == 0:
            torch.save(model.state_dict(), folder_exp + f'model-{epoch+1}')
            np.save(folder_exp + f'training_loss{epoch+1}', np.array(training_loss))
            np.save(folder_exp + f'validation_loss{epoch+1}', np.array(validation_loss))
            torch.save(optimizer.state_dict(), folder_exp + f'optimizer{epoch+1}')

    # 最终保存
    np.save(folder_exp + 'training_loss_final', np.array(training_loss))
    np.save(folder_exp + 'validation_loss_final', np.array(validation_loss))
    torch.save(model.state_dict(), folder_exp + 'model_final')
    torch.save(optimizer.state_dict(), folder_exp + 'optimizer_final')
    print(f"训练完成！模型保存至 {folder_exp}")
