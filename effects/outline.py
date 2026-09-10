# -*- coding: utf-8 -*-
"""
Обводка: внешняя и внутренняя.

Плюс — старые функции apply_outer_outline / apply_inner_outline для
обратной совместимости.
"""

from PIL import Image, ImageFilter, ImageChops

from utils import get_color_rgb
from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT, CTRL_COLOR,
)


# ============================================================
#  Классы-эффекты
# ============================================================

class OutlineInner(EffectBase):
    """Внутренняя обводка."""

    id = "outline_inner"
    label_key = "outline_inner"
    stage = "inner"
    params = [
        ParamSpec("enabled", "outline_inner",       CTRL_CHECKBOX, False),
        ParamSpec("color",   "outline_color",       CTRL_COLOR,    "#000000"),
        ParamSpec("width",   "outline_width",       CTRL_INT,      1, 0, 20),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        width = int(self._get(ctx, "width", 1))
        if width <= 0:
            return ctx.image
        color = self._get(ctx, "color", "#000000")
        return apply_inner_outline(ctx.image, ctx.mask, color, width)


class OutlineOuter(EffectBase):
    """
    Внешняя обводка.

    FIX: помимо нового image возвращает расширенную outer_mask — она
    нужна GlowOuter'у, чтобы свечение исходило от РАСШИРЕННОГО силуэта,
    а не от исходного. Передаём результат как dict.
    """

    id = "outline_outer"
    label_key = "outline_outer"
    stage = "outer"
    params = [
        ParamSpec("enabled", "outline_outer",       CTRL_CHECKBOX, False),
        ParamSpec("color",   "outline_color",       CTRL_COLOR,    "#000000"),
        ParamSpec("width",   "outline_width",       CTRL_INT,      2, 0, 20),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        width = int(self._get(ctx, "width", 2))
        if width <= 0:
            return ctx.image
        color = self._get(ctx, "color", "#000000")
        new_img, expanded = apply_outer_outline(ctx.image, ctx.mask, color, width)
        return {"image": new_img, "outer_mask": expanded}


# ============================================================
#  Старые функции
# ============================================================

def apply_outer_outline(image, mask, color, width):
    if width <= 0:
        return image, mask
    outline_rgb = get_color_rgb(color)
    kernel_size = int(width * 2) + 1
    expanded = mask.filter(ImageFilter.MaxFilter(size=kernel_size))
    outline_mask = ImageChops.subtract(expanded, mask)
    outline_layer = Image.new("RGBA", image.size, outline_rgb + (255,))
    outline_layer.putalpha(outline_mask)
    return Image.alpha_composite(outline_layer, image), expanded


def apply_inner_outline(image, mask, color, width):
    if width <= 0:
        return image
    pad = int(width * 2)
    w, h = image.size
    padded_size = (w + 2 * pad, h + 2 * pad)

    padded_image = Image.new("RGBA", padded_size, (0, 0, 0, 0))
    padded_image.paste(image, (pad, pad))
    padded_mask = Image.new("L", padded_size, 0)
    padded_mask.paste(mask, (pad, pad))

    outline_rgb = get_color_rgb(color)
    kernel_size = int(width * 2) + 1
    shrunk_alpha = padded_mask.filter(ImageFilter.MinFilter(size=kernel_size))
    outline_mask = ImageChops.subtract(padded_mask, shrunk_alpha)

    outline_layer = Image.new("RGBA", padded_size, outline_rgb + (0,))
    outline_layer.putalpha(outline_mask)
    padded_image.paste(outline_layer, (0, 0), outline_mask)

    return padded_image.crop((pad, pad, w + pad, h + pad))