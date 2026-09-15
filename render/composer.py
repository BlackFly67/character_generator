# -*- coding: utf-8 -*-
"""
Единый пайплайн сборки одного символа (текст / дуга / иконка).
Используется и превью, и рендером. Без параметра scale —
масштабирование делает вызывающий код (Image.resize).

Общий холст для батча:
- Текст и дуга: холст считается ОДИН РАЗ по максимальным метрикам всех
  символов батча и передаётся во все вызовы compose_full через geom.
- Иконки: у каждой свой холст (geom не передаётся) — размеры у иконок
  разные, общий холст дал бы кривые отступы.

Выравнивание:
- build_content_mask рисует символ БЕЗ выравнивания — маска прижата к
  левому краю своего слота.
- compose_full применяет text_alignment при вставке маски в ОБЩИЙ слот
  (scaled_content_w), поэтому left/center/right работают относительно
  всего холста, а не относительно ширины отдельного символа.

Система эффектов:
- Все стадии PIPELINE применяются через единый _run_stage():
    fill       — halftone_mask → color_fill → gradient → pattern
    inner      — outline_inner → glow_inner → inner_shadow → emboss
    outer      — outline_outer → extrude → glow_outer
    geometry   — skew → perspective
    post       — reflection → glitch
- _run_stage() работает либо с char_layer (fill/inner/outer/geometry),
  либо с final_img (post) — см. параметр image и extra. Post-эффектам
  нужны char_layer/paste_x/paste_y — они передаются через extra
  и попадают в EffectContext.extra.
- Rotation остаётся отдельным вызовом: она глобальная, применяется ко
  всему холсту, а не к символу как эффект.
- ShadowOuter (внешняя тень) — POST_COMPOSE_EFFECTS: работает с
  final_img, вызывается вручную в шаге 14, потому что должна
  находиться ПОД текстом (между фоном и alpha_composite текста).
"""

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageChops

from utils import (
    get_color_rgb, get_shadow_offset, blend_layers,
    rotate_cleanly, create_checkerboard_background,
)
from fonts import load_font_safe_cached as load_font_safe
from effects.halftone import apply_halftone

# --- Система эффектов ---
from effects.core import EffectContext
from effects.registry import get_by_stage
from effects.shadow_outer import ShadowOuter


# ============================================================
#  Arc — переехало из render/arc.py
# ============================================================

def render_arc_text_mask(text, font, radius, start_angle_deg,
                          clockwise=True, flip=False,
                          alignment="center", letter_spacing=0):
    """Копия из прежнего render/arc.py, без изменений."""
    if not text or radius <= 0:
        return Image.new("L", (1, 1), 0), 0, 0
    if flip:
        text = text[::-1]

    temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    widths, max_asc, max_desc = [], 0, 0
    for ch in text:
        bbox = temp_draw.textbbox((0, 0), ch, font=font, anchor="ls")
        widths.append(max(1, bbox[2] - bbox[0]))
        max_asc = max(max_asc, -bbox[1])
        max_desc = max(max_desc, bbox[3])

    spacing_angle = math.degrees(letter_spacing / radius) if radius > 0 else 0
    total_arc_len = sum(widths) + max(0, len(text) - 1) * letter_spacing
    total_angle = math.degrees(total_arc_len / radius) if radius > 0 else 0

    if alignment == "center":
        angle_cursor = start_angle_deg - total_angle / 2.0
    elif alignment == "left":
        angle_cursor = start_angle_deg
    else:
        angle_cursor = start_angle_deg - total_angle

    placements = []
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")

    for ch, ch_width in zip(text, widths):
        char_angle_span = math.degrees(ch_width / radius) if radius > 0 else 0
        char_center_angle = angle_cursor + char_angle_span / 2.0
        theta_math = math.radians(90 - char_center_angle)
        px = radius * math.cos(theta_math)

        if clockwise:
            py = -radius * math.sin(theta_math)
            base_rotation = char_center_angle
        else:
            py = radius * math.sin(theta_math)
            base_rotation = -char_center_angle

        glyph_bbox = temp_draw.textbbox((0, 0), ch, font=font, anchor="ls")
        gw = glyph_bbox[2] - glyph_bbox[0]
        pad = 4
        glyph_img = Image.new("L", (gw + pad * 2, max_asc + max_desc + pad * 2), 0)
        gdraw = ImageDraw.Draw(glyph_img)
        gdraw.text((pad - glyph_bbox[0], pad + max_asc), ch,
                   font=font, anchor="ls", fill=255)

        rotation_deg = base_rotation + (180 if flip else 0)
        rotated = glyph_img.rotate(-rotation_deg, resample=Image.BICUBIC,
                                   expand=True, fillcolor=0)

        placements.append((rotated, px, py))
        min_x = min(min_x, px - rotated.width / 2)
        max_x = max(max_x, px + rotated.width / 2)
        min_y = min(min_y, py - rotated.height / 2)
        max_y = max(max_y, py + rotated.height / 2)
        angle_cursor += char_angle_span + spacing_angle

    canvas_w = max(1, int(math.ceil(max_x - min_x)))
    canvas_h = max(1, int(math.ceil(max_y - min_y)))
    canvas = Image.new("L", (canvas_w, canvas_h), 0)

    for rotated, px, py in placements:
        paste_x = int(round(px - min_x - rotated.width / 2))
        paste_y = int(round(py - min_y - rotated.height / 2))
        region = canvas.crop((paste_x, paste_y,
                              paste_x + rotated.width,
                              paste_y + rotated.height))
        canvas.paste(ImageChops.lighter(region, rotated), (paste_x, paste_y))

    return canvas, int(round(-min_x)), int(round(-min_y))


