import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

JST = timezone(timedelta(hours=9))

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "quotes" / "stock.json"
OUTDIR = ROOT / "output" / "images"
LOG = ROOT / "logs" / "posts.csv"
BGDIR = ROOT / "assets" / "backgrounds"

W, H = 1000, 1500

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
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines

def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)

    stock = load_stock()
    q = pick_unused(stock)
    if not q:
        print("No unused quotes left.")
        return

    # 背景なしの場合は単色
    bg = Image.new("RGB", (W, H), (20, 20, 20))
    draw = ImageDraw.Draw(bg)

    font = ImageFont.load_default()

    quote = q["quote"]
    max_w = int(W * 0.82)
    lines = wrap_text(draw, quote, font, max_w)

    y = int(H * 0.35)
    for line in lines:
        line_w = draw.textlength(line, font=font)
        x = (W - line_w) // 2
        draw.text((x, y), line, font=font)
        y += 28

    ts = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
    out_path = OUTDIR / f"{ts}_{q['id']}.png"
    bg.save(out_path)

    for item in stock:
        if item["id"] == q["id"]:
            item["used"] = True
            break
    save_stock(stock)

    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now(JST).isoformat()},{q['id']},{q['topic']},{out_path.as_posix()},ok,generated_image_only\n")

    print(f"Generated: {out_path}")

if __name__ == "__main__":
    main()
