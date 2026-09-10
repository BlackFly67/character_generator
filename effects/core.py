# -*- coding: utf-8 -*-
"""
Ядро системы эффектов.

Здесь только общие типы для построения классов-эффектов:
- EffectBase — базовый класс эффекта
- EffectContext — контекст, передаваемый в apply()
- ParamSpec — описание параметра для UI
- CTRL_* — типы контролов

Этот файл НЕ содержит функций-эффектов и НЕ содержит хелперов
(blend_layers, rotate_cleanly и т.п. — они в effects/base.py).
"""

from dataclasses import dataclass, field
from typing import Any, Optional
from PIL import Image


# ------------------------------------------------------------
# Типы контролов (используются сайдбаром)
# ------------------------------------------------------------
CTRL_CHECKBOX = "checkbox"
CTRL_INT      = "int"
CTRL_FLOAT    = "float"
CTRL_COLOR    = "color"
CTRL_BLEND    = "blend"
CTRL_OPTION   = "option"
CTRL_DIR      = "dir"
CTRL_STOPS    = "stops"     # редактор цветовых точек (задел на gradient)
CTRL_FILE     = "file"      # выбор файла (задел на pattern)


@dataclass
class ParamSpec:
    """Описание одного параметра эффекта для UI."""
    key: str                        # имя поля без префикса effect_id
    label_key: str                  # ключ i18n
    ctrl: str                       # тип контрола (CTRL_*)
    default: Any = None
    min_val: Optional[int] = None
    max_val: Optional[int] = None
    step: int = 1
    values: Optional[list] = None   # для CTRL_OPTION
    suffix: str = ""


@dataclass
class EffectContext:
    """
    Всё, что нужно эффекту для работы. Заменяет длинные сигнатуры
    вроде (image, mask, color, radius, ...).
    """
    settings: Any
    image: Image.Image                 # RGBA-слой, к которому применяем
    mask: Image.Image                  # L-маска контента (силуэт, базовая)
    fill_mask: Image.Image = None      # маска для заливки (может быть halftone)
    outer_mask: Image.Image = None     # расширенная маска (для glow после outline)
    will_warp: bool = False
    extra: dict = field(default_factory=dict)


class EffectBase:
    """
    Базовый класс эффекта.

    Соглашение об именах:
      - поле "включено" в settings — f"{id}_enabled"
      - поле параметра — f"{id}_{param.key}"

    Это позволяет композеру и сайдбару работать в общем виде:
    не нужно вручную прописывать для каждого эффекта список
    его полей в settings.
    """

    id: str = ""
    label_key: str = ""
    stage: str = "inner"     # "fill" | "inner" | "outer" | "geometry" | "post"
    params: list = []        # list[ParamSpec]

    def apply(self, ctx: EffectContext):
        raise NotImplementedError

    # ---------- хелперы для чтения параметров ----------

    def _get(self, ctx, key, default=None):
        return getattr(ctx.settings, f"{self.id}_{key}", default)

    def _enabled(self, ctx):
        return bool(getattr(ctx.settings, f"{self.id}_enabled", False))