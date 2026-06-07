"""图 5.2 项目状态机"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
import matplotlib
import numpy as np

matplotlib.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC',
                                          'Arial Unicode MS', 'STHeiti']

fig, ax = plt.subplots(figsize=(13, 7.5), dpi=140)
ax.set_xlim(0, 13)
ax.set_ylim(0, 7.5)
ax.axis('off')

def state_circle(cx, cy, r, label, sub, color, fontsize=11):
    ax.add_patch(Circle((cx, cy), r, facecolor=color, edgecolor='#333', linewidth=1.5))
    ax.text(cx, cy + 0.12, label, ha='center', va='center',
            fontsize=fontsize, fontweight='bold')
    ax.text(cx, cy - 0.25, sub, ha='center', va='center',
            fontsize=8.5, color='#444')

def arc_arrow(x1, y1, x2, y2, label='', color='#333', ls='-', curve=0.0, lw=1.5, fs=9,
              label_offset=(0, 0.2)):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                 connectionstyle=f"arc3,rad={curve}",
                                 arrowstyle='-|>', mutation_scale=15,
                                 linewidth=lw, color=color, linestyle=ls))
    if label:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx + label_offset[0], my + label_offset[1], label,
                ha='center', va='center', fontsize=fs, color=color, style='italic',
                bbox=dict(boxstyle='round,pad=0.15', fc='white', ec='none', alpha=0.9))

ax.text(6.5, 7.05, '图 5.2 项目状态机：状态转移与异常回退',
        ha='center', fontsize=13.5, fontweight='bold')

# 五个主要状态 + failed
# 横向布局
y = 4.5
states = [
    (1.5,  y,  0.7, 'draft',      '草稿',      '#FFE0B2'),
    (4.0,  y,  0.7, 'planning',   '规划中',    '#FFF59D'),
    (6.5,  y,  0.7, 'planned',    '已规划',    '#C5E1A5'),
    (9.0,  y,  0.7, 'generating', '生成中',    '#90CAF9'),
    (11.5, y,  0.7, 'done',       '完成',      '#A5D6A7'),
]
for cx, cy, r, label, sub, color in states:
    state_circle(cx, cy, r, label, sub, color)

# Failed 状态 (下方)
state_circle(6.5, 1.5, 0.7, 'failed', '失败', '#EF9A9A')

# 起始状态
ax.add_patch(Circle((0.4, y), 0.15, facecolor='#333'))
arc_arrow(0.55, y, 0.8, y, color='#333', lw=2.0)

# === 正向转移 ===
arc_arrow(2.2, y, 3.3, y,
          label='生成分镜', color='#1565C0', lw=1.8,
          label_offset=(0, 0.25))
arc_arrow(4.7, y, 5.8, y,
          label='Agent 全成功', color='#1565C0', lw=1.8,
          label_offset=(0, 0.25))
arc_arrow(7.2, y, 8.3, y,
          label='开始生成 MV', color='#1565C0', lw=1.8,
          label_offset=(0, 0.25))
arc_arrow(9.7, y, 10.8, y,
          label='Pipeline 合成完成', color='#1565C0', lw=1.8,
          label_offset=(0, 0.25))

# === 失败回退 ===
arc_arrow(4.0, y - 0.7, 6.5, 1.5 + 0.6,
          label='Agent 报错', color='#C62828', lw=1.5, curve=-0.2,
          label_offset=(0.3, 0.0))
arc_arrow(9.0, y - 0.7, 6.5 + 0.5, 1.5 + 0.5,
          label='Pipeline 全部失败', color='#C62828', lw=1.5, curve=0.2,
          label_offset=(-0.3, 0.0))

# === 重试 ===
arc_arrow(6.5 - 0.7, 1.5, 4.0, y - 0.7,
          label='', color='#FF6F00', lw=1.5, curve=-0.2, ls='--')
ax.text(4.6, 2.7, '用户点击重试\n回到失败前状态',
        fontsize=9, color='#FF6F00', style='italic', ha='center')

# === Done -> Generating (重新生成) ===
arc_arrow(11.5, y + 0.7, 9.0, y + 0.7,
          label='用户编辑后重新生成', color='#7B1FA2', lw=1.5, curve=0.3,
          label_offset=(0, 0.35))

# === 用户手动取消 ===
arc_arrow(4.0, y + 0.7, 1.5, y + 0.7,
          label='用户手动取消', color='#666', lw=1.3, curve=-0.4, ls=':',
          label_offset=(0, 0.3))

# === 局部失败但仍 done ===
ax.add_patch(FancyArrowPatch((9.0 + 0.5, y + 0.5), (9.0 + 0.5, y + 0.5),
                             connectionstyle="arc3,rad=2.5",
                             arrowstyle='-|>', mutation_scale=12,
                             linewidth=1.3, color='#888'))
ax.text(9.0, y + 1.6, '部分镜头失败\n占位帧填充仍 done',
        fontsize=9, color='#888', style='italic', ha='center')

# === 旁注 ===
box_text = ('状态由后端 Project.status 字段单点维护\n'
            'WebSocket 实时推送，前端被动更新\n'
            '同一项目 generating 时拒绝重复触发 (409 Conflict)\n'
            'WebSocket 同项目最多 1 个活跃连接')
ax.text(0.5, 0.5, box_text, fontsize=9.5, ha='left',
        bbox=dict(boxstyle='round,pad=0.4', fc='#F5F5F5', ec='#999', lw=1))

# === 图例 ===
ax.annotate('', xy=(8.5, 0.6), xytext=(8.0, 0.6),
            arrowprops=dict(arrowstyle='-|>', color='#1565C0', lw=1.8))
ax.text(8.6, 0.6, '正向转移', fontsize=9, va='center', color='#1565C0')
ax.annotate('', xy=(10.7, 0.6), xytext=(10.2, 0.6),
            arrowprops=dict(arrowstyle='-|>', color='#C62828', lw=1.5))
ax.text(10.8, 0.6, '异常回退', fontsize=9, va='center', color='#C62828')
ax.annotate('', xy=(8.5, 0.2), xytext=(8.0, 0.2),
            arrowprops=dict(arrowstyle='-|>', color='#FF6F00', lw=1.5, linestyle='--'))
ax.text(8.6, 0.2, '用户重试', fontsize=9, va='center', color='#FF6F00')
ax.annotate('', xy=(10.7, 0.2), xytext=(10.2, 0.2),
            arrowprops=dict(arrowstyle='-|>', color='#7B1FA2', lw=1.5))
ax.text(10.8, 0.2, '用户编辑', fontsize=9, va='center', color='#7B1FA2')

plt.tight_layout()
plt.savefig('docs/figures_generated/fig5_2_state_machine.png',
            dpi=160, bbox_inches='tight', facecolor='white')
print('SAVED: docs/figures_generated/fig5_2_state_machine.png')
