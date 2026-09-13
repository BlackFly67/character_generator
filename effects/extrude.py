# -*- coding: utf-8 -*-
"""
3D-выдавливание (Extrude) — имитация объёмного текста.

Рисует depth смещённых копий силуэта символа вдоль угла angle_degrees
(та же трактовка угла, что и в emboss._offset_from_angle: 0°=вправо,
90°=вниз, 180°=влево, 270°=вверх), от дальней грани к ближней, с
цветом, плавно переходящим между color_far и color_near. Результат
подкладывается ПОД уже собранный ctx.image — так исходный текст
остаётся "передней гранью", а стопка слоёв позади него читается как
боковая грань выдавленного объёма.

Стадия "outer" — грань должна быть нарисована уже поверх заливки/
внутренних эффектов, но под внешней обводкой/свечением.
"""

import math
from PIL import Image

from utils import get_color_rgb, blend_layers
from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT, CTRL_COLOR, CTRL_BLEND,
)


class Extrude3D(EffectBase):
    """Псевдо-3D выдавливание силуэта символа."""

    id = "extrude"
    label_key = "extrude"
    stage = "outer"
    params = [
        ParamSpec("enabled",    "extrude",             CTRL_CHECKBOX, False),
        ParamSpec("depth",      "extrude_depth",        CTRL_INT,      10, 1, 100),
        # label_key переиспользует уже переведённый "gradient_angle" —
        # тот же приём, что и в effects/emboss.py, чтобы не тащить
        # новую строку во все языковые файлы.
        ParamSpec("angle",      "gradient_angle",       CTRL_INT,      315, 0, 360),
        ParamSpec("color_near", "extrude_color_near",   CTRL_COLOR,    "#808080"),
        ParamSpec("color_far",  "extrude_color_far",    CTRL_COLOR,    "#202020"),
        ParamSpec("blend_mode", "blend_mode",            CTRL_BLEND,    "normal"),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        depth = int(self._get(ctx, "depth", 10))
        if depth <= 0:
            return ctx.image
        angle = int(self._get(ctx, "angle", 315))
        color_near = self._get(ctx, "color_near", "#808080")
        color_far = self._get(ctx, "color_far", "#202020")
        blend = self._get(ctx, "blend_mode", "normal")
        return apply_extrude(ctx.image, ctx.mask, depth, angle,
                              color_near, color_far, blend)


# ============================================================
#  Функция эффекта
# ============================================================

def _lerp_color(c0, c1, t):
    return tuple(int(round(c0[i] + (c1[i] - c0[i]) * t)) for i in range(3))


def apply_extrude(image, mask, depth, angle_degrees, color_near, color_far,
                   blend_mode="normal"):
    """
    Рисует "боковую грань" из depth слоёв силуэта mask, сдвинутых вдоль
    angle_degrees на 1..depth пикселей — от дальнего слоя (i=depth) к
    ближнему (i=1), чтобы ближние слои перекрывали дальние. Цвет
    интерполируется между color_far (дальняя грань) и color_near
    (ближняя). Готовая стопка подкладывается ПОД image.
    """
    if depth <= 0:
        return image

    theta = math.radians(angle_degrees % 360)
    dx_unit, dy_unit = math.cos(theta), math.sin(theta)

    near_rgb = get_color_rgb(color_near)
    far_rgb = get_color_rgb(color_far)

    stack = Image.new("RGBA", image.size, (0, 0, 0, 0))

    for i in range(depth, 0, -1):
        dx = int(round(dx_unit * i))
        dy = int(round(dy_unit * i))
        if dx == 0 and dy == 0:
            continue

        t = (i - 1) / (depth - 1) if depth > 1 else 0.0
        rgb = _lerp_color(near_rgb, far_rgb, t)

        shifted_mask = Image.new("L", mask.size, 0)
        shifted_mask.paste(mask, (dx, dy))

        layer = Image.new("RGBA", image.size, rgb + (255,))
        layer.putalpha(shifted_mask)
        stack = Image.alpha_composite(stack, layer)

    # blend_layers сам содержит fallback на alpha_composite для
    # mode="normal" (см. utils.blend_layers) — отдельная ветка не нужна.
    return blend_layers(stack, image, blend_mode)