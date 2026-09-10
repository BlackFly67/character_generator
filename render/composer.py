# -*- coding: utf-8 -*-
"""
Единый пайплайн сборки одного символа (текст / дуга / иконка).
Используется и превью, и рендером. Без параметра scale —
масштабирование делает вызывающий код (Image.resize).
"""

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageChops

from utils import (
    get_color_rgb, get_shadow_offset, blend_layers,
    rotate_cleanly, create_checkerboard_background,
)
from fonts import load_font_safe
from effects.glow import apply_outer_glow, apply_inner_glow
from effects.outline import apply_outer_outline, apply_inner_outline
from effects.emboss import apply_emboss
from effects.gradient import apply_gradient_fill
from effects.pattern import apply_pattern_fill, load_pattern_image
from effects.inner_shadow import apply_inner_shadow
from effects.halftone import apply_halftone
from effects.glitch import apply_glitch_effect
from effects.skew import apply_skew_effect
from effects.perspective import apply_perspective_effect


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
#  CharSpec
# ============================================================

@dataclass
class CharSpec:
    text: Optional[str] = None
    icon_path: Optional[str] = None
    index: int = 0
    # Заранее посчитанная маска (для batch-рендера)
    arc_mask: Optional[Image.Image] = None
    arc_anchor: Optional[tuple] = None


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
#  Геометрия
# ============================================================

def compute_canvas_geometry(metrics, settings):
    outer = _calc_outer_effects_width(settings)
    safe_pad = 1

    eff_x = settings.text_scale_x if settings.text_scale_x > 0 else 1.0
    scaled_content_w = max(1, int(round(metrics["content_width"] * eff_x)))

    base_w = scaled_content_w + outer * 2 + safe_pad * 2
    base_h = metrics["content_height"] + outer * 2 + safe_pad * 2
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

    # Отражение расширяет холст снизу
    if settings.reflection_enabled and settings.reflection_opacity > 0:
        content_h = metrics["max_ascent"] + metrics["max_descent"]
        canvas_h += max(0, settings.reflection_gap + content_h)

    if getattr(settings, "canvas_width_enabled", False):
        delta = getattr(settings, "canvas_width_delta",
                        getattr(settings, "canvas_width", 0))
        canvas_w = max(1, canvas_w + delta)
        offset_x += delta // 2

    return {
        "base_w": base_w, "base_h": base_h,
        "rot_base_w": rot_w, "rot_base_h": rot_h,
        "canvas_w": canvas_w, "canvas_h": canvas_h,
        "offset_x": offset_x, "offset_y": offset_y,
        "text_base_x": text_base_x, "text_base_y": text_base_y,
        "scaled_content_w": scaled_content_w,
        "content_height": metrics["content_height"],
        "max_ascent": metrics["max_ascent"],
    }


# ============================================================
#  Маска контента
# ============================================================

