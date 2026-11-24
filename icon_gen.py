import os
from PIL import Image, ImageDraw


def build_icon(out_path: str = "assets/app.ico") -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    sizes = [256, 128, 64, 48, 32, 16]
    frames: list[Image.Image] = []

    for s in sizes:
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        stroke = max(2, round(s * 0.05))
        wave = max(2, round(s * 0.038))

        d.rounded_rectangle(
            [s * 0.05, s * 0.05, s * 0.95, s * 0.95],
            radius=s * 0.22,
            fill=(15, 23, 42, 255),
        )
        d.rounded_rectangle(
            [s * 0.16, s * 0.22, s * 0.42, s * 0.78],
            radius=s * 0.06,
            outline=(56, 189, 248, 255),
            width=stroke,
        )
        d.rounded_rectangle(
            [s * 0.50, s * 0.28, s * 0.84, s * 0.64],
            radius=s * 0.05,
            outline=(250, 204, 21, 255),
            width=stroke,
        )
        d.line(
            [s * 0.58, s * 0.72, s * 0.76, s * 0.72],
            fill=(250, 204, 21, 255),
            width=stroke,
        )
        d.arc(
            [s * 0.36, s * 0.32, s * 0.56, s * 0.52],
            start=-65,
            end=25,
            fill=(248, 250, 252, 255),
            width=wave,
        )
        d.arc(
            [s * 0.32, s * 0.26, s * 0.62, s * 0.56],
            start=-65,
            end=25,
            fill=(248, 250, 252, 255),
            width=wave,
        )
        frames.append(img)

    frames[0].save(out_path, format="ICO", sizes=[(sz, sz) for sz in sizes])


if __name__ == "__main__":
    build_icon()
