# -*- coding: utf-8 -*-
"""
Работа со шрифтами
"""

import os
import glob
import functools
from PIL import ImageFont


def get_default_font():
    """Возвращает путь к системному шрифту по умолчанию."""
    try:
        ImageFont.truetype("arial.ttf", 64)
        return "arial.ttf"
    except:
        try:
            for font_name in ["Arial", "DejaVuSans", "LiberationSans", "FreeSans"]:
                try:
                    ImageFont.truetype(font_name + ".ttf", 64)
                    return font_name + ".ttf"
                except:
                    continue
        except:
            pass
    return None


def find_system_fonts():
    """
    Находит установленные шрифты в системе.
    Возвращает dict {отображаемое имя: {"path": ..., "family": ..., "style": ...}}
    """
    search_dirs = [
        "C:/Windows/Fonts",
        os.path.expanduser("~/Library/Fonts"),
        "/Library/Fonts",
        "/System/Library/Fonts",
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
        os.path.expanduser("~/.local/share/fonts"),
    ]
    
    found = {}
    for base in search_dirs:
        if not os.path.isdir(base):
            continue
        try:
            for ext in ("*.ttf", "*.otf", "*.ttc"):
                for path in glob.glob(os.path.join(base, "**", ext), recursive=True):
                    family, style = None, ""
                    try:
                        family, style = ImageFont.truetype(path, 16).getname()
                    except Exception:
                        pass
                    
                    if not family:
                        family = os.path.splitext(os.path.basename(path))[0]
                        style = ""
                    
                    style = style or ""
                    if not style or style.lower() == "regular":
                        display_name = family
                    else:
                        display_name = f"{family} {style}"
                    
                    if display_name not in found:
                        found[display_name] = {"path": path, "family": family, "style": style}
        except Exception:
            pass
    
    return dict(sorted(found.items(), key=lambda kv: kv[0].lower()))


def tk_style_from_font_style(style):
    """
    Преобразует стиль шрифта в кортеж стилей для Tk.
    Возвращает кортеж ("bold", "italic") или пустой кортеж.
    """
    s = (style or "").lower()
    words = []
    if any(w in s for w in ("bold", "black", "heavy", "semibold", "extrabold")):
        words.append("bold")
    if any(w in s for w in ("italic", "oblique")):
        words.append("italic")
    return tuple(words)


def load_font_safe(font_path, font_size):
    """Безопасно загружает шрифт."""
    try:
        if font_path and os.path.exists(font_path):
            return ImageFont.truetype(font_path, font_size)
        else:
            system_fonts = [
                "arial.ttf", "Arial.ttf",
                "DejaVuSans.ttf", "FreeSans.ttf",
                "LiberationSans-Regular.ttf"
            ]
            for font_name in system_fonts:
                try:
                    return ImageFont.truetype(font_name, font_size)
                except:
                    continue
            return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


# ============================================================
#  Кэш загруженных шрифтов
# ============================================================

@functools.lru_cache(maxsize=64)
def load_font_safe_cached(font_path, font_size):
    """
    Кэшированная версия load_font_safe. Один и тот же (path, size)
    не перепарсивается с диска повторно. Возвращаемый ImageFont не
    мутируется вызывающим кодом — кэширование безопасно.

    Применяется в render/composer.py — там load_font_safe вызывается
    многократно за один рендер (метрики всех символов батча, метрики
    конкретного символа, арка), и без кэша это превращается в десятки
    парсингов одного и того же TTF с диска.

    Args:
        font_path: путь к TTF/OTF-файлу или None (тогда подбирается
            системный шрифт — см. load_font_safe).
        font_size: размер в пикселях, int.

    Оба аргумента должны быть хешируемыми — это условие lru_cache.
    font_path: str | None, font_size: int — оба хешируемы.
    """
    return load_font_safe(font_path, font_size)


# Системные шрифты (кэшируются при импорте)
SYSTEM_FONTS = find_system_fonts()