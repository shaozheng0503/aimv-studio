"""图 7.2 Pipeline 时延分解饼图 + 用户研究 MOS 维度柱状图"""
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

matplotlib.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC',
                                          'Arial Unicode MS', 'STHeiti']
matplotlib.rcParams['axes.unicode_minus'] = False

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6.5), dpi=140)

# ========== 左：Pipeline 时延分解 饼图 ==========
labels = ['视频串行生成', '音乐生成', '图像并发', '合成', 'Agent 规划',
          '音乐分析', '网络与队列']
sizes = [360, 90, 60, 45, 35, 8, 12]  # 秒
colors = ['#EF5350', '#FF9800', '#FFC107', '#66BB6A', '#42A5F5', '#26A69A', '#BDBDBD']
explode = [0.06, 0, 0, 0, 0, 0, 0]  # 突出"视频串行"

wedges, texts, autotexts = ax1.pie(sizes,
                                    labels=[f'{l}\n{s}s' for l, s in zip(labels, sizes)],
                                    colors=colors, explode=explode,
                                    autopct='%1.1f%%',
                                    pctdistance=0.78,
                                    startangle=90,
                                    textprops={'fontsize': 10},
                                    wedgeprops={'edgecolor': 'white', 'linewidth': 1.5})
for at in autotexts:
    at.set_color('white')
    at.set_fontweight('bold')
    at.set_fontsize(9.5)

total = sum(sizes)
ax1.text(0, 0, f'总耗时\n{total}s\n({total//60}m{total%60}s)',
         ha='center', va='center', fontsize=12, fontweight='bold')
ax1.set_title('(a) Pipeline 端到端时延分解\n(30s 输入, 4 分镜, API 模式)',
              fontsize=12.5, fontweight='bold', pad=15)

# ========== 右：用户研究 MOS 柱状图 ==========
dims = ['视觉质量', '剧情连贯性', '节奏感', '整体满意度']
means = [3.8, 3.6, 4.1, 3.9]
stds = [0.6, 0.7, 0.5, 0.6]
ci_low = [3.5, 3.3, 3.9, 3.6]
ci_high = [4.1, 3.9, 4.4, 4.2]

x = np.arange(len(dims))
bars = ax2.bar(x, means, yerr=[np.array(means)-np.array(ci_low),
                                np.array(ci_high)-np.array(means)],
               color=['#5C6BC0', '#26A69A', '#FFA726', '#AB47BC'],
               capsize=8, alpha=0.85, edgecolor='#333', linewidth=1.2,
               error_kw={'lw': 1.8, 'color': '#555'})

# 在柱顶标数值
for i, (m, s) in enumerate(zip(means, stds)):
    ax2.text(i, m + 0.55, f'{m}\n±{s}', ha='center', va='bottom',
             fontsize=10, fontweight='bold')

# 阈值线
ax2.axhline(y=3.0, color='#C62828', linestyle='--', lw=1.5, alpha=0.7)
ax2.text(3.6, 3.05, '可接受阈值 3.0', fontsize=9, color='#C62828', va='bottom', ha='right')

ax2.set_xticks(x)
ax2.set_xticklabels(dims, fontsize=11)
ax2.set_ylabel('MOS 评分 (5 分制 Likert)', fontsize=11)
ax2.set_ylim(0, 5.4)
ax2.set_yticks([0, 1, 2, 3, 4, 5])
ax2.set_title('(b) 用户研究 MOS 评分 (n=18, 误差棒为 95% CI)',
              fontsize=12.5, fontweight='bold', pad=15)
ax2.grid(axis='y', alpha=0.3, linestyle=':')
ax2.spines['top'].set_visible(False)
ax2.spines['right'].set_visible(False)

# 节奏感最高的标注
ax2.annotate('节奏感最高\n音乐结构对齐\n方法的设计直觉印证',
             xy=(2, 4.1), xytext=(2.5, 4.7),
             fontsize=9, color='#E65100', ha='center',
             arrowprops=dict(arrowstyle='->', color='#E65100', lw=1.3),
             bbox=dict(boxstyle='round,pad=0.3', fc='#FFF3E0',
                       ec='#E65100', lw=1, alpha=0.9))

plt.suptitle('图 7.2 系统性能指标', fontsize=14, fontweight='bold', y=1.02)
plt.tight_layout()
plt.savefig('docs/figures_generated/fig7_2_metrics.png',
            dpi=160, bbox_inches='tight', facecolor='white')
print('SAVED: docs/figures_generated/fig7_2_metrics.png')
