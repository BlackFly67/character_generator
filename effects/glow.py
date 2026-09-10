# -*- coding: utf-8 -*-
"""
Glow (outer / inner) — новая система эффектов.

Функционально совпадает с прежними apply_glow_outer / apply_glow_inner
из старых effects/glow.py, но оформлено как классы-эффекты с единым
интерфейсом. Старые функции оставлены ниже для обратной совместимости
(их вызывает только старый код, который мы не трогаем).
"""

from PIL import Image, ImageFilter, ImageChops

from utils import get_color_rgb, blend_layers

# ВАЖНО: типы для системы эффектов — в effects/core.py,
# а НЕ в effects/base.py (там хелперы: blend_layers, rotate_cleanly и т.п.)
from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT, CTRL_COLOR, CTRL_BLEND,
)


# ============================================================
#  Новые классы-эффекты
# ============================================================

class GlowOuter(EffectBase):
    """Внешнее свечение (outer glow)."""

    id = "glow_outer"
    label_key = "glow_outer"
    stage = "outer"
    params = [
        ParamSpec("enabled",   "glow_outer",     CTRL_CHECKBOX, False),
        ParamSpec("color",     "glow_color",     CTRL_COLOR,    "#ffffff"),
        ParamSpec("radius",    "glow_radius",    CTRL_INT,      5,  1, 30),
        ParamSpec("intensity", "glow_intensity", CTRL_INT,      10, 1, 20),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image

        # Свечению нужен видимый источник: либо заливка, либо реально
        # нарисованная внешняя обводка. Та же логика, что и в старом
        # apply_glow_outer (см. комментарии там).
        outline_drawn = (
            getattr(ctx.settings, "outline_outer_enabled", False)
            and getattr(ctx.settings, "outline_outer_width", 0) > 0
        )
        if ctx.settings.transparent_text and not outline_drawn:
            return ctx.image

        color = get_color_rgb(self._get(ctx, "color", "#ffffff"))
        radius = int(self._get(ctx, "radius", 5))
        intensity = int(self._get(ctx, "intensity", 10))

        # Источник свечения: outer_mask (расширенная внешней обводкой)
        # или исходная mask.
        source_mask = ctx.outer_mask if ctx.outer_mask is not None else ctx.mask

        glow_mask = source_mask.filter(ImageFilter.GaussianBlur(radius=radius))
        factor = intensity / 10.0
        if factor != 1.0:
            glow_mask = glow_mask.point(lambda p: min(255, int(p * factor)))

        # Ограничиваем область СНАРУЖИ исходной маски — та же поправка,
        # что и в старом apply_glow_outer.
        glow_mask = ImageChops.subtract(glow_mask, ctx.mask)

        layer = Image.new("RGBA", ctx.image.size, color + (255,))
        layer.putalpha(glow_mask)
        return Image.alpha_composite(layer, ctx.image)


class GlowInner(EffectBase):
    """Внутреннее свечение (inner glow)."""

    id = "glow_inner"
    label_key = "glow_inner"
    stage = "inner"
    params = [
        ParamSpec("enabled",    "glow_inner",     CTRL_CHECKBOX, False),
        ParamSpec("color",      "glow_color",     CTRL_COLOR,    "#ffffff"),
        ParamSpec("radius",     "glow_radius",    CTRL_INT,      3,  1, 30),
        ParamSpec("intensity",  "glow_intensity", CTRL_INT,      10, 1, 20),
        ParamSpec("blend_mode", "blend_mode",     CTRL_BLEND,    "normal"),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image

        color = get_color_rgb(self._get(ctx, "color", "#ffffff"))
        radius = int(self._get(ctx, "radius", 3))
        intensity = int(self._get(ctx, "intensity", 10))
        blend = self._get(ctx, "blend_mode", "normal")

        blurred = ctx.mask.filter(ImageFilter.GaussianBlur(radius=radius))
        glow_mask = ImageChops.invert(blurred)
        glow_mask = ImageChops.multiply(glow_mask, ctx.mask)

        if intensity != 10:
            factor = intensity / 10.0
            glow_mask = glow_mask.point(lambda p: min(255, int(p * factor)))

        layer = Image.new("RGBA", ctx.image.size, color + (255,))
        layer.putalpha(glow_mask)
        return blend_layers(ctx.image, layer, blend)


# ============================================================
#  Старые функции — оставлены для совместимости.
#  Их использует только старый код (в compose_full они больше не
#  вызываются, но функции могут быть нужны другим модулям — превью,
#  экспериментальным утилитам и т.д.).
# ============================================================

def apply_glow_outer(image, mask, color, radius, intensity):
    """Старая функция. См. GlowOuter для новой версии."""
    glow_rgb = get_color_rgb(color)
    glow_mask = mask.filter(ImageFilter.GaussianBlur(radius=radius))
    intensity_factor = intensity / 10.0
    if intensity_factor != 1.0:
        glow_mask = glow_mask.point(lambda p: min(255, int(p * intensity_factor)))
    glow_mask = ImageChops.subtract(glow_mask, mask)
    glow_layer = Image.new("RGBA", image.size, glow_rgb + (255,))
    glow_layer.putalpha(glow_mask)
    return Image.alpha_composite(glow_layer, image)


def apply_glow_inner(image, mask, color, radius, intensity, blend_mode="normal"):
    """Старая функция. См. GlowInner для новой версии."""
    blurred = mask.filter(ImageFilter.GaussianBlur(radius=radius))
    glow_mask = ImageChops.invert(blurred)
    glow_mask = ImageChops.multiply(glow_mask, mask)
    if intensity != 10:
        factor = intensity / 10.0
        glow_mask = glow_mask.point(lambda p: min(255, int(p * factor)))
    glow_rgb = get_color_rgb(color)
    glow_layer = Image.new("RGBA", image.size, glow_rgb + (255,))
    glow_layer.putalpha(glow_mask)
    return blend_layers(image, glow_layer, blend_mode)


# ============================================================
#  Алиасы для обратной совместимости.
#  Старый effects/__init__.py импортирует функции под старыми
#  именами (apply_outer_glow / apply_inner_glow) — оставляем
#  оба набора имён рабочими.
#  ВАЖНО: без отступа! Это атрибуты модуля, а не код внутри
#  функции apply_glow_inner.
# ============================================================

apply_outer_glow = apply_glow_outer
apply_inner_glow = apply_glow_inner