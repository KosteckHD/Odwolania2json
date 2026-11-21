"""Generator brudnych skanów do testów OCR.

Renderuje każdy PDF z katalogu wejściowego do obrazu i psuje go jak skaner
albo zdjęcie telefonem: tło papieru, nierówne światło, pieczątka, podpis,
zagięcie, obrót, rozmycie, szum, kompresja JPEG, niska rozdzielczość, tryb
faksu. Wynik to PDF bez warstwy tekstu, więc backend musi użyć OCR.

Układ wyjścia odpowiada wejściu, z poziomem na górze:
    <output>/<poziom>/<sprawa>/<plik>.pdf
Każdy poziom można więc podać jako --input dla main.py.

Wynik jest powtarzalny: losowość zależy od poziomu i ścieżki pliku.
Sztuczne brudzenie nie zastępuje prawdziwego skanu wydrukowanej kartki; służy
do sprawdzenia, przy jakim poziomie zniekształceń odczyt zaczyna się psuć.

Przykład:
    python evaluation/dirty_scans.py --input .local/uzp-dane --output .local/brudne-skany
"""

import argparse
import io
import math
import random
from pathlib import Path

import pypdfium2
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

LEVELS = {
    # dpi: rozdzielczość skanu; angle: maks. obrót w stopniach; blur: promień
    # rozmycia; noise: sigma szumu; jpeg: jakość kompresji (None = bez JPEG);
    # paper: kolor papieru; shade: siła nierównego oświetlenia (0–1).
    "lekki": dict(dpi=200, angle=0.5, blur=0.3, noise=5, jpeg=80, paper=(247, 245, 240), shade=0.0,
                  stamp=False, signature=True, fold=False, bw=False),
    "sredni": dict(dpi=150, angle=1.5, blur=0.7, noise=12, jpeg=45, paper=(241, 235, 220), shade=0.18,
                   stamp=True, signature=True, fold=True, bw=False),
    "mocny": dict(dpi=120, angle=3.0, blur=1.1, noise=20, jpeg=25, paper=(232, 223, 200), shade=0.38,
                  stamp=True, signature=True, fold=True, bw=False),
    "faks": dict(dpi=100, angle=0.8, blur=0.4, noise=8, jpeg=None, paper=(255, 255, 255), shade=0.0,
                 stamp=False, signature=True, fold=False, bw=True),
}

