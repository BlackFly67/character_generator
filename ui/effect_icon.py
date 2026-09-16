# -*- coding: utf-8 -*-
"""
Рендер FX-иконок на лету.

Каждая иконка — буква «A» с одним включённым эффектом, отрендеренная
через compose_full прямо в памяти (без сохранения PNG).

ВАЖНО: иконки НЕ перекрашиваются (никакого tint). Эффекты вроде
градиента, свечения, emboss, extrude видны только в цвете —
монохромный силуэт их «съедает». Контраст с фоном кнопки
обеспечивается светлым/тёмным фоном самой кнопки, а не перекраской.

Кэш: dict[panel_id, PIL.Image] для базового изображения.
"""

import os
from PIL import Image
import customtkinter as ctk

from config import Settings
from fonts import get_default_font
from render.composer import CharSpec, compose_full


# Размер иконки
ICON_RENDER_SIZE = 80      # рендерим крупно (для качества при HiDPI)
ICON_CONTENT = 64          # буква вписана в 64×64
ICON_UI_SIZE = (40, 40)    # отображается в кнопке (32×32)


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


def _make_settings(text_color="#1a1a1a"):
    """
    Создать Settings для рендера иконки.

    font_path берём из get_default_font() и, если он пуст/невалиден,
    пробуем типичные системные TTF.
    """
    s = Settings()
    s.reset()

    s.text_color = text_color
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


def _render_base(panel_id, text_color="#1a1a1a"):
    """Рендерит базовое изображение иконки (кэшируется)."""
    if panel_id in _BASE_CACHE:
        return _BASE_CACHE[panel_id]

    preset_fn = PRESETS.get(panel_id)
    if preset_fn is None:
        return None

    s = _make_settings(text_color)
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

    _BASE_CACHE[panel_id] = canvas
    return canvas


def get_effect_icon(panel_id, size=ICON_UI_SIZE):
    """
    Возвращает ctk.CTkImage с цветной иконкой эффекта.

    Никакого tint — эффекты видны в цвете.
    """
    key = (panel_id, size)
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
    """Сбросить кэш CTkImage (при смене размера или темы)."""
    _CTK_CACHE.clear()