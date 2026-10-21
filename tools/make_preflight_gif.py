#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 capture_preflight.py 采集的真实结果渲染成演示 GIF + 故事板。

左：终端（preflight 的真实输出）
右：那张表的"数字"—— 明细合计、整列求和、放大倍数（全部来自 audit_data 的真实计算）

清晰度策略与 devflow 演示一致：2 倍超采样 + LANCZOS、少而大、低抖动调色板。

用法：
    python3 tools/demo/capture_preflight.py --out docs/demo-preflight.json
    python3 tools/make_preflight_gif.py --data docs/demo-preflight.json --out docs/demo-preflight.gif
"""
from __future__ import annotations

import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

LW, LH = 1100, 640
SCALE = 1.2
SS = 2
K = SCALE * SS
FPS = 12
PAD = 32

BG = (246, 247, 249)
CARD = (255, 255, 255)
BORDER = (216, 221, 228)
INK = (26, 32, 40)
DIM = (108, 118, 130)
RED = (192, 57, 43)
GREEN = (22, 122, 66)
BLUE = (37, 99, 235)
CODE = (14, 20, 27)
CODE_INK = (210, 220, 230)
CODE_DIM = (130, 145, 160)

CJK_FONTS = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]
MONO_FONTS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "C:/Windows/Fonts/consola.ttf",
]


def load(fonts, size):
    for p in fonts:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, int(size * K))
            except OSError:
                continue
    return ImageFont.load_default()


def is_cjk(ch):
    return "\u2e80" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef" or "\u3000" <= ch <= "\u303f"


def text_w(text, mono, cjk):
    return sum(cjk.getlength(ch) if is_cjk(ch) else mono.getlength(ch) for ch in text) / K


def grid_text(d, text, x, y, mono, cjk, fill):
    cell = mono.getlength("M")
    col = 0.0
    for ch in text:
        if is_cjk(ch):
            w = cjk.getlength(ch)
            d.text(((x * K) + col * cell + (2 * cell - w) / 2, (y - 1) * K), ch, font=cjk, fill=fill)
            col += 2
        else:
            d.text(((x * K) + col * cell, y * K), ch, font=mono, fill=fill)
            col += 1


def truncate(text, max_cells):
    cells, out = 0, []
    for ch in text:
        w = 2 if is_cjk(ch) else 1
        if cells + w > max_cells - 1:
            return "".join(out) + "…"
        out.append(ch)
        cells += w
    return "".join(out)


def card(d, x, y, w, h, fill=CARD, outline=BORDER):
    d.rounded_rectangle([x * K, y * K, (x + w) * K, (y + h) * K], radius=12 * K,
                        fill=fill, outline=outline, width=max(1, int(K)))


FONTS = {}


def money(v):
    return f"{v:,.2f}"


def frame(step, idx, total, typed, shown, prev_numbers):
    img = Image.new("RGB", (int(LW * K), int(LH * K)), BG)
    d = ImageDraw.Draw(img)
    f = FONTS

    d.text((PAD * K, 22 * K), "deliverable-check · 交付前体检", font=f["h1"], fill=INK)
    d.text((PAD * K, 54 * K), "左：真实命令输出　右：那张表的数字", font=f["small"], fill=DIM)
    tag = f"{idx + 1} / {total}"
    d.text(((LW - PAD) * K - f["mono_mid"].getlength(tag), 26 * K), tag, font=f["mono_mid"], fill=DIM)

    # 终端
    left, top, w, h = PAD, 92, 620, 400
    d.rounded_rectangle([left * K, top * K, (left + w) * K, (top + h) * K], radius=12 * K, fill=CODE)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = (left + 16 + i * 14) * K
        d.ellipse([cx, (top + 12) * K, cx + 8 * K, (top + 20) * K], fill=c)

    x0, y = left + 18, top + 42
    grid_text(d, f"❯ {typed}", x0, y, f["mono"], f["cjk"], (140, 235, 150))
    if len(typed) < len(step["cmd"]):
        cells = sum(2 if is_cjk(c) else 1 for c in f"❯ {typed}")
        cx = x0 + cells * (f["mono"].getlength("M") / K)
        d.rectangle([cx * K, y * K, (cx + 6) * K, (y + 15) * K], fill=(120, 180, 255))
    y += 30

    for raw in shown:
        color = CODE_DIM
        dot = None
        if "⛔" in raw or "失败" in raw:
            color, dot = (255, 120, 110), (250, 90, 82)
        elif "✓" in raw or "可交付" in raw:
            color, dot = (120, 220, 140), (80, 200, 110)
        elif "⚠" in raw:
            color, dot = (235, 190, 90), (220, 165, 40)
        elif raw.strip().startswith(("交付前体检", "· 数据")):
            color = CODE_INK
        if y > top + h - 24:
            break
        text = raw.strip().replace("⛔", "").replace("✓", "").replace("⚠", "").strip()
        if dot:
            d.ellipse([(x0 + 1) * K, (y + 4) * K, (x0 + 8) * K, (y + 11) * K], fill=dot)
            grid_text(d, truncate(text, 72), x0 + 14, y, f["mono"], f["cjk"], color)
        else:
            grid_text(d, truncate(text, 74), x0, y, f["mono"], f["cjk"], color)
        y += 22

    # 右侧：数字卡
    rx, ry, rw = 680, 92, 388
    card(d, rx, ry, rw, 190)
    d.text(((rx + 20) * K, (ry + 16) * K), "金额（元）", font=f["label"], fill=DIM)
    nums = step.get("numbers") if step["verdict"] != "clean" else None
    if nums:
        rows = [
            ("明细合计", money(nums["detail"]), INK),
            ("整列求和", money(nums["naive"]), RED),
        ]
        yy = ry + 48
        for name, value, color in rows:
            d.text(((rx + 20) * K, yy * K), name, font=f["small"], fill=DIM)
            d.text(((rx + rw - 20) * K - f["mono"].getlength(value), yy * K), value, font=f["mono"], fill=color)
            yy += 34
        ratio = f"×{nums['ratio']:.2f}"
        d.text(((rx + 20) * K, (ry + 136) * K), "放大", font=f["small"], fill=DIM)
        d.text(((rx + rw - 20) * K - f["h2"].getlength(ratio), (ry + 122) * K), ratio, font=f["h2"], fill=RED)
    else:
        d.text(((rx + 20) * K, (ry + 80) * K), "0 阻断", font=f["h2"], fill=GREEN)
        d.text(((rx + 20) * K, (ry + 120) * K), "没有可检出的结构性错误", font=f["small"], fill=DIM)

    # 右侧：结论卡
    vy = 300
    card(d, rx, vy, rw, 192)
    verdict = step["verdict"]
    if verdict == "blocked":
        cx, cy, r = rx + 34, vy + 44, 14
        d.ellipse([(cx - r) * K, (cy - r) * K, (cx + r) * K, (cy + r) * K], outline=RED, width=int(3 * K))
        d.line([(cx - 6) * K, (cy - 6) * K, (cx + 6) * K, (cy + 6) * K], fill=RED, width=int(3 * K))
        d.line([(cx - 6) * K, (cy + 6) * K, (cx + 6) * K, (cy - 6) * K], fill=RED, width=int(3 * K))
        d.text(((rx + 60) * K, (vy + 24) * K), "不可交付", font=f["h2"], fill=RED)
        d.text(((rx + 20) * K, (vy + 84) * K), "先修阻断项，再谈发出去", font=f["small"], fill=DIM)
        d.text(((rx + 20) * K, (vy + 116) * K), "退出码 1 → 可直接接 CI / 门禁", font=f["small"], fill=DIM)
    elif verdict == "clean":
        cx, cy, r = rx + 34, vy + 44, 14
        d.ellipse([(cx - r) * K, (cy - r) * K, (cx + r) * K, (cy + r) * K], outline=GREEN, width=int(3 * K))
        d.line([(cx - 7) * K, (cy + 1) * K, (cx - 2) * K, (cy + 7) * K], fill=GREEN, width=int(3 * K))
        d.line([(cx - 2) * K, (cy + 7) * K, (cx + 8) * K, (cy - 6) * K], fill=GREEN, width=int(3 * K))
        d.text(((rx + 60) * K, (vy + 24) * K), "可交付", font=f["h2"], fill=GREEN)
        d.text(((rx + 20) * K, (vy + 84) * K), "退出码 0；阻断项归零", font=f["small"], fill=DIM)
    else:
        d.text(((rx + 20) * K, (vy + 22) * K), "修复中", font=f["h2"], fill=BLUE)
        d.text(((rx + 20) * K, (vy + 84) * K), "把结构问题修掉，而不是再算一遍", font=f["small"], fill=DIM)
        d.text(((rx + 20) * K, (vy + 116) * K), "（小计算两遍 = 放大倍数）", font=f["small"], fill=DIM)

    # 底部
    d.text((PAD * K, 522 * K), step["caption"], font=f["caption"], fill=INK)
    x = PAD
    for i in range(total):
        fill = GREEN if i < idx else (BLUE if i == idx else (208, 214, 222))
        d.ellipse([x * K, 566 * K, (x + 9) * K, (566 + 9) * K], fill=fill)
        x += 22
    grid_text(d, "真实输出可复跑：python3 tools/demo/capture_preflight.py && python3 tools/make_preflight_gif.py",
              PAD, 590, f["tiny_mono"], f["tiny"], (140, 150, 162))
    return img.resize((int(LW * SCALE), int(LH * SCALE)), Image.LANCZOS)


def storyboard(frames, ends, out_png):
    """两格：脏表被拦 / 修好后通过。比三格宽图更容易看清。"""
    picks = [frames[ends[0]], frames[ends[-1]]]
    w, h = picks[0].size
    gap = int(12 * SCALE)
    canvas = Image.new("RGB", (w * 2 + gap, h), (231, 235, 240))
    for i, im in enumerate(picks):
        canvas.paste(im, (i * (w + gap), 0))
    canvas.save(out_png, optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = json.load(open(args.data, encoding="utf-8"))
    steps = data["steps"]
    FONTS.update({
        "h1": load(CJK_FONTS, 22), "h2": load(CJK_FONTS, 34), "small": load(CJK_FONTS, 13),
        "label": load(CJK_FONTS, 12), "caption": load(CJK_FONTS, 17),
        "mono": load(MONO_FONTS, 12), "cjk": load(CJK_FONTS, 12),
        "mono_mid": load(MONO_FONTS, 13), "tiny": load(CJK_FONTS, 10), "tiny_mono": load(MONO_FONTS, 10),
    })

    frames, ends = [], []
    prev_numbers = None
    for idx, step in enumerate(steps):
        cmd = step["cmd"]
        for n in range(0, len(cmd) + 1, 12):
            frames.append(frame(step, idx, len(steps), cmd[:n], [], prev_numbers))
        shown = []
        for line in step["lines"]:
            shown = shown + [line]
            frames.append(frame(step, idx, len(steps), cmd, shown, prev_numbers))
        for _ in range(6):
            frames.append(frame(step, idx, len(steps), cmd, shown, prev_numbers))
        if step.get("numbers"):
            prev_numbers = step["numbers"]
        ends.append(len(frames) - 1)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    base = frames[-1].quantize(colors=96, method=Image.MEDIANCUT)
    q = [f.quantize(palette=base, dither=Image.NONE) for f in frames]
    q[0].save(args.out, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0,
              optimize=True, disposal=2)
    poster = os.path.splitext(args.out)[0] + ".png"
    frames[-1].save(poster, optimize=True)
    storyboard(frames, ends, os.path.splitext(args.out)[0] + "-story.png")
    print(f"{args.out}  {len(frames)} 帧  {os.path.getsize(args.out)/1048576:.2f}MB  {frames[0].size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
