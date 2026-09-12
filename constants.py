# -*- coding: utf-8 -*-
"""
Константы приложения
"""

APP_VERSION = "v2 6.0.0"
APP_NAME = "Character Image Generator"

# Диапазоны значений
FONT_SIZE_MIN = 1
FONT_SIZE_MAX = 2000
ROTATION_MIN = -180
ROTATION_MAX = 180
SHADOW_DISTANCE_MIN = 0
SHADOW_DISTANCE_MAX = 50
SHADOW_BLUR_MIN = 0
SHADOW_BLUR_MAX = 30
EMBOSS_DEPTH_MIN = 1
EMBOSS_DEPTH_MAX = 20
EMBOSS_BLUR_MIN = 0
EMBOSS_BLUR_MAX = 10
OUTLINE_WIDTH_MIN = 0
OUTLINE_WIDTH_MAX = 20
GLOW_RADIUS_MIN = 1
GLOW_RADIUS_MAX = 30
GLOW_INTENSITY_MIN = 1
GLOW_INTENSITY_MAX = 20
OPACITY_MIN = 0
OPACITY_MAX = 100
SCALE_MIN = -50
SCALE_MAX = 50
SPACING_MIN = -20
SPACING_MAX = 20
ARC_RADIUS_MIN = 1
ARC_RADIUS_MAX = 2000
ARC_ANGLE_MIN = 0
ARC_ANGLE_MAX = 360
INNER_SHADOW_DISTANCE_MIN = 0
INNER_SHADOW_DISTANCE_MAX = 20
INNER_SHADOW_BLUR_MIN = 0
INNER_SHADOW_BLUR_MAX = 30
REFLECTION_GAP_MIN = -500
REFLECTION_GAP_MAX = 500
REFLECTION_OPACITY_MIN = 0
REFLECTION_OPACITY_MAX = 100
REFLECTION_FADE_MIN = 1
REFLECTION_FADE_MAX = 100
HALFTONE_CELL_MIN = 2
HALFTONE_CELL_MAX = 100
HALFTONE_DOT_MIN = 10
HALFTONE_DOT_MAX = 300
HALFTONE_ANGLE_MIN = 0
HALFTONE_ANGLE_MAX = 360
GLITCH_RGB_SHIFT_MIN = 0
GLITCH_RGB_SHIFT_MAX = 30
GLITCH_SLICE_MIN = 0
GLITCH_SLICE_MAX = 100
SKEW_MIN = -75
SKEW_MAX = 75
PERSPECTIVE_MIN = -50
PERSPECTIVE_MAX = 50
PATTERN_SCALE_MIN = 5
PATTERN_SCALE_MAX = 500
PATTERN_OFFSET_MIN = -9999
PATTERN_OFFSET_MAX = 9999
PATTERN_ANGLE_MIN = 0
PATTERN_ANGLE_MAX = 360

# Значения по умолчанию
DEFAULT_FONT_SIZE = 64
DEFAULT_SHADOW_DISTANCE = 5
DEFAULT_SHADOW_BLUR = 2
DEFAULT_EMBOSS_DEPTH = 4
DEFAULT_EMBOSS_BLUR = 1
DEFAULT_OUTLINE_WIDTH = 2
DEFAULT_INNER_OUTLINE_WIDTH = 1
DEFAULT_GLOW_RADIUS = 5
DEFAULT_GLOW_INTENSITY = 10
DEFAULT_INNER_GLOW_RADIUS = 3
DEFAULT_INNER_GLOW_INTENSITY = 10
DEFAULT_OPACITY = 100
DEFAULT_SCALE = 0
DEFAULT_SPACING = 0
DEFAULT_ROTATION = 0
DEFAULT_ARC_RADIUS = 150
DEFAULT_INNER_SHADOW_DISTANCE = 4
DEFAULT_INNER_SHADOW_BLUR = 3
DEFAULT_REFLECTION_GAP = 2
DEFAULT_REFLECTION_OPACITY = 50
DEFAULT_REFLECTION_FADE = 100
DEFAULT_HALFTONE_CELL = 10
DEFAULT_HALFTONE_DOT = 100
DEFAULT_HALFTONE_ANGLE = 0
DEFAULT_GLITCH_RGB_SHIFT = 4
DEFAULT_GLITCH_SLICE = 30
DEFAULT_GLITCH_SEED = 0
DEFAULT_SKEW = 0
DEFAULT_PERSPECTIVE = 0
DEFAULT_PATTERN_SCALE = 100
DEFAULT_PATTERN_OFFSET = 0
DEFAULT_PATTERN_ANGLE = 0

