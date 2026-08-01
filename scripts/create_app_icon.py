from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

size = 256
image = Image.new("RGBA", (size, size), "#0f766e")
draw = ImageDraw.Draw(image)

draw.rounded_rectangle((18, 18, 238, 238), radius=44, fill="#ffffff")
draw.line((52, 176, 91, 131, 127, 151, 171, 84, 209, 106), fill="#0f766e", width=17, joint="curve")
draw.ellipse((78, 117, 103, 142), fill="#dc2626")
draw.ellipse((158, 71, 184, 97), fill="#dc2626")

try:
    font = ImageFont.truetype("arialbd.ttf", 42)
except OSError:
    font = ImageFont.load_default()
draw.text((61, 190), "LM", fill="#172033", font=font)

image.save(ASSETS / "laoma-stock.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
