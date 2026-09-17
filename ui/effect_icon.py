# -*- coding: utf-8 -*-
"""
Рендер FX-иконок на лету.

Каждая иконка — буква «A» с одним включённым эффектом, отрендеренная
через compose_full прямо в памяти (без сохранения PNG).

Сами цвета пресетов (градиент/свечение/emboss/extrude и т.п.) НЕ
перекрашиваются под тему — это цвета конкретного эффекта, они полезны
как визуальная подсказка "что это за эффект". Но ДВЕ вещи от темы
зависят: (1) насыщенность приглушена общим множителем ICON_SATURATION,
чтобы плитки не выбивались из синей темы приложения "конфетти"-цветами;
(2) базовый цвет буквы для пресетов, не перекрашивающих text_color сами
(outline_inner/outer, skew, perspective), берётся по текущей теме —
тёмный на светлом фоне, светлый на тёмном (см. _TEXT_COLOR_BY_MODE).

Кэш: dict[(panel_id, тема), PIL.Image] для базового изображения,
dict[(panel_id, size, тема), ctk.CTkImage] для готовых для UI.
"""

import os
from PIL import Image, ImageEnhance
import customtkinter as ctk

from config import Settings
from fonts import get_default_font
from render.composer import CharSpec, compose_full


# Размер иконки
ICON_RENDER_SIZE = 80      # рендерим крупно (для качества при HiDPI)
ICON_CONTENT = 64          # буква вписана в 64×64
ICON_UI_SIZE = (40, 40)    # отображается в кнопке (32×32)

# ИСПРАВЛЕНО: раньше пресеты рисовали буквы в "конфетти"-насыщенных
# цветах (#e94b3c красный, #f0c400 жёлтый и т.д.) на все 100% —
# рядом с монохромно-синей темой приложения это выглядело как
# чужеродная мозаика. Само различие цветов между эффектами полезно
# (сразу видно, что за эффект), поэтому цвета не убираем совсем —
# просто снижаем насыщенность так, чтобы плитки читались как часть
# приложения, а не отдельный виджет поверх него. 1.0 = без изменений,
# 0.0 = оттенки серого.
ICON_SATURATION = 0.55

# Цвет буквы для тех пресетов, что НЕ перекрашивают текст сами
# (outline_inner/outer, skew, perspective — см. PRESETS ниже, они не
# трогают text_color). ИСПРАВЛЕНО: раньше это был один хардкод
# "#1a1a1a" всегда, независимо от темы — main_window.py._apply_settings()
# вызывал clear_cache() при смене темы с комментарием "иконки
# перекрашиваются под тему", но фактически НИЧЕГО не перерендеривалось
# по-другому: light_image и dark_image в get_effect_icon() указывали
# на ОДИН И ТОТ ЖЕ объект PIL.Image. Проверено побайтовым сравнением
# пикселей до/после смены темы — результат был идентичен. Теперь
# базовый цвет буквы реально зависит от текущей темы (тёмный на
# светлой, светлый на тёмной — как везде в приложении, см. паттерн
# text_color=("#1a1a1a", "#e0e0e0") в других модулях), а кэш учитывает
# режим темы в ключе, так что clear_cache() при смене темы наконец-то
# на что-то влияет.
_TEXT_COLOR_BY_MODE = {"light": "#1a1a1a", "dark": "#e0e0e0"}


def _current_mode():
    try:
        return "dark" if ctk.get_appearance_mode() == "Dark" else "light"
    except Exception:
        return "light"


# ============================================================
#  Пресеты — по одному эффекту на иконку
# ============================================================

def _p_gradient(s):
    s.gradient_enabled = True
    s.gradient_type = "linear"
    s.gradient_angle = 45
    s.gradient_stops = [
        {"pos": 0.0, "color": "#1f538d"},
        {"pos": 1.0, "color": "#e94b3c"},
    ]

