"""双流 PDE-NHF 快速训练验证 (50 epochs, Q25/P25, L=25)"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch, numpy as np, random
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset

from shared.models.hamiltonian import TwoStreamPriorNHF

torch.manual_seed(1); np.random.seed(1); random.seed(1)

Q = np.load('data/two_stream/Q25.npy')
P = np.load('data/two_stream/P25.npy')
Cond = np.load('data/two_stream/Cond.npy')

N_train, N_val = 150, 50
Q_train = torch.tensor(Q[:N_train], dtype=float)
P_train = torch.tensor(P[:N_train], dtype=float)
Cond_train = torch.tensor(Cond[:N_train], dtype=float)
Q_val = torch.tensor(Q[N_train:N_train+N_val], dtype=float)
P_val = torch.tensor(P[N_train:N_train+N_val], dtype=float)
Cond_val = torch.tensor(Cond[N_train:N_train+N_val], dtype=float)

class QPCondDataset(Dataset):
    def __init__(self, q, p, c):
        self.q, self.p, self.c = q, p, c
    def __len__(self): return len(self.q)
    def __getitem__(self, i): return self.q[i], self.p[i], self.c[i]

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'使用设备: {device}')

model = TwoStreamPriorNHF(L_steps=25, dt=-0.1, L_domain=10.0).to(device).double()
n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f'参数量: {n_params}')
print(f'训练样本: {N_train}, 验证样本: {N_val}')
print(f'蛙跳步数: 25, dt: -0.1')

opt = optim.Adam(model.parameters(), lr=0.0003)
tl = DataLoader(QPCondDataset(Q_train, P_train, Cond_train), batch_size=32, shuffle=True)
vl = DataLoader(QPCondDataset(Q_val, P_val, Cond_val), batch_size=32, shuffle=True)

train_loss, val_loss = [], []
print('开始训练...')
for ep in range(50):
    model.train(); total=0
    for q,p,c in tl:
        q,p,c = q.to(device), p.to(device), c.to(device)
        loss = model.loss(q,p,c)
        opt.zero_grad(); loss.backward(); opt.step()
        total += loss.item()
    train_loss.append(total/len(tl))
    q,p,c = next(iter(vl)); q,p,c = q.to(device), p.to(device), c.to(device)
    vloss = model.loss(q,p,c).item()
    val_loss.append(vloss)
    if (ep+1) % 5 == 0:
        print(f'Epoch {ep+1:3d} | Train: {train_loss[-1]:.2f} | Val: {vloss:.2f}')
        sys.stdout.flush()

np.save('models/two_stream/training_loss_final.npy', np.array(train_loss))
np.save('models/two_stream/validation_loss_final.npy', np.array(val_loss))
torch.save(model.state_dict(), 'models/two_stream/model_final')
print(f'完成! 初始Loss: {train_loss[0]:.2f} -> 最终: {train_loss[-1]:.2f}')
print(f'最小训练Loss: {min(train_loss):.2f} (epoch {np.argmin(train_loss)+1})')
