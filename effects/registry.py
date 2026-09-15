# -*- coding: utf-8 -*-
"""
Реестр эффектов. Единая точка входа для композера (и в будущем —
сайдбара).

PIPELINE задаёт порядок применения. Стадии:
  fill      — заливка (плоский цвет, градиент, узор, halftone)
  inner     — внутренние эффекты (обводка, свечение, тень, эмбесс)
  outer     — внешние эффекты (обводка, свечение)
  geometry  — трансформации (skew, perspective)
  post      — постобработка готового кадра (reflection, glitch)

Порядок ВНУТРИ стадии тоже важен: он определяет, что поверх чего
рисуется. Менять осторожно.

POST_COMPOSE_EFFECTS — эффекты, которые НЕ участвуют в _run_stage()
и НЕ входят в PIPELINE. Они работают не с char_layer, а с final_img
(фон + эффект + текст) и вызываются вручную из compose_full.
Сейчас это только внешняя тень (ShadowOuter) — она накладывается
между фоном и текстом, поэтому не может жить в общем пайплайне.
UI для них строится тем же build_effect_sections из auto_sidebar.py.
"""

# fill
from effects.fill import ColorFill, GradientFill, PatternFill, HalftoneMask

# inner
from effects.outline import OutlineInner
from effects.glow import GlowInner
from effects.inner_shadow import ShadowInner
from effects.emboss import Emboss

# outer
from effects.outline import OutlineOuter
from effects.glow import GlowOuter
from effects.extrude import Extrude3D
from effects.shadow_outer import ShadowOuter

# geometry
from effects.skew import Skew
from effects.perspective import Perspective

# post
from effects.reflection import Reflection
from effects.glitch import Glitch


PIPELINE = [
    # ---- fill ----
    # HalftoneMask ПЕРВЫМ: он меняет fill_mask ДО заливки, чтобы
    # ColorFill/GradientFill/PatternFill увидели уже растровую маску.
    HalftoneMask,
    ColorFill,
    GradientFill,
    PatternFill,

    # ---- inner ----
    OutlineInner,
    GlowInner,
    ShadowInner,
    Emboss,

    # ---- outer ----
    OutlineOuter,
    Extrude3D,
    GlowOuter,

    # ---- geometry ----
    Skew,
    Perspective,

    # ---- post ----
    Reflection,
    Glitch,
]


# Эффекты, которые НЕ участвуют в _run_stage() и не входят в PIPELINE:
# они работают не с char_layer, а с final_img (фон + тень + текст).
# Вызываются вручную из compose_full.
POST_COMPOSE_EFFECTS = [
    ShadowOuter,
]


ALL_EFFECTS = {cls.id: cls for cls in PIPELINE + POST_COMPOSE_EFFECTS}


def get_effect(effect_id):
    return ALL_EFFECTS.get(effect_id)


def get_by_stage(stage):
    return [cls for cls in PIPELINE if cls.stage == stage]