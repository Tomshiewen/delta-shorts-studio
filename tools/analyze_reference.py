#!/usr/bin/env python3
"""
对标视频拆解器。
输入一个视频文件，输出「结构与节奏」的可量化报告 + 缩略图拼版（供人眼判风格）。

能可靠给出：分辨率/帧率/时长/编码、镜头切点、每个镜头时长、平均镜头长度、
前 3 秒镜头数（钩子节奏）、运动强度、主色调、字幕带位置、缩略图拼版。
不能给出：用了哪个剪辑软件/滤镜/AI 模型 —— 那只能猜，本脚本不猜。

用法：
  python analyze_reference.py <视频路径> [--out 输出目录] [--frames N]
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np


def safe(v, d=0.0):
    try:
        f = float(v)
        if f != f or f in (float("inf"), float("-inf")):
            return d
        return f
    except Exception:
        return d


def analyze(path, outdir, sheet_frames=15, max_frames=4000):
    if not os.path.exists(path):
        print(f"找不到文件：{path}")
        return 1
    os.makedirs(outdir, exist_ok=True)

    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        print(f"cv2 打不开：{path}")
        return 1

    fps = safe(cap.get(cv2.CAP_PROP_FPS), 30.0) or 30.0
    total = int(safe(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    w = int(safe(cap.get(cv2.CAP_PROP_FRAME_WIDTH)))
    h = int(safe(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    fourcc = int(safe(cap.get(cv2.CAP_PROP_FOURCC)))
    codec = "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4)).strip("\x00").strip()
    duration = total / fps if fps else 0.0

    # 竖屏按 160x284、横屏按 284x160 归一化，便于统一比较
    size = (160, 284) if h >= w else (284, 160)
    step = max(1, total // max_frames) if total else 1
    sheet_at = set()
    if sheet_frames > 0 and total > 0:
        sheet_at = {int(round(x)) for x in np.linspace(0, max(total - 1, 0), sheet_frames)}

    prev_hist = None
    prev_gray = None
    cuts = []
    motion_series = []
    sub_positions = []
    color_samples = []
    sheet = []
    frames_read = 0
    i = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames_read += 1

        if i % step == 0:
            small = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

            hist = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
            cv2.normalize(hist, hist)

            if prev_hist is not None:
                corr = safe(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL), 1.0)
                pix = safe(np.mean(cv2.absdiff(prev_gray, gray)))
                motion_series.append(round(pix, 2))
                if corr < 0.55 or pix > 30:
                    cuts.append({
                        "frame": i, "t": round(i / fps, 2),
                        "histCorr": round(corr, 3), "pixDiff": round(pix, 2)
                    })
            prev_hist = hist
            prev_gray = gray

            # 字幕带检测：下方 55% 区域里水平边缘最密的那一行（文字特征）
            edges = np.abs(cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3)).astype(np.float32)
            y0 = int(gray.shape[0] * 0.45)
            row = edges[y0:, :].mean(axis=1)
            if row.size:
                sub_positions.append(int(np.argmax(row)) + y0)

            # 主色调采样
            if len(color_samples) < 60:
                px = small.reshape(-1, 3)
                color_samples.append(px[::max(1, len(px) // 500)])

            if i in sheet_at:
                sheet.append((round(i / fps, 2), frame.copy()))

        i += 1
        if total and i >= total:
            break

    cap.release()

    # 镜头表
    bounds = [0] + [c["frame"] for c in cuts] + [max(total - 1, 0)]
    shots = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b <= a:
            continue
        shots.append({"start": round(a / fps, 2), "end": round(b / fps, 2),
                      "dur": round((b - a) / fps, 2)})
    durs = [s["dur"] for s in shots if s["dur"] > 0.05]
    avg_shot = round(sum(durs) / len(durs), 2) if durs else round(duration, 2)
    first3 = [s for s in shots if s["start"] < 3.0]

    # 主色调
    dominant = []
    if color_samples:
        allpx = np.vstack(color_samples).astype(np.uint8)
        lab = cv2.cvtColor(allpx.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
        k = 5
        crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
        _, labels, centers = cv2.kmeans(lab, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
        cnt = np.bincount(labels.flatten(), minlength=k)
        for oi in np.argsort(-cnt):
            bgr = cv2.cvtColor(np.uint8([[centers[oi]]]), cv2.COLOR_LAB2BGR)[0][0]
            dominant.append({
                "hex": "#%02X%02X%02X" % (int(bgr[2]), int(bgr[1]), int(bgr[0])),
                "share": round(float(cnt[oi]) / float(cnt.sum()), 3)
            })

    subtitle = None
    if sub_positions:
        subtitle = {
            "medianRowPct": round(float(np.median(sub_positions)) / size[1] * 100, 1),
            "note": "行边缘最密处的相对高度（%），通常就是字幕所在带"
        }

    report = {
        "file": os.path.basename(path),
        "sizeMB": round(os.path.getsize(path) / 1048576, 2),
        "video": {
            "width": w, "height": h, "aspect": f"{w}:{h}",
            "orientation": "竖屏" if h > w else ("横屏" if w > h else "方形"),
            "fps": round(fps, 2), "codec": codec,
            "totalFrames": total, "durationSec": round(duration, 2),
            "sampledEveryFrames": step, "framesRead": frames_read
        },
        "editing": {
            "cutCount": len(cuts),
            "shotCount": len(shots),
            "avgShotSec": avg_shot,
            "cutsPerMinute": round(len(cuts) / (duration / 60), 1) if duration > 0 else 0,
            "shotsInFirst3Sec": len(first3),
            "hookNote": "前 3 秒镜头数越多，钩子切得越碎"
        },
        "motion": {
            "meanPixelDiff": round(float(np.mean(motion_series)), 2) if motion_series else 0,
            "maxPixelDiff": round(float(np.max(motion_series)), 2) if motion_series else 0,
            "note": "平均帧间像素差；越高说明画面运动或切换越剧烈"
        },
        "color": {"dominant": dominant},
        "subtitle": subtitle,
        "shots": shots[:150],
        "cutList": cuts[:150]
    }

    with open(os.path.join(outdir, "report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 缩略图拼版
    if sheet:
        tw = 240
        tiles = []
        for t, fr in sheet:
            sc = tw / fr.shape[1]
            tiles.append(cv2.resize(fr, (tw, max(1, int(fr.shape[0] * sc)))))
        th = max(t.shape[0] for t in tiles)
        cols = 5
        rows = (len(tiles) + cols - 1) // cols
        canvas = np.zeros((rows * th, cols * tw, 3), np.uint8)
        for n, t in enumerate(tiles):
            r, c = divmod(n, cols)
            canvas[r * th:r * th + t.shape[0], c * tw:c * tw + t.shape[1]] = t
            cv2.putText(canvas, f"{sheet[n][0]}s", (c * tw + 6, r * th + 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 180), 1, cv2.LINE_AA)
        cs = os.path.join(outdir, "contact-sheet.png")
        cv2.imwrite(cs, canvas)
        report["contactSheet"] = cs

    print(json.dumps({k: v for k, v in report.items() if k not in ("shots", "cutList")},
                     ensure_ascii=False, indent=2))
    print(f"\n镜头表与切点列表见: {os.path.join(outdir, 'report.json')}")
    if report.get("contactSheet"):
        print(f"缩略图拼版见: {report['contactSheet']}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--out", default=None)
    ap.add_argument("--frames", type=int, default=15)
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.path)), "ref-analysis")
    sys.exit(analyze(a.path, out, a.frames))
