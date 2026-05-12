import numpy as np
import matplotlib.pyplot as plt

# ==================== 1. 加载 PIC 数据 ====================
print("正在加载 PIC 基准数据...")
try:
    data = np.load('pinn_vlasov_data.npz')
    f_data = data['f_data']
    print(f"数据加载成功！张量维度: {f_data.shape}")
except FileNotFoundError:
    print("错误：找不到 pinn_vlasov_data.npz 文件，请确保它在当前目录下。")
    exit()

# ==================== 2. 绘图参数设置 ====================
dt = 0.125
eval_times = [0.0, 25.0, 50.0]
titles = ['Initial Stage (t = 0)', 'Trapping Stage (t = 25.0)', 'Phase-Space Holes (t = 50.0)']

# 创建 1 行 3 列的宽幅画布，非常适合 PPT 宽屏展示
fig, axes = plt.subplots(1, 3, figsize=(18, 5), sharey=True)

# ==================== 3. 循环绘图 ====================
for i, t_val in enumerate(eval_times):
    # 计算对应的时间步索引
    step_idx = int(t_val / dt)
    # 防止索引越界
    if step_idx >= len(f_data):
        step_idx = len(f_data) - 1

    f_true = f_data[step_idx]
    ax = axes[i]

    # 核心绘图：使用 jet 伪彩色图，并加入 bilinear 使得像素平滑过渡
    im = ax.imshow(f_true.T, extent=[0, 10.0, -5.0, 5.0],
                   origin='lower', aspect='auto', cmap='jet',
                   interpolation='bilinear', vmax=0.7)

    # 设置标题和坐标轴标签
    ax.set_title(f"PIC Truth: {titles[i]}", fontsize=14, pad=10)
    ax.set_xlabel('Position $x$ [$\lambda_D$]', fontsize=12)
    ax.tick_params(axis='both', which='major', labelsize=10)

    if i == 0:
        ax.set_ylabel('Velocity $v$ [$v_{th}$]', fontsize=12)

# ==================== 4. 美化与保存 ====================
# 添加全局统一的 Colorbar
cbar = fig.colorbar(im, ax=axes.ravel().tolist(), pad=0.02)
cbar.set_label('Electron Distribution Function $f(x,v)$', fontsize=12)

# 添加总标题
plt.suptitle('Fully Kinetic PIC Simulation - Two-Stream Instability', fontsize=18, y=1.05, fontweight='bold')

# 保存为 300dpi 的高清 PNG 图片，直接贴到 PPT 里非常清晰
plt.savefig('PIC_GroundTruth_HighRes.png', dpi=300, bbox_inches='tight')
print("高清图片已保存为: PIC_GroundTruth_HighRes.png")

plt.show()