# -*- coding: utf-8 -*-
"""
Тиснение (Emboss).
"""

from PIL import Image, ImageFilter, ImageChops

from utils import get_color_rgb
from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT, CTRL_COLOR,
)


class Emboss(EffectBase):
    """Тиснение."""

    id = "emboss"
    label_key = "emboss"
    stage = "inner"
    params = [
        ParamSpec("enabled",    "emboss",              CTRL_CHECKBOX, False),
        ParamSpec("depth",      "emboss_depth",        CTRL_INT,      3, 1, 20),
        ParamSpec("blur",       "emboss_blur",         CTRL_INT,      1, 0, 10),
        ParamSpec("highlight",  "highlight_color",     CTRL_COLOR,    "#ffffff"),
        ParamSpec("shadow",     "shadow_color_emboss", CTRL_COLOR,    "#000000"),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        depth = int(self._get(ctx, "depth", 3))
        blur = int(self._get(ctx, "blur", 1))
        highlight = self._get(ctx, "highlight", "#ffffff")
        shadow = self._get(ctx, "shadow", "#000000")
        return apply_emboss(ctx.image, ctx.mask, depth, blur, highlight, shadow)


# ============================================================
#  Старая функция
# ============================================================

def apply_emboss(image, mask, depth, blur, highlight_color, shadow_color):
    hl_rgb = get_color_rgb(highlight_color)
    sh_rgb = get_color_rgb(shadow_color)

    shifted_down_right = Image.new("L", mask.size, 0)
    shifted_down_right.paste(mask, (depth, depth))
    hl_mask = ImageChops.subtract(mask, shifted_down_right)

    shifted_up_left = Image.new("L", mask.size, 0)
    shifted_up_left.paste(mask, (-depth, -depth))
    sh_mask = ImageChops.subtract(mask, shifted_up_left)

    if blur > 0:
        hl_mask = hl_mask.filter(ImageFilter.GaussianBlur(radius=blur))
        sh_mask = sh_mask.filter(ImageFilter.GaussianBlur(radius=blur))
        hl_mask = Image.composite(hl_mask, Image.new("L", mask.size, 0), mask)
        sh_mask = Image.composite(sh_mask, Image.new("L", mask.size, 0), mask)

    hl_layer = Image.new("RGBA", image.size, hl_rgb + (255,))
    sh_layer = Image.new("RGBA", image.size, sh_rgb + (255,))
    hl_layer.putalpha(hl_mask)
    sh_layer.putalpha(sh_mask)

    out = Image.alpha_composite(image, hl_layer)
    out = Image.alpha_composite(out, sh_layer)
    return out