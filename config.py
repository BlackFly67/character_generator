# -*- coding: utf-8 -*-
"""
Настройки приложения
"""

import json
import os
from constants import (
    CONFIG_FILE, DEFAULT_FONT_SIZE, DEFAULT_TEXT_COLOR, DEFAULT_BACKGROUND_COLOR,
    DEFAULT_SHADOW_COLOR, DEFAULT_SHADOW_DISTANCE, DEFAULT_SHADOW_BLUR,
    DEFAULT_EMBOSS_DEPTH, DEFAULT_EMBOSS_BLUR, DEFAULT_EMBOSS_HIGHLIGHT,
    DEFAULT_EMBOSS_SHADOW, DEFAULT_OUTLINE_COLOR, DEFAULT_GLOW_COLOR,
    DEFAULT_INNER_SHADOW_COLOR, DEFAULT_GRADIENT_STOPS, DEFAULT_FILENAME_TEMPLATE,
    DEFAULT_ROTATION, DEFAULT_SCALE, DEFAULT_SPACING, DEFAULT_OPACITY,
    DEFAULT_ARC_RADIUS, DEFAULT_INNER_SHADOW_DISTANCE, DEFAULT_INNER_SHADOW_BLUR,
    DEFAULT_REFLECTION_GAP, DEFAULT_REFLECTION_OPACITY, DEFAULT_REFLECTION_FADE,
    DEFAULT_HALFTONE_CELL, DEFAULT_HALFTONE_DOT, DEFAULT_HALFTONE_ANGLE,
    DEFAULT_GLITCH_RGB_SHIFT, DEFAULT_GLITCH_SLICE, DEFAULT_GLITCH_SEED,
    DEFAULT_SKEW, DEFAULT_PERSPECTIVE, DEFAULT_PATTERN_SCALE,
    DEFAULT_PATTERN_OFFSET, DEFAULT_PATTERN_ANGLE
)
from fonts import get_default_font
from utils import safe_color


