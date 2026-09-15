# -*- coding: utf-8 -*-
"""
Каталог иконок и групп для левой колонки (rail).

Иконки — временно текстовые (Unicode / буквы). Позже заменятся
на графические (PNG/SVG) — интерфейс останется тем же:
  RAIL_ICONS[effect_id] = (symbol, tooltip_key)
  RAIL_GROUPS = [(group_id, [effect_id, ...]), ...]
"""

# (symbol, tooltip_label_key)
RAIL_ICONS = {
    # --- Base (ручные секции) ---
    "font":             ("Aa",  "font"),
    "style_text":       ("◨",   "text_color"),

    # --- Fill ---
    "color_fill":       ("■",   "text_color"),
    "gradient":         ("▤",   "gradient_fill"),
    "pattern":          ("▦",   "pattern_fill"),
    "halftone":         ("⁙",   "halftone"),

    # --- Inner ---
    "outline_inner":    ("◉",   "outline_inner"),
    "glow_inner":       ("✦",   "glow_inner"),
    "inner_shadow":     ("◐",   "inner_shadow"),
    "emboss":           ("⬓",   "emboss"),

    # --- Outer ---
    "outline_outer":    ("◎",   "outline_outer"),
    "glow_outer":       ("✧",   "glow_outer"),
    "extrude":          ("⬒",   "extrude"),

    # --- Geometry ---
    "skew":             ("⟋",   "skew"),
    "perspective":      ("⬔",   "perspective"),
    "rotation":         ("↻",   "rotation"),
    "arc":              ("⌒",   "arc_text"),

    # --- Post ---
    "shadow":           ("☁",   "shadow"),
    "reflection":       ("⤓",   "reflection"),
    "glitch":           ("⚡",   "glitch"),

    # --- Extra (глобальные, вне групп эффектов) ---
    "opacity":          ("◑",   "opacity"),
    "background":       ("▨",   "background"),
}


# Группы в порядке отображения.
# first-group "base" — закреплён сверху, не сворачивается, не скроллится.
# Остальные группы — сворачиваемые (клик по разделителю).
RAIL_GROUPS = [
    ("base",     ["font", "style_text"]),
    ("fill",     ["color_fill", "gradient", "pattern", "halftone"]),
    ("inner",    ["outline_inner", "glow_inner", "inner_shadow", "emboss"]),
    ("outer",    ["outline_outer", "glow_outer", "extrude"]),
    ("geometry", ["skew", "perspective", "rotation", "arc"]),
    ("post",     ["shadow", "reflection", "glitch"]),
    ("extra",    ["opacity", "background"]),
]


# id эффектов, у которых есть "включаемость" (f"{id}_enabled" в
# settings). У остальных (font, style_text, rotation, arc, opacity,
# background, color_fill) флага нет.
ENABLEABLE_IDS = {
    "gradient", "pattern", "halftone",
    "outline_inner", "glow_inner", "inner_shadow", "emboss",
    "outline_outer", "glow_outer", "extrude",
    "skew", "perspective",
    "shadow", "reflection", "glitch",
}


def get_icon(effect_id):
    """Возвращает (symbol, tooltip_key) или ('?', effect_id) как fallback."""
    return RAIL_ICONS.get(effect_id, ("?", effect_id))