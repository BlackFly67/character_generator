# -*- coding: utf-8 -*-
"""
Эффекты для обработки изображений.

Публичный API пакета. Здесь реэкспортируются:
  - классы-эффекты новой системы (GlowOuter, GlowInner) — для реестра
    effects/registry.py и для ручного использования;
  - старые функции эффектов — для обратной совместимости со всем кодом,
    который ещё не мигрирован на классы (composer.py, ui/*.py и т.д.);
  - хелперы из effects/base.py (blend_layers, rotate_cleanly и пр.),
    чтобы ими можно было пользоваться через `from effects import ...`.
"""

# --- Glow: новая система + старые функции под двумя наборами имён ---
from .glow import (
    # классы-эффекты (новая система)
    GlowOuter,
    GlowInner,
    # старые функции под новыми именами
    apply_glow_outer,
    apply_glow_inner,
    # алиасы (см. конец effects/glow.py)
    apply_outer_glow,
    apply_inner_glow,
)

# --- Остальные эффекты (пока без классов, только функции) ---
from .shadow import apply_shadow
from .inner_shadow import apply_inner_shadow
from .outline import apply_outer_outline, apply_inner_outline
from .emboss import apply_emboss
from .gradient import apply_gradient_fill
from .pattern import apply_pattern_fill, load_pattern_image
from .halftone import apply_halftone
from .reflection import apply_reflection
from .glitch import apply_glitch_effect
from .skew import apply_skew_effect
from .perspective import apply_perspective_effect

# --- Хелперы из base ---
from .base import (
    blend_layers,
    rotate_cleanly,
    get_color_rgb,
    get_color_rgba,
    get_shadow_offset,
    create_checkerboard_background,
)


__all__ = [
    # Glow — классы и функции
    'GlowOuter',
    'GlowInner',
    'apply_glow_outer',
    'apply_glow_inner',
    'apply_outer_glow',
    'apply_inner_glow',

    # Остальные эффекты
    'apply_shadow',
    'apply_inner_shadow',
    'apply_outer_outline',
    'apply_inner_outline',
    'apply_emboss',
    'apply_gradient_fill',
    'apply_pattern_fill',
    'load_pattern_image',
    'apply_halftone',
    'apply_reflection',
    'apply_glitch_effect',
    'apply_skew_effect',
    'apply_perspective_effect',

    # Хелперы
    'blend_layers',
    'rotate_cleanly',
    'get_color_rgb',
    'get_color_rgba',
    'get_shadow_offset',
    'create_checkerboard_background',
]