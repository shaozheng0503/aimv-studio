"""把 12 张 MV 示例帧拼合为 3 行 4 列的 collage（替换图 6.5 mv_runtime_collage.png）
每行一组风格，演示"跨镜头一致性 + 不同风格的端到端生成能力"
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import sys

FRAME_DIR = Path('docs/figures_generated/mv_frames')
OUT_PATH = Path('docs/figures_generated/fig6_5_mv_collage.png')

groups = [
    ('国风古典：少女 · 云海 · 桃花 · 演唱 · 夕阳',
     ['guofeng_01_overlook', 'guofeng_02_peach',
      'guofeng_03_singing', 'guofeng_04_dusk']),
    ('赛博朋克：少女 · 霓虹街 · 特写 · 天台 · 奔跑',
     ['cyber_01_neon', 'cyber_02_close',
      'cyber_03_rooftop', 'cyber_04_run']),
    ('复古迪斯科：少女 · 舞池 · 特写 · 人群 · 离场',
     ['disco_01_dance', 'disco_02_close',
      'disco_03_crowd', 'disco_04_outside']),
]

# 配置
THUMB = 384  # 每张缩略图边长
GAP = 12     # 间距
LABEL_H = 50 # 行标题高度
PAD = 20     # 整体边距

rows = len(groups)
cols = 4
W = PAD*2 + cols*THUMB + (cols-1)*GAP
H = PAD*2 + rows*THUMB + (rows-1)*GAP + rows*LABEL_H + 40  # +40 for title

canvas = Image.new('RGB', (W, H), 'white')
draw = ImageDraw.Draw(canvas)

# 字体
def load_font(size):
    for p in [
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/System/Library/Fonts/Helvetica.ttc',
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

title_font = load_font(26)
label_font = load_font(17)

# 整图标题
draw.text((PAD, 4), '图 6.5 系统生成 MV 的连续分镜帧（3 组风格 × 每组 4 镜）',
          fill='black', font=title_font)

y = PAD + 36
missing_log = []
for grp_idx, (label, names) in enumerate(groups):
    # 行标题
    draw.text((PAD, y), f'· {label}', fill='#333', font=label_font)
    y += LABEL_H

    # 4 张图
    for col_idx, name in enumerate(names):
        x = PAD + col_idx * (THUMB + GAP)
        p = FRAME_DIR / f'{name}.png'
        if p.exists() and p.stat().st_size > 50000:
            img = Image.open(p).convert('RGB')
            img = img.resize((THUMB, THUMB), Image.LANCZOS)
            canvas.paste(img, (x, y))
            # 分镜编号角标
            draw.rectangle([x, y, x+40, y+24], fill=(0, 0, 0, 180))
            draw.text((x+8, y+3), f'{col_idx+1}', fill='white', font=label_font)
        else:
            # 占位（图还未生成）
            draw.rectangle([x, y, x+THUMB, y+THUMB], fill='#EEE', outline='#999')
            draw.text((x + THUMB//2 - 50, y + THUMB//2 - 10),
                      '(未生成)', fill='#999', font=label_font)
            missing_log.append(name)
    y += THUMB + GAP

# 底部说明
draw.text((PAD, H - 30),
          '注：演示跨镜头一致性（同一主角在 4 个分镜的发型 / 服饰 / 风格保持稳定）与多风格端到端生成能力',
          fill='#555', font=label_font)

canvas.save(OUT_PATH, optimize=True, quality=92)
print(f'SAVED: {OUT_PATH} ({OUT_PATH.stat().st_size//1024} KB)')
if missing_log:
    print(f'MISSING ({len(missing_log)}):', missing_log)