FONT_CANDIDATES = ["C:/Windows/Fonts/arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(size):
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default(size=size)


def render_pages(path, dpi):
    with pypdfium2.PdfDocument(path) as document:
        for page in document:
            bitmap = page.render(scale=dpi / 72)
            yield bitmap.to_pil().convert("RGB")
            bitmap.close()
            page.close()


def multiply(image, overlay):
    return ImageChops.multiply(image, overlay)


def add_stamp(image, rng, dpi):
    """Okrągła pieczątka „ZA ZGODNOŚĆ Z ORYGINAŁEM” nachodząca na tekst w dolnej części strony."""
    w, h = image.size
    r = int(dpi * 0.75)
    layer = Image.new("RGB", (2 * r + 8, 2 * r + 8), (255, 255, 255))
    draw = ImageDraw.Draw(layer)
    ink = (60, 80, 175)
    width = max(2, dpi // 50)
    draw.ellipse((4, 4, 2 * r + 4, 2 * r + 4), outline=ink, width=width)
    draw.ellipse((4 + r // 6, 4 + r // 6, 2 * r + 4 - r // 6, 2 * r + 4 - r // 6), outline=ink, width=max(1, width // 2))
    f = font(int(r * 0.22))
    for i, line in enumerate(["ZA ZGODNOŚĆ", "Z ORYGINAŁEM"]):
        box = draw.textbbox((0, 0), line, font=f)
        draw.text((r + 4 - (box[2] - box[0]) / 2, r + 4 - (box[3] - box[1]) * (1.3 - 1.5 * i)), line, fill=ink, font=f)
    layer = layer.rotate(rng.uniform(-25, 25), fillcolor=(255, 255, 255), resample=Image.BICUBIC)
    x = int(w * rng.uniform(0.45, 0.70))
    y = int(h * rng.uniform(0.55, 0.80))
    region = image.crop((x, y, x + layer.width, y + layer.height))
    image.paste(multiply(region, layer), (x, y))


def add_signature(image, rng, dpi):
    """Odręczny podpis długopisem: kilka nachodzących na siebie łuków."""
    w, h = image.size
    draw = ImageDraw.Draw(image)
    ink = (25, 35, 110)
    x0, y0 = w * rng.uniform(0.15, 0.55), h * rng.uniform(0.70, 0.88)
    length = dpi * rng.uniform(1.2, 1.8)
    points = []
    for i in range(80):
        t = i / 79
        points.append((x0 + t * length + math.sin(t * 19 + rng.random()) * dpi * 0.05,
                       y0 + math.sin(t * 11) * dpi * 0.12 * (1 - t) + math.cos(t * 23) * dpi * 0.04))
    draw.line(points, fill=ink, width=max(2, dpi // 60), joint="curve")


def add_fold(image, rng):
    """Zagięcie kartki: ciemniejsza linia z jaśniejszym pasem obok."""
    w, h = image.size
    y = int(h * rng.uniform(0.30, 0.40))
    band = Image.new("RGB", (w, 14), (255, 255, 255))
    draw = ImageDraw.Draw(band)
    for i, value in enumerate([235, 215, 190, 205, 230, 248, 255]):
        draw.line((0, i * 2, w, i * 2), fill=(value,) * 3, width=2)
    region = image.crop((0, y, w, y + 14))
    image.paste(multiply(region, band), (0, y))


def shade(image, rng, strength):
    """Nierówne światło: rozjaśnienie z jednego rogu, cień w przeciwnym."""
    w, h = image.size
    d = int(math.hypot(w, h)) + 2                        # kwadrat, którego koło wpisane mieści stronę
    gradient = Image.linear_gradient("L").resize((d, d)).rotate(rng.choice([30, 120, 210, 300]), resample=Image.BILINEAR)
    left, top = (d - w) // 2, (d - h) // 2
    gradient = gradient.crop((left, top, left + w, top + h))
    low = int(255 * (1 - strength))
    mask = gradient.point(lambda v: low + (255 - low) * v // 255)
    return multiply(image, Image.merge("RGB", (mask, mask, mask)))


def add_noise(image, sigma):
    noise = Image.effect_noise(image.size, sigma).convert("RGB")
    return ImageChops.add(image, noise, scale=1.0, offset=-128)


def to_fax(image, rng):
    gray = image.convert("L").point(lambda v: 255 if v > 150 else 0)
    draw = ImageDraw.Draw(gray)
    w, h = gray.size
    for _ in range(int(w * h * 0.002)):
        draw.point((rng.randrange(w), rng.randrange(h)), fill=0)
    for _ in range(3):                                   # poziome smugi z podajnika
        y = rng.randrange(h)
        draw.line((0, y, w, y), fill=rng.choice([0, 255]), width=1)
    return gray.convert("1")


def degrade_page(image, cfg, rng, first_page):
    dpi = cfg["dpi"]
    image = multiply(image, Image.new("RGB", image.size, cfg["paper"]))
    if cfg["stamp"] and first_page:
        add_stamp(image, rng, dpi)
    if cfg["signature"] and first_page:
        add_signature(image, rng, dpi)
    if cfg["fold"]:
        add_fold(image, rng)
    if cfg["shade"]:
        image = shade(image, rng, cfg["shade"])
    angle = rng.uniform(-cfg["angle"], cfg["angle"])
    image = image.rotate(angle, resample=Image.BICUBIC, fillcolor=cfg["paper"])
    if cfg["blur"]:
        image = image.filter(ImageFilter.GaussianBlur(cfg["blur"]))
    if cfg["noise"]:
        image = add_noise(image, cfg["noise"])
    if cfg["bw"]:
        return to_fax(image, rng)
    if cfg["jpeg"]:
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", quality=cfg["jpeg"])
        buffer.seek(0)
        image = Image.open(buffer).convert("RGB")
    return image


def degrade_pdf(source, target, level, relative):
    cfg = LEVELS[level]
    rng = random.Random(f"{level}/{relative}")
    pages = [degrade_page(page, cfg, rng, index == 0) for index, page in enumerate(render_pages(source, cfg["dpi"]))]
    target.parent.mkdir(parents=True, exist_ok=True)
    options = {"resolution": cfg["dpi"], "save_all": True, "append_images": pages[1:]}
    if cfg["jpeg"]:
        options["quality"] = cfg["jpeg"]
    pages[0].save(target, "PDF", **options)
    return pages[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True, help="katalog z PDF-ami (np. sprawy UZP)")
    parser.add_argument("--output", type=Path, required=True, help="katalog wynikowy")
    parser.add_argument("--levels", nargs="+", choices=list(LEVELS), default=list(LEVELS))
    parser.add_argument("--preview", type=Path, help="zapisz tu podgląd pierwszej strony każdego poziomu (PNG)")
    parser.add_argument("--preview-file", default=None, help="ścieżka względna PDF-u do podglądu (domyślnie pierwszy)")
    args = parser.parse_args()

    sources = sorted(args.input.rglob("*.pdf"))
    if not sources:
        parser.error(f"brak plików PDF w {args.input}")
    preview_rel = Path(args.preview_file) if args.preview_file else sources[0].relative_to(args.input)
    for level in args.levels:
        for source in sources:
            relative = source.relative_to(args.input)
            first = degrade_pdf(source, args.output / level / relative, level, relative.as_posix())
            if args.preview and relative == preview_rel:
                args.preview.mkdir(parents=True, exist_ok=True)
                first.convert("RGB").save(args.preview / f"skan-{level}.png", optimize=True)
        print(f"{level}: {len(sources)} PDF -> {args.output / level}")


if __name__ == "__main__":
    main()
