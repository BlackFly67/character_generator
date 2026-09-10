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

# geometry
from effects.skew import Skew
from effects.perspective import Perspective

# post
from effects.reflection import Reflection
from effects.glitch import Glitch


PIPELINE = [
    # ---- fill ----
    ColorFill,
    GradientFill,
    PatternFill,
    HalftoneMask,

    # ---- inner ----
    OutlineInner,
    GlowInner,
    ShadowInner,
    Emboss,

    # ---- outer ----
    OutlineOuter,
    GlowOuter,

    # ---- geometry ----
    Skew,
    Perspective,

    # ---- post ----
    Reflection,
    Glitch,
]


ALL_EFFECTS = {cls.id: cls for cls in PIPELINE}


def get_effect(effect_id):
    return ALL_EFFECTS.get(effect_id)


def get_by_stage(stage):
    return [cls for cls in PIPELINE if cls.stage == stage]