def _p_pattern(s):
    s.pattern_enabled = True
    s.pattern_scale = 80
    # Если texture не задан — эффект пропустится; иконка будет как
    # обычная буква A.

def _p_outline_inner(s):
    s.outline_inner_enabled = True
    s.outline_inner_width = 3
    s.outline_inner_color = "#e94b3c"

def _p_outline_outer(s):
    s.outline_outer_enabled = True
    s.outline_outer_width = 3
    s.outline_outer_color = "#e94b3c"

def _p_glow_inner(s):
    s.glow_inner_enabled = True
    s.glow_inner_radius = 5
    s.glow_inner_intensity = 16
    s.glow_inner_color = "#f0c400"

def _p_glow_outer(s):
    s.glow_outer_enabled = True
    s.glow_outer_radius = 7
    s.glow_outer_intensity = 16
    s.glow_outer_color = "#f0c400"

def _p_extrude(s):
    s.extrude_enabled = True
    s.extrude_depth = 6
    s.extrude_angle = 315
    s.extrude_color_near = "#e94b3c"   # красный
    s.extrude_color_far  = "#1f538d"   # синий

def _p_emboss(s):
    s.emboss_enabled = True
    s.emboss_depth = 3
    s.emboss_highlight = "#ffffff"
    s.emboss_shadow = "#000000"

def _p_inner_shadow(s):
    s.inner_shadow_enabled = True
    s.inner_shadow_distance = 4
    s.inner_shadow_color = "#c9c9c9"

def _p_shadow(s):
    s.shadow_enabled = True
    s.shadow_distance = 4
    s.shadow_direction = 8
    s.shadow_blur = 3
    s.shadow_color = "#1f538d" 
    
def _p_skew(s):
    s.skew_enabled = True
    s.skew_x = 20

def _p_perspective(s):
    s.perspective_enabled = True
    s.perspective_x = 50

def _p_reflection(s):
    s.reflection_enabled = True
    s.reflection_gap = 2
    s.reflection_opacity = 70
    s.reflection_fade = 100

def _p_halftone(s):
    s.halftone_enabled = True
    s.halftone_cell_size = 4
    s.halftone_dot_scale = 110

def _p_glitch(s):
    s.glitch_enabled = True
    s.glitch_rgb_shift = 3
    s.glitch_slice_intensity = 50
    s.glitch_seed = 42
    s.text_color = "#f0c400"


PRESETS = {
    "gradient":       _p_gradient,
    "pattern":        _p_pattern,
    "outline_inner":  _p_outline_inner,
    "outline_outer":  _p_outline_outer,
    "glow_inner":     _p_glow_inner,
    "glow_outer":     _p_glow_outer,
    "extrude":        _p_extrude,
    "emboss":         _p_emboss,
    "inner_shadow":   _p_inner_shadow,
    "shadow":         _p_shadow,
    "skew":           _p_skew,
    "perspective":    _p_perspective,
    "reflection":     _p_reflection,
    "halftone":       _p_halftone,
    "glitch":         _p_glitch,
}


# ============================================================
#  Кэш
# ============================================================

_BASE_CACHE = {}    # panel_id -> PIL.Image (RGBA, ICON_RENDER_SIZE²)
_CTK_CACHE = {}     # (panel_id, size) -> ctk.CTkImage


def _make_settings(text_color=None):
    """
    Создать Settings для рендера иконки.

    text_color=None => берём цвет по текущей теме (_current_mode()),
    а не хардкод "#1a1a1a" — см. комментарий у _TEXT_COLOR_BY_MODE
    про то, какой баг это чинит.

    font_path берём из get_default_font() и, если он пуст/невалиден,
    пробуем типичные системные TTF.
    """
    s = Settings()
    s.reset()

    s.text_color = text_color or _TEXT_COLOR_BY_MODE[_current_mode()]
    s.transparent_background = True
    s.background_color = None
    s.transparent_text = False
    s.text_alignment = "center"
    s.font_size = 52

    if not s.font_path:
        s.font_path = get_default_font() or ""

    if not s.font_path or not os.path.exists(s.font_path):
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
        for c in candidates:
            if os.path.exists(c):
                s.font_path = c
                break

    return s


