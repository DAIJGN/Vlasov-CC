import torch
import torch.nn as nn
import numpy as np

# 假设 f_data, L, v_min, v_max, dt 等变量已经从上一步的 PIC 模拟中获得
# 如果是在新文件中，可以使用 np.load('pinn_vlasov_data.npz') 导入

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"使用计算设备: {device}")

# ==================== 正确的数据加载方式 ====================
# 1. 加载 npz 文件对象
data_file = np.load('pinn_vlasov_data.npz')

# 2. 通过键名提取数组
f_data = data_file['f_data']

# 因为我们在新文件里，顺便把其他常量也重新声明一下，或者从 x_grid/v_grid 里推导
Nt, Nx, Nv = f_data.shape
dt = 0.125
L = 10.0
v_th = 1.0

# ==================== 1. 生成坐标网格 ====================
Nt, Nx, Nv = f_data.shape
t_grid = np.linspace(0, Nt * 0.125, Nt, endpoint=False) # dt = 0.125
x_grid = np.linspace(0, 10.0, Nx, endpoint=False)       # L = 10.0
v_grid = np.linspace(-5.0, 5.0, Nv)                     # v_th = 1.0

# 生成三维网格坐标 (T, X, V)
T, X, V = np.meshgrid(t_grid, x_grid, v_grid, indexing='ij')

# 将网格展平，方便随机抽样
T_flat = T.flatten()[:, None]
X_flat = X.flatten()[:, None]
V_flat = V.flatten()[:, None]
F_flat = f_data.flatten()[:, None]

# ==================== 2. 数据采样 (加入重要性采样) ====================
# 原论文前向问题采样量，我们适当增加一点以确保结构清晰
N_ic = 1000
N_bc = 1000
# N_pde = 8000

#改
N_pde = 12000

print("执行重要性采样 (过滤稀疏真空区)...")

# 核心秘籍：找出相空间中有真实电子的“信号区”和真空的“背景区”
idx_signal = np.where(F_flat > 0.05)[0]
idx_bg = np.where(F_flat <= 0.05)[0]

