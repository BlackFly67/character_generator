# -*- coding: utf-8 -*-
"""
Обводка: внешняя и внутренняя.

Плюс — старые функции apply_outer_outline / apply_inner_outline для
обратной совместимости.
"""

import math

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

def _circular_offsets_aa(radius):
    """
    Возвращает список (dy, dx, weight) — смещений внутри круга радиуса
    radius (Евклидово расстояние) с ЛИНЕЙНЫМ anti-aliasing весом на
    границе диска (переходная полоса ~1px: weight=1.0 глубоко внутри,
    плавно падает до 0.0 на самой границе).

    ИСПРАВЛЕНО (после первой правки на "квадрат -> круг"): жёсткий
    порог dist <= radius без сглаживания на радиусах 5-9px даёт
    заметную "лесенку" — растровый круг такого небольшого размера
    физически не может выглядеть гладким без anti-aliasing на границе
    (для сравнения: у самого шрифта края тоже не бинарные, а с
    субпиксельным сглаживанием, поэтому жёсткий круг визуально
    контрастирует со сглаженным контуром буквы). weight здесь и есть
    та самая субпиксельная информация о покрытии.
    """
    r_outer = int(math.ceil(radius)) + 1
    offsets = []
    for dy in range(-r_outer, r_outer + 1):
        for dx in range(-r_outer, r_outer + 1):
            dist = math.hypot(dy, dx)
            weight = max(0.0, min(1.0, radius + 0.5 - dist))
            if weight > 0.0:
                offsets.append((dy, dx, weight))
    return offsets


def _dilate_mask_circular(mask, radius):
    """
    Дилатация (расширение) L-маски по кругу (Евклидово расстояние,
    с anti-aliasing на границе — см. _circular_offsets_aa), а НЕ по
    квадрату, как делает PIL ImageFilter.MaxFilter (Chebyshev/
    "шахматное" расстояние), и не жёстким порогом без сглаживания
    (первая версия этой функции, дававшая видимую "лесенку").

    ИСПРАВЛЕНО: при outline_outer_width 5-9px на размере шрифта 64
    внешняя обводка визуально "ограничивалась прямоугольником" —
    MaxFilter с квадратным ядром раздувал скруглённые части контура
    (изгибы букв "О"/"С", засечки) квадратными углами вместо плавного
    скругления.

    Работаем в градациях серого (uint8), а не bool — иначе теряется
    исходный антиалиасинг маски глифа (частично прозрачные пиксели по
    краю буквы схлопывались бы в жёсткие 0/255 ещё ДО дилатации).
    """
    if radius <= 0:
        return mask
    r = int(math.ceil(radius)) + 1
    arr = np.asarray(mask, dtype=np.uint8)
    h, w = arr.shape
    padded = np.zeros((h + 2 * r, w + 2 * r), dtype=np.uint8)
    padded[r:r + h, r:r + w] = arr

    out = np.zeros((h, w), dtype=np.uint8)
    for dy, dx, weight in _circular_offsets_aa(radius):
        shifted = padded[r + dy:r + dy + h, r + dx:r + dx + w]
        capped = np.minimum(shifted, int(round(weight * 255)))
        np.maximum(out, capped, out=out)

    return Image.fromarray(out, mode="L")


def _erode_mask_circular(mask, radius):
    """
    Эрозия (сжатие) L-маски по кругу с anti-aliasing на границе —
    аналог _dilate_mask_circular, но со "смягчением снизу" вместо
    "смягчения сверху": чем меньше вес offset'а (чем ближе он к
    границе диска), тем меньше он способен утянуть итоговое значение
    вниз (к 0).

    Используется для внутренней обводки вместо PIL
    ImageFilter.MinFilter (та же проблема квадратного структурирующего
    элемента и отсутствия anti-aliasing на границе, что и у дилатации
    выше — здесь менее заметна на тонких штрихах, но на толстых/жирных
    шрифтах с большим width давала такую же "квадратность"/"лесенку"
    углов контура).
    """
    if radius <= 0:
        return mask
    r = int(math.ceil(radius)) + 1
    arr = np.asarray(mask, dtype=np.uint8)
    h, w = arr.shape
    # Паддинг максимумом (255) снаружи — иначе край холста считался бы
    # "пустотой" и эрозия съедала бы контент даже там, где реального
    # фона нет (символ мог быть обрезан по краю холста).
    padded = np.full((h + 2 * r, w + 2 * r), 255, dtype=np.uint8)
    padded[r:r + h, r:r + w] = arr

    out = np.full((h, w), 255, dtype=np.uint8)
    for dy, dx, weight in _circular_offsets_aa(radius):
        shifted = padded[r + dy:r + dy + h, r + dx:r + dx + w]
        floor = int(round((1.0 - weight) * 255))
        loosened = np.maximum(shifted, floor)
        np.minimum(out, loosened, out=out)

    return Image.fromarray(out, mode="L")


# ============================================================
#  Старые функции
# ============================================================

def apply_outer_outline(image, mask, color, width):
    if width <= 0:
        return image, mask
    outline_rgb = get_color_rgb(color)
    # ИСПРАВЛЕНО (2 захода): раньше здесь была
    #   kernel_size = int(width * 2) + 1
    #   expanded = mask.filter(ImageFilter.MaxFilter(size=kernel_size))
    # — квадратная (Chebyshev) дилатация, дающая "блочную"/
    # прямоугольную обводку при width >= ~5px на скруглённых участках
    # контура (буквы "О", "С", засечки и т.п.). Первая замена на
    # круговую дилатацию по жёсткому порогу dist<=radius избавила от
    # прямых углов, но дала видимую "лесенку" на радиусах 5-9px — см.
    # _circular_offsets_aa про anti-aliasing на границе диска.
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
    # — та же проблема квадратного структурирующего элемента и
    # отсутствия anti-aliasing на границе, что и в apply_outer_outline
    # (см. _erode_mask_circular).
    shrunk_alpha = _erode_mask_circular(padded_mask, width)
    outline_mask = ImageChops.subtract(padded_mask, shrunk_alpha)

    outline_layer = Image.new("RGBA", padded_size, outline_rgb + (0,))
    outline_layer.putalpha(outline_mask)
    padded_image.paste(outline_layer, (0, 0), outline_mask)

    return padded_image.crop((pad, pad, w + pad, h + pad))
