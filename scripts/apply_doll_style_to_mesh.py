from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from random import Random

from PIL import Image, ImageDraw, ImageFilter, ImageOps


CANVAS_SIZE = (1536, 3072)
SKIN = (243, 208, 194, 255)
SKIN_SHADE = (228, 186, 171, 255)
HAIR = (196, 91, 49, 255)
HAIR_DARK = (127, 53, 30, 255)
HAIR_LIGHT = (236, 147, 101, 255)
CLOTH = (26, 28, 32, 255)
CLOTH_LIGHT = (82, 86, 93, 255)
EYE_WHITE = (248, 247, 246, 255)
EYE_BLUE = (108, 136, 172, 255)
LIP = (209, 151, 146, 255)
FRECKLE = (155, 96, 70, 255)


@dataclass(frozen=True)
class ProjectionSet:
    color_front: Path
    color_back: Path
    color_left: Path
    color_right: Path
    id_front: Path
    id_back: Path
    id_left: Path
    id_right: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a stylized doll look for a Blender mesh and bake it into a new blend/glb.")
    parser.add_argument("--source-blend", required=True, help="Path to the source .blend file.")
    parser.add_argument("--source-obj", help="Optional fallback .obj source.")
    parser.add_argument("--final-dir", required=True, help="Directory for the final styled outputs.")
    parser.add_argument("--workdir", default="storage/doll_style_job", help="ASCII-safe working directory.")
    parser.add_argument("--outfit", choices=["casual", "bikini", "all"], default="all")
    parser.add_argument(
        "--blender-bin",
        default=r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
        help="Path to blender.exe.",
    )
    return parser.parse_args()


def _slug_name(source_blend: Path) -> str:
    return source_blend.stem.replace(" ", "_")


def _copy_source(path: Path | None, destination: Path) -> Path | None:
    if path is None or not path.exists():
        return None
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, destination)
    return destination


def _ellipse(draw: ImageDraw.ImageDraw, bounds, fill, outline=None, width=1) -> None:
    draw.ellipse(bounds, fill=fill, outline=outline, width=width)


def _rounded(draw: ImageDraw.ImageDraw, bounds, radius, fill, outline=None, width=1) -> None:
    draw.rounded_rectangle(bounds, radius=radius, fill=fill, outline=outline, width=width)


def _line(draw: ImageDraw.ImageDraw, points, fill, width=4) -> None:
    draw.line(points, fill=fill, width=width, joint="curve")


def _freckles(draw: ImageDraw.ImageDraw, *, center: tuple[int, int], radius_x: int, radius_y: int, count: int, seed: int, alpha: int = 145) -> None:
    rng = Random(seed)
    for _ in range(count):
        x = int(center[0] + rng.uniform(-1.0, 1.0) * radius_x)
        y = int(center[1] + rng.uniform(-1.0, 1.0) * radius_y)
        if ((x - center[0]) / max(radius_x, 1)) ** 2 + ((y - center[1]) / max(radius_y, 1)) ** 2 > 1.0:
            continue
        size = rng.randint(2, 5)
        color = (FRECKLE[0], FRECKLE[1], FRECKLE[2], alpha)
        draw.ellipse((x, y, x + size, y + size), fill=color)


def _base_canvases() -> tuple[Image.Image, Image.Image]:
    color = Image.new("RGBA", CANVAS_SIZE, SKIN)
    id_map = Image.new("RGBA", CANVAS_SIZE, (255, 0, 0, 255))
    return color, id_map


