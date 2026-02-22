import json
import random
from datetime import datetime, timezone, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import math

JST = timezone(timedelta(hours=9))

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "quotes" / "stock.json"
OUTDIR = ROOT / "output" / "images"
LOG = ROOT / "logs" / "posts.csv"

W, H = 1000, 1500


# ------------------------
# Gradient Background
# ------------------------
def random_color():
    return (
        random.randint(20, 200),
        random.randint(20, 200),
        random.randint(20, 200),
    )


def create_gradient():
    color1 = random_color()
    color2 = random_color()

    img = Image.new("RGB", (W, H), color1)
    draw = ImageDraw.Draw(img)

    for y in range(H):
        ratio = y / H
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    return img


# ------------------------
# Quote logic
# ------------------------
def load_stock():
    with open(STOCK, "r", encoding="utf-8") as f:
        return json.load(f)


def save_stock(data):
    with open(STOCK, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_unused(stock):
    for q in stock:
        if not q.get("used"):
            return q
    return None


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    line = ""

    for word in words:
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            lines.append(line)
            line = word

    if line:
        lines.append(line)

    return lines


# ------------------------
# Main
# ------------------------
def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    stock = load_stock()
    q = pick_unused(stock)

    if not q:
        print("No unused quotes left.")
        return

    bg = create_gradient()
    draw = ImageDraw.Draw(bg)

    # フォントサイズ自動調整
    font_size = 80
    font = ImageFont.load_default()

    max_width = int(W * 0.85)

    while font_size > 20:
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()

        lines = wrap_text(draw, q["quote"], font, max_width)

        total_height = sum(font.getbbox(line)[3] for line in lines) + (len(lines) - 1) * 20

        if total_height < H * 0.6:
            break

        font_size -= 4

    y = (H - total_height) // 2

    # 影付き文字
    for line in lines:
        bbox = font.getbbox(line)
        line_width = bbox[2]
        line_height = bbox[3]

        x = (W - line_width) // 2

        # shadow
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((x, y), line, font=font, fill=(255, 255, 255))

        y += line_height + 20

    ts = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    out_path = OUTDIR / f"{ts}_{q['id']}.png"
    bg.save(out_path)

    for item in stock:
        if item["id"] == q["id"]:
            item["used"] = True
            break

    save_stock(stock)

    with open(LOG, "a", encoding="utf-8") as f:
        f.write(
            f"{datetime.now(JST).isoformat()},{q['id']},{q['topic']},{out_path.as_posix()},ok,generated_gradient\n"
        )

    print(f"Generated: {out_path}")


if __name__ == "__main__":
    main()
