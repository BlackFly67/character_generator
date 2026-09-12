# -*- coding: utf-8 -*-
"""
Тиснение (Emboss) с плавным углом освещения.

depth интерпретируется как ДЛИНА вектора смещения:
    dx = depth * cos(angle)
    dy = depth * sin(angle)

При angle = 135° — классический emboss: свет сверху-слева,
тень снизу-справа.
При angle = 45° — свет сверху-справа.
При angle = 0° — свет справа.
При angle = 90° — свет снизу.

ВАЖНО: из-за перехода на плавный угол смещение по каждой оси стало
depth × cos/sin вместо старого (depth, depth). Чтобы визуал старых
пресетов сохранился, дефолт emboss_depth поднят с 3 до 4
(4 × 0.707 ≈ 2.8 ≈ старые 3). Старые пресеты с явным emboss_depth = 3
будут выглядеть чуть слабее — пользователь может поднять depth
вручную, если заметит.
"""

import math
from PIL import Image, ImageFilter, ImageChops

from utils import get_color_rgb
from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT, CTRL_COLOR,
)


class Emboss(EffectBase):
    """Тиснение с плавно настраиваемым углом освещения."""

    id = "emboss"
    label_key = "emboss"
    stage = "inner"
    params = [
        ParamSpec("enabled",    "emboss",              CTRL_CHECKBOX, False),
        ParamSpec("depth",      "emboss_depth",        CTRL_INT,      4, 1, 20),
        ParamSpec("blur",       "emboss_blur",         CTRL_INT,      1, 0, 10),
        # label_key переиспользует уже переведённый "gradient_angle",
        # чтобы не тащить новую строку во все языковые файлы.
        ParamSpec("angle",      "gradient_angle",      CTRL_INT,      135, 0, 360),
        ParamSpec("highlight",  "highlight_color",     CTRL_COLOR,    "#ffffff"),
        ParamSpec("shadow",     "shadow_color_emboss", CTRL_COLOR,    "#000000"),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        depth = int(self._get(ctx, "depth", 4))
        blur = int(self._get(ctx, "blur", 1))
        angle = int(self._get(ctx, "angle", 135))
        highlight = self._get(ctx, "highlight", "#ffffff")
        shadow = self._get(ctx, "shadow", "#000000")
        return apply_emboss(ctx.image, ctx.mask, depth, blur, angle,
                             highlight, shadow)


# ============================================================
#  Функция эффекта
# ============================================================

def _offset_from_angle(angle_degrees, depth):
    """
    Возвращает (dx, dy) — смещение по каждой оси для плавного угла.

    Угол трактуется так: 0° = вправо, 90° = вниз, 180° = влево,
    270° = вверх. Диагонали: 45° = вправо-вниз, 135° = влево-вниз.
    """
    theta = math.radians(angle_degrees % 360)
    dx = int(round(depth * math.cos(theta)))
    dy = int(round(depth * math.sin(theta)))
    return dx, dy


def apply_emboss(image, mask, depth, blur, angle_degrees,
                  highlight_color, shadow_color):
    """
    Тиснение: свет падает с направления angle_degrees, грань,
    обращённая к свету, подсвечивается highlight_color, противоположная
    — затемняется shadow_color.
    """
    if depth <= 0:
        return image

    dx, dy = _offset_from_angle(angle_degrees, depth)

    # Если смещение по обеим осям нулевое (например, depth мал и
    # cos/sin дали 0), нечего делать — возвращаем image как есть.
    if dx == 0 and dy == 0:
        return image

    hl_rgb = get_color_rgb(highlight_color)
    sh_rgb = get_color_rgb(shadow_color)

    # highlight-грань — сторона, обращённая к свету: сдвигаем маску
    # НАВСТРЕЧУ свету (в противоположную от (dx, dy) сторону) и
    # вычитаем её из исходной маски.
    shifted_toward_light = Image.new("L", mask.size, 0)
    shifted_toward_light.paste(mask, (-dx, -dy))
    hl_mask = ImageChops.subtract(mask, shifted_toward_light)

    # shadow-грань — противоположная сторона: сдвигаем маску по (dx, dy).
    shifted_away = Image.new("L", mask.size, 0)
    shifted_away.paste(mask, (dx, dy))
    sh_mask = ImageChops.subtract(mask, shifted_away)

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