# ============================================================
#  Icons — переехало из render/icons.py
# ============================================================

def get_icon_mask(path, target_max_dim=None):
    """Копия из прежнего render/icons.py."""
    try:
        with Image.open(path) as im_raw:
            im = im_raw.convert("RGBA")
    except Exception:
        return Image.new("L", (64, 64), 255), 64, 64

    r, g, b, a = im.split()
    if a.getextrema()[0] < 250:
        mask = a
    else:
        gray = im.convert("L")
        w0, h0 = gray.size
        if w0 > 0 and h0 > 0:
            corners = [gray.getpixel((0, 0)), gray.getpixel((w0 - 1, 0)),
                       gray.getpixel((0, h0 - 1)), gray.getpixel((w0 - 1, h0 - 1))]
            bg_is_light = (sum(corners) / len(corners)) > 127
            mask = ImageChops.invert(gray) if bg_is_light else gray
        else:
            mask = gray

    w, h = mask.size
    if target_max_dim is not None and target_max_dim > 0:
        s = target_max_dim / max(w, h)
        nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
        mask = mask.resize((nw, nh), Image.Resampling.LANCZOS)
        return mask, nw, nh
    return mask, w, h


def default_icon_font_size(icon_paths):
    """Для UI: какой font_size даёт нативный размер иконки."""
    from constants import ICON_CANVAS_BASELINE_OVERHEAD
    if not icon_paths:
        return None
    try:
        _, iw, ih = get_icon_mask(icon_paths[0])
    except Exception:
        return None
    return max(1, max(iw, ih) - ICON_CANVAS_BASELINE_OVERHEAD)


# ============================================================
#  CharSpec / BatchGeometry
# ============================================================

@dataclass
class CharSpec:
    text: Optional[str] = None
    icon_path: Optional[str] = None
    index: int = 0
    arc_mask: Optional[Image.Image] = None
    arc_anchor: Optional[tuple] = None


@dataclass
class BatchGeometry:
    """Единая геометрия холста для батча символов.

    Все поля — в РЕАЛЬНОМ размере (без scale). Вызывающий код
    (превью) ресайзит финальную картинку целиком, а не отдельные
    эффекты.
    """
    base_w: int = 0
    base_h: int = 0
    rot_base_w: int = 0
    rot_base_h: int = 0
    canvas_w: int = 0
    canvas_h: int = 0
    offset_x: int = 0
    offset_y: int = 0
    text_base_x: int = 0
    text_base_y: int = 0
    scaled_content_w: int = 0    # ширина слота под контент (максимум по батчу)
    content_height: int = 0       # высота слота под контент
    max_ascent: int = 0           # общая базовая линия (максимум ascent)
    max_descent: int = 0


# ============================================================
#  Хелперы
# ============================================================

