# -*- coding: utf-8 -*-
"""
Каталог иконок для FX-сетки (ui/fx_grid.py).

Иконки — Unicode-символы (монохромные), не эмодзи: корректно
рендерятся на Windows/Linux/macOS одним и тем же системным шрифтом
и легко перекрашиваются через text_color.

Формат:
  RAIL_ICONS[panel_id] = (symbol, tooltip_key)

panel_id — id эффекта из effects/registry.py (PIPELINE + POST_COMPOSE_EFFECTS).
Base-разделы (font, style, rotation, arc, opacity, background) сюда
НЕ входят: они живут отдельно, в верхней части правой колонки
(Sidebar), и строятся через ui/manual_sidebar.py.
"""

# (symbol, tooltip_label_key)
RAIL_ICONS = {
    # --- Fill ---
    "gradient":         ("▤",   "gradient_fill"),
    "pattern":          ("▦",   "pattern_fill"),

    # --- Inner ---
    "outline_inner":    ("◉",   "outline_inner"),
    "glow_inner":       ("✦",   "glow_inner"),
    "emboss":           ("⬓",   "emboss"),
    "inner_shadow":     ("◐",   "inner_shadow"),

    # --- Outer ---
    "outline_outer":    ("◎",   "outline_outer"),
    "glow_outer":       ("✧",   "glow_outer"),
    "extrude":          ("⬒",   "extrude"),
    "shadow":           ("☁",   "shadow"),

    # --- Geometry ---
    "skew":             ("⟋",   "skew"),
    "perspective":      ("⬔",   "perspective"),

    # --- Post ---
    "reflection":       ("⤓",   "reflection"),
    "halftone":         ("⁙",   "halftone"),
    "glitch":           ("⚡",   "glitch"),
}


# Группы FX-сетки в порядке отображения.
# Визуально на экране группы НЕ разделяются — иконки идут одним
# потоком, а этот список задаёт лишь порядок.
#
# i18n-ключи для tooltip: group_fill, group_inner, group_outer,
# group_geometry, group_post.
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
    """Возвращает (symbol, tooltip_key) или ('?', panel_id) как fallback."""
    return RAIL_ICONS.get(panel_id, ("?", panel_id))