class Settings:
    """Класс для управления настройками приложения."""

    def __init__(self):
        self.reset()

    def reset(self):
        """Сбрасывает настройки к значениям по умолчанию."""
        # Основные
        self.language = "en"
        self.theme = "dark"
        self.font_path = get_default_font() or ""

        # FIX: больше нет самостоятельного поля font_size — есть два
        # раздельных размера, а свойство font_size ниже резолвит
        # нужное по активному режиму (icon_mode).
        self.text_font_size = DEFAULT_FONT_SIZE
        self.icon_font_size = None

        # Цвета
        self.text_color = DEFAULT_TEXT_COLOR
        self.saved_text_color = DEFAULT_TEXT_COLOR
        self.background_color = DEFAULT_BACKGROUND_COLOR
        self.shadow_color = DEFAULT_SHADOW_COLOR
        self.emboss_highlight = DEFAULT_EMBOSS_HIGHLIGHT
        self.emboss_shadow = DEFAULT_EMBOSS_SHADOW
        self.outline_outer_color = DEFAULT_OUTLINE_COLOR
        self.outline_inner_color = DEFAULT_OUTLINE_COLOR
        self.glow_outer_color = DEFAULT_GLOW_COLOR
        self.glow_inner_color = DEFAULT_GLOW_COLOR
        self.inner_shadow_color = DEFAULT_INNER_SHADOW_COLOR

        # Флаги
        self.transparent_background = True
        self.transparent_text = False
        self.cutout_mode = False
        self.shadow_enabled = False
        self.emboss_enabled = False
        self.outline_outer_enabled = False
        self.outline_inner_enabled = False
        self.glow_outer_enabled = False
        self.glow_inner_enabled = False
        self.gradient_enabled = False
        self.pattern_enabled = False
        self.inner_shadow_enabled = False
        self.arc_text_enabled = False
        self.halftone_enabled = False
        self.glitch_enabled = False
        self.skew_enabled = False
        self.perspective_enabled = False
        self.reflection_enabled = False
        self.create_bin = False
        self.canvas_width_enabled = False
        self.icon_mode = False

        # Числовые параметры
        self.shadow_distance = DEFAULT_SHADOW_DISTANCE
        self.shadow_direction = 8
        self.shadow_blur = DEFAULT_SHADOW_BLUR
        self.rotation_angle = DEFAULT_ROTATION
        self.text_alignment = "center"
        self.emboss_depth = DEFAULT_EMBOSS_DEPTH
        self.emboss_blur = DEFAULT_EMBOSS_BLUR
        self.outline_outer_width = 2
        self.outline_inner_width = 1
        self.glow_outer_radius = 5
        self.glow_outer_intensity = 10
        self.glow_inner_radius = 3
        self.glow_inner_intensity = 10
        self.text_opacity = 1.0
        self.text_scale_x = 1.0
        self.letter_spacing = 0
        self.gradient_angle = 0
        self.gradient_type = "linear"
        self.gradient_stops = [dict(s) for s in DEFAULT_GRADIENT_STOPS]
        self.pattern_scale = DEFAULT_PATTERN_SCALE
        self.pattern_offset_x = DEFAULT_PATTERN_OFFSET
        self.pattern_offset_y = DEFAULT_PATTERN_OFFSET
        self.pattern_angle = DEFAULT_PATTERN_ANGLE
        self.pattern_image_path = None
        self.pattern_blend_mode = "normal"
        self.inner_shadow_distance = DEFAULT_INNER_SHADOW_DISTANCE
        self.inner_shadow_direction = 8
        self.inner_shadow_blur = DEFAULT_INNER_SHADOW_BLUR
        self.shadow_blend_mode = "normal"
        self.glow_inner_blend_mode = "normal"
        self.inner_shadow_blend_mode = "normal"
        self.arc_radius = DEFAULT_ARC_RADIUS
        self.arc_start_angle = 0
        self.arc_clockwise = True
        self.arc_flip = False
        self.halftone_cell_size = DEFAULT_HALFTONE_CELL
        self.halftone_dot_scale = DEFAULT_HALFTONE_DOT
        self.halftone_angle = DEFAULT_HALFTONE_ANGLE
        self.glitch_rgb_shift = DEFAULT_GLITCH_RGB_SHIFT
        self.glitch_slice_intensity = DEFAULT_GLITCH_SLICE
        self.glitch_seed = DEFAULT_GLITCH_SEED
        self.skew_x = DEFAULT_SKEW
        self.skew_y = DEFAULT_SKEW
        self.perspective_x = DEFAULT_PERSPECTIVE
        self.perspective_y = DEFAULT_PERSPECTIVE
        self.reflection_gap = DEFAULT_REFLECTION_GAP
        self.reflection_opacity = DEFAULT_REFLECTION_OPACITY
        self.reflection_fade = DEFAULT_REFLECTION_FADE
        self.canvas_width_delta = 0

        # Текст и иконки
        self.characters = ""
        self.icon_paths = []
        self.filename_template = DEFAULT_FILENAME_TEMPLATE

    # ============================================================
    #  font_size как property
    # ============================================================

    @property
    def font_size(self):
        """
        Активный размер шрифта: text_font_size или icon_font_size в
        зависимости от icon_mode. Если для режима иконок размер ещё не
        задан (None), возвращаем text_font_size — так при первом входе
        в режим иконок без загруженных иконок приложение получает
        осмысленное значение, а не падает.

        Все присваивания settings.font_size = X попадают в правильное
        поле — не нужно синхронизировать вручную в main_window.
        """
        if getattr(self, "icon_mode", False):
            if self.icon_font_size is None:
                return self.text_font_size if self.text_font_size is not None else DEFAULT_FONT_SIZE
            return self.icon_font_size
        return self.text_font_size if self.text_font_size is not None else DEFAULT_FONT_SIZE

    @font_size.setter
    def font_size(self, value):
        if getattr(self, "icon_mode", False):
            self.icon_font_size = value
        else:
            self.text_font_size = value

    def to_dict(self):
        """Преобразует настройки в словарь для сохранения."""
        return {
            "language": self.language,
            "theme": self.theme,
            "text_color": self.text_color,
            "background_color": self.background_color,
            "transparent_background": self.transparent_background,
            "transparent_text": self.transparent_text,
            "cutout_mode": self.cutout_mode,
            "shadow_enabled": self.shadow_enabled,
            "shadow_color": self.shadow_color,
            "shadow_distance": self.shadow_distance,
            "shadow_direction": self.shadow_direction,
            "shadow_blur": self.shadow_blur,
            # FIX: пишем только text_font_size и icon_font_size, "font_size"
            # больше не самостоятельное поле — при загрузке старых конфигов
            # его значение мигрирует в text_font_size (см. from_dict).
            "text_font_size": self.text_font_size,
            "icon_font_size": self.icon_font_size,
            "rotation_angle": self.rotation_angle,
            "text_alignment": self.text_alignment,
            "font_path": self.font_path,
            "emboss_enabled": self.emboss_enabled,
            "emboss_depth": self.emboss_depth,
            "emboss_blur": self.emboss_blur,
            "emboss_highlight": self.emboss_highlight,
            "emboss_shadow": self.emboss_shadow,
            "outline_outer_enabled": self.outline_outer_enabled,
            "outline_outer_color": self.outline_outer_color,
            "outline_outer_width": self.outline_outer_width,
            "outline_inner_enabled": self.outline_inner_enabled,
            "outline_inner_color": self.outline_inner_color,
            "outline_inner_width": self.outline_inner_width,
            "glow_outer_enabled": self.glow_outer_enabled,
            "glow_outer_color": self.glow_outer_color,
            "glow_outer_radius": self.glow_outer_radius,
            "glow_outer_intensity": self.glow_outer_intensity,
            "glow_inner_enabled": self.glow_inner_enabled,
            "glow_inner_color": self.glow_inner_color,
            "glow_inner_radius": self.glow_inner_radius,
            "glow_inner_intensity": self.glow_inner_intensity,
            "text_opacity": self.text_opacity,
            "text_scale_x": self.text_scale_x,
            "letter_spacing": self.letter_spacing,
            "characters": self.characters,
            "gradient_enabled": self.gradient_enabled,
            "gradient_stops": self.gradient_stops,
            "gradient_type": self.gradient_type,
            "gradient_angle": self.gradient_angle,
            "pattern_enabled": self.pattern_enabled,
            "pattern_image_path": self.pattern_image_path,
            "pattern_scale": self.pattern_scale,
            "pattern_offset_x": self.pattern_offset_x,
            "pattern_offset_y": self.pattern_offset_y,
            "pattern_angle": self.pattern_angle,
            "pattern_blend_mode": self.pattern_blend_mode,
            "inner_shadow_enabled": self.inner_shadow_enabled,
            "inner_shadow_color": self.inner_shadow_color,
            "inner_shadow_distance": self.inner_shadow_distance,
            "inner_shadow_direction": self.inner_shadow_direction,
            "inner_shadow_blur": self.inner_shadow_blur,
            "shadow_blend_mode": self.shadow_blend_mode,
            "glow_inner_blend_mode": self.glow_inner_blend_mode,
            "inner_shadow_blend_mode": self.inner_shadow_blend_mode,
            "arc_text_enabled": self.arc_text_enabled,
            "arc_radius": self.arc_radius,
            "arc_start_angle": self.arc_start_angle,
            "arc_clockwise": self.arc_clockwise,
            "arc_flip": self.arc_flip,
            "halftone_enabled": self.halftone_enabled,
            "halftone_cell_size": self.halftone_cell_size,
            "halftone_dot_scale": self.halftone_dot_scale,
            "halftone_angle": self.halftone_angle,
            "glitch_enabled": self.glitch_enabled,
            "glitch_rgb_shift": self.glitch_rgb_shift,
            "glitch_slice_intensity": self.glitch_slice_intensity,
            "glitch_seed": self.glitch_seed,
            "skew_enabled": self.skew_enabled,
            "skew_x": self.skew_x,
            "skew_y": self.skew_y,
            "perspective_enabled": self.perspective_enabled,
            "perspective_x": self.perspective_x,
            "perspective_y": self.perspective_y,
            "reflection_enabled": self.reflection_enabled,
            "reflection_gap": self.reflection_gap,
            "reflection_opacity": self.reflection_opacity,
            "reflection_fade": self.reflection_fade,
            "filename_template": self.filename_template,
            "icon_mode": self.icon_mode,
            "icon_paths": self.icon_paths,
            "create_bin": self.create_bin,
            "canvas_width_enabled": self.canvas_width_enabled,
            "canvas_width": self.canvas_width_delta
        }

    def from_dict(self, data):
        """Загружает настройки из словаря."""
        if not data:
            return

        # Основные
        self.language = data.get("language", "en")
        self.theme = data.get("theme", "dark")
        self.font_path = data.get("font_path", get_default_font() or "")

        # FIX: раздельные размеры с миграцией старого "font_size".
        # Если в конфиге есть text_font_size — берём его; иначе, если
        # есть legacy-поле "font_size" (старые конфиги), используем его
        # как text_font_size. icon_font_size — None по умолчанию, чтобы
        # при первом входе в режим иконок сработал автоподбор по нативной
        # иконке (default_icon_font_size).
        legacy_font_size = data.get("font_size", DEFAULT_FONT_SIZE)
        self.text_font_size = data.get("text_font_size", legacy_font_size)
        self.icon_font_size = data.get("icon_font_size", None)

        # Цвета
        self.text_color = safe_color(data.get("text_color", DEFAULT_TEXT_COLOR), DEFAULT_TEXT_COLOR)
        self.saved_text_color = self.text_color if self.text_color != "transparent" else DEFAULT_TEXT_COLOR
        self.background_color = safe_color(data.get("background_color", None), None)
        self.shadow_color = safe_color(data.get("shadow_color", DEFAULT_SHADOW_COLOR), DEFAULT_SHADOW_COLOR)
        self.emboss_highlight = safe_color(data.get("emboss_highlight", DEFAULT_EMBOSS_HIGHLIGHT), DEFAULT_EMBOSS_HIGHLIGHT)
        self.emboss_shadow = safe_color(data.get("emboss_shadow", DEFAULT_EMBOSS_SHADOW), DEFAULT_EMBOSS_SHADOW)
        self.outline_outer_color = safe_color(data.get("outline_outer_color", DEFAULT_OUTLINE_COLOR), DEFAULT_OUTLINE_COLOR)
        self.outline_inner_color = safe_color(data.get("outline_inner_color", DEFAULT_OUTLINE_COLOR), DEFAULT_OUTLINE_COLOR)
        self.glow_outer_color = safe_color(data.get("glow_outer_color", DEFAULT_GLOW_COLOR), DEFAULT_GLOW_COLOR)
        self.glow_inner_color = safe_color(data.get("glow_inner_color", DEFAULT_GLOW_COLOR), DEFAULT_GLOW_COLOR)
        self.inner_shadow_color = safe_color(data.get("inner_shadow_color", DEFAULT_INNER_SHADOW_COLOR), DEFAULT_INNER_SHADOW_COLOR)

        # Флаги
        self.transparent_background = data.get("transparent_background", True)
        self.transparent_text = data.get("transparent_text", False)
        self.cutout_mode = data.get("cutout_mode", False)
        self.shadow_enabled = data.get("shadow_enabled", False)
        self.emboss_enabled = data.get("emboss_enabled", False)
        self.outline_outer_enabled = data.get("outline_outer_enabled", False)
        self.outline_inner_enabled = data.get("outline_inner_enabled", False)
        self.glow_outer_enabled = data.get("glow_outer_enabled", False)
        self.glow_inner_enabled = data.get("glow_inner_enabled", False)
        self.gradient_enabled = data.get("gradient_enabled", False)
        self.pattern_enabled = data.get("pattern_enabled", False)
        self.inner_shadow_enabled = data.get("inner_shadow_enabled", False)
        self.arc_text_enabled = data.get("arc_text_enabled", False)
        self.halftone_enabled = data.get("halftone_enabled", False)
        self.glitch_enabled = data.get("glitch_enabled", False)
        self.skew_enabled = data.get("skew_enabled", False)
        self.perspective_enabled = data.get("perspective_enabled", False)
        self.reflection_enabled = data.get("reflection_enabled", False)
        self.create_bin = data.get("create_bin", False)
        self.canvas_width_enabled = data.get("canvas_width_enabled", False)
        self.icon_mode = data.get("icon_mode", False)

        # Числовые параметры
        self.shadow_distance = data.get("shadow_distance", DEFAULT_SHADOW_DISTANCE)
        self.shadow_direction = data.get("shadow_direction", 8)
        self.shadow_blur = data.get("shadow_blur", DEFAULT_SHADOW_BLUR)
        self.rotation_angle = data.get("rotation_angle", DEFAULT_ROTATION)
        self.text_alignment = data.get("text_alignment", "center")
        self.emboss_depth = data.get("emboss_depth", DEFAULT_EMBOSS_DEPTH)
        self.emboss_blur = data.get("emboss_blur", DEFAULT_EMBOSS_BLUR)
        self.outline_outer_width = data.get("outline_outer_width", 2)
        self.outline_inner_width = data.get("outline_inner_width", 1)
        self.glow_outer_radius = data.get("glow_outer_radius", 5)
        self.glow_outer_intensity = data.get("glow_outer_intensity", 10)
        self.glow_inner_radius = data.get("glow_inner_radius", 3)
        self.glow_inner_intensity = data.get("glow_inner_intensity", 10)
        self.text_opacity = data.get("text_opacity", 1.0)
        self.text_scale_x = data.get("text_scale_x", 1.0)
        self.letter_spacing = data.get("letter_spacing", 0)
        self.gradient_angle = data.get("gradient_angle", 0)
        self.gradient_type = data.get("gradient_type", "linear")

        # Градиентные точки
        raw_stops = data.get("gradient_stops") or [dict(s) for s in DEFAULT_GRADIENT_STOPS]
        self.gradient_stops = []
        for s in raw_stops:
            try:
                pos = max(0.0, min(1.0, float(s.get("pos", 0.0))))
                color = safe_color(s.get("color", "#ff0000"), "#ff0000")
                self.gradient_stops.append({"pos": pos, "color": color})
            except (TypeError, ValueError, AttributeError):
                continue
        if len(self.gradient_stops) < 2:
            self.gradient_stops = [dict(s) for s in DEFAULT_GRADIENT_STOPS]

        # Pattern
        self.pattern_image_path = data.get("pattern_image_path", None)
        self.pattern_scale = data.get("pattern_scale", DEFAULT_PATTERN_SCALE)
        self.pattern_offset_x = data.get("pattern_offset_x", DEFAULT_PATTERN_OFFSET)
        self.pattern_offset_y = data.get("pattern_offset_y", DEFAULT_PATTERN_OFFSET)
        self.pattern_angle = data.get("pattern_angle", DEFAULT_PATTERN_ANGLE)
        self.pattern_blend_mode = data.get("pattern_blend_mode", "normal")

        # Внутренняя тень
        self.inner_shadow_distance = data.get("inner_shadow_distance", DEFAULT_INNER_SHADOW_DISTANCE)
        self.inner_shadow_direction = data.get("inner_shadow_direction", 8)
        self.inner_shadow_blur = data.get("inner_shadow_blur", DEFAULT_INNER_SHADOW_BLUR)

        # Режимы смешивания
        self.shadow_blend_mode = data.get("shadow_blend_mode", "normal")
        self.glow_inner_blend_mode = data.get("glow_inner_blend_mode", "normal")
        self.inner_shadow_blend_mode = data.get("inner_shadow_blend_mode", "normal")

        # Текст по дуге
        self.arc_radius = data.get("arc_radius", DEFAULT_ARC_RADIUS)
        self.arc_start_angle = data.get("arc_start_angle", 0)
        self.arc_clockwise = data.get("arc_clockwise", True)
        self.arc_flip = data.get("arc_flip", False)

        # Halftone
        self.halftone_cell_size = data.get("halftone_cell_size", DEFAULT_HALFTONE_CELL)
        self.halftone_dot_scale = data.get("halftone_dot_scale", DEFAULT_HALFTONE_DOT)
        self.halftone_angle = data.get("halftone_angle", DEFAULT_HALFTONE_ANGLE)

        # Глитч
        self.glitch_rgb_shift = data.get("glitch_rgb_shift", DEFAULT_GLITCH_RGB_SHIFT)
        self.glitch_slice_intensity = data.get("glitch_slice_intensity", DEFAULT_GLITCH_SLICE)
        self.glitch_seed = data.get("glitch_seed", DEFAULT_GLITCH_SEED)

        # Скос
        self.skew_x = data.get("skew_x", DEFAULT_SKEW)
        self.skew_y = data.get("skew_y", DEFAULT_SKEW)

        # Перспектива
        self.perspective_x = data.get("perspective_x", DEFAULT_PERSPECTIVE)
        self.perspective_y = data.get("perspective_y", DEFAULT_PERSPECTIVE)

        # Отражение
        self.reflection_gap = data.get("reflection_gap", DEFAULT_REFLECTION_GAP)
        self.reflection_opacity = data.get("reflection_opacity", DEFAULT_REFLECTION_OPACITY)
        self.reflection_fade = data.get("reflection_fade", DEFAULT_REFLECTION_FADE)

        # Текст и иконки
        self.characters = data.get("characters", "")
        self.icon_paths = list(data.get("icon_paths", []))
        self.filename_template = data.get("filename_template", DEFAULT_FILENAME_TEMPLATE)
        self.canvas_width_delta = data.get("canvas_width", 0)

    def load(self, default_config=None):
        """Загружает настройки из файла."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.from_dict(data)
                    return
            except Exception:
                pass

        # Если файла нет или он повреждён, используем дефолтные
        self.reset()

    def save(self):
        """Сохраняет настройки в файл."""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception:
            pass