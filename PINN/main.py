import numpy as np
import matplotlib.pyplot as plt

# ==================== 1. 参数设置（严格对齐原论文） ====================
L = 10.0  # 计算域长度: 10 λ_D
Nx = 256  # 空间网格数: 256 cells
Np = 100000  # 宏粒子数 (使用10万粒子，因为向量化后极快，图像也更平滑)
dt = 0.125  # 时间步长: 0.125 ω_p^{-1}
tEnd = 62.5  # 终止时间: 62.5 ω_p^{-1}
Nt = int(tEnd / dt)  # 总时间步数: 500步

v_th = 1.0  # 电子热速度
v_stream = 1.0  # 漂移速度
v_spread = 0.02  # 热展宽: 0.02 v_th

dx = L / Nx
w = L / Np  # 宏粒子权重，使得平均密度 n_e = 1

# 相空间网格参数 (用于生成 PINN 的 f(t,x,v) 标签)
Nv = 256
v_min, v_max = -5.0 * v_th, 5.0 * v_th
f_data = np.zeros((Nt, Nx, Nv))  # 终极目标：保存给 PINN 训练的连续数据


# ==================== 2. 高效的向量化核心函数 ====================
def deposit_charge_CIC_vectorized(xp, w, dx, Nx):
    """【极速版】CIC电荷沉积：无for循环，使用 np.add.at"""
    rho = np.zeros(Nx)

    # 计算粒子所在的左侧网格索引和权重
    x_idx = xp / dx
    i = np.floor(x_idx).astype(int) % Nx
    ip = (i + 1) % Nx
    xi = x_idx - np.floor(x_idx)

    # 向量化累加电荷 (替代慢速的 for 循环)
    np.add.at(rho, i, w * (1 - xi))
    np.add.at(rho, ip, w * xi)

    return rho


def interp_field_CIC_vectorized(xp, E_grid, dx, Nx):
    """【极速版】CIC电场插值：使用数组切片"""
    x_idx = xp / dx
    i = np.floor(x_idx).astype(int) % Nx
    ip = (i + 1) % Nx
    xi = x_idx - np.floor(x_idx)

    # 向量化插值
    Ep = E_grid[i] * (1 - xi) + E_grid[ip] * xi
    return Ep


def solve_poisson_fft(rho, L, Nx):
    """FFT求解泊松方程"""
    rho_hat = np.fft.fft(rho)
    kx = 2 * np.pi * np.fft.fftfreq(Nx, d=L / Nx)

    E_hat = np.zeros_like(rho_hat, dtype=complex)
    with np.errstate(divide='ignore', invalid='ignore'):
        E_hat = rho_hat / (1j * kx)
    E_hat[0] = 0.0  # 直流分量设为0

    return np.real(np.fft.ifft(E_hat))


# ==================== 3. 初始化 ====================
print(f"初始化 {Np} 个粒子...")
xp = np.random.rand(Np) * L
vp = np.zeros(Np)
half = Np // 2
vp[:half] = v_stream + np.random.randn(half) * v_spread
vp[half:] = -v_stream + np.random.randn(Np - half) * v_spread

# 用于画图的时间点记录
snapshot_steps = [0, int(25.0 / dt), int(37.5 / dt), int(50.0 / dt)]
snapshot_times = [0, 25.0, 37.5, 50.0]

# ==================== 4. 主循环 ====================
print("开始极速 PIC 模拟...")
for step in range(Nt):
    # 1. 极速电荷沉积
    n_e = deposit_charge_CIC_vectorized(xp, 1.0 / (Np / Nx), dx, Nx)  # 归一化使得平均 n_e=1

    # 2. 计算净电荷密度 ρ = n_i - n_e (假设 n_i=1 均匀背景)
    rho = 1.0 - n_e
    rho = rho - np.mean(rho)  # 确保严格的全局电荷中性

    # 3. 解泊松方程
    E_grid = solve_poisson_fft(rho, L, Nx)

    # 4. 极速电场插值
    Ep = interp_field_CIC_vectorized(xp, E_grid, dx, Nx)

    # 5. 推进粒子
    vp = vp - Ep * dt
    xp = xp + vp * dt
    xp = np.mod(xp, L)

    # 6. 【关键环节】提取 PINN 需要的 f(t, x, v) 连续网格数据
    # 使用直方图模拟双线性插值效果，将其压入 f_data
    hist, _, _ = np.histogram2d(xp, vp, bins=[Nx, Nv], range=[[0, L], [v_min, v_max]])
    # 归一化分布函数 (参考公式 15)
    f_data[step] = hist / (Np * dx * ((v_max - v_min) / Nv))

    if step % 100 == 0:
        print(f"  进度: 步骤 {step}/{Nt} (时间 t = {step * dt:.1f} ω_p^-1)")

print("模拟完成！可以准备投喂给 PINN 了。")

# ==================== 5. 论文同款可视化对齐 ====================
fig, axes = plt.subplots(1, 4, figsize=(20, 4), sharey=True)

for i, ax in enumerate(axes):
    step_idx = snapshot_steps[i]
    if step_idx >= Nt: step_idx = Nt - 1

    # 直接提取我们生成的给 PINN 用的 f_data 来画图
    f_t = f_data[step_idx].T

    # 使用 bilinear 插值平滑显示，达到论文里的视觉效果
    im = ax.imshow(f_t, extent=[0, L, v_min, v_max], origin='lower',
                   aspect='auto', cmap='jet', interpolation='bilinear', vmax=0.8)

    ax.set_title(f"t = {snapshot_times[i]} $\omega_p^{{-1}}$")
    ax.set_xlabel('Position $x [\lambda_D]$')
    if i == 0:
        ax.set_ylabel('Velocity $v [v_{th}]$')

cbar = fig.colorbar(im, ax=axes.ravel().tolist(), pad=0.02)
cbar.set_label('Electron Distribution Function $f$')
plt.suptitle('Reconstructed f(x,v) exactly as PINN inputs', fontsize=16, y=1.05)
plt.show()

# 将数据保存，供你的 PyTorch 脚本调用
np.savez_compressed('pinn_vlasov_data.npz', f_data=f_data, x_grid=np.linspace(0,L,Nx), v_grid=np.linspace(v_min,v_max,Nv))