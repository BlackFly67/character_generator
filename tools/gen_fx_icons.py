"""Генератор FX-иконок через собственный рендер."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image
from config import Settings
from render.composer import CharSpec, compose_full


# Пресеты: panel_id -> функция, настраивающая settings.
# Каждый пресет включает ровно один эффект, остальное — дефолт.
PRESETS = {
    "gradient": lambda s: (
        setattr(s, "gradient_enabled", True),
        setattr(s, "gradient_type", "linear"),
        setattr(s, "gradient_angle", 45),
    ),
    "outline_outer": lambda s: (
        setattr(s, "outline_outer_enabled", True),
        setattr(s, "outline_outer_width", 3),
        setattr(s, "outline_outer_color", "#1f538d"),
    ),
    "outline_inner": lambda s: (
        setattr(s, "outline_inner_enabled", True),
        setattr(s, "outline_inner_width", 3),
        setattr(s, "outline_inner_color", "#1f538d"),
    ),
    "glow_outer": lambda s: (
        setattr(s, "glow_outer_enabled", True),
        setattr(s, "glow_outer_radius", 8),
        setattr(s, "glow_outer_color", "#1f538d"),
    ),
    "glow_inner": lambda s: (
        setattr(s, "glow_inner_enabled", True),
        setattr(s, "glow_inner_radius", 5),
        setattr(s, "glow_inner_color", "#1f538d"),
    ),
    "extrude": lambda s: (
        setattr(s, "extrude_enabled", True),
        setattr(s, "extrude_depth", 6),
        setattr(s, "extrude_angle", 315),
    ),
    "emboss": lambda s: (
        setattr(s, "emboss_enabled", True),
        setattr(s, "emboss_depth", 3),
    ),
    "inner_shadow": lambda s: (
        setattr(s, "inner_shadow_enabled", True),
        setattr(s, "inner_shadow_distance", 3),
    ),
    "shadow": lambda s: (
        setattr(s, "shadow_enabled", True),
        setattr(s, "shadow_distance", 3),
        setattr(s, "shadow_direction", 8),
    ),
    "skew": lambda s: (
        setattr(s, "skew_enabled", True),
        setattr(s, "skew_x", 20),
    ),
    "perspective": lambda s: (
        setattr(s, "perspective_enabled", True),
        setattr(s, "perspective_x", 30),
    ),
    "reflection": lambda s: (
        setattr(s, "reflection_enabled", True),
        setattr(s, "reflection_gap", 2),
        setattr(s, "reflection_opacity", 60),
    ),
    "halftone": lambda s: (
        setattr(s, "halftone_enabled", True),
        setattr(s, "halftone_cell_size", 4),
        setattr(s, "halftone_dot_scale", 80),
    ),
    "glitch": lambda s: (
        setattr(s, "glitch_enabled", True),
        setattr(s, "glitch_rgb_shift", 3),
        setattr(s, "glitch_slice_intensity", 40),
        setattr(s, "glitch_seed", 42),
    ),
    "pattern": lambda s: (
        setattr(s, "pattern_enabled", True),
        setattr(s, "pattern_image_path", "assets/pattern_default.png"),
        setattr(s, "pattern_scale", 80),
    ),
}


def main():
    out_dir = "ui/assets/fx_icons"
    os.makedirs(out_dir, exist_ok=True)

    for panel_id, setup in PRESETS.items():
        s = Settings()
        s.reset()
        # Чёрный цвет текста, белый фон — универсальная иконка.
        s.text_color = "#1a1a1a"
        s.background_color = None
        s.transparent_background = True
        s.font_size = 42
        s.font_path = s.font_path or ""  # оставьте дефолт
        s.text_alignment = "center"
        setup(s)

        spec = CharSpec(text="A", index=1)
        img = compose_full(spec, s)

        # Обрезать по bbox и вписать в 64×64.
        bbox = img.split()[3].getbbox()
        if bbox:
            img = img.crop(bbox)
        img.thumbnail((48, 48), Image.LANCZOS)

        canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        canvas.alpha_composite(img, (
            (64 - img.width) // 2,
            (64 - img.height) // 2,
        ))
        canvas.save(os.path.join(out_dir, f"{panel_id}.png"), "PNG")
        print(f"saved: {panel_id}.png")


if __name__ == "__main__":
    main()