def _calc_outer_effects_width(settings):
    w = 0
    if settings.outline_outer_enabled:
        w += settings.outline_outer_width
    if settings.glow_outer_enabled:
        w += settings.glow_outer_radius
    if settings.shadow_enabled:
        w += settings.shadow_blur
    if settings.glitch_enabled:
        w += settings.glitch_rgb_shift
    if getattr(settings, "extrude_enabled", False):
        w += getattr(settings, "extrude_depth", 0)
    return w


def _will_warp(settings):
    return (
        settings.rotation_angle != 0
        or (settings.skew_enabled and (settings.skew_x != 0 or settings.skew_y != 0))
        or (settings.perspective_enabled and (settings.perspective_x != 0 or settings.perspective_y != 0))
    )


def _text_rgb(settings):
    return get_color_rgb(settings.text_color)


def _transp_bg(settings):
    return (0, 0, 0, 0) if settings.transparent_text else _text_rgb(settings) + (0,)


def _run_stage(image, base_mask, settings, stage,
                fill_mask=None, outer_mask=None, extra=None):
    """
    Применяет эффекты одной стадии из реестра в порядке PIPELINE.

    image — что подаётся эффектам:
      - для fill/inner/outer/geometry: char_layer (RGBA-слой символа);
      - для post: final_img (готовый холст с фоном и текстом).

    extra — словарь доп. данных, прокидывается в EffectContext.extra.
    Нужен post-эффектам: Reflection использует char_layer/paste_x/
    paste_y.

    Возвращает кортеж (image, base_mask, fill_mask, outer_mask).

    Некоторые эффекты могут возвращать dict вместо Image — например,
    если им нужно вернуть и image, и обновлённый mask/outer_mask.
    Контракт: возвращать либо Image, либо dict с ключами
    "image", "mask", "fill_mask", "outer_mask".
    """
    for cls in get_by_stage(stage):
        eff = cls()
        ctx = EffectContext(
            settings=settings,
            image=image,
            mask=base_mask,
            fill_mask=fill_mask,
            outer_mask=outer_mask,
            will_warp=_will_warp(settings),
            extra=extra or {},
        )
        result = eff.apply(ctx)
        if isinstance(result, dict):
            image = result.get("image", image)
            base_mask = result.get("mask", base_mask)
            fill_mask = result.get("fill_mask", fill_mask)
            outer_mask = result.get("outer_mask", outer_mask)
        else:
            image = result
    return image, base_mask, fill_mask, outer_mask


# ============================================================
#  Метрики
# ============================================================

def measure_text_metrics(text, settings):
    font = load_font_safe(settings.font_path, settings.font_size)
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=0, anchor="ls")
    left, top, right, bottom = bbox
    content_width = max(1, right - left)
    content_height = max(1, bottom - top)
    max_ascent = max(1, -top)
    max_descent = max(0, bottom)

    letters_info = None
    if settings.letter_spacing != 0 and len(text) > 1:
        letters_info = []
        cum = 0
        for ch in text:
            b = draw.textbbox((0, 0), ch, font=font, stroke_width=0, anchor="ls")
            cl, _, cr, _ = b
            cw = cr - cl
            letters_info.append((ch, cw, cl))
            cum += cw
        content_width = max(1, cum + (len(text) - 1) * settings.letter_spacing)

    return {
        "font": font,
        "content_width": content_width,
        "content_height": content_height,
        "max_ascent": max_ascent,
        "max_descent": max_descent,
        "letters_info": letters_info,
    }


def measure_arc_metrics(text, settings):
    font = load_font_safe(settings.font_path, settings.font_size)
    mask, ax, ay = render_arc_text_mask(
        text, font, settings.arc_radius,
        settings.arc_start_angle, settings.arc_clockwise,
        settings.arc_flip, settings.text_alignment, settings.letter_spacing,
    )
    return {
        "font": font,
        "arc_mask": mask,
        "arc_anchor": (ax, ay),
        "content_width": max(1, mask.width),
        "content_height": max(1, mask.height),
        "max_ascent": max(1, mask.height),
        "max_descent": 0,
        "letters_info": None,
    }


def measure_icon_metrics(icon_path, settings):
    mask, iw, ih = get_icon_mask(icon_path, settings.font_size)
    return {
        "font": None,
        "icon_mask": mask,
        "content_width": max(1, iw),
        "content_height": max(1, ih),
        "max_ascent": max(1, ih),
        "max_descent": 0,
        "letters_info": None,
    }


