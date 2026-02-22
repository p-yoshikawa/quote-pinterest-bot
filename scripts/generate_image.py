import json
import os
import random
import textwrap
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# =====================
# CONFIG
# =====================
WIDTH = 1000
HEIGHT = 1500
MARGIN_X = 90
MARGIN_Y = 140
MAX_PER_RUN = 3

STOCK_PATH = "quotes/stock.json"
TEMPLATE_DIR = "templates"
OUTPUT_DIR = "output/images"

FONT_CANDIDATES = [
    "fonts/PlayfairDisplay-Bold.ttf",
    "fonts/Montserrat-Bold.ttf",
    "fonts/DejaVuSans-Bold.ttf",
]

BASE_FONT_SIZE = 64
MIN_FONT_SIZE = 42
LINE_SPACING = 10
TEXT_COLOR = (255, 255, 255)

SHADOW = True
SHADOW_OFFSET = (3, 4)
SHADOW_COLOR = (0, 0, 0)

DARKEN_BG = True
DARKEN_ALPHA = 80


def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_stock():
    with open(STOCK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_stock(data):
    with open(STOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_unused_with_index(data, n=MAX_PER_RUN):
    picked = []
    for idx, item in enumerate(data):
        if not item.get("used", False):
            picked.append((idx, item))
            if len(picked) >= n:
                break
    return picked


def mark_used_by_index(data, indices):
    for idx in indices:
        data[idx]["used"] = True


def choose_bg_path():
    files = [f for f in os.listdir(TEMPLATE_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    if not files:
        raise FileNotFoundError(f"No background images found in: {TEMPLATE_DIR}")
    return os.path.join(TEMPLATE_DIR, random.choice(files))


def load_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def apply_darken(image: Image.Image):
    if not DARKEN_BG:
        return image
    overlay = Image.new("RGBA", image.size, (0, 0, 0, DARKEN_ALPHA))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def measure_multiline(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont):
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=LINE_SPACING, align="center")
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])


def wrap_to_fit(draw: ImageDraw.ImageDraw, raw: str, font: ImageFont.ImageFont, max_width: int):
    raw = raw.strip()
    if not raw:
        return ""

    for wrap_width in range(28, 10, -1):
        wrapped = textwrap.fill(raw, width=wrap_width)
        w, _ = measure_multiline(draw, wrapped, font)
        if w <= max_width:
            return wrapped

    return textwrap.fill(raw, width=10)


def fit_text(draw: ImageDraw.ImageDraw, raw: str, box_w: int, box_h: int):
    for size in range(BASE_FONT_SIZE, MIN_FONT_SIZE - 1, -2):
        font = load_font(size)
        wrapped = wrap_to_fit(draw, raw, font, box_w)
        w, h = measure_multiline(draw, wrapped, font)
        if w <= box_w and h <= box_h:
            return wrapped, font

    font = load_font(MIN_FONT_SIZE)
    wrapped = wrap_to_fit(draw, raw, font, box_w)
    return wrapped, font


def draw_centered_text(image: Image.Image, text: str):
    draw = ImageDraw.Draw(image)
    box_w = WIDTH - (MARGIN_X * 2)
    box_h = HEIGHT - (MARGIN_Y * 2)

    wrapped, font = fit_text(draw, text, box_w, box_h)
    text_w, text_h = measure_multiline(draw, wrapped, font)

    x = (WIDTH - text_w) / 2
    y = (HEIGHT - text_h) / 2

    if SHADOW:
        draw.multiline_text(
            (x + SHADOW_OFFSET[0], y + SHADOW_OFFSET[1]),
            wrapped,
            font=font,
            fill=SHADOW_COLOR,
            spacing=LINE_SPACING,
            align="center",
        )

    draw.multiline_text(
        (x, y),
        wrapped,
        font=font,
        fill=TEXT_COLOR,
        spacing=LINE_SPACING,
        align="center",
    )


def generate_one(quote_text: str, idx: int, run_no: int):
    bg_path = choose_bg_path()
    base = Image.open(bg_path).convert("RGB").resize((WIDTH, HEIGHT))

    base = apply_darken(base)
    draw_centered_text(base, quote_text)

    # ★ 被り防止：マイクロ秒 + 連番
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")
    filename = f"quote_{idx+1}_{run_no}_{ts}.jpg"
    out_path = os.path.join(OUTPUT_DIR, filename)
    base.save(out_path, quality=95)
    return out_path


def main():
    ensure_dirs()

    data = load_stock()
    total = len(data)
    unused_count = sum(1 for x in data if not x.get("used", False))
    print(f"[DEBUG] stock total={total}, unused(used=false)={unused_count}")

    picked = pick_unused_with_index(data, n=MAX_PER_RUN)
    print(f"[DEBUG] picked count={len(picked)} (MAX_PER_RUN={MAX_PER_RUN})")
    print("[DEBUG] picked indices:", [idx for idx, _ in picked])

    if not picked:
        print("No unused quotes found. (used=false is empty)")
        return

    used_indices = []
    for run_no, (idx, item) in enumerate(picked, start=1):
        try:
            quote_text = (item.get("quote") or item.get("text") or "").strip()
            print(f"[DEBUG] run_no={run_no}, idx={idx}, quote_len={len(quote_text)}")

            if not quote_text:
                print(f"[WARN] Skip empty quote at idx={idx}. keys={list(item.keys())}")
                continue

            out_path = generate_one(quote_text, idx, run_no)
            print(f"Generated: {out_path}")
            used_indices.append(idx)

        except Exception as e:
            # ★ ここが超重要：2枚目で落ちて止まるのを見える化
            print(f"[ERROR] Failed at run_no={run_no}, idx={idx}: {type(e).__name__}: {e}")
            # 止めずに次へ（原因切り分け優先）
            continue

    print(f"[DEBUG] generated_count={len(used_indices)}")

    if used_indices:
        mark_used_by_index(data, used_indices)
        save_stock(data)
        print(f"Marked used=true for indices: {used_indices}")

    print("Done.")


if __name__ == "__main__":
    main()
