# -*- coding: utf-8 -*-
"""
Утилиты: цвета, файлы, изображения
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageChops


def get_color_rgb(color):
    """Преобразует цвет в RGB кортеж."""
    if isinstance(color, str):
        if color.startswith('#'):
            h = color.lstrip('#')
            if len(h) == 6:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            if len(h) == 8:  # RGBA
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        elif color.lower() == 'white':
            return (255, 255, 255)
        elif color.lower() == 'black':
            return (0, 0, 0)
    elif isinstance(color, (tuple, list)):
        return tuple(color[:3])
    return (0, 0, 0)


def get_color_rgba(color):
    """Преобразует цвет в RGBA кортеж."""
    if isinstance(color, str):
        if color == "transparent":
            return (0, 0, 0, 0)
        if color.startswith('#'):
            h = color.lstrip('#')
            if len(h) == 8:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4, 6))
    r, g, b = get_color_rgb(color)
    return (r, g, b, 255)


def safe_color(val, default):
    """
    Безопасно проверяет цвет.

    ИСПРАВЛЕНО (ошибка №7): раньше допускался короткий формат "#fff"
    (len == 4), который get_color_rgb/get_color_rgba не умеют парсить
    (там обрабатываются только len(h) == 6 и len(h) == 8) и который
    молча превращался в чёрный цвет (0, 0, 0). Поддерживаем только
    реально распознаваемые форматы: "#RRGGBB" (7 символов с "#") и
    "#RRGGBBAA" (9 символов с "#"), а также "transparent".
    """
    if isinstance(val, str) and (val == "transparent" or
                                  (val.startswith("#") and len(val) in (7, 9))):
        return val
    return default


def create_checkerboard_background(width, height, cell_size=10):
    """Создаёт шахматный фон для индикации прозрачности."""
    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    for y in range(0, height, cell_size):
        for x in range(0, width, cell_size):
            if (x // cell_size + y // cell_size) % 2 == 0:
                draw.rectangle([x, y, x + cell_size, y + cell_size], 
                               fill=(200, 200, 200, 255))
    return img


def make_safe_filename(s: str) -> str:
    """Создаёт безопасное имя файла."""
    if not s:
        return "empty"
    s = s.replace(" ", "_")
    unsafe_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '\n', '\r', '\t']
    for char in unsafe_chars:
        s = s.replace(char, '_')
    return s.strip('_')[:100].strip('_') or "empty"


def format_filename(template, font_size, index, char):
    """Форматирует имя файла по шаблону."""
    safe_char = make_safe_filename(char)
    tpl = template if template and template.strip() else "{font_size}_{index:02d}_{char}"
    try:
        name = tpl.format(font_size=font_size, index=index, char=safe_char)
    except (KeyError, ValueError, IndexError):
        name = "{font_size}_{index:02d}_{char}".format(
            font_size=font_size, index=index, char=safe_char
        )
    return make_safe_filename(name)


def get_shadow_offset(direction, distance):
    """Возвращает смещение тени для заданного направления."""
    diag = int(distance * 0.707)
    offsets = {
        1: (0, -distance), 2: (0, distance), 3: (-distance, 0), 4: (distance, 0),
        5: (-diag, -diag), 6: (diag, -diag), 7: (-diag, diag), 8: (diag, diag)
    }
    return offsets.get(direction, (0, 0))


def parse_characters(text):
    """Разбирает строку на символы/слова."""
    if not text:
        return []
    if "```" in text:
        return [part.strip() for part in text.split("```") if part.strip()]
    else:
        return text.split()


def blend_layers(base, overlay, mode="normal"):
    """
    Накладывает overlay на base с учётом режима смешивания.
    """
    if mode not in ("multiply", "screen", "overlay") or overlay.mode != "RGBA":
        return Image.alpha_composite(base, overlay)
    
    base_rgb = base.convert("RGB")
    overlay_rgb = overlay.convert("RGB")
    
    if mode == "multiply":
        blended_rgb = ImageChops.multiply(base_rgb, overlay_rgb)
    elif mode == "screen":
        blended_rgb = ImageChops.screen(base_rgb, overlay_rgb)
    else:  # overlay
        try:
            blended_rgb = ImageChops.overlay(base_rgb, overlay_rgb)
        except AttributeError:
            blended_rgb = ImageChops.screen(base_rgb, overlay_rgb)
    
    blended_rgba = blended_rgb.convert("RGBA")
    blended_rgba.putalpha(overlay.split()[3])
    return Image.alpha_composite(base, blended_rgba)


def rotate_cleanly(image, angle, fill_color_rgb=(0, 0, 0)):
    """Поворачивает изображение с раздельной обработкой каналов."""
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    
    r, g, b, a = image.split()
    r = r.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=fill_color_rgb[0])
    g = g.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=fill_color_rgb[1])
    b = b.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=fill_color_rgb[2])
    a = a.rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=0)
    
    return Image.merge("RGBA", (r, g, b, a))