def _apply_saturation(img_rgba, factor):
    """Снижает насыщенность RGBA-изображения, сохраняя альфа-канал."""
    if factor == 1.0:
        return img_rgba
    r, g, b, a = img_rgba.split()
    rgb = ImageEnhance.Color(Image.merge("RGB", (r, g, b))).enhance(factor)
    r2, g2, b2 = rgb.split()
    return Image.merge("RGBA", (r2, g2, b2, a))


def _render_base(panel_id):
    """
    Рендерит базовое изображение иконки (кэшируется по (panel_id, тема)
    — ИСПРАВЛЕНО: раньше кэш был только по panel_id, а text_color внутри
    всегда был хардкод "#1a1a1a" — сколько бы раз ни сменили тему,
    результат оставался тем же самым объектом. Теперь при смене темы
    (_current_mode() меняется) рендерится и кэшируется отдельная версия.
    """
    mode = _current_mode()
    cache_key = (panel_id, mode)
    if cache_key in _BASE_CACHE:
        return _BASE_CACHE[cache_key]

    preset_fn = PRESETS.get(panel_id)
    if preset_fn is None:
        return None

    s = _make_settings()
    preset_fn(s)

    spec = CharSpec(text="Tt", index=1)
    try:
        img = compose_full(spec, s)
    except Exception as e:
        print(f"[effect_icon] {panel_id}: compose_full failed: {e}")
        return None

    bbox = img.split()[3].getbbox()
    if not bbox:
        print(f"[effect_icon] {panel_id}: empty alpha")
        return None

    img = img.crop(bbox)
    img.thumbnail((ICON_CONTENT, ICON_CONTENT), Image.LANCZOS)

    canvas = Image.new("RGBA", (ICON_RENDER_SIZE, ICON_RENDER_SIZE),
                       (0, 0, 0, 0))
    canvas.alpha_composite(img, (
        (ICON_RENDER_SIZE - img.width) // 2,
        (ICON_RENDER_SIZE - img.height) // 2,
    ))

    # Часть варианта "B+D" из обсуждения стилизации: приглушаем
    # насыщенность пресетовых цветов, чтобы плитки не выглядели
    # конфетти на фоне синей темы приложения, но эффекты оставались
    # различимы по цвету.
    canvas = _apply_saturation(canvas, ICON_SATURATION)

    _BASE_CACHE[cache_key] = canvas
    return canvas


def get_effect_icon(panel_id, size=ICON_UI_SIZE):
    """
    Возвращает ctk.CTkImage с цветной иконкой эффекта.

    Никакого tint поверх цветов эффекта — но базовый цвет буквы (для
    пресетов, не перекрашивающих text_color сами) и сама насыщенность
    зависят от темы/настроек — см. _render_base().
    """
    mode = _current_mode()
    key = (panel_id, size, mode)
    if key in _CTK_CACHE:
        return _CTK_CACHE[key]

    base = _render_base(panel_id)

    if base is None:
        ph = Image.new("RGBA", (size[0]*2, size[1]*2), (0, 0, 0, 0))
        ctk_img = ctk.CTkImage(light_image=ph, dark_image=ph, size=size)
        _CTK_CACHE[key] = ctk_img
        return ctk_img

    target = (size[0]*2, size[1]*2)
    resized = base.resize(target, Image.LANCZOS)

    ctk_img = ctk.CTkImage(light_image=resized, dark_image=resized, size=size)
    _CTK_CACHE[key] = ctk_img
    return ctk_img


def clear_cache():
    """Сбросить кэш CTkImage И базовых рендеров (смена размера/темы)."""
    _CTK_CACHE.clear()
    _BASE_CACHE.clear()