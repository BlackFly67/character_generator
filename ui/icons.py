# -*- coding: utf-8 -*-
"""
Каталог иконок для FX-сетки (ui/fx_grid.py).

Иконки теперь рендерятся НА ЛЕТУ через ui/effect_icon.py —
буква «A» с эффектом, без статических PNG. Этот модуль больше
НЕ хранит Unicode-символы для отрисовки — они стали не нужны.

Здесь остались только:
  - RAIL_ICONS[panel_id] → tooltip_key (i18n-ключ названия эффекта);
  - FX_GROUPS — порядок эффектов в сетке (по стадиям);
  - ENABLEABLE_IDS — множество эффектов, у которых есть флаг
    "включён" (f"{id}_enabled" в settings).

get_icon(panel_id) возвращает строку (tooltip_key), чтобы
вызывающий код не распаковывал кортеж.
"""

# panel_id -> tooltip_key (i18n)
RAIL_ICONS = {
    # --- Fill ---
    "gradient":         "gradient_fill",
    "pattern":          "pattern_fill",

    # --- Inner ---
    "outline_inner":    "outline_inner",
    "glow_inner":       "glow_inner",
    "emboss":           "emboss",
    "inner_shadow":     "inner_shadow",

    # --- Outer ---
    "outline_outer":    "outline_outer",
    "glow_outer":       "glow_outer",
    "extrude":          "extrude",
    "shadow":           "shadow",

    # --- Geometry ---
    "skew":             "skew",
    "perspective":      "perspective",

    # --- Post ---
    "reflection":       "reflection",
    "halftone":         "halftone",
    "glitch":           "glitch",
}


# Группы FX-сетки в порядке отображения.
# Визуально на экране группы НЕ разделяются — иконки идут одним
# потоком, а этот список задаёт лишь порядок.
FX_GROUPS = [
    ("group_fill",     ["gradient", "pattern"]),
    ("group_inner",    ["outline_inner", "glow_inner", "emboss", "inner_shadow"]),
    ("group_outer",    ["outline_outer", "glow_outer", "extrude", "shadow"]),
    ("group_geometry", ["skew", "perspective"]),
    ("group_post",     ["reflection", "halftone", "glitch"]),
]


# id эффектов, у которых есть "включаемость" (f"{id}_enabled" в settings).
ENABLEABLE_IDS = {
    "gradient", "pattern",
    "outline_inner", "glow_inner", "emboss", "inner_shadow",
    "outline_outer", "glow_outer", "extrude", "shadow",
    "skew", "perspective",
    "reflection", "halftone", "glitch",
}


def get_icon(panel_id):
    """
    Возвращает tooltip_key (i18n) для panel_id.
    Если panel_id нет в RAIL_ICONS — возвращает сам panel_id как
    fallback (i18n.tr вернёт его как есть).
    """
    return RAIL_ICONS.get(panel_id, panel_id)