"""图 3.3 ShotRouter + ModelRouter 路由与容灾切换"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC',
                                          'Arial Unicode MS', 'STHeiti']

fig, ax = plt.subplots(figsize=(14, 8.5), dpi=140)
ax.set_xlim(0, 14)
ax.set_ylim(0, 8.5)
ax.axis('off')

def box(x, y, w, h, text, color, fs=10, fw='normal', ec='#333'):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.06,rounding_size=0.15",
                                linewidth=1.2, facecolor=color, edgecolor=ec))
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fs, fontweight=fw)

def arrow(x1, y1, x2, y2, label='', color='#333', ls='-', curve=0.0, lw=1.5, fs=8.5):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                 connectionstyle=f"arc3,rad={curve}",
                                 arrowstyle='-|>', mutation_scale=15,
                                 linewidth=lw, color=color, linestyle=ls))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my + 0.15, label, ha='center', va='center',
                fontsize=fs, color=color, style='italic',
                bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.85))

ax.text(7, 8.05, '图 3.3 ShotRouter 决策矩阵 + ModelRouter 容灾切换',
        ha='center', fontsize=13.5, fontweight='bold')

# === 上层：Director 输出 ===
box(0.5, 6.7, 3.5, 1.0,
    'Director 输出每镜\nlabel + style + duration',
    '#B7D9F7', 10.5, 'bold')

# === ShotRouter 决策矩阵 ===
box(5.0, 6.4, 8.5, 1.6,
    'ShotRouter 决策矩阵',
    '#FFF5DA', 11, 'bold')
matrix_text = [
    ('sing + cinematic',  'Seedance 2.0',  'Veo 3.1',     'Wan2.2 14B'),
    ('sing + stylized',   'Grok Video',    'Seedance',    'Wan2.2 14B'),
    ('story + cinematic', 'Veo 3.1',       'Seedance',    'Wan2.2 14B'),
    ('story + stylized',  'Grok Video',    'Veo 3.1',     'Wan2.2 14B'),
    ('story + 其他',      'Wan2.2 14B',    'Veo 3.1',     '占位帧'),
]
# 表头
ax.text(5.2, 7.55, '镜头类型', fontsize=9, fontweight='bold')
ax.text(7.4, 7.55, '首选', fontsize=9, fontweight='bold', color='#2E7D32')
ax.text(9.4, 7.55, '次选', fontsize=9, fontweight='bold', color='#F57C00')
ax.text(11.6, 7.55, '兜底', fontsize=9, fontweight='bold', color='#C62828')
ax.plot([5.1, 13.4], [7.45, 7.45], 'k-', lw=0.8, alpha=0.5)
for i, row in enumerate(matrix_text):
    y = 7.3 - (i+1) * 0.18
    ax.text(5.2, y, row[0], fontsize=8.5)
    ax.text(7.4, y, row[1], fontsize=8.5, color='#2E7D32')
    ax.text(9.4, y, row[2], fontsize=8.5, color='#F57C00')
    ax.text(11.6, y, row[3], fontsize=8.5, color='#C62828')

arrow(4.0, 7.2, 5.0, 7.2, color='#333', lw=1.6)

# === 中层：选中的视频模型 ===
box(5.0, 4.8, 8.5, 0.9,
    '选中模型：调用 Adapter.generate(prompt, init_image, duration)',
    '#C8E6C9', 10.5, 'bold')
arrow(9.2, 6.4, 9.2, 5.7, color='#333', lw=1.6)

# === ModelRouter 容灾切换 ===
box(0.5, 3.3, 13.0, 1.2,
    'ModelRouter 容灾切换层',
    '#FFC9C9', 11, 'bold')

faults = [
    ('超时\n>90s', '#FFE0B2', '切次选\n冷却 60s'),
    ('限流\nHTTP 429', '#FFE0B2', '指数退避\n重试 3 次'),
    ('余额不足\nHTTP 402', '#FFE0B2', '切开源\nWan2.2'),
    ('内容审核\n失败', '#FFE0B2', '回 Director\n软化措辞'),
    ('返回\n格式错误', '#FFE0B2', '同模型\n重试 1 次'),
]
for i, (cause, c, action) in enumerate(faults):
    x = 0.7 + i*2.55
    box(x, 3.5, 1.1, 0.85, cause, c, 9, 'bold')
    box(x + 1.2, 3.5, 1.1, 0.85, action, '#FFCDD2', 8.5)
    arrow(x + 1.1, 3.92, x + 1.2, 3.92, color='#C62828', lw=1.3)
arrow(7.0, 4.8, 7.0, 4.5, color='#C62828', lw=1.6, ls='--',
      label='故障触发', fs=9)

# === 下层：三种全局策略 ===
box(0.5, 1.4, 4.0, 1.4,
    '【开源优先】\n所有镜头默认 Wan2.2 14B\n闭源仅在 Verifier 回退时启用\n适合：成本敏感',
    '#E1BEE7', 9.5, 'bold')
box(5.0, 1.4, 4.0, 1.4,
    '【自动模式（默认）】\n按决策矩阵动态选型\nModelRouter 容灾自适应\n适合：常规用户',
    '#FFF9C4', 9.5, 'bold')
box(9.5, 1.4, 4.0, 1.4,
    '【闭源优先】\n按 ShotRouter 矩阵执行\n开源仅作兜底\n适合：追求最高质量',
    '#B2DFDB', 9.5, 'bold')

# 总控线
ax.text(7, 2.95, '全局策略（用户在工作台手动切换）',
        ha='center', fontsize=11, fontweight='bold')

arrow(7.0, 3.3, 7.0, 2.85, color='#666', lw=1.5)

# === 底部：参数动态调节 ===
box(0.5, 0.2, 13.0, 0.85,
    '动态参数调节  ──  Verifier 连续低分时：cfg_scale 7.5→9.0→11.0  ·  temperature 0.7→0.4→0.2  ·  seed 随机化',
    '#D7CCC8', 10, 'bold')
arrow(7.0, 1.4, 7.0, 1.05, color='#5D4037', lw=1.5,
      label='', fs=9)

plt.tight_layout()
plt.savefig('docs/figures_generated/fig3_3_router.png',
            dpi=160, bbox_inches='tight', facecolor='white')
print('SAVED: docs/figures_generated/fig3_3_router.png')