def _draw_face_front(draw: ImageDraw.ImageDraw, y_offset: int = 0) -> None:
    width, height = CANVAS_SIZE
    eye_y = int(height * 0.17) + y_offset
    eye_dx = int(width * 0.085)
    eye_w = int(width * 0.09)
    eye_h = int(height * 0.025)
    for sign in (-1, 1):
        cx = width // 2 + sign * eye_dx
        _ellipse(draw, (cx - eye_w // 2, eye_y - eye_h // 2, cx + eye_w // 2, eye_y + eye_h // 2), EYE_WHITE)
        iris_w = int(eye_w * 0.38)
        iris_h = int(eye_h * 0.85)
        _ellipse(draw, (cx - iris_w // 2, eye_y - iris_h // 2, cx + iris_w // 2, eye_y + iris_h // 2), EYE_BLUE)
        pupil = int(iris_w * 0.42)
        _ellipse(draw, (cx - pupil // 2, eye_y - pupil // 2, cx + pupil // 2, eye_y + pupil // 2), (48, 54, 63, 255))
        _line(draw, [(cx - eye_w // 2, eye_y - 4), (cx, eye_y - 16), (cx + eye_w // 2, eye_y - 2)], (100, 73, 61, 255), width=5)
        _line(draw, [(cx - eye_w // 3, eye_y - 22), (cx, eye_y - 28), (cx + eye_w // 3, eye_y - 24)], (126, 95, 82, 255), width=6)

    _line(
        draw,
        [(width // 2 - 10, eye_y + 22), (width // 2 - 2, eye_y + 54), (width // 2 + 8, eye_y + 78)],
        (212, 174, 162, 255),
        width=4,
    )
    lip_y = int(height * 0.23) + y_offset
    _line(draw, [(width // 2 - 32, lip_y), (width // 2, lip_y + 10), (width // 2 + 32, lip_y)], LIP, width=6)
    _line(draw, [(width // 2 - 26, lip_y + 8), (width // 2, lip_y + 18), (width // 2 + 26, lip_y + 8)], (223, 164, 157, 255), width=5)
    _freckles(draw, center=(width // 2, int(height * 0.19) + y_offset), radius_x=170, radius_y=95, count=220, seed=7)
    _freckles(draw, center=(width // 2 - 150, int(height * 0.17) + y_offset), radius_x=85, radius_y=60, count=65, seed=17)
    _freckles(draw, center=(width // 2 + 150, int(height * 0.17) + y_offset), radius_x=85, radius_y=60, count=65, seed=27)


def _draw_face_side(draw: ImageDraw.ImageDraw) -> None:
    width, height = CANVAS_SIZE
    eye_x = int(width * 0.57)
    eye_y = int(height * 0.175)
    _ellipse(draw, (eye_x - 46, eye_y - 16, eye_x + 28, eye_y + 16), EYE_WHITE)
    _ellipse(draw, (eye_x - 12, eye_y - 16, eye_x + 16, eye_y + 16), EYE_BLUE)
    _ellipse(draw, (eye_x - 4, eye_y - 12, eye_x + 10, eye_y + 12), (48, 54, 63, 255))
    _line(draw, [(eye_x - 40, eye_y - 6), (eye_x, eye_y - 16), (eye_x + 28, eye_y - 8)], (100, 73, 61, 255), width=5)
    _line(draw, [(eye_x - 20, eye_y - 28), (eye_x + 2, eye_y - 34), (eye_x + 28, eye_y - 28)], (126, 95, 82, 255), width=6)
    _line(draw, [(eye_x + 12, eye_y + 28), (eye_x + 36, eye_y + 42), (eye_x + 54, eye_y + 48)], (214, 176, 163, 255), width=4)
    _line(draw, [(eye_x + 18, eye_y + 72), (eye_x + 42, eye_y + 78), (eye_x + 60, eye_y + 72)], LIP, width=5)
    _freckles(draw, center=(eye_x + 18, int(height * 0.19)), radius_x=120, radius_y=70, count=160, seed=49)


def _hair_front(draw: ImageDraw.ImageDraw, id_draw: ImageDraw.ImageDraw) -> None:
    width, height = CANVAS_SIZE
    left = int(width * 0.24)
    right = int(width * 0.76)
    top = int(height * 0.03)
    lower = int(height * 0.58)

    hair_shape = [
        (left + 80, top + 180),
        (left + 10, top + 340),
        (left + 50, lower - 180),
        (left + 160, lower),
        (width // 2 - 30, lower - 120),
        (width // 2 - 34, top + 100),
        (right - 80, top + 180),
        (right - 10, top + 340),
        (right - 50, lower - 180),
        (right - 160, lower),
        (width // 2 + 30, lower - 120),
        (width // 2 + 34, top + 100),
    ]
    draw.polygon(hair_shape, fill=HAIR)
    id_draw.polygon(hair_shape, fill=(0, 255, 0, 255))
    _ellipse(draw, (left + 180, top, right - 180, top + 330), HAIR)
    _ellipse(id_draw, (left + 180, top, right - 180, top + 330), (0, 255, 0, 255))
    for index in range(18):
        x = left + 90 + int(index * (right - left - 180) / 17)
        alpha = 110 if index % 2 == 0 else 72
        _line(draw, [(x, top + 50), (x - 18, top + 360), (x + 12, lower - 10)], (HAIR_LIGHT[0], HAIR_LIGHT[1], HAIR_LIGHT[2], alpha), width=6)


def _hair_back(draw: ImageDraw.ImageDraw, id_draw: ImageDraw.ImageDraw) -> None:
    width, height = CANVAS_SIZE
    left = int(width * 0.2)
    right = int(width * 0.8)
    top = int(height * 0.03)
    bottom = int(height * 0.62)
    shape = [
        (left + 160, top),
        (right - 160, top),
        (right - 40, top + 340),
        (right - 80, bottom - 90),
        (width // 2 + 110, bottom),
        (width // 2, bottom - 40),
        (width // 2 - 110, bottom),
        (left + 80, bottom - 90),
        (left + 40, top + 340),
    ]
    draw.polygon(shape, fill=HAIR)
    id_draw.polygon(shape, fill=(0, 255, 0, 255))
    for index in range(21):
        x = left + 70 + int(index * (right - left - 140) / 20)
        _line(draw, [(x, top + 20), (x + 8, bottom - 15)], (HAIR_LIGHT[0], HAIR_LIGHT[1], HAIR_LIGHT[2], 95), width=5)


def _hair_side(draw: ImageDraw.ImageDraw, id_draw: ImageDraw.ImageDraw) -> None:
    width, height = CANVAS_SIZE
    shape = [
        (int(width * 0.38), int(height * 0.04)),
        (int(width * 0.64), int(height * 0.04)),
        (int(width * 0.8), int(height * 0.16)),
        (int(width * 0.84), int(height * 0.42)),
        (int(width * 0.78), int(height * 0.57)),
        (int(width * 0.68), int(height * 0.59)),
        (int(width * 0.56), int(height * 0.52)),
        (int(width * 0.46), int(height * 0.41)),
        (int(width * 0.36), int(height * 0.22)),
    ]
    draw.polygon(shape, fill=HAIR)
    id_draw.polygon(shape, fill=(0, 255, 0, 255))
    for index in range(14):
        x = int(width * 0.42) + index * 22
        _line(draw, [(x, int(height * 0.05)), (x + 18, int(height * 0.55))], (HAIR_LIGHT[0], HAIR_LIGHT[1], HAIR_LIGHT[2], 88), width=5)


def _casual_clothes(draw: ImageDraw.ImageDraw, id_draw: ImageDraw.ImageDraw, view: str) -> None:
    width, height = CANVAS_SIZE
    blue = (0, 0, 255, 255)
    if view == "front":
        top = [(width * 0.3, height * 0.29), (width * 0.7, height * 0.29), (width * 0.73, height * 0.49), (width * 0.27, height * 0.49)]
        sleeves_left = (width * 0.21, height * 0.30, width * 0.33, height * 0.39)
        sleeves_right = (width * 0.67, height * 0.30, width * 0.79, height * 0.39)
        shorts = [(width * 0.31, height * 0.50), (width * 0.69, height * 0.50), (width * 0.63, height * 0.64), (width * 0.37, height * 0.64)]
        draw.polygon(top, fill=CLOTH)
        id_draw.polygon(top, fill=blue)
        _rounded(draw, sleeves_left, 22, CLOTH)
        _rounded(draw, sleeves_right, 22, CLOTH)
        _rounded(id_draw, sleeves_left, 22, blue)
        _rounded(id_draw, sleeves_right, 22, blue)
        draw.polygon(shorts, fill=(46, 48, 55, 255))
        id_draw.polygon(shorts, fill=blue)
        _line(draw, [(width * 0.5, height * 0.50), (width * 0.5, height * 0.64)], CLOTH_LIGHT, width=5)
        _line(draw, [(width * 0.39, height * 0.52), (width * 0.35, height * 0.62)], CLOTH_LIGHT, width=4)
        _line(draw, [(width * 0.61, height * 0.52), (width * 0.65, height * 0.62)], CLOTH_LIGHT, width=4)
        _line(draw, [(width * 0.32, height * 0.52), (width * 0.68, height * 0.52)], (118, 120, 128, 255), width=4)
    elif view == "back":
        top = [(width * 0.34, height * 0.31), (width * 0.66, height * 0.31), (width * 0.68, height * 0.48), (width * 0.32, height * 0.48)]
        shorts = [(width * 0.32, height * 0.50), (width * 0.68, height * 0.50), (width * 0.64, height * 0.64), (width * 0.36, height * 0.64)]
        draw.polygon(top, fill=CLOTH)
        id_draw.polygon(top, fill=blue)
        draw.polygon(shorts, fill=(46, 48, 55, 255))
        id_draw.polygon(shorts, fill=blue)
        _rounded(draw, (width * 0.37, height * 0.54, width * 0.46, height * 0.61), 14, (62, 64, 71, 255), outline=CLOTH_LIGHT, width=3)
        _rounded(draw, (width * 0.54, height * 0.54, width * 0.63, height * 0.61), 14, (62, 64, 71, 255), outline=CLOTH_LIGHT, width=3)
    else:
        top = [(width * 0.42, height * 0.30), (width * 0.64, height * 0.30), (width * 0.69, height * 0.49), (width * 0.45, height * 0.49)]
        shorts = [(width * 0.43, height * 0.50), (width * 0.63, height * 0.50), (width * 0.67, height * 0.64), (width * 0.46, height * 0.64)]
        draw.polygon(top, fill=CLOTH)
        draw.polygon(shorts, fill=(46, 48, 55, 255))
        id_draw.polygon(top, fill=blue)
        id_draw.polygon(shorts, fill=blue)

    _rounded(draw, (width * 0.28, height * 0.92, width * 0.43, height * 0.97), 30, CLOTH)
    _rounded(draw, (width * 0.57, height * 0.92, width * 0.72, height * 0.97), 30, CLOTH)
    _rounded(id_draw, (width * 0.28, height * 0.92, width * 0.43, height * 0.97), 30, blue)
    _rounded(id_draw, (width * 0.57, height * 0.92, width * 0.72, height * 0.97), 30, blue)


def _bikini_clothes(draw: ImageDraw.ImageDraw, id_draw: ImageDraw.ImageDraw, view: str) -> None:
    width, height = CANVAS_SIZE
    blue = (0, 0, 255, 255)
    if view == "front":
        left_top = [(width * 0.40, height * 0.34), (width * 0.48, height * 0.43), (width * 0.34, height * 0.43)]
        right_top = [(width * 0.60, height * 0.34), (width * 0.66, height * 0.43), (width * 0.52, height * 0.43)]
        bottom = [(width * 0.40, height * 0.53), (width * 0.60, height * 0.53), (width * 0.55, height * 0.63), (width * 0.45, height * 0.63)]
        for shape in (left_top, right_top, bottom):
            draw.polygon(shape, fill=CLOTH)
            id_draw.polygon(shape, fill=blue)
        _line(draw, [(width * 0.34, height * 0.34), (width * 0.30, height * 0.40)], CLOTH, width=5)
        _line(draw, [(width * 0.66, height * 0.34), (width * 0.70, height * 0.40)], CLOTH, width=5)
    elif view == "back":
        band = [(width * 0.40, height * 0.40), (width * 0.60, height * 0.40), (width * 0.58, height * 0.43), (width * 0.42, height * 0.43)]
        bottom = [(width * 0.40, height * 0.54), (width * 0.60, height * 0.54), (width * 0.64, height * 0.65), (width * 0.36, height * 0.65)]
        draw.polygon(band, fill=CLOTH)
        draw.polygon(bottom, fill=CLOTH)
        id_draw.polygon(band, fill=blue)
        id_draw.polygon(bottom, fill=blue)
    else:
        top = [(width * 0.48, height * 0.34), (width * 0.64, height * 0.36), (width * 0.56, height * 0.45), (width * 0.46, height * 0.43)]
        bottom = [(width * 0.47, height * 0.54), (width * 0.58, height * 0.54), (width * 0.63, height * 0.62), (width * 0.51, height * 0.62)]
        draw.polygon(top, fill=CLOTH)
        draw.polygon(bottom, fill=CLOTH)
        id_draw.polygon(top, fill=blue)
        id_draw.polygon(bottom, fill=blue)

    _rounded(draw, (width * 0.28, height * 0.92, width * 0.43, height * 0.97), 30, CLOTH)
    _rounded(draw, (width * 0.57, height * 0.92, width * 0.72, height * 0.97), 30, CLOTH)
    _rounded(id_draw, (width * 0.28, height * 0.92, width * 0.43, height * 0.97), 30, blue)
    _rounded(id_draw, (width * 0.57, height * 0.92, width * 0.72, height * 0.97), 30, blue)


def _soft_shading(image: Image.Image) -> Image.Image:
    shadow = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow, "RGBA")
    width, height = CANVAS_SIZE
    _ellipse(draw, (width * 0.24, height * 0.08, width * 0.76, height * 0.62), (0, 0, 0, 18))
    _ellipse(draw, (width * 0.18, height * 0.56, width * 0.82, height * 1.02), (0, 0, 0, 14))
    shadow = shadow.filter(ImageFilter.GaussianBlur(38))
    return Image.alpha_composite(image, shadow)


def generate_projection_set(output_dir: Path, outfit: str) -> ProjectionSet:
    output_dir.mkdir(parents=True, exist_ok=True)

    def make_view(view: str) -> tuple[Image.Image, Image.Image]:
        color, id_map = _base_canvases()
        draw = ImageDraw.Draw(color, "RGBA")
        id_draw = ImageDraw.Draw(id_map, "RGBA")

        width, height = CANVAS_SIZE

        if view == "front":
            _hair_front(draw, id_draw)
            _draw_face_front(draw)
        elif view == "back":
            _hair_back(draw, id_draw)
        else:
            _hair_side(draw, id_draw)
            _draw_face_side(draw)

        if outfit == "casual":
            _casual_clothes(draw, id_draw, view)
        else:
            _bikini_clothes(draw, id_draw, view)
            _freckles(draw, center=(width // 2, int(height * 0.33)), radius_x=240, radius_y=190, count=110, seed=111, alpha=78)

        color = _soft_shading(color)
        return color, id_map

    front_color, front_id = make_view("front")
    back_color, back_id = make_view("back")
    left_color, left_id = make_view("left")
    right_color = ImageOps.mirror(left_color)
    right_id = ImageOps.mirror(left_id)

    color_front = output_dir / "front_color.png"
    color_back = output_dir / "back_color.png"
    color_left = output_dir / "left_color.png"
    color_right = output_dir / "right_color.png"
    id_front = output_dir / "front_id.png"
    id_back = output_dir / "back_id.png"
    id_left = output_dir / "left_id.png"
    id_right = output_dir / "right_id.png"

    front_color.save(color_front)
    back_color.save(color_back)
    left_color.save(color_left)
    right_color.save(color_right)
    front_id.save(id_front)
    back_id.save(id_back)
    left_id.save(id_left)
    right_id.save(id_right)

    return ProjectionSet(
        color_front=color_front,
        color_back=color_back,
        color_left=color_left,
        color_right=color_right,
        id_front=id_front,
        id_back=id_back,
        id_left=id_left,
        id_right=id_right,
    )


def run_blender(
    *,
    blender_bin: Path,
    work_blend: Path,
    work_obj: Path | None,
    projection_set: ProjectionSet,
    work_output_dir: Path,
    look_name: str,
) -> None:
    work_output_dir.mkdir(parents=True, exist_ok=True)
    output_blend = work_output_dir / "styled.blend"
    output_glb = work_output_dir / "styled.glb"
    render_dir = work_output_dir / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)

    command = [
        str(blender_bin),
        "--background",
        "--factory-startup",
        "--python",
        str(Path(__file__).resolve().with_name("blender_apply_projection_style.py")),
        "--",
        "--output-blend",
        str(output_blend),
        "--output-glb",
        str(output_glb),
        "--render-dir",
        str(render_dir),
        "--color-front",
        str(projection_set.color_front),
        "--color-back",
        str(projection_set.color_back),
        "--color-left",
        str(projection_set.color_left),
        "--color-right",
        str(projection_set.color_right),
        "--id-front",
        str(projection_set.id_front),
        "--id-back",
        str(projection_set.id_back),
        "--id-left",
        str(projection_set.id_left),
        "--id-right",
        str(projection_set.id_right),
        "--look-name",
        look_name,
    ]
    if work_blend.exists():
        command.extend(["--input-blend", str(work_blend)])
    if work_obj and work_obj.exists():
        command.extend(["--input-obj", str(work_obj)])

    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    output_blend = work_output_dir / "styled.blend"
    output_glb = work_output_dir / "styled.glb"
    combined = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    if completed.returncode != 0 or "Traceback" in combined or not output_blend.exists() or not output_glb.exists():
        raise RuntimeError(completed.stdout + "\n" + completed.stderr)


def copy_artifacts(work_output_dir: Path, final_dir: Path, source_stem: str, outfit: str) -> dict[str, str]:
    final_dir.mkdir(parents=True, exist_ok=True)
    target_blend = final_dir / f"{source_stem}_styled_{outfit}.blend"
    target_glb = final_dir / f"{source_stem}_styled_{outfit}.glb"
    target_render_dir = final_dir / f"{source_stem}_styled_{outfit}_renders"
    if target_render_dir.exists():
        shutil.rmtree(target_render_dir)
    shutil.copy2(work_output_dir / "styled.blend", target_blend)
    shutil.copy2(work_output_dir / "styled.glb", target_glb)
    shutil.copytree(work_output_dir / "renders", target_render_dir)
    return {
        "blend": str(target_blend),
        "glb": str(target_glb),
        "renders": str(target_render_dir),
    }


def main() -> None:
    args = parse_args()
    source_blend = Path(args.source_blend).resolve()
    source_obj = Path(args.source_obj).resolve() if args.source_obj else None
    final_dir = Path(args.final_dir).resolve()
    workdir = Path(args.workdir).resolve()
    blender_bin = Path(args.blender_bin).resolve()

    if not source_blend.exists():
        raise FileNotFoundError(f"Source blend was not found: {source_blend}")
    if not blender_bin.exists():
        raise FileNotFoundError(f"Blender binary was not found: {blender_bin}")

    source_slug = _slug_name(source_blend)
    source_dir = workdir / "source"
    work_blend = _copy_source(source_blend, source_dir / "source.blend")
    work_obj = _copy_source(source_obj, source_dir / "source.obj") if source_obj else None

    outfits = ["casual", "bikini"] if args.outfit == "all" else [args.outfit]
    summary: dict[str, dict[str, str]] = {}

    for outfit in outfits:
        projection_set = generate_projection_set(workdir / "projection_sets" / outfit, outfit)
        work_output_dir = workdir / "styled_outputs" / outfit
        look_name = f"Enya Doll {outfit.title()}"
        run_blender(
            blender_bin=blender_bin,
            work_blend=work_blend,
            work_obj=work_obj,
            projection_set=projection_set,
            work_output_dir=work_output_dir,
            look_name=look_name,
        )
        summary[outfit] = copy_artifacts(work_output_dir, final_dir, source_slug, outfit)

    manifest_path = final_dir / f"{source_slug}_styled_manifest.json"
    manifest_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "outputs": summary, "manifest": str(manifest_path)}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
