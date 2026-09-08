# -*- coding: utf-8 -*-
"""
Рендер текста с применением всех эффектов
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np

from utils import (
    get_color_rgb, get_color_rgba, get_shadow_offset, 
    blend_layers, rotate_cleanly, format_filename,
    create_checkerboard_background, parse_characters
)
from fonts import load_font_safe
from effects.shadow import apply_shadow
from effects.glow import apply_outer_glow, apply_inner_glow
from effects.outline import apply_outer_outline, apply_inner_outline
from effects.emboss import apply_emboss
from effects.gradient import apply_gradient_fill
from effects.pattern import apply_pattern_fill, load_pattern_image
from effects.inner_shadow import apply_inner_shadow
from effects.halftone import apply_halftone
from effects.reflection import apply_reflection
from effects.glitch import apply_glitch_effect
from effects.skew import apply_skew_effect
from effects.perspective import apply_perspective_effect
from render.arc import render_arc_text_mask


def render_characters(characters, settings, progress_callback=None):
    """
    Главная функция рендера символов (текст или иконки).
    """
    if settings.icon_mode:
        from render.icons import render_icons
        return render_icons(characters, settings, progress_callback)
    else:
        return render_text_characters(characters, settings, progress_callback)


def render_text_characters(characters, settings, progress_callback=None):
    """
    Рендер текстовых символов.
    """
    os.makedirs("output", exist_ok=True)
    
    # Загружаем шрифт
    font = load_font_safe(settings.font_path, settings.font_size)
    temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    
    # Проверяем, не пустой ли шрифт
    if font == ImageFont.load_default() and settings.font_size > 20:
        # Предупреждение о битовом шрифте
        pass
    
    # --- Сбор метрик для всех символов ---
    all_metrics = {}
    max_ascent, max_descent, max_width = 0, 0, 0
    arc_masks = {}
    
    if settings.arc_text_enabled:
        # Текст по дуге
        g_xmin, g_xmax, g_ymin, g_ymax = float('inf'), float('-inf'), float('inf'), float('-inf')
        for char in characters:
            mask, anchor_x, anchor_y = render_arc_text_mask(
                char, font, settings.arc_radius, settings.arc_start_angle,
                settings.arc_clockwise, settings.arc_flip,
                settings.text_alignment, settings.letter_spacing
            )
            arc_masks[char] = (mask, anchor_x, anchor_y)
            g_xmin = min(g_xmin, -anchor_x)
            g_xmax = max(g_xmax, mask.width - anchor_x)
            g_ymin = min(g_ymin, -anchor_y)
            g_ymax = max(g_ymax, mask.height - anchor_y)
        
        if g_xmin == float('inf'):
            g_xmin = g_xmax = g_ymin = g_ymax = 0
        
        arc_anchor_x, arc_anchor_y = -g_xmin, -g_ymin
        max_width = g_xmax - g_xmin
        max_ascent = g_ymax - g_ymin
        max_descent = 0
        
    else:
        # Обычный текст
        for char in characters:
            bbox = temp_draw.textbbox((0, 0), char, font=font, stroke_width=0, anchor="ls")
            left, top, right, bottom = bbox
            all_metrics[char] = {
                'width': right - left,
                'height': bottom - top,
                'ascent': -top,
                'descent': bottom,
                'left': left
            }
            max_ascent = max(max_ascent, -top)
            max_descent = max(max_descent, bottom)
            max_width = max(max_width, right - left)
    
    # --- Вычисление размеров холста ---
    outer_effects_width = _calc_outer_effects_width(settings)
    safe_pad = 1
    content_width = max_width
    content_height = max_ascent + max_descent
    
    # Масштабирование по X
    effective_scale = settings.text_scale_x if settings.text_scale_x > 0 else 1.0
    scaled_content_width = max(1, int(round(content_width * effective_scale))) if effective_scale != 1.0 else content_width
    
    base_width = scaled_content_width + outer_effects_width * 2 + (safe_pad * 2)
    base_height = content_height + outer_effects_width * 2 + (safe_pad * 2)
    text_base_x = outer_effects_width + safe_pad
    text_base_y = outer_effects_width + safe_pad
    
    # --- Поворот ---
    angle_rad = math.radians(settings.rotation_angle)
    rot_base_w = int(math.ceil(abs(base_width * math.cos(angle_rad)) + 
                               abs(base_height * math.sin(angle_rad)))) + 2
    rot_base_h = int(math.ceil(abs(base_width * math.sin(angle_rad)) + 
                               abs(base_height * math.cos(angle_rad)))) + 2
    rot_base_w, rot_base_h = max(1, rot_base_w), max(1, rot_base_h)
    
    # --- Skew (расширение холста) ---
    if settings.skew_enabled and (settings.skew_x != 0 or settings.skew_y != 0):
        if settings.skew_x != 0:
            skew_x_rad = math.radians(max(-85.0, min(85.0, settings.skew_x)))
            rot_base_w += int(math.ceil(abs(math.tan(skew_x_rad)) * max(0, rot_base_h - 1)))
        if settings.skew_y != 0:
            skew_y_rad = math.radians(max(-85.0, min(85.0, settings.skew_y)))
            rot_base_h += int(math.ceil(abs(math.tan(skew_y_rad)) * max(0, rot_base_w - 1)))
    
    # --- Тень (расширение холста) ---
    if settings.shadow_enabled:
        margin = settings.shadow_blur
        sh_dx, sh_dy = get_shadow_offset(settings.shadow_direction, settings.shadow_distance)
        min_x = min(0, sh_dx - margin)
        min_y = min(0, sh_dy - margin)
        max_x = max(rot_base_w, rot_base_w + sh_dx + margin)
        max_y = max(rot_base_h, rot_base_h + sh_dy + margin)
    else:
        min_x, min_y = 0, 0
        max_x, max_y = rot_base_w, rot_base_h
    
    canvas_w = int(max_x - min_x)
    canvas_h = int(max_y - min_y)
    offset_x = -min_x
    offset_y = -min_y
    
    # --- Дельта ширины холста ---
    if settings.canvas_width_enabled:
        canvas_w = max(1, canvas_w + settings.canvas_width_delta)
        offset_x += settings.canvas_width_delta // 2
    
    # --- Подготовка ---
    text_rgb = get_color_rgb(settings.text_color)
    transp_bg = text_rgb + (0,) if not settings.transparent_text else (0, 0, 0, 0)
    
    # Загрузка текстуры для паттерна
    pattern_image = None
    if settings.pattern_enabled and settings.pattern_image_path:
        pattern_image = load_pattern_image(settings.pattern_image_path)
    
    # Градиентные точки
    gradient_stops = settings.gradient_stops if settings.gradient_stops else [
        {"pos": 0.0, "color": "#ff0000"},
        {"pos": 1.0, "color": "#0000ff"}
    ]
    
    used_filenames = set()
    generated_files = []
    total = len(characters)
    
    # --- Основной цикл по символам ---
    for index, char in enumerate(characters, 1):
        # --- Создание маски символа ---
        if settings.arc_text_enabled:
            # Текст по дуге
            if char not in arc_masks:
                continue
            arc_mask, arc_mask_anchor_x, arc_mask_anchor_y = arc_masks[char]
            paste_x_mask = arc_anchor_x - arc_mask_anchor_x
            paste_y_mask = arc_anchor_y - arc_mask_anchor_y
            
            content_mask = Image.new("L", (content_width, content_height), 0)
            content_mask.paste(arc_mask, (paste_x_mask, paste_y_mask))
            
        else:
            # Обычный текст
            if char not in all_metrics:
                continue
            metrics = all_metrics[char]
            content_mask = Image.new("L", (content_width, content_height), 0)
            draw = ImageDraw.Draw(content_mask)
            
            if settings.text_alignment == "left":
                text_x = -metrics['left']
            elif settings.text_alignment == "right":
                text_x = content_width - metrics['width'] - metrics['left']
            else:
                text_x = (content_width - metrics['width']) / 2 - metrics['left']
            
            text_y = max_ascent
            draw.text((text_x, text_y), char, font=font, anchor="ls", fill=255)
        
        # Масштабирование по X
        if scaled_content_width != content_width:
            content_mask = content_mask.resize((scaled_content_width, content_height), 
                                               Image.Resampling.LANCZOS)
        
        # Вставка в холст с отступами
        text_mask = Image.new("L", (base_width, base_height), 0)
        text_mask.paste(content_mask, (text_base_x, text_base_y))
        
        char_layer = Image.new("RGBA", (base_width, base_height), transp_bg)
        base_mask = text_mask
        
        # --- Геометрические искажения (для halftone) ---
        will_warp = (settings.rotation_angle != 0 or
                     (settings.skew_enabled and (settings.skew_x != 0 or settings.skew_y != 0)) or
                     (settings.perspective_enabled and (settings.perspective_x != 0 or settings.perspective_y != 0)))
        
        # --- Halftone (до искажений) ---
        fill_mask = base_mask
        if settings.halftone_enabled and not settings.transparent_text and not will_warp:
            fill_mask = apply_halftone(base_mask, settings.halftone_cell_size,
                                      settings.halftone_dot_scale, settings.halftone_angle)
        
        # --- Заливка ---
        if not settings.transparent_text:
            if settings.gradient_enabled:
                char_layer = apply_gradient_fill(char_layer, fill_mask,
                                                 gradient_stops,
                                                 settings.gradient_type,
                                                 settings.gradient_angle)
            else:
                text_fill_layer = Image.new("RGBA", char_layer.size, text_rgb + (255,))
                text_fill_layer.putalpha(fill_mask)
                char_layer = Image.alpha_composite(char_layer, text_fill_layer)
            
            # Паттерн поверх заливки
            if settings.pattern_enabled and pattern_image is not None:
                char_layer = apply_pattern_fill(char_layer, fill_mask, pattern_image,
                                                settings.pattern_scale,
                                                settings.pattern_offset_x,
                                                settings.pattern_offset_y,
                                                settings.pattern_angle,
                                                settings.pattern_blend_mode)
        
        # --- Внутренние эффекты ---
        # Внутренняя обводка
        if settings.outline_inner_enabled and settings.outline_inner_width > 0:
            char_layer = apply_inner_outline(char_layer, base_mask,
                                            settings.outline_inner_color,
                                            settings.outline_inner_width)
        
        # Внутреннее свечение
        if settings.glow_inner_enabled:
            char_layer = apply_inner_glow(char_layer, base_mask,
                                         settings.glow_inner_color,
                                         settings.glow_inner_radius,
                                         settings.glow_inner_intensity,
                                         settings.glow_inner_blend_mode)
        
        # Внутренняя тень
        if settings.inner_shadow_enabled:
            char_layer = apply_inner_shadow(char_layer, base_mask,
                                           settings.inner_shadow_color,
                                           settings.inner_shadow_distance,
                                           settings.inner_shadow_direction,
                                           settings.inner_shadow_blur,
                                           settings.inner_shadow_blend_mode)
        
        # Тиснение
        if settings.emboss_enabled:
            char_layer = apply_emboss(char_layer, base_mask,
                                     settings.emboss_depth,
                                     settings.emboss_blur,
                                     settings.emboss_highlight,
                                     settings.emboss_shadow)
        
        # --- Внешние эффекты ---
        outer_mask = base_mask
        outline_drawn = False
        
        # Внешняя обводка
        if settings.outline_outer_enabled and settings.outline_outer_width > 0:
            char_layer, outer_mask = apply_outer_outline(char_layer, base_mask,
                                                         settings.outline_outer_color,
                                                         settings.outline_outer_width)
            outline_drawn = True
        
        # Внешнее свечение
        if settings.glow_outer_enabled and (not settings.transparent_text or outline_drawn):
            char_layer = apply_outer_glow(char_layer, outer_mask,
                                         settings.glow_outer_color,
                                         settings.glow_outer_radius,
                                         settings.glow_outer_intensity)
        
        # --- Общая прозрачность ---
        if settings.text_opacity < 1.0:
            r, g, b, a = char_layer.split()
            a = a.point(lambda p: int(p * settings.text_opacity))
            char_layer = Image.merge("RGBA", (r, g, b, a))
        
        # --- Поворот ---
        if settings.rotation_angle != 0:
            char_layer = rotate_cleanly(char_layer, -settings.rotation_angle, text_rgb)
        
        # --- Skew ---
        if settings.skew_enabled and (settings.skew_x != 0 or settings.skew_y != 0):
            char_layer = apply_skew_effect(char_layer, settings.skew_x, settings.skew_y, text_rgb)
        
        # --- Perspective ---
        if settings.perspective_enabled and (settings.perspective_x != 0 or settings.perspective_y != 0):
            char_layer = apply_perspective_effect(char_layer, settings.perspective_x,
                                                  settings.perspective_y, text_rgb)
        
        # --- Halftone (после искажений) ---
        if settings.halftone_enabled and not settings.transparent_text and will_warp:
            warped_alpha = char_layer.split()[3]
            halftoned_alpha = apply_halftone(warped_alpha, settings.halftone_cell_size,
                                            settings.halftone_dot_scale, settings.halftone_angle)
            r, g, b, _ = char_layer.split()
            char_layer = Image.merge("RGBA", (r, g, b, halftoned_alpha))
        
        # --- Сборка финального изображения ---
        # Фон
        if settings.transparent_background or settings.background_color is None:
            final_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        else:
            bg_col = settings.background_color
            if isinstance(bg_col, str) and bg_col.startswith('#'):
                bg_col = tuple(int(bg_col.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (255,)
            elif isinstance(bg_col, str):
                bg_col = (255, 255, 255, 255) if bg_col == "white" else (0, 0, 0, 255)
            final_img = Image.new("RGBA", (canvas_w, canvas_h), bg_col)
        
        # Позиция вставки
        paste_x = offset_x + (rot_base_w - char_layer.width) // 2
        paste_y = offset_y + (rot_base_h - char_layer.height) // 2
        
        # --- Тень ---
        if settings.shadow_enabled:
            shadow_rgb = get_color_rgb(settings.shadow_color)
            transp_shadow_bg = shadow_rgb + (0,) if not settings.transparent_text else (0, 0, 0, 0)
            
            shadow_mask = char_layer.split()[3]
            shadow_layer = Image.new("RGBA", char_layer.size, shadow_rgb + (255,))
            shadow_layer.putalpha(shadow_mask)
            
            if settings.shadow_blur > 0:
                shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=settings.shadow_blur))
            
            sh_dx, sh_dy = get_shadow_offset(settings.shadow_direction, settings.shadow_distance)
            shadow_final = Image.new("RGBA", (canvas_w, canvas_h), transp_shadow_bg)
            shadow_final.paste(shadow_layer, (paste_x + sh_dx, paste_y + sh_dy))
            
            # Режим смешивания тени
            effective_blend = settings.shadow_blend_mode
            if settings.transparent_background and settings.shadow_blend_mode in ("multiply", "overlay"):
                effective_blend = "normal"
            
            final_img = blend_layers(final_img, shadow_final, effective_blend)
        
        # --- Вставка текста ---
        layer_text = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        layer_text.paste(char_layer, (paste_x, paste_y))
        final_img = Image.alpha_composite(final_img, layer_text)
        
        # --- Cutout ---
        if not settings.transparent_text and settings.cutout_mode and settings.background_color is not None:
            mask = text_mask.copy()
            if settings.rotation_angle != 0:
                mask = mask.rotate(-settings.rotation_angle, resample=Image.BICUBIC, expand=True)
            mask = mask.point(lambda p: 255 if p > 128 else 0)
            full_mask = Image.new("L", (canvas_w, canvas_h), 0)
            full_mask.paste(mask, (paste_x, paste_y))
            r, g, b, a = final_img.split()
            new_a = Image.composite(Image.new('L', final_img.size, 0), a, full_mask)
            final_img = Image.merge('RGBA', (r, g, b, new_a))
        
        # --- Отражение ---
        if settings.reflection_enabled:
            final_img = apply_reflection(final_img, char_layer, paste_x, paste_y,
                                         settings.background_color,
                                         settings.reflection_gap,
                                         settings.reflection_opacity / 100.0,
                                         settings.reflection_fade / 100.0)
        
        # --- Глитч ---
        if settings.glitch_enabled:
            final_img = apply_glitch_effect(final_img,
                                           settings.glitch_rgb_shift,
                                           settings.glitch_slice_intensity,
                                           seed=(settings.glitch_seed + index) & 0xFFFFFFFF)
        
        # --- Сохранение ---
        suffix = "_cutout" if (settings.transparent_text and settings.cutout_mode) else ""
        base_name = format_filename(settings.filename_template, settings.font_size, index, char)
        candidate = f"{base_name}{suffix}"
        final_name = candidate
        dupe_n = 2
        while final_name in used_filenames:
            final_name = f"{candidate}_{dupe_n}"
            dupe_n += 1
        used_filenames.add(final_name)
        
        output_filename = os.path.join("output", f"{final_name}.png")
        final_img.save(output_filename, "PNG")
        generated_files.append(output_filename)
        
        # --- LVGL .bin ---
        if settings.create_bin:
            from render.lvgl import save_lvgl_v8_bin
            bin_dir = os.path.join("output", "bin")
            os.makedirs(bin_dir, exist_ok=True)
            bin_filename = os.path.join(bin_dir, f"{final_name}.bin")
            save_lvgl_v8_bin(np.array(final_img.convert("RGBA")), bin_filename,
                            color_depth=32, has_alpha=True, swap_16=False)
        
        if progress_callback:
            progress_callback(index, total)
    
    return generated_files


def _calc_outer_effects_width(settings):
    """Вычисляет ширину внешних эффектов для отступа."""
    width = 0
    if settings.outline_outer_enabled:
        width += settings.outline_outer_width
    if settings.glow_outer_enabled:
        width += settings.glow_outer_radius
    if settings.shadow_enabled:
        width += settings.shadow_blur
    return width


def render_arc_characters(characters, settings, progress_callback=None):
    """
    Рендер текста по дуге/окружности (отдельная функция для совместимости).
    """
    # Просто вызываем основную функцию с включённым arc_text_enabled
    # Это нужно для случаев, когда вызывается напрямую
    old_arc_enabled = settings.arc_text_enabled
    settings.arc_text_enabled = True
    result = render_text_characters(characters, settings, progress_callback)
    settings.arc_text_enabled = old_arc_enabled
    return result