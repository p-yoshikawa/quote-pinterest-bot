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

# フォント（なければ自動フォールバック）
# ※ GitHub Actionsでも確実に動かすなら、fonts/ にttfを同梱推奨
FONT_CANDIDATES = [
    "fonts/PlayfairDisplay-Bold.ttf",
    "fonts/Montserrat-Bold.ttf",
    "fonts/DejaVuSans-Bold.ttf",
]

BASE_FONT_SIZE = 64
MIN_FONT_SIZE = 42
LINE_SPACING = 10  # 行間(px)
TEXT_COLOR = (255, 255, 255)

# 文字を読みやすくする薄い影（ONにしておく）
SHADOW = True
SHADOW_OFFSET = (3, 4)
SHADOW_COLOR = (0, 0, 0)

# 背景を少し暗くして文字を読みやすく（ONにしておく）
DARKEN_BG = True
DARKEN_ALPHA = 80  # 0-255（大きいほど暗い）


def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_stock():
    with open(STOCK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_stock(data):
    with open(STOCK_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_unused(data, n=MAX_PER_RUN):
    picked = []
    for item in data:
        if not item.get("used", False):
            picked.append(item)
            if len(picked) >= n:
                break
    return picked


def mark_used(data, ids):
    ids_set = set(ids)
    for item in data:
        if item.get("id") in ids_set:
            item["used"] = True


def choose_bg_path():
    files = [f for f in os.listdir(TEMPLATE_DIR) if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    if not files:
        raise FileNotFoundError(f"No background images found in: {TEMPLATE_DIR}")
    return os.path.join(TEMPLATE_DIR, random.choice(files))


def load_font(size: int):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    # 最後の手段（Pillowのデフォルト）
    return ImageFont.load_default()


def apply_darken(image: Image.Image):
    if not DARKEN_BG:
        return image
    overlay = Image.new("RGBA", image.size, (0, 0, 0, DARKEN_ALPHA))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def measure_multiline(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont):
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=LINE_SPACING, align="center")
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w, h


def wrap_to_fit(draw: ImageDraw.ImageDraw, raw: str, font: ImageFont.ImageFont, max_width: int):
    # ざっくり words wrap: 幅に収まるように wrap 幅を探す
    # まず長文で詰まりすぎを避けるために最大幅からスタート
    words = raw.strip()
    if not words:
        return ""

    # 探索範囲（英語想定）
    for wrap_width in range(28, 10, -1):
        wrapped = textwrap.fill(words, width=wrap_width)
        w, _ = measure_multiline(draw, wrapped, font)
        if w <= max_width:
            return wrapped

    # それでも無理なら強めに折り返し
    return textwrap.fill(words, width=10)


def fit_text(draw: ImageDraw.ImageDraw, raw: str, box_w: int, box_h: int):
    # フォントサイズを下げながら、幅＆高さに入る最適を探す
    for size in range(BASE_FONT_SIZE, MIN_FONT_SIZE - 1, -2):
        font = load_font(size)
        wrapped = wrap_to_fit(draw, raw, font, box_w)
        w, h = measure_multiline(draw, wrapped, font)

        if w <= box_w and h <= box_h:
            return wrapped, font

    # 最後まで入らなければ最小フォントで返す
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
        sx = x + SHADOW_OFFSET[0]
        sy = y + SHADOW_OFFSET[1]
        draw.multiline_text(
            (sx, sy),
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


def generate_one(quote_text: str, quote_id):
    bg_path = choose_bg_path()
    base = Image.open(bg_path).convert("RGB").resize((WIDTH, HEIGHT))

    base = apply_darken(base)
    draw_centered_text(base, quote_text)

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"quote_{quote_id}_{ts}.jpg"
    out_path = os.path.join(OUTPUT_DIR, filename)
    base.save(out_path, quality=95)
    return out_path


def main():
    ensure_dirs()

    data = load_stock()
    picked = pick_unused(data, n=MAX_PER_RUN)

    if not picked:
        print("No unused quotes found. (used=false is empty)")
        return

    generated_paths = []
    used_ids = []

    for item in picked:
        quote_id = item.get("id")
        quote_text = item.get("quote", "").strip()
        if not quote_text:
            continue

        out_path = generate_one(quote_text, quote_id)
        generated_paths.append(out_path)
        used_ids.append(quote_id)
        print(f"Generated: {out_path}")

    if used_ids:
        mark_used(data, used_ids)
        save_stock(data)
        print(f"Marked used=true for IDs: {used_ids}")

    print(f"Done. Generated {len(generated_paths)} image(s).")


if __name__ == "__main__":
    main()