# --- a. 初始条件 (IC) 采样 t = 0 ---
idx_ic_all = np.where(T_flat == t_grid[0])[0]
idx_ic_signal = np.intersect1d(idx_ic_all, idx_signal)
idx_ic_bg = np.intersect1d(idx_ic_all, idx_bg)
# 强制一半点落在初始电子束上，一半落在背景
ic_s = np.random.choice(idx_ic_signal, N_ic//2, replace=False)
ic_b = np.random.choice(idx_ic_bg, N_ic//2, replace=False)
idx_ic = np.concatenate([ic_s, ic_b])

t_ic = torch.tensor(T_flat[idx_ic], dtype=torch.float32).to(device)
x_ic = torch.tensor(X_flat[idx_ic], dtype=torch.float32).to(device)
v_ic = torch.tensor(V_flat[idx_ic], dtype=torch.float32).to(device)
f_ic = torch.tensor(F_flat[idx_ic], dtype=torch.float32).to(device)

# --- b. 边界条件 (BC) 采样 (同理) ---
idx_bc_all = np.where((X_flat == x_grid[0]) | (X_flat == x_grid[-1]) |
                      (V_flat == v_grid[0]) | (V_flat == v_grid[-1]))[0]
idx_bc_signal = np.intersect1d(idx_bc_all, idx_signal)
idx_bc_bg = np.intersect1d(idx_bc_all, idx_bg)
bc_s = np.random.choice(idx_bc_signal, N_bc//2, replace=False)
bc_b = np.random.choice(idx_bc_bg, N_bc//2, replace=False)
idx_bc = np.concatenate([bc_s, bc_b])

t_bc = torch.tensor(T_flat[idx_bc], dtype=torch.float32).to(device)
x_bc = torch.tensor(X_flat[idx_bc], dtype=torch.float32).to(device)
v_bc = torch.tensor(V_flat[idx_bc], dtype=torch.float32).to(device)
f_bc = torch.tensor(F_flat[idx_bc], dtype=torch.float32).to(device)

# --- c. 内部约束点 (PDE Collocation points) 采样 ---
# 强制 4000 个点打在电子束演化的轨迹上！
pde_s = np.random.choice(idx_signal, N_pde//2, replace=False)
pde_b = np.random.choice(idx_bg, N_pde//2, replace=False)
idx_pde = np.concatenate([pde_s, pde_b])

t_pde = torch.tensor(T_flat[idx_pde], dtype=torch.float32, requires_grad=True).to(device)
x_pde = torch.tensor(X_flat[idx_pde], dtype=torch.float32, requires_grad=True).to(device)
v_pde = torch.tensor(V_flat[idx_pde], dtype=torch.float32, requires_grad=True).to(device)
f_pde_true = torch.tensor(F_flat[idx_pde], dtype=torch.float32).to(device)

print(f"采样完成！强制锚定内部核心信号点: {N_pde//2} 个")


# ==================== 3. 定义 PINN 模型 ====================
class PINN_Vlasov(nn.Module):
    # def __init__(self, num_layers=4, neurons_per_layer=50):


    # 改
    def __init__(self, num_layers=8, neurons_per_layer=100):
        super(PINN_Vlasov, self).__init__()

        layers = []
        # 输入层: t, x, v (3个维度)
        layers.append(nn.Linear(3, neurons_per_layer))
        layers.append(nn.Tanh())

        # 隐藏层
        for _ in range(num_layers - 1):
            layers.append(nn.Linear(neurons_per_layer, neurons_per_layer))
            layers.append(nn.Tanh())

        # 输出层: f 和 E (2个维度)
        layers.append(nn.Linear(neurons_per_layer, 2))

        self.net = nn.Sequential(*layers)

        # 权重初始化：原论文提到将偏置和权重初始化为零，
        # 但完全为零会导致梯度无法更新，通常使用的是 Xavier 或 默认的均匀初始化。
        # 我们这里保持 PyTorch 默认初始化。

    def forward(self, t, x, v):
        # 【补丁1：极其重要的输入归一化】
        # 将 t (0~62.5), x (0~10), v (-5~5) 映射到 [-1, 1] 附近
        t_norm = (t / 62.5) * 2.0 - 1.0
        x_norm = (x / 10.0) * 2.0 - 1.0
        v_norm = v / 5.0

        # 拼接归一化后的输入喂给网络
        inputs = torch.cat([t_norm, x_norm, v_norm], dim=1)
        outputs = self.net(inputs)

        f_pred = outputs[:, 0:1]
        E_pred = outputs[:, 1:2]
        return f_pred, E_pred


model = PINN_Vlasov().to(device)
print(model)

# ==================== 4. 核心：物理损失函数计算 ====================
# 生成用于积分的固定 v 网格张量 (原论文速度范围是 -5 到 5)
# Nv_int = 256

# 报内存而改
Nv_int = 128
v_int_grid = torch.linspace(-5.0, 5.0, Nv_int, device=device).view(1, -1)
dv = (5.0 - (-5.0)) / (Nv_int - 1)


def compute_physics_loss(model, t_pde, x_pde, v_pde):
    # ---------------------------------------------------------
    # A. 计算 Vlasov 方程残差 (在随机采样的 t, x, v 点上)
    # ---------------------------------------------------------
    f_pred, E_pred = model(t_pde, x_pde, v_pde)

    # 使用自动微分计算一阶偏导数
    # create_graph=True 允许计算高阶导数并保留计算图用于反向传播
    f_t = torch.autograd.grad(f_pred, t_pde, grad_outputs=torch.ones_like(f_pred), create_graph=True)[0]
    f_x = torch.autograd.grad(f_pred, x_pde, grad_outputs=torch.ones_like(f_pred), create_graph=True)[0]
    f_v = torch.autograd.grad(f_pred, v_pde, grad_outputs=torch.ones_like(f_pred), create_graph=True)[0]
    E_x = torch.autograd.grad(E_pred, x_pde, grad_outputs=torch.ones_like(E_pred), create_graph=True)[0]

    # 论文公式(6): df/dt + v*df/dx - E*df/dv = 0
    # 注意: 原论文在逆问题中定义方程时带上了 λ1 和 λ2，前向问题中实际上就是常规的 Vlasov 方程。
    # 根据归一化公式和电子的带电符号，原论文公式实际为 df/dt + v*df/dx - E*df/dv = 0 (对于电子)
    vlasov_residual = f_t + v_pde * f_x - E_pred * f_v

    # ---------------------------------------------------------
    # B. 计算 Poisson 方程残差 (需要使用梯形法则计算密度积分)
    # ---------------------------------------------------------
    # 为了积分，我们需要在当前的 t_pde, x_pde 处，沿 v 轴展开预测 f
    N_points = t_pde.shape[0]

    # 将 t 和 x 复制 Nv_int 份：shape (N_points * Nv_int, 1)
    t_rep = t_pde.repeat(1, Nv_int).view(-1, 1)
    x_rep = x_pde.repeat(1, Nv_int).view(-1, 1)
    # 将 v 网格复制 N_points 份
    v_rep = v_int_grid.repeat(N_points, 1).view(-1, 1)

    # 预测这些点上的分布函数
    f_int_pred, _ = model(t_rep, x_rep, v_rep)

    # 将结果 reshape 回 (N_points, Nv_int) 以便在第 1 维度上做积分
    f_int_pred = f_int_pred.view(N_points, Nv_int)

    # 使用 PyTorch自带的梯形积分计算密度 n_e = \int f dv
    density = torch.trapz(f_int_pred, v_int_grid, dim=1).view(-1, 1)

    # 论文公式(7): dE/dx = n_e - 1 => dE/dx - n_e + 1 = 0
    poisson_residual = E_x - density + 1.0

    # 整合所有的物理残差，求均方误差 (MSE)
    loss_eq = torch.mean(vlasov_residual ** 2) + torch.mean(poisson_residual ** 2)
    return loss_eq


# ==================== 5. 训练准备与主循环 ====================
# 按照论文设置 AdamW 优化器
optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.005)

# 【新增】定义学习率调度器：每 10000 步，学习率衰减为原来的一半
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=10000, gamma=0.5)

# epochs = 2000  # 原论文跑了非常多 epoch，我们在精简版先跑 10000 次看看趋势


#改
epochs = 20000
loss_history = []

print("开始训练 PINN 模型...")
model.train()

for epoch in range(epochs):
    optimizer.zero_grad()

    # 1. 计算边界条件损失 L_BC
    f_bc_pred, _ = model(t_bc, x_bc, v_bc)
    loss_bc = torch.mean((f_bc_pred - f_bc) ** 2)

    # 2. 计算初始条件损失 L_IC
    f_ic_pred, _ = model(t_ic, x_ic, v_ic)
    loss_ic = torch.mean((f_ic_pred - f_ic) ** 2)

    # 3. 计算物理方程约束损失 L_eq
    loss_eq = compute_physics_loss(model, t_pde, x_pde, v_pde)

    # 【补丁3：计算内部锚点的 Data Loss】
    f_pde_pred, _ = model(t_pde, x_pde, v_pde)
    loss_data = torch.mean((f_pde_pred - f_pde_true) ** 2)

    # 4. 重新分配极其重要的加权总损失
    weight_data = 0.7 # 给予内部锚点最高的权重，强制显现形状！
    weight_ic = 0.1
    weight_bc = 0.1
    weight_eq = 0.1  # 物理方程作为平滑和约束的正则化项

    loss = weight_eq * loss_eq + weight_ic * loss_ic + weight_bc * loss_bc + weight_data * loss_data

    # 5. 反向传播与优化
    loss.backward()
    optimizer.step()

    # 【新增】让调度器更新学习率
    scheduler.step()

    if epoch % 500 == 0:
        current_lr = optimizer.param_groups[0]['lr']
        print(f"Epoch: {epoch:5d} | Loss: {loss.item():.6f} | LR: {current_lr:.6f}")


    loss_history.append(loss.item())

    if epoch % 500 == 0:
        print(
            f"Epoch: {epoch:5d} | Total Loss: {loss.item():.6f} | L_eq: {loss_eq.item():.6f} | L_ic: {loss_ic.item():.6f} | L_bc: {loss_bc.item():.6f}| L_data: {loss_data.item():.6f} ")

print("训练完成！")

# 保存训练好的模型权重
torch.save(model.state_dict(), 'pinn_vlasov_weights.pth')
print("模型权重已保存到硬盘！")

# 简单画一下 Loss 曲线
import matplotlib.pyplot as plt

plt.figure()
plt.plot(loss_history)
plt.yscale('log')
plt.title('PINN Training Loss')
plt.xlabel('Epoch')
plt.ylabel('Loss (Log Scale)')
plt.show()

# ==================== 6. 模型推理与对比评估 ====================
print("开始模型推理评估...")

# 将模型设置为评估模式 (关闭梯度计算以节省内存和加速)
model.eval()

# 我们选取原论文中展示的两个经典时刻：中期(t=25) 和 晚期(t=50)
eval_times = [25.0, 50.0]

# 准备画图：2行(PIC真值 vs PINN预测)，2列(不同时间)
fig, axes = plt.subplots(2, 2, figsize=(12, 10), sharex=True, sharey=True)

# 定义网格分辨率 (使用推理时的高分辨率)
Nx_test, Nv_test = 256, 256
x_test = torch.linspace(0, 10.0, Nx_test)
v_test = torch.linspace(-5.0, 5.0, Nv_test)
X_test, V_test = torch.meshgrid(x_test, v_test, indexing='ij')

with torch.no_grad():  # 禁用自动微分
    for i, t_val in enumerate(eval_times):
        # 1. 构建张量输入
        T_test = torch.full_like(X_test, t_val)

        t_flat = T_test.flatten().unsqueeze(1).to(device)
        x_flat = X_test.flatten().unsqueeze(1).to(device)
        v_flat = V_test.flatten().unsqueeze(1).to(device)

        # 2. 网络前向预测
        f_pred_flat, _ = model(t_flat, x_flat, v_flat)
        f_pred = f_pred_flat.view(Nx_test, Nv_test).cpu().numpy()

        # 3. 获取对应的 PIC 真值 (从 f_data 里取)
        # 找到最接近 t_val 的时间步索引
        dt = 0.125
        step_idx = int(t_val / dt)
        f_true = f_data[step_idx]

        # 4. 绘图 - 上排: PIC真实数据 (Ground Truth)
        ax_true = axes[0, i]
        im_true = ax_true.imshow(f_true.T, extent=[0, 10.0, -5.0, 5.0],
                                 origin='lower', aspect='auto', cmap='jet', vmax=0.7)
        ax_true.set_title(f"PIC Truth (t = {t_val})")
        if i == 0: ax_true.set_ylabel('Velocity v')

        # 5. 绘图 - 下排: PINN预测结果 (Prediction)
        ax_pred = axes[1, i]
        im_pred = ax_pred.imshow(f_pred.T, extent=[0, 10.0, -5.0, 5.0],
                                 origin='lower', aspect='auto', cmap='jet', vmax=0.7)
        ax_pred.set_title(f"PINN Predict (t = {t_val})")
        ax_pred.set_xlabel('Position x')
        if i == 0: ax_pred.set_ylabel('Velocity v')

# 添加 colorbar
cbar = fig.colorbar(im_true, ax=axes.ravel().tolist(), pad=0.02)
cbar.set_label('Distribution f(x,v)')

plt.suptitle('PINN vs PIC (Forward Problem)', fontsize=16)
plt.show()