def build_content_mask(spec, metrics, geom, settings):
    if spec.icon_path is not None:
        mask = metrics["icon_mask"]
        eff_x = settings.text_scale_x if settings.text_scale_x > 0 else 1.0
        target_w = max(1, int(round(mask.width * eff_x)))
        if target_w != mask.width:
            mask = mask.resize((target_w, mask.height), Image.Resampling.LANCZOS)
        return mask

    if settings.arc_text_enabled:
        arc = metrics["arc_mask"]
        cm = Image.new("L", (geom["scaled_content_w"], geom["content_height"]), 0)
        px = max(0, (geom["scaled_content_w"] - arc.width) // 2)
        py = max(0, (geom["content_height"] - arc.height) // 2)
        cm.paste(arc, (px, py))
        return cm

    font = metrics["font"]
    letters = metrics["letters_info"]
    cm = Image.new("L", (geom["scaled_content_w"], geom["content_height"]), 0)
    d = ImageDraw.Draw(cm)

    if letters is not None:
        tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        scaled = []
        cum = 0
        for ch, _, _ in letters:
            b = tmp.textbbox((0, 0), ch, font=font, anchor="ls")
            cl, _, cr, _ = b
            cw = cr - cl
            scaled.append((ch, cw, cl))
            cum += cw
        total = cum + (len(scaled) - 1) * settings.letter_spacing

        if settings.text_alignment == "left":
            x0 = -scaled[0][2]
        elif settings.text_alignment == "right":
            x0 = geom["scaled_content_w"] - total - scaled[0][2]
        else:
            x0 = (geom["scaled_content_w"] - total) / 2 - scaled[0][2]

        cur = x0
        for ch, cw, _ in scaled:
            d.text((cur, geom["max_ascent"]), ch, font=font, anchor="ls", fill=255)
            cur += cw + settings.letter_spacing
    else:
        tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        b = tmp.textbbox((0, 0), spec.text, font=font, anchor="ls")
        left, _, right, _ = b
        w = right - left
        if settings.text_alignment == "left":
            x = -left
        elif settings.text_alignment == "right":
            x = geom["scaled_content_w"] - w - left
        else:
            x = (geom["scaled_content_w"] - w) / 2 - left
        d.text((x, geom["max_ascent"]), spec.text, font=font, anchor="ls", fill=255)

    return cm


# ============================================================
#  Отражение (перенесено из превью, работает с финальным img)
# ============================================================

def _apply_reflection(final_img, char_layer, paste_x, paste_y,
                       gap, opacity, fade):
    bbox = char_layer.split()[3].getbbox()
    if bbox is None:
        return final_img

    cleft, ctop, cright, cbottom = bbox
    visible = char_layer.crop(bbox)
    reflected = visible.transpose(Image.FLIP_TOP_BOTTOM)

    rp_h = reflected.height
    fade_px = max(1, min(rp_h, int(round(rp_h * fade))))
    grad = np.linspace(opacity, 0.0, fade_px, dtype=np.float64)
    if rp_h > fade_px:
        grad = np.concatenate([grad, np.zeros(rp_h - fade_px, dtype=np.float64)])

    r, g, b, a = reflected.split()
    alpha = np.asarray(a, dtype=np.float64)
    new_alpha = np.clip(alpha * grad.reshape(-1, 1), 0, 255).astype(np.uint8)
    reflected.putalpha(Image.fromarray(new_alpha))

    dest_x = paste_x + cleft
    dest_y = paste_y + cbottom + gap
    if dest_x < final_img.width and dest_y < final_img.height:
        final_img = final_img.copy()
        final_img.alpha_composite(reflected, (dest_x, dest_y))
    return final_img


# ============================================================
#  Главная функция
# ============================================================

def compose_full(spec: CharSpec, settings) -> Image.Image:
    """
    Собирает финальное изображение одного символа в РЕАЛЬНОМ размере.
    Масштабирование делает вызывающий код через Image.resize.
    """
    # 1. Метрики
    if spec.icon_path is not None:
        metrics = measure_icon_metrics(spec.icon_path, settings)
    elif settings.arc_text_enabled:
        metrics = measure_arc_metrics(spec.text, settings)
    else:
        metrics = measure_text_metrics(spec.text, settings)

    # 2. Геометрия
    geom = compute_canvas_geometry(metrics, settings)

    # 3. Маска
    content_mask = build_content_mask(spec, metrics, geom, settings)

    base_w, base_h = geom["base_w"], geom["base_h"]
    text_mask = Image.new("L", (base_w, base_h), 0)
    text_mask.paste(content_mask, (geom["text_base_x"], geom["text_base_y"]))

    char_layer = Image.new("RGBA", (base_w, base_h), _transp_bg(settings))
    base_mask = text_mask

    # 4. Halftone до искажений
    will_warp = _will_warp(settings)
    fill_mask = base_mask
    if settings.halftone_enabled and not settings.transparent_text and not will_warp:
        fill_mask = apply_halftone(base_mask, settings.halftone_cell_size,
                                    settings.halftone_dot_scale,
                                    settings.halftone_angle)

    # 5. Заливка
    if not settings.transparent_text:
        if settings.gradient_enabled:
            stops = settings.gradient_stops or [
                {"pos": 0.0, "color": "#ff0000"},
                {"pos": 1.0, "color": "#0000ff"},
            ]
            char_layer = apply_gradient_fill(char_layer, fill_mask, stops,
                                              settings.gradient_type,
                                              settings.gradient_angle)
        else:
            fill = Image.new("RGBA", char_layer.size, _text_rgb(settings) + (255,))
            fill.putalpha(fill_mask)
            char_layer = Image.alpha_composite(char_layer, fill)

        if settings.pattern_enabled and settings.pattern_image_path:
            pat = load_pattern_image(settings.pattern_image_path)
            if pat is not None:
                char_layer = apply_pattern_fill(
                    char_layer, fill_mask, pat,
                    settings.pattern_scale,
                    settings.pattern_offset_x, settings.pattern_offset_y,
                    settings.pattern_angle, settings.pattern_blend_mode,
                )

    # 6. Внутренние эффекты
    if settings.outline_inner_enabled and settings.outline_inner_width > 0:
        char_layer = apply_inner_outline(char_layer, base_mask,
                                          settings.outline_inner_color,
                                          settings.outline_inner_width)

    if settings.glow_inner_enabled:
        char_layer = apply_inner_glow(char_layer, base_mask,
                                       settings.glow_inner_color,
                                       settings.glow_inner_radius,
                                       settings.glow_inner_intensity,
                                       settings.glow_inner_blend_mode)

    if settings.inner_shadow_enabled:
        char_layer = apply_inner_shadow(char_layer, base_mask,
                                         settings.inner_shadow_color,
                                         settings.inner_shadow_distance,
                                         settings.inner_shadow_direction,
                                         settings.inner_shadow_blur,
                                         settings.inner_shadow_blend_mode)

    if settings.emboss_enabled:
        char_layer = apply_emboss(char_layer, base_mask,
                                   settings.emboss_depth, settings.emboss_blur,
                                   settings.emboss_highlight, settings.emboss_shadow)

    # 7. Внешние эффекты
    outer_mask = base_mask
    outline_drawn = False
    if settings.outline_outer_enabled and settings.outline_outer_width > 0:
        char_layer, outer_mask = apply_outer_outline(
            char_layer, base_mask, settings.outline_outer_color,
            settings.outline_outer_width,
        )
        outline_drawn = True

    if settings.glow_outer_enabled and (not settings.transparent_text or outline_drawn):
        char_layer = apply_outer_glow(char_layer, outer_mask,
                                       settings.glow_outer_color,
                                       settings.glow_outer_radius,
                                       settings.glow_outer_intensity)

    # 8. Прозрачность
    if settings.text_opacity < 1.0:
        r, g, b, a = char_layer.split()
        a = a.point(lambda p: int(p * settings.text_opacity))
        char_layer = Image.merge("RGBA", (r, g, b, a))

    # 9. Поворот / skew / perspective
    if settings.rotation_angle != 0:
        char_layer = rotate_cleanly(char_layer, -settings.rotation_angle,
                                     _text_rgb(settings))
    if settings.skew_enabled and (settings.skew_x != 0 or settings.skew_y != 0):
        char_layer = apply_skew_effect(char_layer, settings.skew_x,
                                        settings.skew_y, _text_rgb(settings))
    if settings.perspective_enabled and (settings.perspective_x != 0 or settings.perspective_y != 0):
        char_layer = apply_perspective_effect(char_layer, settings.perspective_x,
                                               settings.perspective_y,
                                               _text_rgb(settings))

    # 10. Halftone после искажений
    if settings.halftone_enabled and not settings.transparent_text and will_warp:
        alpha = char_layer.split()[3]
        ht = apply_halftone(alpha, settings.halftone_cell_size,
                             settings.halftone_dot_scale, settings.halftone_angle)
        r, g, b, _ = char_layer.split()
        char_layer = Image.merge("RGBA", (r, g, b, ht))

    # 11. Фон
    cw, ch = geom["canvas_w"], geom["canvas_h"]
    if settings.transparent_background or settings.background_color is None:
        final_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    else:
        bg = settings.background_color
        if isinstance(bg, str) and bg.startswith("#"):
            bg = tuple(int(bg.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        elif isinstance(bg, str):
            bg = (255, 255, 255, 255) if bg == "white" else (0, 0, 0, 255)
        final_img = Image.new("RGBA", (cw, ch), bg)

    # 12. Позиция вставки
    paste_x = geom["offset_x"] + (geom["rot_base_w"] - char_layer.width) // 2
    paste_y = geom["offset_y"] + (geom["rot_base_h"] - char_layer.height) // 2

    # 13. Тень
    if settings.shadow_enabled:
        shadow_rgb = get_color_rgb(settings.shadow_color)
        shadow_bg = (0, 0, 0, 0) if settings.transparent_text else shadow_rgb + (0,)
        sh_mask = char_layer.split()[3]
        sh_layer = Image.new("RGBA", char_layer.size, shadow_rgb + (255,))
        sh_layer.putalpha(sh_mask)
        if settings.shadow_blur > 0:
            sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(radius=settings.shadow_blur))
        dx, dy = get_shadow_offset(settings.shadow_direction, settings.shadow_distance)
        sh_final = Image.new("RGBA", (cw, ch), shadow_bg)
        sh_final.paste(sh_layer, (paste_x + dx, paste_y + dy))

        blend_mode = settings.shadow_blend_mode
        if settings.transparent_background and blend_mode in ("multiply", "overlay"):
            blend_mode = "normal"
        final_img = blend_layers(final_img, sh_final, blend_mode)

    # 14. Текст
    layer_text = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    layer_text.paste(char_layer, (paste_x, paste_y))
    final_img = Image.alpha_composite(final_img, layer_text)

    # 15. Cutout
    if (not settings.transparent_text and settings.cutout_mode
            and not settings.transparent_background):
        mask = text_mask.copy()
        if settings.rotation_angle != 0:
            mask = mask.rotate(-settings.rotation_angle, resample=Image.BICUBIC, expand=True)
        mask = mask.point(lambda p: 255 if p > 128 else 0)
        full_mask = Image.new("L", (cw, ch), 0)
        full_mask.paste(mask, (paste_x, paste_y))
        r, g, b, a = final_img.split()
        new_a = Image.composite(Image.new("L", final_img.size, 0), a, full_mask)
        final_img = Image.merge("RGBA", (r, g, b, new_a))

    # 16. Отражение
    if settings.reflection_enabled:
        final_img = _apply_reflection(
            final_img, char_layer, paste_x, paste_y,
            settings.reflection_gap,
            settings.reflection_opacity / 100.0,
            settings.reflection_fade / 100.0,
        )

    # 17. Glitch
    if settings.glitch_enabled:
        final_img = apply_glitch_effect(
            final_img, settings.glitch_rgb_shift,
            settings.glitch_slice_intensity,
            seed=(settings.glitch_seed + spec.index) & 0xFFFFFFFF,
        )

    return final_img