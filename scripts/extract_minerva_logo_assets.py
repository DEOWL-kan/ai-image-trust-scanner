from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "frontend" / "dashboard" / "assets"
SOURCE = ASSET_DIR / "minerva-logo-source.png"
FALLBACK_SOURCE = ASSET_DIR / "minerva-logo.png"

# Crop boxes are tuned for the supplied 1448 x 1086 Minerva lockup image.
# Adjust these values if the source artwork is replaced with a differently
# framed export.
MARK_CROP = (135, 440, 435, 635)
WORDMARK_CROP = (480, 485, 1355, 590)
FULL_CROP = (135, 425, 1365, 650)


def source_path() -> Path:
    if SOURCE.exists():
        return SOURCE
    if FALLBACK_SOURCE.exists():
        SOURCE.write_bytes(FALLBACK_SOURCE.read_bytes())
        return SOURCE
    raise FileNotFoundError(
        "Missing Minerva logo source. Place the reference image at "
        f"{SOURCE.relative_to(ROOT)}"
    )


def transparent_crop(image: Image.Image, box: tuple[int, int, int, int], *, blur_radius: int = 22) -> Image.Image:
    crop = image.crop(box).convert("RGBA")
    rgb = crop.convert("RGB")
    background = rgb.filter(ImageFilter.GaussianBlur(blur_radius))
    diff = ImageChops.difference(rgb, background).convert("L")

    px = rgb.load()
    alpha = Image.new("L", rgb.size, 0)
    alpha_px = alpha.load()
    width, height = rgb.size
    for y in range(height):
        for x in range(width):
            r, g, b = px[x, y]
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            saturation = max(r, g, b) - min(r, g, b)
            gold = r > 160 and g > 105 and b < 130 and saturation > 28
            ink = b < 125 and luminance < 178
            contrast = diff.getpixel((x, y))
            raw = max(0, min(255, int((contrast - 18) * 6.2)))
            metal = luminance < 218 and (saturation > 9 or b < 178)
            if luminance > 224 and saturation < 18 and not gold:
                raw = min(raw, 16)
            if ink:
                raw = max(raw, int((178 - luminance) * 2.8))
            elif metal:
                raw = max(raw, int((218 - luminance) * 1.55))
            if gold:
                raw = max(raw, int(min(230, saturation * 3.1)))
            alpha_px[x, y] = max(0, min(255, raw))

    alpha = alpha.filter(ImageFilter.GaussianBlur(0.55))
    alpha = alpha.point(lambda value: max(0, min(255, int(value * 1.42))))
    crop.putalpha(alpha)
    return trim(crop)


def trim(image: Image.Image) -> Image.Image:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if not bbox:
        return image
    pad = 10
    left = max(0, bbox[0] - pad)
    top = max(0, bbox[1] - pad)
    right = min(image.width, bbox[2] + pad)
    bottom = min(image.height, bbox[3] + pad)
    return image.crop((left, top, right, bottom))


def save_png(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, "PNG", optimize=True)


def main() -> None:
    src = source_path()
    image = Image.open(src).convert("RGB")
    mark = transparent_crop(image, MARK_CROP, blur_radius=18)
    wordmark = transparent_crop(image, WORDMARK_CROP, blur_radius=26)
    full = transparent_crop(image, FULL_CROP, blur_radius=30)

    save_png(mark, ASSET_DIR / "minerva-mark.png")
    save_png(wordmark, ASSET_DIR / "minerva-wordmark.png")
    save_png(full, ASSET_DIR / "minerva-full-lockup.png")

    print("Minerva logo assets extracted:")
    for name in ("minerva-mark.png", "minerva-wordmark.png", "minerva-full-lockup.png"):
        output = ASSET_DIR / name
        with Image.open(output) as generated:
            print(f"- {output.relative_to(ROOT)} {generated.size[0]}x{generated.size[1]}")
    print("If the source artwork changes, adjust MARK_CROP, WORDMARK_CROP, and FULL_CROP in this script.")


if __name__ == "__main__":
    main()
