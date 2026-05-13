"""双流 PDE-NHF 快速训练验证 (50 epochs, Q25/P25, L=25)"""
import torch, numpy as np, random, sys
import torch.nn as nn
import torch.distributions as D
from torch.autograd import grad
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset

torch.manual_seed(1); np.random.seed(1); random.seed(1)

Q = np.load('data/two_stream/Q25.npy')
P = np.load('data/two_stream/P25.npy')
Cond = np.load('data/two_stream/Cond.npy')
L_domain = 10.0

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

class Potential(nn.Module):
    def __init__(self, hidden_dim=256):
        super().__init__()
        self.phi = nn.Sequential(nn.Linear(1, hidden_dim), nn.Softplus(), nn.Linear(hidden_dim, hidden_dim))
        self.rho = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.Softplus(), nn.Linear(hidden_dim, 1))
    def forward(self, q):
        qc = q - q.mean(dim=1, keepdim=True)
        return self.rho(self.phi(qc.unsqueeze(-1)).sum(dim=1)).squeeze(-1)

class NHF(nn.Module):
    def __init__(self, L_steps, dt):
        super().__init__()
        self.L, self.dt = L_steps, dt
        self.V_net = Potential()
        self.register_parameter(name='a', param=nn.Parameter(torch.ones(1)))
    def potential_energy(self, q): return self.V_net(q)
    def leapfrog_integrator(self, q, p, L_s, dt):
        V = self.potential_energy(q)
        gq, = grad(V.sum(), q, create_graph=True)
        for _ in range(L_s):
            p = p - 0.5*dt*gq; q = q + self.a**2*p*dt
            V = self.potential_energy(q); gq, = grad(V.sum(), q, create_graph=True)
            p = p - 0.5*dt*gq
        return q, p
    def forward(self, q, p, cond):
        vs, vsp = cond[:,0].unsqueeze(1), cond[:,1].unsqueeze(1)
        q.requires_grad, p.requires_grad = True, True
        q, p = self.leapfrog_integrator(q, p, self.L, self.dt)
        return q, p, vs, vsp
    def loss(self, q, p, cond):
        q0, p0, vs, vsp = self.forward(q, p, cond)
        lp1 = D.Normal(vs, vsp).log_prob(p0)
        lp2 = D.Normal(-vs, vsp).log_prob(p0)
        log_p = torch.logsumexp(torch.stack([lp1+np.log(0.5), lp2+np.log(0.5)], dim=-1), dim=-1).sum(dim=1)
        log_q = -np.log(L_domain) * q0.shape[1]
        return -(log_q + log_p).mean()

model = NHF(L_steps=25, dt=-0.1).to(device).double()
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
