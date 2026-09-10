# -*- coding: utf-8 -*-
"""
Эффекты заливки:
  - ColorFill     — плоская заливка текстурой цвета текста
  - GradientFill  — градиентная заливка поверх плоской
  - PatternFill   — заливка узором/текстурой
  - HalftoneMask  — растр из точек ПЕРЕД заливкой (меняет fill_mask)

Здесь же — старые функции заливки, оставленные для обратной
совместимости.
"""

from PIL import Image

from utils import get_color_rgb
from effects.gradient import apply_gradient_fill
from effects.pattern import apply_pattern_fill, load_pattern_image
from effects.halftone import apply_halftone
from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT, CTRL_COLOR, CTRL_FLOAT,
    CTRL_OPTION, CTRL_BLEND,
)


# ============================================================
#  ColorFill
# ============================================================

class ColorFill(EffectBase):
    """Плоская заливка цветом text_color. Применяется первой."""

    id = "color_fill"
    label_key = "text_color"
    stage = "fill"
    params = []   # читает только text_color + transparent_text

    def apply(self, ctx: EffectContext):
        s = ctx.settings
        if s.transparent_text:
            return ctx.image

        rgb = get_color_rgb(s.text_color)
        mask = ctx.fill_mask if ctx.fill_mask is not None else ctx.mask
        fill = Image.new("RGBA", ctx.image.size, rgb + (255,))
        fill.putalpha(mask)
        return Image.alpha_composite(ctx.image, fill)


# ============================================================
#  GradientFill
# ============================================================

class GradientFill(EffectBase):
    """Градиентная заливка поверх уже нанесённого цвета."""

    id = "gradient"
    label_key = "gradient_fill"
    stage = "fill"
    params = [
        ParamSpec("enabled",  "gradient_fill",  CTRL_CHECKBOX, False),
        ParamSpec("type",     "gradient_type",  CTRL_OPTION,   "linear",
                  values=["linear", "radial", "angle", "reflected", "diamond"]),
        ParamSpec("angle",    "gradient_angle", CTRL_INT,      0, 0, 360),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        stops = ctx.settings.gradient_stops or [
            {"pos": 0.0, "color": "#ff0000"},
            {"pos": 1.0, "color": "#0000ff"},
        ]
        mask = ctx.fill_mask if ctx.fill_mask is not None else ctx.mask
        return apply_gradient_fill(
            ctx.image, mask, stops,
            ctx.settings.gradient_type,
            ctx.settings.gradient_angle,
        )


# ============================================================
#  PatternFill
# ============================================================

class PatternFill(EffectBase):
    """Заливка узором/текстурой поверх градиента/цвета."""

    id = "pattern"
    label_key = "pattern_fill"
    stage = "fill"
    params = [
        ParamSpec("enabled",     "pattern_fill",   CTRL_CHECKBOX, False),
        ParamSpec("scale",       "pattern_scale",  CTRL_INT,      100, 5, 500),
        ParamSpec("offset_x",    "pattern_offset_x", CTRL_INT,    0, -9999, 9999),
        ParamSpec("offset_y",    "pattern_offset_y", CTRL_INT,    0, -9999, 9999),
        ParamSpec("angle",       "pattern_angle",  CTRL_INT,      0, 0, 360),
        ParamSpec("blend_mode",  "blend_mode",     CTRL_BLEND,    "normal"),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        s = ctx.settings
        if not s.pattern_image_path:
            return ctx.image
        pat = load_pattern_image(s.pattern_image_path)
        if pat is None:
            return ctx.image
        mask = ctx.fill_mask if ctx.fill_mask is not None else ctx.mask
        return apply_pattern_fill(
            ctx.image, mask, pat,
            s.pattern_scale,
            s.pattern_offset_x, s.pattern_offset_y,
            s.pattern_angle, s.pattern_blend_mode,
        )


# ============================================================
#  HalftoneMask
# ============================================================

class HalftoneMask(EffectBase):
    """
    Halftone как МАСКА: превращает fill_mask в растр из точек.
    Применяется ДО заливки (ColorFill/GradientFill/PatternFill
    увидят уже растровую маску).
    """

    id = "halftone"
    label_key = "halftone"
    stage = "fill"       # до ColorFill по порядку PIPELINE
    params = [
        ParamSpec("enabled",    "halftone",       CTRL_CHECKBOX, False),
        ParamSpec("cell_size",  "halftone_cell_size",   CTRL_INT, 10, 2, 100),
        ParamSpec("dot_scale",  "halftone_dot_scale",   CTRL_INT, 100, 10, 300),
        ParamSpec("angle",      "halftone_angle",       CTRL_INT, 0, 0, 360),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        s = ctx.settings
        if s.transparent_text:
            return ctx.image
        if ctx.will_warp:
            # при искажениях halftone применяется ПОСЛЕ трансформаций —
            # эта ветка в compose_full реализована отдельно.
            return ctx.image
        base = ctx.fill_mask if ctx.fill_mask is not None else ctx.mask
        new_fill_mask = apply_halftone(
            base,
            s.halftone_cell_size,
            s.halftone_dot_scale,
            s.halftone_angle,
        )
        return {"image": ctx.image, "fill_mask": new_fill_mask}