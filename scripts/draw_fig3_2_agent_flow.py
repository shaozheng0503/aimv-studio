"""图 3.2 多 Agent 协作流转图 (v2 简洁版)
重点：清晰展示串行规划 + 反思分支，不强调每个 State 字段
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mp
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Songti SC',
                                          'Arial Unicode MS', 'STHeiti']
matplotlib.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(figsize=(14, 8), dpi=140)
ax.set_xlim(0, 14)
ax.set_ylim(0, 8)
ax.axis('off')

C_INPUT = '#FFE8B0'
C_PRE = '#FFF5DA'
C_AGENT = '#B7D9F7'
C_VERIFIER = '#FFC9C9'
C_PIPE = '#C8E6C9'
C_OUT = '#FFD180'

def box(x, y, w, h, text, color, fs=10.5, fw='normal'):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle="round,pad=0.06,rounding_size=0.18",
                                linewidth=1.3, facecolor=color, edgecolor='#333'))
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fs, fontweight=fw)

def arrow(x1, y1, x2, y2, label='', color='#333', ls='-', curve=0.0,
          label_pos=0.5, label_above=True, lw=1.5, fs=9):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                 connectionstyle=f"arc3,rad={curve}",
                                 arrowstyle='-|>', mutation_scale=18,
                                 linewidth=lw, color=color, linestyle=ls))
    if label:
        mx = x1 + (x2 - x1) * label_pos
        my = y1 + (y2 - y1) * label_pos
        dy = 0.18 if label_above else -0.22
        ax.text(mx, my + dy, label, ha='center', va='center',
                fontsize=fs, color=color, style='italic',
                bbox=dict(boxstyle='round,pad=0.15', fc='white',
                          ec='none', alpha=0.85))

# === 标题 ===
ax.text(7, 7.55, '图 3.2 多 Agent 协作流转：串行规划 + 反思分支',
        ha='center', fontsize=14, fontweight='bold')

# === 第 1 行：输入 + 音乐分析 ===
box(0.4, 6.0, 2.8, 0.9, '用户输入\n一句话创意 + (可选) 音轨', C_INPUT, 10.5, 'bold')
box(3.7, 6.0, 2.8, 0.9, '音乐分析模块\nMFCC+chroma+段落聚类', C_PRE, 10.5, 'bold')
arrow(3.2, 6.45, 3.7, 6.45, color='#333', lw=1.6)

# === 第 2 行：三个串行 Agent ===
y2 = 4.3
box(0.4, y2, 2.8, 1.1,
    'Screenwriter\n剧本 Agent\nGPT-4o · temp 0.7',
    C_AGENT, 10.5, 'bold')
box(3.7, y2, 2.8, 1.1,
    'Director\n导演 Agent\nGPT-4o · temp 0.5',
    C_AGENT, 10.5, 'bold')
box(7.0, y2, 2.8, 1.1,
    'Music Producer\n音乐 Agent\nClaude Haiku · temp 0.4',
    C_AGENT, 10.5, 'bold')

# 输入箭头
arrow(1.8, 6.0, 1.8, 5.4, color='#333', lw=1.6)
arrow(5.1, 6.0, 5.1, 5.4, color='#333', lw=1.6)
# 横向串接箭头 (含字段标签)
arrow(3.2, 4.85, 3.7, 4.85,
      label='character_bank\nstoryboard', color='#1565C0', lw=1.7, fs=8.5)
arrow(6.5, 4.85, 7.0, 4.85,
      label='prompt_pack', color='#1565C0', lw=1.7, fs=8.5)
# 跨节点：Screenwriter -> Music Producer (storyboard.mood)
arrow(3.2, 4.3, 7.0, 4.4, color='#7B1FA2', curve=-0.25, ls='--',
      label='storyboard.mood', fs=8.5, label_pos=0.55)

# === 第 3 行：Pipeline 生成层 ===
y3 = 2.6
box(0.4, y3, 8.4, 1.1,
    'Pipeline 生成层  ──  图像并发 + 音乐并发  →  视频链路(末帧接力)  →  合成',
    C_PIPE, 11, 'bold')
arrow(5.1, 4.3, 5.1, 3.7, label='', color='#333', lw=1.7)

# === Verifier (右侧反思 Agent) ===
box(10.5, 3.2, 3.0, 1.7,
    'Verifier\n质检 Agent\nGPT-4o-mini · temp 0.1\n\n视觉 / 一致性 / 契合度',
    C_VERIFIER, 10.5, 'bold')

# Pipeline -> Verifier
arrow(8.8, 3.15, 10.5, 3.6, color='#444', lw=1.6,
      label='每镜送审', fs=9, label_pos=0.4)
# Verifier 反思回退 (虚线)
arrow(10.5, 4.5, 1.6, 4.85, color='#FF6F00', ls='--', curve=0.25, lw=1.8)
ax.text(5.8, 5.5,
        '反思分支：评分 < 3.0\n第1档调参重试 → 第2档换模型 → 第3档回到 Director 改 prompt → 第4档占位帧',
        ha='center', fontsize=9, color='#FF6F00', fontweight='bold',
        bbox=dict(boxstyle='round,pad=0.3', fc='#FFF3E0',
                  ec='#FF6F00', alpha=0.9))

# === 第 4 行：最终输出 ===
y4 = 0.7
box(0.4, y4, 8.4, 1.0,
    '最终输出  ──  MV 视频 + 字幕 + 元数据  →  5 大平台导出',
    C_OUT, 11, 'bold')
arrow(4.6, 2.6, 4.6, 1.7, color='#333', lw=1.7,
      label='Verifier 通过', fs=9, label_pos=0.5)

# === 图例 ===
lx, ly = 10.5, 0.3
ax.add_patch(mp.Rectangle((lx, ly + 1.1), 0.35, 0.2,
                         facecolor=C_AGENT, edgecolor='#333'))
ax.text(lx + 0.45, ly + 1.2, '生成 Agent', fontsize=9, va='center')
ax.add_patch(mp.Rectangle((lx, ly + 0.8), 0.35, 0.2,
                         facecolor=C_VERIFIER, edgecolor='#333'))
ax.text(lx + 0.45, ly + 0.9, '反思 Agent', fontsize=9, va='center')
ax.add_patch(mp.Rectangle((lx, ly + 0.5), 0.35, 0.2,
                         facecolor=C_PIPE, edgecolor='#333'))
ax.text(lx + 0.45, ly + 0.6, '生成层', fontsize=9, va='center')
ax.annotate('', xy=(lx + 1.8, ly + 1.2), xytext=(lx + 1.4, ly + 1.2),
            arrowprops=dict(arrowstyle='-|>', color='#1565C0', lw=1.5))
ax.text(lx + 1.9, ly + 1.2, '串行依赖', fontsize=9, va='center', color='#1565C0')
ax.annotate('', xy=(lx + 1.8, ly + 0.9), xytext=(lx + 1.4, ly + 0.9),
            arrowprops=dict(arrowstyle='-|>', color='#7B1FA2',
                            lw=1.5, linestyle='--'))
ax.text(lx + 1.9, ly + 0.9, '跨节点依赖', fontsize=9, va='center', color='#7B1FA2')
ax.annotate('', xy=(lx + 1.8, ly + 0.6), xytext=(lx + 1.4, ly + 0.6),
            arrowprops=dict(arrowstyle='-|>', color='#FF6F00',
                            lw=1.5, linestyle='--'))
ax.text(lx + 1.9, ly + 0.6, '反思回退', fontsize=9, va='center', color='#FF6F00')

plt.tight_layout()
plt.savefig('docs/figures_generated/fig3_2_agent_flow.png',
            dpi=160, bbox_inches='tight', facecolor='white')
print('SAVED: docs/figures_generated/fig3_2_agent_flow.png')
