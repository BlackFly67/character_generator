# -*- coding: utf-8 -*-
"""
Внутренняя тень (Inner Shadow).
"""

from PIL import Image, ImageFilter, ImageChops

from utils import get_color_rgb, get_shadow_offset, blend_layers
from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT, CTRL_COLOR, CTRL_BLEND, CTRL_DIR,
)


class ShadowInner(EffectBase):
    """Внутренняя тень — эффект вдавленности."""

    id = "inner_shadow"
    label_key = "inner_shadow"
    stage = "inner"
    params = [
        ParamSpec("enabled",    "inner_shadow",           CTRL_CHECKBOX, False),
        ParamSpec("color",      "inner_shadow_color",     CTRL_COLOR,    "#000000"),
        ParamSpec("distance",   "inner_shadow_distance",  CTRL_INT,      4, 0, 20),
        ParamSpec("direction",  "shadow_direction",       CTRL_DIR,      8),
        ParamSpec("blur",       "inner_shadow_blur",      CTRL_INT,      3, 0, 30),
        ParamSpec("blend_mode", "blend_mode",             CTRL_BLEND,    "normal"),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        distance = int(self._get(ctx, "distance", 4))
        if distance == 0:
            return ctx.image
        color = self._get(ctx, "color", "#000000")
        direction = int(self._get(ctx, "direction", 8))
        blur = int(self._get(ctx, "blur", 3))
        blend = self._get(ctx, "blend_mode", "normal")
        return apply_inner_shadow(ctx.image, ctx.mask, color, distance,
                                   direction, blur, blend)


# ============================================================
#  Старая функция
# ============================================================

def apply_inner_shadow(image, mask, color, distance, direction, blur, blend_mode="normal"):
    """Внутренняя тень (Inner Shadow)."""
    if distance == 0:
        return image
    shadow_rgb = get_color_rgb(color)
    dx, dy = get_shadow_offset(direction, distance)

    shifted_mask = Image.new("L", mask.size, 0)
    shifted_mask.paste(mask, (dx, dy))
    shadow_mask = ImageChops.subtract(mask, shifted_mask)
    if blur > 0:
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=blur))
    shadow_mask = ImageChops.multiply(shadow_mask, mask)

    shadow_layer = Image.new("RGBA", image.size, shadow_rgb + (255,))
    shadow_layer.putalpha(shadow_mask)
    return blend_layers(image, shadow_layer, blend_mode)