# ============================================================
#  Batch geometry — ОБЩИЙ холст для батча
# ============================================================

def compute_batch_geometry(specs, settings) -> BatchGeometry:
    """
    Вычисляет ЕДИНУЮ геометрию холста по всем спеку батча.
    Холст получается по МАКСИМАЛЬНЫМ метрикам — все символы вставляются
    в один и тот же размер, узкая буква («.») центрируется в слоте
    широкой («М»), базовая линия общая.
    """
    outer = _calc_outer_effects_width(settings)
    safe_pad = 1
    eff_x = settings.text_scale_x if settings.text_scale_x > 0 else 1.0

    max_cw = 1
    max_ch = 1
    max_ascent = 1
    max_descent = 0

    for spec in specs:
        if spec.icon_path is not None:
            m = measure_icon_metrics(spec.icon_path, settings)
        elif settings.arc_text_enabled:
            m = measure_arc_metrics(spec.text, settings)
        else:
            m = measure_text_metrics(spec.text, settings)

        cw = max(1, int(round(m["content_width"] * eff_x)))
        ch = m["content_height"]
        if cw > max_cw:
            max_cw = cw
        if ch > max_ch:
            max_ch = ch
        if m["max_ascent"] > max_ascent:
            max_ascent = m["max_ascent"]
        if m["max_descent"] > max_descent:
            max_descent = m["max_descent"]

    base_w = max_cw + outer * 2 + safe_pad * 2
    base_h = max_ch + outer * 2 + safe_pad * 2
    text_base_x = outer + safe_pad
    text_base_y = outer + safe_pad

    angle_rad = math.radians(settings.rotation_angle)
    rot_w = int(math.ceil(abs(base_w * math.cos(angle_rad))
                          + abs(base_h * math.sin(angle_rad)))) + 2
    rot_h = int(math.ceil(abs(base_w * math.sin(angle_rad))
                          + abs(base_h * math.cos(angle_rad)))) + 2
    rot_w, rot_h = max(1, rot_w), max(1, rot_h)

    if settings.skew_enabled and (settings.skew_x != 0 or settings.skew_y != 0):
        if settings.skew_x != 0:
            sx = math.radians(max(-85.0, min(85.0, settings.skew_x)))
            rot_w += int(math.ceil(abs(math.tan(sx)) * max(0, rot_h - 1)))
        if settings.skew_y != 0:
            sy = math.radians(max(-85.0, min(85.0, settings.skew_y)))
            rot_h += int(math.ceil(abs(math.tan(sy)) * max(0, rot_w - 1)))

    if settings.shadow_enabled:
        margin = settings.shadow_blur
        dx, dy = get_shadow_offset(settings.shadow_direction, settings.shadow_distance)
        min_x, min_y = min(0, dx - margin), min(0, dy - margin)
        max_x = max(rot_w, rot_w + dx + margin)
        max_y = max(rot_h, rot_h + dy + margin)
    else:
        min_x = min_y = 0
        max_x, max_y = rot_w, rot_h

    canvas_w = int(max_x - min_x)
    canvas_h = int(max_y - min_y)
    offset_x, offset_y = -min_x, -min_y

    if settings.reflection_enabled and settings.reflection_opacity > 0:
        canvas_h += max(0, settings.reflection_gap + max_ch)

    if getattr(settings, "canvas_width_enabled", False):
        delta = getattr(settings, "canvas_width_delta",
                        getattr(settings, "canvas_width", 0))
        canvas_w = max(1, canvas_w + delta)
        offset_x += delta // 2

    return BatchGeometry(
        base_w=base_w, base_h=base_h,
        rot_base_w=rot_w, rot_base_h=rot_h,
        canvas_w=canvas_w, canvas_h=canvas_h,
        offset_x=offset_x, offset_y=offset_y,
        text_base_x=text_base_x, text_base_y=text_base_y,
        scaled_content_w=max_cw,
        content_height=max_ch,
        max_ascent=max_ascent,
        max_descent=max_descent,
    )


# ============================================================
#  Маска контента
# ============================================================