# Цвета по умолчанию
DEFAULT_TEXT_COLOR = "#ffffff"
DEFAULT_BACKGROUND_COLOR = None  # прозрачный
DEFAULT_SHADOW_COLOR = "#808080"
DEFAULT_EMBOSS_HIGHLIGHT = "#ffffff"
DEFAULT_EMBOSS_SHADOW = "#000000"
DEFAULT_OUTLINE_COLOR = "#000000"
DEFAULT_GLOW_COLOR = "#ffffff"
DEFAULT_INNER_SHADOW_COLOR = "#000000"

# Градиент по умолчанию
DEFAULT_GRADIENT_STOPS = [
    {"pos": 0.0, "color": "#ff0000"},
    {"pos": 1.0, "color": "#0000ff"}
]

# Режимы смешивания
BLEND_MODES = ["normal", "multiply", "screen", "overlay"]

# Направления теней
SHADOW_DIRECTIONS = [
    {"value": 5, "symbol": "↖"},
    {"value": 1, "symbol": "↑"},
    {"value": 6, "symbol": "↗"},
    {"value": 3, "symbol": "←"},
    {"value": 0, "symbol": "●"},
    {"value": 4, "symbol": "→"},
    {"value": 7, "symbol": "↙"},
    {"value": 2, "symbol": "↓"},
    {"value": 8, "symbol": "↘"}
]

# Типы градиентов
GRADIENT_TYPES = ["linear", "radial", "angle", "reflected", "diamond"]

# Форматы файлов
IMAGE_EXTENSIONS = (".png", ".bmp", ".gif", ".jpg", ".jpeg", ".webp")
FONT_EXTENSIONS = (".ttf", ".otf", ".ttc", ".pfb", ".pfm", ".fon", ".fnt")

# Шаблон имени файла по умолчанию
DEFAULT_FILENAME_TEMPLATE = "{font_size}_{index:02d}_{char}"

# Конфигурационные файлы
CONFIG_FILE = "config.json"
STYLE_PRESETS_FILE = "style_presets.json"
LANGUAGES_FILE = "languages.json"
PATTERNS_FILE = "patterns.json"

# Текст для превью
PREVIEW_TEXT = "АаБбГг149"

# Константы для иконок
ICON_CANVAS_BASELINE_OVERHEAD = 4

# Параметры LVGL
LVGL_COLOR_DEPTH = 32
LVGL_HAS_ALPHA = True
LVGL_SWAP_16 = False

# ==================== СТИЛЬ ПРЕСЕТЫ ====================

# Ключи, которые сохраняются в пресетах стиля
STYLE_PRESET_KEYS = [
    "text_color", "background_color", "transparent_background", "transparent_text", "cutout_mode",
    "shadow_enabled", "shadow_color", "shadow_distance", "shadow_direction", "shadow_blur", "shadow_blend_mode",
    "emboss_enabled", "emboss_depth", "emboss_blur", "emboss_angle",
    "emboss_highlight", "emboss_shadow",
    "outline_outer_enabled", "outline_outer_color", "outline_outer_width",
    "outline_inner_enabled", "outline_inner_color", "outline_inner_width",
    "glow_outer_enabled", "glow_outer_color", "glow_outer_radius", "glow_outer_intensity",
    "glow_inner_enabled", "glow_inner_color", "glow_inner_radius", "glow_inner_intensity", "glow_inner_blend_mode",
    "text_opacity", "text_scale_x", "letter_spacing",
    "gradient_enabled", "gradient_stops", "gradient_type", "gradient_angle",
    "pattern_enabled", "pattern_image_path", "pattern_scale",
    "pattern_offset_x", "pattern_offset_y", "pattern_angle", "pattern_blend_mode",
    "inner_shadow_enabled", "inner_shadow_color", "inner_shadow_distance", "inner_shadow_direction",
    "inner_shadow_blur", "inner_shadow_blend_mode",
    "reflection_enabled", "reflection_gap", "reflection_opacity", "reflection_fade",
    "halftone_enabled", "halftone_cell_size", "halftone_dot_scale", "halftone_angle",
    "glitch_enabled", "glitch_rgb_shift", "glitch_slice_intensity", "glitch_seed",
]

