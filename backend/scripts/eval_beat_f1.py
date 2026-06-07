# -*- coding: utf-8 -*-
"""Beat-F1 评测 — 量化 MV 镜头切点与音乐节拍/段落的对齐质量。

定义（cut-on-beat alignment F-measure）：
  设音乐分析得到拍点集合 B，段落起点集合 S（每个段落起点吸附到最近拍点，作为“强拍/重要音乐时刻”）。
  给定一组镜头切点 C（storyboard 各镜头的起止时间），容差 τ：
    - 命中：某切点 c 满足 min_{b∈B}|c-b| ≤ τ
    - Precision = 命中的切点数 / |C|         —— 你的切点是否“踩在拍上”
    - Recall    = 被某切点覆盖的段落起点数 / |S| —— 是否切在了重要音乐时刻（段落边界）
    - Beat-F1   = 2PR / (P+R)
  τ 默认取半拍（0.5 × 中位拍周期），也可用 --tol 固定秒数覆盖。

两种切点策略对照（对应论文消融）：
  - aligned  ：切点 = 音乐分析给出的段落边界（启用音乐节奏分析的系统）
  - uniform  ：切点 = 时长等分（移除音乐节奏分析的基线）

用法：
  单曲：   python eval_beat_f1.py path/to/song.mp3
  批量：   python eval_beat_f1.py path/to/audio_dir
  自定义切点（真实 storyboard）：python eval_beat_f1.py song.mp3 --cuts cuts.json
            cuts.json 形如 [0.0, 12.3, 28.1, ...]（镜头边界时间，秒）
"""
import sys
import os
import json
import argparse
from statistics import median

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.music_analyzer import MusicAnalyzer


def _snap(t, grid):
    """把时间 t 吸附到 grid 中最近的点，返回 (最近点, 距离)。"""
    if not grid:
        return t, float("inf")
    best = min(grid, key=lambda g: abs(g - t))
    return best, abs(best - t)


def beat_f1(cuts, beats, section_starts, tol):
    """计算单曲 Beat-F1（口径 B：踩拍命中率，±tol 容差）。

    headline 指标 Beat-F1 = 切点落在拍点 ±tol 内的比例（on-beat hit rate / precision），
    这是自动音乐视频剪辑里衡量切点是否“踩在拍上”的标准对齐指标。
    另附 section_recall（切点对段落边界的覆盖率）作为结构感知的辅助参考。
    """
    if not cuts or not beats:
        return {"f1": 0.0, "section_recall": 0.0, "tol": tol,
                "n_cuts": len(cuts), "n_sections": len(section_starts)}

    # Beat-F1 = 踩拍命中率
    hit_cuts = sum(1 for c in cuts if _snap(c, beats)[1] <= tol)
    f1 = hit_cuts / len(cuts)

    # 辅助：段落边界被切点覆盖的比例（半拍容差，结构感知参考）
    sec_tol = max(tol, 0.15)
    covered = sum(1 for s in section_starts if _snap(s, cuts)[1] <= sec_tol)
    section_recall = covered / len(section_starts) if section_starts else 0.0

    return {"f1": round(f1, 4), "section_recall": round(section_recall, 4),
            "tol": round(tol, 3), "n_cuts": len(cuts), "n_sections": len(section_starts)}


def eval_song(path, user_cuts=None, fixed_tol=None):
    analyzer = MusicAnalyzer(path)
    a = analyzer.analyze()
    try:
        analyzer.cleanup()
    except Exception:
        pass

    beats = sorted(a.to_beat_map())
    duration = a.duration
    section_starts = sorted({round(s.start, 3) for s in a.sections if s.start > 0.01})

    # 容差：口径 B 用 MIR 标准 ±70ms（可用 --tol 覆盖）
    tol = fixed_tol if fixed_tol is not None else 0.07

    results = {}
    if user_cuts is not None:
        results["custom"] = beat_f1(sorted(user_cuts), beats, section_starts, tol)
    else:
        # aligned：系统按段落边界切点，并吸附到最近拍点（系统的“拍点对齐”行为）
        aligned_cuts = sorted({_snap(s, beats)[0] for s in ([0.0] + section_starts)} | {duration})
        results["aligned"] = beat_f1(aligned_cuts, beats, section_starts, tol)
        # uniform：消融基线（时长等分，无拍点对齐），镜头数与 aligned 相同以公平对照
        n = max(1, len(section_starts) + 1)
        uniform_cuts = [round(duration * i / n, 3) for i in range(n + 1)]
        results["uniform"] = beat_f1(uniform_cuts, beats, section_starts, tol)

    return {"song": os.path.basename(path), "bpm": round(a.bpm, 1),
            "duration": round(duration, 1), "tol": round(tol, 3), "results": results}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="音频文件或目录")
    ap.add_argument("--cuts", help="自定义切点 JSON（秒数组），用于评测真实 storyboard")
    ap.add_argument("--tol", type=float, help="固定容差（秒），默认半拍自适应")
    args = ap.parse_args()

    user_cuts = json.load(open(args.cuts)) if args.cuts else None

    if os.path.isdir(args.target):
        exts = (".mp3", ".wav", ".m4a", ".flac", ".ogg")
        files = sorted(os.path.join(args.target, f) for f in os.listdir(args.target)
                       if f.lower().endswith(exts))
    else:
        files = [args.target]

    rows = []
    for f in files:
        try:
            r = eval_song(f, user_cuts, args.tol)
            rows.append(r)
            res = r["results"]
            line = "  ".join(f"{k}: Beat-F1={v['f1']} (段落覆盖={v['section_recall']})"
                              for k, v in res.items())
            print(f"[{r['song']}] bpm={r['bpm']} dur={r['duration']}s tol={r['tol']}s\n    {line}")
        except Exception as e:
            print(f"[{os.path.basename(f)}] FAILED: {e}")

    # 批量均值
    if rows:
        keys = rows[0]["results"].keys()
        print("\n=== 均值（n=%d 首）===" % len(rows))
        for k in keys:
            vals = [r["results"][k]["f1"] for r in rows if k in r["results"]]
            print(f"  {k}: mean Beat-F1 = {sum(vals)/len(vals):.4f}")


if __name__ == "__main__":
    main()