def build_content_mask(spec, metrics, settings):
    """
    Строит маску контента В НОРМАЛЬНОМ РАЗМЕРЕ (свой размер для каждого
    символа), затем сжимает её по X, если text_scale_x != 1.0.

    Выравнивание текста (text_alignment) здесь НЕ применяется — маска
    всегда прижата к левому краю своего слота. Горизонтальное
    выравнивание делает compose_full при вставке маски в общий слот
    (scaled_content_w), чтобы left/center/right работали относительно
    всего холста, а не относительно ширины отдельного символа.
    """
    if spec.icon_path is not None:
        mask = metrics["icon_mask"].copy()
    elif settings.arc_text_enabled:
        arc = metrics["arc_mask"]
        mask = Image.new("L", (metrics["content_width"], metrics["content_height"]), 0)
        px = max(0, (mask.width - arc.width) // 2)
        py = max(0, (mask.height - arc.height) // 2)
        mask.paste(arc, (px, py))
    else:
        font = metrics["font"]
        letters = metrics["letters_info"]
        mask = Image.new("L", (metrics["content_width"], metrics["content_height"]), 0)
        d = ImageDraw.Draw(mask)

        if letters is not None:
            cur = -letters[0][2]
            for ch, cw, _ in letters:
                d.text((cur, metrics["max_ascent"]), ch,
                       font=font, anchor="ls", fill=255)
                cur += cw + settings.letter_spacing
        else:
            tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            b = tmp.textbbox((0, 0), spec.text, font=font, anchor="ls")
            left = b[0]
            d.text((-left, metrics["max_ascent"]), spec.text,
                   font=font, anchor="ls", fill=255)

    # Сжатие/расширение по X применяем к маске целиком.
    eff_x = settings.text_scale_x if settings.text_scale_x > 0 else 1.0
    if eff_x != 1.0:
        new_w = max(1, int(round(mask.width * eff_x)))
        if new_w != mask.width:
            mask = mask.resize((new_w, mask.height), Image.Resampling.LANCZOS)

    return mask


# ============================================================
#  Главная функция
# ============================================================

def compose_full(spec: CharSpec, settings,
                 geom: Optional[BatchGeometry] = None) -> Image.Image:
    """
    Собирает финальное изображение одного символа в РЕАЛЬНОМ размере.

    geom — общая геометрия батча. Если None, считается по одному
    спеку (используется в превью для одиночного символа и в
    render_icons, где у каждой иконки свой холст).

    Символ центрируется по X в общем слоте scaled_content_w (с учётом
    text_alignment) и прижимается к общей базовой линии max_ascent.
    """
    # 1. Метрики конкретного символа
    if spec.icon_path is not None:
        metrics = measure_icon_metrics(spec.icon_path, settings)
    elif settings.arc_text_enabled:
        metrics = measure_arc_metrics(spec.text, settings)
    else:
        metrics = measure_text_metrics(spec.text, settings)

    # 2. Маска контента (свой размер, без выравнивания)
    content_mask = build_content_mask(spec, metrics, settings)

    # 3. Геометрия: общая или локальная
    if geom is None:
        geom = compute_batch_geometry([spec], settings)

    base_w, base_h = geom.base_w, geom.base_h

    # 4. Вставляем content_mask в ОБЩИЙ слот:
    #    - по X: выравниваем внутри scaled_content_w согласно text_alignment;
    #    - по Y: прижимаем к общей базовой линии (max_ascent).
    content_w = content_mask.width
    content_h = content_mask.height

    align = settings.text_alignment
    if align == "left":
        paste_in_slot_x = geom.text_base_x
    elif align == "right":
        paste_in_slot_x = geom.text_base_x + (geom.scaled_content_w - content_w)
    else:  # center
        paste_in_slot_x = geom.text_base_x + (geom.scaled_content_w - content_w) // 2

    paste_in_slot_y = geom.text_base_y + (geom.max_ascent - metrics["max_ascent"])

    text_mask = Image.new("L", (base_w, base_h), 0)
    text_mask.paste(content_mask, (paste_in_slot_x, paste_in_slot_y))

    char_layer = Image.new("RGBA", (base_w, base_h), _transp_bg(settings))
    base_mask = text_mask

    # 5. Fill-стадия: halftone_mask → color_fill → gradient → pattern
    will_warp = _will_warp(settings)
    fill_mask = base_mask
    char_layer, base_mask, fill_mask, outer_mask = _run_stage(
        char_layer, base_mask, settings, "fill",
        fill_mask=fill_mask, outer_mask=None,
    )

    # 6. Inner-стадия: outline_inner → glow_inner → inner_shadow → emboss
    char_layer, base_mask, fill_mask, outer_mask = _run_stage(
        char_layer, base_mask, settings, "inner",
        fill_mask=fill_mask, outer_mask=None,
    )

    # 7. Outer-стадия: outline_outer → extrude → glow_outer
    # OutlineOuter возвращает dict с обновлённым outer_mask — его
    # увидит GlowOuter. Если OutlineOuter выключен, outer_mask
    # остаётся base_mask.
    outer_mask = base_mask
    char_layer, base_mask, fill_mask, outer_mask = _run_stage(
        char_layer, base_mask, settings, "outer",
        fill_mask=fill_mask, outer_mask=outer_mask,
    )

    # 8. Прозрачность (глобальная, не эффект)
    if settings.text_opacity < 1.0:
        r, g, b, a = char_layer.split()
        a = a.point(lambda p: int(p * settings.text_opacity))
        char_layer = Image.merge("RGBA", (r, g, b, a))

    # 9. Rotation (глобальная, вне PIPELINE)
    if settings.rotation_angle != 0:
        char_layer = rotate_cleanly(char_layer, -settings.rotation_angle,
                                     _text_rgb(settings))

    # 10. Geometry-стадия: skew → perspective
    char_layer, base_mask, fill_mask, outer_mask = _run_stage(
        char_layer, base_mask, settings, "geometry",
        fill_mask=fill_mask, outer_mask=outer_mask,
    )

    # 11. Halftone после искажений
    if settings.halftone_enabled and not settings.transparent_text and will_warp:
        alpha = char_layer.split()[3]
        ht = apply_halftone(alpha, settings.halftone_cell_size,
                             settings.halftone_dot_scale, settings.halftone_angle)
        r, g, b, _ = char_layer.split()
        char_layer = Image.merge("RGBA", (r, g, b, ht))

    # 12. Фон
    cw, ch = geom.canvas_w, geom.canvas_h
    if settings.transparent_background or settings.background_color is None:
        final_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    else:
        bg = settings.background_color
        if isinstance(bg, str) and bg.startswith("#"):
            bg = tuple(int(bg.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        elif isinstance(bg, str):
            bg = (255, 255, 255, 255) if bg == "white" else (0, 0, 0, 255)
        final_img = Image.new("RGBA", (cw, ch), bg)

    # 13. Позиция вставки слоя
    paste_x = geom.offset_x + (geom.rot_base_w - char_layer.width) // 2
    paste_y = geom.offset_y + (geom.rot_base_h - char_layer.height) // 2

    # 14. Тень (post-compose: работает с final_img, вызывается вручную,
    #     потому что должна оказаться ПОД текстом — между фоном и
    #     alpha_composite текста в шаге 15).
    if settings.shadow_enabled:
        shadow_ctx = EffectContext(
            settings=settings,
            image=final_img,
            mask=base_mask,
            extra={
                "char_layer": char_layer,
                "paste_x": paste_x,
                "paste_y": paste_y,
                "canvas_w": cw,
                "canvas_h": ch,
            },
        )
        final_img = ShadowOuter().apply(shadow_ctx)

    # 15. Текст
    layer_text = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    layer_text.paste(char_layer, (paste_x, paste_y))
    final_img = Image.alpha_composite(final_img, layer_text)

    # 16. Cutout
    if (not settings.transparent_text and settings.cutout_mode
            and not settings.transparent_background):
        # Маска для выреза — альфа уже полностью трансформированного
        # layer_text (см. FIX в предыдущих итерациях).
        full_mask = layer_text.split()[3].point(lambda p: 255 if p > 128 else 0)
        r, g, b, a = final_img.split()
        new_a = Image.composite(Image.new("L", final_img.size, 0), a, full_mask)
        final_img = Image.merge("RGBA", (r, g, b, new_a))

    # 17. Post-стадия: reflection → glitch
    # Работает с final_img. Reflection берёт char_layer/paste_x/paste_y
    # из extra. Glitch использует settings.glitch_seed — общий для
    # всех символов батча (поэтому spec_index в extra НЕ передаётся).
    final_img, _, _, _ = _run_stage(
        final_img, base_mask, settings, "post",
        extra={
            "char_layer": char_layer,
            "paste_x": paste_x,
            "paste_y": paste_y,
        },
    )

    return final_img