# ==================== НАСТРОЙКИ ПО УМОЛЧАНИЮ ====================

DEFAULT_CONFIG = {
    "language": "en",
    "theme": "dark",
    "text_color": "#ffffff",
    "background_color": None,
    "transparent_background": True,
    "transparent_text": False,
    "cutout_mode": False,
    "shadow_enabled": False,
    "shadow_color": "#808080",
    "shadow_distance": 5,
    "shadow_direction": 8,
    "shadow_blur": 2,
    "font_size": 64,
    "text_font_size": 64,
    "icon_font_size": None,
    "rotation_angle": 0,
    "text_alignment": "center",
    "font_path": None,
    "emboss_enabled": False,
    "emboss_depth": 4,
    "emboss_blur": 1,
    "emboss_angle": 45,
    "emboss_highlight": "#ffffff",
    "emboss_shadow": "#000000",
    "outline_outer_enabled": False,
    "outline_outer_color": "#000000",
    "outline_outer_width": 2,
    "outline_inner_enabled": False,
    "outline_inner_color": "#000000",
    "outline_inner_width": 1,
    "glow_outer_enabled": False,
    "glow_outer_color": "#ffffff",
    "glow_outer_radius": 5,
    "glow_outer_intensity": 10,
    "glow_inner_enabled": False,
    "glow_inner_color": "#ffffff",
    "glow_inner_radius": 3,
    "glow_inner_intensity": 10,
    "text_opacity": 1.0,
    "text_scale_x": 1.0,
    "letter_spacing": 0,
    "characters": "",
    "gradient_enabled": False,
    "gradient_stops": [{"pos": 0.0, "color": "#ff0000"}, {"pos": 1.0, "color": "#0000ff"}],
    "gradient_type": "linear",
    "gradient_angle": 0,
    "pattern_enabled": False,
    "pattern_image_path": None,
    "pattern_scale": 100,
    "pattern_offset_x": 0,
    "pattern_offset_y": 0,
    "pattern_angle": 0,
    "pattern_blend_mode": "normal",
    "inner_shadow_enabled": False,
    "inner_shadow_color": "#000000",
    "inner_shadow_distance": 4,
    "inner_shadow_direction": 8,
    "inner_shadow_blur": 3,
    "shadow_blend_mode": "normal",
    "glow_inner_blend_mode": "normal",
    "inner_shadow_blend_mode": "normal",
    "arc_text_enabled": False,
    "arc_radius": 150,
    "arc_start_angle": 0,
    "arc_clockwise": True,
    "arc_flip": False,
    "halftone_enabled": False,
    "halftone_cell_size": 10,
    "halftone_dot_scale": 100,
    "halftone_angle": 0,
    "glitch_enabled": False,
    "glitch_rgb_shift": 4,
    "glitch_slice_intensity": 30,
    "glitch_seed": 0,
    "skew_enabled": False,
    "skew_x": 0,
    "skew_y": 0,
    "perspective_enabled": False,
    "perspective_x": 0,
    "perspective_y": 0,
    "reflection_enabled": False,
    "reflection_gap": 2,
    "reflection_opacity": 50,
    "reflection_fade": 100,
    "filename_template": "{font_size}_{index:02d}_{char}",
    "icon_mode": False,
    "icon_paths": [],
    "create_bin": False,
    "canvas_width_enabled": False,
    "canvas_width_delta": 0,
    "saved_background_color": None,
    "saved_text_color": "#ffffff"
}