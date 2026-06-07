"""国风专题 collage：4 张连续分镜帧 + 标签
用于展示"跨镜头一致性"——同一主角在 4 个分镜中外貌服饰保持稳定
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

FRAME_DIR = Path('docs/figures_generated/mv_frames')
OUT = Path('docs/figures_generated/fig6_7_guofeng_consistency.png')

frames = [
    ('guofeng_01_overlook', '镜头 1 · 远景\n少女独立山间，俯瞰云海'),
    ('guofeng_02_peach',    '镜头 2 · 中景\n桃花林中起舞'),
    ('guofeng_03_singing',  '镜头 3 · 近景演唱\n含泪深情演唱'),
    ('guofeng_04_dusk',     '镜头 4 · 远景收尾\n夕阳石桥独行'),
]

T = 480
GAP = 14
LABEL_H = 70
PAD = 24
TITLE_H = 56

W = PAD*2 + 4*T + 3*GAP
H = PAD*2 + T + LABEL_H + TITLE_H + 80  # +80 for bottom annotation

canvas = Image.new('RGB', (W, H), 'white')
draw = ImageDraw.Draw(canvas)

def load_font(size):
    for p in [
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Medium.ttc',
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

title_font = load_font(28)
label_font = load_font(18)
note_font = load_font(16)

draw.text((PAD, 8),
          '图 6.7 国风系列连续分镜帧 ── 跨镜头一致性示意',
          fill='black', font=title_font)
draw.text((PAD, 48),
          '同一主角（淡粉汉服 + 金色腰带 + 长黑发）在四个不同场景的分镜中保持发型、服饰、风格的视觉连续',
          fill='#555', font=note_font)

y = PAD + TITLE_H
for i, (name, label) in enumerate(frames):
    x = PAD + i * (T + GAP)
    p = FRAME_DIR / f'{name}.png'
    if p.exists():
        img = Image.open(p).convert('RGB')
        img = img.resize((T, T), Image.LANCZOS)
        canvas.paste(img, (x, y))
        # 角标
        draw.rectangle([x, y, x+44, y+30], fill=(0, 0, 0))
        draw.text((x+12, y+5), f'{i+1}', fill='white', font=label_font)
    # 标签
    draw.text((x, y + T + 8), label, fill='#222', font=label_font)

# 底部说明
draw.text((PAD, y + T + LABEL_H + 16),
          '机制：character_bank 在 Screenwriter 阶段一次固化角色描述 + 末帧链路把上镜末帧作为下镜起始参考帧（详见 3.4 / 3.5 节）',
          fill='#1565C0', font=note_font)

canvas.save(OUT, optimize=True, quality=92)
print(f'SAVED: {OUT} ({OUT.stat().st_size//1024} KB)')
