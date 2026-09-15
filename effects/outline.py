# -*- coding: utf-8 -*-
"""
Обводка: внешняя и внутренняя.

Плюс — старые функции apply_outer_outline / apply_inner_outline для
обратной совместимости.
"""

from PIL import Image, ImageFilter, ImageChops
import numpy as np

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
#  Круговая дилатация/эрозия (замена квадратным PIL-фильтрам)
# ============================================================

def _circular_offsets(radius):
    """
    Возвращает список (dy, dx) — смещений внутри круга радиуса radius
    (Евклидово расстояние), включая центр (0, 0).

    Используется вместо PIL ImageFilter.MaxFilter/MinFilter, которые
    работают по квадратному (Chebyshev) структурирующему элементу —
    см. комментарий в apply_outer_outline про артефакт "прямоугольной"
    обводки на больших width.
    """
    r = int(round(radius))
    offsets = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r:
                offsets.append((dy, dx))
    return offsets


def _dilate_mask_circular(mask, radius):
    """
    Дилатация (расширение) L-маски по кругу (Евклидово расстояние),
    а НЕ по квадрату, как делает PIL ImageFilter.MaxFilter (Chebyshev/
    "шахматное" расстояние).

    ИСПРАВЛЕНО: при outline_outer_width 5-9px на размере шрифта 64
    внешняя обводка визуально "ограничивалась прямоугольником" — на
    самом деле это MaxFilter с квадратным ядром (kernel_size x
    kernel_size) раздувал скруглённые части контура (изгибы букв
    "О"/"С", засечки) квадратными углами вместо плавного скругления.
    Чем больше width относительно размера деталей глифа, тем заметнее
    становился этот "блочный" эффект — визуально читался как
    прямоугольная граница вокруг символа, а не как контур,
    повторяющий его форму.
    """
    if radius <= 0:
        return mask
    r = int(round(radius))
    arr = np.asarray(mask, dtype=bool)
    h, w = arr.shape
    padded = np.zeros((h + 2 * r, w + 2 * r), dtype=bool)
    padded[r:r + h, r:r + w] = arr

    out = np.zeros_like(arr)
    for dy, dx in _circular_offsets(r):
        out |= padded[r + dy:r + dy + h, r + dx:r + dx + w]

    return Image.fromarray((out.astype(np.uint8) * 255), mode="L")


def _erode_mask_circular(mask, radius):
    """
    Эрозия (сжатие) L-маски по кругу — аналог _dilate_mask_circular,
    но с логическим AND вместо OR (пиксель остаётся включённым только
    если ВСЕ пиксели в радиусе radius вокруг него были включены).

    Используется для внутренней обводки вместо PIL
    ImageFilter.MinFilter (та же проблема квадратного структурирующего
    элемента, что и у MaxFilter в дилатации — здесь менее заметна,
    так как сжатие идёт внутрь уже узкого штриха буквы, но при больших
    width на толстых/жирных шрифтах то же самое "квадратное" искажение
    может проявиться и тут).
    """
    if radius <= 0:
        return mask
    r = int(round(radius))
    arr = np.asarray(mask, dtype=bool)
    h, w = arr.shape
    # Паддинг единицами (True) снаружи — иначе край холста считался бы
    # "пустотой" и эрозия съедала бы контент даже там, где реального
    # фона нет (символ мог быть обрезан по краю холста).
    padded = np.ones((h + 2 * r, w + 2 * r), dtype=bool)
    padded[r:r + h, r:r + w] = arr

    out = np.ones_like(arr)
    for dy, dx in _circular_offsets(r):
        out &= padded[r + dy:r + dy + h, r + dx:r + dx + w]

    return Image.fromarray((out.astype(np.uint8) * 255), mode="L")


# ============================================================
#  Старые функции
# ============================================================

def apply_outer_outline(image, mask, color, width):
    if width <= 0:
        return image, mask
    outline_rgb = get_color_rgb(color)
    # ИСПРАВЛЕНО: раньше здесь была
    #   kernel_size = int(width * 2) + 1
    #   expanded = mask.filter(ImageFilter.MaxFilter(size=kernel_size))
    # — квадратная (Chebyshev) дилатация, дающая "блочную"/
    # прямоугольную обводку при width >= ~5px на скруглённых участках
    # контура (буквы "О", "С", засечки и т.п.). См. подробности в
    # _dilate_mask_circular.
    expanded = _dilate_mask_circular(mask, width)
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
    # ИСПРАВЛЕНО: раньше здесь была
    #   kernel_size = int(width * 2) + 1
    #   shrunk_alpha = padded_mask.filter(ImageFilter.MinFilter(size=kernel_size))
    # — та же проблема квадратного структурирующего элемента, что и в
    # apply_outer_outline (см. _erode_mask_circular). Эффект менее
    # заметен на тонких штрихах, но на толстых/жирных шрифтах с
    # большим width давал такую же "квадратность" углов контура.
    shrunk_alpha = _erode_mask_circular(padded_mask, width)
    outline_mask = ImageChops.subtract(padded_mask, shrunk_alpha)

    outline_layer = Image.new("RGBA", padded_size, outline_rgb + (0,))
    outline_layer.putalpha(outline_mask)
    padded_image.paste(outline_layer, (0, 0), outline_mask)

    return padded_image.crop((pad, pad, w + pad, h + pad))
