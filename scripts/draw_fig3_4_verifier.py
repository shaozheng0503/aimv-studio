"""图 3.4 Verifier 三维评分 + 四档重试闭环"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Wedge
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC',
                                          'Arial Unicode MS', 'STHeiti']

fig, ax = plt.subplots(figsize=(13, 8.5), dpi=140)
ax.set_xlim(0, 13)
ax.set_ylim(0, 8.5)
ax.axis('off')

def box(x, y, w, h, text, color, fs=10, fw='normal', ec='#333'):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.06,rounding_size=0.15",
                                linewidth=1.2, facecolor=color, edgecolor=ec))
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fs, fontweight=fw)

def arrow(x1, y1, x2, y2, label='', color='#333', ls='-', curve=0.0, lw=1.5, fs=9):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                 connectionstyle=f"arc3,rad={curve}",
                                 arrowstyle='-|>', mutation_scale=15,
                                 linewidth=lw, color=color, linestyle=ls))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my + 0.15, label, ha='center', va='center',
                fontsize=fs, color=color, style='italic',
                bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.85))

ax.text(6.5, 8.05, '图 3.4 Verifier 三维评分与四档重试闭环',
        ha='center', fontsize=13.5, fontweight='bold')

# === 上层：镜头生成完成 ===
box(0.5, 6.7, 3.5, 0.9,
    '镜头视频生成完成\nvideo_url + 元数据',
    '#C8E6C9', 10.5, 'bold')

# === 中部：Verifier 三维评分 ===
box(5.5, 5.8, 6.5, 2.0,
    '',
    '#FFC9C9', 10, 'bold')
ax.text(8.75, 7.55, 'Verifier (GPT-4o-mini, temp 0.1)',
        ha='center', fontsize=11, fontweight='bold')

# 三个评分维度
dims = [
    ('视觉质量 v\n伪影 / 模糊 / 失真', 0.4, '#FFCDD2'),
    ('角色一致性 c\n与 character_bank\n对齐', 0.4, '#FFCDD2'),
    ('提示词契合度 a\n画面是否呈现\nprompt 情节', 0.2, '#FFCDD2'),
]
for i, (text, w, c) in enumerate(dims):
    x = 5.7 + i*2.1
    box(x, 6.0, 2.0, 1.3, text, c, 9, 'bold')
    ax.text(x + 1.0, 5.92, f'权重 {w}', ha='center', fontsize=8.5, color='#666')

arrow(4.0, 7.15, 5.5, 6.85, color='#333', lw=1.6)

# === 综合评分公式 ===
box(0.5, 4.2, 11.5, 0.85,
    'score = 0.4 × v + 0.4 × c + 0.2 × a   ──   阈值 θ = 3.0',
    '#FFF9C4', 11, 'bold')
arrow(8.75, 5.8, 8.75, 5.05, color='#333', lw=1.6)

# === 分支：通过 vs 失败 ===
# 通过 (左)
box(0.5, 2.5, 3.0, 1.2,
    '✓ 通过\nscore ≥ 3.0\n→ 进入下一镜头\n→ 末帧链路推进',
    '#A5D6A7', 10, 'bold', ec='#2E7D32')
arrow(3.0, 4.2, 2.0, 3.7, color='#2E7D32', lw=1.8,
      label='通过', fs=10)

# 失败 (右) → 四档重试
arrow(9.5, 4.2, 11.0, 3.7, color='#C62828', lw=1.8,
      label='评分 < 3.0', fs=10)

# 四档重试链
box(5.5, 2.8, 7.0, 1.05,
    '第 1 档  ──  保持模型 + cfg_scale 调高 + 换 seed',
    '#FFE0B2', 10, 'bold')
box(5.5, 1.7, 7.0, 1.05,
    '第 2 档  ──  切换到 ShotRouter 中的 fallback 模型',
    '#FFCC80', 10, 'bold')
box(5.5, 0.6, 7.0, 1.05,
    '第 3 档  ──  回到 Director 改写 prompt（带失败原因摘要）',
    '#FFB74D', 10, 'bold')
# 第 4 档放在最底层
ax.text(9.0, 0.2,
        '第 4 档（极少触发）：使用前镜末帧作为占位帧',
        ha='center', fontsize=9.5, fontweight='bold', color='#5D4037')

# 重试递进箭头
for y0 in [3.3, 2.2]:
    arrow(9.0, y0 - 0.45, 9.0, y0 - 0.55, color='#FF6F00', lw=1.5)

# 失败原因反馈回 Verifier
arrow(5.5, 3.3, 7.7, 6.0, color='#7B1FA2', curve=0.3, ls='--', lw=1.5)
ax.text(6.2, 4.7, '失败原因\ncomment 反馈',
        fontsize=8.5, color='#7B1FA2', style='italic')

# === 旁注：缓解 LLM 自评偏置 ===
box(0.5, 0.2, 4.5, 1.8,
    '【缓解 LLM 自评偏置】\n\n· Verifier 选 GPT-4o-mini\n  (与生成端 GPT-4o 非同族)\n\n· CLIPScore 客观指标\n  做交叉校验\n\n· 显著偏离时启用\n  二次复检 (temp=0)',
    '#E0E0E0', 9, 'normal', ec='#666')

plt.tight_layout()
plt.savefig('docs/figures_generated/fig3_4_verifier.png',
            dpi=160, bbox_inches='tight', facecolor='white')
print('SAVED: docs/figures_generated/fig3_4_verifier.png')
