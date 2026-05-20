"""v_spread 受控对比评估：加载三个模型，生成 Loss+相空间对比图"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch, numpy as np
import torch.nn as nn
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from shared.models.hamiltonian import NeuralHamiltonianFlow

def w1(u, v):
    return np.sum(np.abs(np.sort(u) - np.sort(v))) / len(u)

device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f'Device: {device}')

L_steps, dt = 10, 0.25
configs = [
    ('vspread_005', 0.05, 'steelblue'),
    ('vspread_010', 0.10, 'darkorange'),
    ('vspread_020', 0.20, 'seagreen'),
]

fig = plt.figure(figsize=(18, 15))
results = {}

for row, (folder, vsp, color) in enumerate(configs):
    # Load data
    Q25 = np.load(f'data/two_stream/{folder}/Q25.npy')
    P25 = np.load(f'data/two_stream/{folder}/P25.npy')
    Q00 = np.load(f'data/two_stream/{folder}/Q00.npy')
    P00 = np.load(f'data/two_stream/{folder}/P00.npy')
    Cond = np.load(f'data/two_stream/{folder}/Cond.npy')

    # Load model
    model = NeuralHamiltonianFlow(L_steps=L_steps, dt=-dt).to(device).double()
    try:
        model.load_state_dict(torch.load(f'models/two_stream/{folder}/model_final', map_location=device))
        model.eval()
    except FileNotFoundError:
        print(f'WARNING: Model not found for {folder}, skipping')
        continue

    # Load loss
    train_loss = np.load(f'models/two_stream/{folder}/training_loss_final.npy')
    val_loss = np.load(f'models/two_stream/{folder}/validation_loss_final.npy')

    # Pick test sample (last 20% as validation)
    test_idx = 400  # index 400-499 are "unseen" (training uses 0-399)

    # Predict
    q0 = torch.tensor(Q00[test_idx], dtype=torch.float64).to(device)
    p0 = torch.tensor(P00[test_idx], dtype=torch.float64).to(device)
    q_pred, p_pred = model.sample(q0, p0, nsteps=L_steps, delta_t=dt)
    q_pred, p_pred = q_pred.cpu().numpy().squeeze(0), p_pred.cpu().numpy().squeeze(0)

    q_true, p_true = Q25[test_idx], P25[test_idx]
    w1_q = w1(q_pred, q_true)
    w1_p = w1(p_pred, p_true)

    vs = Cond[test_idx, 0]
    alpha = vs / vsp
    results[folder] = {'w1_q': w1_q, 'w1_p': w1_p, 'train_loss': train_loss, 'val_loss': val_loss,
                       'alpha': alpha, 'v_stream': vs}

    # Column 1: Loss curve
    ax1 = fig.add_subplot(3, 3, row*3 + 1)
    epochs = range(1, len(train_loss)+1)
    ax1.plot(epochs, train_loss, color=color, linewidth=1.5, alpha=0.85, label='Train')
    ax1.plot(epochs, val_loss, color=color, linewidth=1.5, alpha=0.4, linestyle='--', label='Val')
    ax1.axhline(y=104, color='gray', linestyle=':', alpha=0.5, linewidth=0.8)
    ax1.set_xlabel('Epoch'); ax1.set_ylabel('Loss')
    ax1.set_title(f'v_spread={vsp}, alpha={alpha:.1f}\n'
                  f'Train: {train_loss[0]:.0f} -> {train_loss[-1]:.0f} (min={min(train_loss):.0f})',
                  fontsize=10)
    ax1.legend(fontsize=8, loc='upper right')
    ax1.grid(True, alpha=0.3)

    # Column 2: PIC Ground Truth
    ax2 = fig.add_subplot(3, 3, row*3 + 2)
    ax2.scatter(q_true, p_true, s=1, alpha=0.4, color='crimson', edgecolors='none', rasterized=True)
    ax2.set_xlabel('Position x'); ax2.set_ylabel('Velocity v')
    ax2.set_title(f'PIC t=2.5 (Ground Truth)\nv_stream={vs:.2f}, v_spread={vsp}', fontsize=10)
    ax2.set_xlim(0, 10); ax2.set_ylim(-2.5, 2.5)

    # Column 3: HNF Prediction
    ax3 = fig.add_subplot(3, 3, row*3 + 2)  # Wait, this overwrites col 2...
    # Actually let me use a different layout

plt.close()

# Redo with correct layout
fig, axes = plt.subplots(3, 3, figsize=(16, 13))

for row, (folder, vsp, color) in enumerate(configs):
    Q25 = np.load(f'data/two_stream/{folder}/Q25.npy')
    P25 = np.load(f'data/two_stream/{folder}/P25.npy')
    Q00 = np.load(f'data/two_stream/{folder}/Q00.npy')
    P00 = np.load(f'data/two_stream/{folder}/P00.npy')
    Cond = np.load(f'data/two_stream/{folder}/Cond.npy')

    model = NeuralHamiltonianFlow(L_steps=L_steps, dt=-dt).to(device).double()
    try:
        model.load_state_dict(torch.load(f'models/two_stream/{folder}/model_final', map_location=device))
        model.eval()
    except FileNotFoundError:
        for j in range(3):
            axes[row, j].text(0.5, 0.5, 'Model not trained yet', ha='center', va='center')
            axes[row, j].set_title(f'v_spread={vsp} (NOT FOUND)')
        continue

    train_loss = np.load(f'models/two_stream/{folder}/training_loss_final.npy')
    val_loss = np.load(f'models/two_stream/{folder}/validation_loss_final.npy')
    test_idx = 400
    q0 = torch.tensor(Q00[test_idx], dtype=torch.float64).to(device)
    p0 = torch.tensor(P00[test_idx], dtype=torch.float64).to(device)
    q_pred, p_pred = model.sample(q0, p0, nsteps=L_steps, delta_t=dt)
    q_pred, p_pred = q_pred.cpu().numpy().squeeze(0), p_pred.cpu().numpy().squeeze(0)
    q_true, p_true = Q25[test_idx], P25[test_idx]
    w1_q = w1(q_pred, q_true)
    w1_p = w1(p_pred, p_true)
    vs = Cond[test_idx, 0]
    alpha = vs / vsp

    # Col 1: Loss
    ax = axes[row, 0]
    epochs = range(1, len(train_loss)+1)
    ax.plot(epochs, train_loss, color=color, linewidth=1.5, alpha=0.9, label='Train')
    ax.plot(epochs, val_loss, color=color, linewidth=1.2, alpha=0.35, linestyle='--', label='Val')
    ax.set_xlabel('Epoch'); ax.set_ylabel('Loss')
    ax.set_title(f'v_spread={vsp} | alpha={alpha:.1f} | min={min(train_loss):.0f}', fontsize=9)
    ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

    # Col 2: PIC (t=2.5)
    ax = axes[row, 1]
    ax.scatter(q_true, p_true, s=1, alpha=0.4, color='crimson', edgecolors='none', rasterized=True)
    ax.set_xlabel('x'); ax.set_ylabel('v')
    ax.set_title(f'PIC t=2.5 (v_spread={vsp})', fontsize=9)
    ax.set_xlim(0, 10); ax.set_ylim(-2.5, 2.5)

    # Col 3: HNF (t=2.5)
    ax = axes[row, 2]
    ax.scatter(q_pred, p_pred, s=1, alpha=0.4, color=color, edgecolors='none', rasterized=True)
    ax.set_xlabel('x'); ax.set_ylabel('v')
    ax.set_title(f'HNF t=2.5 | W1(x)={w1_q:.3f} W1(v)={w1_p:.3f}', fontsize=9)
    ax.set_xlim(0, 10); ax.set_ylim(-2.5, 2.5)

    results[folder] = {'w1_q': w1_q, 'w1_p': w1_p, 'train_min': min(train_loss),
                       'train_final': train_loss[-1], 'alpha': alpha}

plt.suptitle(f'v_spread Comparison: Two-Stream PDE-NHF\n(L={L_steps}, dt={dt}, N_train=400, Epochs=200)',
             fontsize=12, y=1.01)
plt.tight_layout()
plt.savefig('models/two_stream/v_spread_comparison_results.png', dpi=150, bbox_inches='tight')
print('Saved: models/two_stream/v_spread_comparison_results.png')

# Print summary
print('\n====== Summary ======')
print(f'{"v_spread":>12} {"alpha":>8} {"W1(x)":>8} {"W1(v)":>8} {"Loss(min)":>10} {"Loss(final)":>12}')
for folder, vsp, _ in configs:
    if folder in results:
        r = results[folder]
        print(f'{vsp:>12.2f} {r["alpha"]:>8.1f} {r["w1_q"]:>8.3f} {r["w1_p"]:>8.3f} {r["train_min"]:>10.0f} {r["train_final"]:>12.0f}')
    else:
        print(f'{vsp:>12.2f} {"N/A":>8} {"N/A":>8} {"N/A":>8} {"N/A":>10} {"N/A":>12}')
